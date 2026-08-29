"""Constants for Aquagem iSaver."""

DOMAIN = "aquagem_isaver"
PLATFORMS = ["sensor", "number", "fan", "binary_sensor"]

CONF_SCAN_INTERVAL = "scan_interval"
CONF_MIN_OPERATING_SPEED = "min_operating_speed"
CONF_MAX_OPERATING_SPEED = "max_operating_speed"
CONF_NIGHT_SPEED = "night_speed"
CONF_ECO_SPEED = "eco_speed"
CONF_DAY_SPEED = "day_speed"
CONF_MAX_PRESET_SPEED = "max_preset_speed"

DEFAULT_NAME = "iSaver Power 1100"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 5

# Physical protocol limits. Options may narrow this range, never extend it.
MIN_SPEED = 1200
MAX_SPEED = 2900
SPEED_STEP = 100
OFF_COMMAND = 1

DEFAULT_MIN_OPERATING_SPEED = 1200
DEFAULT_MAX_OPERATING_SPEED = 2900
DEFAULT_NIGHT_SPEED = 1200
DEFAULT_ECO_SPEED = 2000
DEFAULT_DAY_SPEED = 2400
DEFAULT_MAX_PRESET_SPEED = 2900

# Language-neutral internal preset identifiers. Display names are translated by HA.
PRESET_MAX = "max"
PRESET_DAY = "day"
PRESET_ECO = "eco"
PRESET_NIGHT = "night"
PRESET_CUSTOM = "custom"

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
