# Changelog

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
