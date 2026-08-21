"""Local TCP protocol used by the Aquagem RS485 gateway."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .const import (
    DEVICE_ADDRESS,
    MAX_SPEED,
    MIN_SPEED,
    OFF_COMMAND,
    READ_FUNCTION,
    READ_STATUS_BODY,
    READ_STATUS_REPLY_LENGTH,
    WRITE_SPEED_PREFIX,
)


class AquagemError(Exception):
    """Base protocol error."""


class AquagemConnectionError(AquagemError):
    """The gateway could not be reached."""


class AquagemProtocolError(AquagemError):
    """The gateway returned an invalid frame."""


@dataclass(frozen=True, slots=True)
class AquagemStatus:
    """Decoded iSaver operating data returned by the C3 read."""

    fault_code: int
    pump_on: bool
    speed: int


def crc16_modbus(data: bytes) -> bytes:
    """Return Modbus CRC16 in the observed RTU wire order (low byte first)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def frame(body: bytes) -> bytes:
    """Append the protocol CRC."""
    return body + crc16_modbus(body)


def decode_status(reply: bytes) -> AquagemStatus:
    """Decode and validate the fixed 9-byte C3 status response."""
    if len(reply) != READ_STATUS_REPLY_LENGTH:
        raise AquagemProtocolError(
            f"Longueur de trame invalide ({len(reply)} octets): {reply.hex(' ')}"
        )

    if reply[0] != DEVICE_ADDRESS or reply[1] != READ_FUNCTION:
        raise AquagemProtocolError(f"En-tête de trame invalide: {reply.hex(' ')}")

    expected_crc = crc16_modbus(reply[:-2])
    if reply[-2:] != expected_crc:
        raise AquagemProtocolError(
            "CRC invalide: "
            f"reçu {reply[-2:].hex(' ')}, attendu {expected_crc.hex(' ')}"
        )

    fault_code = int.from_bytes(reply[2:4], "big")
    pump_on = bool(reply[4] & 0x01)
    speed = int.from_bytes(reply[5:7], "big")

    if not 0 <= speed <= MAX_SPEED:
        raise AquagemProtocolError(f"Vitesse invalide: {speed} rpm")

    return AquagemStatus(
        fault_code=fault_code,
        pump_on=pump_on,
        speed=speed,
    )


class AquagemClient:
    """Small stateless client; one TCP exchange at a time."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def test_connection(self) -> None:
        """Check that the TCP gateway accepts a connection.

        A silent RTU-buffered gateway must not block creation of the Home
        Assistant entry. Actual protocol replies are checked by the coordinator.
        """
        async with self._lock:
            writer = None
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                detail = str(err) or f"Délai de réponse dépassé ({self.timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def _exchange(self, request: bytes, reply_length: int) -> bytes:
        async with self._lock:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                writer.write(request)
                await writer.drain()
                # TCP is a byte stream: the RTU response can arrive fragmented.
                reply = await asyncio.wait_for(
                    reader.readexactly(reply_length), self.timeout
                )
            except asyncio.IncompleteReadError as err:
                partial = err.partial
                raise AquagemProtocolError(
                    f"Trame trop courte ({len(partial)} octets): {partial.hex(' ')}"
                ) from err
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                detail = str(err) or f"Délai de réponse dépassé ({self.timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

        return reply

    async def _send(self, request: bytes) -> None:
        """Send a frame without requiring an acknowledgement.

        Some RTU-buffered gateways do not return write acknowledgements even
        though the command is accepted by the iSaver.
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
                detail = str(err) or f"Délai de connexion dépassé ({self.timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def read_status(self) -> AquagemStatus:
        """Read faults, pump state and actual speed in one C3 request."""
        reply = await self._exchange(
            frame(READ_STATUS_BODY),
            READ_STATUS_REPLY_LENGTH,
        )
        return decode_status(reply)

    async def write_speed(self, speed: int) -> None:
        """Write an RPM override; value 1 is the validated persistent OFF command."""
        if speed != OFF_COMMAND and not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(
                f"La vitesse doit être {OFF_COMMAND} (arrêt) ou comprise "
                f"entre {MIN_SPEED} et {MAX_SPEED}"
            )
        body = WRITE_SPEED_PREFIX + speed.to_bytes(2, "big")
        await self._send(frame(body))
