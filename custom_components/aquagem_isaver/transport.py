"""Transport backends for Aquagem pump protocols."""

from __future__ import annotations

import asyncio
from time import monotonic
from typing import Protocol

import serialx


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


class TcpTransport:
    """Transparent RS485-over-TCP transport."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    async def test_connection(self, timeout: float) -> None:
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
    """Persistent direct serial transport backed by serialx."""

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
        self._last_exchange_end = 0.0

    @property
    def endpoint(self) -> str:
        return self.device

    async def _open(self, timeout: float) -> None:
        if self._reader is not None and self._writer is not None:
            return

        async with asyncio.timeout(timeout):
            reader, writer = await serialx.open_serial_connection(
                url=self.device,
                baudrate=self.baudrate,
            )
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
            except OSError:
                pass

    async def _respect_inter_frame_delay(self) -> None:
        if not self._last_exchange_end or not self.inter_frame_delay:
            return
        remaining = (
            self.inter_frame_delay - (monotonic() - self._last_exchange_end)
        )
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def test_connection(self, timeout: float) -> None:
        try:
            await self._open(timeout)
        finally:
            await self._drop_connection()

    async def exchange(
        self, request: bytes, reply_length: int, timeout: float
    ) -> bytes:
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
        except (OSError, TimeoutError, asyncio.IncompleteReadError):
            # Drop the stream after any failed transaction. This clears partial
            # bytes and lets serialx reopen a clean connection on the next poll.
            await self._drop_connection()
            raise
        else:
            self._last_exchange_end = monotonic()
            return reply

    async def send(self, request: bytes, timeout: float) -> None:
        await self._respect_inter_frame_delay()
        try:
            await self._open(timeout)
            assert self._writer is not None
            async with asyncio.timeout(timeout):
                self._writer.write(request)
                await self._writer.drain()
        except (OSError, TimeoutError):
            await self._drop_connection()
            raise
        else:
            self._last_exchange_end = monotonic()

    async def close(self) -> None:
        await self._drop_connection()
