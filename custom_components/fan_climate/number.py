"""Number platform for Fan Climate Control.

Exposes number entities allowing the user to configure:
- Temperature step per speed increase
- Number of fan speeds supported
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FanClimateData
from .const import (
    CONF_NUM_SPEEDS,
    CONF_TEMP_STEP,
    DEFAULT_NUM_SPEEDS,
    DEFAULT_TEMP_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fan Climate Control number entities."""
    _LOGGER.debug("Setting up Fan Climate Control number platform")
    data: FanClimateData = entry.runtime_data
    async_add_entities(
        [
            FanClimateTempStepNumber(hass, entry, data),
            FanClimateNumSpeedsNumber(hass, entry, data),
        ]
    )


class FanClimateTempStepNumber(NumberEntity, RestoreEntity):
    """Number entity to control the temperature step per speed increase."""

    _attr_has_entity_name = True
    _attr_name = "Temperature Step"
    _attr_icon = "mdi:thermometer-chevron-up"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.1
    _attr_native_max_value = 20.0
    _attr_native_step = 0.5

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        data: FanClimateData,
    ) -> None:
        """Initialize the number entity."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_temp_step"
        self._attr_native_unit_of_measurement = (
            hass.config.units.temperature_unit or UnitOfTemperature.FAHRENHEIT
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fan Climate Control",
            model="Virtual",
        )
        self._attr_native_value = float(self._data.temp_step)

    async def async_added_to_hass(self) -> None:
        """Restore previous value if available."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                val = float(last_state.state)
                self._attr_native_value = val
                self._data.temp_step = val
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Update the temperature step."""
        self._attr_native_value = float(value)
        self._data.temp_step = float(value)
        self.async_write_ha_state()

        # Update config entry data so it persists
        new_data = {**self._entry.data, CONF_TEMP_STEP: float(value)}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Notify climate entity to recalculate fan speed immediately
        await self._data.async_notify_listeners()


class FanClimateNumSpeedsNumber(NumberEntity, RestoreEntity):
    """Number entity to control the number of fan speeds supported."""

    _attr_has_entity_name = True
    _attr_name = "Number of Speeds"
    _attr_icon = "mdi:speedometer"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        data: FanClimateData,
    ) -> None:
        """Initialize the number entity."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_num_speeds"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fan Climate Control",
            model="Virtual",
        )
        self._attr_native_value = int(self._data.num_speeds)

    async def async_added_to_hass(self) -> None:
        """Restore previous value if available."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                val = int(float(last_state.state))
                self._attr_native_value = val
                self._data.num_speeds = val
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Update the number of fan speeds."""
        val_int = int(value)
        self._attr_native_value = val_int
        self._data.num_speeds = val_int
        self.async_write_ha_state()

        # Update config entry data so it persists
        new_data = {**self._entry.data, CONF_NUM_SPEEDS: val_int}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Notify climate entity to recalculate fan speed immediately
        await self._data.async_notify_listeners()
