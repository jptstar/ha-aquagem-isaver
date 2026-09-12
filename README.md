<p align="center">
  <img src="https://raw.githubusercontent.com/jptstar/ha-aquagem-isaver/main/custom_components/aquagem_isaver/brand/icon.png" width="180" alt="Aquagem Pump Home Assistant integration">
</p>

<h1 align="center">Aquagem Pump — Home Assistant</h1>
<p align="center"><strong>Local RS485 control and diagnostics for compatible Aquagem variable-speed pool pumps.</strong></p>
<p align="center">USB-RS485 · RS485/TCP · Modbus RTU · No cloud</p>

<p align="center">
  <a href="https://github.com/jptstar/ha-aquagem-isaver/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/jptstar/ha-aquagem-isaver"></a>
  <a href="https://github.com/hacs/integration"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5"></a>
  <a href="LICENSE"><img alt="GPL-3.0-or-later" src="https://img.shields.io/badge/License-GPL--3.0--or--later-blue"></a>
</p>

## Aquagem Pump 0.4.1

Version **0.4.1** is a maintenance release on top of 0.4.0. For validated DM15 / INVERsilence V1.5 pumps, Home Assistant now creates only the applicable fault-map diagnostic entities once the map is known and removes stale legacy-only entities that previously remained as **Unavailable / No disponible**.

Antonio Garcia's real-hardware DM15 feedback confirms **Mode Code 15**, the 5% capacity grid, register `2004` power reporting, the extended energy/diagnostic block and the physical touch-panel lockout while active Modbus communication is in use.

The 0.4.x line includes transparent **RS485/TCP gateways**, direct **USB-RS485 / Modbus RTU**, multi-device RS485 buses, FIFO transaction scheduling and a persistent software operating-hours counter.

> [!IMPORTANT]
> Aquagem Pump is an unofficial community integration. It is independent and is not developed, approved, endorsed or maintained by Aquagem.

## Compatibility

The integration is structured around the detected or selected **local protocol**, not only the commercial model name.

| Protocol profile | Validated hardware | Serial settings | Control | Status |
|---|---|---|---|:---:|
| **C3 / D0** | **iSaver Power 1100** | `1200-8-N-1` | RPM `1200–2900`, OFF=`1` | ✅ Protocol validated |
| **Modbus 03 / 10** | **DM15 / INVERsilence** | `9600-8-N-1` | Capacity `30–100%` in 5% steps, OFF=`0` | ✅ Protocol validated |

The validated DM15 / INVERsilence profile uses:

- holding registers `2001..2004` for fault, state, running capacity and power;
- function `0x03` for reads;
- function `0x10` and register `3001` for writes;
- capacity steps `30, 35, 40, ... 100%`;
- `3001 = 0` for OFF;
- optional V1.5 registers `2007..2009` when supported by the pump.

Other Aquagem pumps using the same register layout may work, but are not marked as validated until real-hardware feedback confirms them.

## Connection modes

### Transparent RS485/TCP gateway

This remains the easiest setup for network-connected installations. A WaveShare or equivalent gateway must stay in **transparent TCP Server mode**; Aquagem Pump sends complete serial RTU frames itself.

Typical gateway settings:

| Setting | Value |
|---|---|
| TCP mode | TCP Server |
| TCP port | `502` |
| Data bits | `8` |
| Parity | None |
| Stop bits | `1` |
| Flow control | None |
| Protocol conversion | None / transparent |
| iSaver baud | `1200` |
| DM15 / Aquagem Modbus baud | `9600` |

Do **not** enable a gateway's “Modbus TCP to RTU” conversion mode.

#### Validated WaveShare RS485-to-Ethernet example

A **WaveShare RS485-to-Ethernet** gateway has been validated with a real **Aquagem iSaver Power 1100**. The screenshot below shows the working transparent TCP configuration used during validation.

<p align="center">
  <img src="docs/images/waveshare_isaver_setup.webp" width="900" alt="Validated WaveShare RS485-to-Ethernet settings for Aquagem iSaver Power 1100 with Home Assistant">
</p>

