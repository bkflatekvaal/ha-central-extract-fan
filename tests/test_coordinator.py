"""Controller-level relay and indicator tests without a Home Assistant install."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import importlib.util
import inspect
from pathlib import Path
import sys

import pytest
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).parents[1] / "custom_components/central_extract_fan"


def _install_home_assistant_stubs() -> None:
    """Install the small Home Assistant API surface used by the controller."""
    homeassistant = ModuleType("homeassistant")
    const = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        FAN = "fan"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        SWITCH = "switch"
        BUTTON = "button"
        NUMBER = "number"

    const.Platform = Platform
    const.STATE_OFF = "off"
    const.STATE_ON = "on"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"

    core = ModuleType("homeassistant.core")
    core.callback = lambda func: func

    helpers = ModuleType("homeassistant.helpers")
    event = ModuleType("homeassistant.helpers.event")
    event.async_call_later = lambda *_args: (lambda: None)
    event.async_track_state_change_event = lambda hass, entities, callback: hass.track_states(entities, callback)
    event.async_track_time_interval = lambda *_args: (lambda: None)

    util = ModuleType("homeassistant.util")
    dt = ModuleType("homeassistant.util.dt")
    dt.utcnow = lambda: datetime.now(UTC)
    util.dt = dt

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.const": const,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.event": event,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
        }
    )


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_install_home_assistant_stubs()
package = ModuleType("central_extract_fan_test")
package.__path__ = [str(ROOT)]
sys.modules["central_extract_fan_test"] = package
control = _load_module("central_extract_fan_test.control", "control.py")
const = _load_module("central_extract_fan_test.const", "const.py")
coordinator = _load_module("central_extract_fan_test.coordinator", "coordinator.py")


class States:
    def __init__(self, values):
        self.values = dict(values)
        self.listeners = []

    def get(self, entity_id):
        value = self.values.get(entity_id)
        return None if value is None else SimpleNamespace(state=value)

    def set(self, entity_id, value):
        old_state = self.get(entity_id)
        if value is None:
            self.values.pop(entity_id, None)
        else:
            self.values[entity_id] = value
        if old_state != self.get(entity_id):
            event = SimpleNamespace(data={"entity_id": entity_id, "old_state": old_state, "new_state": self.get(entity_id)})
            for entities, callback in self.listeners:
                if entity_id in entities: callback(event)

    def is_state(self, entity_id, expected):
        return self.values.get(entity_id) == expected


class Services:
    def __init__(self, states):
        self.states = states
        self.calls = []

    async def async_call(self, domain, service, data, blocking):
        entity_id = data["entity_id"]
        self.states.set(entity_id, "on" if service == "turn_on" else "off")
        self.calls.append((entity_id, service, dict(self.states.values)))


class Hass:
    def __init__(self, values):
        self.states = States(values)
        self.services = Services(self.states)
        self.tasks = []

    def track_states(self, entities, callback):
        listener = (entities, callback)
        self.states.listeners.append(listener)
        return lambda: self.states.listeners.remove(listener)

    def async_create_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    async def drain(self):
        async def finish():
            while self.tasks:
                tasks, self.tasks = self.tasks, []
                await asyncio.gather(*tasks)
        await asyncio.wait_for(finish(), timeout=1)



def make_controller(values, **options):
    data = {
        const.CONF_CH1: "switch.ch1",
        const.CONF_CH2: "switch.ch2",
        const.CONF_HUMIDITY_SENSORS: [],
    }
    entry = SimpleNamespace(data=data, options=options, entry_id="test", title="Test fan")
    hass = Hass(values)
    return coordinator.CentralExtractFanController(hass, entry), hass


def test_medium_to_low_hardware_order_is_break_before_make():
    controller, hass = make_controller({"switch.ch1": "off", "switch.ch2": "on"}, relay_switch_delay_ms=1000)
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    original_sleep = coordinator.asyncio.sleep
    coordinator.asyncio.sleep = fake_sleep
    try:
        asyncio.run(controller._apply_level(control.LEVEL_LOW))
    finally:
        coordinator.asyncio.sleep = original_sleep

    assert [(entity, service) for entity, service, _snapshot in hass.services.calls] == [
        ("switch.ch2", "turn_off"),
        ("switch.ch1", "turn_on"),
    ]
    assert delays == [1.0]
    assert hass.services.calls[0][2]["switch.ch1"] == "off"
    assert hass.services.calls[0][2]["switch.ch2"] == "off"
    assert not any(
        snapshot["switch.ch1"] == snapshot["switch.ch2"] == "on"
        for _entity, _service, snapshot in hass.services.calls
    )


def test_low_to_medium_hardware_order_uses_millisecond_delay():
    controller, hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"}, relay_switch_delay_ms=500)
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    original_sleep = coordinator.asyncio.sleep
    coordinator.asyncio.sleep = fake_sleep
    try:
        asyncio.run(controller._apply_level(control.LEVEL_MEDIUM))
    finally:
        coordinator.asyncio.sleep = original_sleep

    assert [(entity, service) for entity, service, _snapshot in hass.services.calls] == [
        ("switch.ch1", "turn_off"),
        ("switch.ch2", "turn_on"),
    ]
    assert delays == [0.5]


def test_simple_high_transitions_have_no_delay():
    cases = (
        ({"switch.ch1": "on", "switch.ch2": "off"}, control.LEVEL_HIGH, ("switch.ch2", "turn_on")),
        ({"switch.ch1": "off", "switch.ch2": "on"}, control.LEVEL_HIGH, ("switch.ch1", "turn_on")),
        ({"switch.ch1": "on", "switch.ch2": "on"}, control.LEVEL_LOW, ("switch.ch2", "turn_off")),
        ({"switch.ch1": "on", "switch.ch2": "on"}, control.LEVEL_MEDIUM, ("switch.ch1", "turn_off")),
    )
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    original_sleep = coordinator.asyncio.sleep
    coordinator.asyncio.sleep = fake_sleep
    try:
        for initial, target, expected_call in cases:
            controller, hass = make_controller(initial, relay_switch_delay_ms=500)
            asyncio.run(controller._apply_level(target))
            assert [(entity, service) for entity, service, _snapshot in hass.services.calls] == [expected_call]
    finally:
        coordinator.asyncio.sleep = original_sleep

    assert delays == []


def test_startup_synchronizes_only_mismatched_available_indicators():
    controller, hass = make_controller(
        {
            "switch.ch1": "on",
            "switch.ch2": "off",
            "switch.ch1_indicator": "off",
            "switch.ch1_matching": "on",
            "switch.ch2_unavailable": "unavailable",
        },
        indicators_ch1=["switch.ch1_indicator", "switch.ch1_matching"],
        indicators_ch2=["switch.ch2_unavailable"],
    )
    asyncio.run(controller.async_initialize())
    assert [(entity, service) for entity, service, _snapshot in hass.services.calls] == [
        ("switch.ch1_indicator", "turn_on")
    ]


def test_recovered_indicator_is_synchronized_without_fan_changes():
    controller, hass = make_controller(
        {
            "switch.ch1": "off",
            "switch.ch2": "on",
            "switch.ch2_indicator": "unavailable",
        },
        indicators_ch2=["switch.ch2_indicator"],
    )
    controller.state.effective_level = control.LEVEL_MEDIUM
    hass.states.values["switch.ch2_indicator"] = "off"
    event = SimpleNamespace(data={"entity_id": "switch.ch2_indicator"})
    asyncio.run(controller._handle_state_change(event))
    assert [(entity, service) for entity, service, _snapshot in hass.services.calls] == [
        ("switch.ch2_indicator", "turn_on")
    ]
    assert hass.states.values["switch.ch1"] == "off"
    assert hass.states.values["switch.ch2"] == "on"


def test_rpm_deviation_remains_live_while_fault_is_suppressed_during_settling():
    controller, hass = make_controller(
        {
            "switch.ch1": "on",
            "switch.ch2": "off",
            "sensor.rpm": "1200",
        },
        rpm_sensor="sensor.rpm",
        rpm_low=470,
        rpm_tolerance=20,
        rpm_settle_time=30,
    )
    controller.state.effective_level = control.LEVEL_LOW
    controller._last_output_change = datetime.now(UTC)

    controller._check_rpm()

    assert controller.state.expected_rpm == 470
    assert controller.state.rpm_deviation == 730
    assert controller.state.fan_fault is False

    controller._last_output_change = datetime.now(UTC) - timedelta(seconds=31)
    controller._check_rpm()

    assert controller.state.expected_rpm == 470
    assert controller.state.rpm_deviation == 730
    assert controller.state.fan_fault is True


def test_default_boost_is_always_high_and_explicit_medium_is_supported():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    asyncio.run(controller.async_start_boost())
    assert controller.state.boost_level == control.LEVEL_HIGH
    assert controller.state.effective_level == control.LEVEL_HIGH
    asyncio.run(controller.async_start_boost(control.LEVEL_MEDIUM))
    assert controller.state.boost_level == control.LEVEL_MEDIUM
    assert controller.state.effective_level == control.LEVEL_MEDIUM


def test_explicit_low_override_and_off_rejection():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "on"})
    controller.state.manual_level = control.LEVEL_HIGH
    asyncio.run(controller.async_start_boost(control.LEVEL_LOW))
    assert controller.state.boost_level == control.LEVEL_LOW
    assert controller.state.effective_level == control.LEVEL_LOW

    try:
        asyncio.run(controller.async_start_boost(control.LEVEL_OFF))
    except ValueError:
        pass
    else:
        raise AssertionError("Off must not be accepted as a timed override level")


def test_starting_again_replaces_level_and_restarts_requested_duration():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    asyncio.run(controller.async_start_boost(control.LEVEL_LOW, 5))
    first_until = controller.state.boost_until
    asyncio.run(controller.async_start_boost(control.LEVEL_MEDIUM, 30))
    assert controller.state.boost_level == control.LEVEL_MEDIUM
    assert controller.state.boost_until > first_until
    remaining = (controller.state.boost_until - datetime.now(UTC)).total_seconds()
    assert 1798 <= remaining <= 1800


def test_default_boost_is_high_from_auto_medium_auto_low_and_manual_low():
    for humidity, manual in (
        (65, None),
        (40, None),
        (40, control.LEVEL_LOW),
    ):
        controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off", "sensor.humidity": str(humidity)})
        controller.entry.data[const.CONF_HUMIDITY_SENSORS] = ["sensor.humidity"]
        controller.state.manual_level = manual
        asyncio.run(controller.async_start_boost())
        assert controller.state.boost_level == control.LEVEL_HIGH
        assert controller.state.effective_level == control.LEVEL_HIGH


def test_explicit_medium_override_is_held_while_auto_changes():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off", "sensor.humidity": "40"})
    controller.entry.data[const.CONF_HUMIDITY_SENSORS] = ["sensor.humidity"]
    asyncio.run(controller.async_start_boost(control.LEVEL_MEDIUM))
    _hass.states.values["sensor.humidity"] = "90"
    asyncio.run(controller.async_recalculate())
    assert controller.state.requested_level == control.LEVEL_HIGH
    assert controller.state.effective_level == control.LEVEL_MEDIUM


def test_cancel_and_expiry_return_to_current_underlying_state():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    controller.state.manual_level = control.LEVEL_LOW
    asyncio.run(controller.async_start_boost(control.LEVEL_HIGH))
    assert controller.state.effective_level == control.LEVEL_HIGH
    asyncio.run(controller.async_cancel_boost())
    assert controller.state.effective_level == control.LEVEL_LOW
    controller.state.manual_level = None
    asyncio.run(controller.async_start_boost(control.LEVEL_MEDIUM))
    asyncio.run(controller._boost_finished(datetime.now(UTC)))
    assert controller.state.effective_level == control.LEVEL_LOW


def test_expiry_returns_to_current_auto_state():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off", "sensor.humidity": "40"})
    controller.entry.data[const.CONF_HUMIDITY_SENSORS] = ["sensor.humidity"]
    asyncio.run(controller.async_start_boost(control.LEVEL_MEDIUM))
    _hass.states.values["sensor.humidity"] = "90"
    asyncio.run(controller._boost_finished(datetime.now(UTC)))
    assert controller.state.effective_level == control.LEVEL_HIGH


def test_restore_active_boost_level_without_extending_and_ignore_expired():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    future = datetime.now(UTC) + timedelta(minutes=12)
    asyncio.run(controller.async_restore(None, future, control.LEVEL_MEDIUM))
    assert controller.state.boost_until == future
    assert controller.state.boost_level == control.LEVEL_MEDIUM
    assert controller.state.effective_level == control.LEVEL_MEDIUM

    expired_controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    expired_controller.state.boost_until = future
    expired_controller.state.boost_level = control.LEVEL_MEDIUM
    past = datetime.now(UTC) - timedelta(minutes=1)
    asyncio.run(expired_controller.async_restore(None, past, control.LEVEL_HIGH))
    assert expired_controller.state.boost_until is None
    assert expired_controller.state.boost_level is None
    assert expired_controller.state.effective_level == control.LEVEL_LOW


def test_legacy_restore_without_boost_level_defaults_to_high():
    controller, _hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
    future = datetime.now(UTC) + timedelta(minutes=12)
    asyncio.run(controller.async_restore(None, future))
    assert controller.state.boost_until == future
    assert controller.state.boost_level == control.LEVEL_HIGH
    assert controller.state.effective_level == control.LEVEL_HIGH


def test_boost_controller_method_signatures_match_callers():
    start = inspect.signature(coordinator.CentralExtractFanController.async_start_boost)
    restore = inspect.signature(coordinator.CentralExtractFanController.async_restore)
    assert tuple(start.parameters) == ("self", "level", "duration")
    assert start.parameters["level"].default is None
    assert start.parameters["duration"].default is None
    assert tuple(restore.parameters) == ("self", "manual", "boost_until", "boost_level")
    assert restore.parameters["boost_level"].default is None
    setup_source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "async_start_boost(level, call.data.get(\"duration\"))" in setup_source
    fan_source = (ROOT / "fan.py").read_text(encoding="utf-8")
    assert "async_restore(manual, boost, boost_level)" in fan_source

def relay_calls(hass):
    return [(entity, service) for entity, service, _snapshot in hass.services.calls if entity in ("switch.ch1", "switch.ch2")]


@pytest.mark.parametrize("invalid", [None, "unknown", "unavailable", "invalid"])
@pytest.mark.parametrize("channel", ["switch.ch1", "switch.ch2"])
def test_invalid_relay_state_never_matches_or_sends_commands(invalid, channel):
    async def scenario():
        controller, hass = make_controller({"switch.ch1": "off", "switch.ch2": "off", channel: invalid})
        assert controller._read_channels() is None
        assert not any(controller._outputs_match(level) for level in range(4))
        before = controller._last_output_change
        assert await controller._set_switch(channel, True) is False
        assert await controller._apply_level(control.LEVEL_HIGH) is False
        await controller.async_recalculate()
        assert hass.services.calls == []
        assert controller._last_output_change == before
    asyncio.run(scenario())


def test_startup_without_relays_waits_for_both_and_recalculates_latest_inputs():
    async def scenario():
        controller, hass = make_controller(
            {"sensor.humidity": "90", "switch.indicator": "off"},
            humidity_sensors=["sensor.humidity"], indicators_ch1=["switch.indicator"],
        )
        before = controller._last_output_change
        await controller.async_initialize()
        await controller.async_restore(None, None)
        assert controller.state.effective_level == control.LEVEL_HIGH
        assert controller._read_channels() is None
        assert hass.services.calls == []
        hass.states.set("switch.ch1", "off")
        await hass.drain()
        assert hass.services.calls == []
        assert controller._last_output_change == before
        hass.states.set("sensor.humidity", "65")
        await hass.drain()
        hass.states.set("switch.ch2", "off")
        await hass.drain()
        assert controller.state.effective_level == control.LEVEL_MEDIUM
        assert controller._read_channels() == (False, True)
        assert relay_calls(hass) == [("switch.ch2", "turn_on")]
        await controller.async_shutdown()
    asyncio.run(scenario())


@pytest.mark.parametrize("channel", ["switch.ch1", "switch.ch2"])
@pytest.mark.parametrize("unavailable", [None, "unknown", "unavailable"])
def test_runtime_unavailability_defers_control_and_indicators_until_recovery(channel, unavailable):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "switch.indicator": "off"},
            indicators_ch2=["switch.indicator"],
        )
        await controller.async_initialize()
        before = controller._last_output_change
        hass.states.set(channel, unavailable)
        await hass.drain()
        await controller.async_set_manual_level(control.LEVEL_HIGH)
        # Even a recovering indicator must not advertise the deferred target.
        hass.states.set("switch.indicator", "unavailable")
        hass.states.set("switch.indicator", "off")
        await hass.drain()
        assert hass.services.calls == []
        assert controller._last_output_change == before
        hass.states.set(channel, "on" if channel == "switch.ch1" else "off")
        await hass.drain()
        assert controller._read_channels() == (True, True)
        assert relay_calls(hass) == [("switch.ch2", "turn_on")]
        assert hass.states.is_state("switch.indicator", "on")
        await controller.async_shutdown()
    asyncio.run(scenario())


@pytest.mark.parametrize("channel", ["switch.ch1", "switch.ch2"])
def test_relay_unavailable_during_delay_aborts_then_recovers(monkeypatch, channel):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "switch.indicator": "off"},
            relay_switch_delay_ms=500, indicators_ch2=["switch.indicator"],
        )
        await controller.async_initialize()
        before = controller._last_output_change
        delays = []
        async def lose_relay(delay):
            delays.append(delay)
            hass.states.set(channel, "unavailable")
        monkeypatch.setattr(coordinator.asyncio, "sleep", lose_relay)
        await controller.async_set_manual_level(control.LEVEL_MEDIUM)
        await hass.drain()
        assert relay_calls(hass) == [("switch.ch1", "turn_off")]
        assert delays == [0.5]
        assert controller._last_output_change == before
        assert controller._settle_cancel is None
        assert hass.states.is_state("switch.indicator", "off")
        hass.states.set(channel, "off")
        await hass.drain()
        assert controller._read_channels() == (False, True)
        assert relay_calls(hass) == [("switch.ch1", "turn_off"), ("switch.ch2", "turn_on")]
        assert hass.states.is_state("switch.indicator", "on")
        await controller.async_shutdown()
    asyncio.run(scenario())


@pytest.mark.parametrize("initial,target,expected", [
    (("on", "off"), control.LEVEL_MEDIUM, [("switch.ch1", "turn_off"), ("switch.ch2", "turn_on")]),
    (("off", "on"), control.LEVEL_LOW, [("switch.ch2", "turn_off"), ("switch.ch1", "turn_on")]),
])
def test_own_relay_events_preserve_delay_without_loops_or_deadlock(monkeypatch, initial, target, expected):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": initial[0], "switch.ch2": initial[1], "switch.indicator": "off"},
            relay_switch_delay_ms=250, indicators_ch2=["switch.indicator"],
        )
        await controller.async_initialize()
        await hass.drain()
        hass.services.calls.clear()
        delays = []
        real_sleep = asyncio.sleep
        async def yield_during_delay(delay):
            delays.append(delay)
            await real_sleep(0)
            assert controller._lock.locked()
            assert controller._read_channels() == (False, False)
        monkeypatch.setattr(coordinator.asyncio, "sleep", yield_during_delay)
        await asyncio.wait_for(controller.async_set_manual_level(target), timeout=1)
        await hass.drain()
        assert relay_calls(hass) == expected
        assert delays == [0.25]
        assert controller._outputs_match(target)
        assert not controller._lock.locked()
        await controller.async_shutdown()
    asyncio.run(scenario())


def test_queued_recalculation_reads_inputs_only_after_acquiring_lock():
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "sensor.humidity": "90"},
            humidity_sensors=["sensor.humidity"],
        )
        async with controller._lock:
            pending = asyncio.create_task(controller.async_recalculate())
            await asyncio.sleep(0)
            hass.states.set("sensor.humidity", "40")
        await asyncio.wait_for(pending, timeout=1)
        assert controller.state.control_humidity == 40
        assert controller.state.effective_level == control.LEVEL_LOW
        assert hass.services.calls == []
    asyncio.run(scenario())


@pytest.mark.parametrize("manual,boost,silent,expected", [
    (None, None, False, control.LEVEL_HIGH),
    (None, None, True, control.LEVEL_LOW),
    (control.LEVEL_MEDIUM, None, True, control.LEVEL_MEDIUM),
    (control.LEVEL_MEDIUM, control.LEVEL_HIGH, True, control.LEVEL_HIGH),
])
def test_recovery_preserves_control_precedence(manual, boost, silent, expected):
    async def scenario():
        controller, hass = make_controller(
            {"sensor.humidity": "90", "schedule.silent": "on" if silent else "off"},
            humidity_sensors=["sensor.humidity"], silent_schedule="schedule.silent", silent_max_level=control.LEVEL_LOW,
        )
        await controller.async_initialize()
        until = datetime.now(UTC) + timedelta(minutes=5) if boost else None
        await controller.async_restore(manual, until, boost)
        assert hass.services.calls == []
        hass.states.set("switch.ch1", "off")
        hass.states.set("switch.ch2", "off")
        await hass.drain()
        assert controller.state.effective_level == expected
        assert controller._outputs_match(expected)
        await controller.async_shutdown()
    asyncio.run(scenario())


def test_unconfirmed_break_does_not_make_or_mark_transition_complete(monkeypatch):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "switch.indicator": "off"},
            relay_switch_delay_ms=500, indicators_ch2=["switch.indicator"],
        )
        before = controller._last_output_change
        calls, delays = [], []
        async def unconfirmed_call(domain, service, data, blocking):
            calls.append((data["entity_id"], service))
        async def delay(seconds):
            delays.append(seconds)
        monkeypatch.setattr(hass.services, "async_call", unconfirmed_call)
        monkeypatch.setattr(coordinator.asyncio, "sleep", delay)
        assert await controller._apply_level(control.LEVEL_MEDIUM) is False
        assert calls == [("switch.ch1", "turn_off")]
        assert delays == [0.5]
        assert controller._last_output_change == before
        assert controller._settle_cancel is None
        assert hass.states.is_state("switch.indicator", "off")
    asyncio.run(scenario())

def test_relay_attribute_events_do_not_retry_unconfirmed_commands(monkeypatch):
    async def scenario():
        controller, hass = make_controller({"switch.ch1": "on", "switch.ch2": "off"})
        await controller.async_initialize()
        calls = []
        async def attribute_only_call(domain, service, data, blocking):
            calls.append((data["entity_id"], service))
            controller._state_changed(SimpleNamespace(data={
                "entity_id": data["entity_id"],
                "old_state": SimpleNamespace(state="off", attributes={"report": 1}),
                "new_state": SimpleNamespace(state="off", attributes={"report": 2}),
            }))
        monkeypatch.setattr(hass.services, "async_call", attribute_only_call)
        before = controller._last_output_change
        await controller.async_set_manual_level(control.LEVEL_HIGH)
        await hass.drain()
        assert calls == [("switch.ch2", "turn_on")]
        assert controller._last_output_change == before
        assert controller._settle_cancel is None
        await controller.async_shutdown()
    asyncio.run(scenario())


def test_service_failure_does_not_mark_success_and_releases_lock(monkeypatch):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "switch.indicator": "off"},
            indicators_ch2=["switch.indicator"],
        )
        before = controller._last_output_change
        original_call = hass.services.async_call
        async def failed_call(*args, **kwargs):
            raise RuntimeError("Relay service failed")
        monkeypatch.setattr(hass.services, "async_call", failed_call)
        with pytest.raises(RuntimeError, match="Relay service failed"):
            await controller.async_set_manual_level(control.LEVEL_HIGH)
        assert controller._last_output_change == before
        assert controller._settle_cancel is None
        assert not controller._lock.locked()
        assert hass.states.is_state("switch.indicator", "off")
        monkeypatch.setattr(hass.services, "async_call", original_call)
        await asyncio.wait_for(controller.async_recalculate(), timeout=1)
        assert controller._outputs_match(control.LEVEL_HIGH)
        assert hass.states.is_state("switch.indicator", "on")
    asyncio.run(scenario())


def test_unavailability_during_final_service_call_is_not_success(monkeypatch):
    async def scenario():
        controller, hass = make_controller(
            {"switch.ch1": "on", "switch.ch2": "off", "switch.indicator": "off"},
            indicators_ch2=["switch.indicator"],
        )
        before = controller._last_output_change
        async def lose_other_relay(domain, service, data, blocking):
            hass.states.set(data["entity_id"], "on")
            hass.states.set("switch.ch1", "unavailable")
        monkeypatch.setattr(hass.services, "async_call", lose_other_relay)
        assert await controller._apply_level(control.LEVEL_HIGH) is False
        assert controller._last_output_change == before
        assert controller._settle_cancel is None
        assert hass.states.is_state("switch.indicator", "off")
    asyncio.run(scenario())
