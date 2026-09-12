"""Transport backends for Aquagem pump protocols."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from time import monotonic
from typing import AsyncIterator, Protocol


class AquagemTransport(Protocol):
    """Byte transport used by the protocol layer."""

    @property
    def endpoint(self) -> str:
        """Human-readable endpoint."""

    async def test_connection(self, timeout: float) -> None:
        """Verify that the transport can be opened."""

    async def exchange(
        self, request: bytes, reply_length: int, timeout: float
    ) -> bytes:
        """Send one request and read one response."""

    async def send(self, request: bytes, timeout: float) -> None:
        """Send one request without waiting for a response."""

    async def close(self) -> None:
        """Release transport resources."""


class Rs485BusManager:
    """Explicit FIFO transaction queue shared by one physical RS485 bus."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.last_exchange_end = 0.0
        self._waiters: deque[asyncio.Future[None]] = deque()

    def _wake_next(self) -> None:
        """Wake the oldest non-cancelled waiter."""
        while self._waiters and self._waiters[0].cancelled():
            self._waiters.popleft()
        if self._waiters and not self._waiters[0].done():
            self._waiters[0].set_result(None)

    async def acquire(self) -> None:
        """Queue for the bus and acquire it strictly in arrival order."""
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        if len(self._waiters) == 1:
            waiter.set_result(None)

        try:
            await waiter
        except BaseException:
            # A cancelled waiter must never block the queue. If it had already
            # reached the head, pass ownership to the next queued transaction.
            was_head = bool(self._waiters and self._waiters[0] is waiter)
            try:
                self._waiters.remove(waiter)
            except ValueError:
                pass
            if was_head:
                self._wake_next()
            raise

    def release(self) -> None:
        """Release the current transaction and wake the next FIFO waiter."""
        if not self._waiters:
            raise RuntimeError(f"RS485 bus {self.key} released without an owner")
        self._waiters.popleft()
        self._wake_next()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Rs485BusManager]:
        """Hold exclusive bus ownership for one complete transaction."""
        await self.acquire()
        try:
            yield self
        finally:
            self.release()


_SHARED_BUSES: dict[str, Rs485BusManager] = {}


def _shared_bus(key: str) -> Rs485BusManager:
    """Return the process-wide FIFO manager for one bus endpoint."""
    manager = _SHARED_BUSES.get(key)
    if manager is None:
        manager = Rs485BusManager(key)
        _SHARED_BUSES[key] = manager
    return manager


async def _read_expected_reply(
    reader: asyncio.StreamReader,
    request: bytes,
    reply_length: int,
) -> bytes:
    """Read a fixed response while recognizing standard Modbus exceptions."""
    # Standard Modbus exception responses are always 5 bytes including CRC.
    # Read their function byte first so an unsupported register does not turn
    # into a full timeout while waiting for the normal response length.
    if len(request) >= 2 and request[1] in (0x03, 0x10):
        header = await reader.readexactly(2)
        if header[1] == (request[1] | 0x80):
            return header + await reader.readexactly(3)
        return header + await reader.readexactly(reply_length - 2)

    return await reader.readexactly(reply_length)


def _is_serialx_exception(err: BaseException) -> bool:
    """Return whether an error is serialx-specific without importing it for TCP."""
    try:
        from serialx import SerialException
    except ImportError:
        return False
    return isinstance(err, SerialException)


