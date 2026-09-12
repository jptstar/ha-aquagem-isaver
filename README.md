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

## Aquagem Pump 0.4.3

Version **0.4.3** makes local-panel coexistence clearer and easier to monitor from Home Assistant.

The feature previously named **Local panel assist** is now shown as **Return to local control / Retour au contrôle local**. It is **enabled by default**. After a Home Assistant command, Aquagem Pump temporarily stops status reads so the pump's physical panel can recover local control. The default protected silence is now **70 seconds**, adjustable from **50 to 180 seconds** in 5-second steps.

Two additional entities make the handover visible:

- **Local panel control available / Commande locale disponible** — binary sensor with a hand icon; ON means the physical panel is available again.
- **Time until local control / Temps restant avant contrôle local** — live countdown in seconds during the protected silence.

### Why this is needed

Real-hardware validation on an **Aquagem iSaver Power 1100** established the following behavior:

```text
Home Assistant sends D0
→ remote priority remains active for about 60 s
→ a C3 status read during this window prolongs/restarts that remote priority
→ after a real silent window, the physical panel regains control
→ once local control has returned, later C3 reads do not restore the old D0 setpoint
```

Tests also showed that keeping the WaveShare TCP connection open without sending RS485 traffic does **not** keep the remote priority active. The important condition is the absence of pump protocol traffic during the handover window.

Aquagem Pump therefore uses this sequence when **Return to local control** is enabled:

```text
normal polling
→ Home Assistant changes speed/state
→ one D0 or Modbus write
→ 70 s protected bus silence by default
→ local panel becomes available
→ normal polling resumes automatically
```

A second Home Assistant command during the protected window is still accepted immediately and restarts the timer from the newest command.

For **DM15 / standard Aquagem Modbus**, the same generic post-command quiet-window mechanism is applied because active RS485 communication can interfere with local-panel use. The exact handover timing can vary by model/firmware, so the delay remains configurable from **50 to 180 seconds**.

> [!IMPORTANT]
> Aquagem Pump is an unofficial community integration. It is independent and is not developed, approved, endorsed or maintained by Aquagem.

## Compatibility

| Protocol profile | Validated hardware | Serial settings | Control | Status |
|---|---|---|---|:---:|
| **C3 / D0** | **iSaver Power 1100** | `1200-8-N-1` | RPM `1200–2900`, OFF=`1` | ✅ Protocol validated |
| **Modbus 03 / 10** | **DM15 / INVERsilence** | `9600-8-N-1` | Capacity `30–100%` in 5% steps, OFF=`0` | ✅ Protocol validated |

Other Aquagem pumps using the same register layout may work, but are not marked as validated until real-hardware feedback confirms them.

## Connection modes

### Transparent RS485/TCP gateway

A WaveShare or equivalent gateway must stay in **transparent TCP Server mode**. Aquagem Pump builds and validates the complete serial frames itself.

Typical settings:

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

Do **not** enable a gateway's Modbus TCP-to-RTU conversion mode.

A real **WaveShare RS485-to-Ethernet** installation has been validated with an iSaver Power 1100. For that setup use **1200 baud, 8 data bits, no parity, 1 stop bit, TCP Server, port 502, Protocol None and Multi-host disabled**.

