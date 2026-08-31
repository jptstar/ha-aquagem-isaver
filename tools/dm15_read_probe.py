#!/usr/bin/env python3
"""Read-only Aquagem InverSmart / DM15 Modbus RTU-over-TCP probe.

This utility is intentionally READ ONLY. It sends only Modbus function 0x03
(Read Holding Registers) through a transparent RS485-to-TCP gateway.

The exact DM15 serial baud rate has not yet been confirmed from a DM15-specific
protocol document. Start with 9600-8-N-1 because that is documented for a
closely related Aquagem Modbus protocol. If there is no RS485 response at all,
change the gateway serial side to 1200-8-N-1 and repeat the exact same test.

WaveShare settings for each test:
    TCP Server / transparent mode
    Protocol: None
    8 data bits, no parity, 1 stop bit (8N1)
    Baud rate: 9600 first, then 1200 only if 9600 gives no response

Examples:
    # First test: configure the WaveShare for 9600-8-N-1
    python3 tools/dm15_read_probe.py 192.168.1.50 --baud 9600

    # Fallback test: change the WaveShare to 1200-8-N-1 first
    python3 tools/dm15_read_probe.py 192.168.1.50 --baud 1200

The --baud option is informational only: this script cannot reconfigure the
WaveShare serial port. Its purpose is to record which gateway setting was used
in the console output.

The probe tries both common register-address interpretations around the
Aquagem-documented 2001..2004 status block:
    start 2001, count 4
    start 2000, count 4

Default Modbus slave address is 0xAA (170).
"""

from __future__ import annotations

import argparse
import socket
import time


def modbus_crc(data: bytes) -> int:
    """Return Modbus CRC16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def build_read_request(unit: int, start: int, count: int) -> bytes:
    """Build Modbus RTU function 03 request."""
    body = bytes(
        (
            unit,
            0x03,
            (start >> 8) & 0xFF,
            start & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
        )
    )
    crc = modbus_crc(body)
    return body + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def recv_until_idle(sock: socket.socket, timeout: float) -> bytes:
    """Receive bytes until the gateway becomes idle."""
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
        # A normal 4-register response is only 13 bytes; a short idle timeout
        # lets us collect fragmented TCP packets without waiting too long.
        sock.settimeout(0.15)
    return b"".join(chunks)


def parse_response(response: bytes, unit: int) -> str:
    """Return a human-readable summary without interpreting device semantics."""
    if not response:
        return "no response"
    if len(response) < 5:
        return f"short response ({len(response)} bytes)"

    received_crc = response[-2] | (response[-1] << 8)
    calculated_crc = modbus_crc(response[:-2])
    crc_ok = received_crc == calculated_crc

    if response[0] != unit:
        return f"unexpected slave 0x{response[0]:02X}; CRC {'OK' if crc_ok else 'BAD'}"

    function = response[1]
    if function == 0x83 and len(response) >= 5:
        return f"Modbus exception 0x{response[2]:02X}; CRC {'OK' if crc_ok else 'BAD'}"

    if function != 0x03:
        return f"unexpected function 0x{function:02X}; CRC {'OK' if crc_ok else 'BAD'}"

    byte_count = response[2]
    payload = response[3:-2]
    if byte_count != len(payload):
        return (
            f"byte-count mismatch ({byte_count} announced, {len(payload)} received); "
            f"CRC {'OK' if crc_ok else 'BAD'}"
        )

    registers = [
        (payload[i] << 8) | payload[i + 1]
        for i in range(0, len(payload) - 1, 2)
    ]
    values = ", ".join(f"{value} (0x{value:04X})" for value in registers)
    return f"CRC {'OK' if crc_ok else 'BAD'}; registers: [{values}]"


def probe(host: str, port: int, unit: int, timeout: float, baud: int) -> int:
    """Run the two read-only probes."""
    print("Aquagem DM15 / InverSmart read-only probe")
    print(f"Gateway: {host}:{port}")
    print(f"Slave: 0x{unit:02X} ({unit})")
    print(f"Serial setting being tested: {baud}-8-N-1")
    print("Gateway mode: transparent TCP server / Protocol None")
    print("NOTE: --baud does not configure the WaveShare; set it in the gateway UI.\n")

    attempts = ((2001, 4), (2000, 4))
    got_any_response = False

    for start, count in attempts:
        request = build_read_request(unit, start, count)
        print(f"Read Holding Registers start={start}, count={count}")
        print(f"TX: {request.hex(' ').upper()}")

        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.sendall(request)
                response = recv_until_idle(sock, timeout)
        except OSError as err:
            print(f"TCP error: {err}\n")
            continue

        print(f"RX: {response.hex(' ').upper() if response else '<none>'}")
        print(f"Result: {parse_response(response, unit)}\n")
        got_any_response |= bool(response)
        time.sleep(0.25)

    if not got_any_response:
        print("No RS485 response was received for either read request.")
        print("Check A/B wiring, transparent mode, Protocol None and slave address.")
        if baud == 9600:
            print("Next step: change the WaveShare serial baud rate to 1200 and rerun:")
            print(f"  python3 tools/dm15_read_probe.py {host} --port {port} --baud 1200")
        else:
            print("Both the wiring/settings and the assumed protocol may need further investigation.")
        return 2

    print("A response was received. Do not send write commands yet.")
    print("Please send the complete console output back for analysis.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Modbus probe for Aquagem DM15 / InverSmart pumps"
    )
    parser.add_argument("host", help="RS485-to-TCP gateway IP address or hostname")
    parser.add_argument("--port", type=int, default=502, help="TCP port (default: 502)")
    parser.add_argument(
        "--unit",
        type=lambda value: int(value, 0),
        default=0xAA,
        help="Modbus slave address, decimal or 0x-prefixed (default: 0xAA)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        choices=(9600, 1200),
        default=9600,
        help=(
            "WaveShare serial baud rate used for this test (informational only; "
            "default: 9600)"
        ),
    )
    parser.add_argument(
        "--timeout", type=float, default=1.5, help="TCP/read timeout in seconds"
    )
    args = parser.parse_args()

    if not 0 <= args.unit <= 247:
        parser.error("--unit must be between 0 and 247")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    return probe(args.host, args.port, args.unit, args.timeout, args.baud)


if __name__ == "__main__":
    raise SystemExit(main())
