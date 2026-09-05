"""Aquagem variable-speed pump integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_MODBUS_UNIT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_TRANSPORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    PROTOCOL_PUMP_MODBUS,
    PUMP_MODBUS_BAUDRATE,
    PUMP_MODBUS_DEFAULT_UNIT,
    PUMP_MODBUS_RTU_GUARD_SECONDS,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .coordinator import AquagemCoordinator
from .protocol import AquagemClient
from .transport import SerialTransport


def _serial_title_suffix(serial_port: str) -> str:
    clean = serial_port.split("?", 1)[0].rstrip("/")
    return clean.rsplit("/", 1)[-1] or serial_port


def _entry_title(data: dict, fallback_title: str) -> str:
    """Build a compact title without changing config-entry identity."""
    name = data.get(CONF_NAME, fallback_title)
    if data.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_SERIAL:
        serial_port = data.get(CONF_SERIAL_PORT)
        if serial_port:
            return f"{name} {_serial_title_suffix(str(serial_port))}"
        return str(name)

    host = data.get(CONF_HOST)
    return f"{name} {host}" if host else str(name)


def _build_client(entry: ConfigEntry) -> AquagemClient:
    """Create the protocol client for the entry's stored transport."""
    if entry.data.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_SERIAL:
        return AquagemClient(
            protocol=entry.data.get(CONF_PROTOCOL, PROTOCOL_PUMP_MODBUS),
            modbus_unit=entry.data.get(
                CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT
            ),
            transport=SerialTransport(
                entry.data[CONF_SERIAL_PORT],
                PUMP_MODBUS_BAUDRATE,
                inter_frame_delay=PUMP_MODBUS_RTU_GUARD_SECONDS,
            ),
        )

    return AquagemClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        protocol=entry.data.get(CONF_PROTOCOL),
        modbus_unit=entry.data.get(
            CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT
        ),
    )


async def async_migrate_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Migrate older entries to the transport-aware config format."""
    if entry.version > 3:
        return False

    if entry.version < 3:
        data = dict(entry.data)

        if CONF_NAME not in data:
            clean_name = entry.title
            host = str(data.get(CONF_HOST, ""))
            if host and clean_name.endswith(f" {host}"):
                clean_name = clean_name[: -(len(host) + 1)]
            data[CONF_NAME] = clean_name

        # Every entry created before 0.4 used a transparent TCP gateway.
        data.setdefault(CONF_TRANSPORT, TRANSPORT_TCP)

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=3,
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up from a config entry."""
    client = _build_client(entry)
    coordinator = AquagemCoordinator(
        hass,
        client,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    # Legacy entries may not yet store a protocol. The first successful refresh
    # detects it read-only; then persist the result so normal polling never
    # needs to probe multiple profiles again.
    await coordinator.async_refresh()

    if coordinator.last_update_success and client.protocol is not None:
        data = dict(entry.data)
        changed = False

        if data.get(CONF_TRANSPORT) is None:
            data[CONF_TRANSPORT] = TRANSPORT_TCP
            changed = True

        if data.get(CONF_PROTOCOL) != client.protocol:
            data[CONF_PROTOCOL] = client.protocol
            changed = True

        if (
            client.is_pump_modbus
            and data.get(CONF_MODBUS_UNIT) != client.modbus_unit
        ):
            data[CONF_MODBUS_UNIT] = client.modbus_unit
            changed = True

        if CONF_NAME not in data:
            clean_name = entry.title
            host = str(data.get(CONF_HOST, ""))
            if host and clean_name.endswith(f" {host}"):
                clean_name = clean_name[: -(len(host) + 1)]
            data[CONF_NAME] = clean_name
            changed = True

        title = _entry_title(data, entry.title)
        if changed or entry.title != title:
            hass.config_entries.async_update_entry(
                entry,
                data=data,
                title=title,
            )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entity_registry = er.async_get(hass)

    # 0.2.1 replaced the legacy pump switch with a variable-speed fan entity.
    legacy_switch = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{entry.entry_id}_pump"
    )
    if legacy_switch is not None:
        entity_registry.async_remove(legacy_switch)

    # The estimated-power sensor was experimental and is no longer exposed.
    estimated_power = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{entry.entry_id}_estimated_power"
    )
    if estimated_power is not None:
        entity_registry.async_remove(estimated_power)

    # 0.3.4 promotes register 2004 from a disabled raw diagnostic value to the
    # documented pump power sensor. Remove the old experimental registry entry
    # so the new enabled power entity is created cleanly.
    raw_2004 = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{entry.entry_id}_raw_2004"
    )
    if raw_2004 is not None:
        entity_registry.async_remove(raw_2004)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload after an option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload an entry and release any persistent serial connection."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        if coordinator is not None:
            await coordinator.client.async_close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
