"""Aquagem direct speed/capacity command."""

from homeassistant.components.number import NumberEntity, NumberMode

from .const import (
    CONF_MAX_OPERATING_SPEED,
    CONF_MIN_OPERATING_SPEED,
    DEFAULT_MAX_OPERATING_SPEED,
    DEFAULT_MIN_OPERATING_SPEED,
    DOMAIN,
)
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the direct protocol-native setpoint entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AquagemSpeedNumber(coordinator, entry)])


class AquagemSpeedNumber(AquagemEntity, NumberEntity):
    """Direct RS485 speed/capacity setpoint for advanced/manual control."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)

        if coordinator.client.is_pump_modbus:
            self._attr_unique_id = f"{entry.entry_id}_capacity_command"
            self._attr_translation_key = "capacity_command"
            self._attr_native_unit_of_measurement = "%"
            self._attr_native_step = coordinator.client.speed_step
            self._attr_native_min_value = coordinator.client.minimum_speed
            self._attr_native_max_value = coordinator.client.maximum_speed
        else:
            # Preserve the released iSaver identity for existing installations.
            self._attr_unique_id = f"{entry.entry_id}_speed_command"
            self._attr_translation_key = "speed_command"
            self._attr_native_unit_of_measurement = "rpm"
            self._attr_native_step = coordinator.client.speed_step
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
        step = self.coordinator.client.speed_step
        if self.coordinator.client.is_pump_modbus:
            # The pump rounds unsupported percentages down to its 5% grid.
            speed = int(value) // step * step
        else:
            speed = round(value / step) * step
        speed = min(self._attr_native_max_value, max(self._attr_native_min_value, speed))
        await self.coordinator.async_set_speed(int(speed))
