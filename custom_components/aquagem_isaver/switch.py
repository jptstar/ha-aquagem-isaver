"""Aquagem iSaver pump switch."""

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, OFF_COMMAND
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AquagemPumpSwitch(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemPumpSwitch(AquagemEntity, SwitchEntity):
    """Pump power state backed by the real register 2002 state."""

    _attr_translation_key = "pump"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pump"

    @property
    def is_on(self):
        data = self.coordinator.data
        return bool(data and data.pump_on)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_speed(self.coordinator.last_running_speed)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_speed(OFF_COMMAND)
