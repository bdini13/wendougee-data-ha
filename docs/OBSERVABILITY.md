# Espresso observability · 0.5.0

This release improves visibility, not the machine's control permissions. All new
entities read cached state or bounded local storage. No new Bluetooth requests,
write addresses, automatic captures or control retries are introduced.

## Schedule health

Each boiler has a local health sensor: armed, executing, disabled, paused, check_machine,
control_disabled, invalid_times, blocked or not_listening. These stay available
during a machine-read failure, so the reason a schedule is paused remains visible.
Armed means listeners are installed and local prerequisites pass, not that the
future hardware command is guaranteed to succeed. Communication health is separate.

Attributes expose enable/listener/uncertainty state, on/off times, last result,
last verified timestamp and next eligible action/time. The next-edge calculation
uses HA's timezone-aware time matcher and skips a local date already attempted.
It is display-only and cannot enqueue an action. Verified results now persist
alongside existing uncertainty markers; old installations start with no recorded
verification. A failed off action can leave the boiler heating. No remote emergency
stop, startup catch-up, missed-edge replay or retry was added.

## Shot journal and chart

The existing private activity store now retains at most 30 completed observations
and one curve capped at 600 numeric samples. Raw frames, addresses and capture
filenames remain excluded. The journal attribute is excluded from Recorder to avoid
duplicating the entire history whenever a new shot arrives. Lifetime counters and
historical last-shot values are preserved; no old totals are converted into invented
records. Journal recording begins with new observations on this version.

Records contain first-idle timestamp, observed timer, observed peak pressure,
pumped volume, scale reading at first idle, source and coverage. **Scale at stop is
not final cup yield**; the final-yield field remains null. No weight-rate interpretation,
scale tare, stop-at-weight or new profile controls are implemented.

Routine polling may miss shots and peaks and is explicitly labelled poll/sparse.
An explicit successful trace feeds the same journal after capture completes. Only
capture-sourced samples produce a detailed curve. A counter/timer reset during
active state discards the stale prefix observed on the local machine. The existing
five-second, tightly sampled idle-tail rule refines volume without double-counting
water. An ambiguous end is not a completed journal record.

The native `image` platform serves an SVG through HA's image proxy; no frontend
plugins or public capture directory is needed. The three axes independently label
bar, mL and g. Lines break at gaps over two seconds. A later poll-only completed
shot clears the previous curve, avoiding a misleading latest-shot display.
HA image URLs contain rotating access tokens: do not publish those URLs.

## Dashboard installation

Use `dashboards/espresso.yaml`, with Overview, Shots, Trends and Evidence views.
Resolve entity IDs on the target; existing IDs are deliberately not renamed.
Enable the existing read-only scale-weight, heating-mode, manual-time,
manual-pressure and water-alarm-enable entities if disabled. Keep weight-rate
disabled. Targets are read-only; no inert temperature-editing helper is shown.

The date selector uses the `espresso_trends` collection shared by the two statistics
cards. Daily/weekly/monthly changes are lower-bound observed counts/volume, not
complete machine records, cup yield, steam usage or household consumption.
Backflush age is time since an observed cleaning-to-idle transition, not proof
of physical cleanliness or a manufacturer-prescribed interval.

## Optional phone notifications

Import `blueprints/automation/wendougee_data/schedule_failure.yaml` and create one
automation per desired boiler. Select its schedule-health sensor and a notification
action for your phone, with a message such as: “Espresso boiler schedule failed.
The boiler may still be on. Check the machine. No automatic retry was sent.”
The blueprint does not choose recipients, actuate equipment or send a test message.
It reacts to a new paused/check_machine state; delivery is not guaranteed and does
not replace the built-in persistent notification or physical safeguards.

## Updates and evidence boundaries

HA 2026.9.1 is the deployed baseline; tests use 2026.9.3. Updating HA is a separate
maintenance operation, deferred until the first scheduled cycle is verified.
No firmware/OTA update is part of this release. The app screenshot audit records
V3.1.5(260908), but the displayed OTA label is not assumed to be installed firmware.

References: [native image entity](https://developers.home-assistant.io/docs/core/entity/image/),
[tile features](https://www.home-assistant.io/dashboards/features/),
[statistics graph](https://www.home-assistant.io/dashboards/statistics-graph/),
[sections](https://www.home-assistant.io/dashboards/sections/),
[HA September release](https://www.home-assistant.io/blog/2026/09/02/release-20269/).
