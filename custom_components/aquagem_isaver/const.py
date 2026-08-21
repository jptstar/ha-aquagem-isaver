"""Constants for Aquagem iSaver."""

DOMAIN = "aquagem_isaver"
PLATFORMS = ["sensor", "number", "switch", "binary_sensor"]

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_NAME = "iSaver Power 1100"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 5

MIN_SPEED = 1200
MAX_SPEED = 2900
OFF_COMMAND = 1

DEVICE_ADDRESS = 0xAA
READ_FUNCTION = 0xC3
WRITE_FUNCTION = 0xD0

# Proprietary Aquagem frames validated against a working iSaver Power 1100.
# Reading from 2001 returns:
#   2001 (2 bytes): fault bitfield
#   2002 (1 byte): operating state, bit 0 = pump on
#   2003 (2 bytes): actual pump speed in rpm
READ_STATUS_BODY = bytes((DEVICE_ADDRESS, READ_FUNCTION, 0x07, 0xD1, 0x00, 0x02))
WRITE_SPEED_PREFIX = bytes((DEVICE_ADDRESS, WRITE_FUNCTION, 0x0B, 0xB9))
READ_STATUS_REPLY_LENGTH = 9
