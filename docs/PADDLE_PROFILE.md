# Paddle-bound versus app-selected profile

Owner clarification, 2026-09-26: the requested default-shot action must execute
the recipe bound to the **physical paddle**, not whichever profile an app last
uploaded for immediate execution. We must not silently substitute the latter.

## Evidence, not yet exact-machine control proof

The pinned GeeFlow DATA S implementation distinguishes:

| Purpose | Mode register | Constant/variable recipe bank |
|---|---:|---:|
| Active app-selected profile | 87 | 2048 |
| Paddle/button-bound profile | 88 | 2560 |

Its `bindProfile` uploads the bound bank, then writes register 30 with value 1.
Its app `startProfileBrewing` instead uploads the active bank and pulses coil 150.
Therefore coil 150 alone is **not established as a command to run the bound bank**.
Neither re-binding nor copying banks is authorized as an invisible substitute for
the requested start action; both change machine configuration.

GeeFlow calls coil 154 manual brewing; LitaLite describes a configured-shot latch
verified primarily on LITA-BA, while Crema calls it a raw three-way valve. The
existing conflict remains unresolved for this DATA S. Do not probe coil 154 merely
to discover which interpretation is correct.

Sources: the pinned revisions in [UPSTREAM_SOURCES](../research/UPSTREAM_SOURCES.md),
GeeFlow `WendougeeRegisters.kt`, `WendougeeProfileCompiler.kt`,
`WendougeeDataSController.kt`; LitaLite `PROTOCOL.md`; Crema
`MachineConstants.swift`. This is independently written documentation, not copied
implementation. No new live control evidence was obtained in this work.

## Current deployment and next evidence

0.2.0 enables only the brew/steam boiler switches on the target. The optional
app-profile start implementation is off, and Espresso displays a pending note
instead of the wrong shot button. No boiler or pump activation was performed.

Next, capture one normal **user-operated paddle shot** with read-only telemetry
and operating-state capture, alongside read-only identification of mode/binding
and profile banks. This can identify the state path and recipe differences; it
cannot by itself prove a remote trigger. Then correlate an official-app action
explicitly intended for the bound recipe, or obtain exact-model protocol evidence,
before implementing and supervising the remote activation test. Preserve both
recipe banks and binding settings throughout; reject mode 4 and unknown modes.
