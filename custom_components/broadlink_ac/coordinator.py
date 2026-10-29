"""Coordinator and serialized command handling."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import time
from dataclasses import replace
from datetime import timedelta
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AMBIENT_INTERVAL,
    CONF_INVERT_DISPLAY,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .protocol.device import (
    AcDevice,
    AuthenticationError,
    DeviceError,
    ProtocolError,
    TransportError,
    UnsupportedDeviceError,
)
from .protocol.state import AcState
from .store import AcStore

_LOGGER = logging.getLogger(__name__)


class BroadlinkAcCoordinator(DataUpdateCoordinator[AcState]):
    """Own the confirmed state and one device command queue."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device: AcDevice, store: AcStore) -> None:
        self.entry = entry
        self.device = device
        self.store = store
        self.name = entry.options.get(CONF_NAME) or entry.data.get(CONF_NAME) or device.mac
        self.invert_display = bool(entry.options.get(CONF_INVERT_DISPLAY, False))
        poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        self.poll_interval = min(MAX_POLL_INTERVAL, max(MIN_POLL_INTERVAL, poll_interval))
        self._base_poll_interval = self.poll_interval
        self._poll_backoff = 0
        self.last_packet: float | None = None
        self.error_count = 0
        self.consecutive_failures = 0
        self._last_ambient = 0.0
        self._io_lock = asyncio.Lock()
        self._pending_changes: dict[str, Any] = {}
        self._pending_waiters: list[asyncio.Future[None]] = []
        self._debounce_task: asyncio.Task[None] | None = None
        self._shutdown = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {device.mac}",
            update_interval=timedelta(seconds=self.poll_interval),
        )

    async def async_load_session(self) -> None:
        """Restore persisted session fields when valid."""
        data = await self.store.async_load()
        try:
            self.device.load_session(
                bytes.fromhex(str(data["device_id"])),
                bytes.fromhex(str(data["device_key"])),
                int(data.get("sequence", 0)),
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.debug("No usable persisted session for %s", self.device.mac)

    async def _persist_session(self) -> None:
        session = self.device.session_data()
        if session is not None:
            await self.store.async_save(session)

    async def _with_retries(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        """Run one operation with bounded retry and one re-auth attempt."""
        started = time.monotonic()
        reauth_used = False
        last_error: Exception | None = None
        for attempt in range(3):
            if time.monotonic() - started >= 10:
                break
            try:
                result = await operation()
                await self._persist_session()
                return result
            except AuthenticationError as err:
                last_error = err
                if reauth_used:
                    break
                self.device.invalidate_session()
                reauth_used = True
            except UnsupportedDeviceError as err:
                last_error = err
                break
            except (TransportError, ProtocolError) as err:
                last_error = err
            if attempt < 2:
                await asyncio.sleep(0.5)
        await self._persist_session()
        raise last_error or DeviceError("operation timed out")

    def _record_success(self) -> None:
        self.last_packet = time.time()
        self.consecutive_failures = 0
        self._poll_backoff = 0
        self.update_interval = timedelta(seconds=self._base_poll_interval)

    def _record_failure(self, error: Exception) -> None:
        self.error_count += 1
        self.consecutive_failures += 1
        self._poll_backoff = min(30, 2 ** min(self.consecutive_failures - 1, 4))
        self.update_interval = timedelta(seconds=self._poll_backoff)
        _LOGGER.debug("Broadlink AC operation failed for %s: %s", self.device.mac, error)

    async def _async_update_data(self) -> AcState:
        """Poll state and ambient data."""
        async with self._io_lock:
            try:
                state = await self._with_retries(self.device.read_state)
                if time.monotonic() - self._last_ambient >= AMBIENT_INTERVAL:
                    state = state.with_ambient(await self._with_retries(self.device.read_ambient))
                    self._last_ambient = time.monotonic()
                self._record_success()
                return state
            except DeviceError as err:
                self._record_failure(err)
                if self.data is not None and self.consecutive_failures < 3:
                    return self.data
                raise UpdateFailed(str(err)) from err

    async def async_request_state_change(self, **changes: Any) -> None:
        """Debounce and apply changes to the full device state."""
        if self.data is None:
            state = await self._async_update_data()
            self.async_set_updated_data(state)
        self._pending_changes.update(changes)
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        self._pending_waiters.append(waiter)
        if self._debounce_task is None:
            self._debounce_task = asyncio.create_task(self._flush_pending_changes())
        await waiter

    async def _flush_pending_changes(self) -> None:
        await asyncio.sleep(0.3)
        changes = self._pending_changes
        waiters = self._pending_waiters
        self._pending_changes = {}
        self._pending_waiters = []
        self._debounce_task = None
        previous = self.data
        assert previous is not None
        try:
            proposed = replace(previous, **changes)
        except TypeError as err:
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_exception(err)
            return
        self.async_set_updated_data(proposed)
        try:
            async with self._io_lock:
                await self._with_retries(lambda: self.device.apply_state(proposed))
                await asyncio.sleep(0.5)
                confirmed = await self._with_retries(self.device.read_state)
                confirmed = confirmed.with_ambient(proposed.ambient_temperature)
                self._record_success()
                self.async_set_updated_data(confirmed)
        except (DeviceError, ValueError) as err:
            self._record_failure(err)
            self.async_set_updated_data(previous)
            if self.consecutive_failures >= 3:
                self.async_set_update_error(UpdateFailed(str(err)))
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_exception(err)
            return
        for waiter in waiters:
            if not waiter.done():
                waiter.set_result(None)

    async def async_shutdown(self) -> None:
        """Cancel pending work and close the device socket."""
        self._shutdown = True
        if self._debounce_task is not None:
            task = self._debounce_task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self.device.close()
