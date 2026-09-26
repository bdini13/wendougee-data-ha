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

## Version 0.1.1 benchmark attempt · 2026-09-22

- The user opened Home Assistant's action UI, selected the loaded
  WENDOUGEE DATA S entry, entered the required `READ ONLY` confirmation and
  invoked `wendougee_data.benchmark_read_only_sampling`.
- The action was registered and resolved the loaded integration entry, proving
  that 0.1.1 loaded beyond the earlier unauthenticated restart checkpoint.
- It returned the generic error `No sampling rate completed successfully`.
  Because 0.1.1 discarded rejected-stage diagnostics, no rate or transport
  limit can be inferred from that message.
- Code review identified two implementation defects: the two-second sampling
  window started before the ESPHome-proxy connection was ready, and the session
  allowed only three seconds where normal integration reads allow fifteen.
- Version 0.1.2 corrects those defects offline, adds 1 Hz and 2 Hz fallback
  stages before 5 Hz and 10 Hz, and returns a privacy-safe failure category.
  It has not yet been deployed or run against the machine.
- No trace file or control command was created by this attempt.

## Version 0.1.2 deployment checkpoint · 2026-09-22

- A fresh full Home Assistant backup completed before installation.
- The target archive matched the locally verified SHA-256 digest, and its
  manifest reported version 0.1.2. The complete 0.1.1 component was preserved
  in a dated rollback directory outside `custom_components/`.
- `ha core check` completed successfully before restart. The restart command
  completed successfully, the frontend returned HTTP 200 and the integration
  loaded with only Home Assistant's standard custom-integration warning.
- The corrected benchmark has not yet been invoked, so no maximum clean rate
  or dynamic field behavior is claimed from this deployment.
- No high-rate trace or control command was sent.

## Version 0.1.2 corrected sampling benchmark · 2026-09-22

- The user invoked the confirmed read-only benchmark with the machine idle.
- The 1 Hz stage returned three complete telemetry/state pairs in 3.001 seconds,
  sustained 0.923 pairs/s and passed the 85% threshold. Mean pair round trip was
  about 460 ms and the maximum was about 558 ms.
- The 2 Hz stage returned six complete pairs in 3.001 seconds, sustained 2.038
  pairs/s and passed. Mean pair round trip was about 441 ms and the maximum was
  about 508 ms.
- The 5 Hz stage returned eight valid complete pairs, sustained 2.456 pairs/s
  and stopped the ladder with `insufficient_cadence`. Mean pair round trip was
  about 410 ms and the maximum was about 434 ms. There was no reported
  transport or protocol failure.
- The integration selected 2 Hz in memory for the next bounded trace. These
  results characterize the current two-read telemetry-plus-state path through
  this ESPHome proxy; they do not establish the maximum telemetry-only rate of
  the machine itself.
- No raw trace or control command was sent.

## Unattended read-only proxy probe · 2026-09-22

- A bounded secondary client completed the encrypted ESPHome API handshake and
  confirmed the proxy was running ESPHome 2026.9.0 with its active-connection,
  remote-cache, raw-advertisement and scanner-state capabilities available.
- A 45-second secondary subscription observed the proxy scanner cycling in
  passive mode but received no mirrored advertisements. Home Assistant retained
  ownership of its normal proxy path.
- One connection attempt targeted only the already configured DATA S address.
  It timed out before GATT discovery; cleanup also timed out. The integration
  logged one telemetry-poll failure at the same time. This cannot distinguish
  single-central contention from the machine being temporarily unreachable.
- The probe stopped after that first uncertain connection attempt. It did not
  subscribe to the machine, send a Modbus request, write a setting, or retry.
  The planned telemetry-only rate test therefore remains pending.
- A later Supervisor check reported Home Assistant healthy and supported. The
  retained recent Core log contained the one coincident failure and no later
  Wendougee failure, but successful polls are not logged and authenticated
  entity state was unavailable, so coordinator recovery is not claimed from
  that check alone.

## Active-connection failure investigation · 2026-09-23

- After the earlier successful 2 Hz benchmark, a later confirmed benchmark
  stopped at its first 1 Hz stage with zero samples and
  `transport_or_protocol_failure`. A config-entry reload also failed. This is
  a change from the previously working path; it is not evidence that the
  machine rejected a Modbus request.
- Home Assistant Core restarts and separate power cycles of the machine and
  proxy did not restore polling. The official mobile app subsequently
  connected and displayed live data, which establishes that the machine's BLE
  peripheral was still operating at that time.
