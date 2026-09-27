# Guarded daily boiler schedules · 0.4.0

The integration now connects the existing Espresso helpers to native Home
Assistant local-time listeners. No separate automation YAML is needed. Schedules
operate only when the integration's boiler-control opt-in and that boiler's
`input_boolean.espresso_<brew|steam>_schedule_enabled` are on. The matching
`input_datetime.espresso_<boiler>_on_time` and `_off_time` set daily edges.

The owner's requested configuration is **brew on 06:30, off 09:00**, with steam
disabled (its saved 07:00–09:00 times are preserved). HA uses `America/New_York`,
including daylight-saving changes, rather than fixed EST year-round.

The six existing storage helpers had explicit `initial` values from their earlier
planning-only setup. Those values reset brew to disabled/07:00 at restart. They
were removed through HA's helper-update APIs (same IDs, other helpers unchanged),
and the owner's 06:30–09:00/on and steam-off preferences restored. Do not add
`initial` overrides when creating these helpers if user choices should survive
restart; use normal HA restore-state behavior instead.

## What happens at an edge

1. Verify enablement, configured edge, exactly one machine entry, and no prior
   profile/cleaning/schedule uncertainty. Wait at most five seconds for the shared
   Bluetooth lock, then recheck. Requests more than 60 seconds late are skipped.
2. Save a per-boiler pending marker and that edge's local calendar date before
   any hardware transaction. Repeated fallback-hour callbacks cannot replay the
   same on/off edge, even across reloads; each edge runs at most once per day.
3. Use the existing boiler transaction: fresh configuration and idle state,
   water-alarm guard on heating, no write if already correct, otherwise one FC06
   enable-setting write, exact echo and all-37-register readback. No setpoint,
   profile, cleaning or shot command is permitted by this path.
4. Publish the verified configuration and clear the pending marker only after
   successful persistence. Nothing forces the schedule toggle back on if the
   owner disables it while an action is running.
5. A failed/busy/uncertain action turns that boiler's schedule helper off and
   raises an HA persistent notification. An uncertain attempt remains locked
   across restart. No automatic retry or compensating stop is sent.

Startup, reload and helper edits install only **future** listeners; missed times
are not caught up. Editing a time after that edge has already run does not grant
a second same-day execution. Changing/turning off a schedule does not immediately
switch the boiler; use the independent boiler switch for a manual action.

## Requirements and failure recovery

Keep the machine physically powered, its water supply ready, HA/proxy/Wi-Fi
operational, and competing phone apps disconnected. The schedule cannot turn on
an unplugged machine. If the machine is brewing, cleaning, unreachable or has
ambiguous status at an edge, the guarded action can fail and pause the schedule.
**A failed off action can leave the boiler on.** This is not an emergency stop
or a guarantee of shutdown during a network/power outage.

After a failure, physically check the machine. For a pending uncertainty lock,
run `wendougee_data.acknowledge_boiler_schedule` with the integration entry,
`boiler: brew` or `steam`, and `confirmation: MACHINE CHECKED`. This performs a
fresh idle read, clears only the schedule lock, and never starts/stops heating.
Re-enable the relevant schedule separately. It will wait for the next future edge.

Diagnostics contain each boiler's enablement, registered-listener status,
configured times, uncertainty marker and last runtime result. Helper absence or
invalid/equal times means no listener is installed; check diagnostics rather than
assuming an enabled toggle proves a valid schedule. Temperature planning helpers
are not connected to writes and are omitted from the active schedule cards.

## Verification boundary

Framework tests use simulated Bluetooth and cover clock firing, readback,
no startup/edit actuation, preserved disabled steam, duplicate/DST suppression,
bounded lock wait, storage failure, cancellation, restart uncertainty and recovery.
The on/off transport already has protocol tests and one attended steam-off
readback validation. **No new live boiler command was sent during this work; the
first scheduled brew on/off cycle still requires live verification.**

Deployment: fresh full backup with database, verified 0.4.0 archive and installed
file checksum, successful HA configuration check, retained 0.3.1 rollback copy.
Runtime diagnostics confirm brew enabled/listening at 06:30 and 09:00, steam
disabled/not listening, no uncertainty locks and both results `not_run`. Existing
shot/water/cleaning history and machine settings are preserved. The Espresso
dashboard has 31 resolved/available references and exact saved-config readback;
three maintenance-template branches pass. Local tests: 253 (157 package + 96 HA);
both implementation CI jobs passed. One isolated routine poll failure recovered
before verification; this is not extended reliability/soak evidence.

A second complete restart after removing helper startup overrides verified the
owner's settings persisted: brew enabled with both 06:30/09:00 listeners, steam
disabled without listeners, both pending markers false and both results `not_run`.
All 22 telemetry entities recovered, with both boilers still off and history
unchanged. The first poll after this restart succeeded; no schedule command was
sent during either restart or helper migration.
