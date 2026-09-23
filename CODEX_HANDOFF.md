# Codex handoff: WENDOUGEE DATA S Home Assistant

## Mission

Build a local-first, cloud-independent Home Assistant integration for Bobby's WENDOUGEE DATA S. Treat the espresso machine as safety-relevant physical equipment: read-only telemetry first; every control must be explicit, constrained, tested, and disabled by default until validated on real hardware.

## Workspace

- Mac project root: `~/Documents/Codex/CodexProjects/wendougee-data-ha`
- Ignored upstream clones: `research/upstream/`
- Ignored private captures: `research/artifacts/private/captures/`
- Public protocol synthesis: `docs/protocol.md`
- Source inventory: `research/UPSTREAM_SOURCES.md`
- Capability map and evidence levels: `CAPABILITIES.md`
- Prioritized validation batches and unresolved conflicts: `docs/VALIDATION_PLAN.md`
- GitHub: `https://github.com/bdini13/wendougee-data-ha`

The Mac has the ChatGPT desktop app and existing Codex authentication state under `~/.codex/`, but the standalone `codex` CLI is not currently on `PATH`. The folder is ready to open as a Codex project; do not assume CLI availability.

## Critical discovery: do not reverse-engineer from zero

Substantial exact-machine work already exists:

1. **GeeFlow** is a Kotlin Multiplatform controller whose only real tested machine is the WENDOUGEE DATA S. It already implements BLE discovery, Modbus framing, telemetry, profile execution, boiler settings, cleaning, smart-scale support, and safety warnings.[4][5][6]
2. **LitaLite** documents static analysis of official Android app v3.1.0 plus live LITA-BA tests. It identifies the GATT UUIDs, Modbus RTU transport, register map, command frames, profile writes, telemetry, and FF55 side channel.[1][2]
3. **Crema** is a native Swift client that targets LITA-BA/LITA-BR/DATA-S with transport abstractions, Modbus, FF55 handling, telemetry, profile logic, and tests. Its comments trace live verification to LITA-BA, so it is not independent DATA-S hardware evidence.[3]
4. **DecentEbar** automates the official Android E-Bar UI through AccessibilityService rather than replacing its BLE client; it is useful for UI/profile semantics and operational comparison.[7]

The best path is a clean Python implementation based on independently verified protocol facts—not another blind packet-capture campaign.

Read `research/LITALITE_CREMA_REVIEW.md` before borrowing any design. It records safety gaps, parser limitations, the failed Crema test invocation, and the licensing boundary.

## Confirmed transport baseline

### Locally observed on Bobby's DATA S

- Advertisement name matches `WDG_Data_*`.
- The BLE radio identifies as Espressif.
- Advertisement TX-power field is `+9 dBm`.
- Raw nRF captures exist locally but are intentionally excluded from Git because they contain device-specific addresses.
- A supervised direct connection on 2026-09-20 verified the expected service and both communication characteristics.
- The documented 22-register telemetry request returned a CRC-valid response on the DATA S. The idle response decoded to brew `94.6 °C`, steam `27.2 °C`, no water alarm, and zero pressure/flow/volume. That frame was not retained as a fixture; physical-display comparison remains to be performed.

### Upstream protocol evidence

- Custom service: `00010203-0405-0607-0809-0a0b0c0d1910`.[1]
- Modbus read/write/notify characteristic: `00010203-0405-0607-0809-0a0b0c0d2b10`.[1]
- FF55 event/status characteristic: `00010203-0405-0607-0809-0a0b0c0d2c10`.[1]
- Primary control protocol is Modbus RTU, slave address `0x01`, with CRC16-Modbus transmitted low byte first.[1]
- Upstream testing reports no pairing, PIN, or authentication handshake for direct GATT access.[1]
- GeeFlow independently contains matching command frames and register constants for the DATA S.[4][5][6]

### High-value telemetry map

The table below combines LitaLite's register notes with GeeFlow's DATA-S parser offsets.[1][20]

