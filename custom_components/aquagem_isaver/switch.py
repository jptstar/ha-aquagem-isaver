"""Aquagem pump switch."""

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, MIN_SPEED
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AquagemPumpSwitch(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemPumpSwitch(AquagemEntity, SwitchEntity):
    _attr_translation_key = "pump"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pump"

    @property
    def is_on(self):
        return self.coordinator.data["speed"] >= MIN_SPEED

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_speed(self.coordinator.last_running_speed)

    async def async_turn_off(self, **kwargs):
        # The iSaver protocol uses value 1 as OFF. Value 0 is transient and
        # the drive resumes its previously stored speed.
        await self.coordinator.async_set_speed(1)
