"""Diagnostic sensors."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime
from homeassistant.util import dt as dt_util
from .const import (
    CONF_HIGH_THRESHOLD,
    CONF_HYSTERESIS,
    CONF_MEDIUM_THRESHOLD,
    CONF_SILENT_SCHEDULE,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_HYSTERESIS,
    DEFAULT_MEDIUM_THRESHOLD,
    DOMAIN,
    LEVEL_NAMES,
)
from .entity import CentralExtractFanEntity

DESCRIPTIONS = (
 SensorEntityDescription(key="control_humidity", translation_key="control_humidity", native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.HUMIDITY, state_class=SensorStateClass.MEASUREMENT),
 SensorEntityDescription(key="humidity_source", translation_key="humidity_source", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="requested_level", translation_key="requested_level", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="effective_level", translation_key="effective_level", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="control_source", translation_key="control_source", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="boost_remaining", translation_key="boost_remaining", native_unit_of_measurement=UnitOfTime.SECONDS, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="expected_rpm", translation_key="expected_rpm", native_unit_of_measurement="rpm", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="rpm_deviation", translation_key="rpm_deviation", native_unit_of_measurement="rpm", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="medium_threshold", translation_key="medium_threshold", native_unit_of_measurement=PERCENTAGE, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="high_threshold", translation_key="high_threshold", native_unit_of_measurement=PERCENTAGE, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="hysteresis", translation_key="hysteresis", native_unit_of_measurement=PERCENTAGE, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="next_silent_change", translation_key="next_silent_change", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
)
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([CentralExtractFanSensor(hass.data[DOMAIN][entry.entry_id], entry, d) for d in DESCRIPTIONS])
class CentralExtractFanSensor(CentralExtractFanEntity, SensorEntity):
    def __init__(self, controller, entry, description): super().__init__(controller, entry, description.key); self.entity_description = description
    @property
    def native_value(self):
        key = self.entity_description.key
        if key == "boost_remaining": return self.controller.boost_remaining_seconds
        if key == "rpm_deviation":
            value = self.controller.state.rpm_deviation
            return round(value) if value is not None else None
        if key in (CONF_MEDIUM_THRESHOLD, CONF_HIGH_THRESHOLD, CONF_HYSTERESIS):
            defaults = {CONF_MEDIUM_THRESHOLD: DEFAULT_MEDIUM_THRESHOLD, CONF_HIGH_THRESHOLD: DEFAULT_HIGH_THRESHOLD, CONF_HYSTERESIS: DEFAULT_HYSTERESIS}
            return self.controller.cfg.get(key, defaults[key])
        if key == "next_silent_change":
            schedule = self.controller.cfg.get(CONF_SILENT_SCHEDULE)
            state = self.controller.hass.states.get(schedule) if schedule else None
            value = state.attributes.get("next_event") if state else None
            return dt_util.parse_datetime(value) if isinstance(value, str) else value
        value = getattr(self.controller.state, key)
        return LEVEL_NAMES[value] if key in ("requested_level", "effective_level") else value
