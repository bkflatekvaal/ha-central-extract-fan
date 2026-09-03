"""Constants for Villavent Extract Fan."""
from homeassistant.const import Platform
from .control import LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM, LEVEL_NAMES, LEVEL_OFF

DOMAIN = "villavent_extract_fan"
PLATFORMS = [Platform.FAN, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON, Platform.NUMBER]
CONF_CH1 = "channel_1"
CONF_CH2 = "channel_2"
CONF_HUMIDITY_SENSORS = "humidity_sensors"
CONF_MEDIUM_THRESHOLD = "medium_threshold"
CONF_HIGH_THRESHOLD = "high_threshold"
CONF_HYSTERESIS = "hysteresis"
LEGACY_CONF_SWITCH_DELAY = "switch_delay"
CONF_RELAY_SWITCH_DELAY_MS = "relay_switch_delay_ms"
CONF_SILENT_SCHEDULE = "silent_schedule"
CONF_SILENT_MAX_LEVEL = "silent_max_level"
CONF_SILENT_ALLOW_OFF = "silent_allow_off"
CONF_RPM_SENSOR = "rpm_sensor"
CONF_RPM_LOW = "rpm_low"
CONF_RPM_MEDIUM = "rpm_medium"
CONF_RPM_HIGH = "rpm_high"
CONF_RPM_TOLERANCE = "rpm_tolerance"
CONF_RPM_SETTLE_TIME = "rpm_settle_time"
CONF_INDICATORS_CH1 = "indicators_ch1"
CONF_INDICATORS_CH2 = "indicators_ch2"
CONF_BOOST_DURATION = "boost_duration"
DEFAULT_MEDIUM_THRESHOLD = 60.0
DEFAULT_HIGH_THRESHOLD = 75.0
DEFAULT_HYSTERESIS = 5.0
DEFAULT_RELAY_SWITCH_DELAY_MS = 500
DEFAULT_BOOST_DURATION = 30
DEFAULT_SILENT_MAX_LEVEL = LEVEL_MEDIUM
DEFAULT_RPM_TOLERANCE = 20.0
DEFAULT_RPM_SETTLE_TIME = 15
