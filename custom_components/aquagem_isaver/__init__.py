"""Aquagem variable-speed pump integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_INITIAL_OPERATING_HOURS,
    CONF_MODBUS_UNIT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_TRANSPORT,
    DEFAULT_INITIAL_OPERATING_HOURS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ISAVER_BAUDRATE,
    ISAVER_SERIAL_GUARD_SECONDS,
    PLATFORMS,
    PROTOCOL_ISAVER,
    PROTOCOL_PUMP_MODBUS,
    PUMP_MODBUS_BAUDRATE,
    PUMP_MODBUS_DEFAULT_UNIT,
    PUMP_MODBUS_RTU_GUARD_SECONDS,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .coordinator import AquagemCoordinator
from .protocol import AquagemClient
from .runtime import AquagemRuntimeTracker
from .transport import SerialTransport


def _serial_title_suffix(serial_port: str) -> str:
    clean = serial_port.split("?", 1)[0].rstrip("/")
    return clean.rsplit("/", 1)[-1] or serial_port


def _unit_suffix(data: dict) -> str:
    """Return a visible Modbus unit suffix for multi-device buses."""
    if data.get(CONF_PROTOCOL) != PROTOCOL_PUMP_MODBUS:
        return ""
    unit = int(data.get(CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT))
    return f" [0x{unit:02X}]"


def _entry_title(data: dict, fallback_title: str) -> str:
    """Build a compact title without changing entity identity."""
    name = data.get(CONF_NAME, fallback_title)
    suffix = _unit_suffix(data)
    if data.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_SERIAL:
        serial_port = data.get(CONF_SERIAL_PORT)
        if serial_port:
            return f"{name} {_serial_title_suffix(str(serial_port))}{suffix}"
        return f"{name}{suffix}"

    host = data.get(CONF_HOST)
    return f"{name} {host}{suffix}" if host else f"{name}{suffix}"


def _entry_unique_id(data: dict) -> str | None:
    """Return the canonical device identity on a shared physical bus."""
    transport = data.get(CONF_TRANSPORT, TRANSPORT_TCP)
    protocol = data.get(CONF_PROTOCOL)

    if transport == TRANSPORT_SERIAL:
        serial_port = data.get(CONF_SERIAL_PORT)
        if not serial_port:
            return None
        if protocol == PROTOCOL_PUMP_MODBUS:
            unit = int(data.get(CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT))
            return f"serial:{serial_port}:modbus:{unit:02X}"
        if protocol == PROTOCOL_ISAVER:
            return f"serial:{serial_port}:isaver"
        return f"serial:{serial_port}"

    host = data.get(CONF_HOST)
    port = data.get(CONF_PORT)
    if host is None or port is None:
        return None
    if protocol == PROTOCOL_PUMP_MODBUS:
        unit = int(data.get(CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT))
        return f"tcp:{host}:{port}:modbus:{unit:02X}"
    if protocol == PROTOCOL_ISAVER:
        return f"tcp:{host}:{port}:isaver"
    return f"tcp:{host}:{port}"


def _sync_entry_unique_id(hass: HomeAssistant, entry: ConfigEntry, data: dict) -> None:
    """Keep the config-entry identity aligned with endpoint + Modbus unit."""
    expected_unique_id = _entry_unique_id(data)
    if expected_unique_id is None or entry.unique_id == expected_unique_id:
        return

    duplicate = next(
        (
            other
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
            and _entry_unique_id(dict(other.data)) == expected_unique_id
        ),
        None,
    )
    if duplicate is None:
        hass.config_entries.async_update_entry(entry, unique_id=expected_unique_id)


def _serial_transport(entry: ConfigEntry) -> SerialTransport:
    """Create the direct serial transport for the stored protocol profile."""
    protocol = entry.data.get(CONF_PROTOCOL, PROTOCOL_PUMP_MODBUS)
    if protocol == PROTOCOL_ISAVER:
        return SerialTransport(
            entry.data[CONF_SERIAL_PORT],
            ISAVER_BAUDRATE,
            inter_frame_delay=ISAVER_SERIAL_GUARD_SECONDS,
        )
    return SerialTransport(
        entry.data[CONF_SERIAL_PORT],
        PUMP_MODBUS_BAUDRATE,
        inter_frame_delay=PUMP_MODBUS_RTU_GUARD_SECONDS,
    )


def _build_client(entry: ConfigEntry) -> AquagemClient:
    """Create the protocol client for the entry's stored transport."""
    if entry.data.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_SERIAL:
        return AquagemClient(
            protocol=entry.data.get(CONF_PROTOCOL, PROTOCOL_PUMP_MODBUS),
            modbus_unit=entry.data.get(
                CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT
            ),
            transport=_serial_transport(entry),
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
    """Migrate older entries to the transport-aware multi-device format."""
    if entry.version > 4:
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

    if entry.version < 4:
        # Version 4 changes config-entry identity from one-entry-per-endpoint to
        # endpoint + protocol + Modbus unit. Entity unique IDs still use the
        # stable entry_id, so existing Home Assistant entities are preserved.
        hass.config_entries.async_update_entry(entry, version=4)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up from a config entry."""
    _sync_entry_unique_id(hass, entry, dict(entry.data))

    client = _build_client(entry)
    runtime_tracker = AquagemRuntimeTracker(
        hass,
        entry.entry_id,
        entry.data.get(
            CONF_INITIAL_OPERATING_HOURS, DEFAULT_INITIAL_OPERATING_HOURS
        ),
    )
    await runtime_tracker.async_load()

    coordinator = AquagemCoordinator(
        hass,
        client,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        runtime_tracker,
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

        # Detection may have changed the canonical identity from endpoint-only
        # to endpoint + protocol + unit, so synchronize it once more.
        _sync_entry_unique_id(hass, entry, data)

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
    """Unload an entry and release transport/runtime resources."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        if coordinator is not None:
            await coordinator.runtime_tracker.async_shutdown()
            await coordinator.client.async_close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
