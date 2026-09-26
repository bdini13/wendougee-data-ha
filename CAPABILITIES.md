# WENDOUGEE DATA S capability map

Source audit: 2026-09-20; live-read update: 2026-09-26. Target: Bobby's WENDOUGEE DATA S; firmware and installed E-Bar version not yet recorded. This is a research baseline, **not a declaration that these controls work safely on this machine**.

## What we have, and what remains

**0.3.0 cleaning update:** A09 now has a guarded opt-in start using the current
stored program unchanged. The owner's app screenshots show 5 s cleaning, 5 s
standing and 3 repetitions, agreeing with the read-only decode. Parameter editing
is still app-only; the pilot rejects programs over 120 seconds. Synthetic tests
pass; no HA-initiated cleaning cycle has yet been performed. See
[cleaning control](docs/CLEANING_CONTROL.md).

**0.2.0 control implementation update:** B01/B02 now have opt-in boiler switches;
A04 has an opt-in start-only button for the current active stored mode-2 profile.
Only B01/B02 are enabled on the target: the owner specifically wants the separately
stored paddle-bound recipe, so A04's app-profile path is off and not a substitute.
Paddle activation remains unimplemented; see [evidence and next test](docs/PADDLE_PROFILE.md).
These are simulation-tested, not physically commissioned. The historical 0.1.2
read-only description below predates this change. No setpoint writes, recipe
uploads, binding changes, cleaning control or automatic schedule was enabled.

Existing projects supply concrete implementations for telemetry, boiler settings, cleaning, brewing, profiles, and scale connectivity. We do not need to rediscover those protocols from scratch. The remaining work is independent implementation, exact-machine verification, resolving conflicts, and building a reliable Home Assistant integration.

Our Python package implements CRC, allowlisted read requests, strict response framing, ten-field telemetry and configuration/state decoders, passive-only FF55 event validation, serialized failure-quarantined read sessions, and a one-shot Bleak CLI. These have offline tests, including fake Bluetooth lifecycle failures; see [offline implementation details](docs/OFFLINE_CORE.md). The first installed 0.1.1 benchmark invocation exposed an implementation timing/timeout defect before any rate was accepted. Version 0.1.2 fixes that defect with a 1 → 2 → 5 → 10 Hz ladder and is installed on HA 2026.9.1 after a fresh backup, checksum verification, configuration check and healthy restart. The corrected HA benchmark selected 2 Hz for complete telemetry/state pairs. A later apparent active-connection regression was traced on 2026-09-26 to the standalone diagnostic harness omitting the advertisement subscription that owns ESPHome proxy BLE connections. After correction, Proxy 2 repeatedly connected, completed service discovery and returned CRC-valid telemetry on both ESPHome 2026.7.2 and restored 2026.9.0. A telemetry-only ladder on 2026.9.0 accepted 8 Hz and rejected 10 Hz after sustaining about 8.01 reads/s. That ladder passively captured nine exact-machine opcode-`0x83` FF55 frames, establishing a checksum-valid alternating binary marker; a follow-on 60-second event-only capture decoded 19/19 alternating frames and measured an approximately six-second same-marker period without establishing marker semantics. A checked HA Core restart subsequently restored all 22 enabled entities; a fresh paired benchmark again selected 2 Hz, the first successful 10-second private hardware trace captured 20 correlated idle samples at 1.99 Hz, and a later 180-second soak captured all 360 requested pairs at 2.003 Hz without a gap over one second. An offline-only module constructs the four documented boiler FC06 request shapes and validates exact echoes, but no Home Assistant service, control entity or transport can send them. See the [HA guide](docs/HOME_ASSISTANT.md), [control design](docs/CONTROL_DESIGN.md) and [sanitized live record](docs/LIVE_VALIDATION_2026-09-21.md).

“100%” needs a bounded denominator: all user-facing functions in a recorded E-Bar version on a recorded DATA S firmware, plus explicitly inventoried unsupported/unknown functions. BLE access alone cannot establish complete firmware internals, undocumented service behavior, or control of mechanical hardware. This map is not yet an exhaustive inventory of the installed official app.

