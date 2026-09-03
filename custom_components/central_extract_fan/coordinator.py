"""Central controller for all regulation and hardware access."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util
from .const import *  # noqa: F403
from .control import channels_for_level, effective_level, highest_valid_humidity, hysteresis_level, indicator_needs_update, level_from_channels, relay_transition

@dataclass
class ControllerState:
    requested_level: int = LEVEL_LOW
    effective_level: int = LEVEL_LOW
    control_humidity: float | None = None
    humidity_source: str | None = None
    control_source: str = "humidity"
    manual_level: int | None = None
    boost_until: datetime | None = None
    boost_level: int | None = None
    humidity_fault: bool = False
    fan_fault: bool = False
    expected_rpm: float | None = None
    rpm_deviation: float | None = None

class CentralExtractFanController:
    def __init__(self, hass, entry):
        self.hass, self.entry, self.state = hass, entry, ControllerState()
        self._unsubs, self._callbacks = [], set()
        self._boost_cancel = self._settle_cancel = None
        self._last_output_change, self._lock = dt_util.utcnow(), asyncio.Lock()
    @property
    def cfg(self): return {**self.entry.data, **self.entry.options}
    @property
    def device_info(self): return {"identifiers": {(DOMAIN, self.entry.entry_id)}, "name": self.entry.title, "manufacturer": "Villavent / Flexit / Generic", "model": "Three-speed extract fan controller"}
    def add_update_listener(self, cb):
        self._callbacks.add(cb); return lambda: self._callbacks.discard(cb)
    @callback
    def _notify(self):
        for cb in tuple(self._callbacks): cb()

    async def async_initialize(self):
        physical = level_from_channels(self.hass.states.is_state(self.cfg[CONF_CH1], STATE_ON), self.hass.states.is_state(self.cfg[CONF_CH2], STATE_ON))
        self.state.effective_level, self.state.requested_level = physical, max(LEVEL_LOW, physical)
        indicators = self.cfg.get(CONF_INDICATORS_CH1, []) + self.cfg.get(CONF_INDICATORS_CH2, [])
        inputs = list(self.cfg.get(CONF_HUMIDITY_SENSORS, [])) + [self.cfg[k] for k in (CONF_SILENT_SCHEDULE, CONF_RPM_SENSOR) if self.cfg.get(k)] + indicators
        if inputs: self._unsubs.append(async_track_state_change_event(self.hass, inputs, self._state_changed))
        self._unsubs.append(async_track_time_interval(self.hass, self._minute_tick, timedelta(minutes=1)))
        if self.cfg.get(CONF_RPM_SENSOR): self._schedule_settle()
        await self._sync_indicators(*channels_for_level(physical))
        await self.async_recalculate(False)
    async def async_restore(self, manual, boost_until, boost_level=None):
        self.state.manual_level = manual
        if boost_until and boost_until > dt_util.utcnow():
            self.state.boost_until = boost_until
            self.state.boost_level = boost_level if boost_level in (LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH) else LEVEL_HIGH
            self._schedule_boost()
        await self.async_recalculate()
    async def async_shutdown(self):
        for unsub in self._unsubs: unsub()
        for cancel in (self._boost_cancel, self._settle_cancel):
            if cancel: cancel()
    @callback
    def _state_changed(self, event): self.hass.async_create_task(self._handle_state_change(event))
    async def _handle_state_change(self, event):
        entity_id = event.data["entity_id"]
        if entity_id in self.cfg.get(CONF_INDICATORS_CH1, []):
            await self._sync_indicator(entity_id, channels_for_level(self.state.effective_level)[0])
            return
        if entity_id in self.cfg.get(CONF_INDICATORS_CH2, []):
            await self._sync_indicator(entity_id, channels_for_level(self.state.effective_level)[1])
            return
        await self.async_recalculate()
    @callback
    def _minute_tick(self, _now):
        if self._boost_active(): self._notify()
    def _read_humidity(self):
        values = {}
        for entity_id in self.cfg.get(CONF_HUMIDITY_SENSORS, []):
            state = self.hass.states.get(entity_id)
            if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN): continue
            values[entity_id] = state.state
        return highest_valid_humidity(values)
    def _silent_active(self):
        entity_id = self.cfg.get(CONF_SILENT_SCHEDULE)
        return bool(entity_id and self.hass.states.is_state(entity_id, STATE_ON))
    def _boost_active(self): return bool(self.state.boost_until and self.state.boost_until > dt_util.utcnow())

    async def async_recalculate(self, apply_output=True):
        humidity, source = self._read_humidity()
        self.state.control_humidity, self.state.humidity_source, self.state.humidity_fault = humidity, source, humidity is None
        self.state.requested_level = hysteresis_level(humidity, self.state.requested_level, float(self.cfg.get(CONF_MEDIUM_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD)), float(self.cfg.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)), float(self.cfg.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)))
        silent_max = int(self.cfg.get(CONF_SILENT_MAX_LEVEL, DEFAULT_SILENT_MAX_LEVEL))
        active_boost_level = self.state.boost_level if self._boost_active() else None
        level, source_name = effective_level(self.state.requested_level, self.state.manual_level, active_boost_level, self._silent_active(), silent_max)
        self.state.effective_level = level
        self.state.control_source = "fallback" if self.state.humidity_fault and source_name == "humidity" else source_name
        if apply_output and not self._outputs_match(level): await self._apply_level(level)
        self._check_rpm(); self._notify()
    def _outputs_match(self, level):
        target = channels_for_level(level)
        return all(self.hass.states.is_state(self.cfg[key], STATE_ON) == target[i] for i, key in enumerate((CONF_CH1, CONF_CH2)))
    async def _apply_level(self, level):
        async with self._lock:
            target = channels_for_level(level)
            current = tuple(self.hass.states.is_state(self.cfg[k], STATE_ON) for k in (CONF_CH1, CONF_CH2))
            changes = relay_transition(current, target)
            for pos, (i, turn_on) in enumerate(changes):
                await self._set_switch(self.cfg[(CONF_CH1, CONF_CH2)[i]], turn_on)
                break_before_make = len(changes) == 2 and changes[0][1] is False and changes[1][1] is True
                if pos == 0 and break_before_make:
                    delay_ms = int(self.cfg.get(CONF_RELAY_SWITCH_DELAY_MS, DEFAULT_RELAY_SWITCH_DELAY_MS))
                    if delay_ms: await asyncio.sleep(delay_ms / 1000)
            if changes: self._last_output_change = dt_util.utcnow(); self._schedule_settle()
            await self._sync_indicators(*target)
    async def _sync_indicators(self, ch1, ch2):
        for entity_id in self.cfg.get(CONF_INDICATORS_CH1, []): await self._sync_indicator(entity_id, ch1)
        for entity_id in self.cfg.get(CONF_INDICATORS_CH2, []): await self._sync_indicator(entity_id, ch2)
    async def _sync_indicator(self, entity_id, turn_on):
        state = self.hass.states.get(entity_id)
        if indicator_needs_update(state.state if state else None, turn_on): await self._set_switch(entity_id, turn_on)
    async def _set_switch(self, entity_id, turn_on): await self.hass.services.async_call("switch", "turn_on" if turn_on else "turn_off", {"entity_id": entity_id}, blocking=True)
    async def async_set_manual_level(self, level): self.state.manual_level = level; await self.async_recalculate()
    async def async_start_boost(self, level=None, duration=None):
        self.state.boost_level = level if level in (LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH) else LEVEL_HIGH
        minutes = int(duration if duration is not None else self.cfg.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION))
        self.state.boost_until = dt_util.utcnow() + timedelta(minutes=minutes); self._schedule_boost(); await self.async_recalculate()
    def _schedule_boost(self):
        if self._boost_cancel: self._boost_cancel()
        self._boost_cancel = async_call_later(self.hass, self.boost_remaining_seconds, self._boost_finished)
    async def async_cancel_boost(self):
        if self._boost_cancel: self._boost_cancel()
        self._boost_cancel, self.state.boost_until, self.state.boost_level = None, None, None; await self.async_recalculate()
    async def async_toggle_boost(self):
        if self._boost_active(): await self.async_cancel_boost()
        else: await self.async_start_boost()
    async def _boost_finished(self, _now): self._boost_cancel, self.state.boost_until, self.state.boost_level = None, None, None; await self.async_recalculate()
    def _schedule_settle(self):
        if self._settle_cancel: self._settle_cancel()
        self._settle_cancel = async_call_later(self.hass, int(self.cfg.get(CONF_RPM_SETTLE_TIME, DEFAULT_RPM_SETTLE_TIME)), self._settle_finished)
    async def _settle_finished(self, _now): self._settle_cancel = None; self._check_rpm(); self._notify()
    def _check_rpm(self):
        self.state.expected_rpm = self.state.rpm_deviation = None
        rpm_entity = self.cfg.get(CONF_RPM_SENSOR)
        if not rpm_entity: self.state.fan_fault = False; return
        expected = {LEVEL_OFF: 0, LEVEL_LOW: self.cfg.get(CONF_RPM_LOW), LEVEL_MEDIUM: self.cfg.get(CONF_RPM_MEDIUM), LEVEL_HIGH: self.cfg.get(CONF_RPM_HIGH)}[self.state.effective_level]
        self.state.expected_rpm = float(expected) if expected not in (None, "") else None
        state = self.hass.states.get(rpm_entity)
        try: rpm = float(state.state) if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else None
        except (TypeError, ValueError): rpm = None
        if rpm is not None and self.state.expected_rpm is not None: self.state.rpm_deviation = rpm - self.state.expected_rpm
        if (dt_util.utcnow() - self._last_output_change).total_seconds() < int(self.cfg.get(CONF_RPM_SETTLE_TIME, DEFAULT_RPM_SETTLE_TIME)): self.state.fan_fault = False; return
        if rpm is None: self.state.fan_fault = True; return
        if self.state.expected_rpm is None: self.state.fan_fault = False; return
        self.state.fan_fault = abs(self.state.rpm_deviation) > max(self.state.expected_rpm * float(self.cfg.get(CONF_RPM_TOLERANCE, DEFAULT_RPM_TOLERANCE)) / 100, 1)
    @property
    def boost_remaining_seconds(self): return max(0, int((self.state.boost_until - dt_util.utcnow()).total_seconds())) if self._boost_active() else 0
