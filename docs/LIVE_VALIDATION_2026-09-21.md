# WENDOUGEE DATA S live validation · 2026-09-21 onward

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

- Target: WENDOUGEE DATA S; firmware and installed E-Bar version not yet
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
- A short post-restart smoke window covered four consecutive 30-second polling
  intervals with Core healthy and no Wendougee coordinator failure logged. This
  is not a long-duration soak test.
- A later bounded idle soak sampled Home Assistant once per minute for 15
  consecutive checkpoints while the installed 0.0.7 integration continued its
  30-second polling. Core remained healthy, the config entry and all 11
  entities remained present, and the Wendougee coordinator logged no failure.
  This does not exercise restart, deliberate disconnect, unload or app
  contention and is still not a long-duration soak.

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

## Version 0.0.8 deployment follow-up

Later the same day, version 0.0.8 was deployed to the same HA 2026.9.1 target:

- A fresh full HA backup completed before any component file changed. The
  previous component directory was also preserved in a hidden rollback folder.
- The built archive's SHA-256 matched before extraction, its manifest reported
  0.0.8, and `ha core check` passed before restart.
- After restart, HA reported version 0.0.8, one config entry, one device and all
  23 entities. Six remain enabled and 17 provisional configuration/state or
  measurement entities are disabled by default.
- Schema-2 diagnostics reported a successful current sample with no last
  error, both boilers disabled, water-alarm detection enabled, idle operating
  state and no unknown operating-state bits. The temperatures were 19.7 °C
  brew and 23.6 °C steam; other activity values remained zero.
- The post-upgrade observation extended beyond the coordinator's ten-minute
  configuration-refresh cadence. Five additional one-minute checkpoints all
  found Core healthy, 23 registered entities, no Wendougee failure line and an
  unchanged private-capture timestamp.
- A normal config-entry reload completed successfully. Post-reload diagnostics
  again showed a successful current sample and the same internally consistent
  idle/configuration state. The private raw capture was not repeated.
- No control, provisioning, reset, boiler, cleaning, valve, brew, calibration,
  bootloader or OTA command was sent.

This validates one restart, scheduled split-cadence reads and one
unload/reload cycle. It is not evidence for deliberate proxy loss, official-app
contention, a disabled entry, long-duration reliability or physical units.

## Later unattended read-only follow-up

At 19:09 and 19:16 EDT, two downloaded diagnostics snapshots from the installed
0.0.8 integration reported a successful latest poll, no retained error, both
boilers disabled, idle operation and no unknown state bits. Brew temperature
was 18.5 °C in both snapshots; steam temperature changed from 22.6 °C to
22.5 °C. The changed decoded value is evidence that the later snapshot was not
an identical saved document, but it is not a calibrated temperature check.

Home Assistant's Core log also showed two isolated coordinator failures that
day, first at 13:13 and last at 18:26 EDT. The healthy 19:09 and 19:16
snapshots establish subsequent automatic recovery; the available log entry did
not expose a sanitized root cause. No failure was deliberately induced. A
separate passive advertisement observer on the Mac could not establish its own
proxy API session during this follow-up, so that attempt supplies no additional
advertisement evidence. No machine control or configuration write was sent.

This follow-up motivated schema-3 diagnostics in version 0.0.9: UTC timestamps
and success, failure and consecutive-failure counters for the current
integration runtime.

## Version 0.0.9 deployment follow-up · 2026-09-22

Version 0.0.9 was subsequently deployed to the same HA 2026.9.1 target:

- A new full HA backup completed before the installed component changed. The
  0.0.8 component directory and the 0.0.9 staging directory were retained in a
  rollback archive outside `custom_components/`.
- The archive's SHA-256 matched the local build, its manifest reported 0.0.9,
  and `ha core check` passed before the corrected restart. The installed build
  corresponds to commit `664f5f2`; the deployed ZIP's SHA-256 is
  `a0b82a2381600dd08bc8b785c7a8eeed6ba209a1eaa5a3d2e7d814e417bdae08`.
- The first restart did not load the integration because hidden staging and
  rollback directories had been left directly beneath `custom_components/`.
  Home Assistant tried to import their leading-dot directory names as custom
  integrations. Moving those deployment-only directories outside the scan path
  fixed the issue; no integration source change or machine transaction was
  required. A second `ha core check` passed before restarting again.
