# DATA S validation plan

Prepared 2026-09-20. Companion to the [capability map](../CAPABILITIES.md), whose stable IDs and pinned sources are used below. This plan authorizes no hardware action. Do not launch upstream research scripts: some write immediately on connection.

## Efficient order of work

1. **Source audit (this pass):** map available implementations, contradictions, missing endpoints, and the actual local baseline. Completed as a first pass, not a full official-app inventory.
2. **Offline foundation:** independently implement and test reusable read transactions/config/state decoding; build replay fixtures before connecting. This work needs no machine or user input.
3. **One approved baseline read session:** completed through HA's ESPHome proxy on 2026-09-21; configuration, state, alarm-enable and telemetry were collected without changing machine settings.
4. **One attended observation session:** user operates the normal controls while the client only reads. Compare displays, time and scale; observe meaningful state transitions.
5. **Read-only HA release:** config flow, shared Bluetooth, sensors, diagnostics and reconnection before remote controls.
6. **Small supervised control batches:** reversible settings first, profile upload/readback without activation next, brew/clean/accessories last. A fresh approval immediately before each hardware test is required.
7. **Targeted reverse engineering only for remaining gaps:** official-app traffic/static analysis for standby, faults, calibration and unresolved FF55 behavior. No blind register sweeps or fuzzing on the machine.

This separates tasks we can automate from tasks that require physical evidence. Do not spend time capturing every known packet when a documented request plus controlled readback can settle the question.

## Batch 0: offline work that can proceed without input

**Implementation update:** the allowlisted response layer, configuration/state decoders, injected read session and fake-Bleak tests are implemented and offline-tested. See [OFFLINE_CORE.md](OFFLINE_CORE.md). The read-only HA coordinator/config flow and 23 entities are also implemented with simulated split-cadence polling/recovery tests; configuration and operating-state entities default to disabled pending physical comparison. See [HOME_ASSISTANT.md](HOME_ASSISTANT.md). The [versioned evidence envelope and approval-gated baseline paths](EVIDENCE_COLLECTION.md) are implemented and offline-tested, including a response-only action for HA's shared Bluetooth/proxy route. The HA-proxy path completed one real four-read baseline on 2026-09-21; its sanitized result is documented in [the live-validation record](LIVE_VALIDATION_2026-09-21.md). Official-app inventory, physical comparison, direct-Python validation and extended operational soak testing remain pending. The original task list below is retained as the batch's scope; it is not a claim that all tasks are complete. Follow failing test → implementation → full-suite verification.

- Generalize the response layer for FC03 configuration reads and FC01 state reads, keeping an explicit read allowlist. Decode Modbus exceptions promptly, validate slave/function/length/CRC, serialize requests, and bound buffers/timeouts.
- Handle fragmented, coalesced, unsolicited, stale and corrupt traffic deliberately. FC03 responses do not echo the starting register: matching function/count alone cannot distinguish a late reply to a different same-length read. Drain/reset session state after timeout, and document remaining ambiguity.
- Add fake-transport tests for notification setup failure, disconnect while awaiting response, cleanup failures, duplicate frames, delayed replies, reconnect and cancellation. These now cover failure quarantine and fresh-session recovery. The HA coordinator opens a fresh short read-only session for each poll, including recovery after failures; normal polls read telemetry plus operating state, and every twentieth poll refreshes the complete fixed configuration set. A persistent connection manager is not implemented.
- Add typed configuration and status models. Preserve unknown raw fields in private diagnostics; never infer heater-on or machine-ready from temperature alone.
- Design a versioned fixture envelope: capability IDs, source, model/firmware/app version, timestamp, operation, expected units, observations, and known limitations. Clearly label synthetic fixtures; do not manufacture a “captured” response from the reported temperatures.
- Keep actual captures local and ignored. Commit only minimal sanitized protocol fixtures reviewed for serials, addresses, names, tokens and other identifiers.
- Inventory installed official-app screens when legitimately accessible; no settings changes needed. Otherwise record the UI inventory as pending, not silently complete.