For the validated iSaver setup, use **1200 baud, 8 data bits, no parity, 1 stop bit, TCP Server, port 502, Protocol None and Multi-host disabled**. For a DM15 / Aquagem Modbus pump, keep the transparent gateway principle and use **9600-8-N-1** instead.

The gateway is only a transparent transport: Aquagem Pump builds and validates the complete serial frames itself. Other transparent RS485/TCP gateways can work as well; WaveShare is documented here because this configuration was validated on real hardware.

➡️ **[WaveShare RS485-to-Ethernet setup guide for Aquagem + Home Assistant](https://jptstar.github.io/ha-aquagem-isaver/waveshare-rs485-home-assistant.html)**

### Direct USB-RS485

Home Assistant 2026.9+ can connect directly to a USB-RS485 adapter through its native serial stack.

- iSaver C3/D0: `1200-8-N-1`
- DM15 / Aquagem Modbus: `9600-8-N-1`
- prefer a stable `/dev/serial/by-id/...` path when available

Aquagem Pump declares the Home Assistant `usb` dependency. In Home Assistant 2026.9 that system integration supplies the compatible `serialx` version used by the direct serial transport.

## Multiple Modbus devices on one RS485 bus

Version 0.4.1 supports several addressed Aquagem Modbus pumps behind the same physical bus.

Example with one USB-RS485 adapter:

```text
/dev/serial/by-id/usb-RS485...
  ├── DM15 0xAA
  ├── DM15 0xAB
  └── DM15 0xAC
```

The same applies behind one transparent RS485/TCP gateway:

```text
192.168.1.50:502
  ├── DM15 0xAA
  ├── DM15 0xAB
  └── DM15 0xAC
```

Each slave address becomes a separate Home Assistant config entry with its own entities and operating-hours counter.

A shared **FIFO RS485 bus manager** serializes complete request/response transactions, so two Home Assistant entries cannot interleave frames on the same physical line. Cancelled queued requests are removed cleanly instead of blocking the bus.

> One physical RS485 line still uses one serial configuration. Do not mix the 1200-baud iSaver profile and the 9600-baud Modbus profile on the same wired bus.

## Entities

Common entities for all supported profiles:

| Entity | Type | Purpose |
|---|---|---|
| Pump | Fan | ON/OFF and variable-speed control |
| Actual speed / capacity | Sensor | RPM for iSaver, % for Modbus |
| Direct setpoint | Number | Native RPM or capacity command |
| Alarm | Binary sensor | Global fault state |
| Fault code | Sensor | Raw fault word |
| Connection | Binary sensor | Communication status |
| Operating hours | Sensor | Persistent software runtime counter |

Additional Modbus entities:

| Entity | Source |
|---|---|
| Power | register `2004`, W |
| Energy consumption | optional register `2007`, kWh |
| Mode code | optional register `2008` |
| Software version | optional register `2009` |
| Fault binary sensors | active documented legacy/V1.5 fault map |

The V1.5 block is optional. Older or alternate Aquagem maps continue to work when registers `2007..2009` are not implemented. Once the map is known, inactive-map fault entities are removed instead of being left permanently unavailable.

## Operating-hours counter

Every supported pump profile has a persistent software **Operating hours** sensor.

- stored across Home Assistant restarts and integration reloads;
- counts only while the pump is considered running;
- pauses after the communication-failure threshold is reached;
- can start from an existing hour value when the integration is added;
- can be **Set** or **Reset** from the integration options.

The counter is software-based and therefore cannot accumulate time while Home Assistant itself is stopped.

## Automatic protocol detection

Automatic detection is available for TCP gateway setup and uses **read-only probes**.

The integration validates:

1. the proprietary iSaver C3 response signature and CRC;
2. the Aquagem Modbus `03` response for registers `2001..2004`;
3. address `0xAA` first and then the Aquagem address range `0xA0..0xBF` when required;
4. coherent frame structure, CRC, state and running-capacity values.

A generic Modbus reply is not enough to identify an Aquagem pump.

For shared Modbus buses, the setup can also target a specific slave address directly.

## Home Assistant control

### iSaver Power 1100

| Control | Behaviour |
|---|---|
| OFF | validated persistent command value `1` |
| ON | restores the last running RPM |
| Physical range | `1200–2900 rpm` |
| RPM grid | `100 rpm` |
| HA profiles | Max · Day/Jour · Eco · Night/Nuit · Custom/Perso |

The Home Assistant profiles are shortcuts created by the integration; they are not claimed to be native iSaver panel modes.

### DM15 / standard Aquagem Modbus

| Control | Behaviour |
|---|---|
| OFF | writes `3001 = 0` |
| ON | restores the last running capacity |
| Physical range | `30–100%` |
| Capacity grid | `5%` |
| Feedback | actual running capacity from register `2003` |

Unsupported percentages are rounded down to the lower 5% step before writing.

## Communication resilience

Short communication failures do not immediately make the pump unavailable.

- the last validated state is preserved through the first two consecutive failed polls;
- the third consecutive failure marks communication offline;
- polling slows while offline;
- the first successful response restores normal operation immediately.

Serial transport errors drop and recreate the underlying connection cleanly on the next transaction.

## Installation

### HACS

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jptstar&repository=ha-aquagem-isaver&category=integration">
    <img alt="Add Aquagem Pump to HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg">
  </a>
</p>

Or add `jptstar/ha-aquagem-isaver` under **HACS → Custom repositories → Integration**, install **Aquagem Pump**, restart Home Assistant and add it from **Settings → Devices & services**.

Minimum Home Assistant version for the 0.4.x serial stack: **2026.9.0**.

### Manual

Copy:

```text
custom_components/aquagem_isaver
```

into your Home Assistant `custom_components` directory and restart Home Assistant.

## Setup

Choose the connection method in the config flow:

- **RS485/TCP**: enter the gateway host and port; automatic protocol detection is the normal path. For a shared Modbus bus, optionally enter the target slave address.
- **Direct serial / USB-RS485**: select the serial device, select the pump protocol and enter the Modbus slave address when using DM/Aquagem Modbus.

Modbus addresses are accepted in decimal or hexadecimal form in the Aquagem range `0xA0..0xBF`.

Existing entries can be reconfigured without deleting their entities.

## Protocol reference

### iSaver Power 1100 — C3/D0

Validated status request:

```text
AA C3 07 D1 00 02 8C 8C
```

Response structure:

```text
AA C3 [fault hi] [fault lo] [state] [speed hi] [speed lo] [CRC lo] [CRC hi]
```

Speed write prefix:

```text
AA D0 0B B9 [speed hi] [speed lo] [CRC lo] [CRC hi]
```

### DM15 / Aquagem Modbus 03/10

Core read:

```text
slave: 0xA0..0xBF (default 0xAA)
function: 0x03
start register: 2001
count: 4
```

Core registers:

| Register | Interpretation |
|---:|---|
| `2001` | fault bitfield |
| `2002` | operating state |
| `2003` | actual running capacity (%) |
| `2004` | electrical power (W) |

Write:

```text
function 0x10
register 3001
0       = OFF
30..100 = running capacity in 5% steps
```

Optional Modbus V1.5 extension:

| Register | Interpretation |
|---:|---|
| `2007` | energy consumption, scaled to kWh |
| `2008` | mode code |
| `2009` | software version |

## Validation policy

Protocol support is marked as validated only after repeatable real-hardware checks. Transport and scheduling logic is additionally checked by CI, including config-flow dispatch and FIFO/cancellation behavior for shared RS485 buses.

No undocumented write command is added merely to probe hardware.

## Contributions & credits

- **Antonio Garcia** — independent real-hardware DM15 / INVERsilence validation: Modbus read map, native 5% capacity grid, register `2004` power reporting, extended energy/diagnostic registers, confirmed Mode Code `15`, guarded write/OFF behavior and confirmation that the physical touch-panel remains locked while active Modbus communication is in use.

Thanks to everyone sharing diagnostics, protocol captures, device variants and real-hardware feedback.

## Project

Created and maintained by **Jean-Philippe TESTART · `jptstar`**.

Documentation: https://jptstar.github.io/ha-aquagem-isaver/

## License

Copyright © 2026 Jean-Philippe TESTART (`jptstar`).

Distributed under **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). See [LICENSE](LICENSE).

Versions through **0.3.0** were published under the MIT License. **0.3.1 and later** are published under GPL-3.0-or-later.
