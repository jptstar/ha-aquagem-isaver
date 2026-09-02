"""Update coordinator for supported Aquagem pump protocols."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import PROTOCOL_ISAVER
from .protocol import AquagemClient, AquagemError, AquagemStatus


class AquagemCoordinator(DataUpdateCoordinator[AquagemStatus]):
    """Coordinate polling and commands."""

    def __init__(self, hass: HomeAssistant, client: AquagemClient, interval: int) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name="Aquagem pump",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.last_running_speed = client.minimum_speed
        self.active_preset: str | None = None
        self.active_preset_speed: int | None = None

    async def _async_update_data(self) -> AquagemStatus:
        try:
            status = await self.client.read_status()
        except AquagemError as err:
            raise UpdateFailed(str(err)) from err

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
