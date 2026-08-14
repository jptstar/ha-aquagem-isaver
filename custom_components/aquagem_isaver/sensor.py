"""Aquagem speed sensor."""

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AquagemSpeedSensor(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemSpeedSensor(AquagemEntity, SensorEntity):
    _attr_translation_key = "speed"
    _attr_native_unit_of_measurement = "rpm"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_speed"

    @property
    def native_value(self):
        return self.coordinator.data["speed"]
