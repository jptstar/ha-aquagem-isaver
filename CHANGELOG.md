# Changelog

## 0.3.5-beta.2

- Replace the Aquagem Pump app/HACS/web icon with a transparent-background PNG.
- Keep all Modbus V1.5 beta functionality unchanged from 0.3.5-beta.1.

## 0.3.5-beta.1

- Add optional Aquagem Modbus V1.5 extended reads for registers `2007..2009` without making them mandatory for older/alternate Modbus maps.
- Add **Energy consumption** from register `2007` using the documented kWh value scaled by 1,000.
- Add diagnostic **Mode code** (`2008`) and **Software version** (`2009`) sensors for DM-family validation.
- Add the official V1.5 fault map from the Aquagem RS485 Modbus document, selected only when the extended mode code matches `10/15/19/23/28`.
- Keep the previous Aquagem Modbus fault map as a fallback for devices that do not expose the V1.5 extension.
- Keep the validated DM15 5% capacity grid and register `2004` power sensor from 0.3.4.
- Replace the project brand icon/logo used by Home Assistant, HACS and the project website.
- Mark this release as a beta intended for Antonio's DM15 hardware validation before 0.3.5 stable.

## 0.3.4

- Correct DM15 / standard Aquagem Modbus capacity control to the pump's real **5% steps** (30, 35, 40, ... 100%).
- Mirror the pump's native behavior by rounding unsupported Modbus percentages down to the lower 5% step before writing.
- Promote holding register `2004` from a disabled raw diagnostic value to a native Home Assistant **Power** sensor in watts.
- Add the Home Assistant `power` device class and `measurement` state class for register `2004`.
- Add complete Spanish translations for setup, options and entities.
- Keep generated Home Assistant entity IDs based on the English entity names while allowing localized display names in French and Spanish.