The [2026-09-26 autonomous audit](research/AUTONOMOUS_AUDIT_2026-09-26.md)
checks newer GeeFlow changes: its DATA S protocol files are unchanged, device
renaming is app-local, and terminal telemetry timing needs explicit shot-boundary
validation. All 12 unmapped positions in the saved idle telemetry block stayed
zero; no new readiness or fault signal was established.

## Reading the map

- **Impl**: executable upstream implementation; not proof every path was physically tested.
- **Notes**: upstream documentation/static-analysis clue, not established DATA S behavior.
- **Conflict**: incompatible or ambiguous descriptions requiring an experiment.
- **Absent**: no endpoint identified in the reviewed sources; not proof the feature is impossible.
- Local **offline**: our implementation exists with synthetic/known-frame tests.
- Local **native once**: observed in the earlier direct CoreBluetooth read; semantics still need comparison.
- Local **HA baseline**: observed in the approved 2026-09-21 four-read HA/proxy session; still not physically calibrated.
- Local **—**: neither locally implemented nor verified.
- HA column is the destination roadmap, not a commitment to expose hazardous operations. T01–T04/T06 and S01–S12 have real read-path evidence described in the [HA guide](docs/HOME_ASSISTANT.md) and [live record](docs/LIVE_VALIDATION_2026-09-21.md). Provisional read-only configuration and operating-state entities are implemented but disabled by default pending physical comparison. Read evidence for a setting is not write/control evidence.

All addresses below are **decimal**; FC denotes Modbus function code. Do not execute entries as a command checklist. Even Modbus reads use a BLE characteristic write and require the project's immediate pre-test approval. See the [validation plan](docs/VALIDATION_PLAN.md).

### Transport and lifecycle

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| T01 | Discovery and GATT layout | Impl: `WDG_Data_*`, service `1910`, Modbus `2b10`, events `2c10` [G-control], [L] | Native once + HA-proxy discovery | Discovery/config flow |
| T02 | Read telemetry | Impl: FC03, 1404/count 22 [L], [C]; GeeFlow reads count 20 [G-command] | Offline + native once + HA baseline | Coordinator |
| T03 | Read configuration | Impl: FC03, 0/count 37; separate 396/count 1 [G-command], [G-control] | Offline + HA baseline | Config state/diagnostics |
| T04 | Read operating state | Impl: FC01, 182/count 24 [G-command], [G-parser] | Offline + HA baseline | State sensor |
| T05 | Event framing / stream setup | Impl: FF55 variants; GeeFlow initialization [G-control], [G-scale]. Length/meaning conflicts [L] | Offline passive decoder; 28 local opcode-`0x83` frames validated across two captures with an alternating binary marker and approximately six-second same-marker period; no FF55 initialization needed; semantics unknown | Internal, initially excluded |
| T06 | Request/session handling | Impl upstream [G-session]; local strict stream/session with one outstanding request | Earlier HA restart, >10-minute split-cadence window and config-entry reload succeeded; corrected Proxy 2 diagnostics on 2026-09-26 connected, discovered services and returned valid telemetry on ESPHome 2026.7.2 and 2026.9.0. The earlier diagnostic timeouts were caused by a missing advertisement subscription. | Unavailable/reconnect handling |
| T07 | Identity, model, firmware version | Notes: FF55 `04` interpreted as serial upstream; firmware/model query not established [G-parser], [L] | — | Redacted device info, gated |
| T08 | Pairing/security and app coexistence | Notes: direct access without pairing [L]; no pairing prompt in local native read | Proxy 2 connected without pairing once mobile Bluetooth was excluded and the diagnostic client held the required proxy subscription; deliberate simultaneous-app contention remains untested | Single-owner connection policy |

### Telemetry and state

