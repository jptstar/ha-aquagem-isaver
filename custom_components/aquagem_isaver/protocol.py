"""Local TCP protocols used by Aquagem RS485 gateways."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace

from .const import (
    ISAVER_DEVICE_ADDRESS,
    MAX_SPEED,
    MIN_SPEED,
    OFF_COMMAND,
    PROTOCOL_ISAVER,
    PROTOCOL_PUMP_MODBUS,
    PUMP_MODBUS_CAPACITY_STEP,
    PUMP_MODBUS_COMMAND_REGISTER,
    PUMP_MODBUS_DEFAULT_UNIT,
    PUMP_MODBUS_EXTENDED_COUNT,
    PUMP_MODBUS_EXTENDED_REPLY_LENGTH,
    PUMP_MODBUS_EXTENDED_START,
    PUMP_MODBUS_MAX_CAPACITY,
    PUMP_MODBUS_MIN_CAPACITY,
    PUMP_MODBUS_OFF_COMMAND,
    PUMP_MODBUS_READ_FUNCTION,
    PUMP_MODBUS_STATUS_COUNT,
    PUMP_MODBUS_STATUS_REPLY_LENGTH,
    PUMP_MODBUS_STATUS_START,
    PUMP_MODBUS_UNIT_MAX,
    PUMP_MODBUS_UNIT_MIN,
    PUMP_MODBUS_WRITE_FUNCTION,
    READ_FUNCTION,
    READ_STATUS_BODY,
    READ_STATUS_REPLY_LENGTH,
    SPEED_STEP,
    SUPPORTED_PROTOCOLS,
    WRITE_SPEED_PREFIX,
)


class AquagemError(Exception):
    """Base protocol error."""


class AquagemConnectionError(AquagemError):
    """The gateway could not be reached or did not answer in time."""


class AquagemProtocolError(AquagemError):
    """The gateway returned an invalid frame or no known profile matched."""


@dataclass(frozen=True, slots=True)
class AquagemStatus:
    """Decoded operating data shared by the supported Aquagem profiles."""

    fault_code: int
    pump_on: bool
    speed: int
    protocol: str
    power_w: int | None = None
    energy_raw: int | None = None
    mode_code: int | None = None
    software_version: int | None = None


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
    if reply[0] != ISAVER_DEVICE_ADDRESS or reply[1] != READ_FUNCTION:
        raise AquagemProtocolError(f"Invalid iSaver header: {reply.hex(' ')}")
    _validate_crc(reply)

    fault_code = int.from_bytes(reply[2:4], "big")
    state = reply[4]
    pump_on = bool(state & 0x01)
    speed = int.from_bytes(reply[5:7], "big")

    if state & ~0x01:
        raise AquagemProtocolError(f"Unexpected iSaver state byte: 0x{state:02X}")
    if not 0 <= speed <= MAX_SPEED:
        raise AquagemProtocolError(f"Invalid iSaver speed: {speed} rpm")

    return AquagemStatus(
        fault_code=fault_code,
        pump_on=pump_on,
        speed=speed,
        protocol=PROTOCOL_ISAVER,
    )


def decode_pump_modbus_status(reply: bytes, unit: int) -> AquagemStatus:
    """Decode and validate Aquagem pump holding registers 2001..2004."""
    if len(reply) != PUMP_MODBUS_STATUS_REPLY_LENGTH:
        raise AquagemProtocolError(
            f"Invalid Modbus pump frame length ({len(reply)} bytes): {reply.hex(' ')}"
        )
    if reply[0] != unit or reply[1] != PUMP_MODBUS_READ_FUNCTION:
        raise AquagemProtocolError(f"Invalid Modbus pump header: {reply.hex(' ')}")
    _validate_crc(reply)

    byte_count = reply[2]
    payload = reply[3:-2]
    if byte_count != 8 or len(payload) != 8:
        raise AquagemProtocolError(
            f"Invalid Modbus pump byte count {byte_count}: {reply.hex(' ')}"
        )

    fault_code, state, capacity, power_w = (
        int.from_bytes(payload[index : index + 2], "big")
        for index in range(0, len(payload), 2)
    )

    # Signature checks are deliberately stricter than a plain CRC check. They
    # prevent another Modbus device from being mistaken for an Aquagem pump.
    if state not in (0, 1):
        raise AquagemProtocolError(f"Unexpected Modbus pump state: 0x{state:04X}")
    if state == 0 and capacity != 0:
        raise AquagemProtocolError(
            f"Implausible stopped Modbus pump capacity: {capacity}%"
        )
    if state == 1 and not PUMP_MODBUS_MIN_CAPACITY <= capacity <= PUMP_MODBUS_MAX_CAPACITY:
        raise AquagemProtocolError(
            f"Implausible running Modbus pump capacity: {capacity}%"
        )

    return AquagemStatus(
        fault_code=fault_code,
        pump_on=bool(state),
        speed=capacity,
        protocol=PROTOCOL_PUMP_MODBUS,
        power_w=power_w,
    )


def decode_pump_modbus_extended(reply: bytes, unit: int) -> tuple[int, int, int]:
    """Decode Aquagem Modbus V1.5 registers 2007..2009."""
    if len(reply) != PUMP_MODBUS_EXTENDED_REPLY_LENGTH:
        raise AquagemProtocolError(
            f"Invalid extended Modbus frame length ({len(reply)} bytes): {reply.hex(' ')}"
        )
    if reply[0] != unit or reply[1] != PUMP_MODBUS_READ_FUNCTION:
        raise AquagemProtocolError(f"Invalid extended Modbus header: {reply.hex(' ')}")
    _validate_crc(reply)

    byte_count = reply[2]
    payload = reply[3:-2]
    if byte_count != 6 or len(payload) != 6:
        raise AquagemProtocolError(
            f"Invalid extended Modbus byte count {byte_count}: {reply.hex(' ')}"
        )

    energy_raw, mode_code, software_version = (
        int.from_bytes(payload[index : index + 2], "big")
        for index in range(0, len(payload), 2)
    )
    return energy_raw, mode_code, software_version


class AquagemClient:
    """Small stateless TCP client with read-only protocol auto-detection."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        protocol: str | None = None,
        modbus_unit: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.protocol = protocol if protocol in SUPPORTED_PROTOCOLS else None
        self.modbus_unit = modbus_unit or PUMP_MODBUS_DEFAULT_UNIT
        self._lock = asyncio.Lock()
        self._extended_modbus_supported: bool | None = None

    @property
    def is_pump_modbus(self) -> bool:
        return self.protocol == PROTOCOL_PUMP_MODBUS

    @property
    def minimum_speed(self) -> int:
        return PUMP_MODBUS_MIN_CAPACITY if self.is_pump_modbus else MIN_SPEED

    @property
    def maximum_speed(self) -> int:
        return PUMP_MODBUS_MAX_CAPACITY if self.is_pump_modbus else MAX_SPEED

    @property
    def speed_step(self) -> int:
        return PUMP_MODBUS_CAPACITY_STEP if self.is_pump_modbus else SPEED_STEP

    @property
    def off_command(self) -> int:
        return PUMP_MODBUS_OFF_COMMAND if self.is_pump_modbus else OFF_COMMAND

    @property
    def model(self) -> str:
        if self.protocol == PROTOCOL_PUMP_MODBUS:
            return "Aquagem Modbus Pump"
        if self.protocol == PROTOCOL_ISAVER:
            return "iSaver Power 1100"
        return "Aquagem Pump"

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

    async def _read_pump_modbus_extended(
        self,
        unit: int,
        timeout: float | None = None,
    ) -> tuple[int, int, int]:
        body = bytes(
            (
                unit,
                PUMP_MODBUS_READ_FUNCTION,
                (PUMP_MODBUS_EXTENDED_START >> 8) & 0xFF,
                PUMP_MODBUS_EXTENDED_START & 0xFF,
                0x00,
                PUMP_MODBUS_EXTENDED_COUNT,
            )
        )
        reply = await self._exchange(
            frame(body), PUMP_MODBUS_EXTENDED_REPLY_LENGTH, timeout=timeout
        )
        return decode_pump_modbus_extended(reply, unit)

    async def _read_pump_modbus_status(
        self,
        unit: int | None = None,
        timeout: float | None = None,
    ) -> AquagemStatus:
        unit = self.modbus_unit if unit is None else unit
        body = bytes(
            (
                unit,
                PUMP_MODBUS_READ_FUNCTION,
                (PUMP_MODBUS_STATUS_START >> 8) & 0xFF,
                PUMP_MODBUS_STATUS_START & 0xFF,
                0x00,
                PUMP_MODBUS_STATUS_COUNT,
            )
        )
        reply = await self._exchange(
            frame(body), PUMP_MODBUS_STATUS_REPLY_LENGTH, timeout=timeout
        )
        status = decode_pump_modbus_status(reply, unit)

        # V1.5 adds useful read-only registers 2007..2009. Probe them without
        # making them a requirement for the generic Aquagem Modbus profile so
        # older/alternate register maps continue to work.
        if self._extended_modbus_supported is not False:
            try:
                energy_raw, mode_code, software_version = await self._read_pump_modbus_extended(
                    unit, timeout=timeout
                )
            except AquagemError:
                self._extended_modbus_supported = False
            else:
                self._extended_modbus_supported = True
                status = replace(
                    status,
                    energy_raw=energy_raw,
                    mode_code=mode_code,
                    software_version=software_version,
                )

        return status

    async def detect_protocol(self) -> AquagemStatus:
        """Detect a supported profile using read-only signature checks."""
        errors: list[str] = []

        # Proprietary iSaver signature at its validated fixed address.
        try:
            status = await self._read_isaver_status(timeout=min(self.timeout, 0.8))
        except AquagemError as err:
            errors.append(f"{PROTOCOL_ISAVER}: {err}")
        else:
            self.protocol = PROTOCOL_ISAVER
            return status

        # Standard Modbus pump signature. 0xAA is the common/default address,
        # so try it first before scanning the documented configurable A0..BF range.
        units = [PUMP_MODBUS_DEFAULT_UNIT, *(
            unit
            for unit in range(PUMP_MODBUS_UNIT_MIN, PUMP_MODBUS_UNIT_MAX + 1)
            if unit != PUMP_MODBUS_DEFAULT_UNIT
        )]
        for index, unit in enumerate(units):
            timeout = min(self.timeout, 0.8 if index == 0 else 0.18)
            try:
                status = await self._read_pump_modbus_status(unit, timeout=timeout)
            except AquagemError as err:
                if index == 0:
                    errors.append(f"{PROTOCOL_PUMP_MODBUS}@0x{unit:02X}: {err}")
                continue
            self.protocol = PROTOCOL_PUMP_MODBUS
            self.modbus_unit = unit
            return status

        raise AquagemProtocolError(
            "No supported Aquagem protocol signature detected (" + "; ".join(errors) + ")"
        )

    async def validate_forced_protocol(self) -> AquagemStatus:
        """Validate a manually selected profile without writing to the pump."""
        if self.protocol == PROTOCOL_ISAVER:
            return await self._read_isaver_status()
        if self.protocol == PROTOCOL_PUMP_MODBUS:
            return await self._read_pump_modbus_status()
        raise AquagemProtocolError("No protocol selected")

    async def read_status(self) -> AquagemStatus:
        """Read status using the stored profile, or auto-detect once if needed."""
        if self.protocol == PROTOCOL_ISAVER:
            return await self._read_isaver_status()
        if self.protocol == PROTOCOL_PUMP_MODBUS:
            return await self._read_pump_modbus_status()
        return await self.detect_protocol()

    async def _write_pump_modbus_capacity(self, capacity: int) -> None:
        if capacity != PUMP_MODBUS_OFF_COMMAND and not (
            PUMP_MODBUS_MIN_CAPACITY <= capacity <= PUMP_MODBUS_MAX_CAPACITY
        ):
            raise ValueError(
                f"Modbus pump capacity must be 0 (OFF) or "
                f"{PUMP_MODBUS_MIN_CAPACITY}..{PUMP_MODBUS_MAX_CAPACITY}%"
            )

        unit = self.modbus_unit
        body = bytes(
            (
                unit,
                PUMP_MODBUS_WRITE_FUNCTION,
                (PUMP_MODBUS_COMMAND_REGISTER >> 8) & 0xFF,
                PUMP_MODBUS_COMMAND_REGISTER & 0xFF,
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
                unit,
                PUMP_MODBUS_WRITE_FUNCTION,
                (PUMP_MODBUS_COMMAND_REGISTER >> 8) & 0xFF,
                PUMP_MODBUS_COMMAND_REGISTER & 0xFF,
                0x00,
                0x01,
            )
        )
        if reply[:6] != expected:
            raise AquagemProtocolError(
                f"Unexpected Modbus pump write ACK: {reply.hex(' ')}"
            )

    async def write_speed(self, speed: int) -> None:
        """Write a speed/capacity command using the detected protocol."""
        if self.protocol is None:
            await self.detect_protocol()

        if self.protocol == PROTOCOL_PUMP_MODBUS:
            await self._write_pump_modbus_capacity(speed)
            return

        if speed != OFF_COMMAND and not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(
                f"iSaver speed must be {OFF_COMMAND} (OFF) or {MIN_SPEED}..{MAX_SPEED} rpm"
            )
        body = WRITE_SPEED_PREFIX + speed.to_bytes(2, "big")
        await self._send(frame(body))
