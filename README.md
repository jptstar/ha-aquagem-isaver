<p align="center">
  <img src="https://raw.githubusercontent.com/jptstar/ha-aquagem-isaver/main/custom_components/aquagem_isaver/brand/icon.png" width="180" alt="Aquagem iSaver">
</p>

<h1 align="center">Aquagem iSaver — Home Assistant</h1>
<p align="center"><strong>Local control and diagnostics for the iSaver Power pool pump inverter.</strong></p>
<p align="center">RS485 · Local polling · No cloud</p>

<p align="center">
  <a href="https://github.com/jptstar/ha-aquagem-isaver"><img alt="Version" src="https://img.shields.io/badge/version-0.2.6-blue"></a>
  <a href="https://github.com/hacs/integration"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-blue"></a>
</p>

> **Unofficial personal project.** Built for fun around a real Aquagem iSaver Power 1100. This project is not affiliated with, endorsed by, or maintained by Aquagem. Product names and trademarks belong to their respective owners.

## What it does

The integration talks directly to the proprietary iSaver RS485 protocol through a transparent RS485-to-TCP gateway.

One C3 status read returns:

- register `2001`: fault bitfield
- register `2002`: real pump running state
- register `2003`: actual pump speed

Speed commands are written to register `3001`.

No MQTT, Node-RED or cloud service is required once the integration is installed.

## Main control

The pump is exposed as a Home Assistant **fan entity** so ON/OFF and variable speed are available from one control.

| Control | Behaviour |
| --- | --- |
| OFF | Sends the validated iSaver stop value `1` |
| ON | Restores the last running speed, constrained to the configured range |
| Speed | Home Assistant `0–100%`, mapped to the configured RPM range |
| Max | Configurable RPM profile |
| Day / Jour | Configurable RPM profile |
| Eco | Configurable RPM profile |
| Night / Nuit | Configurable RPM profile |
| Custom / Perso | Automatically shown when the current RPM does not match any configured profile |

The four speed profiles are **Home Assistant profiles**, inspired by the previous Node-RED setup. They are not claimed to be native Modbus mode registers. Selecting a profile simply writes its configured RPM value.

The displayed profile is determined from the **actual pump speed**. If the measured RPM exactly matches Max, Day, Eco or Night, that profile is shown even when the speed was changed outside Home Assistant. Any other running speed is displayed as **Custom**.

Preset identifiers are language-neutral internally (`max`, `day`, `eco`, `night`, `custom`) and Home Assistant translates their display names automatically:

- English: **Max · Day · Eco · Night · Custom**
- French: **Max · Jour · Eco · Nuit · Perso**

This keeps automations independent from the Home Assistant interface language. Labels used by version 0.2.5 are also accepted as compatibility aliases when passed directly to the preset service.

## Options

Open **Settings → Devices & services → Aquagem iSaver → Configure**.

You can set:

| Option | Default | Limits |
| --- | ---: | --- |
| Polling interval | `5 s` | 5–300 s |
| Minimum operating speed | `1200 rpm` | 1200–2900, steps of 100 |
| Maximum operating speed | `2900 rpm` | 1200–2900, steps of 100 |
| Night profile | `1200 rpm` | inside configured min/max |
| Eco profile | `2000 rpm` | inside configured min/max |
| Day profile | `2400 rpm` | inside configured min/max |
| Max profile | `2900 rpm` | inside configured min/max |

The physical protocol safety limits remain fixed: **never below 1200 rpm and never above 2900 rpm**. The configured minimum must also be lower than the configured maximum.

## Reconfigure device

Existing devices can be reconfigured without removing and recreating the integration.

Open the Aquagem iSaver integration entry and choose **Reconfigure**. You can change:

- device name
- RS485/TCP gateway IP address
- TCP port

Home Assistant tests the new connection before saving and automatically reloads the integration after a successful change. Existing entity identities are preserved.

## Entities

| Entity | Type | Source / role |
| --- | --- | --- |
| Pump | Fan | ON/OFF, 0–100% speed and profiles |
| RPM setpoint | Number | Direct RPM command within configured limits |
| Actual speed | Sensor | `2003` |
| Alarm | Binary sensor | `2001 != 0` |
| RS485 communication error | Binary sensor | `2001 bit 4` |
| High temperature speed reduction | Binary sensor | `2001 bit 5` |
| Keypad communication error | Binary sensor | `2001 bit 6` |
| Keypad EEPROM error | Binary sensor | `2001 bit 7` |
| RTC clock error | Binary sensor | `2001 bit 8` |
| Main board EEPROM error | Binary sensor | `2001 bit 9` |
| Current detection circuit fault | Binary sensor | `2001 bit 10` |
| Main drive fault | Binary sensor | `2001 bit 11` |
| Heatsink sensor fault | Binary sensor | `2001 bit 12` |
| Heatsink overheat | Binary sensor | `2001 bit 13` |
| Overcurrent | Binary sensor | `2001 bit 14` |
| Abnormal input voltage | Binary sensor | `2001 bit 15` |
| Raw fault code | Sensor | `2001` |
| Connection | Binary sensor | Coordinator status |

