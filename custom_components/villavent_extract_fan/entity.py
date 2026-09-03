"""Shared entity base."""
from homeassistant.core import callback
class VillaventEntity:
    _attr_has_entity_name = True
    def __init__(self, controller, entry, key): self.controller = controller; self._attr_unique_id = f"{entry.entry_id}_{key}"; self._attr_device_info = controller.device_info
    async def async_added_to_hass(self): self.async_on_remove(self.controller.add_update_listener(self._handle_update))
    @callback
    def _handle_update(self): self.async_write_ha_state()
