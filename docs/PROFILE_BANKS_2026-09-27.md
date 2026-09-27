# Read-only DATA S profile-bank snapshot — 2026-09-27

The owner approved investigating the active and physical-paddle-bound recipes.
A bounded, single-owner proxy diagnostic completed 12 serialized FC01/FC03
requests. No machine configuration/control write, profile upload, binding or
activation was sent. Raw frames remain in an owner-only, gitignored capture.

| Read | Observed value |
| --- | --- |
| Active selector, register 87 | 2 |
| Bound selector, register 88 | 2 |
| Active header, 2048–2054 | Seven zero words; unsupported/empty-looking, not a valid decoded recipe |
| Bound header, 2560–2566 | Volume finish, 65 mL, staged layout, auto-link flag 0 |
| First bound stage, 2568–2573 | 28 s, 9.0 bar, flow field 0, wait 0, terminal flag 1, pressure priority |

The bound header was reread and matched. Both selectors and all 37 configuration
words matched before/after. Operating-state reads were idle before, between banks
and after. Frame checks included CRC, slave, function and expected payload length.
FC03 does not echo the requested address; serialized reads cannot authenticate a
same-shaped unsolicited reply. This is a bounded observation, not an atomic dump
or proof of persistence across power loss. Unused stages were not scanned.

The bound values are consistent with the owner's app screenshot showing a bound
“Constant pressure 9bar” recipe with 65 mL. No profile name was read from BLE.
The 28-second field is a stored stage parameter, not a promise that a shot runs
exactly 28 seconds; the volume finish can matter. Actual execution semantics still
need comparison. The zero active header must not be interpreted as a safe recipe,
even though its selector is 2. Do not enable the existing app-profile start action.

## Meaning for remote paddle activation

This establishes readable, distinct active/bound storage on this DATA S. It does
**not** establish which remote command executes the bound bank. Coil 154 remains
conflicted; coil 150 must not be assumed to substitute. No copying/rebinding of
the bound profile into the active bank is authorized as a hidden workaround.

Next: obtain exact-model command evidence for bound-recipe activation, preferably
correlating an official-app action that explicitly promises that behavior. A
supervised start test is separate and requires fresh owner readiness approval.

## Implementation and provenance

`profile_reads.py` is an independently written, read-only research utility with
two documented banks, selectors and a finite 18-stage ceiling from the documented
167-word layout. It does not expand installed HA actions. Direct-layout headers,
unknown flags and mode 4 are not interpreted as staged recipes. Sources: pinned
GeeFlow register/compiler facts and LitaLite header/stage documentation, as listed
in `research/UPSTREAM_SOURCES.md`; no upstream implementation copied.

An initial helper import failed on local Python 3.9 before any Bluetooth access;
the private helper was corrected without changing production code. The successful
probe was followed by HA setup retries; an integration reload did not recover.
A successful configuration check and Core restart restored healthy telemetry at
09:41:08 UTC, brew armed 06:30–09:00 and steam schedule disabled. Both boilers
remained off, uncertainty locks clear, history unchanged. No component deployment.
Future reads should run through a tested HA coordinator diagnostic to avoid this
standalone connection-handoff failure mode.
