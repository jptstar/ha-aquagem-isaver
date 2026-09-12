# Aquagem Pump 0.4.0 alpha

This alpha series separates protocol handling from the connection transport and adds direct serial / USB-RS485 support.

## 0.4.0-alpha.8

- Add **multiple Aquagem Modbus devices on the same physical RS485 bus**.
- Direct USB-RS485 entries are now identified by serial port **and Modbus slave address**, so addresses such as `0xAA`, `0xAB` and `0xAC` can coexist on one adapter.
- RS485/TCP entries are now identified by gateway host/port **and Modbus slave address**, so several pumps can share one transparent gateway.
- Serialize complete request/reply transactions with an explicit process-wide **FIFO `Rs485BusManager`**. Separate Home Assistant config entries can no longer interleave frames on the same downstream RS485 line, and queued transactions are served in arrival order.
- Cancelled queued transactions are removed cleanly and cannot block devices waiting behind them.
- Direct serial transactions release the port after each frame so another addressed pump can use the same USB-RS485 adapter safely.
- Serial framing is now explicitly opened as **8-N-1** instead of relying on serial-library defaults.
- TCP setup accepts an optional Modbus address. Leave it empty for the existing automatic read-only protocol/address detection, or enter an address to validate a specific Modbus pump on a shared bus.
- Reconfiguration can change a Modbus slave address without blocking other addresses already using the same serial port or TCP gateway.
- Existing entity unique IDs stay based on the Home Assistant config-entry ID, so migration to the multi-device bus identity does not recreate entities.
- Add CI coverage for FIFO ordering and cancellation of a queued transaction.
- A single direct serial port still cannot mix the 1200-baud proprietary iSaver profile and the 9600-baud Aquagem Modbus profile; one physical RS485 line must use one serial configuration.

## 0.4.0-alpha.7

- Fix serial reconfiguration: the `reconfigure_serial` form now has the public `async_step_reconfigure_serial()` handler Home Assistant requires when the form is submitted.
- Add a CI regression check ensuring every literal config-flow `step_id` has a matching public `async_step_<step_id>()` method.

## 0.4.0-alpha.6

- Harden direct serial error handling by normalizing `serialx` backend failures into transport errors handled by the integration.
- After write-only iSaver D0 commands, keep the serial port open long enough for the frame to leave the UART, then close/reopen the stream before the next C3 poll. This prevents an optional D0 acknowledgement or stale bytes from being mistaken for the following status response.
- Keep config-entry endpoint identity synchronized after TCP or serial reconfiguration so a changed endpoint cannot later be configured as an accidental duplicate.
- Make the Modbus fault entity set stable and switch the active legacy/V1.5 bit mapping dynamically when register `2008` is learned after startup. V1.5 detection is remembered through temporary extended-register read failures.
- Change the GitHub release workflow so automatic releases are published only after the `Validate` workflow succeeds on a push to `main`.
- No new pump protocol commands are introduced in this hardening release.

## 0.4.0-alpha.5

- Add a persistent **Operating hours** sensor for every supported pump/drive profile, on TCP and direct serial.
- Count time only while the pump state is confirmed ON; after the integration reaches its communication-failure threshold, accumulation pauses until communication is restored.
- Persist the software hour meter independently from the config entry so Home Assistant restarts and integration reloads keep the accumulated value.
- New installations can enter an **initial operating-hours value** (default `0 h`) to take over an existing pump or drive counter.
- Existing installations start from `0 h` unless a value is set from the integration options.
- Add an options menu with **Set operating-hours counter** and **Reset operating-hours counter** actions.
- Reset is deliberately a configuration action only: no Home Assistant `button` entity is created.
- The sensor uses Home Assistant duration / `total_increasing` semantics so it can be graphed and included in long-term statistics.

## 0.4.0-alpha.4

- Harden existing WaveShare / TCP installations after the serial transport introduction.
- Stop pinning a private `serialx` requirement in the custom integration; Home Assistant's built-in `usb` dependency now owns the compatible serialx version.
- Import serialx only when a direct serial connection is actually opened.
- A serial-library problem can therefore no longer prevent an existing TCP pump entry from loading or prevent the TCP config flow from opening.
- Keep all alpha.3 serial profiles and protocol behavior unchanged.

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
- multiple addressed pumps may share one USB-RS485 adapter
- request/reply transactions are serialized FIFO per physical bus

## Hardware

Connect the pump's RS485 A/B pair to a compatible USB-RS485 adapter and expose that adapter to Home Assistant. Prefer the stable `/dev/serial/by-id/...` path when available.

In Home Assistant 2026.9, the port should also appear under **Settings → Connectivity → Serial**.

## Still intentionally deferred

- community C3/D0 legacy variants
- doubled-RPM variants
- automatic serial baud/protocol detection
- changing an existing entry between TCP and serial transport
- interpreting/depending on a D0 acknowledgement for command success

These are kept separate so the validated iSaver and DM-family profiles remain stable while serial transport is tested independently.
