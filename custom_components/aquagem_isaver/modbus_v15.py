"""Experimental Aquagem Modbus V1.5 extended register reader."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .const import (
    PROTOCOL_PUMP_MODBUS,
    PUMP_MODBUS_COMMAND_REGISTER,
    PUMP_MODBUS_EXTENDED_STATUS_COUNT,
    PUMP_MODBUS_EXTENDED_STATUS_REPLY_LENGTH,
    PUMP_MODBUS_EXTENDED_STATUS_START,
    PUMP_MODBUS_INTER_REQUEST_DELAY,
    PUMP_MODBUS_MAX_CAPACITY,
    PUMP_MODBUS_MIN_CAPACITY,
    PUMP_MODBUS_OFF_COMMAND,
    PUMP_MODBUS_PROFILE_V15,
    PUMP_MODBUS_READ_FUNCTION,
    PUMP_MODBUS_SETPOINT_REPLY_LENGTH,
    PUMP_MODBUS_V15_MODE_CODES,
)
from .protocol import AquagemProtocolError, crc16_modbus, frame


@dataclass(frozen=True, slots=True)
class AquagemV15Status:
    """Decoded status for the official V1.5 register block."""

    fault_code: int
    pump_on: bool
    speed: int
    protocol: str
    raw_2004: int
    raw_2005: int
    raw_2006: int
    raw_2007: int
    energy_kwh: float
    mode_code: int
    software_version: int
    command_capacity: int | None
    modbus_profile: str = PUMP_MODBUS_PROFILE_V15


def _validate_reply(reply: bytes, unit: int, function: int) -> None:
    if reply[0] != unit or reply[1] != function:
        raise AquagemProtocolError(f"Unexpected Modbus header: {reply.hex(' ')}")
    if reply[-2:] != crc16_modbus(reply[:-2]):
        raise AquagemProtocolError(f"Invalid Modbus CRC: {reply.hex(' ')}")


def _validate_state(state: int, capacity: int) -> None:
    if state not in (0, 1):
        raise AquagemProtocolError(f"Unexpected V1.5 pump state: {state}")
    if state == 0 and capacity != 0:
        raise AquagemProtocolError(
            f"Implausible stopped V1.5 capacity: {capacity}%"
        )
    if state == 1 and not PUMP_MODBUS_MIN_CAPACITY <= capacity <= PUMP_MODBUS_MAX_CAPACITY:
        raise AquagemProtocolError(
            f"Implausible running V1.5 capacity: {capacity}%"
        )


async def _read_setpoint(client) -> int:
    """Read holding register 3001 as documented by Aquagem V1.5."""
    unit = client.modbus_unit
    body = bytes(
        (
            unit,
            PUMP_MODBUS_READ_FUNCTION,
            (PUMP_MODBUS_COMMAND_REGISTER >> 8) & 0xFF,
            PUMP_MODBUS_COMMAND_REGISTER & 0xFF,
            0x00,
            0x01,
        )
    )
    reply = await client._exchange(frame(body), PUMP_MODBUS_SETPOINT_REPLY_LENGTH)
    _validate_reply(reply, unit, PUMP_MODBUS_READ_FUNCTION)
    if reply[2] != 2:
        raise AquagemProtocolError(f"Invalid register 3001 byte count: {reply.hex(' ')}")
    value = int.from_bytes(reply[3:5], "big")
    if value != PUMP_MODBUS_OFF_COMMAND and not (
        PUMP_MODBUS_MIN_CAPACITY <= value <= PUMP_MODBUS_MAX_CAPACITY
    ):
        raise AquagemProtocolError(f"Unexpected register 3001 value: {value}")
    return value


async def async_read_v15_status(client) -> AquagemV15Status:
    """Read 2001..2009 and 3001 according to the Aquagem V1.5 PDF."""
    unit = client.modbus_unit
    body = bytes(
        (
            unit,
            PUMP_MODBUS_READ_FUNCTION,
            (PUMP_MODBUS_EXTENDED_STATUS_START >> 8) & 0xFF,
            PUMP_MODBUS_EXTENDED_STATUS_START & 0xFF,
            0x00,
            PUMP_MODBUS_EXTENDED_STATUS_COUNT,
        )
    )
    reply = await client._exchange(frame(body), PUMP_MODBUS_EXTENDED_STATUS_REPLY_LENGTH)
    _validate_reply(reply, unit, PUMP_MODBUS_READ_FUNCTION)
    payload = reply[3:-2]
    if reply[2] != 18 or len(payload) != 18:
        raise AquagemProtocolError(f"Invalid V1.5 byte count: {reply.hex(' ')}")

    registers = [
        int.from_bytes(payload[index : index + 2], "big")
        for index in range(0, 18, 2)
    ]
    (
        fault_code,
        state,
        capacity,
        power_w,
        raw_2005,
        raw_2006,
        raw_2007,
        mode_code,
        software_version,
    ) = registers

    _validate_state(state, capacity)
    if mode_code not in PUMP_MODBUS_V15_MODE_CODES:
        raise AquagemProtocolError(
            f"Unexpected V1.5 mode code {mode_code}; expected one of "
            f"{PUMP_MODBUS_V15_MODE_CODES}"
        )

    # The official timing diagram requires >=50 ms between the slave reply and
    # the next master request.
    await asyncio.sleep(PUMP_MODBUS_INTER_REQUEST_DELAY)
    try:
        command_capacity = await _read_setpoint(client)
    except AquagemProtocolError:
        command_capacity = None

    return AquagemV15Status(
        fault_code=fault_code,
        pump_on=bool(state),
        speed=capacity,
        protocol=PROTOCOL_PUMP_MODBUS,
        raw_2004=power_w,
        raw_2005=raw_2005,
        raw_2006=raw_2006,
        raw_2007=raw_2007,
        energy_kwh=raw_2007 / 1000,
        mode_code=mode_code,
        software_version=software_version,
        command_capacity=command_capacity,
    )
