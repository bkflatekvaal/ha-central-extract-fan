from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_RELAY_SWITCH_DELAY_MS,
    CONF_SHOW_OFF_PRESET,
    DOMAIN,
    LEGACY_CONF_SILENT_ALLOW_OFF,
    LEGACY_CONF_SWITCH_DELAY,
    PLATFORMS,
    LEVEL_NAMES,
)
from .coordinator import CentralExtractFanController

START_BOOST_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids, vol.Optional("level"): vol.In(LEVEL_NAMES[1:]), vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=240))})
CANCEL_BOOST_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register integration actions."""
    hass.data.setdefault(DOMAIN, {})
    async def controllers_for(call: ServiceCall):
        targets = set(call.data.get(ATTR_ENTITY_ID, []))
        controllers = list(hass.data[DOMAIN].values())
        return [controller for controller in controllers if not targets or getattr(controller, "fan_entity_id", None) in targets]
    async def start_boost(call: ServiceCall):
        level = LEVEL_NAMES.index(call.data["level"]) if "level" in call.data else None
        for controller in await controllers_for(call): await controller.async_start_boost(level, call.data.get("duration"))
    async def cancel_boost(call: ServiceCall):
        for controller in await controllers_for(call): await controller.async_cancel_boost()
    hass.services.async_register(DOMAIN, "start_boost", start_boost, schema=START_BOOST_SCHEMA)
    hass.services.async_register(DOMAIN, "cancel_boost", cancel_boost, schema=CANCEL_BOOST_SCHEMA)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the legacy seconds-based relay delay to milliseconds."""
    if entry.version < 3:
        data = dict(entry.data)
        options = dict(entry.options)
        if entry.version < 2:
            legacy_delay = options.pop(LEGACY_CONF_SWITCH_DELAY, data.pop(LEGACY_CONF_SWITCH_DELAY, None))
            if legacy_delay is not None and CONF_RELAY_SWITCH_DELAY_MS not in options:
                options[CONF_RELAY_SWITCH_DELAY_MS] = min(5000, max(0, round(float(legacy_delay) * 1000)))
        legacy_allow_off = options.pop(LEGACY_CONF_SILENT_ALLOW_OFF, data.pop(LEGACY_CONF_SILENT_ALLOW_OFF, None))
        if legacy_allow_off is not None and CONF_SHOW_OFF_PRESET not in options:
            options[CONF_SHOW_OFF_PRESET] = bool(legacy_allow_off)
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=3)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = CentralExtractFanController(hass, entry)
    await controller.async_initialize()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_shutdown()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
