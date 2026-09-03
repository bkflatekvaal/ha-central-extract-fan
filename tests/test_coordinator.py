"""Controller-level relay and indicator tests without a Home Assistant install."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).parents[1] / "custom_components/villavent_extract_fan"


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
    const.STATE_ON = "on"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"

    core = ModuleType("homeassistant.core")
    core.callback = lambda func: func

    helpers = ModuleType("homeassistant.helpers")
    event = ModuleType("homeassistant.helpers.event")
    event.async_call_later = lambda *_args: (lambda: None)
    event.async_track_state_change_event = lambda *_args: (lambda: None)
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
package = ModuleType("villavent_test")
package.__path__ = [str(ROOT)]
sys.modules["villavent_test"] = package
control = _load_module("villavent_test.control", "control.py")
const = _load_module("villavent_test.const", "const.py")
coordinator = _load_module("villavent_test.coordinator", "coordinator.py")


class States:
    def __init__(self, values):
        self.values = dict(values)

    def get(self, entity_id):
        value = self.values.get(entity_id)
        return None if value is None else SimpleNamespace(state=value)

    def is_state(self, entity_id, expected):
        return self.values.get(entity_id) == expected


class Services:
    def __init__(self, states):
        self.states = states
        self.calls = []

    async def async_call(self, domain, service, data, blocking):
        entity_id = data["entity_id"]
        self.states.values[entity_id] = "on" if service == "turn_on" else "off"
        self.calls.append((entity_id, service, dict(self.states.values)))


class Hass:
    def __init__(self, values):
        self.states = States(values)
        self.services = Services(self.states)

    def async_create_task(self, coroutine):
        return asyncio.create_task(coroutine)


def make_controller(values, **options):
    data = {
        const.CONF_CH1: "switch.ch1",
        const.CONF_CH2: "switch.ch2",
        const.CONF_HUMIDITY_SENSORS: [],
    }
    entry = SimpleNamespace(data=data, options=options, entry_id="test", title="Test fan")
    hass = Hass(values)
    return coordinator.VillaventController(hass, entry), hass


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
