"""Config flow for Aquagem iSaver Power."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_DAY_SPEED,
    CONF_ECO_SPEED,
    CONF_MAX_OPERATING_SPEED,
    CONF_MAX_PRESET_SPEED,
    CONF_MIN_OPERATING_SPEED,
    CONF_NIGHT_SPEED,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAY_SPEED,
    DEFAULT_ECO_SPEED,
    DEFAULT_MAX_OPERATING_SPEED,
    DEFAULT_MAX_PRESET_SPEED,
    DEFAULT_MIN_OPERATING_SPEED,
    DEFAULT_NAME,
    DEFAULT_NIGHT_SPEED,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SPEED,
    MIN_SPEED,
    SPEED_STEP,
)
from .protocol import AquagemClient, AquagemConnectionError


SPEED_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SPEED,
        max=MAX_SPEED,
        step=SPEED_STEP,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="rpm",
    )
)

SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=5,
        max=300,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="s",
    )
)


class AquagemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Aquagem gateway."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Configure a new Aquagem gateway."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            client = AquagemClient(host, user_input[CONF_PORT])
            try:
                await client.test_connection()
            except AquagemConnectionError:
                errors["base"] = "cannot_connect"
            else:
                name = user_input.pop(CONF_NAME)
                return self.async_create_entry(title=name, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """Reconfigure an existing Aquagem gateway."""
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip() or DEFAULT_NAME
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])

            endpoint_in_use = any(
                entry.entry_id != reconfigure_entry.entry_id
                and entry.data.get(CONF_HOST) == host
                and entry.data.get(CONF_PORT, DEFAULT_PORT) == port
                for entry in self._async_current_entries()
            )

            if endpoint_in_use:
                errors["base"] = "endpoint_in_use"
            else:
                client = AquagemClient(host, port)
                try:
                    await client.test_connection()
                except AquagemConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    # Keep the config-entry identity stable while allowing the
                    # RS485/TCP endpoint itself to change.
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        title=name,
                        data_updates={CONF_HOST: host, CONF_PORT: port},
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=reconfigure_entry.title): str,
                vol.Required(
                    CONF_HOST, default=reconfigure_entry.data[CONF_HOST]
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=reconfigure_entry.data.get(CONF_PORT, DEFAULT_PORT),
                ): int,
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return AquagemOptionsFlow()


class AquagemOptionsFlow(config_entries.OptionsFlow):
    """Configure polling, operating limits and Home Assistant speed profiles."""

    async def async_step_init(self, user_input=None):
        """Manage Aquagem options."""
        errors = {}

        if user_input is not None:
            speed_keys = (
                CONF_MIN_OPERATING_SPEED,
                CONF_MAX_OPERATING_SPEED,
                CONF_NIGHT_SPEED,
                CONF_ECO_SPEED,
                CONF_DAY_SPEED,
                CONF_MAX_PRESET_SPEED,
            )
            for key in speed_keys:
                user_input[key] = int(user_input[key])
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])

            minimum = user_input[CONF_MIN_OPERATING_SPEED]
            maximum = user_input[CONF_MAX_OPERATING_SPEED]
            profile_speeds = (
                user_input[CONF_NIGHT_SPEED],
                user_input[CONF_ECO_SPEED],
                user_input[CONF_DAY_SPEED],
                user_input[CONF_MAX_PRESET_SPEED],
            )

            if any(
                speed < MIN_SPEED
                or speed > MAX_SPEED
                or speed % SPEED_STEP != 0
                for speed in (minimum, maximum, *profile_speeds)
            ):
                errors["base"] = "invalid_speed_step"
            elif minimum >= maximum:
                errors["base"] = "invalid_speed_range"
            elif any(speed < minimum or speed > maximum for speed in profile_speeds):
                errors["base"] = "profile_out_of_range"
            else:
                return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        values = user_input or options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): SCAN_INTERVAL_SELECTOR,
                    vol.Required(
                        CONF_MIN_OPERATING_SPEED,
                        default=values.get(
                            CONF_MIN_OPERATING_SPEED, DEFAULT_MIN_OPERATING_SPEED
                        ),
                    ): SPEED_SELECTOR,
                    vol.Required(
                        CONF_MAX_OPERATING_SPEED,
                        default=values.get(
                            CONF_MAX_OPERATING_SPEED, DEFAULT_MAX_OPERATING_SPEED
                        ),
                    ): SPEED_SELECTOR,
                    vol.Required(
                        CONF_NIGHT_SPEED,
                        default=values.get(CONF_NIGHT_SPEED, DEFAULT_NIGHT_SPEED),
                    ): SPEED_SELECTOR,
                    vol.Required(
                        CONF_ECO_SPEED,
                        default=values.get(CONF_ECO_SPEED, DEFAULT_ECO_SPEED),
                    ): SPEED_SELECTOR,
                    vol.Required(
                        CONF_DAY_SPEED,
                        default=values.get(CONF_DAY_SPEED, DEFAULT_DAY_SPEED),
                    ): SPEED_SELECTOR,
                    vol.Required(
                        CONF_MAX_PRESET_SPEED,
                        default=values.get(
                            CONF_MAX_PRESET_SPEED, DEFAULT_MAX_PRESET_SPEED
                        ),
                    ): SPEED_SELECTOR,
                }
            ),
            errors=errors,
        )