“HA baseline” below means bytes decoded in the 2026-09-21 session, **not** calibrated readings. Zero-valued fields provide no evidence about their units or dynamic behavior.

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| S01 | Brew temperature | Impl: 1409 / 10 °C [G-parser], [L] | Native once 94.6 °C; HA baseline 20.1 °C | Temperature sensor |
| S02 | Steam temperature | Impl: 1408 / 10 °C [G-parser], [L] | Native once 27.2 °C; HA baseline 23.9 °C | Temperature sensor |
| S03 | Pressure | Impl: 1410 / 10 bar; GeeFlow calls it pump, not puck pressure [G-parser], [G-state] | Native once + HA baseline, zero | Pressure sensor |
| S04 | Cumulative pumped volume | Impl: 1411, mL; do not equate with beverage yield [G-parser], [G-state], [L] | Native once + HA baseline, zero | Shot-volume sensor |
| S05 | Instantaneous flow | Impl: 1422 raw mL/s; scaling still requires calibration [G-parser], [L] | Native once + HA baseline, zero | Flow sensor, provisional |
| S06 | Elapsed shot time | Conflict: 1405 / 10 seconds in LitaLite; GeeFlow parser retains raw integer [G-parser], [L] | Native once + HA baseline, zero | Duration sensor after unit check |
| S07 | Pump-active time | Notes/Impl: 1417 seconds [L], [C] | Native once + HA baseline, zero | Duration sensor, provisional |
| S08 | Scale weight | Impl: 1412 / 10 g [G-parser] | Native once + HA baseline, zero; no scale proof | Weight sensor |
| S09 | Weight rate | Impl: 1423 / 10 g/s [G-parser]; negative/signed behavior unresolved | Native once + HA baseline, zero | Yield-rate sensor, gated |
| S10 | Water shortage alarm asserted | Impl: 1406 nonzero [G-parser], [L] | Native once + HA baseline, false; alarm state untested | Problem binary sensor |
| S11 | Idle/manual/profile/cleaning/free-variable state | Impl: masks in FC01 reply [G-parser]; see plan for offsets and conflicting flags | HA baseline idle; no unknown bits | Enumerated state sensor |
| S12 | Heater enabled versus actively heating/ready | Impl: configuration 6/7 gives enable state [G-parser]; active heater/ready signals not established | HA baseline: both enables off; active/ready unknown | Enabled-state feedback; no invented ready flag |
| S13 | Detailed faults | Notes: NTC, pressure, heating/water/extraction timeout names; no validated bitfield [L] | — | Future diagnostic sensors |

### Boiler and machine configuration

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| B01 | Brew heating enable | Impl: FC06 register 7, **0 enabled / 1 disabled** [G-control] | Read once as off; no write proof | Opt-in switch after readback validation |
| B02 | Steam heating enable | Impl: FC06 register 6, **0 enabled / 1 disabled** [G-control] | Read once as off; no write proof | Opt-in switch after readback validation |
| B03 | Brew target temperature | Impl: FC06 register 9, whole °C (unlike measured temperature) [G-control] | Read once as 92 °C; no write proof | Number; validated limits required |
| B04 | Steam target temperature | Impl: FC06 register 8, whole °C [G-control] | Read once as 126 °C; no write proof | Number; validated limits required |
| B05 | Heating mode | Impl: FC06 register 22; 1 full-speed, 0 pulse [G-control] | Read once as full-speed; no write proof | Select; physical semantics unverified |
| B06 | Water-alarm enable / water-source setup | Impl: FC10 register 396, 1 enabled / 0 disabled [G-control]; distinct from S10 | Read once as enabled; no write proof | Advanced setting, disabled by default |
| B07 | Standby temperature/timer/wake | Notes: candidate registers 14/33 and app symbols, incomplete [L] | — | Unknown; no entity yet |
| B08 | True mains power / remote wake from off | Absent in reviewed controller/notes | — | Do not label heating switches “main power” |
| B09 | Units and other app preferences | Notes: app symbols, unclear machine-versus-app ownership [L] | — | Determine ownership before exposing |

