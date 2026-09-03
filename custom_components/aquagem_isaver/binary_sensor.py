"""Aquagem connectivity and fault sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, PROTOCOL_ISAVER, PROTOCOL_PUMP_MODBUS
from .entity import AquagemEntity


@dataclass(frozen=True, kw_only=True)
class AquagemFaultDescription(BinarySensorEntityDescription):
    """Description of one documented fault bit."""

    bit: int
    protocol: str


ISAVER_FAULTS: tuple[AquagemFaultDescription, ...] = (
    AquagemFaultDescription(key="rs485_error", translation_key="rs485_error", bit=4, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="temperature_derating", translation_key="temperature_derating", bit=5, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="keypad_communication_error", translation_key="keypad_communication_error", bit=6, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="keypad_eeprom_error", translation_key="keypad_eeprom_error", bit=7, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="rtc_error", translation_key="rtc_error", bit=8, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="main_eeprom_error", translation_key="main_eeprom_error", bit=9, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="current_detection_error", translation_key="current_detection_error", bit=10, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="main_drive_error", translation_key="main_drive_error", bit=11, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="heatsink_sensor_error", translation_key="heatsink_sensor_error", bit=12, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="heatsink_overheat", translation_key="heatsink_overheat", bit=13, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="overcurrent", translation_key="overcurrent", bit=14, protocol=PROTOCOL_ISAVER),
    AquagemFaultDescription(key="input_voltage_error", translation_key="input_voltage_error", bit=15, protocol=PROTOCOL_ISAVER),
)

# Legacy/basic mapping retained for Aquagem Modbus variants that do not match
# the V1.5 extended register signature.
PUMP_MODBUS_FAULTS: tuple[AquagemFaultDescription, ...] = (
    AquagemFaultDescription(key="modbus_dc_voltage_abnormal", translation_key="modbus_dc_voltage_abnormal", bit=0, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_ac_current_sampling_error", translation_key="modbus_ac_current_sampling_error", bit=1, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_phase_loss", translation_key="modbus_phase_loss", bit=2, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_master_drive_error", translation_key="modbus_master_drive_error", bit=3, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_heatsink_sensor_error", translation_key="modbus_heatsink_sensor_error", bit=4, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_heatsink_overheat", translation_key="modbus_heatsink_overheat", bit=5, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_output_current_limit", translation_key="modbus_output_current_limit", bit=6, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_input_voltage_abnormal", translation_key="modbus_input_voltage_abnormal", bit=7, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_no_water", translation_key="modbus_no_water", bit=8, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_display_comm_error", translation_key="modbus_display_comm_error", bit=9, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_display_eeprom_error", translation_key="modbus_display_eeprom_error", bit=10, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_rtc_error", translation_key="modbus_rtc_error", bit=11, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_main_eeprom_error", translation_key="modbus_main_eeprom_error", bit=12, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_motor_current_detection_error", translation_key="modbus_motor_current_detection_error", bit=13, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_motor_power_overload", translation_key="modbus_motor_power_overload", bit=14, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_pfc_protection", translation_key="modbus_pfc_protection", bit=15, protocol=PROTOCOL_PUMP_MODBUS),
)

# Official Aquagem "Inverter Pool Pump RS485 Modbus V1.5 (for V1.0.0)" mapping.
# Bit 0 is reserved and therefore intentionally has no binary sensor.
PUMP_MODBUS_V15_FAULTS: tuple[AquagemFaultDescription, ...] = (
    AquagemFaultDescription(key="modbus_communication_error", translation_key="modbus_communication_error", bit=1, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_no_water", translation_key="modbus_no_water", bit=2, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_rtc_error", translation_key="modbus_rtc_error", bit=3, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_display_eeprom_error", translation_key="modbus_display_eeprom_error", bit=4, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_circuit_board_error", translation_key="modbus_circuit_board_error", bit=5, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_motor_power_overload", translation_key="modbus_motor_power_overload", bit=6, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_pfc_protection", translation_key="modbus_pfc_protection", bit=7, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_dc_voltage_abnormal", translation_key="modbus_dc_voltage_abnormal", bit=8, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_ac_current_sampling_error", translation_key="modbus_ac_current_sampling_error", bit=9, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_phase_loss", translation_key="modbus_phase_loss", bit=10, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_master_drive_error", translation_key="modbus_master_drive_error", bit=11, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_heatsink_sensor_error", translation_key="modbus_heatsink_sensor_error", bit=12, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_heatsink_overheat", translation_key="modbus_heatsink_overheat", bit=13, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_output_current_limit", translation_key="modbus_output_current_limit", bit=14, protocol=PROTOCOL_PUMP_MODBUS),
    AquagemFaultDescription(key="modbus_input_voltage_abnormal", translation_key="modbus_input_voltage_abnormal", bit=15, protocol=PROTOCOL_PUMP_MODBUS),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up connectivity, global alarm and protocol-specific fault bits."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    protocol = coordinator.client.protocol
    if protocol == PROTOCOL_ISAVER:
        faults = ISAVER_FAULTS
    elif coordinator.v15_profile is True:
        faults = PUMP_MODBUS_V15_FAULTS
    else:
        faults = PUMP_MODBUS_FAULTS
    async_add_entities(
        [
            AquagemConnectivity(coordinator, entry),
            AquagemAlarm(coordinator, entry),
            *(
                AquagemFaultBinarySensor(coordinator, entry, description)
                for description in faults
            ),
        ]
    )


class AquagemConnectivity(AquagemEntity, BinarySensorEntity):
    """Connection health."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_connectivity"

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def is_on(self):
        return self.coordinator.communication_online is True

    @property
    def extra_state_attributes(self):
        return {
            "consecutive_failures": self.coordinator.consecutive_failures,
            "failure_threshold": self.coordinator.failure_threshold,
            "modbus_v15_profile": self.coordinator.v15_profile,
        }


class AquagemAlarm(AquagemEntity, BinarySensorEntity):
    """Global alarm derived from the complete fault word."""

    _attr_translation_key = "alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_alarm"

    @property
    def is_on(self):
        data = self.coordinator.data
        return bool(data and data.fault_code)


class AquagemFaultBinarySensor(AquagemEntity, BinarySensorEntity):
    """One documented fault bit for the active protocol."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, description: AquagemFaultDescription):
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self):
        data = self.coordinator.data
        return bool(data and data.fault_code & (1 << self.entity_description.bit))
