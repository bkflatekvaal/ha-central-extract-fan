"""Boost buttons."""
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from .const import DOMAIN
from .entity import CentralExtractFanEntity
DESCRIPTIONS = (ButtonEntityDescription(key="start_boost", translation_key="start_boost", icon="mdi:fan-plus"), ButtonEntityDescription(key="cancel_boost", translation_key="cancel_boost", icon="mdi:fan-remove"))
async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([BoostButton(hass.data[DOMAIN][entry.entry_id], entry, d) for d in DESCRIPTIONS])
class BoostButton(CentralExtractFanEntity, ButtonEntity):
    def __init__(self, controller, entry, description): super().__init__(controller, entry, description.key); self.entity_description = description
    async def async_press(self): await (self.controller.async_start_boost() if self.entity_description.key == "start_boost" else self.controller.async_cancel_boost())
