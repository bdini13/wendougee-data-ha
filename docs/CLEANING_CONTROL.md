# Attended cleaning control · 0.3.0

The owner requested one supervised backflush using the existing machine settings.
The supplied official-app screenshots show **Cleaning time 5 s, Standing time 5 s,
Cleaning count 3**, agreeing with the preceding read-only register decode. The
screenshots establish those displayed values, not the machine's full allowed ranges.
Screenshots remain private; no image or raw capture was added to this repository.

## Stored parameters, not a hard-coded recipe

Start reads registers 0–36 freshly. Cleaning time and standing/rest time come from
registers 0 and 1 in tenths of seconds; count is register 2. They are **never written**
by this action. Settings changes remain in the official app for now. The action
reads them again on every invocation, so the implementation is not fixed to 5/5/3.

Initial pilot envelope: run and rest each 1–60 seconds, count 1–10, and
`(run + rest) × count ≤ 120 seconds`. These are conservative integration gates,
**not manufacturer safety limits or a claim of complete settings support**.
Unsupported programs fail before activation; values are never silently clamped.

## Start, observation and uncertainty

1. Enable the separate **attended cleaning** integration option (default off).
2. Fit the correct blind/backflush basket, prepare the machine according to its
   normal cleaning instructions, remain present, and disconnect competing apps.
3. Use the Espresso **Start stored cleaning program** confirmation, or the HA
   `wendougee_data.start_cleaning` action with the integration entry and literal
   `BACKFLUSH READY`. The action supports an optional response.
4. The integration rejects busy/unknown state, a reported water alarm, disabled
   brew boiler or unsupported parameters. It saves an uncertainty lock before
   entering the operation, then sends exactly one coil-155 press/release pair.
   Both replies must be exact CRC-valid echoes. Release is bounded and attempted
   even after press timeout or cancellation; no second press or stop is inferred.
5. All 37 configuration words must remain unchanged and cleaning state must be
   observed. Monitoring continues through at least the stored program's nominal
   window (including the last standing interval) and requires two successive idle
   observations. A final full configuration comparison must also remain unchanged.
   Entity observations update during this window, including backflush history.
6. Failure, cancellation or process death retains a persistent lock across reloads.
   Check the machine physically before using `acknowledge_cleaning_uncertainty`
   with `MACHINE CHECKED`; this additionally requires a fresh idle read. It does
   **not** stop the machine. A profile uncertainty also blocks cleaning and vice versa.

The dashboard confirmation and service phrase cannot prove physical preparation;
direct HA `button.press` calls can invoke the enabled button. Do not automate it.
Never loosen a pressurized portafilter. Loss of connectivity does not prove pump
stop. There is no remote emergency stop and no blind retry of this toggle command.

## Evidence limits

The command follows independently expressed protocol facts in the pinned GeeFlow
DATA S implementation: coil 155 press then release, operating-state cleaning mask
`0x20`. Existing polling and boiler transport evidence is not cleaning proof.
Synthetic tests cover command shape, parameter preservation, rejection, cancellation,
uncertain acknowledgements, monitoring, opt-in and durable lock behavior.

Deployment verification: 157 package/protocol and 61 HA tests pass. Version 0.3.0
was installed after a full HA backup, archive checksum and configuration check.
After restart, the new services and optional button were present, telemetry was
available, and the Espresso dashboard's 33 entity references resolved without
unavailable entities. Dashboard configuration was read back exactly and its three
maintenance-template branches validated against HA. No visual browser QA was done.

### First attended live test · 2026-09-26

After deployment, the owner freshly confirmed presence, fitted blind/backflush
basket, water readiness and app disconnection, and approved one stored program.
One HA service invocation was sent at 18:14:04 UTC (14:14:04 EDT). It returned:

- Program: 5 s cleaning, 5 s standing, 3 repetitions; no parameter writes.
- Result: `cleaning_observed_then_idle`; 34 observations across 30.491 seconds
  of monitoring after confirmed start, including two successive idle reads.
- Peak reported pump pressure: 9.9 bar, not an independently calibrated measurement.
- All 37 configuration registers unchanged after activation and at final readback.
- Last observed backflush updated to 18:14:36 UTC; uncertainty lock cleared.
- One start/release pair only; no retry, stop, boiler or profile command.

This verifies one real HA-initiated cleaning-state transition and unchanged
configuration. The owner subsequently confirmed observing all three physical
repetitions and successful normal completion. This completes the physical
comparison for this one stored-program run; individual intervals were not
independently timed. It does not prove cleaning effectiveness, chemical suitability,
cancellation safety or loss-of-connection behavior. Future attended tests still
need fresh readiness confirmation; deployment/setup/reload never starts cleaning.
