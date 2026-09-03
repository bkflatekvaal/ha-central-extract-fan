"""Diagnostic sensors."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime
from .const import DOMAIN, LEVEL_NAMES
from .entity import VillaventEntity

DESCRIPTIONS = (
 SensorEntityDescription(key="control_humidity", translation_key="control_humidity", native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.HUMIDITY, state_class=SensorStateClass.MEASUREMENT),
 SensorEntityDescription(key="humidity_source", translation_key="humidity_source", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="requested_level", translation_key="requested_level", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="effective_level", translation_key="effective_level", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="control_source", translation_key="control_source", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="boost_remaining", translation_key="boost_remaining", native_unit_of_measurement=UnitOfTime.SECONDS, entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="expected_rpm", translation_key="expected_rpm", native_unit_of_measurement="rpm", entity_category=EntityCategory.DIAGNOSTIC),
 SensorEntityDescription(key="rpm_deviation", translation_key="rpm_deviation", native_unit_of_measurement="rpm", entity_category=EntityCategory.DIAGNOSTIC),
)
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([VillaventSensor(hass.data[DOMAIN][entry.entry_id], entry, d) for d in DESCRIPTIONS])
class VillaventSensor(VillaventEntity, SensorEntity):
    def __init__(self, controller, entry, description): super().__init__(controller, entry, description.key); self.entity_description = description
    @property
    def native_value(self):
        key = self.entity_description.key
        if key == "boost_remaining": return self.controller.boost_remaining_seconds
        value = getattr(self.controller.state, key)
        return LEVEL_NAMES[value] if key in ("requested_level", "effective_level") else value
