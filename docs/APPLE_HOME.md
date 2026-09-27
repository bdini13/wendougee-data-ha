# Apple Home and Siri

The existing HomeKit Bridge exposes the brew-boiler switch as **Espresso Machine**.
Owner explicitly selected brew-only behavior. This enables/disables brew heating,
not mains power. The machine must remain physically switched on.

- “Siri, turn on the espresso machine.”
- “Siri, turn off the espresso machine.”

Steam, shot-start and cleaning controls are not exposed. The physical device name
remains WENDOUGEE DATA S and entity ID remains
`switch.wendougee_data_s_brew_boiler`; only this switch's friendly label is
Espresso Machine. Existing guarded boiler transactions still handle commands.

Existing schedules remain independent: a Siri command does not disable scheduling.
Phone readiness alerts still require the brew schedule enabled; scheduled-off
alerts do not fire for a manual Siri shutdown. Boiler disabled feedback is machine
configuration readback, not independent electrical measurement.

## Deployment verification — 2026-09-27

Backed up the prior registry record and bridge options-flow details privately.
Used the supported entity registry and HomeKit options APIs, retaining the existing
garage-door selection and all other options. No new bridge or re-pairing was used.
Readback confirms an explicit two-entity filter (existing garage door plus brew
switch), no broad domain exposure. Loaded bridge diagnostics show the Espresso
Machine switch accessory and two paired clients. No boiler command, Core restart,
shot or cleaning action was sent. Apple Home UI appearance and HomePod voice
recognition still require owner confirmation; HA cannot prove the phone synced.

If it is not immediately visible, reopen Apple Home and inspect the bridge's
assigned room. Avoid deleting/re-pairing the bridge, which also carries the
existing garage door. Apple Home may retain a locally customized accessory name.
