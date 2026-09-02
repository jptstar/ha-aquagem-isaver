#!/usr/bin/env python3
"""Interactive Aquagem DM15 / InverSmart Modbus validation tool.

This tool validates the documented read registers first, then asks the user to
verify several manual pump speeds. Only after all required read/manual checks
pass does it offer an optional Modbus write phase.

Documented DM15/InverSmart profile used by this tool:
    Modbus RTU over transparent RS485/TCP gateway
    Slave address: 0xAA (170)
    Serial: 9600-8-N-1
    Read function: 0x03
    Write function: 0x10
    2001: error bitfield
    2002: operating state (bit 0 = pump on)
    2003: running capacity (%)
    2004: live value, kept RAW because the public table does not give a clear unit
    3001: running capacity command (0 = OFF, 30..100 = running %)

SAFETY
------
The write phase changes the real pump speed. Stay physically close to the pump
and controller. Be ready to take back manual control immediately or disconnect
power if the pump behaves unexpectedly. The script aborts the write sequence on
communication errors, new fault bits, unexpected state/capacity, or negative
operator confirmation.

The script never writes before all read-only and manual-speed checks pass and
an explicit interactive confirmation is entered.
"""

from __future__ import annotations

import argparse
import socket
import time
from dataclasses import dataclass

READ_FUNCTION = 0x03
WRITE_FUNCTION = 0x10
STATUS_START = 2001
STATUS_COUNT = 4
COMMAND_REGISTER = 3001
DEFAULT_UNIT = 0xAA
DEFAULT_PORT = 502
DEFAULT_BAUD = 9600
MANUAL_TEST_SPEEDS = (30, 50, 70, 100)
WRITE_TEST_SPEEDS = (30, 50, 70, 100)

FAULT_BITS = {
    0: "DC voltage abnormal",
    1: "AC current sampling circuit failure",
    2: "Phase-deficient protection",
    3: "Master drive error",
    4: "Heat sink sensor error",
    5: "Heat sink over-temperature",
    6: "Output current exceeds limit",
    7: "Input voltage abnormal",
    8: "No-water protection",
    9: "Display board / master communication failure",
    10: "Display board EEPROM reading failure",
    11: "RTC time reading error",
    12: "Master board EEPROM reading failure",
    13: "Motor current detection error",
    14: "Motor power overload",
    15: "PFC protection",
}


@dataclass
class Status:
    fault_code: int
    state: int
    capacity: int
    reg2004: int

    @property
    def pump_on(self) -> bool:
        return bool(self.state & 0x0001)


class ProbeError(RuntimeError):
    """Validation or communication error."""


