# Dashboard visual regression repair

Owner screenshot showed three configuration errors on Trends. Entity availability
and backend template validation had passed but did not exercise frontend card
construction. Prior visual validation was explicitly incomplete; this gap allowed
the defect through.

An isolated Chrome session reproduced all three errors at 390 × 844. The actual
error-card configuration reported **Collection keys must start with energy_.**
The date selector and both linked statistics graphs used `espresso_trends`.
All three now use `energy_espresso_trends`; a failing-then-passing regression test
enforces the shared key and required prefix. No statistic entity, recorded history,
machine state or scheduling setting was changed.

Live dashboard backed up before saving; saved configuration readback matched.
All 41 entity references available; four current templates and three maintenance
branches passed backend checks. Actual rendered Overview, Shots, Trends and
Evidence tabs were captured and inspected at phone (390 × 844) and desktop
(1440 × 1000) widths. Card counts were 48, 7, 6, 9 respectively, with zero
`hui-error-card` instances in all eight views. Screenshots remain private because
desktop navigation contains unrelated home details. Empty current-day charts and
the no-captured-shot placeholder are valid states, not missing-entity errors.

Clicked Previous in the date selector: both linked graphs requested September 26
statistics (04:00 UTC through September 27 03:59:59.999 UTC, matching local EDT).
Captured and inspected the populated previous-day view, then clicked Next back
to the current day with no rendered errors. All 281 tests pass (164 + 117), as
do lint, formatting, compilation, JSON and whitespace checks.

Native UI control timed out. An isolated browser used an ephemeral in-memory
credential and a localhost-only SSH tunnel; no browser profile or credential was
retained. No power, schedule, shot, cleaning or benchmark control was clicked.
Future dashboard work must include rendered screenshots and safe interaction
checks, not just YAML/entity validation; this is now in AGENTS.md.

## Boiler-card priority follow-up

Moved both power/schedule cards immediately beneath the machine image and added
reported setpoint plus measured temperature beneath each power switch. Captured
phone/desktop overview and individual boiler cards; shortened titles and On/Off
time labels after spotting truncation. Temperatures retain HA's selected display
units and setpoints are explicitly read-only. All four tabs were rechecked for
rendered errors, and date navigation was retested. No machine action was fired.