### Brewing and cleaning

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| A01 | Manual/paddle preset duration | Impl: FC10 register 17, seconds × 10 [G-control] | Read once as 30.0 s; no write proof | Advanced number |
| A02 | Manual/paddle preset pressure | Impl: FC10 register 19, bar × 10 [G-control] | Read once as 9.0 bar; no write proof | Advanced number |
| A03 | Manual start/stop | Conflict: GeeFlow pulses coil 154 for both directions with state guards; other notes call it a valve [G-control], [L] | — | Blocked pending exact-machine semantics |
| A04 | Profile/button start/stop | Impl: coil 150 press/release; **same pulse for start and stop**, not an idempotent off command [G-control] | — | Explicit action, not ordinary switch |
| A05 | Enter/exit free-variable brewing | Impl: registers 15/1459 and coil 157; stop uses refreshed status plus zero targets [G-control] | — | Advanced action, withheld |
| A06 | Live pressure/flow target | Impl: FC10 at 1419/count 2: pressure × 10 or flow × 10, other field zero [G-control] | — | Internal live-control API, withheld |
| A07 | Change regulator during a running shot | Impl limitation: GeeFlow declares live mode switching unsupported [G-profile-cap] | — | Do not promise pressure↔flow switching |
| A08 | Cleaning duration/rest/repetitions | Impl: FC10 registers 0/1/2; first two in tenths of seconds [G-control] | Read once as 5 s / 5 s / 3; no write proof | Advanced configuration |
| A09 | Cleaning start/stop | Impl: coil 155 pulse, same action for both directions with state guards [G-control] | — | Attended maintenance action only |
| A10 | Independent valve/steam/hot-water actuation | Conflict/Absent: 154 ambiguous; no established DATA S remote steam/hot-water endpoint | — | Excluded until evidence exists |
| A11 | Daily/deep cleaning reminders | GeeFlow 1.0.2 stores reminder intervals/due dates in app-local preferences [G-maint-store]; “deep” reuses A08/A09 with a separately saved program and defaults to twice the daily cycle count [G-maint-default], [G-maint-start] | Last observed backflush is tracked locally in HA; no distinct machine reminder/read endpoint | HA maintenance helpers/history, not a BLE entity |

No reviewed stop path is a demonstrated hardware emergency stop. A network client cannot promise to stop the pump after losing its connection.

### Profiles and execution

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| P01 | Native staged pressure/flow/time profile | Impl: header and staged register layout [G-compiler], [L]; mode taxonomy differs | — | Validated upload action; no automatic start |
| P02 | Native weight/volume termination | Impl: header goal discriminator and target [G-compiler]; scale dependency for weight | — | Profile field after physical validation |
| P03 | Wait/last-stage/flow-priority/autolink fields | Impl: compiler writes fields [G-compiler]; behavior and priority need tests | — | Profile fields, individually gated |
| P04 | Active versus bound/paddle profile | Impl: bases 2048/2560, selectors 87/88, bind register 30 [G-reg], [G-control] | — | Selected/bound profile after readback |
| P05 | Additional quick-key slots and capacities | Conflict: LitaLite lists 3048/3560; GeeFlow supports active/bound paths [L], [G-reg] | — | Blocked; do not “correct” addresses by guessing |
| P06 | Readback, persistence, restart/disconnect behavior | Read access exists; complete transactional readback and persistence semantics not demonstrated by reviewed upload paths | — | Prerequisite for all profile controls |
| P07 | Recorded/free-variable profile (mode 4) | Impl: eight tables plus control registers; not the staged layout [G-compiler], [G-reg] | — | Explicitly rejected in this project until validated |
| P08 | Host-executed advanced profiles | Impl: live sessions, rich conditions/ramps [G-profile-cap], [G-live]; depends on continuous client | — | Separate later feature; not native machine support |
| P09 | Profile validation and interoperability | Impl upstream compilers/importers; range, version and capacity boundaries need original implementation [G-compiler], [C] | — | Versioned local profile API |
| P10 | Shot graphs/history/import/export | Impl app-side in reviewed apps [C], [D]; not evidence of machine-stored history | — | HA recorder/local files, separate from device capabilities |

### Accessories, calibration, service functions

