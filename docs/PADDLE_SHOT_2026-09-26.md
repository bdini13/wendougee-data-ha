# First complete read-only paddle-shot trace · 2026-09-26

The owner reported the portafilter prepared, operated the physical paddle normally,
and confirmed the shot finished. Cup weight was **not measured**. The agent sent
only the existing read-only benchmark and trace actions; no brew or boiler control
was sent during this capture. The requested paddle-bound remote trigger remains
unimplemented and disabled.

## Capture integrity

- UTC window: 17:38:21.365719–17:41:21.367723, about 180 seconds.
- The fresh benchmark selected 2 Hz; 5 Hz failed cadence, not protocol validation.
- Capture: **360 telemetry/state pairs**, achieved 1.99998 Hz.
- Offline replay independently revalidated all **720 raw response frames** with
  the original strict decoders and matched every saved decoded value.
- Median pair-completion interval: 0.510 seconds; maximum: 1.020 seconds. One
  interval exceeded one second. This was not an atomic telemetry/state snapshot:
  each pair comprises two sequential requests.
- Raw trace remains owner-only (`0600`) and ignored by Git. Only reviewed
  aggregate observations and transition values are recorded here.

## Observed shot

| Measurement | Machine-reported observation |
|---|---|
| State sequence | Idle → profile → idle |
| Active-state raw bits | `0x000002` in all 45 active samples; zero elsewhere |
| Elapsed shot timer | Final latched value **22.4 s** |
| Pump pressure | Peak **9.5 bar**; not a measurement of puck pressure |
| Brew temperature while active | **92.0–94.4 °C**, without physical calibration |
| Pumped-volume counter | **64 mL** last active sample; **66 mL** settled after idle |
| Scale weight/rate fields | Zero throughout; unavailable cup-weight evidence, not zero yield |
| Water-alarm flag | False throughout |

The first active state was observed at offset 55.909 s and the first subsequent
idle at 78.437 s. Including adjacent sample boundaries brackets the active-state
duration at roughly 21.914–23.039 s, consistent with the 22.4 s elapsed timer.
This supports the timer's decisecond interpretation for this shot, but is not an
independent stopwatch comparison or proof of every timing field's semantics.

All 12 currently unmapped telemetry positions stayed zero, including during the
shot. No new fault, readiness, or heater-power field was identified.

## Confirmed last-shot finalization limitation

| Capture offset | State | Timer | Pumped counter | Pressure |
|---:|---|---:|---:|---:|
| 77.823 s | Profile | 22.0 s | 64 mL | 8.9 bar |
| 78.437 s | Idle | 22.4 s | 65 mL | 8.9 bar |
| 79.053 s | Idle | 22.4 s | 65 mL | 8.9 bar |
| 79.563 s | Idle | 22.4 s | 65 mL | 0.8 bar |
| 79.973 s | Idle | 22.4 s | 66 mL | 0.8 bar |
| 80.384 s | Idle | 22.4 s | 66 mL | 0.0 bar |

The volume continued to settle for at least 1.536 s after the first observed idle
state. The deployed activity tracker finalizes from the peak seen **while active**,
so it saved **64 mL**, under the settled machine counter by 2 mL for this shot.
Its cumulative water accounting still processes positive idle deltas, so the total
gained the full **66 mL**. HA's observed-shot count advanced from 2 to 3.

This locally confirms the terminal-timing concern from the earlier
[upstream audit](../research/AUTONOMOUS_AUDIT_2026-09-26.md). The discrepancy could
include sequential-read timing, cached telemetry and physical flow settling; this
trace does not uniquely separate them. Do not replace the current result with cup
yield or silently edit the stored history.

## Next steps and boundaries

1. Add an independently written regression test and a bounded post-shot
   finalization policy, keeping later shots, cleaning, resets and long polling
   gaps from being assigned to the previous shot. The observed tail exceeds one
   second; a one-second-only policy would miss this example.
2. Repeat with a measured cup weight and independent shot duration for comparison.
3. Investigate the bound-profile mode/bank and remote trigger without changing
   the recipe. The paddle produced the profile flag, **not** the manual flag;
   this narrows the mapping but does not establish which remote coil activates
   the bound bank. No new control command is justified by this observation alone.
