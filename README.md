# Villavent Extract Fan

Home Assistant custom integration for a three-speed central extract fan controlled by two switch entities. It provides humidity regulation, manual presets, timed boost, optional silent hours, RPM diagnostics, and indicator outputs.

## Install with HACS as a custom repository

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/bkflatekvaal/ha-villavent-extract-fan` and choose category **Integration**.
3. Find **Villavent Extract Fan** in HACS and select **Download**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Villavent Extract Fan**.

The GitHub repository must be public. Manual installation is also possible by copying `custom_components/villavent_extract_fan` to Home Assistant's `custom_components` directory.

## Hardware mapping

| Level | CH1 | CH2 |
|---|---|---|
| Off | Off | Off |
| Low | On | Off |
| Medium | Off | On |
| High | On | On |

Only changed relays are actuated. Low/Medium swaps use break-before-make switching with the configured millisecond delay (default 500 ms):

- Low → Off → Medium
- Medium → Off → Low

This deliberately avoids a temporary High state and its noticeable burst of fan noise. Direct transitions between High and Low or Medium change only the one relay that differs and incur no switching delay. Existing entries using the old seconds-based setting are converted to milliseconds automatically.

## Configuration and humidity control

Initial setup asks only for CH1, CH2, and one or more humidity sensors. The selector shows humidity-class sensors. Unavailable, unknown, and non-numeric values are ignored. Options allow changing both control relays and humidity sensors later, along with thresholds, hysteresis, boost duration, switching delay, silent hours, RPM settings, and multiple indicator switches per channel.

The highest valid humidity reading controls the fan. If none is valid, the fault entity turns on and automatic mode falls back to Low. With medium 60%, high 75%, and hysteresis 5 points: Low rises at 65%, Medium falls at 55%, Medium rises at 80%, and High falls at 70%. Inside each band the prior request is retained, with no dead zones.

## Modes, boost, and silent hours

The fan presets are **Auto**, **Low**, **Medium**, and **High** by default. Enable **Show Off in fan controls** to expose the Off preset and turn-off control. Selecting a speed creates a persistent manual override; select Auto (or turn on Automatic control) to resume regulation. Normal automatic humidity control never requests Off.

Precedence is: **Boost → Manual override → Automatic humidity control**. Silent hours cap automatic control only; they never cap Boost or a manual level. Boost preserves the selected manual/automatic mode. When boost expires or is cancelled, the controller recalculates from current humidity and schedule state instead of restoring a stale speed.

Silent hours are disabled unless a schedule entity is selected. Its automatic maximum may be Off, Low, or Medium; choosing Off is sufficient and requires no additional permission checkbox. A diagnostic timestamp shows the schedule's next change when Home Assistant provides it. The configured humidity thresholds and hysteresis are also exposed as diagnostic sensors.

Use the generated **Start boost** and **Cancel boost** button entities. Example automation action (select your generated entity because its ID may differ):

```yaml
action: button.press
target:
  entity_id: button.villavent_extract_fan_start_boost
```

## RPM diagnostics and indicators

RPM feedback is diagnostic only. Expected RPM and whole-number RPM deviation remain live during the settling period; only fan-fault evaluation is delayed. RPM diagnostics never alter speed. Indicator switches mirror commanded CH1/CH2 states; unavailable indicators are skipped.

At startup the physical speed is derived from CH1/CH2 without writing relays. Home Assistant restoration then restores manual/boost state and the controller safely converges to the required level.
