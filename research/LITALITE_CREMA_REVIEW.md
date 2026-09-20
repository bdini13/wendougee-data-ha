# Focused review: LitaLite and Crema

Reviewed snapshots:

- `dallonby/LitaLite` — `3a26b7ec114ff03f228dd8cfc232b3885cd523cb`
- `dallonby/Crema` — `930879755a76cefef010c05a39485e09cf59b819`

This is a reference review for the Wendougee Home Assistant project, not an upstream PR review.

## Executive assessment

**LitaLite is the strongest protocol notebook and Python experimentation toolkit, but not a production library.** Its evidence trail is valuable, its CRC fixtures execute successfully, and its notes clearly distinguish many observations from hypotheses. Its direct-control scripts are intentionally experimental and need stronger safety gates, response validation, and tests before any ideas are used in Home Assistant.[1][2][21][22][23]

**Crema is the strongest typed Apple-platform implementation of the LitaLite findings, but it is not independent DATA-S evidence.** It has a good transport abstraction and packet-fixture tests, while its own comments state that the constants came from the official APK and were verified live against LITA-BA. The reusable library builds on the Mac, but the test target currently fails because the package does not make the imported `Testing` module available.[3][24][25][27][28]

Neither repository has a detectable license. Treat both as all-rights-reserved research references: do not copy their code or prose into this MIT project without permission.

## LitaLite review

### What is strong

- `PROTOCOL.md` records provenance, dates, packet transcripts, corrections, confirmed-versus-inferred fields, and open questions unusually well.[1]
- The GATT map, Modbus RTU frame shape, CRC16 parameters, safe read fixtures, telemetry block, profile slots, and write sequencing are sufficiently precise to create independent tests.[1]
- The Python tools cover scanning, service discovery, read-only listening, HCI-snoop decoding, register watching, telemetry recording, and targeted experiments.[2]
- `scripts/modbus.py` is small and understandable. Its on-Mac self-test verified all **18/18** included packet CRC fixtures.[21]
- The handoff explicitly says live validation was against LITA-BA and lists DATA-S compatibility as something to confirm, avoiding an unsupported exact-machine claim.[2]

### Blocking/licensing concern

- No license file is present. The code and documentation cannot be assumed reusable merely because the repository is public. Reimplement protocol behavior independently and retain attribution to the research.[1][2]

### Safety warnings

- `press_coil.py` and `press_register.py` perform hardware writes immediately after connecting; they have no interactive confirmation, address allowlist, dry-run mode, emergency cleanup guarantee, or validation that the machine is attended and safely prepared.[22]
- If `press_coil.py` is interrupted after the ON write but before the OFF write, the `KeyboardInterrupt` handler exits without a `finally` release. For a momentary-control protocol, that is an unacceptable pattern for production code.[22]
- `send_profile.py --demo` is not a simulation: it writes the captured profile into a real quick-key slot. `--brew` is optional, but the profile mutation happens regardless. The name can mislead users into treating it as harmless.[23]
- `probe.py` accepts arbitrary hexadecimal writes. Its prose warns that writes change state, but the program does not enforce read-only function codes.

### Correctness and robustness warnings

- `parse_response()` validates only minimum length and CRC. It does not reject the wrong slave, Modbus exception responses, impossible byte counts, mismatched functions, or a response belonging to another request.[21]
- Request builders do not validate numeric ranges or maximum frame size.
- The scripts accumulate notification bytes until the entire buffer has a valid CRC. A corrupted byte, unsolicited frame, or multiple frames in one notification can poison the buffer; there is no framing/resynchronization loop.
- Request/response handling is script-local and assumes only one request at a time. That is acceptable for experiments but unsuitable for a long-running Home Assistant connection.
- The repository has no automated test suite. The CRC self-test is useful but does not cover fragmented responses, exception frames, byte-count validation, timeouts, reconnects, or malformed notifications.[21]
- Some protocol sections have stale/open-question wording after earlier sections claim live confirmation. Treat packet transcripts and current code cross-checks as stronger evidence than unchecked TODO lists.
- Register 1422 flow scaling is explicitly an inference from physical sanity checking, not a controlled calibration. Preserve that uncertainty.[1][2]

### Reusable facts, not reusable code

Use as independently implemented test fixtures:

- advertising prefix `WDG_Data_`
- custom service and `2b10`/`2c10` characteristics
- CRC16-Modbus parameters
- safe reads from registers 0, 387, 1404, and 1441
- telemetry register candidates
- profile header/stage layout and known packet transcript
- single-active-central operational constraint

Do not port the scripts wholesale.

## Crema review

### What is strong

