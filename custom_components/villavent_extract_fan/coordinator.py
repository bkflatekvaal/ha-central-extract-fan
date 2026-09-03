from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import *


@dataclass
class ControllerState:
    requested_level: int = LEVEL_LOW
    effective_level: int = LEVEL_LOW
    control_humidity: float | None = None
    humidity_source: str | None = None
    control_source: str = "humidity"
    manual_level: int | None = None
    boost_until: datetime | None = None
    humidity_fault: bool = False
    fan_fault: bool = False


class VillaventController:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.state = ControllerState()
        self._listeners: list[Any] = []
        self._entity_update_callbacks: set[Any] = set()
        self._boost_cancel: Any | None = None
        self._last_output_change = dt_util.utcnow()
        self._writing_outputs = asyncio.Lock()

    @property
    def cfg(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def add_update_listener(self, cb):
        self._entity_update_callbacks.add(cb)
        return lambda: self._entity_update_callbacks.discard(cb)

    @callback
    def _notify_entities(self) -> None:
        for cb in list(self._entity_update_callbacks):
            cb()

    async def async_initialize(self) -> None:
        entities = [self.cfg[CONF_CH1], self.cfg[CONF_CH2], *self.cfg.get(CONF_HUMIDITY_SENSORS, [])]
        for optional in (CONF_SILENT_SCHEDULE, CONF_RPM_SENSOR):
            if self.cfg.get(optional):
                entities.append(self.cfg[optional])
        entities.extend(self.cfg.get(CONF_INDICATORS_CH1, []))
        entities.extend(self.cfg.get(CONF_INDICATORS_CH2, []))
        self._listeners.append(async_track_state_change_event(self.hass, entities, self._async_state_changed))
        await self.async_recalculate(force_output=True)

    async def async_shutdown(self) -> None:
        for unsub in self._listeners:
            unsub()
        self._listeners.clear()
        if self._boost_cancel:
            self._boost_cancel()
            self._boost_cancel = None

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_recalculate())

    def _read_humidity(self) -> tuple[float | None, str | None, list[str], list[str]]:
        valid: list[tuple[float, str]] = []
        unavailable: list[str] = []
        for entity_id in self.cfg.get(CONF_HUMIDITY_SENSORS, []):
            st = self.hass.states.get(entity_id)
            if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                unavailable.append(entity_id)
                continue
            try:
                valid.append((float(st.state), entity_id))
            except (TypeError, ValueError):
                unavailable.append(entity_id)
        if not valid:
            return None, None, [], unavailable
        value, source = max(valid, key=lambda x: x[0])
        return value, source, [e for _, e in valid], unavailable

    def _calculate_requested_level(self, humidity: float | None) -> int:
        if humidity is None:
            return LEVEL_LOW

        medium = float(self.cfg.get(CONF_MEDIUM_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD))
        high = float(self.cfg.get(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD))
        hyst = float(self.cfg.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS))
        current = self.state.requested_level or LEVEL_LOW

        # Closed hysteresis state machine. Threshold values are the nominal borders;
        # hysteresis defines the full margin on each side of each nominal border.
        med_up = medium + hyst
        med_down = medium - hyst
        high_up = high + hyst
        high_down = high - hyst

        if current <= LEVEL_LOW:
            if humidity >= high_up:
                return LEVEL_HIGH
            if humidity >= med_up:
                return LEVEL_MEDIUM
            return LEVEL_LOW

        if current == LEVEL_MEDIUM:
            if humidity >= high_up:
                return LEVEL_HIGH
            if humidity <= med_down:
                return LEVEL_LOW
            return LEVEL_MEDIUM

        if current >= LEVEL_HIGH:
            if humidity <= med_down:
                return LEVEL_LOW
            if humidity <= high_down:
                return LEVEL_MEDIUM
            return LEVEL_HIGH

        return LEVEL_LOW

    def _silent_active(self) -> bool:
        entity_id = self.cfg.get(CONF_SILENT_SCHEDULE)
        return bool(entity_id and self.hass.states.is_state(entity_id, STATE_ON))

    def _boost_active(self) -> bool:
        return self.state.boost_until is not None and self.state.boost_until > dt_util.utcnow()

    def _calculate_effective_level(self, requested: int) -> tuple[int, str]:
        if self._boost_active():
            level = LEVEL_HIGH
            source = "boost"
        elif self.state.manual_level is not None:
            level = self.state.manual_level
            source = "manual"
        else:
            level = max(LEVEL_LOW, requested)
            source = "humidity" if not self.state.humidity_fault else "fallback"

        if self._silent_active():
            max_level = int(self.cfg.get(CONF_SILENT_MAX_LEVEL, DEFAULT_SILENT_MAX_LEVEL))
            allow_off = bool(self.cfg.get(CONF_SILENT_ALLOW_OFF, False))
            if max_level == LEVEL_OFF and not allow_off:
                max_level = LEVEL_LOW
            if level > max_level:
                level = max_level
                source = f"{source}+silent"
        return level, source

    async def async_recalculate(self, force_output: bool = False) -> None:
        humidity, source, available, unavailable = self._read_humidity()
        self.state.control_humidity = humidity
        self.state.humidity_source = source
        self.state.humidity_fault = humidity is None
        requested = self._calculate_requested_level(humidity)
        self.state.requested_level = requested
        effective, control_source = self._calculate_effective_level(requested)
        changed = effective != self.state.effective_level
        self.state.effective_level = effective
        self.state.control_source = control_source

        if changed or force_output:
            await self._async_apply_level(effective)
        await self._async_check_rpm_fault()
        self._notify_entities()

    async def _async_apply_level(self, level: int) -> None:
        async with self._writing_outputs:
            ch1 = level in (LEVEL_LOW, LEVEL_HIGH)
            ch2 = level in (LEVEL_MEDIUM, LEVEL_HIGH)
            await self._async_set_switch(self.cfg[CONF_CH1], ch1)
            delay = float(self.cfg.get(CONF_SWITCH_DELAY, DEFAULT_SWITCH_DELAY))
            if delay > 0:
                await asyncio.sleep(delay)
            await self._async_set_switch(self.cfg[CONF_CH2], ch2)
            self._last_output_change = dt_util.utcnow()
            await self._async_sync_indicators(ch1, ch2)

    async def _async_set_switch(self, entity_id: str, on: bool) -> None:
        await self.hass.services.async_call(
            "switch",
            "turn_on" if on else "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _async_sync_indicators(self, ch1: bool, ch2: bool) -> None:
        for entity_id in self.cfg.get(CONF_INDICATORS_CH1, []):
            st = self.hass.states.get(entity_id)
            if st and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                await self._async_set_switch(entity_id, ch1)
        for entity_id in self.cfg.get(CONF_INDICATORS_CH2, []):
            st = self.hass.states.get(entity_id)
            if st and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                await self._async_set_switch(entity_id, ch2)

    async def async_set_manual_level(self, level: int | None) -> None:
        self.state.manual_level = level
        await self.async_recalculate(force_output=True)

    async def async_start_boost(self, minutes: int | None = None) -> None:
        duration = int(minutes or self.cfg.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION))
        self.state.boost_until = dt_util.utcnow() + timedelta(minutes=duration)
        if self._boost_cancel:
            self._boost_cancel()
        from homeassistant.helpers.event import async_call_later
        self._boost_cancel = async_call_later(self.hass, duration * 60, self._async_boost_finished)
        await self.async_recalculate(force_output=True)

    async def async_cancel_boost(self) -> None:
        if self._boost_cancel:
            self._boost_cancel()
            self._boost_cancel = None
        self.state.boost_until = None
        await self.async_recalculate(force_output=True)

    async def _async_boost_finished(self, _now) -> None:
        self._boost_cancel = None
        self.state.boost_until = None
        await self.async_recalculate(force_output=True)

    async def _async_check_rpm_fault(self) -> None:
        rpm_entity = self.cfg.get(CONF_RPM_SENSOR)
        if not rpm_entity:
            self.state.fan_fault = False
            return
        settle = int(self.cfg.get(CONF_RPM_SETTLE_TIME, DEFAULT_RPM_SETTLE_TIME))
        if (dt_util.utcnow() - self._last_output_change).total_seconds() < settle:
            self.state.fan_fault = False
            return
        st = self.hass.states.get(rpm_entity)
        if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self.state.fan_fault = True
            return
        try:
            rpm = float(st.state)
        except (TypeError, ValueError):
            self.state.fan_fault = True
            return

        expected_map = {
            LEVEL_LOW: self.cfg.get(CONF_RPM_LOW),
            LEVEL_MEDIUM: self.cfg.get(CONF_RPM_MEDIUM),
            LEVEL_HIGH: self.cfg.get(CONF_RPM_HIGH),
            LEVEL_OFF: 0,
        }
        expected = expected_map.get(self.state.effective_level)
        if expected in (None, ""):
            self.state.fan_fault = False
            return
        expected = float(expected)
        tolerance = float(self.cfg.get(CONF_RPM_TOLERANCE, DEFAULT_RPM_TOLERANCE)) / 100.0
        low = expected * (1 - tolerance)
        high = expected * (1 + tolerance)
        self.state.fan_fault = not (low <= rpm <= high)

    @property
    def boost_remaining_seconds(self) -> int:
        if not self._boost_active():
            return 0
        return max(0, int((self.state.boost_until - dt_util.utcnow()).total_seconds()))
