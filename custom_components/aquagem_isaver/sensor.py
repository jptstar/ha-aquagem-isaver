"""Aquagem pump sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, PUMP_MODBUS_ENERGY_SCALE
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up protocol-appropriate pump sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AquagemSpeedSensor(coordinator, entry),
        AquagemFaultCodeSensor(coordinator, entry),
    ]
    if coordinator.client.is_pump_modbus:
        entities.extend(
            [
                AquagemPowerSensor(coordinator, entry),
                AquagemEnergyConsumptionSensor(coordinator, entry),
                AquagemModeCodeSensor(coordinator, entry),
                AquagemSoftwareVersionSensor(coordinator, entry),
            ]
        )
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
        return data.power_w if data is not None else None


class AquagemEnergyConsumptionSensor(AquagemEntity, SensorEntity):
    """Energy consumption from Modbus V1.5 register 2007."""

    _attr_translation_key = "energy_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_energy_consumption"

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None or data.energy_raw is None:
            return None
        return data.energy_raw / PUMP_MODBUS_ENERGY_SCALE


class AquagemModeCodeSensor(AquagemEntity, SensorEntity):
    """Raw Modbus V1.5 mode code from register 2008."""

    _attr_translation_key = "mode_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mode_code"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.mode_code if data is not None else None


class AquagemSoftwareVersionSensor(AquagemEntity, SensorEntity):
    """Raw software-version value from Modbus V1.5 register 2009."""

    _attr_translation_key = "software_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_software_version"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.software_version if data is not None else None
