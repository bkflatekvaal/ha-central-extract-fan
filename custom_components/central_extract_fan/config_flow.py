"""Configuration flow."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import *  # noqa: F403

SWITCH = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))
SWITCHES = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch", multiple=True))
HUMIDITY = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.HUMIDITY, multiple=True))
SCHEDULE = selector.EntitySelector(selector.EntitySelectorConfig(domain="schedule"))
SENSOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3
    async def async_step_user(self, user_input=None):
        if user_input:
            if user_input[CONF_CH1] == user_input[CONF_CH2]: return self.async_show_form(step_id="user", data_schema=self._schema(user_input), errors={"base": "channels_must_differ"})
            await self.async_set_unique_id(f"{user_input[CONF_CH1]}_{user_input[CONF_CH2]}"); self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Central Extract Fan", data=user_input)
        return self.async_show_form(step_id="user", data_schema=self._schema({}))
    def _schema(self, c):
        return vol.Schema({vol.Required(CONF_CH1): SWITCH, vol.Required(CONF_CH2): SWITCH, vol.Required(CONF_HUMIDITY_SENSORS): HUMIDITY})
    @staticmethod
    @callback
    def async_get_options_flow(config_entry): return OptionsFlow()

class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        c = user_input or {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input:
            if user_input[CONF_CH1] == user_input[CONF_CH2]: errors["base"] = "channels_must_differ"
            elif not user_input.get(CONF_HUMIDITY_SENSORS): errors["base"] = "humidity_required"
            elif user_input[CONF_HIGH_THRESHOLD] <= user_input[CONF_MEDIUM_THRESHOLD]: errors["base"] = "high_must_exceed_medium"
            else: return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._schema(c), errors=errors)
    def _schema(self, c):
        optional = lambda key: {"default": c[key]} if c.get(key) not in (None, "") else {}
        return vol.Schema({
            vol.Required(CONF_CH1, default=c.get(CONF_CH1)): SWITCH,
            vol.Required(CONF_CH2, default=c.get(CONF_CH2)): SWITCH,
            vol.Required(CONF_HUMIDITY_SENSORS, default=c.get(CONF_HUMIDITY_SENSORS, [])): HUMIDITY,
            vol.Required(CONF_MEDIUM_THRESHOLD, default=c.get(CONF_MEDIUM_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(CONF_HIGH_THRESHOLD, default=c.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(CONF_HYSTERESIS, default=c.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
            vol.Required(CONF_BOOST_DURATION, default=c.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
            vol.Required(CONF_RELAY_SWITCH_DELAY_MS, default=c.get(CONF_RELAY_SWITCH_DELAY_MS, DEFAULT_RELAY_SWITCH_DELAY_MS)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=5000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="ms")),
            vol.Optional(CONF_SILENT_SCHEDULE, **optional(CONF_SILENT_SCHEDULE)): SCHEDULE,
            vol.Required(CONF_SILENT_MAX_LEVEL, default=str(c.get(CONF_SILENT_MAX_LEVEL, DEFAULT_SILENT_MAX_LEVEL))): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": "0", "label": "Off"}, {"value": "1", "label": "Low"}, {"value": "2", "label": "Medium"}])),
            vol.Required(CONF_SHOW_OFF_PRESET, default=c.get(CONF_SHOW_OFF_PRESET, False)): bool,
            vol.Optional(CONF_RPM_SENSOR, **optional(CONF_RPM_SENSOR)): SENSOR,
            vol.Optional(CONF_RPM_LOW, **optional(CONF_RPM_LOW)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(CONF_RPM_MEDIUM, **optional(CONF_RPM_MEDIUM)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(CONF_RPM_HIGH, **optional(CONF_RPM_HIGH)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_RPM_TOLERANCE, default=c.get(CONF_RPM_TOLERANCE, DEFAULT_RPM_TOLERANCE)): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
            vol.Required(CONF_RPM_SETTLE_TIME, default=c.get(CONF_RPM_SETTLE_TIME, DEFAULT_RPM_SETTLE_TIME)): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
            vol.Optional(CONF_INDICATORS_CH1, default=c.get(CONF_INDICATORS_CH1, [])): SWITCHES,
            vol.Optional(CONF_INDICATORS_CH2, default=c.get(CONF_INDICATORS_CH2, [])): SWITCHES,
        })
