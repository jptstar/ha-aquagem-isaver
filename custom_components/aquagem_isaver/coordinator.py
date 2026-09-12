"""Update coordinator for supported Aquagem pump protocols."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import logging
from time import monotonic

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHANGE_SOURCE_EXTERNAL,
    CHANGE_SOURCE_HOME_ASSISTANT,
    CHANGE_SOURCE_UNKNOWN,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_LOCAL_CONTROL_ASSIST,
    DEFAULT_OFFLINE_SCAN_INTERVAL,
    ISAVER_MIN_IDLE_SCAN_INTERVAL,
    LOCAL_CONTROL_COMMAND_SETTLE_SECONDS,
    LOCAL_CONTROL_FAST_WINDOW_SECONDS,
    MAX_IDLE_SCAN_INTERVAL,
    MIN_IDLE_SCAN_INTERVAL,
    PROTOCOL_ISAVER,
)
from .protocol import AquagemClient, AquagemError, AquagemStatus
from .runtime import AquagemRuntimeTracker

_LOGGER = logging.getLogger(__name__)


class AquagemCoordinator(DataUpdateCoordinator[AquagemStatus]):
    """Coordinate polling, commands and the software operating-hours counter."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AquagemClient,
        interval: int,
        runtime_tracker: AquagemRuntimeTracker,
    ) -> None:
        self.client = client
        self._normal_update_interval = timedelta(seconds=interval)
        self._offline_update_interval = timedelta(
            seconds=max(DEFAULT_OFFLINE_SCAN_INTERVAL, interval)
        )
        minimum_idle = (
            ISAVER_MIN_IDLE_SCAN_INTERVAL
            if client.protocol == PROTOCOL_ISAVER
            else MIN_IDLE_SCAN_INTERVAL
        )
        self._idle_scan_interval_seconds = max(
            DEFAULT_IDLE_SCAN_INTERVAL, interval, minimum_idle
        )
        self._idle_update_interval = timedelta(
            seconds=self._idle_scan_interval_seconds
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquagem pump",
            update_interval=self._normal_update_interval,
        )
        self.runtime_tracker = runtime_tracker
        self.last_running_speed = client.minimum_speed
        self.active_preset: str | None = None
        self.active_preset_speed: int | None = None
        self.communication_online: bool | None = None
        self.consecutive_failures = 0
        self.failure_threshold = DEFAULT_FAILURE_THRESHOLD
        self.last_communication_error: str | None = None

        # Opt-in adaptive polling. Standard Modbus pumps simply need useful quiet
        # gaps between transactions. The proprietary iSaver C3/D0 profile is
        # different: C3 reads made more often than 60 seconds keep a preceding D0
        # remote-speed override alive, so its idle interval must exceed that
        # watchdog before the panel/manual state can regain priority.
        self.local_control_assist = DEFAULT_LOCAL_CONTROL_ASSIST
        self.last_change_source = CHANGE_SOURCE_UNKNOWN
        self._fast_poll_until = 0.0
        self._last_ha_command_at = 0.0
        self._pending_ha_target: tuple[bool, int] | None = None

    @property
    def normal_scan_interval_seconds(self) -> int:
        """Return the configured fast polling interval."""
        return int(self._normal_update_interval.total_seconds())

    @property
    def minimum_idle_scan_interval_seconds(self) -> int:
        """Return the protocol-safe minimum interval for local-panel assist."""
        protocol_minimum = (
            ISAVER_MIN_IDLE_SCAN_INTERVAL
            if self.client.protocol == PROTOCOL_ISAVER
            else MIN_IDLE_SCAN_INTERVAL
        )
        return max(protocol_minimum, self.normal_scan_interval_seconds)

    @property
    def idle_scan_interval_seconds(self) -> int:
        """Return the adaptive idle polling interval."""
        return self._idle_scan_interval_seconds

    @staticmethod
    def _control_state(status: AquagemStatus) -> tuple[bool, int]:
        """Return the comparable ON/OFF and active-speed state."""
        return status.pump_on, status.speed if status.pump_on else 0

    def _reschedule_current_data(self) -> None:
        """Apply a changed interval immediately without forcing a bus read."""
        if self.data is not None and self.communication_online is not False:
            # async_set_updated_data cancels the old timer and schedules the next
            # refresh from the currently selected interval. Re-publishing the
            # same validated data is intentional: changing a configuration entity
            # must not itself generate an RS485/TCP transaction.
            self.async_set_updated_data(self.data)

    def set_local_control_assist(self, enabled: bool) -> None:
        """Enable or disable adaptive local-panel-friendly polling."""
        self.local_control_assist = bool(enabled)
        if self.local_control_assist:
            # Enter idle mode immediately when the user enables the feature.
            # For iSaver this creates the >60 s C3 silence required to let a
            # previous D0 remote override expire. A later HA command wakes fast
            # polling until that command has been observed.
            self._fast_poll_until = 0.0
            if self.communication_online is not False:
                self.update_interval = self._idle_update_interval
        elif self.communication_online is not False:
            self.update_interval = self._normal_update_interval
        self._reschedule_current_data()

    def set_idle_scan_interval(self, seconds: int | float) -> None:
        """Update the local-control idle polling interval."""
        minimum = self.minimum_idle_scan_interval_seconds
        value = max(minimum, min(MAX_IDLE_SCAN_INTERVAL, int(round(seconds))))
        self._idle_scan_interval_seconds = value
        self._idle_update_interval = timedelta(seconds=value)
        if (
            self.local_control_assist
            and self.communication_online is not False
            and monotonic() >= self._fast_poll_until
        ):
            self.update_interval = self._idle_update_interval
            self._reschedule_current_data()

    def _set_success_polling_interval(self, now: float) -> None:
        """Select fast or idle polling after a successful read."""
        if self.local_control_assist and now >= self._fast_poll_until:
            self.update_interval = self._idle_update_interval
        else:
            self.update_interval = self._normal_update_interval

    def _track_change_source(
        self,
        previous: AquagemStatus | None,
        status: AquagemStatus,
        now: float,
    ) -> None:
        """Classify pump state/capacity changes without writing anything back."""
        actual = self._control_state(status)

        if self._pending_ha_target is not None:
            if actual == self._pending_ha_target:
                # The command written by Home Assistant has been observed on the
                # wire; subsequent changes can again be classified as external.
                self.last_change_source = CHANGE_SOURCE_HOME_ASSISTANT
                self._pending_ha_target = None

                # On iSaver, every additional C3 read inside the 60 s watchdog
                # prolongs the D0 remote override. Once the requested state has
                # been confirmed, immediately start the long idle gap instead of
                # keeping the generic 30 s fast window alive.
                if (
                    self.local_control_assist
                    and self.client.protocol == PROTOCOL_ISAVER
                ):
                    self._fast_poll_until = 0.0
            elif (
                now - self._last_ha_command_at
                >= LOCAL_CONTROL_COMMAND_SETTLE_SECONDS
            ):
                # A command that still does not match after the settle period is
                # treated as an external/local change instead of being forced
                # back to the optimistic Home Assistant value.
                if previous is not None and self._control_state(previous) != actual:
                    self.last_change_source = CHANGE_SOURCE_EXTERNAL
                    self._pending_ha_target = None
                    self._fast_poll_until = 0.0
            return

        if previous is not None and self._control_state(previous) != actual:
            self.last_change_source = CHANGE_SOURCE_EXTERNAL
            # Keep the slower idle cadence after a physical/external change so
            # the person at the panel receives another useful silent window.
            self._fast_poll_until = 0.0

    async def _async_update_data(self) -> AquagemStatus:
        previous = self.data
        try:
            status = await self.client.read_status()
        except AquagemError as err:
            self.consecutive_failures += 1
            self.last_communication_error = str(err)

            # Preserve startup behavior: without any validated data yet, a failed
            # refresh must still be reported to Home Assistant.
            if self.data is None:
                self.communication_online = False
                self.runtime_tracker.pause()
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
                # Do not keep accumulating indefinitely from a stale ON state.
                self.runtime_tracker.pause()
            else:
                self.communication_online = True
                # Short failures retry at the normal interval to distinguish a
                # transient error from a genuine offline device quickly.
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

        now = monotonic()
        self.communication_online = True
        self.consecutive_failures = 0
        self.last_communication_error = None
        self._track_change_source(previous, status, now)
        self._set_success_polling_interval(now)
        self.runtime_tracker.update_running(status.pump_on)

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

        now = monotonic()
        target_on = speed != self.client.off_command
        target_speed = speed if target_on else 0
        self.last_change_source = CHANGE_SOURCE_HOME_ASSISTANT
        self._last_ha_command_at = now
        self._pending_ha_target = (target_on, target_speed)
        self._fast_poll_until = now + LOCAL_CONTROL_FAST_WINDOW_SECONDS
        # A Home Assistant command always wakes the fast polling cadence. Do not
        # force an immediate read: the released iSaver path intentionally avoids
        # reading directly after its write-only D0 frame.
        self.update_interval = self._normal_update_interval

        current = self.data or AquagemStatus(
            fault_code=0,
            pump_on=False,
            speed=0,
            protocol=self.client.protocol or PROTOCOL_ISAVER,
        )

        if not target_on:
            self.active_preset = None
            self.active_preset_speed = None
            optimistic = replace(current, pump_on=False, speed=0)
            self.runtime_tracker.update_running(False)
        else:
            self.last_running_speed = speed
            self.active_preset = preset
            self.active_preset_speed = speed if preset is not None else None
            optimistic = replace(current, pump_on=True, speed=speed)
            self.runtime_tracker.update_running(True)

        self.async_set_updated_data(optimistic)
