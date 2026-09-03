from __future__ import annotations
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([BoostDurationNumber(hass, hass.data[DOMAIN][entry.entry_id], entry)])

class BoostDurationNumber(NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    def __init__(self,hass,c,e): self.hass=hass; self.controller=c; self.entry=e; self._attr_unique_id=f"{e.entry_id}_boost_duration"; self._attr_name="Boost duration"
    @property
    def native_value(self): return int(self.controller.cfg.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION))
    async def async_set_native_value(self, value: float) -> None:
        opts = dict(self.entry.options)
        opts[CONF_BOOST_DURATION] = int(value)
        self.hass.config_entries.async_update_entry(self.entry, options=opts)