class TcpTransport:
    """Transparent RS485-over-TCP transport with a shared FIFO bus."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._bus = _shared_bus(f"tcp:{host}:{port}")

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    async def test_connection(self, timeout: float) -> None:
        async with self._bus.transaction():
            writer = None
            try:
                async with asyncio.timeout(timeout):
                    _, writer = await asyncio.open_connection(self.host, self.port)
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def exchange(
        self, request: bytes, reply_length: int, timeout: float
    ) -> bytes:
        # Several Modbus units can sit behind the same transparent gateway.
        # Serialize the complete request/reply pair in explicit FIFO order so
        # config entries cannot interleave frames on the downstream RS485 bus.
        async with self._bus.transaction():
            writer = None
            try:
                async with asyncio.timeout(timeout):
                    reader, writer = await asyncio.open_connection(self.host, self.port)
                    writer.write(request)
                    await writer.drain()
                    return await _read_expected_reply(reader, request, reply_length)
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def send(self, request: bytes, timeout: float) -> None:
        async with self._bus.transaction():
            writer = None
            try:
                async with asyncio.timeout(timeout):
                    _, writer = await asyncio.open_connection(self.host, self.port)
                    writer.write(request)
                    await writer.drain()
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def close(self) -> None:
        """TCP connections are intentionally short-lived."""


class SerialTransport:
    """Direct serial transport sharing one physical RS485 bus safely."""

    def __init__(
        self,
        device: str,
        baudrate: int,
        *,
        inter_frame_delay: float = 0.0,
    ) -> None:
        self.device = device
        self.baudrate = baudrate
        self.inter_frame_delay = max(0.0, inter_frame_delay)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._bus = _shared_bus(f"serial:{device}:{baudrate}:8N1")

    @property
    def endpoint(self) -> str:
        return self.device

    async def _open(self, timeout: float) -> None:
        if self._reader is not None and self._writer is not None:
            return

        # Serial support is optional for existing TCP installations. Import
        # serialx only when a serial transport is actually used, so a serial
        # dependency problem can never prevent a WaveShare/TCP entry from
        # loading or its config flow from opening.
        try:
            from serialx import Parity, StopBits, open_serial_connection
        except ImportError as err:
            raise OSError("Home Assistant serial support is unavailable") from err

        try:
            async with asyncio.timeout(timeout):
                reader, writer = await open_serial_connection(
                    url=self.device,
                    baudrate=self.baudrate,
                    bytesize=8,
                    parity=Parity.NONE,
                    stopbits=StopBits.ONE,
                )
        except Exception as err:
            if _is_serialx_exception(err):
                raise OSError(str(err) or "Serial connection failed") from err
            raise

        self._reader = reader
        self._writer = writer

    async def _drop_connection(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception as err:
                if not isinstance(err, OSError) and not _is_serialx_exception(err):
                    raise

    async def _respect_inter_frame_delay(self) -> None:
        if not self._bus.last_exchange_end or not self.inter_frame_delay:
            return
        remaining = (
            self.inter_frame_delay - (monotonic() - self._bus.last_exchange_end)
        )
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def test_connection(self, timeout: float) -> None:
        async with self._bus.transaction():
            try:
                await self._open(timeout)
            finally:
                await self._drop_connection()

    async def exchange(
        self, request: bytes, reply_length: int, timeout: float
    ) -> bytes:
        # Direct serial entries sharing one adapter must never keep competing
        # file descriptors open. Hold FIFO ownership for the complete RTU frame,
        # then close so the next addressed device can use the same port.
        async with self._bus.transaction():
            await self._respect_inter_frame_delay()
            try:
                await self._open(timeout)
                assert self._reader is not None
                assert self._writer is not None

                async with asyncio.timeout(timeout):
                    self._writer.write(request)
                    await self._writer.drain()
                    reply = await _read_expected_reply(
                        self._reader, request, reply_length
                    )
            except Exception as err:
                await self._drop_connection()
                if _is_serialx_exception(err):
                    raise OSError(str(err) or "Serial transaction failed") from err
                raise
            else:
                await self._drop_connection()
                self._bus.last_exchange_end = monotonic()
                return reply

    async def send(self, request: bytes, timeout: float) -> None:
        """Send a write-only frame and release the shared serial bus."""
        async with self._bus.transaction():
            await self._respect_inter_frame_delay()
            try:
                await self._open(timeout)
                assert self._writer is not None
                async with asyncio.timeout(timeout):
                    self._writer.write(request)
                    await self._writer.drain()

                    # At low baud rates drain() may only mean that bytes reached
                    # the OS/driver buffer. Keep the port open for at least one
                    # complete 8N1 frame time before closing it. Closing also
                    # discards any optional D0 acknowledgement before the next
                    # addressed transaction on the shared bus.
                    wire_time = (len(request) * 10.0) / max(1, self.baudrate)
                    await asyncio.sleep(wire_time + 0.02)
            except Exception as err:
                await self._drop_connection()
                if _is_serialx_exception(err):
                    raise OSError(str(err) or "Serial write failed") from err
                raise
            else:
                await self._drop_connection()
                self._bus.last_exchange_end = monotonic()

    async def close(self) -> None:
        async with self._bus.transaction():
            await self._drop_connection()
