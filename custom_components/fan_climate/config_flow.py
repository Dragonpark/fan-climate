"""Config flow for Fan Climate Control.

Provides a simplified setup wizard requiring only fan and temperature source entities,
auto-detecting the number of fan speeds from the fan's 'percentage_step' attribute,
and allowing post-setup adjustments.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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


def _detect_fan_speeds(hass: Any, fan_entity_id: str) -> int:
    """Auto-detect the number of speeds supported by the fan.

    Calculates speeds as round(100 / percentage_step).
    Defaults to DEFAULT_NUM_SPEEDS if attribute is unavailable or invalid.
    """
    state = hass.states.get(fan_entity_id)
    if state and state.attributes:
        pct_step = state.attributes.get("percentage_step")
        if pct_step is not None:
            try:
                pct_step_val = float(pct_step)
                if pct_step_val > 0:
                    return max(1, round(100.0 / pct_step_val))
            except (ValueError, TypeError, ZeroDivisionError):
                pass
    return DEFAULT_NUM_SPEEDS


def _build_user_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the initial setup schema containing only fan and temp entities."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_FAN_ENTITY,
                default=defaults.get(CONF_FAN_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="fan")
            ),
            vol.Required(
                CONF_TEMP_ENTITY,
                default=defaults.get(CONF_TEMP_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["climate", "sensor"]
                )
            ),
        }
    )


class FanClimateConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Fan Climate Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Ensure the same fan isn't already configured.
            await self.async_set_unique_id(user_input[CONF_FAN_ENTITY])
            self._abort_if_unique_id_configured()

            # Auto-detect number of speeds from percentage_step
            fan_entity_id = user_input[CONF_FAN_ENTITY]
            detected_speeds = _detect_fan_speeds(self.hass, fan_entity_id)

            data = {
                CONF_FAN_ENTITY: fan_entity_id,
                CONF_TEMP_ENTITY: user_input[CONF_TEMP_ENTITY],
                CONF_SET_POINT: DEFAULT_SET_POINT,
                CONF_NUM_SPEEDS: detected_speeds,
                CONF_TEMP_STEP: DEFAULT_TEMP_STEP,
            }

            title = (
                f"Fan Climate – {fan_entity_id.split('.')[-1]}"
            )
            return self.async_create_entry(
                title=title, data=data
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FanClimateOptionsFlow:
        """Return the options flow handler."""
        return FanClimateOptionsFlow(config_entry)


class FanClimateOptionsFlow(config_entries.OptionsFlow):
    """Handle option updates for an existing entry."""

    def __init__(
        self, config_entry: config_entries.ConfigEntry
    ) -> None:
        """Initialise."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            user_input[CONF_NUM_SPEEDS] = int(
                user_input[CONF_NUM_SPEEDS]
            )
            # Merge options back into data so reload picks them up.
            new_data = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        defaults = dict(self._config_entry.data)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TEMP_ENTITY,
                    default=defaults.get(CONF_TEMP_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["climate", "sensor"]
                    )
                ),
                vol.Required(
                    CONF_NUM_SPEEDS,
                    default=defaults.get(CONF_NUM_SPEEDS, DEFAULT_NUM_SPEEDS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=100,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TEMP_STEP,
                    default=defaults.get(CONF_TEMP_STEP, DEFAULT_TEMP_STEP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=20,
                        step=0.5,
                        unit_of_measurement="°",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
