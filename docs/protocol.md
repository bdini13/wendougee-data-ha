# BLE protocol notes

This document records only behavior confirmed from real hardware or reproducible captures.

## Discovery

| Field | Confirmed value |
|---|---|
| Transport | Bluetooth Low Energy |
| Observed local-name pattern | `WDG_Data_*` |
| Tested machine | Wendougee DATA S |
| Sniffer hardware | Nordic Semiconductor nRF52840 Dongle (PCA10059) |
| Sniffer firmware | Nordic nRF Sniffer for Bluetooth LE 4.1.1 |

## Unknowns to resolve

- GATT service and characteristic UUIDs
- Pairing and encryption behavior
- Authentication or session handshake
- Telemetry notification format
- Command framing and checksums
- Safe command/state model

## Capture procedure

1. Keep raw captures outside Git; `captures/` is ignored by default.
2. Start the Nordic sniffer before opening the official E-Bar app.
3. Select the `WDG_Data_*` advertiser.
4. Record one action at a time and note exact timestamps.
5. Sanitize Bluetooth addresses, pairing material, account data, and device identifiers before publishing evidence.

## Initial action matrix

Capture each action in a separate session when possible:

1. App launch and reconnect without changing machine state
2. Read machine status
3. Change one non-brewing setting
4. Start and stop a safe, supervised function
5. Observe one normal espresso shot

Do not infer command meanings from a single packet. Confirm each mapping with repeated captures and state observations.
