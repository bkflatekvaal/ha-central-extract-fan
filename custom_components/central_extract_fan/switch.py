"""Automatic control switch."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import CentralExtractFanEntity
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([AutomaticSwitch(hass.data[DOMAIN][entry.entry_id], entry)])
class AutomaticSwitch(CentralExtractFanEntity, SwitchEntity):
    _attr_translation_key = "automatic_control"; _attr_entity_category = EntityCategory.CONFIG; _attr_icon = "mdi:fan-auto"
    def __init__(self, controller, entry): super().__init__(controller, entry, "automatic_control")
    @property
    def is_on(self): return self.controller.state.manual_level is None
    async def async_turn_on(self, **kwargs): await self.controller.async_set_manual_level(None)
    async def async_turn_off(self, **kwargs): await self.controller.async_set_manual_level(self.controller.state.effective_level)
