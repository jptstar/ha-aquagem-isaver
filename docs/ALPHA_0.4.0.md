# Aquagem Pump 0.4.0-alpha.2

This alpha starts the transport-layer refactor and adds the first **direct Modbus RTU** path.

## Alpha.2 fix

- Fix Home Assistant 2026.9 startup failure caused by requesting `serialx==1.8.2` while Home Assistant 2026.9 pins `serialx==1.9.0`.
- Align the custom integration requirement with Home Assistant 2026.9: `serialx==1.9.0`.
- Declare the Home Assistant `usb` dependency so the native `SerialPortSelector` can populate USB serial devices correctly.

## What is new

- Existing transparent **RS485/TCP** gateways continue to use the same protocol code.
- New **Direct serial / USB-RS485** connection type in the config flow.
- Direct serial is intentionally limited to the validated **DM-family / standard Aquagem Modbus** profile in this first alpha.
- Serial settings are fixed to **9600 baud, 8 data bits, no parity, 1 stop bit**.
- Uses Home Assistant's native `SerialPortSelector` and `serialx`.
- Keeps the Modbus address configurable in the documented Aquagem range `0xA0..0xBF` (default `0xAA`).
- Adds a conservative 5 ms Modbus RTU inter-frame guard for direct serial.
- Recognizes standard 5-byte Modbus exception replies instead of waiting for a full normal response.
- Optional V1.5 registers `2007..2009` are disabled only by explicit unsupported-register/function exceptions; transient failures are retried later.
- Existing 0.3.x entries migrate automatically to `transport=tcp` without changing their config-entry identity or entity unique IDs.

## Scope

Direct serial in this alpha supports:

- DM15 / INVERsilence-style standard Aquagem Modbus
- function `0x03` reads
- function `0x10` writes
- core registers `2001..2004`
- optional V1.5 registers `2007..2009`
- command register `3001`

Not enabled yet:

- direct serial iSaver C3/D0
- legacy C3/D0 variants from the community forum
- doubled-RPM variants
- switching an existing entry from TCP to serial in the reconfigure flow

## Hardware

Connect the pump's RS485 A/B pair to a compatible USB-RS485 adapter and expose that adapter to Home Assistant. Prefer the stable `/dev/serial/by-id/...` path when available.

In Home Assistant 2026.9, the port should also appear under **Settings → Connectivity → Serial**.

## Test priority

For the first hardware test, verify:

1. the USB-RS485 port appears in the Aquagem Pump setup form;
2. the DM pump validates at address `0xAA`;
3. registers `2001..2004` update normally;
4. `2007..2009` behave the same as through the WaveShare;
5. 5% capacity commands and OFF receive valid Modbus acknowledgements;
6. unplugging/replugging the adapter recovers on a later poll.
