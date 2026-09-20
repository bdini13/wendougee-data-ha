# Wendougee DATA BLE protocol knowledge base

This document separates locally observed facts from upstream findings. Raw captures and device-specific identifiers remain private and gitignored.

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

## Upstream protocol consensus

LitaLite reports a custom service and two communication characteristics discovered through official-app analysis and live testing.[1] GeeFlow independently implements matching Modbus commands/registers and states that the DATA S is its tested physical machine.[4][5][6]

| Role | UUID |
|---|---|
| Service | `00010203-0405-0607-0809-0a0b0c0d1910` |
| Modbus read/write/notify | `00010203-0405-0607-0809-0a0b0c0d2b10` |
| FF55 event/status | `00010203-0405-0607-0809-0a0b0c0d2c10` |

Upstream testing reports that direct GATT access did not require pairing, a PIN, or an application authentication exchange.[1] This must still be verified read-only against Bobby's DATA S. If confirmed, document that any nearby BLE central could potentially attempt control; do not expose automatic brew actions.

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
| 1411 | Total dispensed volume | mL |
| 1412 | Scale weight | divide by 10 for g |
| 1417 | Pump-active time | seconds |
| 1422 | Instantaneous flow | reported as raw mL/s; controlled confirmation remains desirable |
| 1423 | Weight rate | divide by 10 for g/s |

Safe request, now locally verified on the DATA S:

```text
01 03 05 7C 00 16 05 10
```

Interpretation: slave 1, read holding registers, start 1404 (`0x057C`), count 22, CRC `0x1005` transmitted low-byte first.[1]

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

Therefore, begin by verifying UUIDs and safe reads on Bobby's DATA S, not by assuming every LITA observation transfers unchanged.

## Next evidence to collect

1. Direct service discovery with the official app disconnected.
2. Read-only subscribe and telemetry request.
3. Save sanitized service/characteristic metadata and byte fixtures.
4. Compare decoded temperatures/pressure/volume with the machine display.
5. Repeat during one manually initiated shot; the client must not initiate it.
6. Map alarms and boiler-state fields before exposing controls.

## Sources

[1] https://github.com/dallonby/LitaLite/blob/main/PROTOCOL.md
[2] https://github.com/dallonby/LitaLite/blob/main/HANDOFF.md
[3] https://github.com/dallonby/Crema
[4] https://github.com/drobekk/GeeFlow
[5] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeRegisters.kt
[6] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeCommands.kt
[20] https://github.com/drobekk/GeeFlow/blob/main/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeFrameParser.kt
