# Roadmap

Last reviewed: 2026-09-26. The goal is a well-understood, local-first WENDOUGEE DATA S integration—not an unqualified promise that every hidden firmware function can or should be remotely controlled.

## 1. Research and offline foundation — implemented

- [x] Review existing exact-machine projects and record pinned sources/license boundaries.
- [x] Establish the 60-item capability map and separate upstream claims from local proof.
- [x] Implement CRC, allowlisted reads, configuration/state/telemetry decoding and strict response validation.
- [x] Test fragmentation, malformed packets, timeouts, cancellation and stale/duplicate responses.
- [x] Implement read-only HA discovery, confirmed setup, sensors, recovery and diagnostics.
- [x] Build a self-contained ZIP and test it independently of the development checkout.
- [x] Add a versioned private evidence envelope and approval-gated baseline reader.
- [x] Add an explicitly confirmed four-read baseline action for HA's shared Bluetooth/proxy route.
- [x] Add a passive-only FF55 decoder from exact-machine evidence, with strict checksum/length validation and no frame construction or write path.
- [x] Capture a timestamped 60-second event-only window: 19/19 opcode-`0x83` frames decoded, the marker alternated, and each value recurred about every six seconds without any FF55 command.

Evidence: 117 protocol/package tests plus 40 HA framework tests at this checkpoint. One earlier native telemetry read and the 2026-09-21 HA-proxy baseline have different limits; see the [sanitized live record](docs/LIVE_VALIDATION_2026-09-21.md).

## 2. Hardware validation — next gate

- [ ] Record machine model, firmware and installed official-app version, without publishing identifiers.
- [ ] Reproduce the telemetry read through the Python client with supported Bluetooth permissions.
- [ ] Compare temperatures, pressure, timing, flow and scale values with appropriate physical references.
- [ ] Save reviewed, sanitized fixtures with provenance; distinguish captured and synthetic data.
- [x] Verify known configuration and operating-state read framing/decoding during a separately approved session.
- [ ] Resolve unknown units/status flags before changing entity defaults.

Exit criterion: repeatable reads with documented limits, physical comparisons and no unaccounted-for device changes. Use the [batched validation plan](docs/VALIDATION_PLAN.md); no blind probing or unsafe fault induction.

## 3. HA pilot and operational reliability

- [x] Back up the target HA configuration and obtain explicit deployment approval.
- [x] Verify that the target HA host has registered the ESPHome proxy as a remote Bluetooth adapter.
- [x] Test discovery, telemetry, baseline reads and entity registration through the actual HA/ESPHome proxy path.
- [x] Add provisional read-only configuration and operating-state entities, disabled by default.
- [x] Complete a bounded 15-minute idle soak on 0.0.7 with no coordinator failures.
- [x] Deploy 0.0.8 after a fresh full backup; validate restart, the split polling cadence and a config-entry reload.
- [x] Observe recovery after two naturally occurring isolated polling failures; add privacy-safe per-runtime poll-health diagnostics for more decisive soak evidence.
- [x] Deploy 0.0.9 after a fresh full backup; verify one device, 23 entities and advancing schema-3 poll counters with zero failures after the corrected restart.
- [x] Build and deploy 0.1.0 after a fresh full backup; verify canonical naming, 30 entities, schema-4 activity/poll diagnostics, dashboard/helpers, restart and config-entry reload.
- [x] Build, offline-test and install 0.1.1's fail-closed 5 Hz → 10 Hz sampling benchmark and private bounded trace action after a fresh backup and successful configuration check.
- [x] Diagnose the first 0.1.1 benchmark failure and build 0.1.2 with connection setup excluded from the sampling window, a 15-second proxy session timeout, a 1 → 2 → 5 → 10 Hz ladder and returned stage diagnostics.
- [x] Deploy 0.1.2 after a fresh full backup, checksum verification and configuration check; verify a healthy restart.
- [x] Repeat the corrected read-only benchmark; select 2 Hz for complete telemetry/state pairs after 5 Hz sustained about 2.46 pairs/s and failed only the cadence threshold.
- [x] Restore repeatable active BLE connection establishment in the standalone diagnostic path. ESPHome requires the owning API client to subscribe to advertisements; omitting that subscription caused the proxy cleanup loop to schedule the apparent immediate disconnect.
- [x] Run a controlled alternate-proxy A/B test before changing machine state. Proxy 2 receives the target reliably, and the corrected harness connects and completes service discovery.
- [x] Complete a rollback-safe proxy firmware matrix on Proxy 2. ESPHome 2026.7.2 and 2026.9.0 both connected and returned valid telemetry at about 103 ms and 102 ms respectively; Proxy 2 was restored to verified 2026.9.0.
- [x] Benchmark telemetry alone through Proxy 2. The bounded ladder accepted 2, 3, 4, 5 and 8 Hz, then rejected 10 Hz after sustaining about 8.01 reads/s; private raw evidence remains excluded from Git.
- [x] Confirm the installed HA entry recovers after a checked Core restart. All 22 enabled entities became available, and the rerun paired-read benchmark again selected 2 Hz.
- [x] Complete the first private bounded hardware trace: 20 correlated idle samples over 10.00 seconds at 1.99 Hz, stored owner-only with raw evidence excluded from Git.
- [x] Complete a 180-second idle soak at the selected paired-read rate: all 360 samples completed at 2.003 Hz, with no interval over one second and private raw evidence excluded from Git.
- [x] Capture one user-initiated normal paddle shot at 2 Hz without a control command: 360 valid pairs, profile state `0x2`, 22.4 s timer. See [shot record](docs/PADDLE_SHOT_2026-09-26.md).
- [ ] Fix last-shot finalization: this capture recorded 64 mL while active, but the machine counter settled at 66 mL after idle. Preserve boundaries against later shots, cleaning and counter resets.
- [ ] Retain at least five seconds after that shot; resolve delayed terminal volume, reset/latching and sequential telemetry/state timing before claiming final shot totals.
- [ ] Test deliberate disconnects, unavailable state, app contention and bounded polling load under failure.
- [ ] Run a soak test and verify unload/disable stops polling and releases connections.
- [ ] Review diagnostics and any third-party debug logs for identifier leakage.
- [ ] Physically validate configuration/status semantics, then review defaults, options and usability refinements.

