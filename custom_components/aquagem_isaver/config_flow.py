"""Config flow for supported Aquagem variable-speed pumps."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DAY_SPEED,
    CONF_ECO_SPEED,
    CONF_MAX_OPERATING_SPEED,
    CONF_MAX_PRESET_SPEED,
    CONF_MIN_OPERATING_SPEED,
    CONF_MODBUS_UNIT,
    CONF_NIGHT_SPEED,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_TRANSPORT,
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
    ISAVER_BAUDRATE,
    ISAVER_SERIAL_GUARD_SECONDS,
    MAX_SPEED,
    MIN_SPEED,
    PROTOCOL_ISAVER,
    PROTOCOL_PUMP_MODBUS,
    PUMP_MODBUS_BAUDRATE,
    PUMP_MODBUS_DEFAULT_UNIT,
    PUMP_MODBUS_RTU_GUARD_SECONDS,
    PUMP_MODBUS_UNIT_MAX,
    PUMP_MODBUS_UNIT_MIN,
    SPEED_STEP,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .protocol import AquagemClient, AquagemConnectionError, AquagemError
from .transport import SerialTransport


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

MODBUS_ADDRESS_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

TRANSPORT_CHOICES = {
    TRANSPORT_TCP: "RS485/TCP gateway",
    TRANSPORT_SERIAL: "Direct serial / USB-RS485",
}

MANUAL_PROTOCOLS = {
    PROTOCOL_ISAVER: "iSaver Power 1100 — C3/D0 (1200 baud)",
    PROTOCOL_PUMP_MODBUS: "DM15 / Aquagem Modbus pump — 03/10 (9600 baud)",
}


def _serial_title_suffix(serial_port: str) -> str:
    """Return a compact serial endpoint label for the config entry title."""
    clean = serial_port.split("?", 1)[0].rstrip("/")
    return clean.rsplit("/", 1)[-1] or serial_port


def _format_modbus_unit(unit: int) -> str:
    """Format the stored Modbus unit for the address text field."""
    return f"0x{unit:02X}"


def _parse_modbus_unit(value) -> int:
    """Accept decimal or hexadecimal Aquagem Modbus addresses."""
    if isinstance(value, int):
        unit = value
    else:
        text = str(value).strip()
        if not text:
            unit = PUMP_MODBUS_DEFAULT_UNIT
        else:
            lowered = text.lower()
            if lowered.startswith("0x"):
                unit = int(lowered, 16)
            elif any(char in "abcdefABCDEF" for char in text):
                unit = int(text, 16)
            else:
                unit = int(text, 10)

    if not PUMP_MODBUS_UNIT_MIN <= unit <= PUMP_MODBUS_UNIT_MAX:
        raise ValueError("Modbus address outside Aquagem range")
    return unit


def _serial_transport(serial_port: str, protocol: str) -> SerialTransport:
    """Build the serial transport with the validated profile settings."""
    if protocol == PROTOCOL_ISAVER:
        return SerialTransport(
            serial_port,
            ISAVER_BAUDRATE,
            inter_frame_delay=ISAVER_SERIAL_GUARD_SECONDS,
        )
    return SerialTransport(
        serial_port,
        PUMP_MODBUS_BAUDRATE,
        inter_frame_delay=PUMP_MODBUS_RTU_GUARD_SECONDS,
    )


class AquagemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Aquagem pump over TCP or direct serial."""

    VERSION = 3

    def __init__(self) -> None:
        self._pending_name = DEFAULT_NAME
        self._pending_data: dict | None = None

    async def async_step_user(self, user_input=None):
        """Choose the connection transport."""
        if user_input is not None:
            self._pending_name = str(user_input[CONF_NAME]).strip() or DEFAULT_NAME
            if user_input[CONF_TRANSPORT] == TRANSPORT_SERIAL:
                return await self.async_step_serial()
            return await self.async_step_tcp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_TRANSPORT, default=TRANSPORT_TCP): vol.In(
                        TRANSPORT_CHOICES
                    ),
                }
            ),
        )

    async def async_step_tcp(self, user_input=None):
        """Configure a transparent RS485/TCP gateway."""
        errors = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = AquagemClient(host, port)
            try:
                await client.test_connection()
            except AquagemConnectionError:
                errors["base"] = "cannot_connect"
            else:
                try:
                    await client.detect_protocol()
                except AquagemError:
                    self._pending_data = {
                        CONF_NAME: self._pending_name,
                        CONF_TRANSPORT: TRANSPORT_TCP,
                        CONF_HOST: host,
                        CONF_PORT: port,
                    }
                    return await self.async_step_manual()

                data = {
                    CONF_NAME: self._pending_name,
                    CONF_TRANSPORT: TRANSPORT_TCP,
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_PROTOCOL: client.protocol,
                }
                if client.is_pump_modbus:
                    data[CONF_MODBUS_UNIT] = client.modbus_unit
                return self.async_create_entry(
                    title=f"{self._pending_name} {host}", data=data
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="tcp",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_serial(self, user_input=None):
        """Configure direct serial for Modbus RTU or proprietary C3/D0."""
        errors = {}
        if user_input is not None:
            serial_port = str(user_input[CONF_SERIAL_PORT])
            protocol = str(user_input[CONF_PROTOCOL])

            try:
                unit = (
                    _parse_modbus_unit(
                        user_input.get(
                            CONF_MODBUS_UNIT,
                            _format_modbus_unit(PUMP_MODBUS_DEFAULT_UNIT),
                        )
                    )
                    if protocol == PROTOCOL_PUMP_MODBUS
                    else PUMP_MODBUS_DEFAULT_UNIT
                )
            except (TypeError, ValueError):
                errors["base"] = "invalid_modbus_address"
            else:
                await self.async_set_unique_id(f"serial:{serial_port}")
                self._abort_if_unique_id_configured()

                client = AquagemClient(
                    protocol=protocol,
                    modbus_unit=unit,
                    transport=_serial_transport(serial_port, protocol),
                )
                try:
                    await client.test_connection()
                    await client.validate_forced_protocol()
                except (AquagemError, ValueError):
                    errors["base"] = "cannot_validate_serial"
                else:
                    data = {
                        CONF_NAME: self._pending_name,
                        CONF_TRANSPORT: TRANSPORT_SERIAL,
                        CONF_SERIAL_PORT: serial_port,
                        CONF_PROTOCOL: protocol,
                    }
                    if protocol == PROTOCOL_PUMP_MODBUS:
                        data[CONF_MODBUS_UNIT] = unit
                    return self.async_create_entry(
                        title=(
                            f"{self._pending_name} "
                            f"{_serial_title_suffix(serial_port)}"
                        ),
                        data=data,
                    )
                finally:
                    await client.async_close()

        return self.async_show_form(
            step_id="serial",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_PORT): SerialPortSelector(),
                    vol.Required(
                        CONF_PROTOCOL, default=PROTOCOL_PUMP_MODBUS
                    ): vol.In(MANUAL_PROTOCOLS),
                    vol.Optional(
                        CONF_MODBUS_UNIT,
                        default=_format_modbus_unit(PUMP_MODBUS_DEFAULT_UNIT),
                    ): MODBUS_ADDRESS_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_manual(self, user_input=None):
        """Fallback when TCP automatic signature detection did not succeed."""
        if self._pending_data is None:
            return self.async_abort(reason="manual_without_gateway")

        errors = {}
        if user_input is not None:
            protocol = user_input[CONF_PROTOCOL]
            unit = int(user_input.get(CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT))
            client = AquagemClient(
                self._pending_data[CONF_HOST],
                self._pending_data[CONF_PORT],
                protocol=protocol,
                modbus_unit=unit,
            )
            try:
                await client.validate_forced_protocol()
            except AquagemError:
                errors["base"] = "cannot_validate_manual"
            else:
                data = {**self._pending_data, CONF_PROTOCOL: protocol}
                if protocol == PROTOCOL_PUMP_MODBUS:
                    data[CONF_MODBUS_UNIT] = unit
                name = data[CONF_NAME]
                host = data[CONF_HOST]
                self._pending_data = None
                return self.async_create_entry(title=f"{name} {host}", data=data)
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROTOCOL, default=PROTOCOL_ISAVER): vol.In(
                        MANUAL_PROTOCOLS
                    ),
                    vol.Optional(
                        CONF_MODBUS_UNIT,
                        default=PUMP_MODBUS_DEFAULT_UNIT,
                    ): vol.All(
                        int,
                        vol.Range(
                            min=PUMP_MODBUS_UNIT_MIN,
                            max=PUMP_MODBUS_UNIT_MAX,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Reconfigure the existing endpoint without changing transport type."""
        reconfigure_entry = self._get_reconfigure_entry()
        transport = reconfigure_entry.data.get(CONF_TRANSPORT, TRANSPORT_TCP)
        if transport == TRANSPORT_SERIAL:
            return await self._async_step_reconfigure_serial(
                reconfigure_entry, user_input
            )
        return await self._async_step_reconfigure_tcp(reconfigure_entry, user_input)

    async def _async_step_reconfigure_tcp(self, reconfigure_entry, user_input):
        errors = {}

        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip() or DEFAULT_NAME
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])

            endpoint_in_use = any(
                entry.entry_id != reconfigure_entry.entry_id
                and entry.data.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_TCP
                and entry.data.get(CONF_HOST) == host
                and entry.data.get(CONF_PORT, DEFAULT_PORT) == port
                for entry in self._async_current_entries()
            )

            if endpoint_in_use:
                errors["base"] = "endpoint_in_use"
            else:
                protocol = reconfigure_entry.data.get(CONF_PROTOCOL)
                unit = reconfigure_entry.data.get(
                    CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT
                )
                client = AquagemClient(
                    host,
                    port,
                    protocol=protocol,
                    modbus_unit=unit,
                )
                try:
                    await client.test_connection()
                    if protocol is None:
                        await client.detect_protocol()
                    else:
                        await client.validate_forced_protocol()
                except AquagemError:
                    errors["base"] = "cannot_connect"
                else:
                    data_updates = {
                        CONF_NAME: name,
                        CONF_TRANSPORT: TRANSPORT_TCP,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PROTOCOL: client.protocol,
                    }
                    if client.is_pump_modbus:
                        data_updates[CONF_MODBUS_UNIT] = client.modbus_unit
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        title=f"{name} {host}",
                        data_updates=data_updates,
                    )
                finally:
                    await client.async_close()

        default_name = reconfigure_entry.data.get(
            CONF_NAME,
            reconfigure_entry.title.rsplit(" ", 1)[0],
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
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

    async def _async_step_reconfigure_serial(self, reconfigure_entry, user_input):
        errors = {}
        protocol = reconfigure_entry.data.get(CONF_PROTOCOL, PROTOCOL_PUMP_MODBUS)

        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip() or DEFAULT_NAME
            serial_port = str(user_input[CONF_SERIAL_PORT])

            try:
                unit = (
                    _parse_modbus_unit(
                        user_input.get(
                            CONF_MODBUS_UNIT,
                            _format_modbus_unit(PUMP_MODBUS_DEFAULT_UNIT),
                        )
                    )
                    if protocol == PROTOCOL_PUMP_MODBUS
                    else PUMP_MODBUS_DEFAULT_UNIT
                )
            except (TypeError, ValueError):
                errors["base"] = "invalid_modbus_address"
            else:
                endpoint_in_use = any(
                    entry.entry_id != reconfigure_entry.entry_id
                    and entry.data.get(CONF_TRANSPORT) == TRANSPORT_SERIAL
                    and entry.data.get(CONF_SERIAL_PORT) == serial_port
                    for entry in self._async_current_entries()
                )

                if endpoint_in_use:
                    errors["base"] = "serial_endpoint_in_use"
                else:
                    client = AquagemClient(
                        protocol=protocol,
                        modbus_unit=unit,
                        transport=_serial_transport(serial_port, protocol),
                    )
                    try:
                        await client.test_connection()
                        await client.validate_forced_protocol()
                    except (AquagemError, ValueError):
                        errors["base"] = "cannot_validate_serial"
                    else:
                        data_updates = {
                            CONF_NAME: name,
                            CONF_TRANSPORT: TRANSPORT_SERIAL,
                            CONF_SERIAL_PORT: serial_port,
                            CONF_PROTOCOL: protocol,
                        }
                        if protocol == PROTOCOL_PUMP_MODBUS:
                            data_updates[CONF_MODBUS_UNIT] = unit
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            title=f"{name} {_serial_title_suffix(serial_port)}",
                            data_updates=data_updates,
                        )
                    finally:
                        await client.async_close()

        default_name = reconfigure_entry.data.get(CONF_NAME, DEFAULT_NAME)
        schema_fields = {
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(
                CONF_SERIAL_PORT,
                default=reconfigure_entry.data[CONF_SERIAL_PORT],
            ): SerialPortSelector(),
        }
        if protocol == PROTOCOL_PUMP_MODBUS:
            schema_fields[
                vol.Required(
                    CONF_MODBUS_UNIT,
                    default=_format_modbus_unit(
                        reconfigure_entry.data.get(
                            CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT
                        )
                    ),
                )
            ] = MODBUS_ADDRESS_SELECTOR

        schema = vol.Schema(schema_fields)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id="reconfigure_serial",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return AquagemOptionsFlow()


class AquagemOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and iSaver-specific RPM profiles."""

    async def async_step_init(self, user_input=None):
        """Manage options for the active protocol."""
        errors = {}
        is_modbus = self.config_entry.data.get(CONF_PROTOCOL) == PROTOCOL_PUMP_MODBUS

        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            if is_modbus:
                return self.async_create_entry(title="", data=user_input)

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

        if is_modbus:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): SCAN_INTERVAL_SELECTOR,
                }
            )
        else:
            schema = vol.Schema(
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
            )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
