"""Aquagem pump sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
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
        if coordinator.v15_profile is True:
            entities.extend(
                [
                    AquagemEnergySensor(coordinator, entry),
                    AquagemModeCodeSensor(coordinator, entry),
                    AquagemSoftwareVersionSensor(coordinator, entry),
                    AquagemCapacitySetpointFeedbackSensor(coordinator, entry),
                    AquagemRaw2005Sensor(coordinator, entry),
                    AquagemRaw2006Sensor(coordinator, entry),
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


class AquagemEnergySensor(AquagemEntity, SensorEntity):
    """Cumulative power consumption from register 2007."""

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
        return getattr(data, "energy_kwh", None)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return {"raw_register_2007": getattr(data, "raw_2007", None)}


class AquagemModeCodeSensor(AquagemEntity, SensorEntity):
    """Raw V1.5 mode code from register 2008."""

    _attr_translation_key = "mode_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mode_code"

    @property
    def native_value(self):
        data = self.coordinator.data
        return getattr(data, "mode_code", None)


class AquagemSoftwareVersionSensor(AquagemEntity, SensorEntity):
    """Raw software version value from register 2009."""

    _attr_translation_key = "software_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_software_version"

    @property
    def native_value(self):
        data = self.coordinator.data
        return getattr(data, "software_version", None)


class AquagemCapacitySetpointFeedbackSensor(AquagemEntity, SensorEntity):
    """Read-back of the native capacity setpoint from register 3001."""

    _attr_translation_key = "capacity_setpoint_feedback"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_capacity_setpoint_feedback"

    @property
    def native_value(self):
        data = self.coordinator.data
        return getattr(data, "command_capacity", None)


class AquagemRaw2005Sensor(AquagemEntity, SensorEntity):
    """Raw reserved register 2005 for beta validation."""

    _attr_translation_key = "register_2005"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_register_2005"

    @property
    def native_value(self):
        data = self.coordinator.data
        return getattr(data, "raw_2005", None)


class AquagemRaw2006Sensor(AquagemEntity, SensorEntity):
    """Raw reserved register 2006 for beta validation."""

    _attr_translation_key = "register_2006"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_register_2006"

    @property
    def native_value(self):
        data = self.coordinator.data
        return getattr(data, "raw_2006", None)
