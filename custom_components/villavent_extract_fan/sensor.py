from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ControlHumiditySensor(c, entry), RequestedLevelSensor(c, entry), EffectiveLevelSensor(c, entry),
        ControlSourceSensor(c, entry), HumiditySourceSensor(c, entry), BoostRemainingSensor(c, entry),
    ])


class BaseSensor(SensorEntity):
    def __init__(self, c, entry, key, name):
        self.controller = c
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_update_listener(self._update))

    @callback
    def _update(self): self.async_write_ha_state()

class ControlHumiditySensor(BaseSensor):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = "humidity"
    def __init__(self,c,e): super().__init__(c,e,"control_humidity","Control humidity")
    @property
    def native_value(self): return self.controller.state.control_humidity

class RequestedLevelSensor(BaseSensor):
    def __init__(self,c,e): super().__init__(c,e,"requested_level","Requested level")
    @property
    def native_value(self): return self.controller.state.requested_level

class EffectiveLevelSensor(BaseSensor):
    def __init__(self,c,e): super().__init__(c,e,"effective_level","Effective level")
    @property
    def native_value(self): return self.controller.state.effective_level

class ControlSourceSensor(BaseSensor):
    def __init__(self,c,e): super().__init__(c,e,"control_source","Control source")
    @property
    def native_value(self): return self.controller.state.control_source

class HumiditySourceSensor(BaseSensor):
    def __init__(self,c,e): super().__init__(c,e,"humidity_source","Humidity source")
    @property
    def native_value(self): return self.controller.state.humidity_source

class BoostRemainingSensor(BaseSensor):
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    def __init__(self,c,e): super().__init__(c,e,"boost_remaining","Boost remaining")
    @property
    def native_value(self): return self.controller.boost_remaining_seconds
