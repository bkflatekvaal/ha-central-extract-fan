from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM, LEVEL_OFF

PRESETS = {LEVEL_OFF: "off", LEVEL_LOW: "low", LEVEL_MEDIUM: "medium", LEVEL_HIGH: "high"}
REV_PRESETS = {v: k for k, v in PRESETS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([VillaventFan(hass.data[DOMAIN][entry.entry_id], entry)])


class VillaventFan(FanEntity):
    _attr_supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_preset_modes = list(REV_PRESETS)
    _attr_speed_count = 3

    def __init__(self, controller, entry) -> None:
        self.controller = controller
        self._attr_name = entry.title or "Villavent"
        self._attr_unique_id = f"{entry.entry_id}_fan"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.controller.add_update_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self.controller.state.effective_level > LEVEL_OFF

    @property
    def percentage(self):
        return {LEVEL_OFF: 0, LEVEL_LOW: 33, LEVEL_MEDIUM: 66, LEVEL_HIGH: 100}[self.controller.state.effective_level]

    @property
    def preset_mode(self):
        if self.controller.state.manual_level is None:
            return "auto"
        return PRESETS[self.controller.state.manual_level]

    @property
    def preset_modes(self):
        return ["auto", "off", "low", "medium", "high"]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == "auto":
            await self.controller.async_set_manual_level(None)
        else:
            await self.controller.async_set_manual_level(REV_PRESETS[preset_mode])

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            level = LEVEL_OFF
        elif percentage < 50:
            level = LEVEL_LOW
        elif percentage < 84:
            level = LEVEL_MEDIUM
        else:
            level = LEVEL_HIGH
        await self.controller.async_set_manual_level(level)

    async def async_turn_on(self, **kwargs) -> None:
        await self.controller.async_set_manual_level(LEVEL_LOW)

    async def async_turn_off(self, **kwargs) -> None:
        await self.controller.async_set_manual_level(LEVEL_OFF)