def modbus_crc(data: bytes) -> int:
    """Return Modbus CRC16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def add_crc(body: bytes) -> bytes:
    crc = modbus_crc(body)
    return body + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def build_read_request(unit: int, start: int, count: int) -> bytes:
    return add_crc(
        bytes(
            (
                unit,
                READ_FUNCTION,
                (start >> 8) & 0xFF,
                start & 0xFF,
                (count >> 8) & 0xFF,
                count & 0xFF,
            )
        )
    )


def build_write_capacity_request(unit: int, value: int) -> bytes:
    """Build function 0x10 write of one INT16 register at 3001."""
    if value != 0 and not 30 <= value <= 100:
        raise ValueError("capacity command must be 0 (OFF) or 30..100 percent")
    body = bytes(
        (
            unit,
            WRITE_FUNCTION,
            (COMMAND_REGISTER >> 8) & 0xFF,
            COMMAND_REGISTER & 0xFF,
            0x00,
            0x01,
            0x02,
            (value >> 8) & 0xFF,
            value & 0xFF,
        )
    )
    return add_crc(body)


def recv_until_idle(sock: socket.socket, timeout: float) -> bytes:
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    while True:
        try:
            chunk = sock.recv(256)
        except socket.timeout:
            break
        if not chunk:
            break
        chunks.append(chunk)
        sock.settimeout(0.15)
    return b"".join(chunks)


def transact(host: str, port: int, request: bytes, timeout: float) -> bytes:
    print(f"TX: {request.hex(' ').upper()}")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(request)
            response = recv_until_idle(sock, timeout)
    except OSError as err:
        raise ProbeError(f"TCP error: {err}") from err
    print(f"RX: {response.hex(' ').upper() if response else '<none>'}")
    if not response:
        raise ProbeError("no response")
    return response


def validate_crc(response: bytes) -> None:
    if len(response) < 5:
        raise ProbeError(f"short response ({len(response)} bytes)")
    received_crc = response[-2] | (response[-1] << 8)
    calculated_crc = modbus_crc(response[:-2])
    if received_crc != calculated_crc:
        raise ProbeError(
            f"bad CRC: received 0x{received_crc:04X}, expected 0x{calculated_crc:04X}"
        )


def parse_read_response(response: bytes, unit: int, expected_count: int) -> list[int]:
    validate_crc(response)
    if response[0] != unit:
        raise ProbeError(f"unexpected slave 0x{response[0]:02X}")
    if response[1] == (READ_FUNCTION | 0x80):
        raise ProbeError(f"Modbus exception 0x{response[2]:02X}")
    if response[1] != READ_FUNCTION:
        raise ProbeError(f"unexpected function 0x{response[1]:02X}")

    byte_count = response[2]
    payload = response[3:-2]
    if byte_count != len(payload):
        raise ProbeError(
            f"byte-count mismatch: announced {byte_count}, received {len(payload)}"
        )
    if byte_count != expected_count * 2:
        raise ProbeError(
            f"unexpected data length: got {byte_count} bytes, expected {expected_count * 2}"
        )

    return [
        (payload[i] << 8) | payload[i + 1]
        for i in range(0, len(payload), 2)
    ]


def parse_write_response(response: bytes, unit: int) -> None:
    validate_crc(response)
    if response[0] != unit:
        raise ProbeError(f"unexpected slave 0x{response[0]:02X}")
    if response[1] == (WRITE_FUNCTION | 0x80):
        raise ProbeError(f"Modbus exception 0x{response[2]:02X}")
    if response[1] != WRITE_FUNCTION:
        raise ProbeError(f"unexpected function 0x{response[1]:02X}")
    if len(response) != 8:
        raise ProbeError(f"unexpected write ACK length: {len(response)} bytes")

    start = (response[2] << 8) | response[3]
    count = (response[4] << 8) | response[5]
    if start != COMMAND_REGISTER or count != 1:
        raise ProbeError(
            f"unexpected write ACK: start={start}, count={count}; expected 3001, 1"
        )


def read_register(
    host: str, port: int, unit: int, timeout: float, register: int
) -> int:
    print(f"Read register {register}")
    response = transact(host, port, build_read_request(unit, register, 1), timeout)
    value = parse_read_response(response, unit, 1)[0]
    print(f"Result: {value} (0x{value:04X})\n")
    return value


def read_status(host: str, port: int, unit: int, timeout: float) -> Status:
    print("Read status block 2001..2004")
    response = transact(
        host,
        port,
        build_read_request(unit, STATUS_START, STATUS_COUNT),
        timeout,
    )
    values = parse_read_response(response, unit, STATUS_COUNT)
    status = Status(*values)
    print_status(status)
    return status


def print_status(status: Status) -> None:
    print(
        "Decoded: "
        f"2001 fault=0x{status.fault_code:04X}, "
        f"2002 state=0x{status.state:04X} ({'ON' if status.pump_on else 'OFF'}), "
        f"2003 capacity={status.capacity}%, "
        f"2004 raw={status.reg2004} (0x{status.reg2004:04X})"
    )
    if status.fault_code:
        print("Active fault bits:")
        for bit, label in FAULT_BITS.items():
            if status.fault_code & (1 << bit):
                print(f"  bit {bit}: {label}")
    else:
        print("Active fault bits: none")
    print()


def ask_enter_or_abort(message: str) -> None:
    answer = input(f"{message}\nPress ENTER when ready, or type q to abort: ").strip().lower()
    if answer == "q":
        raise KeyboardInterrupt


def ask_yes(message: str) -> bool:
    return input(f"{message} [y/N]: ").strip().lower() in {"y", "yes"}


def check_initial_registers(host: str, port: int, unit: int, timeout: float) -> Status:
    print("=" * 72)
    print("PHASE 1 - READ-ONLY REGISTER VALIDATION")
    print("=" * 72)

    block = read_status(host, port, unit, timeout)

    print("Now checking each documented readable register individually.")
    individual = {}
    for register in range(2001, 2005):
        individual[register] = read_register(host, port, unit, timeout, register)
        time.sleep(0.15)

    # 2004 is a live value and may legitimately change between sequential reads,
    # so the individual-read phase validates response/CRC/addressing rather than
    # requiring all values to remain byte-for-byte identical to the earlier block.
    if individual[2001]:
        raise ProbeError(
            "fault register 2001 is non-zero; do not continue to write tests"
        )

    print("PASS: registers 2001..2004 all respond individually with valid CRC.\n")
    return block


def manual_speed_validation(
    host: str, port: int, unit: int, timeout: float
) -> None:
    print("=" * 72)
    print("PHASE 2 - MANUAL SPEED VALIDATION (READ ONLY)")
    print("=" * 72)
    print(
        "For each step, set the pump speed MANUALLY on its own controller.\n"
        "The script will only read registers and verify that 2003 follows the\n"
        "manual percentage. No Modbus write is sent in this phase.\n"
    )

    for speed in MANUAL_TEST_SPEEDS:
        ask_enter_or_abort(
            f"Set the pump MANUALLY to {speed}% and wait until the speed is stable."
        )
        status = read_status(host, port, unit, timeout)

        if status.fault_code:
            raise ProbeError(
                f"fault code became 0x{status.fault_code:04X} during manual {speed}% test"
            )
        if not status.pump_on:
            raise ProbeError(f"register 2002 reports OFF during manual {speed}% test")
        if status.capacity != speed:
            raise ProbeError(
                f"manual {speed}% test mismatch: register 2003 reports {status.capacity}%"
            )
        print(f"PASS: manual {speed}% -> register 2003 = {speed}%.\n")

    print("PASS: all required manual-speed checks matched register 2003.\n")


def write_capacity(
    host: str,
    port: int,
    unit: int,
    timeout: float,
    value: int,
) -> None:
    label = "OFF" if value == 0 else f"{value}%"
    print(f"Write register 3001 = {value} ({label}) using function 0x10")
    response = transact(
        host, port, build_write_capacity_request(unit, value), timeout
    )
    parse_write_response(response, unit)
    print("Write ACK: CRC OK, register 3001, count 1\n")


def modbus_speed_validation(
    host: str,
    port: int,
    unit: int,
    timeout: float,
    settle: float,
) -> bool:
    print("=" * 72)
    print("PHASE 3 - MODBUS SPEED COMMAND TESTS")
    print("=" * 72)
    print(
        "WARNING: the following phase WILL CHANGE THE REAL PUMP SPEED.\n"
        "Stay next to the pump/controller. Keep manual control available.\n"
        "If the pump accelerates unexpectedly, makes abnormal noise, loses water,\n"
        "or behaves abnormally, take manual control immediately or disconnect\n"
        "power before doing anything else.\n"
    )

    phrase = input(
        "Type exactly 'I ACCEPT MODBUS WRITES' to unlock the write tests: "
    ).strip()
    if phrase != "I ACCEPT MODBUS WRITES":
        print("Write phase not unlocked. Exiting without sending any write command.")
        return False

    for speed in WRITE_TEST_SPEEDS:
        ask_enter_or_abort(
            f"NEXT MODBUS TEST: command {speed}%. Ensure it is safe to change speed now."
        )
        before = read_status(host, port, unit, timeout)
        if before.fault_code:
            raise ProbeError("fault present before write; aborting write sequence")

        write_capacity(host, port, unit, timeout, speed)
        print(f"Waiting {settle:.1f} s for the pump to settle...\n")
        time.sleep(settle)
        after = read_status(host, port, unit, timeout)

        if after.fault_code:
            raise ProbeError(
                f"new fault after {speed}% command: 0x{after.fault_code:04X}"
            )
        if not after.pump_on:
            raise ProbeError(f"pump reports OFF after {speed}% command")
        if after.capacity != speed:
            raise ProbeError(
                f"commanded {speed}% but register 2003 reports {after.capacity}%"
            )

        print(f"PASS: Modbus command {speed}% -> register 2003 = {speed}%.\n")
        if not ask_yes("Does the physical pump sound and behave normally?"):
            raise ProbeError(
                "operator did not confirm normal pump behaviour; stopping write sequence"
            )
        print()

    print("PASS: all Modbus speed commands 30/50/70/100% were validated.\n")
    return True


def final_stop_test(
    host: str,
    port: int,
    unit: int,
    timeout: float,
    settle: float,
) -> None:
    print("=" * 72)
    print("PHASE 4 - FINAL OFF TEST")
    print("=" * 72)
    print(
        "The documented DM15 command is register 3001 = 0 for OFF.\n"
        "This is the final test and is intentionally performed only after all\n"
        "speed commands have passed.\n"
    )

    phrase = input("Type exactly 'STOP WITH 0' to send the OFF command: ").strip()
    if phrase != "STOP WITH 0":
        print("OFF test skipped. No stop command was sent.")
        return

    write_capacity(host, port, unit, timeout, 0)
    print(f"Waiting {settle:.1f} s for the pump to stop...\n")
    time.sleep(settle)
    status = read_status(host, port, unit, timeout)

    if status.fault_code:
        raise ProbeError(f"fault after OFF command: 0x{status.fault_code:04X}")
    if status.pump_on or status.capacity != 0:
        print("!!! OFF VALIDATION FAILED !!!")
        print(
            "The pump did not report a clean OFF state. Take manual control now.\n"
            "If the real pump is not safely stopped, disconnect power if necessary."
        )
        raise ProbeError(
            f"OFF mismatch: state=0x{status.state:04X}, capacity={status.capacity}%"
        )

    print("PASS: register 3001 = 0 stopped the pump; 2002=OFF and 2003=0%.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive full Modbus validation for Aquagem DM15 / InverSmart"
    )
    parser.add_argument("host", help="RS485-to-TCP gateway IP address or hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--unit", type=lambda value: int(value, 0), default=DEFAULT_UNIT
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help="Informational only; configure the gateway itself to this baud rate",
    )
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument(
        "--settle",
        type=float,
        default=3.0,
        help="Seconds to wait after each Modbus command before re-reading",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Run register and manual-speed validation only; never offer writes",
    )
    args = parser.parse_args()

    if not 0 <= args.unit <= 247:
        parser.error("--unit must be between 0 and 247")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.settle < 0:
        parser.error("--settle must be >= 0")

    print("Aquagem DM15 / InverSmart full validation probe")
    print(f"Gateway: {args.host}:{args.port}")
    print(f"Slave: 0x{args.unit:02X} ({args.unit})")
    print(f"Serial setting being tested: {args.baud}-8-N-1")
    print("Gateway mode: transparent TCP server / Protocol None")
    print("NOTE: --baud does not configure the WaveShare; set it in the gateway UI.")
    print()
    print("SAFETY: stay next to the pump throughout the test.")
    print("Be ready to take manual control or disconnect power if behaviour is abnormal.")
    print()

    try:
        check_initial_registers(args.host, args.port, args.unit, args.timeout)
        manual_speed_validation(args.host, args.port, args.unit, args.timeout)

        if args.read_only:
            print("Read-only mode requested: all read/manual checks passed. No writes sent.")
            return 0

        writes_completed = modbus_speed_validation(
            args.host, args.port, args.unit, args.timeout, args.settle
        )
        if not writes_completed:
            return 0

        # Requiring an explicit second confirmation prevents accidental OFF.
        if not ask_yes("Proceed to the separate final OFF test?"):
            print("OFF test skipped.")
            return 0
        final_stop_test(args.host, args.port, args.unit, args.timeout, args.settle)

    except KeyboardInterrupt:
        print("\nTest aborted by operator. No further commands will be sent.")
        return 130
    except ProbeError as err:
        print(f"\nTEST ABORTED: {err}")
        print("No further Modbus write commands will be sent.")
        print("If pump behaviour is abnormal, take manual control or disconnect power.")
        return 2

    print("=" * 72)
    print("ALL REQUESTED TESTS COMPLETED SUCCESSFULLY")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