| Register | Meaning | Scale |
|---:|---|---|
| 1405 | Elapsed brew time | deciseconds |
| 1406 | Water-level alarm | nonzero = alarm |
| 1408 | Steam-boiler temperature | value / 10 °C |
| 1409 | Brew-boiler temperature | value / 10 °C |
| 1410 | Brew pressure | value / 10 bar |
| 1411 | Dispensed volume | mL |
| 1412 | Scale weight | value / 10 g |
| 1417 | Pump-active time | seconds |
| 1422 | Instantaneous flow | raw mL/s; upstream flags this as needing further controlled confirmation |
| 1423 | Weight rate | value / 10 g/s |

The main safe telemetry request is holding-register read `01 03 05 7C 00 16 05 10`, which requests 22 registers starting at 1404.[1]

## Safety boundary

Until Bobby explicitly approves live control testing:

- Allowed: scanning, service discovery, notification subscription, safe Modbus reads, parser development, offline replay, tests.
- Not allowed: coil/register writes, brew start/stop, boiler changes, cleaning cycles, raw valve commands, factory reset, provisioning, OTA, or bootloader entry.
- Never send `AT+RST`.
- Never copy raw captures, Bluetooth addresses, session tokens, APKs, credentials, or device identifiers into Git.
- Assume a single active BLE central; disconnect/force-close the official app before direct-client tests.

## Licensing boundary

- `GeeFlow`: GPL-3.0. Study behavior and protocol facts, but copying/adapting its code into this MIT project may impose GPL obligations.
- `LitaLite`: no repository license was detected. Treat as read-only research; do not copy code or prose.
- `Crema`: no repository license was detected. Treat as read-only research; do not copy code.
- `DecentEbar`: PolyForm Noncommercial 1.0.0 with required notice. Do not copy code into this MIT project.
- `hacs-xbloom`: MIT; useful as a modern local-BLE Home Assistant architectural reference.[8]
- `home_assistant_delonghi_primadonna`: Apache-2.0; useful as a coffee-machine BLE integration reference.[9]

Protocol facts and on-wire observations should be independently expressed and backed by tests; preserve attribution in research documentation.

## Recommended architecture

### 1. Pure protocol/client package

Keep Home Assistant dependencies out of the core:

```text
src/wendougee_data/
  const.py
  crc.py
  modbus.py
  frames.py
  telemetry.py
  client.py
  exceptions.py
```

Responsibilities:

- CRC16-Modbus
- request builders and response validation
- notification stream reassembly
- typed telemetry decoding
- transport protocol/interface so tests use a fake client
- serialized request/response access with timeouts
- reconnect-safe subscriptions

Use `bleak` for an initial standalone client.[15] Home Assistant owns and shares Bluetooth scanning, so the integration layer must use HA's Bluetooth APIs rather than creating an independent long-running scanner.[16][17]

### 2. Home Assistant integration

```text
custom_components/wendougee_data/
  __init__.py
  bluetooth.py
  config_flow.py
  const.py
  coordinator.py
  diagnostics.py
  manifest.json
  sensor.py
  binary_sensor.py
  strings.json
  translations/en.json
```

- Keep the existing `WDG_Data_*` Bluetooth manifest matcher; HA's manifest supports Bluetooth discovery matchers.[18]
- Config flow should confirm discovery, derive a stable unique ID without exposing a raw address, and prevent duplicates.
- Start with read-only sensors: steam temperature, brew temperature, pressure, volume, flow, elapsed time, connection state, and any verified boiler/water alarms.
- Add control entities only in a later, separately approved phase.
- Follow current Home Assistant Bluetooth and quality-scale guidance.[16][17][19]

### 3. Testing strategy

Use strict RED → GREEN → REFACTOR:

1. CRC fixtures from known frames.
2. Modbus request builders.
3. response CRC/length/function validation.
4. telemetry decoding from byte fixtures.
5. fragmented/coalesced notification handling.
6. timeout, disconnect, malformed frame, and exception responses.
7. config-flow discovery and duplicate prevention.
8. coordinator reconnect and unavailable-state behavior.

No production behavior without a failing test first.

## First Codex task

**Status update, 2026-09-21:** the pure read-only slice below is complete and offline-tested. A native CoreBluetooth helper obtained one idle telemetry response, and the HA integration later completed an approved four-read baseline through the installed ESPHome proxy. The direct Python/Bleak client remains unvalidated. The source-first capability audit is in `CAPABILITIES.md`; use `docs/VALIDATION_PLAN.md` and `docs/LIVE_VALIDATION_2026-09-21.md` for subsequent work rather than repeating the initial implementation or claiming all telemetry semantics are validated.

