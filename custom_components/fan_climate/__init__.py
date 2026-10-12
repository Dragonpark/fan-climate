"""Fan Climate Control integration.

Automatically controls a fan entity's speed based on a climate/sensor
entity's temperature reading. When the temperature exceeds a configurable
set point, the fan turns on and increases speed in steps as the
temperature rises.

Exposes a climate entity and number entities for temperature step and speeds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .const import (
    CONF_FAN_ENTITY,
    CONF_NUM_SPEEDS,
    CONF_SET_POINT,
    CONF_TEMP_ENTITY,
    CONF_TEMP_STEP,
    DEFAULT_NUM_SPEEDS,
    DEFAULT_SET_POINT,
    DEFAULT_TEMP_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.NUMBER]


@dataclass
class FanClimateData:
    """Runtime data for a Fan Climate Control config entry."""

    fan_entity: str
    temp_entity: str
    set_point: float
    num_speeds: int
    temp_step: float
    enabled: bool = True
    update_listeners: list[Callable[[], Any]] = field(default_factory=list)

    def register_update_listener(self, listener: Callable[[], Any]) -> Callable[[], None]:
        """Register a callback for when parameters change."""
        self.update_listeners.append(listener)

        def _remove() -> None:
            if listener in self.update_listeners:
                self.update_listeners.remove(listener)

        return _remove

    async def async_notify_listeners(self) -> None:
        """Notify listeners of an update."""
        for listener in list(self.update_listeners):
            res = listener()
            if hasattr(res, "__await__"):
                await res


def calculate_fan_speed(
    current_temp: float,
    set_point: float,
    num_speeds: int,
    temp_step: float,
) -> int:
    """Calculate the desired fan speed level (0 = off).

    Returns a value between 0 and num_speeds (inclusive).
    Speed 0 means the fan should be off.
    Speed 1..num_speeds maps to increasing fan percentages.
    """
    if current_temp < set_point:
        return 0

    diff = current_temp - set_point
    # Speed 1 starts at set_point, speed 2 at set_point + temp_step, etc.
    speed_level = int(diff / temp_step) + 1
    return min(speed_level, num_speeds)


def speed_to_percentage(speed_level: int, num_speeds: int) -> int:
    """Convert a speed level to a fan percentage.

    Uses evenly-spaced percentage steps so the values align with
    Home Assistant's ordered fan speed model.
    """
    if speed_level <= 0 or num_speeds <= 0:
        return 0
    percentage_step = 100 / num_speeds
    return min(round(speed_level * percentage_step), 100)


def _get_temperature(state: State | None) -> float | None:
    """Extract the current temperature from a state object.

    Supports both climate entities (via current_temperature attribute)
    and sensor entities (via state value).
    """
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None

    # Climate entities store temperature in an attribute.
    current_temp = state.attributes.get("current_temperature")
    if current_temp is not None:
        try:
            return float(current_temp)
        except (ValueError, TypeError):
            return None

    # Sensor entities store the value directly in state.
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fan Climate Control from a config entry."""
    data = FanClimateData(
        fan_entity=entry.data[CONF_FAN_ENTITY],
        temp_entity=entry.data[CONF_TEMP_ENTITY],
        set_point=float(entry.data.get(CONF_SET_POINT, DEFAULT_SET_POINT)),
        num_speeds=int(entry.data.get(CONF_NUM_SPEEDS, DEFAULT_NUM_SPEEDS)),
        temp_step=float(entry.data.get(CONF_TEMP_STEP, DEFAULT_TEMP_STEP)),
    )
    entry.runtime_data = data

    # Listen for option changes so the user can tweak thresholds on the fly.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Forward to platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Fan Climate Control config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
