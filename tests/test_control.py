"""Tests for the pure controller state machine."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("control", Path(__file__).parents[1] / "custom_components/villavent_extract_fan/control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

def test_channel_truth_table():
    for level, channels in enumerate(((False, False), (True, False), (False, True), (True, True))):
        assert control.channels_for_level(level) == channels
        assert control.level_from_channels(*channels) == level

def test_closed_stateful_hysteresis():
    calc = control.hysteresis_level
    assert calc(64.9, 1, 60, 75, 5) == 1
    assert calc(65, 1, 60, 75, 5) == 2
    assert calc(56, 2, 60, 75, 5) == 2
    assert calc(55, 2, 60, 75, 5) == 1
    assert calc(80, 2, 60, 75, 5) == 3
    assert calc(71, 3, 60, 75, 5) == 3
    assert calc(70, 3, 60, 75, 5) == 2

def test_no_dead_zone_and_direct_transitions():
    for previous in range(4):
        for humidity in range(101):
            assert control.hysteresis_level(humidity, previous, 60, 75, 5) in (1, 2, 3)
    assert control.hysteresis_level(90, 1, 60, 75, 5) == 3
    assert control.hysteresis_level(40, 3, 60, 75, 5) == 1

def test_unavailable_humidity_falls_back_low():
    assert control.hysteresis_level(None, 3, 60, 75, 5) == 1

def test_precedence_manual_boost_silent_auto():
    effective = control.effective_level
    assert effective(3, None, False, True, 1) == (1, "humidity+silent")
    assert effective(1, None, True, True, 1) == (3, "boost")
    assert effective(3, 0, True, True, 1) == (0, "manual")
    assert effective(1, 2, False, True, 1) == (2, "manual")
    assert effective(3, None, False, False, 1) == (3, "humidity")
