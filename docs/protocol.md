# WENDOUGEE DATA S BLE protocol knowledge base

This document separates locally observed facts from upstream findings. Raw captures and device-specific identifiers remain private and gitignored.

For the broader feature inventory, evidence levels, control ambiguities and remaining work, see the [capability map](../CAPABILITIES.md) and [validation plan](VALIDATION_PLAN.md). Those documents pin the upstream revisions reviewed on 2026-09-20.

## Local observations: DATA S

- Advertising name pattern: `WDG_Data_*`.
- The advertising address's OUI resolves to Espressif; this is an address-vendor observation, not proof of the machine's exact BLE chip or module.
- Advertising payload includes general-discoverable, BLE-only flags, complete local name, and a `+9 dBm` TX-power field.
- Nordic nRF52840 + nRF Sniffer 4.1.1 successfully captures advertisements.
- Initial over-the-air attempts did not reliably follow the data connection. Existing upstream work makes direct GATT validation the more efficient next step.
- On 2026-09-20, a supervised direct CoreBluetooth test verified the expected custom service and both `2b10`/`2c10` characteristics on Bobby's DATA S.
- The test subscribed to both characteristics and sent the documented telemetry request exactly once. The machine returned one CRC-valid, 49-byte function-03 response containing 22 registers.
- The idle response decoded to brew boiler `94.6 °C`, steam boiler `27.2 °C`, no water-level alarm, and zero pressure, flow, volume, scale weight, and brew/pump time. These values were protocol-plausible but were not independently compared with the physical display during the headless session.
- No control, provisioning, reset, boiler-setting, cleaning, valve, or brew command was sent.
- This was a temporary native CoreBluetooth helper, not validation of the Python/Bleak CLI. No firmware version or sanitized response fixture was retained. The reported values are a session observation, not a reproducible fixture or calibration result.
- On 2026-09-21, Home Assistant 2026.9.1 discovered the same DATA S through an active ESPHome proxy and completed the four allowlisted reads once. All responses passed the integration's strict function, length and CRC checks. Decoded telemetry was consistent with an idle, cold machine; configuration reported both boiler enables off; alarm detection was enabled; and the operating-state bits decoded as idle with no unknown flags. The user had intentionally left the boilers off, but no physical-display comparison was possible. Raw frames remain private. See [the sanitized live-validation record](LIVE_VALIDATION_2026-09-21.md).
- Later that day, integration 0.0.8 registered all 23 read-only entities on the target, remained healthy beyond its ten-minute configuration-refresh cadence and completed one config-entry reload. This validates a bounded HA/proxy lifecycle path, not physical field semantics or long-duration reliability.
- On 2026-09-22, integration 0.0.9 was installed after another full backup. Its redacted schema-3 diagnostics advanced from two to four successful polls with zero failures, retained idle/boilers-off state and reported no unknown operating bits. This validates the new per-runtime health evidence across a short live interval, not an extended soak or physical semantics.

## Upstream protocol consensus

LitaLite reports a custom service and two communication characteristics discovered through official-app analysis and live testing.[1] GeeFlow independently implements matching Modbus commands/registers and states that the DATA S is its tested physical machine.[4][5][6]

| Role | UUID |
|---|---|
| Service | `00010203-0405-0607-0809-0a0b0c0d1910` |
| Modbus read/write/notify | `00010203-0405-0607-0809-0a0b0c0d2b10` |
| FF55 event/status | `00010203-0405-0607-0809-0a0b0c0d2c10` |

Upstream testing reports that direct GATT access did not require pairing, a PIN, or an application authentication exchange.[1] The local native read did not prompt for pairing, but this is not a comprehensive security test. Nearby BLE access may permit control; do not expose automatic brew actions.

## Modbus RTU transport

Frame shape:

```text
[slave=0x01] [function] [payload...] [CRC low] [CRC high]
```

CRC parameters:

- CRC16-Modbus
- initial value `0xFFFF`
- reflected polynomial behavior
- low byte transmitted first

Observed function codes:[1]