Exit criterion: documented recovery behavior and a usable monitoring integration on the actual installation. No shot-rate logging or hardware-independent compatibility claims without evidence.

## 4. Carefully gated controls

- [x] Implement opt-in attended cleaning with fresh stored-parameter reads, unchanged settings, exact pulse echoes, full-window observation and durable uncertainty guard (0.3.0).
- [x] Perform one supervised cleaning start after fresh readiness approval; observe cleaning then idle and verify all configuration unchanged (2026-09-26).
- [x] Compare the successful cleaning-state test with the owner's physical observation: all three repetitions and normal completion confirmed (2026-09-26).

- [ ] Validate conservative setting ranges, polarity, response correlation, readback and persistence.
- [x] Implement opt-in boiler enable switches and a stored mode-2 profile start button, with synthetic transaction tests and fail-closed guards (0.2.0, requested by owner).
- [ ] Commission those controls with supervised exact-machine write/readback and shot observation before routine use; temperature controls and scheduling remain withheld.
- [ ] Resolve remote activation of the **paddle-bound** recipe specifically. The optional app-selected-profile action remains disabled on the target; it is not the requested default-shot control.
- [ ] Validate profile layout, slot capacity and complete readback; keep upload separate from activation.
- [ ] Resolve toggle-versus-stop semantics and app/physical-control races before brew/clean actions.
- [ ] Add supported accessory features after resolving FF55 direction/context conflicts.

Exit criterion for **each** control: original tests, exact-machine evidence, documented prerequisites, failure behavior and explicit activation policy. A timed-out toggle must never be blindly retried. Mode 4 and unverified slots remain rejected until independently validated.

Raw valves, PID/calibration, factory reset, bootloader and OTA remain research-only; learning their meaning does not imply exposing them as HA controls. Remote stop is not a hardware emergency stop.

## 5. Release readiness

- [ ] Complete the installed official-app feature inventory and account for unsupported/app-only features.
- [ ] Broaden tests using sanitized real fixtures and documented compatibility cases.
- [ ] Add release packaging checks, HACS validation, versioning and release notes.
- [ ] Perform an independent code/safety review; review AI-assisted assumptions explicitly.
- [ ] Publish a release only with accurate support and hardware-evidence claims.

No dates are promised. Hardware access, protocol ambiguities and safety findings can change priorities. Use [the label catalog](.github/labels.json) to classify issues; its 14 labels are available on [GitHub](https://github.com/bdini13/wendougee-data-ha/labels) as of 2026-09-26.