**Offline foundation update:** `reads.py`, `state.py`, and `session.py` provide allowlisted configuration/status reads, strict framing, typed decoders, and failure-quarantined serialized sessions. The standalone telemetry client uses that session through a tested fake-Bleak adapter. See `docs/OFFLINE_CORE.md`. Real fixtures and physical comparison remain pending.

**HA implementation update:** `docs/HOME_ASSISTANT.md` describes the read-only integration and build. Version 0.0.9 is installed and uses shared Bluetooth, confirmed setup, 23 read-only entities, split runtime/configuration polling, failure recovery, cancellation cleanup and allowlisted schema-3 diagnostics with per-runtime poll timestamps and success/failure counters. Normal polling reads telemetry plus operating state; every twentieth poll refreshes the complete fixed configuration set. An explicitly confirmed, response-only HA action can return the four fixed baseline responses; it has no arbitrary request or control path. A headless YAML opt-in handles both cached and later Bluetooth discovery and fails closed rather than selecting among multiple cached machines. Its optional one-shot capture flag creates an attempt marker before the first complete refresh, writes an owner-only private file on success, and never repeats the raw capture after failure or restart. Verification: 90 independent protocol/package tests on Python 3.13 and 29 real HA framework tests on HA 2026.9.3 / Python 3.14, with simulated Bluetooth and network disabled. Build `scripts/build_integration.py` before HA tests; it generates the ignored `_protocol` copy from our own sources and `dist/wendougee_data.zip`. On 2026-09-21, after the earlier 0.0.7 proxy baseline, a fresh full backup was created and 0.0.8 was installed on HA 2026.9.1. The target registered one device and 23 entities, produced redacted schema-2 diagnostics, remained healthy beyond the ten-minute configuration-refresh cadence, completed a config-entry reload, and later recovered after two isolated poll failures. On 2026-09-22, another full backup preceded the 0.0.9 deployment; after correcting a deployment-directory placement error outside the integration itself, HA loaded version 0.0.9 with one device and 23 entities. Schema-3 diagnostics advanced from two to four successful polls with zero failures, idle state, both boilers disabled and no unknown operating bits. No baseline action was invoked. Only sanitized values are documented in `docs/LIVE_VALIDATION_2026-09-21.md`. Physical comparison, deliberate disconnect/app-contention tests, extended soak testing and direct-Python validation remain pending.

**0.1.0 update:** canonical user-facing naming is now `WENDOUGEE DATA S`. Seven new read-only activity entities persist only events seen by the poller: observed shot/cleaning activity, observed shot and pumped-water totals, last observed shot/time/volume and last observed backflush. Their names and diagnostics explicitly disclose that they are lower bounds at the configured poll cadence. Schema-4 diagnostics include only identifier-free activity values. The built-in-card Espresso dashboard adds live status, recent activity, daily statistics and inert independent boiler-schedule planning helpers. An original AI-generated white/rose-gold illustration replaces unlicensed retailer photography. The independently written boiler-setting module can construct only FC06 registers 6/7/8/9 and validate exact echoes; it has no HA service, control entity or write-capable transport. Verification at this checkpoint is 106 protocol/package tests plus 32 HA framework tests. A fresh full backup preceded target installation; after restart and config-entry reload, all 30 entities loaded and schema-4 successful polls advanced from five to eleven with zero failures. See `docs/DASHBOARD.md`, `docs/CONTROL_DESIGN.md` and the live-validation record.

**0.1.1 update:** an explicitly confirmed read-only benchmark tests serialized telemetry/state pairs at 5 Hz and then 10 Hz, stops at the first failure, and selects only a stage sustaining at least 85% of target. A second confirmed action captures 10–180 seconds at the selected in-memory rate and writes decoded samples plus raw response hex to a unique owner-only private file outside the repository. It updates activity observations from every correlated sample but exposes no automatic trigger or control command. Verification at this checkpoint is 106 protocol/package tests plus 36 HA framework tests. A fresh full backup preceded target installation; archive verification and `ha core check` passed, the prior component is preserved in a rollback directory, and Home Assistant restarted with its Supervisor observer healthy. The browser authentication session became unavailable after restart, so authenticated service registration/entity verification and the hardware sampling benchmark remain pending. No high-rate trace or control command was sent.