- A raw 30-second proxy observation then saw the exact configured target as a
  single public-address advertiser. Its mean RSSI was -69 dBm, with a -73 to
  -66 dBm range. The proxy API was healthy, its scanner was running, and all
  three active-connection slots were free.
- In that uncontended window, one approved ESPHome V3 connection-only attempt
  stopped after 20 seconds. The proxy discovered the target, stopped scanning,
  promoted a client slot and logged `Connecting`, but never logged
  `Connection open`. Cleanup released the slot. No GATT discovery,
  notification subscription or Modbus request occurred.
- Earlier bounded diagnostics produced the same pre-open timeout with V3 cache
  enabled and with an explicit public address type. ESPHome's legacy V1 route
  is unavailable in this firmware (`V1 connections removed`). These attempts
  therefore do not implicate frame construction, notification parsing or the
  DATA S register map.
- The proxy identifies as an original ESP32 running ESPHome 2026.9.0 with all
  advertised Bluetooth-proxy feature flags. [ESPHome issue 18614][esphome-18614]
  describes an original-ESP32 active-proxy regression introduced in 2026.8,
  but that report reached `Connection open` and failed later. Its fix,
  [pull request 18609][esphome-18609], was merged for 2026.8.1 and 2026.9.0.
  It is relevant background, not an exact match or sufficient reason to claim
  a downgrade will fix this installation.
- A direct Mac comparison could not start because macOS denied Bluetooth
  permission to both local helper app identities before scanning. That result
  is inconclusive and caused no machine connection.
- The current evidence localizes the immediate failure below the application
  protocol: the ESP32 begins a BLE link attempt but does not receive a
  connection-open event. Plausible remaining causes include ESP32/peripheral
  radio interoperability, a machine-side central policy change, or a physical
  RF asymmetry. Distinguishing them requires a controlled second-central or
  alternate-proxy A/B test.

No control, configuration, provisioning, reset, boiler, cleaning, valve,
brew, calibration, bootloader or OTA command was sent during this
investigation.

## Controlled second-proxy A/B · 2026-09-26

- A second original ESP32 was backed up and configured as
  `ESP32 Bluetooth Proxy 2` with the official generic Bluetooth-proxy package
  and ESPHome 2026.9.0. This board has a 26 MHz crystal, so the generic
  40 MHz build produced an invalid-crystal warning and unusable runtime output.
  Rebuilding for its detected 26 MHz crystal restored normal Wi-Fi, Bluetooth
  scanning and the encrypted ESPHome API. The private pre-repair flash image,
  API key and local configuration remain excluded from Git.
- Both proxies advertised their ESPHome services over mDNS. Proxy 2 reported
  the full Bluetooth-proxy feature mask, an active scanner and three free
  connection slots. Home Assistant config-entry adoption was not inspected in
  this session because the previously available authenticated browser session
  had expired; mDNS visibility alone is not claimed as completed HA adoption.
- Sequential 30-second raw, passive observations at the machine location gave
  the following sanitized comparison:

  | Path | All advertisements | Nearby devices | DATA S advertisements | DATA S RSSI min / mean / max |
  | --- | ---: | ---: | ---: | ---: |
  | Proxy 1 | 1,739 | 37 | 244 | -78 / -71.4 / -64 dBm |
  | Proxy 2 | 1,513 | 30 | 207 | -94 / -84.7 / -81 dBm |

  Proxy 2 therefore had a weaker path, but still received roughly seven target
  advertisements per second—ample evidence that failure to notice the
  peripheral was not the active-connection blocker.
- With the diagnostic harness later shown to be incomplete, both proxies then
  reproduced the same bounded connection-only timeout with the exact configured
  public address. Proxy 2 also timed out in the client's
  feature-mask-zero compatibility mode and with its V3 cache hint enabled.
  No characteristic discovery, subscription or machine request was sent.
- Proxy 2's sanitized debug trace progressed through target discovery, scan
  stop, client promotion and `Connecting`. ESP-IDF then logged
  `GATTC_ConfigureMTU GATT_BUSY`; cleanup disconnected and freed the slot. It
  never delivered a successful connection callback.
- This A/B result rules out a unique failure of Proxy 1 and makes simple RSSI
  loss unlikely as the primary cause. The remaining leading branches are an
  already-owned/single-central machine connection and interoperability shared
  by the original-ESP32/ESPHome 2026.9.0 Bluedroid path. A test with all mobile
  app processes fully disconnected is the next non-mutating discriminator.

### Mobile-central exclusion follow-up

- After the official app was force-quit and Bluetooth was disabled on nearby
  mobile devices, the next Proxy 2 V3 connection attempt advanced further: the
  proxy logged `Connection open` and, during timeout cleanup, `Service discovery
  complete`. This proves the ESP32 can establish a physical BLE link when the
  mobile central is excluded.
