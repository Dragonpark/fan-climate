"""Climate platform for Fan Climate Control.

Exposes a climate entity that mirrors the monitored temperature source,
lets the user adjust the set-point via the thermostat card, and
automatically commands a fan entity at the calculated speed.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    FanClimateData,
    _get_temperature,
    calculate_fan_speed,
    speed_to_percentage,
)
from .const import CONF_SET_POINT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fan Climate Control climate entity."""
    _LOGGER.debug("Setting up Fan Climate Control climate platform")
    async_add_entities([FanClimateEntity(hass, entry)])


class FanClimateEntity(ClimateEntity, RestoreEntity):
    """Climate entity that controls a fan based on temperature."""

    _attr_has_entity_name = True
    _attr_name = None  # Uses the device name directly.
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 32
    _attr_max_temp = 120
    _attr_icon = "mdi:fan-auto"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the climate entity."""
        self._entry = entry
        self._data: FanClimateData = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_temperature_unit = (
            hass.config.units.temperature_unit or UnitOfTemperature.FAHRENHEIT
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fan Climate Control",
            model="Virtual",
        )
        # Defaults – may be overwritten by state restore.
        self._attr_hvac_mode = HVACMode.FAN_ONLY
        self._attr_target_temperature = self._data.set_point
        self._attr_current_temperature: float | None = None
        self._attr_hvac_action = HVACAction.OFF
        self._current_speed: int = 0
        self._current_percentage: int = 0
        self._unsub_listener: Any = None
        self._unsub_data_listener: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore previous state and start listening for temperature changes."""
        await super().async_added_to_hass()

        # Restore previous HVAC mode and target temperature if available.
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if last_state.state in (HVACMode.OFF, HVACMode.FAN_ONLY):
                self._attr_hvac_mode = HVACMode(last_state.state)
                self._data.enabled = self._attr_hvac_mode != HVACMode.OFF
            restored_temp = last_state.attributes.get(ATTR_TEMPERATURE)
            if restored_temp is not None:
                try:
                    self._attr_target_temperature = float(restored_temp)
                    self._data.set_point = self._attr_target_temperature
                except (ValueError, TypeError):
                    pass

        # Register listener for data parameter updates from number entities
        self._unsub_data_listener = self._data.register_update_listener(
            self._handle_data_update
        )

        # Register a listener for the temperature source entity.
        self._unsub_listener = async_track_state_change_event(
            self.hass, [self._data.temp_entity], self._async_on_temp_change
        )

        # Read the current temperature immediately.
        state = self.hass.states.get(self._data.temp_entity)
        temp = _get_temperature(state)
        if temp is not None:
            self._attr_current_temperature = temp
            if self._data.enabled:
                await self._async_update_fan()

        _LOGGER.debug(
            "Fan Climate entity added: fan=%s temp=%s set_point=%.1f speeds=%d step=%.1f",
            self._data.fan_entity,
            self._data.temp_entity,
            self._data.set_point,
            self._data.num_speeds,
            self._data.temp_step,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from entities."""
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        if self._unsub_data_listener:
            self._unsub_data_listener()
            self._unsub_data_listener = None

    @callback
    def _handle_data_update(self) -> None:
        """Handle parameters updated externally (e.g. via number entity)."""
        self.async_write_ha_state()
        if self._data.enabled:
            self.hass.async_create_task(self._async_update_fan())

    # ------------------------------------------------------------------
    # Temperature tracking
    # ------------------------------------------------------------------

    @callback
    def _async_on_temp_change(self, event: Event) -> None:
        """React to temperature entity state changes."""
        new_state = event.data.get("new_state")
        temp = _get_temperature(new_state)
        if temp is None:
            return
        self._attr_current_temperature = temp
        self.async_write_ha_state()
        if self._data.enabled:
            self.hass.async_create_task(self._async_update_fan())

    # ------------------------------------------------------------------
    # Climate actions
    # ------------------------------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Update the set-point temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._attr_target_temperature = temp
        self._data.set_point = temp
        self.async_write_ha_state()

        # Update entry data to persist
        new_data = {**self._entry.data, CONF_SET_POINT: temp}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        if self._data.enabled:
            await self._async_update_fan()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Handle HVAC mode changes (FAN_ONLY = enabled, OFF = disabled)."""
        self._attr_hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            self._data.enabled = False
            self._attr_hvac_action = HVACAction.OFF
            self._current_speed = 0
            self._current_percentage = 0
            self.async_write_ha_state()
            # Turn the fan off when the user disables automation.
            await self.hass.services.async_call(
                "fan",
                "turn_off",
                {"entity_id": self._data.fan_entity},
                blocking=True,
            )
        else:
            self._data.enabled = True
            self.async_write_ha_state()
            await self._async_update_fan()

    # ------------------------------------------------------------------
    # Extra attributes
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose configuration and computed state as extra attributes."""
        return {
            "fan_entity": self._data.fan_entity,
            "temp_entity": self._data.temp_entity,
            "num_speeds": self._data.num_speeds,
            "temp_step": self._data.temp_step,
            "current_speed_level": self._current_speed,
            "current_fan_percentage": self._current_percentage,
        }

    # ------------------------------------------------------------------
    # Fan control
    # ------------------------------------------------------------------

    async def _async_update_fan(self) -> None:
        """Recalculate the desired fan speed and send commands."""
        if self._attr_current_temperature is None:
            return

        speed = calculate_fan_speed(
            self._attr_current_temperature,
            self._data.set_point,
            self._data.num_speeds,
            self._data.temp_step,
        )
        percentage = speed_to_percentage(speed, self._data.num_speeds)

        self._current_speed = speed
        self._current_percentage = percentage

        _LOGGER.debug(
            "Temp %.1f => speed %d/%d (%d%%) for %s",
            self._attr_current_temperature,
            speed,
            self._data.num_speeds,
            percentage,
            self._data.fan_entity,
        )

        if speed == 0:
            self._attr_hvac_action = HVACAction.IDLE
            self.async_write_ha_state()
            await self.hass.services.async_call(
                "fan",
                "turn_off",
                {"entity_id": self._data.fan_entity},
                blocking=True,
            )
        else:
            self._attr_hvac_action = HVACAction.FAN
            self.async_write_ha_state()
            await self.hass.services.async_call(
                "fan",
                "turn_on",
                {"entity_id": self._data.fan_entity},
                blocking=True,
            )
            await self.hass.services.async_call(
                "fan",
                "set_percentage",
                {"entity_id": self._data.fan_entity, "percentage": percentage},
                blocking=True,
            )
