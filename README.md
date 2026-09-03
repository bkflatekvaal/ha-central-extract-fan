# Central Extract Fan

Home Assistant custom integration for a three-speed central extract fan, including relay-controlled systems commonly found in Villavent and Flexit installations. It provides humidity regulation, manual presets, timed boost, optional silent hours, RPM diagnostics, and indicator outputs.

## Install with HACS as a custom repository

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/bkflatekvaal/ha-central-extract-fan` and choose category **Integration**.
3. Find **Central Extract Fan** in HACS and select **Download**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Central Extract Fan**.

The GitHub repository must be public. Manual installation is also possible by copying `custom_components/central_extract_fan` to Home Assistant's `custom_components` directory.

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

The fan presets are **Auto**, **Low**, **Medium**, and **High** by default. Enable **Show and allow Off in fan controls** to expose and permit the Off preset. When disabled, Off is omitted from the preset list and zero-percent or turn-off commands resolve safely to Low. Some Home Assistant dashboards may still render the fan domain's standard power button, but it cannot stop this fan while Off is disabled. Selecting a speed creates a persistent manual override; select Auto (or turn on Automatic control) to resume regulation. Normal automatic humidity control never requests Off.

Precedence is: **Boost → Manual override → Automatic humidity control**. Silent hours cap automatic control only; they never cap Boost or a manual level. Boost is a time-limited High override—not another manual mode. It preserves the selected manual/automatic mode and keeps automatic humidity regulation running underneath. When boost expires or is cancelled, the controller recalculates from current humidity and schedule state instead of restoring a stale speed. The action may explicitly request Low or Medium as a generic timed override.

Silent hours are disabled unless a schedule entity is selected. Its automatic maximum may be Off, Low, or Medium; choosing Off is sufficient and requires no additional permission checkbox. A diagnostic timestamp shows the schedule's next change when Home Assistant provides it. The configured humidity thresholds and hysteresis are also exposed as diagnostic sensors.

Use **Start boost**, **Cancel boost**, or **Toggle boost**. Start boost and an inactive toggle always start a High boost for the configured duration. Starting boost again restarts that duration. Boost status is exposed through an active binary sensor, remaining-seconds sensor, and restart-safe **Boost ends at** timestamp.

The integration also provides `central_extract_fan.start_boost` and `central_extract_fan.cancel_boost` actions. Level and duration are optional; an omitted level always means High, and an omitted duration uses the configured duration. For example, a 30-minute Medium timed override:

```yaml
action: central_extract_fan.start_boost
target:
  entity_id: fan.central_extract_fan
data:
  level: medium
  duration: 30
```

External button automations can start different levels without changing manual mode—for example, map a single press to `level: high` and a double press to `level: medium`. The integration remains independent of the button or relay hardware.

The original Start boost button remains available for simple automations (select your generated entity because its ID may differ):

```yaml
action: button.press
target:
  entity_id: button.central_extract_fan_start_boost
```

## RPM diagnostics and indicators

RPM feedback is diagnostic only. Expected RPM and whole-number RPM deviation remain live during the settling period; only fan-fault evaluation is delayed. RPM diagnostics never alter speed. Indicator switches mirror commanded CH1/CH2 states; unavailable indicators are skipped.

At startup the physical speed is derived from CH1/CH2 without writing relays. Home Assistant restoration then restores manual/boost state and the controller safely converges to the required level.