| Code | Operation |
|---:|---|
| `0x01` | Read coils |
| `0x03` | Read holding registers |
| `0x05` | Write single coil |
| `0x06` | Write single holding register |
| `0x10` | Write multiple holding registers |

## Read-only telemetry

Upstream maps the 1404+ block as follows:[1][20]

| Register | Meaning | Conversion/status |
|---:|---|---|
| 1405 | Elapsed brew time | divide by 10 for seconds |
| 1406 | Water-level alarm | nonzero = alarm |
| 1408 | Steam-boiler temperature | divide by 10 for °C |
| 1409 | Brew-boiler temperature | divide by 10 for °C |
| 1410 | Pressure | divide by 10 for bar |
| 1411 | Cumulative pumped volume | mL; not necessarily beverage yield |
| 1412 | Scale weight | divide by 10 for g |
| 1417 | Pump-active time | seconds |
| 1422 | Instantaneous flow | reported as raw mL/s; controlled confirmation remains desirable |
| 1423 | Weight rate | divide by 10 for g/s |

Safe request, now locally verified on the DATA S:

```text
01 03 05 7C 00 16 05 10
```

Interpretation: slave 1, read holding registers, start 1404 (`0x057C`), count 22, CRC `0x1005` transmitted low-byte first.[1]

The one local response confirms framing and a plausible decode, not every unit. Register 1405's conversion still needs a stopwatch comparison (GeeFlow's parser retains the raw integer); flow and signed scale behavior also remain provisional. GeeFlow reads 20 registers from the same base, whereas our decoder expects 22; do not feed a 20-register response into the current fixed-length decoder.

## Known controls—documented, not approved for use

The following are recorded for protocol completeness but must not be sent without explicit approval and supervised physical validation:[1][5][6]

| Address | Type | Reported role |
|---:|---|---|
| 87 | holding register | active brew mode |
| 150 | coil | brew-button press/release toggle |
| 154 | coil | **unresolved conflict:** described upstream as both a configured-shot trigger and a raw valve; do not use |
| 155 | coil | cleaning cycle |
| 157 | coil | free-variable brew path in GeeFlow; earlier LitaLite experiment found no obvious effect on one LITA-BA |

Never send undocumented `FF55` provisioning commands, `AT+RST`, OTA/YModem traffic, or arbitrary register writes.

## FF55 event channel

Upstream reports two FF55 frame families on the event characteristic:[1]

- opcode-oriented `FF 55 FF FF ...` commands/events
- fixed-header `FF 55 02 59 20 00 ...` status/accessory frames

Potential uses include heartbeat state, smart-scale/grinder interaction, session/name operations, and provisioning. This area is less completely mapped than Modbus and is not needed for the initial read-only HA integration.

## Compatibility status

- GeeFlow says the DATA S is its only tested real espresso machine.[4]
- LitaLite's live validation was primarily against LITA-BA and lists DATA-S compatibility as a cross-model item to confirm.[2]
- Crema targets LITA-BA, LITA-BR, and DATA-S in its public project description and constants.[3]

UUIDs and one telemetry read have now been observed on Bobby's DATA S. This does not establish configuration/control compatibility or transfer every LITA observation unchanged.

## Next evidence to collect

1. Compare decoded values with the display, stopwatch and scale during attended observation.
2. Record model/firmware/app provenance and review a minimal captured fixture before publication.
3. Reproduce the read through the direct Python transport only if maintaining that separate path is useful.
4. Observe one manually initiated shot; the client must not initiate it.
5. Run deliberate proxy-loss, app-contention, disable and extended soak tests through the HA path; restart and one config-entry reload have succeeded.
6. Resolve the capability map's conflicts before exposing the affected controls.

See the [batched plan](VALIDATION_PLAN.md) for exact scope and acceptance criteria. No new hardware session was performed during the capability audit.

## Sources

[1] https://github.com/dallonby/LitaLite/blob/main/PROTOCOL.md
[2] https://github.com/dallonby/LitaLite/blob/main/HANDOFF.md
[3] https://github.com/dallonby/Crema
[4] https://github.com/drobekk/GeeFlow
[5] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeRegisters.kt
[6] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeCommands.kt
[20] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeFrameParser.kt