➡️ **[WaveShare RS485-to-Ethernet setup guide](https://jptstar.github.io/ha-aquagem-isaver/waveshare-rs485-home-assistant.html)**

### Direct USB-RS485

Home Assistant 2026.9+ can connect directly through its native serial stack.

- iSaver C3/D0: `1200-8-N-1`
- DM15 / Aquagem Modbus: `9600-8-N-1`
- prefer a stable `/dev/serial/by-id/...` path when available

## Multiple Modbus devices on one RS485 bus

Several addressed Aquagem Modbus pumps can share one physical bus. Each slave address becomes a separate Home Assistant config entry while a shared FIFO RS485 bus manager serializes complete request/response transactions.

Example:

```text
192.168.1.50:502
  ├── DM15 0xAA
  ├── DM15 0xAB
  └── DM15 0xAC
```

Do not mix the 1200-baud iSaver profile and the 9600-baud Modbus profile on the same wired RS485 line.

## Entities

Common entities include:

| Entity | Type | Purpose |
|---|---|---|
| Pump | Fan | ON/OFF and variable-speed control |
| Actual speed / capacity | Sensor | RPM for iSaver, % for Modbus |
| Direct setpoint | Number | Native RPM or capacity command |
| Alarm | Binary sensor | Global fault state |
| Fault code | Sensor | Raw fault word |
| Connection | Binary sensor | Communication status |
| Operating hours | Sensor | Persistent software runtime counter |
| **Return to local control** | Switch | Enables the protected post-command quiet window; ON by default |
| **Delay before return to local control** | Number | 50–180 s, default 70 s on new installs |
| **Time until local control** | Sensor | Live seconds remaining during the quiet window |
| **Local panel control available** | Binary sensor | Hand indicator; ON when the local panel is available |
| Last control change source | Sensor | Home Assistant or external/local panel |

Additional DM15 / Modbus entities include electrical power from register `2004`, optional energy consumption from `2007`, mode code `2008`, software version `2009`, and protocol-specific fault sensors.

## Local-control handover in practice

Example with a 70-second default:

```text
t = 0 s    Home Assistant commands 1800 rpm
           → remote control active
           → countdown starts at 70 s
           → hand binary sensor is OFF

t ≈ 70 s   protected silence expires
           → hand binary sensor becomes ON
           → normal status polling resumes

later       user changes speed on the physical panel
           → accepted locally
           → Home Assistant sees it on the next normal status read
```

If Home Assistant sends another command before the timer expires, the countdown restarts from that newest command.

Disabling **Return to local control** removes this protected window and restores normal polling immediately. On iSaver hardware this can prevent the physical panel from regaining control if status reads keep arriving inside the remote-priority watchdog period.

## Home Assistant control

### iSaver Power 1100

| Control | Behaviour |
|---|---|
| OFF | validated persistent command value `1` |
| ON | restores the last running RPM |
| Physical range | `1200–2900 rpm` |
| RPM grid | `100 rpm` |
| HA profiles | Max · Day/Jour · Eco · Night/Nuit · Custom/Perso |

### DM15 / standard Aquagem Modbus

| Control | Behaviour |
|---|---|
| OFF | writes `3001 = 0` |
| ON | restores the last running capacity |
| Physical range | `30–100%` |
| Capacity grid | `5%` |
| Feedback | actual running capacity from register `2003` |

## Operating-hours counter

Every supported pump profile has a persistent software **Operating hours** sensor. It survives Home Assistant restarts and integration reloads, pauses after the communication-failure threshold is reached, and can start from an existing hour value.

## Automatic protocol detection

TCP gateway setup can automatically detect supported profiles using read-only probes. The integration validates the proprietary iSaver C3 response signature and the Aquagem Modbus `03` response before selecting a protocol.

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

## Documentation

- [Aquagem Pump documentation](https://jptstar.github.io/ha-aquagem-isaver/)
- [Aquagem iSaver Power 1100 + Home Assistant](https://jptstar.github.io/ha-aquagem-isaver/isaver-power-1100-home-assistant.html)
- [Aquagem DM15 / INVERsilence + Home Assistant](https://jptstar.github.io/ha-aquagem-isaver/aquagem-dm15-home-assistant.html)
- [WaveShare RS485/TCP setup](https://jptstar.github.io/ha-aquagem-isaver/waveshare-rs485-home-assistant.html)

## Contributions & credits

**Antonio Garcia** provided independent real-hardware DM15 / INVERsilence validation including the Modbus read map, native 5% capacity grid, register `2004` power reporting, extended energy/diagnostic registers, Mode Code `15` observation and guarded write/OFF behavior.

Thanks to everyone sharing diagnostics, protocol captures, device variants and real-hardware feedback.

## Project

Created and maintained by **Jean-Philippe TESTART · `jptstar`**.

## License

Copyright © 2026 Jean-Philippe TESTART (`jptstar`).

Distributed under **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). See [LICENSE](LICENSE).

Versions through **0.3.0** were published under the MIT License. **0.3.1 and later** are published under GPL-3.0-or-later.
