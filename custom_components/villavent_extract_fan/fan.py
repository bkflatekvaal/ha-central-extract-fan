"""Fan entity."""
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from .const import CONF_SHOW_OFF_PRESET, DOMAIN, LEVEL_NAMES

async def async_setup_entry(hass, entry, async_add_entities): async_add_entities([VillaventFan(hass.data[DOMAIN][entry.entry_id], entry)])
class VillaventFan(FanEntity, RestoreEntity):
    _attr_has_entity_name = True; _attr_name = None; _attr_speed_count = 3
    def __init__(self, controller, entry): self.controller = controller; self._attr_unique_id = f"{entry.entry_id}_fan"; self._attr_device_info = controller.device_info
    async def async_added_to_hass(self):
        await super().async_added_to_hass(); self.async_on_remove(self.controller.add_update_listener(self.async_write_ha_state))
        previous = await self.async_get_last_state(); manual = boost = None
        if previous:
            preset = previous.attributes.get("preset_mode")
            if preset in LEVEL_NAMES: manual = LEVEL_NAMES.index(preset)
            if raw := previous.attributes.get("boost_until"):
                try: boost = dt_util.parse_datetime(raw)
                except (TypeError, ValueError): pass
        await self.controller.async_restore(manual, boost)
    @property
    def is_on(self): return self.controller.state.effective_level > 0
    @property
    def percentage(self): return (0, 33, 66, 100)[self.controller.state.effective_level]
    @property
    def supported_features(self):
        features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON
        return features | FanEntityFeature.TURN_OFF if self.controller.cfg.get(CONF_SHOW_OFF_PRESET, False) else features
    @property
    def preset_modes(self):
        levels = LEVEL_NAMES if self.controller.cfg.get(CONF_SHOW_OFF_PRESET, False) else LEVEL_NAMES[1:]
        return ["auto", *levels]
    @property
    def preset_mode(self): return "auto" if self.controller.state.manual_level is None else LEVEL_NAMES[self.controller.state.manual_level]
    @property
    def extra_state_attributes(self): return {"boost_until": self.controller.state.boost_until.isoformat() if self.controller.state.boost_until else None}
    async def async_set_preset_mode(self, preset_mode): await self.controller.async_set_manual_level(None if preset_mode == "auto" else LEVEL_NAMES.index(preset_mode))
    async def async_set_percentage(self, percentage): await self.controller.async_set_manual_level(0 if percentage <= 0 else 1 if percentage < 50 else 2 if percentage < 84 else 3)
    async def async_turn_on(self, **kwargs): await self.controller.async_set_manual_level(1)
    async def async_turn_off(self, **kwargs): await self.controller.async_set_manual_level(0)
