# Upstream research inventory

The repositories below are cloned under `research/upstream/` on the Mac Codex workspace. That directory is intentionally gitignored. Commit SHAs capture the reviewed snapshot; update deliberately and record the new SHA.

The 2026-09-20 cross-source audit is recorded in [CAPABILITIES.md](../CAPABILITIES.md), with pinned file links, and [docs/VALIDATION_PLAN.md](../docs/VALIDATION_PLAN.md), with GeeFlow register/behavior findings and conflicts. Implemented upstream does not mean validated on the local DATA S.

## Exact Wendougee work

| Local folder | Repository | Snapshot | License | Why it matters |
|---|---|---|---|---|
| `GeeFlow` | `drobekk/GeeFlow` | `10f2d191f984a35d021eb7127e3813fc3d6a8fa8` | GPL-3.0 | Complete Kotlin Multiplatform controller tested on DATA S; BLE, Modbus, telemetry, profiles, settings, cleaning, scale support, and app-local maintenance reminders.[4][5][6] |
| `LitaLite` | `dallonby/LitaLite` | `3a26b7ec114ff03f228dd8cfc232b3885cd523cb` | No license detected | Detailed protocol notes and Python research scripts; live verification was primarily LITA-BA, with DATA-S compatibility still to confirm.[1][2] |
| `Crema` | `dallonby/Crema` | `930879755a76cefef010c05a39485e09cf59b819` | No license detected | Swift/CoreBluetooth implementation targeting LITA-BA/LITA-BR/DATA-S; its constants state live verification was against LITA-BA, so use it as a cross-check rather than exact DATA-S proof.[3] |
| `DecentEbar` | `akiskev/DecentEbar` | `f5f85fd42626ec26a50c10290d41bd0ef3fe9907` | PolyForm Noncommercial 1.0.0 | Android AccessibilityService automation of official E-Bar UI; useful for profile semantics and behavioral comparison, not as the BLE transport.[7] |

## Similar-machine and accessory references

| Local folder | Repository | Snapshot | License | Reusable concepts |
|---|---|---|---|---|
| `hacs-xbloom` | `saya6k/hacs-xbloom` | `3000c0f02b487d45df4eddf6ef4f66b10a88ece8` | MIT | Modern HACS local-BLE coffee integration structure, connection lifecycle, entities, and tests.[8] |
| `home_assistant_delonghi_primadonna` | `Arbuzov/home_assistant_delonghi_primadonna` | `f264a31ef0cfdbaa607d138901924849d9d02026` | Apache-2.0 | BLE coffee-machine integration patterns and entities.[9] |
| `bookoo-opensource` | `BooKooCode/OpenSource` | `6e3f48a81aa7b209871517cf7cda19399d8a16ba` | MIT | Open Bluetooth protocols for BOOKOO scales/espresso accessories that may pair with Wendougee workflows.[10] |
| `hass-gaggiuino` | `ALERTua/hass-gaggiuino` | `88ebec5a8da581e5ef6ff2c86f5ba296cb98296f` | GPL-3.0 | Espresso-focused HA entity model and HACS packaging; transport is not the Wendougee BLE protocol.[11] |
| `lelit-bianca-protocol` | `magnusnordlander/lelit-bianca-protocol` | `a2f47bc5f2c8e3efc706e4b412c235ead33f5bd9` | No license detected | Example of disciplined protocol investigation and documenting observed versus inferred behavior.[12] |

## Official applications

Latest remote audit: **2026-09-26**. GeeFlow HEAD advanced to
`cf5fe5f659e659718ca98430691503794001fb39`; its eight Wendougee protocol/controller
files have identical Git blobs to the local `10f2d19` snapshot. New findings
concern app-local renaming and terminal shot telemetry handling. LitaLite and
Crema HEADs are unchanged. See [the autonomous audit](AUTONOMOUS_AUDIT_2026-09-26.md)
for pinned evidence and limits; local reference checkouts were not changed.

- Android package: `com.g472631889.stf`.[13]
- The Google Play listing was updated 2026-02-14 but does not expose its
  version number in the storefront metadata.[13]
- The main iOS `Wendougee` listing, App Store ID `1663713132`, reports version
  3.1.2; the separate `wendougee e-bar` listing, App Store ID `6737214986`,
  reports version 3.0.8. The user's installed app/version remains unknown.[14][15]
- LitaLite reports its protocol work used static analysis of official Android app v3.1.0 and a bundled Flutter/WebView debugging asset.[1]

Do not commit an APK or extracted app contents. If static analysis is revisited, record app version, source, hashes, and legal/ethical purpose; keep artifacts private.

## Selection notes

- Exact-machine sources are highest priority.
- Architecture references are for patterns, not blind copying.
- Lack of a license means normal copyright applies; facts may be independently implemented, but code/prose should not be copied.
- GPL and PolyForm sources have obligations incompatible with casually copying code into this MIT project.

### GeeFlow 1.0.2 follow-up

The 2026-09-22 refresh from the original pinned revision to `10f2d19` added
daily/deep cleaning reminders and chart/UI changes but did not modify the DATA S
register, command, parser, transport, or controller files used by this protocol
audit. The reminder implementation stores due dates and intervals in app-local
DataStore preferences.[16] Its default deep program copies the normal cleaning
settings with twice the cycle count, bounded by the same constraints.[17] Both
program types use the existing cleaning settings/start path. This is app
behavior, not evidence of a separate deep-clean register or command.[18]

The refresh also changes chart models and derives profile phase completion
markers in application code. Those changes add no newly identified on-wire
field or event.[19][20]

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
[10] https://github.com/BooKooCode/OpenSource
[11] https://github.com/ALERTua/hass-gaggiuino
[12] https://github.com/magnusnordlander/lelit-bianca-protocol
[13] https://play.google.com/store/apps/details?id=com.g472631889.stf&hl=en_US
[14] https://apps.apple.com/us/app/wendougee-e-bar/id6737214986
[15] https://apps.apple.com/us/app/wendougee/id1663713132
[16] https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/MaintenanceSettingsRepositoryImpl.kt
[17] https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/domain/device/src/commonMain/kotlin/app/geeflow/domain/device/usecase/ObserveMaintenanceSettingsUseCase.kt
[18] https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/domain/device/src/commonMain/kotlin/app/geeflow/domain/device/usecase/StartCleaningUseCase.kt
[19] https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/feature/device/dashboard/src/commonMain/kotlin/app/geeflow/presentation/feature/device/dashboard/model/BrewChartMapping.kt
[20] https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/feature/device/dashboard/src/commonMain/kotlin/app/geeflow/presentation/feature/device/dashboard/model/ChartPhaseMapping.kt