| ID | Capability | Evidence / mechanism | Local status | Proposed HA destination |
|---|---|---|---|---|
| X01 | Scale connectivity enable/status | Impl: FF55 `9a`, query versus enable/disable payloads [G-command], [G-parser] | — | Advanced scale setting/status |
| X02 | Scale discovery/list | Conflict: GeeFlow `8c` plus discovery events; LitaLite assigns overlapping naming/session meanings [G-command], [G-parser], [L] | — | Accessory selection, gated |
| X03 | Scale connect/disconnect/identity | Conflict: GeeFlow `80`/`87`, status `8b`, events; direction/context unresolved across sources [G-control], [G-parser], [L] | — | Accessory management, gated |
| X04 | Scale tare/timer forwarding through machine | Absent from reviewed machine controller; DecentEbar uses direct accessory BLE [D] | — | Separate scale integration unless forwarding proven |
| X05 | Grinder status/settings | Notes: one Variant-B example, insufficient behavioral map [L] | — | Research only |
| X06 | Pressure/flow PID tuning | Notes: app symbol names, no validated addresses/units/ranges [L] | — | Service-only research, no HA controls |
| X07 | Sensor offsets/calibration | Notes: pressure/flow/temperature offset names [L] | — | Service-only research, no HA controls |
| X08 | Naming/provisioning/factory reset | Conflict: FF55 interpretations overlap accessory operations [L], [G-parser] | — | Excluded from routine integration |
| X09 | Firmware update/bootloader | Notes: OTA/YModem path [L]; no verified image/compatibility/recovery procedure | — | Study only; no update entity |

## Evidence limits and completion criteria

Local evidence now covers one earlier native idle telemetry response and one HA/proxy four-read idle baseline on the same machine. Neither had a physical display comparison; firmware remains unrecorded; no captured frame is approved as a public fixture. The sessions did not prove nonzero units, configuration persistence, running-state transitions, accessory behavior, reconnect reliability or safe control. Source implementations reduce discovery work; they do not remove validation work.

To graduate a capability to supported, record: firmware/app version, precise request and response semantics, units/ranges, prerequisites, sanitized fixture, offline tests, independent readback where applicable, physical observation, failure/reconnect behavior, and HA tests. Track app coverage separately from protocol coverage and supported HA coverage; a percentage mixing them would be misleading.

Distributor guidance corroborates user-facing boiler settings, water-source alarm configuration, paddle profile binding, scale pairing, profiles, and cleaning. It is a useful UI checklist seed, not a wire-protocol authority or a substitute for inspecting the installed app. [Distributor guide][UI]

See [the validation batches and conflict ledger](docs/VALIDATION_PLAN.md). The 2026-09-21 update records read-only hardware evidence only; it performed no control action.

## Pinned evidence

The [source inventory](research/UPSTREAM_SOURCES.md) records licenses. These are independently expressed facts, not imported upstream implementation. All upstream code links below pin the reviewed commits; the distributor page is a dated, unpinned observation.

[G-reg]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeRegisters.kt
[G-command]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeCommands.kt
[G-control]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeDataSController.kt
[G-parser]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeFrameParser.kt
[G-state]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/model/DeviceState.kt
[G-session]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/ble/modbus/ModbusSession.kt
[G-compiler]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeProfileCompiler.kt
[G-profile-cap]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeProfiling.kt
[G-live]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeePressureSession.kt
[G-scale]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeScaleFrame.kt
[G-maint-store]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/MaintenanceSettingsRepositoryImpl.kt
[G-maint-default]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/domain/device/src/commonMain/kotlin/app/geeflow/domain/device/usecase/ObserveMaintenanceSettingsUseCase.kt
[G-maint-start]: https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/domain/device/src/commonMain/kotlin/app/geeflow/domain/device/usecase/StartCleaningUseCase.kt
[L]: https://github.com/dallonby/LitaLite/blob/3a26b7ec114ff03f228dd8cfc232b3885cd523cb/PROTOCOL.md
[C]: https://github.com/dallonby/Crema/tree/930879755a76cefef010c05a39485e09cf59b819
[D]: https://github.com/akiskev/DecentEbar/blob/f5f85fd42626ec26a50c10290d41bd0ef3fe9907/README.md
[UI]: https://espressooutlet.com/pages/wendougee-data-espresso-machine
