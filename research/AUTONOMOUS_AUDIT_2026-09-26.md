# Autonomous protocol and feature audit · 2026-09-26

This pass reviewed public upstream changes and replayed existing private evidence.
No new machine connection, Modbus request, configuration write or control command
was initiated. Existing HA polling continued normally.

## Upstream changes since the last audit

GeeFlow advanced 15 commits from `10f2d191f984a35d021eb7127e3813fc3d6a8fa8`
to `cf5fe5f659e659718ca98430691503794001fb39`. Complete Git tree comparisons
confirmed identical blobs for all eight Wendougee controller/protocol files,
including registers, commands, frame parser, scale framing and profile compiler.
Only the demo controller changed within that controller directory. The local
reference checkout remains pinned at its original reviewed revision.

LitaLite and Crema HEADs still match the revisions in [the source inventory](UPSTREAM_SOURCES.md).

| Finding | Evidence | Implication for this project |
| --- | --- | --- |
| Device rename is app-local | GeeFlow's rename use case calls its repository, DAO and SQL `updateName`; no controller call | Use HA's existing device naming. Do not infer a BLE rename command or expand the FF55 allowlist. |
| Final telemetry can lag idle state | GeeFlow waits up to one second for fresh terminal telemetry while still connected and idle | An attended trace should retain several seconds after the shot ends. A telemetry/state pair is two sequential reads, not an atomic machine snapshot. |
| Free-control button reset is UI state | Error handling restores the app's button state | A UI reset does not establish physical pump stop or an acknowledged stop command. |
| Profile completion markers are calculated | Changes combine recorded measurements with configured finish conditions | Charts and phase boundaries may be computed by an app rather than reported by a distinct machine event. |

Sources: [rename implementation](https://github.com/drobekk/GeeFlow/commit/cf5fe5f659e659718ca98430691503794001fb39),
[terminal telemetry handling](https://github.com/drobekk/GeeFlow/blob/2913af67f8ae6948f5402fa100247969ff883b19/shared/domain/brew/src/commonMain/kotlin/app/geeflow/domain/brew/usecase/FinalBrewTelemetry.kt),
[completion changes](https://github.com/drobekk/GeeFlow/commit/2913af67f8ae6948f5402fa100247969ff883b19),
[free-control error behavior](https://github.com/drobekk/GeeFlow/commit/4eb40ba5781dbbf65057b8e1617e88a50b8a90dc).
These are source findings, not additional local hardware validation. No upstream
code or test fixture was copied into this MIT project.

## Heartbeat interpretation remains narrower than the name

GeeFlow labels opcode `0x83` as heartbeat, but its controller uses receipt to
mark smart-scale search active **only when smart-scale support is enabled** and
clears that indication after a ten-second timeout. It does not interpret our
binary marker as boiler readiness, machine health or a specific on/off state.
See the pinned [frame parser](https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeFrameParser.kt)
and [controller](https://github.com/drobekk/GeeFlow/blob/10f2d191f984a35d021eb7127e3813fc3d6a8fa8/shared/data/device/src/commonMain/kotlin/app/geeflow/data/device/impl/controller/WendougeeDataSController.kt).

Our 28 passive frames establish framing, checksum and an alternating marker.
The timestamped subset establishes a roughly six-second same-marker recurrence
through this proxy. It cannot settle accessory-search semantics without a
controlled accessory-state comparison. The parser therefore keeps `marker`
as an uninterpreted binary value; no HA readiness or search entity is added.

## Private idle trace replay

All 360 saved 49-byte telemetry replies passed the original strict decoder
again, including CRC, slave, function and length checks. The analysis streamed
private data directly from HA and emitted only aggregate register activity.

- Brew-temperature register 1409 had 24 distinct values and 257 transitions.
- Steam-temperature register 1408 had three distinct values and 17 transitions.
- The other 20 registers remained zero throughout this idle window.
- All 12 positions not mapped by our telemetry decoder—1404, 1407, 1413–1416,
  1418–1421 and 1424–1425—were constant zero. Some have upstream control-related
  hypotheses; this capture does not verify them.

There is no changing unknown field in this capture to correlate with a
heater-ready state, heater duty or fault. Zero is neither proof of unsupported
functionality nor validation of a proposed meaning.

## Consequences for shot analytics

Current HA polling reads telemetry before operating state. A shot may stop
between those reads. In addition, the activity tracker stores the peak volume
seen while the shot state is active; it does not yet incorporate a delayed
terminal volume into the previous shot. Therefore **last observed shot volume**
must continue to be presented as an observed value, not final cup yield.

Before changing this behavior, capture the stop boundary and subsequent idle
samples on the DATA S. Establish whether volume resets immediately, remains
latched or increases after idle; prevent cleaning activity or a later shot from
being assigned to the previous one. The saved idle trace contains no such
transition and cannot resolve this design choice.

## Useful next work

While unattended, static protocol review, offline replay, dashboard improvements
and regression testing remain productive. Repeating identical idle captures has
diminishing discovery value. The next decisive evidence is one normal manually
initiated shot including its final seconds and at least five seconds afterward,
followed by an attended scale/app comparison. Machine/app version provenance is
still needed to define a complete official-feature inventory.
