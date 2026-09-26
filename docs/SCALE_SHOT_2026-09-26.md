# Attended paddle shot with BOOKOO scale · 2026-09-26

The owner reported a BOOKOO Themis Ultra connected to the machine over Bluetooth
and prepared for weight capture. The agent ran only the existing read-only
benchmark and 180-second capture; the owner operated the paddle. No brew, boiler,
cleaning, profile, scale-pairing or tare command was sent by the integration.

## Integrity and shot-volume validation

- Integration: installed 0.3.1 on HA 2026.9.1, through the existing ESPHome proxy.
- Benchmark accepted 2 Hz paired reads; 5 Hz reached 2.427 Hz and was rejected
  for cadence, not a transport/protocol error.
- Capture: 18:41:39.381242–18:44:39.382120 UTC; 360 pairs at 2.0013 Hz.
- All 720 raw frames revalidated offline and matched the saved decoded fields.
  Longest pair-completion gap: 0.873 s; none exceeded one second.
- State: idle → profile (`0x2`, 54 samples) → idle; no water alarm or unknown bits.
- Final timer: 26.8 s; peak reported pump pressure: 9.6 bar. These are machine
  readings, not independently timed or calibrated physical measurements.
- Last active counter: 63 mL; first idle: 65 mL; settled: 66 mL, 2.150 s later.
- HA saved **66 mL** for the last shot. Observed shots advanced 3 → 4 and total
  water 276 → 342 mL, adding exactly 66 mL. Cleaning history stayed unchanged.
- Routine polling recovered without failures; control options/locks were unchanged.

This is one live validation of 0.3.1's terminal-volume correction at 2 Hz. It does
not validate ordinary 30-second polling as complete shot tracking or establish
pumped volume as cup yield. The first active pair still contained old telemetry
(63 mL, 30 s) before the next pair reset to 0 mL / 0.4 s: paired reads are not
atomic, and stale start values remain a separate attribution risk.

## Weight evidence and unresolved fields

The machine forwarded changing scale-weight data in register 1412 during the shot.
Decoded weight reached 32.7 g at the last active sample, then:

| Seconds after first idle | Weight field | Pumped counter |
|---:|---:|---:|
| 0.000 | 33.6 g | 65 mL |
| 0.511 | 34.7 g | 65 mL |
| 1.147 | 34.8 g | 65 mL |
| 2.150 | 34.6 g | 66 mL |
| 7.270 | 32.1 g | 66 mL |
| 10.055 | 32.3 g | 66 mL |

The owner subsequently reported a final BOOKOO display weight of **34.2 g**.
The machine's decoded weight also reached 34.2 g about 32.580 seconds after first
idle, providing one display-value comparison for the forwarded field. Individual
interval timing and whether the cup was touched/moved were not reported. Later
weight changes and zero transitions prevent selecting a unique final cup yield
from telemetry alone. Do not substitute the early 34.8 g value, overall trace
maximum of 49.4 g, or final sample for the owner's reported 34.2 g yield.

The current unsigned weight-rate decoder produced implausible readings up to
6553.5 g/s. High raw words include 65535 and 65532, consistent with a possible
signed representation (-0.1 and -0.4 if signed tenths), but signedness/sentinels
and behavior during cup movement remain unverified. Weight-rate data must not
be used for control or treated as calibrated flow.

Previously unmapped register 1415 varied from 0 to 494 and equaled register 1412
in 329/360 samples. This is a candidate related scale field, not an established
meaning or a new exposed entity. Other 11 unmapped positions remained zero.

Raw frames stay owner-only (`0600`) in private ignored storage. Only this reviewed
summary is public. Next: separately test weight-rate interpretation, stable cup
yield selection and stale initial telemetry boundaries offline. The single display
comparison does not establish general calibration or a final-yield algorithm.
