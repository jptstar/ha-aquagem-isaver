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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    PUMP_MODBUS_DEFAULT_UNIT,
)
from .coordinator import AquagemCoordinator
from .protocol import AquagemClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    client = AquagemClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        protocol=entry.data.get(CONF_PROTOCOL),
        modbus_unit=entry.data.get(CONF_MODBUS_UNIT, PUMP_MODBUS_DEFAULT_UNIT),
    )
    coordinator = AquagemCoordinator(
        hass, client, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    # Existing 0.2.x entries do not yet store a protocol. The first successful
    # refresh detects it read-only; then persist the result so normal polling
    # never needs to probe multiple profiles again.
    await coordinator.async_refresh()

    if coordinator.last_update_success and client.protocol is not None:
        data = dict(entry.data)
        changed = False

        if data.get(CONF_PROTOCOL) != client.protocol:
            data[CONF_PROTOCOL] = client.protocol
            changed = True
        if client.is_pump_modbus and data.get(CONF_MODBUS_UNIT) != client.modbus_unit:
            data[CONF_MODBUS_UNIT] = client.modbus_unit
            changed = True

        if CONF_NAME not in data:
            clean_name = entry.title
            host = str(entry.data[CONF_HOST])
            if clean_name.endswith(f" {host}"):
                clean_name = clean_name[: -(len(host) + 1)]
            data[CONF_NAME] = clean_name
            changed = True

        title = f"{data[CONF_NAME]} {entry.data[CONF_HOST]}"
        if changed or entry.title != title:
            hass.config_entries.async_update_entry(entry, data=data, title=title)

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

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
