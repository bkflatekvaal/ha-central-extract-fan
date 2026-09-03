from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from .const import *

HUMIDITY_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="humidity", multiple=True))
SWITCH_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))
MULTI_SWITCH_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch", multiple=True))
SCHEDULE_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="schedule"))
SENSOR_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input[CONF_HIGH_THRESHOLD] <= user_input[CONF_MEDIUM_THRESHOLD]:
                errors["base"] = "high_must_exceed_medium"
            else:
                title = user_input.pop(CONF_NAME)
                return self.async_create_entry(title=title, data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_NAME, default="Villavent"): str,
            vol.Required(CONF_CH1): SWITCH_SELECTOR,
            vol.Required(CONF_CH2): SWITCH_SELECTOR,
            vol.Required(CONF_HUMIDITY_SENSORS): HUMIDITY_SELECTOR,
            vol.Required(CONF_MEDIUM_THRESHOLD, default=DEFAULT_MEDIUM_THRESHOLD): vol.Coerce(float),
            vol.Required(CONF_HIGH_THRESHOLD, default=DEFAULT_HIGH_THRESHOLD): vol.Coerce(float),
            vol.Required(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
            vol.Optional(CONF_SWITCH_DELAY, default=DEFAULT_SWITCH_DELAY): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry): self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        c = {**self.entry.data, **self.entry.options}
        schema = vol.Schema({
            vol.Required(CONF_HUMIDITY_SENSORS, default=c.get(CONF_HUMIDITY_SENSORS, [])): HUMIDITY_SELECTOR,
            vol.Required(CONF_MEDIUM_THRESHOLD, default=c.get(CONF_MEDIUM_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD)): vol.Coerce(float),
            vol.Required(CONF_HIGH_THRESHOLD, default=c.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)): vol.Coerce(float),
            vol.Required(CONF_HYSTERESIS, default=c.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
            vol.Optional(CONF_BOOST_DURATION, default=c.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
            vol.Optional(CONF_SILENT_SCHEDULE, default=c.get(CONF_SILENT_SCHEDULE)): SCHEDULE_SELECTOR,
            vol.Optional(CONF_SILENT_MAX_LEVEL, default=c.get(CONF_SILENT_MAX_LEVEL, DEFAULT_SILENT_MAX_LEVEL)): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value":"0","label":"Off"},{"value":"1","label":"Low"},{"value":"2","label":"Medium"}], mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_SILENT_ALLOW_OFF, default=c.get(CONF_SILENT_ALLOW_OFF, False)): bool,
            vol.Optional(CONF_RPM_SENSOR, default=c.get(CONF_RPM_SENSOR)): SENSOR_SELECTOR,
            vol.Optional(CONF_RPM_LOW, default=c.get(CONF_RPM_LOW)): vol.Coerce(float),
            vol.Optional(CONF_RPM_MEDIUM, default=c.get(CONF_RPM_MEDIUM)): vol.Coerce(float),
            vol.Optional(CONF_RPM_HIGH, default=c.get(CONF_RPM_HIGH)): vol.Coerce(float),
            vol.Optional(CONF_RPM_TOLERANCE, default=c.get(CONF_RPM_TOLERANCE, DEFAULT_RPM_TOLERANCE)): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
            vol.Optional(CONF_RPM_SETTLE_TIME, default=c.get(CONF_RPM_SETTLE_TIME, DEFAULT_RPM_SETTLE_TIME)): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
            vol.Optional(CONF_INDICATORS_CH1, default=c.get(CONF_INDICATORS_CH1, [])): MULTI_SWITCH_SELECTOR,
            vol.Optional(CONF_INDICATORS_CH2, default=c.get(CONF_INDICATORS_CH2, [])): MULTI_SWITCH_SELECTOR,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
