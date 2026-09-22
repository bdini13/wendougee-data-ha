# Boiler scheduling and control safety design

Status: **offline design only**. Home Assistant 0.1.0 contains no callable
machine-write path. The dashboard schedule helpers are inert planning inputs.

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
register. The module is bundled for offline tests, but the Home Assistant BLE
transport still rejects everything outside the fixed read allowlist.

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
