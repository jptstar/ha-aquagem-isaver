# Changelog

## 0.3.4

- Correct DM15 / standard Aquagem Modbus capacity control to the pump's real **5% steps** (30, 35, 40, ... 100%).
- Mirror the pump's native behavior by rounding unsupported Modbus percentages down to the lower 5% step before writing.
- Promote holding register `2004` from a disabled raw diagnostic value to a native Home Assistant **Power** sensor in watts.
- Add the Home Assistant `power` device class and `measurement` state class for register `2004`.
- Add complete Spanish translations for setup, options and entities.
- Keep generated Home Assistant entity IDs based on the English entity names while allowing localized display names in French and Spanish.

## 0.3.3

- Debounce transient local communication failures: keep the last validated pump state through the first two consecutive failed polls.
- Mark the pump offline only after 3 consecutive communication failures.
- Reduce polling to 30 seconds while offline, or keep the configured polling interval when it is already slower.
- Restore the online state and normal polling immediately on the first successful protocol response.
- Keep the connectivity diagnostic available while offline and expose the current consecutive-failure count and threshold as attributes.
- Keep protocol framing, register maps, scaling and write commands unchanged.

## 0.3.2

- Version-only release created before the resilience changes reached the release tag; no functional integration code change compared with 0.3.1.

## 0.3.1

- Change the project license from MIT to **GNU GPL v3.0 or later** (`GPL-3.0-or-later`).
- Update the README license badge and project licensing notice.
- Clarify that releases through 0.3.0 remain available under the license terms under which they were published.

## 0.3.0

- Add validated **DM15 / INVERsilence** support through standard Modbus RTU at 9600-8-N-1.
- Add read-only automatic protocol detection with signature and CRC validation.
- Detect standard Aquagem Modbus pumps at address `0xAA` first, then scan the configurable `0xA0..0xBF` range when needed.
- Keep a manual protocol fallback when automatic detection cannot identify the pump.
- Store the detected protocol and Modbus address so normal polling does not repeat auto-detection.
- Expose DM15 / standard Modbus pumps as a Home Assistant `fan` with native 30–100% running-capacity control and `0` for OFF.
- Add a direct capacity setpoint number entity and actual running-capacity sensor.
- Add the documented standard Modbus fault bits and keep register `2004` as a disabled-by-default raw diagnostic until its unit is independently established.
- Preserve iSaver Power 1100 C3/D0 support, RPM control, Home Assistant profiles and the validated persistent OFF value `1`.
- Include the gateway IP address in the integration entry title while keeping the device name clean.
- Restructure the README for multi-protocol Aquagem pump support.
- Add a Contributions & credits section thanking Antonio Garcia for independent DM15 / INVERsilence hardware validation.
- Update the Project/author section to match the TSUN Local project presentation.

## 0.2.7

- Add validated WaveShare RS485/TCP gateway setup guidance in English and French.
- Document the working gateway settings: TCP Server, port 502, 1200 baud, 8N1, Protocol None and Multi-host disabled.
- Add the validated advanced WaveShare timing/settings used by the working iSaver setup.
- Add a real anonymized WaveShare configuration screenshot to the README.
- Remove the README Brand assets and Credits sections.

## 0.2.6

- Make pump preset identifiers language-neutral internally: `max`, `day`, `eco`, `night`, `custom`.
- Add native Home Assistant localization for all preset names.
- Display **Max · Jour · Eco · Nuit · Perso** in French.
- Display **Max · Day · Eco · Night · Custom** in English.
- Keep preset detection based on the actual RPM reported by the iSaver.
- Accept the 0.2.5 French preset labels as compatibility aliases for existing service calls.

## 0.2.5

- Remove the **Estimated power** sensor and its RPM-based interpolation model.
- Remove the obsolete estimated-power entity from the Home Assistant entity registry during upgrade.
- Display **Max**, **Jour**, **Eco**, **Nuit** or **Perso** from the actual RPM reported by the iSaver.

## 0.2.4

- Add an **Estimated power** sensor in watts.
- Build the estimate from physical iSaver panel measurements at 1200, 1550, 2000, 2400 and 2900 rpm.
- Use piecewise-linear interpolation between calibration points instead of presenting a calculated cubic law as measured power.
- Publish a ±10 W estimate tolerance and estimated minimum/maximum attributes.
- Return `0 W` when the reported pump state is OFF.
- Keep the sensor explicitly documented as an estimate; C3 does not expose a validated electrical-power field.

## 0.2.3

- Add a native Home Assistant **Reconfigure** flow for existing Aquagem iSaver entries.
- Allow changing the device name, gateway IP address and TCP port without deleting and recreating the integration.
- Test the new gateway connection before saving.
- Reject an IP/port pair already used by another Aquagem iSaver entry.
- Reload the integration automatically after a successful reconfiguration.

## 0.2.2

- Fix the integration Options screen returning HTTP 500 before rendering.
- Replace custom Voluptuous speed validators in the UI schema with native Home Assistant number selectors.
- Keep 1200–2900 rpm physical limits and 100 rpm speed steps.
- Keep server-side validation for minimum/maximum range and profile speeds.

## 0.2.1

- Replace the pump switch with a Home Assistant `fan` entity.
- Add variable-speed control from 0–100% mapped to a configurable RPM range.
- Add configurable Home Assistant profiles: **Nuit**, **Eco**, **Jour** and **Max**.
- Add integration options for profile RPM values.
- Add configurable minimum and maximum operating speeds.
- Enforce the physical 1200–2900 rpm limits and 100 rpm speed steps.
- Keep direct RPM control through the number entity.
- Remove the obsolete pump switch registry entry during upgrade.
- Keep the polling interval configurable from the same Options screen.

## 0.2.0

- Add local brand icon and logo for Home Assistant/HACS.
- Rename the integration to **Aquagem iSaver** while keeping the existing domain.
- Decode the complete C3 status response in one poll.
- Use the real pump state from register 2002.
- Add the documented register 2001 fault entities.
- Add a raw fault-code diagnostic sensor.
- Validate the full status-frame CRC.
- Keep the physically validated `1` command for persistent OFF.
- Clarify that the panel's stored speed modes are not Modbus presets.
- Add English/French entity names and entity icons.
- Add HACS and hassfest validation workflows.
- Refresh the README and project metadata.

## 0.1.4

- Use value `1` for the persistent iSaver stop command.

## 0.1.3

- Avoid an immediate status read after a write command.

## 0.1.2

- Reassemble fragmented TCP responses.
- Use the Home Assistant-compatible `rpm` unit.

## 0.1.0

- Initial HACS integration.
