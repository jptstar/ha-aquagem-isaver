"""Aquagem speed command."""

from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN, MAX_SPEED, MIN_SPEED
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AquagemSpeedNumber(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemSpeedNumber(AquagemEntity, NumberEntity):
    _attr_translation_key = "speed_command"
    _attr_native_min_value = MIN_SPEED
    _attr_native_max_value = MAX_SPEED
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "rpm"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_speed_command"

    @property
    def native_value(self):
        speed = self.coordinator.data["speed"]
        return speed if speed >= MIN_SPEED else self.coordinator.last_running_speed

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_speed(round(value))
        await self.coordinator.async_request_refresh()
