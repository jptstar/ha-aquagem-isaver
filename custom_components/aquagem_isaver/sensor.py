"""Aquagem iSaver sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AquagemSpeedSensor(coordinator, entry),
            AquagemFaultCodeSensor(coordinator, entry),
        ]
    )


class AquagemSpeedSensor(AquagemEntity, SensorEntity):
    """Actual pump speed reported by register 2003."""

    _attr_translation_key = "speed"
    _attr_native_unit_of_measurement = "rpm"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_speed"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.speed if data is not None else None


class AquagemFaultCodeSensor(AquagemEntity, SensorEntity):
    """Raw fault bitfield from register 2001."""

    _attr_translation_key = "fault_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fault_code"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.fault_code if data is not None else None
