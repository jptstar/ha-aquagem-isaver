"""Update coordinator for supported Aquagem pump protocols."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_OFFLINE_SCAN_INTERVAL,
    PROTOCOL_ISAVER,
)
from .protocol import AquagemClient, AquagemError, AquagemStatus

_LOGGER = logging.getLogger(__name__)


class AquagemCoordinator(DataUpdateCoordinator[AquagemStatus]):
    """Coordinate polling and commands."""

    def __init__(self, hass: HomeAssistant, client: AquagemClient, interval: int) -> None:
        self._normal_update_interval = timedelta(seconds=interval)
        self._offline_update_interval = timedelta(
            seconds=max(DEFAULT_OFFLINE_SCAN_INTERVAL, interval)
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquagem pump",
            update_interval=self._normal_update_interval,
        )
        self.client = client
        self.last_running_speed = client.minimum_speed
        self.active_preset: str | None = None
        self.active_preset_speed: int | None = None
        self.communication_online: bool | None = None
        self.consecutive_failures = 0
        self.failure_threshold = DEFAULT_FAILURE_THRESHOLD
        self.last_communication_error: str | None = None

    async def _async_update_data(self) -> AquagemStatus:
        try:
            status = await self.client.read_status()
        except AquagemError as err:
            self.consecutive_failures += 1
            self.last_communication_error = str(err)

            # Preserve startup behavior: without any validated data yet, a failed
            # refresh must still be reported to Home Assistant.
            if self.data is None:
                self.communication_online = False
                raise UpdateFailed(str(err)) from err

            if self.consecutive_failures >= self.failure_threshold:
                if self.communication_online is not False:
                    _LOGGER.warning(
                        "Aquagem pump is unavailable after %s consecutive "
                        "communication failures (%s); polling reduced to every "
                        "%s seconds",
                        self.consecutive_failures,
                        type(err).__name__,
                        int(self._offline_update_interval.total_seconds()),
                    )
                self.communication_online = False
                self.update_interval = self._offline_update_interval
            else:
                self.communication_online = True
                self.update_interval = self._normal_update_interval
                _LOGGER.debug(
                    "Aquagem communication attempt failed (%s/%s, %s); keeping "
                    "the pump available and retrying in %s seconds",
                    self.consecutive_failures,
                    self.failure_threshold,
                    type(err).__name__,
                    int(self._normal_update_interval.total_seconds()),
                )

            # Match TSUN Local's resilience model: keep the last validated state
            # during communication failures. Entity availability is driven by
            # communication_online instead of one isolated failed poll.
            return self.data

        if self.communication_online is False:
            _LOGGER.info("Aquagem pump communication restored; normal polling resumed")

        self.communication_online = True
        self.consecutive_failures = 0
        self.last_communication_error = None
        self.update_interval = self._normal_update_interval

        if not self.client.minimum_speed <= self.last_running_speed <= self.client.maximum_speed:
            self.last_running_speed = self.client.minimum_speed

        if status.pump_on and status.speed >= self.client.minimum_speed:
            self.last_running_speed = status.speed

        if (
            not status.pump_on
            or self.active_preset_speed is None
            or status.speed != self.active_preset_speed
        ):
            self.active_preset = None
            self.active_preset_speed = None

        return status

    async def async_set_speed(self, speed: int, preset: str | None = None) -> None:
        """Write a command and publish an optimistic state until the next poll."""
        await self.client.write_speed(speed)

        current = self.data or AquagemStatus(
            fault_code=0,
            pump_on=False,
            speed=0,
            protocol=self.client.protocol or PROTOCOL_ISAVER,
        )

        if speed == self.client.off_command:
            self.active_preset = None
            self.active_preset_speed = None
            optimistic = replace(current, pump_on=False, speed=0)
        else:
            self.last_running_speed = speed
            self.active_preset = preset
            self.active_preset_speed = speed if preset is not None else None
            optimistic = replace(current, pump_on=True, speed=speed)

        self.async_set_updated_data(optimistic)
