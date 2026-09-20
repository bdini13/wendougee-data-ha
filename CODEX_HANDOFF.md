# Codex handoff: Wendougee DATA Home Assistant

## Mission

Build a local-first, cloud-independent Home Assistant integration for Wendougee DATA-family espresso machines, beginning with Bobby's DATA S. Treat the espresso machine as safety-relevant physical equipment: read-only telemetry first; every control must be explicit, constrained, tested, and disabled by default until validated on real hardware.

## Workspace

- Mac project root: `~/Documents/Codex/CodexProjects/wendougee-data-ha`
- Ignored upstream clones: `research/upstream/`
- Ignored private captures: `research/artifacts/private/captures/`
- Public protocol synthesis: `docs/protocol.md`
- Source inventory: `research/UPSTREAM_SOURCES.md`
- GitHub: `https://github.com/bdini13/wendougee-data-ha`

The Mac has the ChatGPT desktop app and existing Codex authentication state under `~/.codex/`, but the standalone `codex` CLI is not currently on `PATH`. The folder is ready to open as a Codex project; do not assume CLI availability.

## Critical discovery: do not reverse-engineer from zero

Substantial exact-machine work already exists:

1. **GeeFlow** is a Kotlin Multiplatform controller whose only real tested machine is the Wendougee DATA S. It already implements BLE discovery, Modbus framing, telemetry, profile execution, boiler settings, cleaning, smart-scale support, and safety warnings.[4][5][6]
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
- The documented 22-register telemetry request returned a CRC-valid response on the DATA S. The idle fixture decoded to brew `94.6 °C`, steam `27.2 °C`, no water alarm, and zero pressure/flow/volume. Physical-display comparison remains to be performed.

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
