"""Boost duration setting."""
from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory, UnitOfTime
from .const import CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION, DOMAIN
from .entity import VillaventEntity
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([BoostDuration(hass, hass.data[DOMAIN][entry.entry_id], entry)])
class BoostDuration(VillaventEntity, NumberEntity):
    _attr_translation_key = "boost_duration"; _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1; _attr_native_max_value = 240; _attr_native_step = 1; _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    def __init__(self, hass, controller, entry): super().__init__(controller, entry, "boost_duration"); self.hass, self.entry = hass, entry
    @property
    def native_value(self): return int(self.controller.cfg.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION))
    async def async_set_native_value(self, value): self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, CONF_BOOST_DURATION: int(value)})
