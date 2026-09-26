# Offline read-only foundation

The initial foundation was implemented offline on 2026-09-20 with synthetic
fixtures and fake transports. Subsequent HA deployment, bounded live reads and
passive event evidence are recorded in [the live-validation history](LIVE_VALIDATION_2026-09-21.md).
This page describes the reusable protocol layer; offline tests alone do not
validate physical field meanings.

## Implemented

- `reads.py`: fixed allowlist of telemetry (FC03 1404/22), configuration (FC03 0/37), water-alarm enable (FC03 396/1), and operating state (FC01 182/24).
- `ReadResponseStream`: bounded fragment assembly and extraction of coalesced FC01/FC03 frames and exception replies; validates CRC, rejects corrupt headers, and fails closed without speculative resynchronization.
- `validate_read_response`: checks slave, function, exact payload size, total length and CRC; raises a typed exception with the device's Modbus error code.
- `state.py`: typed, immutable configuration and state. Boiler enable polarity and setting units are explicit. Unknown enum values stay unknown. All 37 configuration words and 24 status bits are retained in memory for private analysis; contradictory flags are not collapsed into a single apparently valid state.
- `events.py`: passive-only FF55 framing and checksum validation for the two documented event families. It narrowly decodes the exact-machine opcode-`0x83` binary marker observed on 2026-09-26 without assigning a meaning, generating frames or exposing a write path.
- `ReadSession`: injected transport, serialized requests, bounded setup/read/cleanup, immediate notification of disconnect while awaiting a response, no retries, and quarantine after errors/timeouts/in-flight cancellation.
- Standalone Bleak adapter: waits for both subscriptions, wires disconnect callbacks, attempts cleanup after partial setup, and rejects any bytes outside the read allowlist.
- Existing telemetry CLI still sends **only one telemetry request** when explicitly invoked with its read flag. A separate evidence command can send each of the four fixed reads once, but only after an immediate typed confirmation; see [EVIDENCE_COLLECTION.md](EVIDENCE_COLLECTION.md). There is no scan or connection on import.

The original telemetry parser and assembler remain available for compatibility.
The live client uses the stricter general read session rather than the old
assembler for transport handling. The later HA integration consumes this layer;
its transport still exposes only the fixed read allowlist.

## Deliberate failure policy

The frame extractor understands coalesced frames, but the session expects exactly one response to its single outstanding request. Extra frames, trailing bytes, or unsolicited data invalidate that session. Corrupt input also fails rather than skipping bytes to search for a plausible reply.

Timeout, cancellation after request ownership, response mismatch, device exception, send failure, or disconnect prevents further reads on the same session. A caller must close it and construct a new transport with a fresh connection. There is no automatic reconnect, polling or retry loop. Cancelling a reader that is still waiting for the request lock does not invalidate another reader's transaction.

This is intentionally conservative until captures establish whether the machine emits unsolicited Modbus traffic. The read transport ignores FF55 notifications, and no FF55 initialization command is sent. Captured FF55 frames can be inspected separately with the passive parser; parsing them does not change session behavior.

Modbus RTU read replies do not echo the requested register address or contain transaction IDs. A same-shaped unsolicited reply during a pending read cannot be authenticated as that read's response. Serialization and a fresh connection after uncertainty reduce ambiguity, but do not remove this protocol limitation. No implementation should claim complete response correlation on that basis alone.

## Tests

The protocol/package suite contains 117 tests at the current checkpoint, covering existing CRC/telemetry functionality plus:

- known request frames and allowlist enforcement, including rejecting a control frame before transmission;
- configuration scaling/polarity, unknown values, state conflicts and unknown flags;
- response identity, lengths, CRC and device exceptions;
- every split boundary of a small frame, coalescing and bounded malformed input;
- serialization, duplicate/unsolicited/late responses, disconnect, timeout and cancellation;
- setup/send/cleanup failures, hung operations and fresh-session recovery;
- fake Bleak subscription ordering, write mode selection, disconnect forwarding and one-shot CLI workflow.
- FF55 variant, length, reserved-byte and checksum validation, plus narrow binary heartbeat-marker decoding and malformed-frame rejection.

Tests label their new fixtures synthetic. They do not recreate or claim to retain the previous native-helper capture. Run `python -m pytest` in the development environment; tests do not require the machine.

## Still pending

- Supported-permission, real Python/Bleak validation; no bypass of macOS privacy controls.
- Reviewed public fixtures with model/firmware/app provenance; real baseline and trace captures exist privately, but no raw frame is approved for publication.
- Physical confirmation of units, configuration meanings, status flags and natural unsolicited traffic.
- Broader disconnect, contention and disable tests; HA polling and bounded idle soaks have succeeded, while these failure scenarios remain incomplete.
- Physical validation of the deployed HA entities; see [HOME_ASSISTANT.md](HOME_ASSISTANT.md). The shared-Bluetooth adapter, config flow, availability handling and tests are implemented and the integration has completed live read-only validation.

The next hardware session remains subject to immediate explicit approval under `AGENTS.md`; running the offline suite needs none.
