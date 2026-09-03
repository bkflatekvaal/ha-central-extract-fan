from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_RELAY_SWITCH_DELAY_MS,
    CONF_SHOW_OFF_PRESET,
    DOMAIN,
    LEGACY_CONF_SILENT_ALLOW_OFF,
    LEGACY_CONF_SWITCH_DELAY,
    PLATFORMS,
)
from .coordinator import CentralExtractFanController


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
