# Villavent Extract Fan

Home Assistant custom integration for a 3-speed central extract fan controlled by two switch outputs.

## Features
- 3-speed CH1/CH2 output mapping
- Multiple humidity sensors; highest valid value wins
- Closed hysteresis state machine (no dead zones)
- Manual override: off/low/medium/high/auto
- Timed boost with automatic return to current control state
- Optional Home Assistant schedule for silent hours
- Optional silent-hours maximum level
- Optional RPM feedback and fan fault detection
- Optional mirrored indicator switches for each output channel
- Ignores unavailable humidity sensors; falls back to low if all are unavailable

## Install
Copy `custom_components/villavent_extract_fan` to your Home Assistant `/config/custom_components/` directory and restart Home Assistant.
Then go to **Settings → Devices & services → Add integration → Villavent Extract Fan**.

## Output mapping
| Level | CH1 | CH2 |
|---|---|---|
| Off | Off | Off |
| Low | On | Off |
| Medium | Off | On |
| High | On | On |

## Notes
This is an initial v0.1 implementation. Test with real hardware before relying on it unattended.
