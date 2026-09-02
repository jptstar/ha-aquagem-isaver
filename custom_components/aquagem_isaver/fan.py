"""Aquagem variable-speed pool pump control."""

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
    PRESET_CUSTOM,
    PRESET_DAY,
    PRESET_ECO,
    PRESET_MAX,
    PRESET_NIGHT,
)
from .entity import AquagemEntity

# Accept labels used by 0.2.5 and common English equivalents when called from
# existing automations. New state/service values remain language-neutral.
_LEGACY_PRESET_ALIASES = {
    "Max": PRESET_MAX,
    "Jour": PRESET_DAY,
    "Eco": PRESET_ECO,
    "Nuit": PRESET_NIGHT,
    "Perso": PRESET_CUSTOM,
    "Day": PRESET_DAY,
    "Night": PRESET_NIGHT,
    "Custom": PRESET_CUSTOM,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Aquagem pump fan entity."""
    async_add_entities([AquagemPumpFan(hass.data[DOMAIN][entry.entry_id], entry)])


class AquagemPumpFan(AquagemEntity, FanEntity):
    """Variable-speed pool pump represented as a Home Assistant fan."""

    _attr_translation_key = "pump"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pump"

    @property
    def supported_features(self) -> FanEntityFeature:
        features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        # Max/Day/Eco/Night are Home Assistant RPM shortcuts for the iSaver.
        # Standard Modbus pumps expose their native 30..100% capacity directly.
        if not self.coordinator.client.is_pump_modbus:
            features |= FanEntityFeature.PRESET_MODE
        return features

    @property
    def _minimum_speed(self) -> int:
        if self.coordinator.client.is_pump_modbus:
            return self.coordinator.client.minimum_speed
        return self._entry.options.get(
            CONF_MIN_OPERATING_SPEED, DEFAULT_MIN_OPERATING_SPEED
        )

    @property
    def _maximum_speed(self) -> int:
        if self.coordinator.client.is_pump_modbus:
            return self.coordinator.client.maximum_speed
        return self._entry.options.get(
            CONF_MAX_OPERATING_SPEED, DEFAULT_MAX_OPERATING_SPEED
        )

    @property
    def _speed_step(self) -> int:
        return self.coordinator.client.speed_step

    @property
    def _preset_speeds(self) -> dict[str, int]:
        if self.coordinator.client.is_pump_modbus:
            return {}
        options = self._entry.options
        return {
            PRESET_MAX: options.get(CONF_MAX_PRESET_SPEED, DEFAULT_MAX_PRESET_SPEED),
            PRESET_DAY: options.get(CONF_DAY_SPEED, DEFAULT_DAY_SPEED),
            PRESET_ECO: options.get(CONF_ECO_SPEED, DEFAULT_ECO_SPEED),
            PRESET_NIGHT: options.get(CONF_NIGHT_SPEED, DEFAULT_NIGHT_SPEED),
        }

    def _normalize_speed(self, speed: float) -> int:
        """Clamp a command to the active protocol limits and control grid."""
        speed = round(speed / self._speed_step) * self._speed_step
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

        if self.coordinator.client.is_pump_modbus:
            # Register 2003 is already the physical running-capacity percentage.
            return min(100, max(0, int(data.speed)))

        speed = min(self._maximum_speed, max(self._minimum_speed, data.speed))
        return ranged_value_to_percentage(
            (self._minimum_speed, self._maximum_speed), speed
        )

    @property
    def speed_count(self) -> int:
        if self.coordinator.client.is_pump_modbus:
            # Keep Home Assistant's slider on a 1% grid. Commands from 1..29%
            # are safely clamped to the documented 30% physical minimum.
            return 100
        return ((self._maximum_speed - self._minimum_speed) // self._speed_step) + 1

    @property
    def preset_modes(self) -> list[str]:
        if self.coordinator.client.is_pump_modbus:
            return []
        return [*self._preset_speeds, PRESET_CUSTOM]

    @property
    def preset_mode(self) -> str | None:
        data = self.coordinator.data
        if self.coordinator.client.is_pump_modbus or data is None or not data.pump_on:
            return None

        for preset, speed in self._preset_speeds.items():
            if data.speed == speed:
                return preset
        return PRESET_CUSTOM

    async def async_set_percentage(self, percentage: int) -> None:
        """Set pump speed from Home Assistant's 0-100% fan control."""
        if percentage <= 0:
            await self.coordinator.async_set_speed(self.coordinator.client.off_command)
            return

        if self.coordinator.client.is_pump_modbus:
            await self.coordinator.async_set_speed(self._normalize_speed(percentage))
            return

        raw_speed = percentage_to_ranged_value(
            (self._minimum_speed, self._maximum_speed), percentage
        )
        await self.coordinator.async_set_speed(self._normalize_speed(raw_speed))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Apply a configurable iSaver Home Assistant speed profile."""
        if self.coordinator.client.is_pump_modbus:
            raise ValueError("Preset modes are not used by percentage-based Modbus pumps")

        preset_mode = _LEGACY_PRESET_ALIASES.get(preset_mode, preset_mode)
        if preset_mode == PRESET_CUSTOM:
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
        """Turn on, optionally with a percentage or iSaver profile."""
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
        """Turn the pump off with the command validated for its protocol."""
        await self.coordinator.async_set_speed(self.coordinator.client.off_command)
