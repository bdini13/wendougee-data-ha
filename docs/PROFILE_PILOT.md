# Attended 9 bar active-profile pilot · 0.6.0

## Validation status

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
