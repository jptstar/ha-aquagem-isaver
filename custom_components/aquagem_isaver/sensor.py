"""Aquagem pump sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
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
        entities.append(AquagemPowerSensor(coordinator, entry))
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


class AquagemPowerSensor(AquagemEntity, SensorEntity):
    """Electrical power reported by Modbus holding register 2004."""

    _attr_translation_key = "power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.raw_2004 if data is not None else None