**0.1.2 update:** the user-run 0.1.1 action confirmed that the installed integration and benchmark service loaded, but it returned no accepted rate. Review found that the implementation started its two-second sampling clock before the ESPHome-proxy connection was ready and allowed only three seconds for the session, so this failure was not evidence of a machine cadence limit. Version 0.1.2 starts measurement after connection, uses the normal 15-second session timeout, tests 1 → 2 → 5 → 10 Hz for three seconds per stage, and returns privacy-safe `transport_or_protocol_failure` or `insufficient_cadence` results even when no rate passes. Verification at this checkpoint is 106 protocol/package tests plus 40 HA framework tests. A fresh full backup preceded installation; archive verification and `ha core check` passed, Home Assistant restarted successfully, the frontend returned HTTP 200 and the integration loaded without its own error. The corrected benchmark accepted 1 Hz and 2 Hz complete telemetry/state pairs, then sustained about 2.46 pairs/s at a 5 Hz target and stopped for insufficient cadence without a transport/protocol failure. It selected 2 Hz in memory for the next bounded trace. This is a proxy/two-read-path limit, not a proven telemetry-only machine maximum. No high-rate trace or control command was sent.

**2026-09-22 research/proxy follow-up:** a secondary read-only client confirmed the ESPHome proxy's encrypted API session, ESPHome 2026.9.0 and advertised Bluetooth-proxy feature support. Its passive subscription received scanner-state changes but no mirrored advertisements. One already-configured-target connection attempt timed out before GATT discovery and coincided with one normal HA poll failure, so it cannot distinguish an unreachable machine from central/slot contention. The probe stopped immediately: it never subscribed to the machine, sent a Modbus request or retried. Do not repeat it while HA owns the machine path without a deliberate connection-ownership plan. A new GeeFlow 1.0.2 audit found no changes to the DATA-S register, command, parser, transport or controller files. Its new daily/deep cleaning reminders are app-local preferences; deep cleaning uses the existing cleaning path with a separately stored program, not a newly identified register or command. The next live gate remains the existing 2 Hz private trace during one manually initiated normal shot.

Implement only the pure, read-only protocol slice:

1. Add packaging/test configuration suitable for Python 3.13.
2. Write failing tests for CRC16-Modbus and the safe telemetry read request.
3. Implement the minimal CRC and Modbus read-request builder.
4. Write failing tests for parsing a 22-register holding-register response.
5. Implement typed telemetry decoding for registers 1405, 1406, 1408, 1409, 1410, 1411, 1412, 1417, 1422, and 1423.
6. Run the complete suite and commit only after green.

Do **not** connect to the machine or implement writes in this first task.

## Later milestones

1. Standalone Bleak scanner + GATT service verification.
2. Safe live read and notification capture with the official app disconnected.
3. Config flow and read-only entities.
4. Real HA test deployment after explicit approval and backup.
5. Optional controls, one category at a time, each with interlocks and supervised physical validation.
6. HACS validation, diagnostics redaction, documentation, and release hardening.

For any later profile work, reject mode 4 and unverified slots/modes until DATA-S fixtures exist. Validate all numeric bounds and slot capacity, fail on the first response mismatch, read back the complete profile, and keep brew activation as a separate operation.

## Sources

[1] https://github.com/dallonby/LitaLite/blob/main/PROTOCOL.md
[2] https://github.com/dallonby/LitaLite/blob/main/HANDOFF.md
[3] https://github.com/dallonby/Crema
[4] https://github.com/drobekk/GeeFlow
[5] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeRegisters.kt
[6] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeCommands.kt
[7] https://github.com/akiskev/DecentEbar
[8] https://github.com/saya6k/hacs-xbloom
[9] https://github.com/Arbuzov/home_assistant_delonghi_primadonna
[15] https://github.com/hbldh/bleak
[16] https://developers.home-assistant.io/docs/core/bluetooth/api
[17] https://developers.home-assistant.io/docs/core/bluetooth/bluetooth_fetching_data
[18] https://developers.home-assistant.io/docs/creating_integration_manifest
[19] https://developers.home-assistant.io/docs/core/integration-quality-scale
[20] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeFrameParser.kt
