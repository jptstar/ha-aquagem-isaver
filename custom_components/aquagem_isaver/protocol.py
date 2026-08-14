"""Local TCP protocol used by the Aquagem RS485 gateway."""

from __future__ import annotations

import asyncio

from .const import READ_SPEED_BODY, WRITE_SPEED_PREFIX


class AquagemError(Exception):
    """Base protocol error."""


class AquagemConnectionError(AquagemError):
    """The gateway could not be reached."""


class AquagemProtocolError(AquagemError):
    """The gateway returned an invalid frame."""


def crc16_modbus(data: bytes) -> bytes:
    """Return Modbus CRC16, least-significant byte first."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def frame(body: bytes) -> bytes:
    """Append the protocol CRC."""
    return body + crc16_modbus(body)


class AquagemClient:
    """Small stateless client; one TCP exchange at a time."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def _exchange(self, request: bytes, minimum_reply: int = 7) -> bytes:
        async with self._lock:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                writer.write(request)
                await writer.drain()
                reply = await asyncio.wait_for(reader.read(256), self.timeout)
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                raise AquagemConnectionError(str(err)) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

        if len(reply) < minimum_reply:
            raise AquagemProtocolError(f"Trame trop courte ({len(reply)} octets)")
        return reply

    async def _send(self, request: bytes) -> None:
        """Send a frame without requiring an acknowledgement.

        Node-RED uses a plain ``tcp out`` node for writes. Some RTU-buffered
        gateways therefore acknowledge nothing even though the write succeeds.
        """
        async with self._lock:
            writer = None
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                writer.write(request)
                await writer.drain()
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                raise AquagemConnectionError(str(err)) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def read_speed(self) -> int:
        """Read the actual/commanded speed from response bytes 5 and 6."""
        reply = await self._exchange(frame(READ_SPEED_BODY))
        speed = int.from_bytes(reply[5:7], "big")
        if not 0 <= speed <= 65535:
            raise AquagemProtocolError("Vitesse invalide")
        return speed

    async def write_speed(self, speed: int) -> None:
        """Write a speed. Zero is the explicit stop command."""
        if speed != 0 and not 1200 <= speed <= 2900:
            raise ValueError("La vitesse doit être 0 ou comprise entre 1200 et 2900")
        body = WRITE_SPEED_PREFIX + speed.to_bytes(2, "big")
        await self._send(frame(body))
