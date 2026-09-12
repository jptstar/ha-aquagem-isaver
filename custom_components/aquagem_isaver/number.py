"""Aquagem direct speed/capacity command and local-panel timing control."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_MAX_OPERATING_SPEED,
    CONF_MIN_OPERATING_SPEED,
    DEFAULT_MAX_OPERATING_SPEED,
    DEFAULT_MIN_OPERATING_SPEED,
    DOMAIN,
    MAX_IDLE_SCAN_INTERVAL,
)
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up protocol-native setpoint and local-panel timing controls."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AquagemSpeedNumber(coordinator, entry),
            AquagemIdlePollingIntervalNumber(coordinator, entry),
        ]
    )


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


class AquagemIdlePollingIntervalNumber(AquagemEntity, NumberEntity, RestoreEntity):
    """Post-command bus silence used by local-panel assist."""

    # Keep the beta translation key and unique ID so existing installations retain
    # their entity registry entry and restored value. In 0.4.2 the entity's
    # meaning is explicitly the post-command silence, not a permanent idle poll.
    _attr_translation_key = "idle_polling_interval"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_step = 5
    _attr_native_max_value = MAX_IDLE_SCAN_INTERVAL

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_idle_polling_interval"
        self._attr_native_min_value = coordinator.minimum_idle_scan_interval_seconds

    @property
    def available(self) -> bool:
        """Keep the configuration number available while the pump is offline."""
        return True

    @property
    def native_value(self):
        return self.coordinator.idle_scan_interval_seconds

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        try:
            restored = float(last_state.state)
        except (TypeError, ValueError):
            return
        self.coordinator.set_idle_scan_interval(restored)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.set_idle_scan_interval(value)
        self.async_write_ha_state()
