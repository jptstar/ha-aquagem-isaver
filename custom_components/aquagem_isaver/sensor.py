"""Aquagem iSaver sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import AquagemEntity


POWER_CALIBRATION_POINTS = (
    (1200, 120),
    (1550, 176),
    (2000, 328),
    (2400, 532),
    (2900, 936),
)
POWER_ESTIMATE_TOLERANCE_W = 10


def estimate_power_w(rpm: int) -> int | None:
    """Estimate input power from the measured RPM/power calibration curve."""
    if rpm <= 0:
        return 0

    if rpm < POWER_CALIBRATION_POINTS[0][0] or rpm > POWER_CALIBRATION_POINTS[-1][0]:
        return None

    for (rpm_low, watts_low), (rpm_high, watts_high) in zip(
        POWER_CALIBRATION_POINTS,
        POWER_CALIBRATION_POINTS[1:],
        strict=True,
    ):
        if rpm_low <= rpm <= rpm_high:
            if rpm == rpm_low:
                return watts_low
            if rpm == rpm_high:
                return watts_high

            ratio = (rpm - rpm_low) / (rpm_high - rpm_low)
            return round(watts_low + ratio * (watts_high - watts_low))

    return None


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AquagemSpeedSensor(coordinator, entry),
            AquagemEstimatedPowerSensor(coordinator, entry),
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


class AquagemEstimatedPowerSensor(AquagemEntity, SensorEntity):
    """Estimated electrical power from measured panel calibration points."""

    _attr_translation_key = "estimated_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_estimated_power"

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None:
            return None
        if not data.pump_on:
            return 0
        return estimate_power_w(data.speed)

    @property
    def extra_state_attributes(self):
        value = self.native_value
        attributes = {
            "estimate_tolerance_w": POWER_ESTIMATE_TOLERANCE_W,
            "method": "piecewise_linear_interpolation",
            "calibration_points": ", ".join(
                f"{rpm} rpm={watts} W" for rpm, watts in POWER_CALIBRATION_POINTS
            ),
        }
        if value is not None:
            attributes["estimated_min_w"] = max(0, value - POWER_ESTIMATE_TOLERANCE_W)
            attributes["estimated_max_w"] = value + POWER_ESTIMATE_TOLERANCE_W
        return attributes


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
