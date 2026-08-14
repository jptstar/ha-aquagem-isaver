"""Update coordinator for Aquagem iSaver Power."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .protocol import AquagemClient, AquagemError


class AquagemCoordinator(DataUpdateCoordinator[dict[str, int]]):
    """Coordinate polling and commands."""

    def __init__(self, hass: HomeAssistant, client: AquagemClient, interval: int) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name="Aquagem iSaver Power",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.last_running_speed = 1200

    async def _async_update_data(self) -> dict[str, int]:
        try:
            speed = await self.client.read_speed()
        except AquagemError as err:
            raise UpdateFailed(str(err)) from err
        if speed >= 1200:
            self.last_running_speed = speed
        return {"speed": speed}

    async def async_set_speed(self, speed: int) -> None:
        await self.client.write_speed(speed)
        if speed >= 1200:
            self.last_running_speed = speed
        self.async_set_updated_data({"speed": speed})
