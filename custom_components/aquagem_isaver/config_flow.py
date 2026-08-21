"""Config flow for Aquagem iSaver Power."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_DAY_SPEED,
    CONF_ECO_SPEED,
    CONF_MAX_SPEED,
    CONF_NIGHT_SPEED,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAY_SPEED,
    DEFAULT_ECO_SPEED,
    DEFAULT_MAX_SPEED,
    DEFAULT_NAME,
    DEFAULT_NIGHT_SPEED,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SPEED,
    MIN_SPEED,
)
from .protocol import AquagemClient, AquagemConnectionError


class AquagemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Aquagem gateway."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AquagemOptionsFlow()


class AquagemOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and Home Assistant speed profiles."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        speed = vol.All(vol.Coerce(int), vol.Range(min=MIN_SPEED, max=MAX_SPEED))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_NIGHT_SPEED,
                        default=options.get(CONF_NIGHT_SPEED, DEFAULT_NIGHT_SPEED),
                    ): speed,
                    vol.Required(
                        CONF_ECO_SPEED,
                        default=options.get(CONF_ECO_SPEED, DEFAULT_ECO_SPEED),
                    ): speed,
                    vol.Required(
                        CONF_DAY_SPEED,
                        default=options.get(CONF_DAY_SPEED, DEFAULT_DAY_SPEED),
                    ): speed,
                    vol.Required(
                        CONF_MAX_SPEED,
                        default=options.get(CONF_MAX_SPEED, DEFAULT_MAX_SPEED),
                    ): speed,
                }
            ),
        )
