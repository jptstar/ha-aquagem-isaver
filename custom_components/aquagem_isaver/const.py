"""Constants for Aquagem iSaver Power."""

DOMAIN = "aquagem_isaver"
PLATFORMS = ["sensor", "number", "switch", "binary_sensor"]

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_NAME = "Aquagem iSaver Power 1100"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 10
MIN_SPEED = 1200
MAX_SPEED = 2900

# Proprietary frames found in the Aquagem/RS485-to-TCP Node-RED flow.
READ_SPEED_BODY = bytes((0xAA, 0xC3, 0x07, 0xD1, 0x00, 0x02))
WRITE_SPEED_PREFIX = bytes((0xAA, 0xD0, 0x0B, 0xB9))
