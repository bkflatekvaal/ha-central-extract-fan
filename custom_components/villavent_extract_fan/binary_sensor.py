"""Status and fault sensors."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import VillaventEntity
DESCRIPTIONS = (
 BinarySensorEntityDescription(key="humidity_fault", translation_key="humidity_fault", device_class=BinarySensorDeviceClass.PROBLEM, entity_category=EntityCategory.DIAGNOSTIC),
 BinarySensorEntityDescription(key="fan_fault", translation_key="fan_fault", device_class=BinarySensorDeviceClass.PROBLEM, entity_category=EntityCategory.DIAGNOSTIC),
 BinarySensorEntityDescription(key="boost_active", translation_key="boost_active"),
 BinarySensorEntityDescription(key="silent_active", translation_key="silent_active"),
)
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([StatusSensor(hass.data[DOMAIN][entry.entry_id], entry, d) for d in DESCRIPTIONS])
class StatusSensor(VillaventEntity, BinarySensorEntity):
    def __init__(self, controller, entry, description): super().__init__(controller, entry, description.key); self.entity_description = description
    @property
    def is_on(self):
        return {"humidity_fault": self.controller.state.humidity_fault, "fan_fault": self.controller.state.fan_fault, "boost_active": self.controller.boost_remaining_seconds > 0, "silent_active": self.controller._silent_active()}[self.entity_description.key]