- The local API client did not receive a successful completion callback before
  its 15-second bound. Its disconnect raced the late service discovery and the
  proxy logged `GATTC_ConfigureMTU GATT_BUSY`. Therefore this attempt does not
  establish a usable read session, but it invalidates the stronger claim that
  the failure is always pre-open.
- An immediate cached retry and a later fresh attempt with a 40-second bound
  did not reopen the link. Both returned to the earlier `Connecting` → timeout
  → `GATT_BUSY` cleanup path. No characteristic read or write was issued.
- The evidence now supports two interacting factors: mobile/single-central
  contention can block initial link establishment, and the machine/proxy pair
  can remain in a sticky post-connection state that prevents a repeatable
  session. A machine power cycle with mobile Bluetooth still disabled is the
  next bounded discriminator.
- Power-cycling the machine alone did not clear the failure. The proxy still
  reported the existing Bluedroid `conn_id=3` in its immediate
  `GATTC_ConfigureMTU GATT_BUSY` cleanup path.
- The user then power-cycled Proxy 2 as well, left the freshly restarted
  machine on and kept mobile Bluetooth disabled. One fresh connection-only
  attempt used a 60-second client bound. The encrypted proxy API was healthy,
  but Bluedroid again scheduled a disconnect immediately after `Connecting`,
  logged `GATTC_ConfigureMTU GATT_BUSY conn_id = 3`, and never reached
  `Connection open`. No characteristic read or write was issued.
- This clean-state reproduction rules out a merely stale machine or proxy
  session as a sufficient explanation. The one earlier `Connection open` was
  real but transient; it has not been made repeatable.

No GATT characteristic write, Modbus request or machine control was sent in
this A/B session.

### Diagnostic correction and rollback-safe firmware matrix

- Source review showed that ESPHome's Bluetooth-proxy cleanup loop disconnects
  reserved BLE links when no API connection owns the proxy's advertisement
  subscription. The standalone connection and read probes authenticated to the
  API and requested a device connection, but did not subscribe to
  advertisements. Their immediate `Disconnect before connected` and subsequent
  `GATTC_ConfigureMTU GATT_BUSY` logs were therefore caused by the diagnostic
  harness, not evidence of an ESPHome or DATA S connection regression.
- The probes were corrected to subscribe before requesting the connection and
  to retain that subscription until after disconnect. Proxy selection is now
  explicit so an A/B command cannot silently use Proxy 1's defaults.
- Proxy 2 was changed only for the approved firmware matrix. Its exact private
  configuration and rollback material were preserved. On ESPHome 2026.7.2 the
  corrected connection-only probe reached `Connection open` and `Service
  discovery complete`; one allowlisted telemetry read returned a CRC-valid
  decoded response in 103.1 ms.
- Proxy 2 was then rebuilt and restored to ESPHome 2026.9.0. Version, name and
  Bluetooth-proxy feature mask were verified after reboot. The same corrected
  connection-only probe completed, and the identical telemetry read returned a
  CRC-valid response in 101.7 ms. The near-equal results do not support a
  2026.7.2-versus-2026.9.0 regression on this path.
- A bounded telemetry-only ladder on restored 2026.9.0 accepted 2, 3, 4, 5 and
  8 Hz. The 8 Hz stage completed 24 samples in 3.00 seconds at 8.10 reads/s,
  with a 122 ms mean and 269 ms maximum round trip. The next 10 Hz stage
  completed 24 samples in 3.06 seconds at 8.01 reads/s and failed the 85%
  cadence threshold. Eight hertz is therefore the fastest clean rate measured
  for the single-telemetry-read path in this short test; it is not a guarantee
  for paired reads, shot conditions or long-duration operation.
- The telemetry ladder also passively received nine event-characteristic
  frames before sampling. All nine were checksum-valid, nine-byte opcode
  frames using opcode `0x83`, a zero reserved byte and a one-byte binary marker
  that alternated between `0` and `1`. The observed checksum is the low byte of
  the sum of all preceding bytes plus one. Event timestamps were not retained,
  so the marker's cadence and meaning remain unknown. A strict passive-only
  parser now covers this evidence without constructing an FF55 command. Raw
  frames and device identifiers remain in owner-only ignored evidence files
  and are not published here.
