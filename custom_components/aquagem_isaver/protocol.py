"""Local TCP protocols used by Aquagem RS485 gateways."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .const import (
    DEVICE_ADDRESS,
    DM15_CAPACITY_STEP,
    DM15_COMMAND_REGISTER,
    DM15_MAX_CAPACITY,
    DM15_MIN_CAPACITY,
    DM15_OFF_COMMAND,
    DM15_READ_FUNCTION,
    DM15_STATUS_COUNT,
    DM15_STATUS_REPLY_LENGTH,
    DM15_STATUS_START,
    DM15_WRITE_FUNCTION,
    MAX_SPEED,
    MIN_SPEED,
    OFF_COMMAND,
    PROTOCOL_DM15,
    PROTOCOL_ISAVER,
    READ_FUNCTION,
    READ_STATUS_BODY,
    READ_STATUS_REPLY_LENGTH,
    SPEED_STEP,
    WRITE_SPEED_PREFIX,
)


class AquagemError(Exception):
    """Base protocol error."""


class AquagemConnectionError(AquagemError):
    """The gateway could not be reached or did not answer in time."""


class AquagemProtocolError(AquagemError):
    """The gateway returned an invalid frame."""


@dataclass(frozen=True, slots=True)
class AquagemStatus:
    """Decoded operating data shared by the supported Aquagem profiles."""

    fault_code: int
    pump_on: bool
    speed: int
    protocol: str
    raw_2004: int | None = None


def crc16_modbus(data: bytes) -> bytes:
    """Return Modbus CRC16 in RTU wire order (low byte first)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def frame(body: bytes) -> bytes:
    """Append a Modbus CRC to a request body."""
    return body + crc16_modbus(body)


def _validate_crc(reply: bytes) -> None:
    if len(reply) < 4:
        raise AquagemProtocolError(f"Frame too short: {reply.hex(' ')}")
    expected_crc = crc16_modbus(reply[:-2])
    if reply[-2:] != expected_crc:
        raise AquagemProtocolError(
            f"Invalid CRC: received {reply[-2:].hex(' ')}, "
            f"expected {expected_crc.hex(' ')}"
        )


def decode_isaver_status(reply: bytes) -> AquagemStatus:
    """Decode the fixed 9-byte proprietary C3 iSaver status response."""
    if len(reply) != READ_STATUS_REPLY_LENGTH:
        raise AquagemProtocolError(
            f"Invalid iSaver frame length ({len(reply)} bytes): {reply.hex(' ')}"
        )
    if reply[0] != DEVICE_ADDRESS or reply[1] != READ_FUNCTION:
        raise AquagemProtocolError(f"Invalid iSaver header: {reply.hex(' ')}")
    _validate_crc(reply)

    fault_code = int.from_bytes(reply[2:4], "big")
    pump_on = bool(reply[4] & 0x01)
    speed = int.from_bytes(reply[5:7], "big")
    if not 0 <= speed <= MAX_SPEED:
        raise AquagemProtocolError(f"Invalid iSaver speed: {speed} rpm")

    return AquagemStatus(
        fault_code=fault_code,
        pump_on=pump_on,
        speed=speed,
        protocol=PROTOCOL_ISAVER,
    )


def decode_dm15_status(reply: bytes) -> AquagemStatus:
    """Decode DM15 holding registers 2001..2004."""
    if len(reply) != DM15_STATUS_REPLY_LENGTH:
        raise AquagemProtocolError(
            f"Invalid DM15 frame length ({len(reply)} bytes): {reply.hex(' ')}"
        )
    if reply[0] != DEVICE_ADDRESS or reply[1] != DM15_READ_FUNCTION:
        raise AquagemProtocolError(f"Invalid DM15 header: {reply.hex(' ')}")
    _validate_crc(reply)

    byte_count = reply[2]
    payload = reply[3:-2]
    if byte_count != 8 or len(payload) != 8:
        raise AquagemProtocolError(
            f"Invalid DM15 byte count {byte_count}: {reply.hex(' ')}"
        )

    registers = [
        int.from_bytes(payload[index : index + 2], "big")
        for index in range(0, len(payload), 2)
    ]
    fault_code, state, capacity, raw_2004 = registers
    if not 0 <= capacity <= DM15_MAX_CAPACITY:
        raise AquagemProtocolError(f"Invalid DM15 running capacity: {capacity}%")

    return AquagemStatus(
        fault_code=fault_code,
        pump_on=bool(state & 0x0001),
        speed=capacity,
        protocol=PROTOCOL_DM15,
        raw_2004=raw_2004,
    )


