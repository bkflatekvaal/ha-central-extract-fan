from __future__ import annotations
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([AutomaticControlSwitch(hass.data[DOMAIN][entry.entry_id], entry)])

class AutomaticControlSwitch(SwitchEntity):
    def __init__(self,c,e): self.controller=c; self._attr_unique_id=f"{e.entry_id}_automatic_control"; self._attr_name="Automatic control"
    async def async_added_to_hass(self): self.async_on_remove(self.controller.add_update_listener(self._u))
    @callback
    def _u(self): self.async_write_ha_state()
    @property
    def is_on(self): return self.controller.state.manual_level is None
    async def async_turn_on(self, **kwargs): await self.controller.async_set_manual_level(None)
    async def async_turn_off(self, **kwargs): await self.controller.async_set_manual_level(self.controller.state.effective_level)