## Batch 1: approved baseline read session

Prerequisites: supported macOS Bluetooth permissions for the actual client, exact target selection if more than one machine is visible, official app disconnected, bounded session duration, no FF55 setup/provisioning guesses. Never modify macOS privacy databases to obtain access. The native-helper success does not establish working Python/Bleak permissions or transport.

| Read | Scope | Capability coverage | Evidence to retain privately, then sanitize |
|---|---|---|---|
| FC03 1404/count 22 | Telemetry only | T02, S01–S10 | Complete frames, timing, nonzero values where naturally present |
| FC03 0/count 37 | Known configuration block used by GeeFlow | T03, B01–B05, A01/A02/A08 | Raw words plus decoder output; mark unknown fields |
| FC03 396/count 1 | Water-alarm enable | B06, separate from S10 | Configuration versus current alarm assertion |
| FC01 182/count 24 | Operating flags | T04, S11 | Raw bits, decoded state, contradictions |

No polling rate is locally validated. Begin with single serialized requests, then a conservative bounded repeat only within the approved test. Record response time and failures before increasing frequency. Do not scan arbitrary address ranges.

2026-09-21 result: HA's shared Bluetooth transport obtained valid responses for all four reads and retained the raw envelope privately. This validates the HA/proxy framing and decoders, not the direct Python/Bleak client or physical units. The machine reported idle, both boiler enables off, water-alarm detection enabled, and plausible ambient temperatures while the user intentionally left the boilers off. No control followed. See [the sanitized record](LIVE_VALIDATION_2026-09-21.md).

Remaining success criteria: reproduce the transaction through the direct Python transport only if that path remains useful, complete physical comparisons, and review a minimal fixture before publishing any captured bytes. CRC validity proves transport integrity, not field semantics.

## Batch 2: attended, read-only observation

One prepared session can settle much of S01–S12 and reduce future control risk:

- Record machine firmware/model and official-app version from supported UI/labels; redact serials. Record relevant starting settings without altering them.
- Compare both temperatures and enabled states with machine/app displays at the same time. Distinguish heating enabled, measured temperature and readiness.
- During a **manually initiated** normal shot, compare elapsed/pump timers with a stopwatch, pump pressure with the appropriate display, flow with plausible volume change, and state flags before/during/after. Pumped volume is not the weight or volume in the cup.
- If a compatible scale is already present and normally connected, compare nonzero weight and rate. Record tare behavior and whether negative readings exist; zero alone is not validation.
- Observe alarms only when they occur safely in normal use. Do not run a boiler dry, unplug sensors, obstruct plumbing or induce overpressure to validate faults.
- Check natural disconnect/reconnect and stale-data handling while idle. Do not deliberately disconnect during an active shot before a separately approved safety plan.

No user is currently required to do these steps; they remain queued until an attended session is possible. Do not issue unattended brew/cleaning operations to manufacture data.

## Batch 3: control gates, after read-only HA is reliable

For every mutation: explicit immediate approval, machine attended/prepared, known initial state, conservative validated range, one serialized transaction, correlated acknowledgment, independent readback and physical observation. Preserve the original setting for an approved restore. If an acknowledgment times out, state is **unknown**; read to reconcile. Never automatically retry a pulse/toggle.

| Order | Category | Gate before enabling it in HA |
|---|---|---|
| 1 | Boiler enable/targets and configuration | Correct polarity/units, readback, constraints, persistence and recovery proven; alarm disable remains advanced |
| 2 | Profile configuration only | Validate entire payload and slot bounds offline; snapshot known original data; abort on mismatch; verify complete readback; no activation |
| 3 | Native profile activation and manual actions | Proven state guards and stop semantics; distinct approved start; physical safe-stop procedure |
| 4 | Cleaning and accessories | Correct prerequisites, pulse semantics and FF55 direction/context established |
| 5 | Live host-controlled profiles | Explicit disconnect/timeout risk model; no claim that software watchdog guarantees pump stop |

