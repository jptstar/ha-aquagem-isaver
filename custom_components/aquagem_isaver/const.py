"""Constants for supported Aquagem pump protocols."""

DOMAIN = "aquagem_isaver"
PLATFORMS = ["sensor", "number", "fan", "binary_sensor"]

CONF_SCAN_INTERVAL = "scan_interval"
CONF_MIN_OPERATING_SPEED = "min_operating_speed"
CONF_MAX_OPERATING_SPEED = "max_operating_speed"
CONF_NIGHT_SPEED = "night_speed"
CONF_ECO_SPEED = "eco_speed"
CONF_DAY_SPEED = "day_speed"
CONF_MAX_PRESET_SPEED = "max_preset_speed"
CONF_PROTOCOL = "protocol"
CONF_MODBUS_UNIT = "modbus_unit"
CONF_TRANSPORT = "transport"
CONF_SERIAL_PORT = "serial_port"

TRANSPORT_TCP = "tcp"
TRANSPORT_SERIAL = "serial"
SUPPORTED_TRANSPORTS = (TRANSPORT_TCP, TRANSPORT_SERIAL)

DEFAULT_NAME = "Aquagem Pump"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_OFFLINE_SCAN_INTERVAL = 30

# Protocol identifiers are intentionally model-independent where possible.
# Auto-detection validates protocol signatures; it does not guess a commercial
# model name from a generic Modbus response.
PROTOCOL_ISAVER = "isaver_c3_d0"
PROTOCOL_PUMP_MODBUS = "pump_modbus_03_10"
SUPPORTED_PROTOCOLS = (PROTOCOL_ISAVER, PROTOCOL_PUMP_MODBUS)

# iSaver Power 1100 proprietary C3/D0 profile.
MIN_SPEED = 1200
MAX_SPEED = 2900
SPEED_STEP = 100
OFF_COMMAND = 1
ISAVER_BAUDRATE = 1200

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

ISAVER_DEVICE_ADDRESS = 0xAA
READ_FUNCTION = 0xC3
WRITE_FUNCTION = 0xD0

# Proprietary Aquagem frames validated against a working iSaver Power 1100.
# Reading from 2001 returns:
#   2001 (2 bytes): fault bitfield
#   2002 (1 byte): operating state, bit 0 = pump on
#   2003 (2 bytes): actual pump speed in rpm
READ_STATUS_BODY = bytes((ISAVER_DEVICE_ADDRESS, READ_FUNCTION, 0x07, 0xD1, 0x00, 0x02))
WRITE_SPEED_PREFIX = bytes((ISAVER_DEVICE_ADDRESS, WRITE_FUNCTION, 0x0B, 0xB9))
READ_STATUS_REPLY_LENGTH = 9

# Standard Aquagem pump Modbus profile validated on a real DM15 / INVERsilence.
# Core holding registers 2001..2004 expose fault, state, running capacity and power.
PUMP_MODBUS_READ_FUNCTION = 0x03
PUMP_MODBUS_WRITE_FUNCTION = 0x10
PUMP_MODBUS_STATUS_START = 2001
PUMP_MODBUS_STATUS_COUNT = 4
PUMP_MODBUS_COMMAND_REGISTER = 3001
PUMP_MODBUS_STATUS_REPLY_LENGTH = 13
PUMP_MODBUS_OFF_COMMAND = 0
PUMP_MODBUS_MIN_CAPACITY = 30
PUMP_MODBUS_MAX_CAPACITY = 100
PUMP_MODBUS_CAPACITY_STEP = 5
PUMP_MODBUS_DEFAULT_UNIT = 0xAA
PUMP_MODBUS_UNIT_MIN = 0xA0
PUMP_MODBUS_UNIT_MAX = 0xBF
PUMP_MODBUS_BAUDRATE = 9600

# Modbus RTU requires at least 3.5 character times of silence. At 9600-8-N-1
# that is about 4 ms; use 5 ms to keep direct serial transactions conservative.
PUMP_MODBUS_RTU_GUARD_SECONDS = 0.005

# Aquagem RS485 Modbus V1.5 (for V1.0.0), supplied for DM-family validation.
# These registers are read separately so older/alternate Aquagem register maps
# remain usable even if the extended block is not implemented by the device.
PUMP_MODBUS_EXTENDED_START = 2007
PUMP_MODBUS_EXTENDED_COUNT = 3
PUMP_MODBUS_EXTENDED_REPLY_LENGTH = 11
PUMP_MODBUS_ENERGY_SCALE = 1000
PUMP_MODBUS_V15_MODE_CODES = frozenset((10, 15, 19, 23, 28))