- After the corrected restart, HA reported version 0.0.9, one device and all 23
  entities. No new Wendougee setup or coordinator error appeared; the only
  fresh Wendougee log entry was HA's standard custom-integration warning.
- The first schema-3 diagnostic reported two successful polls, zero failed or
  consecutive-failed polls, a successful current sample and no retained error.
  After more than one 30-second interval, the second diagnostic reported four
  successful polls with the failure counters still at zero and a later UTC
  success timestamp.
- Both diagnostics retained the expected idle state, both boiler-enable flags
  off and no unknown operating-state bits. No baseline action was invoked.
- No control, configuration write, provisioning, reset, cleaning, valve, brew,
  calibration, bootloader or OTA command was sent.

This proves that schema-3 runtime counters distinguish a fresh, advancing live
sample from a stale snapshot on the installed target. It remains only a short
idle observation, not a long-duration reliability test.

## Version 0.1.0 deployment follow-up · 2026-09-22

Version 0.1.0 was installed on the same HA 2026.9.1 target:

- A new full backup named for the pre-0.1.0 state completed before files changed.
  The complete 0.0.9 component directory remains in a rollback directory outside
  `custom_components/`.
- The built ZIP and separately installed dashboard image/source passed SHA-256
  verification. The manifest reported 0.1.0 and `ha core check` passed before
  restart.
- After restart, the entry title and device name were `WENDOUGEE DATA S`; the
  device reported manufacturer `Wendougee`, model `DATA S`, and all 30 expected
  entities were registered.
- The source-controlled Espresso storage dashboard was created with 32 built-in
  cards. Its eight independent schedule/setpoint helpers report 07:00–09:00,
  92 °C brew and 126 °C steam. Both schedule toggles are off and no automation
  or callable machine control exists.
- Nine provisional read-only configuration/state entities used by the dashboard
  were enabled on this target, followed by a successful config-entry reload.
- Six schema-4 checkpoints observed successful-poll counters advance from five
  to eleven with zero failed or consecutive-failed polls. Each sample was idle,
  had no unknown operating bits and did not fabricate shot or cleaning activity.
- Home Assistant's in-memory system log contained no entry from the integration
  after the deployment/reload checks. The served dashboard artwork matched the
  source checksum.
- No baseline action, control, configuration write, boiler, brew, cleaning,
  profile, valve, provisioning, reset, calibration, bootloader or OTA command
  was sent.

This validates installation, restart, entry-title migration, entity registration,
dashboard storage, helper defaults, config-entry reload and a short advancing
read-only polling window. It is not a physical comparison, event-transition test
or long-duration/disconnect/contention soak.

## Version 0.1.1 deployment checkpoint · 2026-09-22

Version 0.1.1 was installed to prepare a bounded dynamic read-only observation:

- A fresh full backup completed before the installed component changed.
- The locally built archive passed SHA-256 verification on the target and its
  manifest reported 0.1.1. The complete 0.1.0 component was moved to a dated
  rollback directory outside `custom_components/`.
- `ha core check` completed successfully before restart. Home Assistant then
  restarted, the frontend returned HTTP 200, and the Supervisor observer
  reported connected, supported and healthy.
- The deployment added only explicitly confirmed read-only actions: a fail-closed
  5 Hz → 10 Hz benchmark and a bounded private trace capture. It added no control
  transport or entity.
- The authenticated browser session became unavailable after restart. Therefore
  service registration, config-entry state, entity availability and the sampling
  benchmark were not claimed as verified in this checkpoint.
- No high-rate benchmark, trace capture, boiler, brew, cleaning, profile, valve,
  provisioning, reset, calibration, bootloader or OTA command was sent.

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
- Firmware/model-detail queries, official-app coexistence, deliberate
  disconnect recovery, disabled-entry behavior and long-duration polling have
  not been validated. One restart and one config-entry reload did succeed.
- The direct Python/Bleak client remains untested on the hardware.
- No real frame is approved as a public fixture yet.

## Recommended next gate

Run an attended, read-only observation while the user operates the machine
normally. Compare both temperatures and state on the display, then observe one
manually initiated shot while the integration only reads. Follow with
deliberate proxy-loss/app-contention checks and an extended soak. Control work
remains a separate, freshly approved phase.