Factory reset, raw valves, calibration/PID changes, bootloader and OTA remain excluded from routine HA controls. Learning their protocol does not require exercising them on this machine.

## Conflict ledger and smallest decisive tests

| Question | Why it matters | Efficient resolution |
|---|---|---|
| Coil 154: manual shot or raw valve? | Wrong interpretation can start water flow | Inspect installed app action traffic and before/after status during a user-operated action; only then approve a specific control test |
| “Stop” pulses 150/154/155 | Repeating a timed-out stop could restart an operation | Confirm state transitions and release behavior; never model as unconditional off; never auto-retry |
| Register 1405 time scale | GeeFlow parser retains raw integer; LitaLite says tenths | Correlate raw changes over a stopwatch interval; audit downstream conversions before declaring an upstream bug |
| Register 1422 flow scale | Current local result was zero | Compare nonzero telemetry and volume deltas; treat bypass/measurement location separately from cup yield |
| Mode 2 versus modes 0–3 | GeeFlow compiles native profiles as mode 2; LitaLite gives four goal/style labels | Read back a known official-app-created profile and mode/header together |
| Slots 3048/3560 and stage capacity | Possible wrong address or overlap | Inspect app-generated writes/readback; no speculative writes or inferred 512-register correction |
| Mode 4 weight data | Intermediate and endpoint scaling differ upstream; real scale evidence incomplete | Capture known app profile with scale, inspect table layout; continue rejecting mode 4 |
| FF55 `80`/`87`/`8b`/`8c` | Scale versus name/session interpretations conflict | Trace characteristic, direction, payload and UI action together; version/model may explain differences |
| FF55 length encoding | Two-byte length versus reserved byte + one-byte length; Variant-B prose inconsistent | Collect independent well-framed examples; short packets cannot distinguish both interpretations |
| Alarm enable versus asserted alarm | Disabling detection is not clearing a fault | Read 396 and 1406 independently, compare UI; never infer one from the other |
| Standby/calibration/fault names | Static symbols may not map to this model | Trace official-app version-specific code/UI to addresses; passive evidence first |
| Persistence and disconnect behavior | ACK says nothing about durable state or safe loss of control | Readback first; separately approved idle reconnect/power-cycle checks; do not experiment mid-shot |

## Technical audit notes

These facts come from the pinned GeeFlow sources linked in the capability map, cross-checked with LitaLite/Crema. All are upstream-only until a DATA S fixture says otherwise.

### Configuration and operating state

- FC03 configuration block 0–36 includes cleaning registers 0/1/2, boiler-enable 6/7, targets 8/9, manual time 17, pressure 19, heating mode 22 and bind 30. Reading a block does not imply every field is understood or safe to write.
- Boiler enable uses inverted polarity (0 enabled), unlike water-alarm enable (1 enabled at 396). Temperature targets are whole °C, while measured temperatures are tenths.
- GeeFlow application bounds include brew target 0–110 °C, steam target 0–140 °C, manual time 0–60 s, manual pressure 0.1–12 bar, cleaning/rest 1–60 s and repeats 1–10. These are **app limits, not manufacturer-validated safe operating ranges**; do not transplant them as HA safety limits.
- Status read starts at coil 182. Parser masks are payload byte 0: manual `0x10`, cleaning `0x20`, profile `0x03`; byte 1: free-variable `0x08`. With standard least-significant-bit-first coil packing, this implies coils 186, 187, 182/183 and 193 respectively. That address derivation is an inference, not a separately captured single-coil map.
- GeeFlow chooses manual, then cleaning, then free-variable, then profile, then idle when interpreting flags. Our diagnostics should preserve contradictory flags rather than hide them behind a priority rule.
- Manual/profile/cleaning start and stop each share their respective pulse. Guarding a pulse with cached state is not sufficient protection from stale-state or concurrent-owner races.
- Free-variable prepare writes 15=4 and 1459=0 (pressure) or 1 (flow), then uses coil 157 and target pair 1419/1420. GeeFlow's stop refreshes state, zeroes targets, conditionally pulses, and refreshes again. No local safety guarantee follows from that sequence.
- Settings setters update their cache after an acknowledgment. That is not independent readback or proof of persistence.

