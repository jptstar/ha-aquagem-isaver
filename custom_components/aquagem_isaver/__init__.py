"""Aquagem iSaver integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import AquagemCoordinator
from .protocol import AquagemClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    client = AquagemClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = AquagemCoordinator(
        hass, client, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    # Do not prevent setup when an RTU-buffered gateway is temporarily silent
    # or already occupied by another TCP client. The coordinator will retry.
    await coordinator.async_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entity_registry = er.async_get(hass)

    # 0.2.1 replaces the legacy pump switch with a variable-speed fan entity.
    # Remove the old registry entry so upgrades do not leave an unavailable
    # switch behind after the platform changes.
    legacy_switch = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{entry.entry_id}_pump"
    )
    if legacy_switch is not None:
        entity_registry.async_remove(legacy_switch)

    # The estimated-power sensor was experimental and is no longer exposed.
    # Remove its registry entry as well so upgrades do not leave a stale entity.
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
