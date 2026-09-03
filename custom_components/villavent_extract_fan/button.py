from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BoostButton(c, entry), CancelBoostButton(c, entry)])

class BoostButton(ButtonEntity):
    def __init__(self,c,e): self.controller=c; self._attr_unique_id=f"{e.entry_id}_boost"; self._attr_name="Start boost"
    async def async_press(self): await self.controller.async_start_boost()

class CancelBoostButton(ButtonEntity):
    def __init__(self,c,e): self.controller=c; self._attr_unique_id=f"{e.entry_id}_cancel_boost"; self._attr_name="Cancel boost"
    async def async_press(self): await self.controller.async_cancel_boost()
