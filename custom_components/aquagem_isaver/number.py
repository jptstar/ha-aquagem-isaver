"""Aquagem iSaver direct RPM command."""

from homeassistant.components.number import NumberEntity, NumberMode

from .const import (
    CONF_MAX_OPERATING_SPEED,
    CONF_MIN_OPERATING_SPEED,
    DEFAULT_MAX_OPERATING_SPEED,
    DEFAULT_MIN_OPERATING_SPEED,
    DOMAIN,
    SPEED_STEP,
)
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AquagemSpeedNumber(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemSpeedNumber(AquagemEntity, NumberEntity):
    """Direct RS485 RPM setpoint for advanced/manual control."""

    _attr_translation_key = "speed_command"
    _attr_native_step = SPEED_STEP
    _attr_native_unit_of_measurement = "rpm"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_speed_command"
        self._attr_native_min_value = entry.options.get(
            CONF_MIN_OPERATING_SPEED, DEFAULT_MIN_OPERATING_SPEED
        )
        self._attr_native_max_value = entry.options.get(
            CONF_MAX_OPERATING_SPEED, DEFAULT_MAX_OPERATING_SPEED
        )

    @property
    def native_value(self):
        data = self.coordinator.data
        speed = (
            data.speed
            if data is not None and data.pump_on
            else self.coordinator.last_running_speed
        )
        return min(self._attr_native_max_value, max(self._attr_native_min_value, speed))

    async def async_set_native_value(self, value: float) -> None:
        speed = round(value / SPEED_STEP) * SPEED_STEP
        speed = min(self._attr_native_max_value, max(self._attr_native_min_value, speed))
        await self.coordinator.async_set_speed(speed)
