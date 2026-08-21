"""Aquagem iSaver connectivity and fault sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import AquagemEntity


@dataclass(frozen=True, kw_only=True)
class AquagemFaultDescription(BinarySensorEntityDescription):
    """Description of one documented 2001 fault bit."""

    bit: int


FAULTS: tuple[AquagemFaultDescription, ...] = (
    AquagemFaultDescription(key="rs485_error", translation_key="rs485_error", bit=4),
    AquagemFaultDescription(
        key="temperature_derating",
        translation_key="temperature_derating",
        bit=5,
    ),
    AquagemFaultDescription(
        key="keypad_communication_error",
        translation_key="keypad_communication_error",
        bit=6,
    ),
    AquagemFaultDescription(
        key="keypad_eeprom_error",
        translation_key="keypad_eeprom_error",
        bit=7,
    ),
    AquagemFaultDescription(key="rtc_error", translation_key="rtc_error", bit=8),
    AquagemFaultDescription(
        key="main_eeprom_error",
        translation_key="main_eeprom_error",
        bit=9,
    ),
    AquagemFaultDescription(
        key="current_detection_error",
        translation_key="current_detection_error",
        bit=10,
    ),
    AquagemFaultDescription(
        key="main_drive_error",
        translation_key="main_drive_error",
        bit=11,
    ),
    AquagemFaultDescription(
        key="heatsink_sensor_error",
        translation_key="heatsink_sensor_error",
        bit=12,
    ),
    AquagemFaultDescription(
        key="heatsink_overheat",
        translation_key="heatsink_overheat",
        bit=13,
    ),
    AquagemFaultDescription(
        key="overcurrent",
        translation_key="overcurrent",
        bit=14,
    ),
    AquagemFaultDescription(
        key="input_voltage_error",
        translation_key="input_voltage_error",
        bit=15,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AquagemConnectivity(coordinator, entry),
            AquagemAlarm(coordinator, entry),
            *(
                AquagemFaultBinarySensor(coordinator, entry, description)
                for description in FAULTS
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
    def is_on(self):
        return self.coordinator.last_update_success


class AquagemAlarm(AquagemEntity, BinarySensorEntity):
    """Global alarm derived from the complete 2001 fault word."""

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
    """One documented fault bit from register 2001."""

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
