# Aquagem Pump 0.4.0 alpha

This alpha series separates protocol handling from the connection transport and adds direct serial / USB-RS485 support.

## 0.4.0-alpha.3

- Replace the Modbus-address range control with a plain address field.
- Accept Modbus addresses as decimal `160..191` or hexadecimal `0xA0..0xBF`.
- Add direct serial support for the validated **iSaver Power 1100 C3/D0** profile.
- iSaver direct serial uses **1200 baud, 8N1** and the existing validated C3/D0 framing.
- Keep a conservative **50 ms** guard between direct iSaver serial transactions.
- Keep direct DM-family / standard Aquagem Modbus RTU at **9600 baud, 8N1**.
- The serial setup lets the user choose the pump profile; the Modbus address field is ignored for iSaver.

## 0.4.0-alpha.2

- Align `serialx` with the Home Assistant 2026.9 constraint (`1.9.0`).
- Declare the Home Assistant `usb` dependency required by the native `SerialPortSelector`.

## 0.4.0-alpha.1

- Existing transparent **RS485/TCP** gateways continue to use the same protocol code.
- Add a pluggable transport layer with TCP and direct serial backends.
- Add direct DM-family / standard Aquagem **Modbus RTU** via USB-RS485.
- Modbus serial settings are fixed to **9600 baud, 8 data bits, no parity, 1 stop bit**.
- Use Home Assistant's native `SerialPortSelector` and `serialx`.
- Keep the Modbus address configurable in the documented Aquagem range `0xA0..0xBF` (default `0xAA`).
- Add a 5 ms Modbus RTU inter-frame guard.
- Recognize standard 5-byte Modbus exception replies.
- Retry optional V1.5 registers `2007..2009` after transient communication failures instead of disabling them for the entire session.
- Existing 0.3.x entries migrate automatically to `transport=tcp` without changing config-entry identity or entity unique IDs.

## Direct serial scope

### iSaver C3/D0

- 1200-8-N-1
- validated C3 status request and 9-byte CRC-checked response
- validated D0 RPM/OFF commands
- 1200–2900 rpm in 100 rpm steps
- OFF command value `1`

### Aquagem Modbus RTU

- 9600-8-N-1
- function `0x03` reads
- function `0x10` writes
- core registers `2001..2004`
- optional V1.5 registers `2007..2009`
- command register `3001`
- address range `0xA0..0xBF`, default `0xAA`

## Hardware

Connect the pump's RS485 A/B pair to a compatible USB-RS485 adapter and expose that adapter to Home Assistant. Prefer the stable `/dev/serial/by-id/...` path when available.

In Home Assistant 2026.9, the port should also appear under **Settings → Connectivity → Serial**.

## Still intentionally deferred

- community C3/D0 legacy variants
- doubled-RPM variants
- automatic serial baud/protocol detection
- changing an existing entry between TCP and serial transport
- D0 acknowledgement/retry changes

These are kept separate so the validated iSaver and DM-family profiles remain stable while serial transport is tested independently.
