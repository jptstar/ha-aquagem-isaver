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
    LOCAL_CONTROL_COMMAND_SETTLE_SECONDS,
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
        self._idle_scan_interval_seconds = DEFAULT_IDLE_SCAN_INTERVAL
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

        # Local-panel coexistence is a temporary post-command silence, not a
        # permanently slow polling mode. Real-hardware iSaver tests established
        # that C3 reads during the remote-override window prolong that override,
        # while C3 reads after the watchdog has expired do not re-apply the old
        # D0 command. The same generic quiet-window mechanism is available to the
        # Modbus/DM profile after Home Assistant writes.
        self.local_control_assist = DEFAULT_LOCAL_CONTROL_ASSIST
        self.last_change_source = CHANGE_SOURCE_UNKNOWN
        self._quiet_until = 0.0
        self._last_ha_command_at = 0.0
        self._pending_ha_target: tuple[bool, int] | None = None

    @property
    def normal_scan_interval_seconds(self) -> int:
        """Return the configured normal polling interval."""
        return int(self._normal_update_interval.total_seconds())

    @property
    def minimum_idle_scan_interval_seconds(self) -> int:
        """Return the minimum configurable post-command silence."""
        return MIN_IDLE_SCAN_INTERVAL

    @property
    def idle_scan_interval_seconds(self) -> int:
        """Return the configured post-command silence in seconds."""
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

    def _quiet_update_interval(self, remaining: float | None = None) -> timedelta:
        """Return an interval that respects both silence and normal polling."""
        silence = (
            self._idle_scan_interval_seconds
            if remaining is None
            else max(0.0, remaining)
        )
        return timedelta(
            seconds=max(float(self.normal_scan_interval_seconds), silence)
        )

    def set_local_control_assist(self, enabled: bool) -> None:
        """Enable or disable the post-command local-panel quiet window."""
        self.local_control_assist = bool(enabled)

        if not self.local_control_assist:
            # Disabling the feature immediately restores normal polling. It does
            # not send a read by itself; the existing coordinator timer is simply
            # rescheduled from the current validated state.
            self._quiet_until = 0.0
            if self.communication_online is not False:
                self.update_interval = self._normal_update_interval
        elif self.communication_online is not False:
            # Enabling the feature while idle must not create an artificial quiet
            # period. Silence begins only after the next Home Assistant write.
            self.update_interval = self._normal_update_interval

        self._reschedule_current_data()

    def set_idle_scan_interval(self, seconds: int | float) -> None:
        """Update the post-command local-panel silence duration."""
        value = max(
            MIN_IDLE_SCAN_INTERVAL,
            min(MAX_IDLE_SCAN_INTERVAL, int(round(seconds))),
        )
        self._idle_scan_interval_seconds = value

        now = monotonic()
        if (
            self.local_control_assist
            and self._last_ha_command_at > 0.0
            and now < self._quiet_until
        ):
            # If the user adjusts the value during an active quiet window, apply
            # the new duration relative to the most recent Home Assistant write.
            self._quiet_until = self._last_ha_command_at + value
            remaining = self._quiet_until - now
            if remaining > 0:
                self.update_interval = self._quiet_update_interval(remaining)
            else:
                self._quiet_until = 0.0
                self.update_interval = self._normal_update_interval
        elif self.communication_online is not False:
            self.update_interval = self._normal_update_interval

        self._reschedule_current_data()

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
                self.last_change_source = CHANGE_SOURCE_HOME_ASSISTANT
                self._pending_ha_target = None
            elif (
                now - self._last_ha_command_at
                >= LOCAL_CONTROL_COMMAND_SETTLE_SECONDS
            ):
                # After a protected quiet window, a different real state is the
                # local/external state. Never force the optimistic HA value back.
                self.last_change_source = CHANGE_SOURCE_EXTERNAL
                self._pending_ha_target = None
            return

        if previous is not None and self._control_state(previous) != actual:
            self.last_change_source = CHANGE_SOURCE_EXTERNAL

    async def _async_update_data(self) -> AquagemStatus:
        # Enforce the quiet window even if Home Assistant requests an early
        # coordinator refresh. No C3/Modbus status request may escape during this
        # period, because a read can itself prolong remote priority on iSaver.
        now = monotonic()
        if (
            self.local_control_assist
            and self.data is not None
            and now < self._quiet_until
        ):
            self.update_interval = self._quiet_update_interval(
                self._quiet_until - now
            )
            return self.data

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
        self._quiet_until = 0.0
        self.communication_online = True
        self.consecutive_failures = 0
        self.last_communication_error = None
        self._track_change_source(previous, status, now)
        self.update_interval = self._normal_update_interval
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

        if self.local_control_assist:
            # Start a true no-read window after every Home Assistant write. A new
            # HA command during the window is still allowed and simply restarts
            # the timer from this latest write.
            self._quiet_until = now + self._idle_scan_interval_seconds
            self.update_interval = self._quiet_update_interval()
        else:
            self._quiet_until = 0.0
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

        # Publishing the optimistic state also schedules the next coordinator
        # refresh using the quiet interval selected above.
        self.async_set_updated_data(optimistic)
