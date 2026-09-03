# Aquagem Pump V1 beta — Antonio validation build

Version: **1.0.0-beta.1**  
Branch: **`beta/v1-antonio`**

This beta is intentionally isolated from `main`. It validates the official **Aquagem Inverter Pool Pump RS485 Modbus V1.5 (for V1.0.0) — 250415** register map on Antonio's DM15 / InverSmart hardware before any public V1 release.

## What this beta reads

The stable/basic Modbus signature remains registers `2001..2004` so older Aquagem variants are not reclassified blindly.

When the extended V1.5 signature is coherent, the beta additionally reads:

| Register | V1.5 definition | Home Assistant beta entity |
|---:|---|---|
| `2001` | Error code | Raw fault code + V1.5 fault binary sensors |
| `2002` | Pool pump running state | Pump state |
| `2003` | Running capacity | Running capacity (%) |
| `2004` | Power, W | Power (W) |
| `2005` | Reserved | Register 2005 (raw), disabled by default |
| `2006` | Reserved | Register 2006 (raw), disabled by default |
| `2007` | Power consumption, kWh ×1000 | Energy consumption (kWh) + raw attribute |
| `2008` | Mode code: 10 / 15 / 19 / 23 / 28 | Mode code |
| `2009` | Software version | Software version |
| `3001` | Running capacity setting | Capacity setpoint feedback + number read-back |

The integration does **not** claim that register `2008` identifies DM10/DM15/DM19/DM23/DM28. That correspondence is a test hypothesis only until validated on hardware or documented explicitly by Aquagem.

## V1.5 alarm mapping under test

For a device that matches the extended V1.5 signature, register `2001` is decoded as follows:

| Bit | V1.5 meaning |
|---:|---|
| 0 | Reserved |
| 1 | Communication Error |
| 2 | No water protection |
| 3 | RTC time reading error |
| 4 | Display Board EEPROM reading failure |
| 5 | Circuit board error |
| 6 | Motor power overload |
| 7 | PFC protection |
| 8 | DC abnormal voltage |
| 9 | AC current sampling circuit failure |
| 10 | Phase-deficient protection |
| 11 | Master driver board error |
| 12 | Heat sink sensor error |
| 13 | Heat sink over heat |
| 14 | Output over current |
| 15 | Abnormal input voltage |

Legacy/basic Modbus devices that do not match the extended V1.5 signature keep the previous mapping.

## What Antonio should report

Please capture the diagnostic entity values with the pump stopped and then running:

1. **Mode code** (`2008`) — especially whether DM15 returns `15`.
2. **Software version** (`2009`).
3. **Energy consumption** (`2007`) and its `raw_register_2007` attribute.
4. **Capacity setpoint feedback** (`3001`) at 30%, 35%, 50%, 70% and 100%.
5. Optional: enable **Register 2005 (raw)** and **Register 2006 (raw)** and report their values.
6. Confirm Power (`2004`) remains coherent in watts.
7. Confirm the physical keypad/touch panel behavior while Home Assistant polling is active and while capacity commands are sent.

## Safety / write behavior

Write behavior is unchanged from v0.3.4:

- `3001 = 0` → OFF
- running range `30..100%`
- user-facing control grid is `5%`
- unsupported requested percentages are rounded down to the lower 5% step

The extended V1.5 validation registers are read-only in this beta. No undocumented local/remote or keypad-lock register is written.
