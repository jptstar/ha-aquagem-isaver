"""Persistent software operating-hours counter for Aquagem pumps."""

from __future__ import annotations

from time import monotonic

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_STORAGE_VERSION = 1
_SAVE_INTERVAL_SECONDS = 60.0


def _storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.runtime_{entry_id}"


class AquagemRuntimeTracker:
    """Accumulate confirmed pump running time and persist it across restarts."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        initial_hours: float = 0.0,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, _STORAGE_VERSION, _storage_key(entry_id))
        self._initial_seconds = max(0.0, float(initial_hours) * 3600.0)
        self._total_seconds = self._initial_seconds
        self._running = False
        self._last_tick: float | None = None
        self._next_save_due = 0.0

    async def async_load(self) -> None:
        """Load the persisted counter, or initialize it from the configured base."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            try:
                self._total_seconds = max(0.0, float(stored["total_seconds"]))
            except (KeyError, TypeError, ValueError):
                self._total_seconds = self._initial_seconds
        else:
            self._total_seconds = self._initial_seconds
            await self._store.async_save(self._data_to_save())

        self._running = False
        self._last_tick = monotonic()
        self._next_save_due = monotonic() + _SAVE_INTERVAL_SECONDS

    def _accrue_to(self, now: float) -> None:
        if self._last_tick is not None and self._running:
            self._total_seconds += max(0.0, now - self._last_tick)
        self._last_tick = now

    @callback
    def _data_to_save(self) -> dict[str, float]:
        total_seconds = self._total_seconds
        if self._running and self._last_tick is not None:
            total_seconds += max(0.0, monotonic() - self._last_tick)
        return {"total_seconds": total_seconds}

    @callback
    def _schedule_periodic_save(self, now: float) -> None:
        if now < self._next_save_due:
            return
        self._next_save_due = now + _SAVE_INTERVAL_SECONDS
        self._store.async_delay_save(self._data_to_save, 0)

    @callback
    def update_running(self, running: bool) -> None:
        """Update the confirmed running state and accrue elapsed time."""
        now = monotonic()
        self._accrue_to(now)
        self._running = bool(running)
        self._schedule_periodic_save(now)

    @callback
    def pause(self) -> None:
        """Stop accumulating while pump state is no longer confirmed."""
        self.update_running(False)

    @property
    def hours(self) -> float:
        """Return the current operating-hours value."""
        total_seconds = self._total_seconds
        if self._running and self._last_tick is not None:
            total_seconds += max(0.0, monotonic() - self._last_tick)
        return total_seconds / 3600.0

    async def async_set_hours(self, hours: float) -> None:
        """Set the counter to an explicit value while preserving run state."""
        now = monotonic()
        self._total_seconds = max(0.0, float(hours) * 3600.0)
        self._last_tick = now
        self._next_save_due = now + _SAVE_INTERVAL_SECONDS
        await self._store.async_save(self._data_to_save())

    async def async_shutdown(self) -> None:
        """Persist the latest value before the integration unloads."""
        now = monotonic()
        self._accrue_to(now)
        self._running = False
        await self._store.async_save(self._data_to_save())


async def async_get_runtime_hours(
    hass: HomeAssistant,
    entry_id: str,
    initial_hours: float = 0.0,
) -> float:
    """Return current runtime from memory when loaded, otherwise from storage."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    tracker = getattr(coordinator, "runtime_tracker", None)
    if tracker is not None:
        return tracker.hours

    store = Store(hass, _STORAGE_VERSION, _storage_key(entry_id))
    stored = await store.async_load()
    if isinstance(stored, dict):
        try:
            return max(0.0, float(stored["total_seconds"])) / 3600.0
        except (KeyError, TypeError, ValueError):
            pass
    return max(0.0, float(initial_hours))


async def async_set_runtime_hours(
    hass: HomeAssistant,
    entry_id: str,
    hours: float,
) -> None:
    """Set runtime in memory/storage without exposing a reset entity."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    tracker = getattr(coordinator, "runtime_tracker", None)
    if tracker is not None:
        await tracker.async_set_hours(hours)
        coordinator.async_update_listeners()
        return

    store = Store(hass, _STORAGE_VERSION, _storage_key(entry_id))
    await store.async_save({"total_seconds": max(0.0, float(hours) * 3600.0)})