- `CremaKit` cleanly separates transport, protocol framing, typed telemetry, profiles, shot history, and application UI.[3]
- `MachineTransport` plus `StubMachineTransport` is a useful design model for keeping hardware out of deterministic tests.
- `Modbus.swift` has clear builders and fixture-based parser/CRC tests.[24][27]
- `FF55.swift` separates opcode and positional frame variants and verifies three captured checksums.[26]
- `BLEMachineTransport` serializes mutable CoreBluetooth state onto a dedicated queue and prevents more than one in-flight Modbus request.[25]
- Actual execution on the Mac confirmed `swift build --target CremaKit` succeeds.

### Blocking/licensing concern

- No license file is present. In addition, `Modbus.swift` explicitly describes itself as a direct port of `LitaLite/scripts/modbus.py`.[24] Do not copy Crema code into the MIT Home Assistant project.

### Build and test findings

- `Package.swift` declares no package dependency that supplies the `Testing` module, while all tests use `import Testing`.[28]
- On the Mac's Apple Swift 6.3.3 toolchain, `swift test` fails at compile time with `no such module 'Testing'`. Therefore none of Crema's tests executed in this review.
- The library target itself builds successfully.
- Swift emits a concurrency warning in `BLEMachineTransport.startScan()` about capturing `self` in concurrently executing code.[25]

### BLE transport warnings

- Connection establishment has no explicit timeout after `manager.connect()`. Failure paths during service/characteristic discovery can leave the checked continuation unresolved.[25]
- Delegate errors from service discovery, characteristic discovery, notification setup, and value updates are mostly ignored.[25]
- The transport marks the machine connected as soon as both characteristic objects are found, before `didUpdateNotificationStateFor` confirms notifications are active.[25]
- A valid Modbus response is not correlated to the function/address of the pending request. Any valid frame on the characteristic can satisfy the continuation.[24][25]
- Reassembly parses the entire accumulated buffer as one frame. It does not extract multiple frames, discard a corrupt prefix, or recover after a poisoned buffer.[25]
- Disconnection clears characteristics but does not immediately fail an in-flight request; callers wait until the timeout fires.[25]
- The transport exposes unrestricted one-way Modbus and FF55 writes with no policy/safety layer.[25]

### Parser/model warnings

- `Modbus.parse()` validates CRC but not slave identity, exception function codes, function-specific lengths, or expected response correlation.[24]
- `FF55.parse()` is based on three live fixtures; the checksum rule and framing should remain provisional until more traffic confirms them.[26]
- The FF55 parser accepts the declared payload portion but does not require the declared length to consume every byte before the checksum, allowing trailing bytes to be silently ignored.[26]
- Crema's `LiveTelemetry` model omits water-level alarm, scale weight, and weight rate fields that GeeFlow's DATA-S parser maps from the same telemetry block.
- Crema advertises DATA-S support, but its constants explicitly trace live verification to LITA-BA; do not treat it as independent DATA-S hardware confirmation.[3]

### Reusable design ideas, not reusable code

- protocol/client library separate from UI or Home Assistant
- fake/stub transport for deterministic tests
- typed frames and telemetry
- one in-flight Modbus request enforced by a lock/actor
- async state and received-frame streams
- fixture-driven packet tests
- explicit machine registry/capability model

For Python/Home Assistant, implement these patterns independently using Home Assistant's Bluetooth manager and `bleak-retry-connector`, with request correlation, frame extraction/resynchronization, and strict read/write policy separation.

## Decision for this project

1. Use **GeeFlow** as the strongest exact DATA-S cross-check.
2. Use **LitaLite** for protocol provenance and byte fixtures.
3. Use **Crema** for architecture ideas and a second implementation cross-check.
4. Write an original Python protocol library under the MIT project.
5. Begin with safe reads only.
6. Add malformed-frame, exception-response, correlation, fragmentation, coalescing, timeout, disconnect, and reconnect tests before live use.
7. Keep all writes behind a separate explicit capability layer that Home Assistant does not enable in the first release.

## Sources

[1] https://github.com/dallonby/LitaLite/blob/main/PROTOCOL.md
[2] https://github.com/dallonby/LitaLite/blob/main/HANDOFF.md
[3] https://github.com/dallonby/Crema
[21] https://github.com/dallonby/LitaLite/blob/main/scripts/modbus.py
[22] https://github.com/dallonby/LitaLite/blob/main/scripts/press_coil.py
[23] https://github.com/dallonby/LitaLite/blob/main/scripts/send_profile.py
[24] https://github.com/dallonby/Crema/blob/main/Sources/CremaKit/Modbus.swift
[25] https://github.com/dallonby/Crema/blob/main/Sources/CremaKit/BLEMachineTransport.swift
[26] https://github.com/dallonby/Crema/blob/main/Sources/CremaKit/FF55.swift
[27] https://github.com/dallonby/Crema/blob/main/Tests/CremaKitTests/ModbusTests.swift
[28] https://github.com/dallonby/Crema/blob/main/Package.swift
