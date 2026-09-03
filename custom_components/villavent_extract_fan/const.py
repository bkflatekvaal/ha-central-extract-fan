from __future__ import annotations

DOMAIN = "villavent_extract_fan"
PLATFORMS = ["fan", "sensor", "binary_sensor", "switch", "button", "number"]

CONF_CH1 = "channel_1"
CONF_CH2 = "channel_2"
CONF_HUMIDITY_SENSORS = "humidity_sensors"
CONF_MEDIUM_THRESHOLD = "medium_threshold"
CONF_HIGH_THRESHOLD = "high_threshold"
CONF_HYSTERESIS = "hysteresis"
CONF_SWITCH_DELAY = "switch_delay"
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
DEFAULT_SWITCH_DELAY = 1.0
DEFAULT_BOOST_DURATION = 30
DEFAULT_SILENT_MAX_LEVEL = 2
DEFAULT_RPM_TOLERANCE = 20.0
DEFAULT_RPM_SETTLE_TIME = 15

LEVEL_OFF = 0
LEVEL_LOW = 1
LEVEL_MEDIUM = 2
LEVEL_HIGH = 3

MODE_AUTO = "auto"
MODE_MANUAL = "manual"
MODE_BOOST = "boost"

ATTR_REQUESTED_LEVEL = "requested_level"
ATTR_EFFECTIVE_LEVEL = "effective_level"
ATTR_CONTROL_HUMIDITY = "control_humidity"
ATTR_CONTROL_SOURCE = "control_source"
ATTR_HUMIDITY_SOURCE = "humidity_source"
ATTR_AVAILABLE_HUMIDITY_SENSORS = "available_humidity_sensors"
ATTR_UNAVAILABLE_HUMIDITY_SENSORS = "unavailable_humidity_sensors"
