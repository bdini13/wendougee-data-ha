# Roadmap

Last reviewed: 2026-09-21. The goal is a well-understood, local-first DATA S integration—not an unqualified promise that every hidden firmware function can or should be remotely controlled.

## 1. Research and offline foundation — implemented

- [x] Review existing exact-machine projects and record pinned sources/license boundaries.
- [x] Establish the 59-item capability map and separate upstream claims from local proof.
- [x] Implement CRC, allowlisted reads, configuration/state/telemetry decoding and strict response validation.
- [x] Test fragmentation, malformed packets, timeouts, cancellation and stale/duplicate responses.
- [x] Implement read-only HA discovery, confirmed setup, sensors, recovery and diagnostics.
- [x] Build a self-contained ZIP and test it independently of the development checkout.
- [x] Add a versioned private evidence envelope and approval-gated baseline reader.
- [x] Add an explicitly confirmed four-read baseline action for HA's shared Bluetooth/proxy route.

Evidence: 90 protocol/package tests plus 29 HA framework tests at this checkpoint. One earlier native telemetry read and the 2026-09-21 HA-proxy baseline have different limits; see the [sanitized live record](docs/LIVE_VALIDATION_2026-09-21.md).

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
- [ ] Test deliberate disconnects, unavailable state, app contention and bounded polling load under failure.
- [ ] Run a soak test and verify unload/disable stops polling and releases connections.
- [ ] Review diagnostics and any third-party debug logs for identifier leakage.
- [ ] Physically validate configuration/status semantics, then review defaults, options and usability refinements.

Exit criterion: documented recovery behavior and a usable monitoring integration on the actual installation. No shot-rate logging or hardware-independent compatibility claims without evidence.

## 4. Carefully gated controls

- [ ] Validate conservative setting ranges, polarity, response correlation, readback and persistence.
- [ ] Add explicitly opt-in boiler/configuration controls only after supervised validation.
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

No dates are promised. Hardware access, protocol ambiguities and safety findings can change priorities. Use [the label catalog](.github/labels.json) to classify issues; its 12 labels are available on [GitHub](https://github.com/bdini13/wendougee-data-ha/labels) as of 2026-09-20.
