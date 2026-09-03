from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HumidityFault(c, entry), FanFault(c, entry), BoostActive(c, entry), SilentHoursActive(c, entry)])

class Base(BinarySensorEntity):
    def __init__(self,c,e,key,name): self.controller=c; self._attr_unique_id=f"{e.entry_id}_{key}"; self._attr_name=name
    async def async_added_to_hass(self): self.async_on_remove(self.controller.add_update_listener(self._u))
    @callback
    def _u(self): self.async_write_ha_state()

class HumidityFault(Base):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    def __init__(self,c,e): super().__init__(c,e,"humidity_fault","Humidity sensor fault")
    @property
    def is_on(self): return self.controller.state.humidity_fault

class FanFault(Base):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    def __init__(self,c,e): super().__init__(c,e,"fan_fault","Fan fault")
    @property
    def is_on(self): return self.controller.state.fan_fault

class BoostActive(Base):
    def __init__(self,c,e): super().__init__(c,e,"boost_active","Boost active")
    @property
    def is_on(self): return self.controller.boost_remaining_seconds > 0

class SilentHoursActive(Base):
    def __init__(self,c,e): super().__init__(c,e,"silent_hours_active","Silent hours active")
    @property
    def is_on(self): return self.controller._silent_active()
