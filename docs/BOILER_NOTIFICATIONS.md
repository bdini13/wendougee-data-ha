# Boiler phone notifications

Friendly copy distinguishes “☕ Espresso time! Brew boiler…” from “💨 Ready to
steam! Steam boiler…”. Shutdown says “😴 Taking a coffee break!” and retains the
boiler name, verified scheduled-shutdown wording and residual-heat warning.
Only wording changed; schedule gates, recipients and deduplication are unchanged.

`scripts/boiler_notifications.py` generates four native HA automations. Pass
explicit companion-phone services to `automations(recipients)`; personal recipients
stay outside Git. No machine commands, polling changes or restart are required.

Create persistent input_text helpers (max 100, **no initial value**), initializing
each once to `none`: `espresso_brew_ready_notified`, `espresso_brew_off_notified`,
`espresso_steam_ready_notified`, `espresso_steam_off_notified`. Install the returned
automation dictionaries through HA's configuration API/editor. Back up existing
automations and preserve unrelated entries.

- Ready checks every 30 seconds. Requires the individual schedule and boiler
  enabled, healthy communication, successful poll less than 90 seconds old,
  numeric temperature/target with matching units, and temperature at or above
  target. At most one ready alert per boiler per local calendar day, including
  already hot when its schedule is enabled. Not whole-machine thermal stability.
- Off requires a new verification timestamp less than 120 seconds old and
  `verified_off`, with the schedule enabled. Manual off, startup restoration,
  unavailable states and uncertain/failed transactions do not qualify. Already
  disabled at the scheduled check also counts. This is machine configuration
  readback, not independent relay/current measurement; boilers remain hot.
- Persisted markers are set before dispatch. Each phone is attempted independently;
  no automatic retries or delivery acknowledgements. Phone/network settings may
  prevent delivery. Normal HA helper persistence is not a transactional push queue.
- The optional schedule-failure blueprint remains inactive.

## Deployment verification — 2026-09-27

Both owner-requested phone services exist. All four configurations were read back
exactly and verified enabled. Existing automations backed up to
`/config/automations.yaml.before-espresso-notifications-20260927`.
Brew remains enabled 06:30–09:00 America/New_York; steam schedule remains disabled.
No machine command or test push sent. Actual receipt awaits a qualifying event.
Offline tests cover ready gating/deduplication and verified-off/startup exclusions.
