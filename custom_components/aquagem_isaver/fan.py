"""Aquagem iSaver fan-style pump control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_DAY_SPEED,
    CONF_ECO_SPEED,
    CONF_MAX_OPERATING_SPEED,
    CONF_MAX_PRESET_SPEED,
    CONF_MIN_OPERATING_SPEED,
    CONF_NIGHT_SPEED,
    DEFAULT_DAY_SPEED,
    DEFAULT_ECO_SPEED,
    DEFAULT_MAX_OPERATING_SPEED,
    DEFAULT_MAX_PRESET_SPEED,
    DEFAULT_MIN_OPERATING_SPEED,
    DEFAULT_NIGHT_SPEED,
    DOMAIN,
    OFF_COMMAND,
    PRESET_CUSTOM,
    PRESET_DAY,
    PRESET_ECO,
    PRESET_MAX,
    PRESET_NIGHT,
    SPEED_STEP,
)
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the iSaver fan entity."""
    async_add_entities([AquagemPumpFan(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemPumpFan(AquagemEntity, FanEntity):
    """Variable-speed pool pump represented as a Home Assistant fan."""

    _attr_translation_key = "pump"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        # Reuse the old pump identity so existing customizations can migrate cleanly.
        self._attr_unique_id = f"{entry.entry_id}_pump"

    @property
    def _minimum_speed(self) -> int:
        return self._entry.options.get(
            CONF_MIN_OPERATING_SPEED, DEFAULT_MIN_OPERATING_SPEED
        )

    @property
    def _maximum_speed(self) -> int:
        return self._entry.options.get(
            CONF_MAX_OPERATING_SPEED, DEFAULT_MAX_OPERATING_SPEED
        )

    @property
    def _preset_speeds(self) -> dict[str, int]:
        options = self._entry.options
        return {
            PRESET_MAX: options.get(CONF_MAX_PRESET_SPEED, DEFAULT_MAX_PRESET_SPEED),
            PRESET_DAY: options.get(CONF_DAY_SPEED, DEFAULT_DAY_SPEED),
            PRESET_ECO: options.get(CONF_ECO_SPEED, DEFAULT_ECO_SPEED),
            PRESET_NIGHT: options.get(CONF_NIGHT_SPEED, DEFAULT_NIGHT_SPEED),
        }

    def _normalize_speed(self, speed: float) -> int:
        """Clamp a command to configured limits and the 100 rpm control grid."""
        speed = round(speed / SPEED_STEP) * SPEED_STEP
        return min(self._maximum_speed, max(self._minimum_speed, int(speed)))

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return None if data is None else data.pump_on

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        if data is None:
            return None
        if not data.pump_on:
            return 0

        speed = min(self._maximum_speed, max(self._minimum_speed, data.speed))
        return ranged_value_to_percentage(
            (self._minimum_speed, self._maximum_speed), speed
        )

    @property
    def speed_count(self) -> int:
        return ((self._maximum_speed - self._minimum_speed) // SPEED_STEP) + 1

    @property
    def preset_modes(self) -> list[str]:
        return [*self._preset_speeds, PRESET_CUSTOM]

    @property
    def preset_mode(self) -> str | None:
        data = self.coordinator.data
        if data is None or not data.pump_on:
            return None

        for preset, speed in self._preset_speeds.items():
            if data.speed == speed:
                return preset

        return PRESET_CUSTOM

    async def async_set_percentage(self, percentage: int) -> None:
        """Set pump speed from Home Assistant's 0-100% fan control."""
        if percentage <= 0:
            await self.coordinator.async_set_speed(OFF_COMMAND)
            return

        raw_speed = percentage_to_ranged_value(
            (self._minimum_speed, self._maximum_speed), percentage
        )
        await self.coordinator.async_set_speed(self._normalize_speed(raw_speed))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Apply a configurable Home Assistant speed profile."""
        if preset_mode == PRESET_CUSTOM:
            # "Perso" describes any running speed that does not match a preset.
            # It has no fixed RPM of its own, so selecting it leaves the speed unchanged.
            return

        try:
            speed = self._preset_speeds[preset_mode]
        except KeyError as err:
            raise ValueError(f"Unsupported preset mode: {preset_mode}") from err
        await self.coordinator.async_set_speed(speed, preset=preset_mode)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on, optionally with a percentage or profile."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        await self.coordinator.async_set_speed(
            self._normalize_speed(self.coordinator.last_running_speed)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off with the validated value-1 command."""
        await self.coordinator.async_set_speed(OFF_COMMAND)
