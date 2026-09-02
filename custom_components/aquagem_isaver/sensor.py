"""Aquagem pump sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up protocol-appropriate pump sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AquagemSpeedSensor(coordinator, entry),
        AquagemFaultCodeSensor(coordinator, entry),
    ]
    if coordinator.client.is_pump_modbus:
        entities.append(AquagemRaw2004Sensor(coordinator, entry))
    async_add_entities(entities)


class AquagemSpeedSensor(AquagemEntity, SensorEntity):
    """Actual RPM or running-capacity value reported by the pump."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        if coordinator.client.is_pump_modbus:
            self._attr_unique_id = f"{entry.entry_id}_capacity"
            self._attr_translation_key = "capacity"
            self._attr_native_unit_of_measurement = "%"
        else:
            # Preserve the released iSaver identity for existing installations.
            self._attr_unique_id = f"{entry.entry_id}_speed"
            self._attr_translation_key = "speed"
            self._attr_native_unit_of_measurement = "rpm"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.speed if data is not None else None


class AquagemFaultCodeSensor(AquagemEntity, SensorEntity):
    """Raw fault bitfield from register 2001 / iSaver status word."""

    _attr_translation_key = "fault_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_fault_code"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.fault_code if data is not None else None


class AquagemRaw2004Sensor(AquagemEntity, SensorEntity):
    """Expose Modbus register 2004 without assigning an unverified unit."""

    _attr_translation_key = "raw_2004"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_raw_2004"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.raw_2004 if data is not None else None