Fault and connection entities are grouped as Home Assistant diagnostics.

## Upgrade note: switch → fan

Starting with 0.2.1, the old pump `switch` is replaced by the variable-speed `fan` entity. The integration removes the obsolete switch registry entry during setup so it does not remain as an unavailable entity.

Automations that explicitly target the former `switch` entity must be updated to the new `fan` entity.

## About the built-in iSaver modes

The iSaver panel has its own stored speed modes. They are **not exposed as documented Modbus preset registers** by the available protocol table.

The Home Assistant profiles in this integration are therefore configurable RPM shortcuts and remain distinct from the panel's internal/manual state.

The inverter can still retain or return to its own local/manual state depending on its internal priority logic.

## Important: OFF is sent as value `1`

The protocol sheet lists `0` as OFF for register `3001`, but the same material also contains an explicit `OFF = 1` note.

On the tested iSaver Power 1100:

- `1` gives a persistent RS485 stop
- `0` can be transient and the inverter may resume its previously stored speed

Independent iSaver RS485 implementations use the same `1 rpm` stop command. For that reason this integration intentionally writes **`1` for OFF**.

## Installation

### HACS

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jptstar&repository=ha-aquagem-isaver&category=integration">
    <img alt="Add Aquagem iSaver to HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg">
  </a>
</p>

Or add the repository manually:

1. Open HACS.
2. Open **Custom repositories**.
3. Add `jptstar/ha-aquagem-isaver`.
4. Select **Integration**.
5. Install **Aquagem iSaver**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration → Aquagem iSaver**.

### Manual

Copy:

```text
custom_components/aquagem_isaver
```

into your Home Assistant `custom_components` directory, then restart Home Assistant.

## WaveShare gateway setup

The iSaver must be connected through a **transparent RS485-to-TCP gateway**. The setup below has been validated with a WaveShare gateway.

<p align="center">
  <img src="docs/images/waveshare_isaver_setup.jpg" width="900" alt="WaveShare RS485-to-TCP settings for Aquagem iSaver">
</p>

The screenshot is anonymized. The example IP addresses are placeholders, and the destination fields are not used while the gateway operates as a TCP server.

| WaveShare setting | Required value |
| --- | --- |
| Work Mode | `TCP Server` |
| Device Port | `502` |
| Baud Rate | `1200` |
| Databits | `8` |
| Parity | `None` |
| Stopbits | `1` |
| Flow control | `None` |
| Protocol | `None` |
| Enable Multi-host | `No` |

> **Important:** do not select **Modbus TCP to RTU**. The iSaver uses its own proprietary serial frames and the integration sends those frames directly through the transparent gateway.

The gateway's **Device IP**, **Subnet Mask** and **Gateway** must match your own LAN. When `Work Mode` is `TCP Server`, the `Destination IP/DNS` and `Destination Port` fields are not used by this integration.

Generic communication defaults used by the integration:

| Setting | Value |
| --- | --- |
| TCP port | `502` |
| Gateway mode | Transparent TCP / RTU buffered |
| iSaver serial format | `1200-8-N-1` |
| iSaver address | `0xAA` |
| Polling interval | `5 s` |
| TCP timeout | `5 s` |

## Protocol

Validated request:

```text
AA C3 07 D1 00 02 8C 8C
```

The 9-byte response is decoded as:

```text
AA C3 [fault hi] [fault lo] [state] [speed hi] [speed lo] [CRC lo] [CRC hi]
```

Write prefix:

```text
AA D0 0B B9 [speed hi] [speed lo] [CRC lo] [CRC hi]
```

The integration validates the complete C3 response, including its CRC, before updating Home Assistant.

## Brand assets

Home Assistant 2026.3 and newer can load the included integration icon and logo directly from:

```text
custom_components/aquagem_isaver/brand/
```

The assets use a transparent background and are inspired by the physical iSaver controller.

## Validation

The repository includes GitHub Actions for:

- Python compilation
- HACS validation
- Home Assistant hassfest

## Credits

Protocol behaviour was cross-checked against a working Node-RED setup, the available iSaver RS485 protocol table, and the independent `backuprestore/isaver-isaverx-RS485-modbus` research.

## Author

**JP — [@jptstar](https://github.com/jptstar)**

Personal Home Assistant project, built for fun.

## License

MIT
