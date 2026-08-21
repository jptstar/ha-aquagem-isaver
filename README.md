<p align="center">
  <img src="https://raw.githubusercontent.com/jptstar/ha-aquagem-isaver/main/custom_components/aquagem_isaver/brand/icon.png" width="180" alt="Aquagem iSaver">
</p>

<h1 align="center">Aquagem iSaver — Home Assistant</h1>
<p align="center"><strong>Local control and diagnostics for the iSaver Power pool pump inverter.</strong></p>
<p align="center">RS485 · Local polling · No cloud</p>

<p align="center">
  <a href="https://github.com/jptstar/ha-aquagem-isaver"><img alt="Version" src="https://img.shields.io/badge/version-0.2.0-blue"></a>
  <a href="https://github.com/hacs/integration"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-blue"></a>
</p>

> **Unofficial personal project.** Built for fun around a real Aquagem iSaver Power 1100. This project is not affiliated with, endorsed by, or maintained by Aquagem. Product names and trademarks belong to their respective owners.

## What it does

The integration talks directly to the proprietary iSaver RS485 protocol through a transparent RS485-to-TCP gateway.

One C3 status read returns the three useful runtime values at once:

- register `2001`: fault bitfield
- register `2002`: real pump running state
- register `2003`: actual pump speed

Speed commands are written to register `3001`.

No MQTT, Node-RED or cloud service is required once the integration is installed.

## Entities

| Entity | Type | Source |
| --- | --- | --- |
| Pump | Switch | Real state from `2002 bit 0` |
| Speed setpoint | Number | Write to `3001`, 1200–2900 rpm |
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

## About the built-in iSaver modes

The iSaver panel has its own stored speed modes. They are **not exposed as Modbus preset registers** by the available protocol table.

This integration therefore does not invent Home Assistant preset modes. It writes a direct RPM override between **1200 and 2900 rpm**.

That keeps the Home Assistant model simple:

- **Pump OFF** → send the validated RS485 stop command
- **Pump ON** → restore the last running RPM known by the integration
- **Speed setpoint** → direct RPM override

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

## Gateway

Default settings:

| Setting | Value |
| --- | --- |
| TCP port | `502` |
| Gateway mode | Transparent TCP / RTU buffered |
| iSaver serial format | `1200-8-N-1` |
| iSaver address | `0xAA` |
| Polling interval | `5 s` |
| TCP timeout | `5 s` |

The polling interval can be changed from the integration options.

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

- HACS validation
- Home Assistant hassfest

## Credits

Protocol behaviour was cross-checked against a working Node-RED setup, the available iSaver RS485 protocol table, and the independent `backuprestore/isaver-isaverx-RS485-modbus` research.

## Author

**JP — [@jptstar](https://github.com/jptstar)**

Personal Home Assistant project, built for fun.

## License

MIT