### Profiles

- Native staged profile: bases 2048 (active) / 2560 (bound); seven-register header, first step at base+8; six meaningful fields per step with stride nine. Step fields describe whole seconds, pressure × 10, flow × 10, wait seconds, last-step and flow-priority flags. Header and gaps need full fixture/readback coverage.
- Mode selector 87 is active; 88 is bound. Binding uses register 30=1 after upload. GeeFlow's native compiler emits mode 2 and a separate header discriminator for weight/volume. Do not conflate mode enum labels with goal type.
- Upstream native limits include pressure 12 bar and flow 8 mL/s. A register's maximum representable duration (65535 seconds) is not a sensible brew safety limit. Stage count must be constrained by verified slot capacity and non-overlap, not merely integer width.
- Mode 4 is a different format: sampled recording with 127 samples at 500 ms intervals plus endpoint, split across eight 64-register blocks at 760, 824, 888, 952, 1016, 1080, 1500 and 1564 (pressure, volume, weight, flow pairs).
- Mode-4 auxiliaries include 79 goal type (0 weight / 1 volume), 87/88 mode 4, 362 control (0 pressure / 1 flow), 358 target, 366 autolink, and 356 marker `0x7f7f`. Pressure/flow samples use tenths; recorded weight intermediate samples and terminal value differ in scaling upstream and lack sufficient real-scale evidence. Do not implement from this summary alone.
- Compiler writes are prepared before sending and responses awaited, but the reviewed start path does not establish complete readback before activation. Our upload and start must be separate.
- Host-executed profiles with conditions/ramps are distinct from device-native profiles. GeeFlow marks live regulator switching unsupported and uses host logic for some flow behavior; its live session uses a 100 ms minimum update interval and a 2 s telemetry timeout. These are implementation choices, not locally validated transport or device safety specifications.

### FF55/accessories

- GeeFlow uses opcode `9a` for scale connectivity query and enable/disable (payload `04` / `00`); `8c` for list, `8b` for status, `80` with name for connect and `87` with name for disconnect.
- Its parser labels `81` as found, `80` active, `86` connected, `88` disconnected, `04` serial and `83` heartbeat. Direction and context matter; LitaLite assigns some overlapping codes other meanings. Never send them based only on their names.
- Variant-B fixed prefix is `FF5502592000`; examples are insufficient for a full grinder/status schema. The notebook's length prose conflicts with its example byte counts.
- Tare/timer through direct Bookoo BLE is not proof that the machine forwards those operations. Keep accessory capabilities separate from machine capabilities.

## Definition of done

Per capability, maintain a result record containing:

```text
capability_id; source_revision; model; firmware; app_version;
evidence_level; fixture_reference; units_and_limits; prerequisites;
physical_comparison; readback_result; failure_behavior; persistence;
offline_tests; hardware_test_date; ha_tests; unresolved_questions
```

Unknown values remain unknown. Mark a capability “not available” only with adequate model/version-specific evidence, not because one repository omitted it. Every official-app screen/action must eventually map to a capability ID or an explicitly app-only feature. A full map also tracks denied/unsupported operations rather than exposing everything remotely.

For the first usable HA milestone: reproducible Python transport, verified sensors and state, shared Bluetooth discovery, unique IDs, duplicate prevention, reconnect/unavailable behavior, redacted diagnostics and tests. Remote brewing is not required for that milestone.