- A follow-on 60-second event-only subscription through Proxy 2 captured 19
  additional frames without a Modbus request or FF55 command. All 19 passed the
  new strict parser and the binary marker alternated throughout. Marker `0`
  recurred at a 6.019-second median period and marker `1` at 5.972 seconds.
  The usual phase was `1`, then `0` about two seconds later, then the next `1`
  about four seconds later. One pair arrived together after a longer gap, so
  proxy delivery can obscure exact device timing. The result supports the
  upstream heartbeat label but does not establish marker semantics.

Only allowlisted FC03 telemetry reads were sent in the matrix. No configuration
write, boiler, brew, cleaning, calibration, reset or firmware command was sent
to the espresso machine. Proxy 2 firmware changes were limited to the approved
test and restoration.

### Home Assistant recovery and first successful private trace

- Home Assistant's configuration check completed successfully, followed by a
  normal Core restart. The host remained on HA 2026.9.1; no host reboot or
  integration redeployment was needed.
- After restart, all 22 enabled WENDOUGEE DATA S entities were available. One
  entity remained `unknown` because its observed-history event has not yet
  occurred; no entity was `unavailable`.
- The approved paired-read benchmark was rerun through HA. It accepted 1 Hz and
  2 Hz, then rejected 5 Hz for insufficient cadence after sustaining 2.22
  complete telemetry/state pairs/s with a 441 ms mean and 532 ms maximum round
  trip. The integration again selected 2 Hz.
- `capture_read_only_trace` then completed for the first time: 20 correlated
  telemetry/state samples over 10.00 seconds at 1.99 Hz. The owner-only file is
  mode `0600`, marked `private_unreviewed`, and remains outside Git.
- The idle trace held brew temperature from 92.3–92.6 °C and steam temperature
  from 27.3–27.4 °C. Pressure, dispensed volume and elapsed brew time remained
  zero; operating state remained `idle` with no unknown bits. These internally
  consistent values are not a substitute for physical calibration.

No control or configuration command was sent during recovery, benchmarking or
trace capture.

### Unattended 180-second idle soak

- A second private trace requested 360 complete telemetry/state pairs over
  180.00 seconds at the selected 2 Hz rate. All 360 samples completed at
  2.003 Hz; the median interval was 0.508 seconds, the 95th percentile was
  0.638 seconds, the maximum was 0.820 seconds and no interval exceeded one
  second.
- Round trips ranged from 337–729 ms with a 458 ms mean. Brew temperature
  ranged from 92.0–96.6 °C and steam temperature from 28.6–28.8 °C. Pressure,
  flow, dispensed volume, brew time, pump time, scale values and weight rate
  remained zero. The machine stayed `idle`, with no water alarm or unknown
  operating-state bits.
- The private REST helper's original 45-second socket timeout expired because
  the service call is synchronous, but Home Assistant continued and safely
  completed the full trace. The ignored helper was adjusted to allow the
  requested duration plus cleanup margin. The resulting owner-only file
  remained mode `0600` and outside Git; this was not a sampling or BLE failure.

No control, configuration or FF55 command was sent during this soak.

## What this proves

- HA shared Bluetooth can discover and connect to this DATA S through this
  ESPHome proxy.
- The integration's four fixed read transactions and response validation work
  on the real machine through the deployed HA path.
- The current configuration and operating-state decoders produce internally
  consistent values for this idle, boilers-off snapshot.
- The one-shot capture and restart guard operated as designed.
- The installed proxy path can sustain 2 Hz complete telemetry/state pairs in
  a bounded idle HA benchmark and a three-minute idle soak without a reported
  protocol or transport failure. The corrected standalone path additionally
  sustained 8 Hz for telemetry alone on restored ESPHome 2026.9.0.
- The exact machine emits a checksum-valid, periodic opcode-`0x83` FF55 marker
  without receiving FF55 initialization in these sessions. Its binary payload
  alternates and has an approximately six-second same-marker period, but its
  meaning remains unproven.
- The apparent standalone connection regression was a diagnostic ownership
  error: an authenticated proxy client must also retain an advertisement
  subscription while it owns BLE links.

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
- The short 8 Hz telemetry-only result does not establish sustained shot-load
  behavior or raise the HA paired-read benchmark's selected 2 Hz rate.
- The direct Python/Bleak client remains untested on the hardware.
- No real frame is approved as a public fixture yet.

## Recommended next gate

Run the selected 2 Hz paired trace during one manually initiated normal shot
and compare dynamic values with physical references. Keep 8 Hz as a provisional
telemetry-only ceiling until a longer shot-load test confirms it. Control work
remains a separate, freshly approved phase.

[esphome-18609]: https://github.com/esphome/esphome/pull/18609
[esphome-18614]: https://github.com/esphome/esphome/issues/18614
