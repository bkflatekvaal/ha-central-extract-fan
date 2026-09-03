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

Only changed relays are actuated. During a Low/Medium swap, the new channel is enabled first and the configured delay is observed before the old channel is disabled, preventing a brief stop. Verify that this overlap is safe for your hardware.

## Configuration and humidity control

Initial setup asks only for CH1, CH2, and one or more humidity sensors. Any sensor may be selected so templates and unusual hardware work; unavailable, unknown, and non-numeric values are ignored. Options contain humidity sensors, thresholds, hysteresis, boost duration, switching delay, silent hours, RPM settings, and multiple indicator switches per channel.

The highest valid humidity reading controls the fan. If none is valid, the fault entity turns on and automatic mode falls back to Low. With medium 60%, high 75%, and hysteresis 5 points: Low rises at 65%, Medium falls at 55%, Medium rises at 80%, and High falls at 70%. Inside each band the prior request is retained, with no dead zones.

## Modes, boost, and silent hours

The fan presets are **Auto**, **Off**, **Low**, **Medium**, and **High**. Selecting a speed creates a persistent manual override; select Auto (or turn on Automatic control) to resume regulation. Automatic mode never requests Off.

Precedence is: manual override (including Off), boost, then automatic humidity control capped by an active silent-hours schedule. Thus silent hours do not cap manual control or boost. Boost does not disable Auto; when it ends, the controller recalculates the correct current level.

Use the generated **Start boost** and **Cancel boost** button entities. Example automation action (select your generated entity because its ID may differ):

```yaml
action: button.press
target:
  entity_id: button.villavent_extract_fan_start_boost
```

## RPM diagnostics and indicators

RPM feedback is diagnostic only. When configured, fan fault, expected RPM, and deviation are evaluated after the settling delay and never alter speed. Indicator switches mirror commanded CH1/CH2 states; unavailable indicators are skipped.

At startup the physical speed is derived from CH1/CH2 without writing relays. Home Assistant restoration then restores manual/boost state and the controller safely converges to the required level.
