# Attended 9 bar active-profile pilot · 0.6.0

## Validation status

### September 29: control reader updated (0.6.3)

Preparation/start now read every bank word through the proven <=16-register
sequence. Their transport allowlists were updated without allowing any new
machine writes. Full 167-word comparisons, backup, exact pilot validation and
separate activation remain intact. 295 tests pass (174 protocol + 121 HA),
including distinct last-word fixtures for both banks. Lint/format/compile/JSON
and diff checks passed. No preparation or activation service was invoked.

Installed after checksum/config checks with the same-day full backup f3aba830
retained and a 0.6.2 component rollback copy. Runtime loaded 0.6.3, idle, normal
polling healthy, locks clear, profile opt-in disabled, brew schedule armed.
Archive SHA-256:
`0419c7327cea94cf6114e33ce381f8e58d587dc14b6959004f6aaef6e498a085`.
Next hardware step still requires fresh explicit approval for attended preparation
and separately confirmed start. The historical notes below describe prior builds.

### September 29: smaller reads verified (0.6.2)

One bounded HA read-only diagnostic succeeded: two complete snapshots of both
167-register banks in fixed chunks of at most 16 registers, all 334 words and
selectors matched. Idle checks bracketed both snapshots. The final seven-word
chunk includes the last register of each bank; nothing is skipped. Each response
passes the same strict identity, byte-count, length and CRC validation. Raw bank
contents are not returned or retained by this diagnostic.

The earlier same-bank 125-register request timed out; smaller chunking is a
verified workaround, not proof of the exact maximum or firmware-versus-proxy
cause. No larger-size sweep, upload, activation or automatic retry was performed.
Preparation/start still use the old reader pending a separately tested change;
do not claim remote brewing is fixed or validated.

Deployment reused the recent completed full backup f3aba830 and retained 0.6.1
for rollback. Config check/restart passed. Archive SHA-256:
`cff773c1601338c446c8ea6f1371f9db40a083f1818b7ce6110ef89b0e5c7ad3`.
294 tests pass (173 protocol + 121 HA), including last-word mutation detection;
lint/format/compile/JSON/diff checks pass. Post-audit runtime: three successful
polls, zero failures, idle, locks clear, remote profile control disabled and
brew schedule still armed for 09:00 local. No boiler settings/history changed.

Next: use the verified chunk sequence for preparation/start's full-bank reads,
update finite allowlists and regression tests, then obtain fresh owner approval
for a separate attended upload/start test. Do not weaken readback requirements.

September 29 reliability patch (0.6.1): preparation now persists a separate
`profile_preparation_locked` flag. Remote start and repeat preparation reject
either profile lock. Boiler schedules continue to check activation/cleaning and
their own uncertainty, but not recipe-preparation uncertainty; fresh idle/alarm
checks and full boiler configuration readback are unchanged. Old ambiguous
`profile_start_locked` records are deliberately not automatically reclassified.
The existing physical-check acknowledgement clears activation uncertainty only;
recipe uncertainty requires investigation/readback, not merely an idle check.

New `audit_profile_reads` action requires `READ ONLY` and reads idle state,
selectors and both complete banks through HA's shared serialized transport. Its
finite allowlist contains only FC01/FC03. First failure ends the run with a safe
stage/category; no addresses, raw replies, recipes or backend error text are
returned. A successful audit does not validate recipe contents or clear locks.
The latest result is available in diagnostics for this runtime. No automatic
retry or polling cadence change. Profile backup writes now explicitly fsync.

Live September 29 result: `active_head` / `timeout`, after successful state and
selector reads. This isolates the first large bank request (FC03, 2048, count
125), not the underlying machine/transport cause. No automatic smaller-read
fallback was attempted, and no machine control was sent. Post-diagnostic routine
polls succeeded with zero failed polls since load; both locks remained clear,
profile opt-in off, brew schedule armed for 09:00 local and steam schedule off.
Next evidence: bounded smaller reads of the same bank, maintaining full-bank
readback requirements before any future upload. Do not bypass verification.

Deployment: full backup f3aba830, retained 0.6.0 rollback, successful config check
and restart. Archive SHA-256:
`7d8821ab8af95b600bc58c5cb3102893e728da6a42a3ce7c9a5fad1fe4e2280d`.
293 tests passed (172 protocol + 121 HA), plus lint/format/compile/JSON/diff checks.

September 27: 170 protocol and 118 HA tests pass, including backup-before-write,
full readback, corrupt echo/bank rejection and durable uncertainty locking.
Full HA backup completed successfully before deployment. Live setup could not
obtain a telemetry sample after restart or entry reload; preparation was never
called and profile opt-in remained disabled. The prior 0.5.1 component was
restored for recovery. No hardware upload/start validation is claimed.

This is a narrowly scoped **app-style upload/start test**, not a discovered
remote paddle command. The owner explicitly approved copying the observed bound
recipe into active storage, leaving the paddle binding unchanged. Start remains
a separately confirmed operation; no automatic start, stop or retry is provided.

## Preparation

`wendougee_data.prepare_9_bar_profile` requires profile-control opt-in, the loaded
entry and confirmation `PREPARE 9 BAR PROFILE`. Busy Bluetooth sessions, uncertainty
locks, non-idle states, alarms, selectors other than 2/2 and recipes other than
the exact observed staged header/stage are rejected. Negotiated GATT payload
capacity must fit the 23-byte header; there is no speculative fragmentation.

Both 167-word banks, selectors and all 37 configuration words are backed up to an
exclusive owner-only JSON file under the existing private trace directory, with
schema `wendougee-data-profile-backup/v1`. The file is flushed/fsynced before writes.
Both banks/configuration are reread before the first write; source changes abort.

Only two fixed FC16 packets are writable: the terminal 28 s / 9 bar / pressure
priority stage at 2056, then the 65 mL staged header at 2048. No selector, binding,
boiler or coil write is allowed on the preparation transport. If already identical,
no upload occurs. Complete post-write bank comparison checks all unchanged words,
including inactive stages/gaps and every bound-bank word. Selectors/configuration
must match and the machine must remain idle. Timeout or mismatch leaves a durable
uncertainty lock; no automatic repair, rollback or activation follows.

## Separate activation

The opt-in stored-profile button now validates the full active-bank read against
the exact pilot header/stage before coil 150 press/release. An empty header with
mode 2 no longer passes. It also requires fresh idle, brew enabled and no water
alarm. Other recipes/modes are rejected, not generalized from this pilot.
The operator must be beside the machine, cup/portafilter/water ready, app
disconnected and able to use physical controls. Network stop is not guaranteed.

28 seconds is the stored stage parameter; volume termination can affect actual
duration. This pilot does not validate final weight, all profile modes, binding
semantics or unattended brewing. Testing uses original synthetic fixtures; upstream
protocol facts are attributed in the existing source inventory, not copied code.
