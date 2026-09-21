# DATA S live validation · 2026-09-21

This is a sanitized record of the first complete Home Assistant read-only
validation through the installed ESPHome Bluetooth proxy. It contains no
Bluetooth address, proxy address, API credential, device-derived stable ID or
raw request/response frame.

## Scope and safeguards

- Bobby explicitly approved read-only testing while away from the machine.
- The DATA S was powered on with both boilers intentionally disabled.
- Only the four fixed allowlisted reads were sent: telemetry, configuration,
  water-alarm enable and operating state.
- No boiler, brew, cleaning, profile, valve, provisioning, reset, calibration,
  bootloader, OTA or other control command was sent.
- The integration created its attempt marker before the baseline, wrote one
  owner-only private capture, and did not repeat the baseline after restart.
- The private envelope and raw frames remain outside Git.

## Environment and transport result

- Target: Wendougee DATA S; firmware and installed E-Bar version not yet
  recorded.
- Home Assistant: 2026.9.1.
- Integration package: 0.0.7.
- Bluetooth path: Home Assistant shared Bluetooth through an ESPHome active
  proxy using the official generic proxy package.
- The proxy's raw advertisement stream saw the `WDG_Data_*` target among other
  nearby devices. The proxy reported its scanner running in active mode.
- Home Assistant initially could not consume the proxy because its existing
  ESPHome config entry lacked the API encryption key required by the current
  proxy firmware. Restoring that entry from the already-installed ESPHome
  configuration resolved discovery without reflashing the proxy.
- All four responses passed the local slave/function/byte-count/length/CRC
  validation. No Modbus exception was returned.
- One config entry, one device and all 11 expected read-only entities were
  registered after a clean restart. Six entities are enabled by default; five
  provisional measurements remain disabled by default.

## Sanitized decoded baseline

### Telemetry

| Field | Decoded value |
|---|---:|
| Brew temperature | 20.1 °C |
| Steam temperature | 23.9 °C |
| Pump pressure | 0.0 bar |
| Pumped volume | 0 mL |
| Scale weight | 0.0 g |
| Elapsed brew time | 0.0 s |
| Pump-active time | 0 s |
| Flow | 0 mL/s |
| Weight rate | 0.0 g/s |
| Water-shortage alarm asserted | No |

### Configuration and operating state

| Field | Decoded value |
|---|---:|
| Steam heating enabled | No |
| Brew heating enabled | No |
| Steam target | 126 °C |
| Brew target | 92 °C |
| Manual time | 30.0 s |
| Manual pressure | 9.0 bar |
| Cleaning time / rest / repetitions | 5.0 s / 5.0 s / 3 |
| Heating mode | Full speed |
| Water-alarm detection enabled | Yes |
| Operating state | Idle |
| Profile / manual / cleaning / free-variable active | No / No / No / No |
| Unknown operating-state bits | None |

The two boiler-enable results agree with the user's stated starting condition.
Temperatures were plausible for a cold machine, and all activity fields were
consistent with idle. This agreement is useful but is not an independent
physical measurement.

## What this proves

- HA shared Bluetooth can discover and connect to this DATA S through this
  ESPHome proxy.
- The integration's four fixed read transactions and response validation work
  on the real machine through the deployed HA path.
- The current configuration and operating-state decoders produce internally
  consistent values for this idle, boilers-off snapshot.
- The one-shot capture and restart guard operated as designed.

## What remains unproven

- No value was compared with the physical display, a stopwatch, a pressure
  reference, a graduated volume or a scale.
- Zero activity values do not validate dynamic units, signed scale behavior or
  shot-state transitions.
- Boiler-enable agreement does not validate write polarity or authorize a
  control test.
- Firmware/model-detail queries, official-app coexistence, reconnect recovery,
  unload behavior and long-duration polling have not been validated.
- The direct Python/Bleak client remains untested on the hardware.
- No real frame is approved as a public fixture yet.

## Recommended next gate

Run an attended, read-only observation while the user operates the machine
normally. Compare both temperatures and state on the display, then observe one
manually initiated shot while the integration only reads. Follow with bounded
idle reconnect and soak tests. Control work remains a separate, freshly
approved phase.
