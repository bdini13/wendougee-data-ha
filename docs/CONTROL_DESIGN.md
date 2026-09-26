# Boiler scheduling and control safety design

Status: **0.2.0 implements opt-in boiler switches and stored-profile start**.
The dashboard schedule helpers remain inert planning inputs. Transactions have
synthetic protocol and HA framework coverage; physical commissioning is pending.
No hardware control was fired during implementation/deployment.

The owner clarified that "default stored profile" means the **physical paddle's
bound recipe**. That activation path is not established. The implemented optional
app-selected-profile path below is therefore **disabled on the target**, and its
button is omitted from Espresso. Only the two boiler switches are opted in.
See [paddle-binding evidence and the remaining test](PADDLE_PROFILE.md).

## Implemented control boundary

The default read transport is unchanged. A separate, short-lived transport admits
only the exact commands needed for a requested transaction. Boiler switches write
only registers 6/7, require fresh idle state, and compare all 37 configuration words
after the exact echo. Turning on additionally checks the reported water alarm.
No operation retries automatically. This is not an emergency-off mechanism.

The shot button pulses coil 150 on then off (100 ms), with bounded release cleanup
even when the press acknowledgement fails or the task is cancelled. It requires
brew enabled, no reported water alarm, active mode register 87 equal to 2, and fresh
idle state immediately before the pulse. It then checks for profile-running state.
It does not change register 87, the paddle binding at 88, a profile, or a setpoint.
"Stored profile" means the current active selection, not a promise that the paddle
uses that same recipe. Mode 4 and all other unverified modes are rejected.

A persistent start-uncertainty latch is saved before the operation; failures,
process death and cancellation cannot silently allow a repeat toggle. Only confirmed
success, known pre-control rejection, or explicit physical-check acknowledgement
with a new idle read clears it. A failed storage clear keeps it locked in memory.
The integration options are the category opt-in; direct HA `button.press` calls
have no physical-presence confirmation. Never schedule shot starts.

Remaining attended checks: separate boiler on/off with unrelated settings stable,
physical enable feedback, selected-profile/paddle relationship, press release,
actual shot start/finish, app contention, power-cycle persistence and fault recovery.
No automatic heating schedule or target-temperature control is enabled by this work.

## Independently implemented protocol facts

Pinned GeeFlow code identifies four FC06 single-register operations for the DATA
S. LitaLite's configuration map independently places the same values in the
0–36 block, although its live control work was primarily on LITA-BA.

| Setting | Register | Encoded value | Current local read evidence |
|---|---:|---|---|
| Steam boiler enabled | 6 | `0` enabled, `1` disabled | Read as disabled |
| Brew boiler enabled | 7 | `0` enabled, `1` disabled | Read as disabled |
| Steam target | 8 | Whole °C | Read as 126 °C |
| Brew target | 9 | Whole °C | Read as 92 °C |

`src/wendougee_data/controls.py` can build only these four request shapes and
validates an FC06 reply as an exact, CRC-valid echo. It accepts no arbitrary
register. The general setting builder remains offline-only for target temperatures.
The separate HA control transport admits only boiler enables and coil-150 pulses;
normal polling still rejects everything outside its fixed read allowlist.

The upstream application accepts broad 0–140 °C steam and 0–110 °C brew ranges.
Those are application bounds, **not manufacturer-validated safe operating
ranges**. They must not become the default Home Assistant limits without local
evidence and a conservative policy decision.

## Required live transaction

A future setting transaction must:

1. require an explicit opt-in for the specific control category;
2. obtain a fresh complete configuration read and verify idle/non-cleaning state;
3. skip the write when the machine already reports the requested value;
4. send one allowlisted FC06 request with no automatic retry;
5. require the exact CRC-valid echo for the same register and value;
6. reconnect after any timeout, disconnect or uncertain response;
7. read the complete configuration block and verify the requested value plus all
   unrelated protected fields;
8. report uncertainty instead of guessing whether a timed-out write succeeded.

Persistence across machine power cycles, official-app contention and two-client
races still require separate tests. A network automation is never a hardware
emergency stop.

## Schedule behavior after validation

The desired initial schedule is independently configurable for brew and steam:

- timezone: Home Assistant local timezone (`America/New_York` on the target);
- on time: 07:00;
- off time: 09:00;
- default enabled state: off until supervised commissioning;
- no startup catch-up that could unexpectedly heat the machine after a restart;
- no repeated setpoint writes at every schedule edge;
- no boiler-on action while brewing, cleaning, unreachable or ambiguous;
- an uncertain transaction disables that boiler's automation and raises a
  persistent notification instead of retrying blindly.

The off edge also uses read-before-write and readback. Although FC06 sets an
explicit value, transport uncertainty and concurrent ownership still make blind
retry unsafe.

## Cleaning/backflush boundary

Upstream implementations use a momentary coil-155 pulse for both starting and
stopping cleaning. That is a toggle-like action, not an idempotent off command.
The current integration only observes the cleaning-state bit and records the
timestamp of an observed active-to-idle transition as **Last observed
backflush**. It does not start or stop cleaning.

Before any cleaning action exists, an attended session must confirm coil 155,
the state transition, configured repetitions/timing, safe cancellation behavior
and loss-of-connection behavior on this exact DATA S.