class AquagemClient:
    """Small stateless TCP client with Aquagem protocol auto-detection."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        protocol: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.protocol = protocol if protocol in (PROTOCOL_ISAVER, PROTOCOL_DM15) else None
        self._lock = asyncio.Lock()

    @property
    def is_dm15(self) -> bool:
        return self.protocol == PROTOCOL_DM15

    @property
    def minimum_speed(self) -> int:
        return DM15_MIN_CAPACITY if self.is_dm15 else MIN_SPEED

    @property
    def maximum_speed(self) -> int:
        return DM15_MAX_CAPACITY if self.is_dm15 else MAX_SPEED

    @property
    def speed_step(self) -> int:
        return DM15_CAPACITY_STEP if self.is_dm15 else SPEED_STEP

    @property
    def off_command(self) -> int:
        return DM15_OFF_COMMAND if self.is_dm15 else OFF_COMMAND

    @property
    def model(self) -> str:
        if self.protocol == PROTOCOL_DM15:
            return "DM15 / INVERsilence"
        if self.protocol == PROTOCOL_ISAVER:
            return "iSaver Power 1100"
        return "Aquagem pump inverter"

    async def test_connection(self) -> None:
        """Check that the TCP gateway accepts a connection."""
        async with self._lock:
            writer = None
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                detail = str(err) or f"Connection timed out ({self.timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def _exchange(
        self,
        request: bytes,
        reply_length: int,
        *,
        timeout: float | None = None,
    ) -> bytes:
        exchange_timeout = self.timeout if timeout is None else timeout
        async with self._lock:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), exchange_timeout
                )
                writer.write(request)
                await writer.drain()
                reply = await asyncio.wait_for(
                    reader.readexactly(reply_length), exchange_timeout
                )
            except asyncio.IncompleteReadError as err:
                partial = err.partial
                raise AquagemProtocolError(
                    f"Short frame ({len(partial)} bytes): {partial.hex(' ')}"
                ) from err
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                detail = str(err) or f"Response timed out ({exchange_timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()
        return reply

    async def _send(self, request: bytes) -> None:
        """Send an iSaver write frame without requiring an acknowledgement."""
        async with self._lock:
            writer = None
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                writer.write(request)
                await writer.drain()
            except (OSError, TimeoutError, asyncio.TimeoutError) as err:
                detail = str(err) or f"Connection timed out ({self.timeout:g} s)"
                raise AquagemConnectionError(detail) from err
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def _read_isaver_status(self, timeout: float | None = None) -> AquagemStatus:
        reply = await self._exchange(
            frame(READ_STATUS_BODY), READ_STATUS_REPLY_LENGTH, timeout=timeout
        )
        return decode_isaver_status(reply)

    async def _read_dm15_status(self, timeout: float | None = None) -> AquagemStatus:
        body = bytes(
            (
                DEVICE_ADDRESS,
                DM15_READ_FUNCTION,
                (DM15_STATUS_START >> 8) & 0xFF,
                DM15_STATUS_START & 0xFF,
                0x00,
                DM15_STATUS_COUNT,
            )
        )
        reply = await self._exchange(
            frame(body), DM15_STATUS_REPLY_LENGTH, timeout=timeout
        )
        return decode_dm15_status(reply)

    async def detect_protocol(self) -> AquagemStatus:
        """Probe both validated profiles without sending any write command."""
        detection_timeout = min(self.timeout, 1.5)
        errors: list[str] = []

        for protocol, reader in (
            (PROTOCOL_ISAVER, self._read_isaver_status),
            (PROTOCOL_DM15, self._read_dm15_status),
        ):
            try:
                status = await reader(timeout=detection_timeout)
            except AquagemError as err:
                errors.append(f"{protocol}: {err}")
                continue
            self.protocol = protocol
            return status

        raise AquagemProtocolError(
            "No supported Aquagem protocol response received (" + "; ".join(errors) + ")"
        )

    async def read_status(self) -> AquagemStatus:
        """Read the status block using the configured or detected profile."""
        if self.protocol == PROTOCOL_ISAVER:
            return await self._read_isaver_status()
        if self.protocol == PROTOCOL_DM15:
            return await self._read_dm15_status()
        return await self.detect_protocol()

    async def _write_dm15_capacity(self, capacity: int) -> None:
        if capacity != DM15_OFF_COMMAND and not DM15_MIN_CAPACITY <= capacity <= DM15_MAX_CAPACITY:
            raise ValueError(
                f"DM15 capacity must be 0 (OFF) or {DM15_MIN_CAPACITY}..{DM15_MAX_CAPACITY}%"
            )

        body = bytes(
            (
                DEVICE_ADDRESS,
                DM15_WRITE_FUNCTION,
                (DM15_COMMAND_REGISTER >> 8) & 0xFF,
                DM15_COMMAND_REGISTER & 0xFF,
                0x00,
                0x01,
                0x02,
                (capacity >> 8) & 0xFF,
                capacity & 0xFF,
            )
        )
        reply = await self._exchange(frame(body), 8)
        _validate_crc(reply)
        expected = bytes(
            (
                DEVICE_ADDRESS,
                DM15_WRITE_FUNCTION,
                (DM15_COMMAND_REGISTER >> 8) & 0xFF,
                DM15_COMMAND_REGISTER & 0xFF,
                0x00,
                0x01,
            )
        )
        if reply[:6] != expected:
            raise AquagemProtocolError(f"Unexpected DM15 write ACK: {reply.hex(' ')}")

    async def write_speed(self, speed: int) -> None:
        """Write a speed/capacity command using the detected protocol."""
        if self.protocol is None:
            await self.detect_protocol()

        if self.protocol == PROTOCOL_DM15:
            await self._write_dm15_capacity(speed)
            return

        if speed != OFF_COMMAND and not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(
                f"iSaver speed must be {OFF_COMMAND} (OFF) or {MIN_SPEED}..{MAX_SPEED} rpm"
            )
        body = WRITE_SPEED_PREFIX + speed.to_bytes(2, "big")
        await self._send(frame(body))
