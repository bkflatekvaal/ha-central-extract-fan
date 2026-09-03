"""Pure regulation logic."""
from __future__ import annotations

LEVEL_OFF, LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH = range(4)
LEVEL_NAMES = ("off", "low", "medium", "high")

def level_from_channels(ch1: bool, ch2: bool) -> int:
    return {(False, False): 0, (True, False): 1, (False, True): 2, (True, True): 3}[(ch1, ch2)]

def channels_for_level(level: int) -> tuple[bool, bool]:
    if level not in range(4): raise ValueError(f"Invalid fan level: {level}")
    return level in (1, 3), level in (2, 3)

def hysteresis_level(humidity: float | None, previous: int, medium: float, high: float, hysteresis: float) -> int:
    """Return a deterministic request using closed stateful hysteresis."""
    if humidity is None: return LEVEL_LOW
    if previous <= LEVEL_LOW:
        if humidity >= high + hysteresis: return LEVEL_HIGH
        return LEVEL_MEDIUM if humidity >= medium + hysteresis else LEVEL_LOW
    if previous == LEVEL_MEDIUM:
        if humidity >= high + hysteresis: return LEVEL_HIGH
        return LEVEL_LOW if humidity <= medium - hysteresis else LEVEL_MEDIUM
    if humidity <= medium - hysteresis: return LEVEL_LOW
    return LEVEL_MEDIUM if humidity <= high - hysteresis else LEVEL_HIGH

def effective_level(requested: int, manual: int | None, boost: bool, silent: bool, silent_max: int) -> tuple[int, str]:
    """Apply precedence: manual, boost, then silent-capped automatic."""
    if manual is not None: return manual, "manual"
    if boost: return LEVEL_HIGH, "boost"
    level = max(LEVEL_LOW, requested)
    return (silent_max, "humidity+silent") if silent and level > silent_max else (level, "humidity")
