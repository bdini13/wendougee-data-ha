# Experimental Home Assistant integration

## 0.3.0 attended cleaning

The new **Start cleaning** button and `wendougee_data.start_cleaning` action use
the machine's stored run/standing/count parameters without changing them. Enable
the separate cleaning option and prepare the blind basket for attended use. The
action observes the nominal program window and return to idle, and retains a
persistent lock on any uncertain result. It neither retries nor sends a stop toggle.
See [cleaning settings, limits and recovery](CLEANING_CONTROL.md). Live cleaning
commissioning is still pending; installation does not run a cycle.

## Existing boiler/profile controls

Version 0.2.0 adds independent **Steam boiler** / **Brew boiler** switches and
**Start stored profile**. Open the integration's Configure/options dialog to
enable either category; both default off. Setup/reload does not activate a control.
The button starts the current active stored mode-2 profile, not necessarily the
paddle-bound recipe. It does not select or upload a profile. The boiler switches
do not change temperature targets. Hardware commissioning remains pending.

The target's boiler switches are enabled; cleaning has its own opt-in. The owner requested
the paddle-bound recipe, whose remote trigger is not established; the different
app-selected-profile control remains off. Espresso shows that distinction rather
than exposing a misleading shot button. See [paddle evidence](PADDLE_PROFILE.md).

Prepare the machine and cup and supervise the first use. An uncertain start
locks repeats durably. After physically checking the machine, invoke
`wendougee_data.acknowledge_profile_uncertainty` with `MACHINE CHECKED`;
the integration must also read a fresh idle state. Do not treat this as stop.
See [the current control design](CONTROL_DESIGN.md) and [README](../README.md#machine-controls).

The following 0.1.2 deployment history describes the earlier read-only release;
its statement that no controls were exposed does not apply to 0.2.0 opt-ins.

Version `0.1.2` is installed on Bobby's HA 2026.9.1 host after a fresh full backup, checksum verification, successful configuration check and healthy restart. Its corrected benchmark selected 2 Hz for complete telemetry/state pairs through the installed ESPHome proxy. A later apparent proxy lifecycle regression was traced on 2026-09-26 to the standalone diagnostic harness omitting ESPHome's required advertisement subscription. The corrected Proxy 2 path connected, discovered services and returned valid telemetry on ESPHome 2026.7.2 and restored 2026.9.0. A separate telemetry-only ladder accepted 8 Hz and rejected 10 Hz for insufficient cadence. A configuration-checked HA Core restart then restored all 22 enabled entities; a fresh paired benchmark selected 2 Hz and the first successful 10-second private trace completed 20 correlated idle samples at 1.99 Hz. The Espresso dashboard, original artwork and disabled-by-default 07:00–09:00 schedule planners are installed. Its bundled boiler-frame module has no Home Assistant transport or service path. Offline framework testing uses **Home Assistant 2026.9.3 / Python 3.14.7**. See the [sanitized live-validation record](LIVE_VALIDATION_2026-09-21.md).

## Included

- Shared Bluetooth discovery for connectable `WDG_Data_*` advertisements, manual selection from HA's discovery cache, explicit polling confirmation and duplicate prevention.
- Nine telemetry sensors, eight decoded-setting sensors, one operating-state sensor, five persistent observed-activity sensors and seven binary sensors: 30 read-only entities total in 0.1.0.
- Bounded, serialized read-only transactions, cleanup on failure/unload, unavailable measurements after a failed poll, and fresh-connection recovery on later polls.
- Stable hashed device/entity identifiers and allowlisted diagnostics with no addresses, names, hashes, raw packets or exception text. Schema 3 adds UTC timestamps and in-memory success, failure and consecutive-failure counters for coordinator polls.
- Persistent observed-shot count, observed pumped-water total, last shot/time/volume and last observed backflush. These are conservative lower bounds because polling can miss complete events.
- One response-only `capture_read_only_baseline` action, requiring the literal confirmation `READ ONLY`, for the four fixed evidence reads through HA's shared Bluetooth path.
- Two response-only evidence actions: a bounded 1 → 2 → 5 → 10 Hz sampling benchmark and a 10–180 second private trace capture at the fastest clean stage. They also require `READ ONLY` and are unavailable as automatic actions.
- No arbitrary command interface, FF55 initialization, standalone scanner, pairing, or cloud backend. Controls require the separate 0.2.0 options above.

Bluetooth discovery and connection selection follow [Home Assistant's shared Bluetooth APIs](https://developers.home-assistant.io/docs/core/bluetooth/api/). Device responses are handled by our independently implemented protocol library.

## Entities

| Entity | Native unit | Default |
|---|---|---|
| Brew temperature | °C | Enabled |
| Steam temperature | °C | Enabled |
| Pump pressure | bar | Enabled |
| Pumped volume | mL | Enabled |
| Flow rate | mL/s | Disabled: scaling needs physical confirmation |
| Scale weight | g | Disabled: connected scale behavior unverified |
| Weight rate | g/s | Disabled: scale/sign behavior unverified |
| Elapsed brew time | s | Disabled: raw time scaling needs confirmation |
| Pump active time | s | Disabled: semantics need confirmation |
| Water shortage | Problem binary sensor | Enabled; not an interlock |
| Reachable | Connectivity binary sensor | Enabled; diagnostic |
| Steam/brew heating enabled | Boolean binary sensors | Disabled: physical comparison pending |
| Water-alarm detection enabled | Boolean binary sensor | Disabled: physical comparison pending |
| Steam/brew targets and heating mode | °C / enum | Disabled: physical comparison pending |
| Manual time / pressure settings | s / bar | Disabled: physical comparison pending |
| Cleaning time / rest / repetitions | s / count | Disabled: physical comparison pending |
| Operating state | Enum | Disabled: transition observation pending |
| Observed shot / cleaning active | Boolean | Enabled; poll-observed only |
| Observed shots / pumped water total | Count / mL | Enabled; persistent total-increasing statistics |
| Last observed shot / volume / backflush | Timestamp / mL | Enabled; unavailable until observed |

Enabled does not mean physically validated. Every value still inherits the evidence limits in [CAPABILITIES.md](../CAPABILITIES.md). Pumped volume is not cup yield, and pump pressure is not necessarily puck pressure. Unknown scale connectivity means zero weight cannot be treated as proof of an empty cup.

Reachable means the **last poll succeeded**, not that a BLE connection is currently held. All other entities become unavailable after a failed poll. Diagnostics omit the previous sample after failure rather than present it as current. Poll-health counters reset when the integration loads; they are operational evidence for that runtime, not durable lifetime totals.

## Polling and safety behavior

Confirmation starts polling every 30 seconds by default (10–300 seconds selectable during setup). Each poll resolves a connectable BLE device through HA, opens a short session, reads telemetry and operating state, and disconnects. Every twentieth poll uses the complete fixed four-read set to refresh configuration and water-alarm-enable state as well. No arbitrary address or write operation is accepted.

The separate `wendougee_data.capture_read_only_baseline` action is intended only for an explicitly approved evidence session. It requires selecting a loaded integration entry, typing `READ ONLY`, and requesting the action response. The action serializes against polling, opens one bounded session, sends telemetry, configuration, water-alarm-setting and operating-state reads exactly once each, and returns request/response hex marked `private_unreviewed`. It does not retry an uncertain transaction. Keep the response private until it has passed the evidence review in [EVIDENCE_COLLECTION.md](EVIDENCE_COLLECTION.md).

Version 0.1.2 corrects `wendougee_data.benchmark_read_only_sampling`. It connects first, then measures three-second stages at 1, 2, 5 and 10 Hz, one serialized telemetry/state pair at a time, using the same 15-second session timeout as normal proxy reads. A stage is accepted only when it completes without a protocol/transport failure and sustains at least 85% of its requested cadence. The first failed stage ends the benchmark; no failed transaction is retried. The response includes either `transport_or_protocol_failure` or `insufficient_cadence` for a rejected stage instead of replacing all results with a generic action error. The fastest clean stage exists only in memory and must be revalidated after an integration reload or HA restart.

On this installation, the latest corrected HA benchmark accepted 1 Hz and 2 Hz, then rejected 5 Hz for insufficient cadence after sustaining 2.22 complete pairs/s with roughly 441 ms mean pair round-trip time. Two hertz remains the selected rate for the **two-read pair path through this proxy**. A separate direct-proxy telemetry-only ladder accepted 8 Hz (8.10 reads/s, 122 ms mean round trip) and rejected 10 Hz after sustaining 8.01 reads/s. The telemetry-only result does not change the integration's paired-sample selection.

After a successful benchmark, `wendougee_data.capture_read_only_trace` records 10–180 seconds at the selected rate. It uses one bounded connection epoch, updates the activity tracker from every correlated sample, and creates a unique owner-only JSON file beneath `wendougee_data_private_traces/` in the HA configuration directory. The file includes decoded values and raw response hex for private analysis. Never publish or commit it before the review procedure in [EVIDENCE_COLLECTION.md](EVIDENCE_COLLECTION.md).

There is one connection attempt per poll and no automatic resend of an uncertain request. A later poll starts a fresh session. HA's normal setup-retry mechanism handles initial connection failure. Malformed replies, timeout or disconnect invalidate that sample. Unloading cancels scheduled/in-flight reads and awaits cleanup.

The cadence is conservative, not hardware-validated. It is intended for basic monitoring, **not full shot graphs or safety-critical automation**. A 30-second interval can miss an entire shot or a short alarm. The official app may contend for the single-central connection; close other clients during live validation. Bounded disconnect attempts cannot guarantee radio cleanup if the platform/backend itself fails.

Unknown fields, detailed faults and controls are not exposed in this milestone. Configuration and operating-state entities are read-only and disabled by default; their presence is not evidence that the corresponding write is safe. Disable/remove the integration to stop polling. Changing the interval currently requires removing/re-adding the entry; IDs remain the same for the same address.

## Packaging and later installation

Build locally without connecting to hardware:

```sh
python scripts/build_integration.py
```

This generates `dist/wendougee_data.zip`, containing `custom_components/wendougee_data/` and the project's MIT license. The build copies only named **original project** protocol modules into a generated `_protocol/` package. The source of truth remains `src/wendougee_data/`; do not edit generated copies. The standalone scanner is excluded. There is no dependency on an unpublished `wendougee-data` PyPI package.

The ZIP can be inspected without running it. Installing, restarting HA, and confirming polling are **approval-gated steps**. Before installation, back up the HA configuration and inspect any existing component directory; do not blindly overwrite it. Extract the generated `custom_components/wendougee_data/` into the HA configuration directory, restart HA, then use Settings → Devices & services to discover/add WENDOUGEE DATA S. Keep the machine attended for its first approved validation.

For an approved headless deployment without an authenticated frontend session,
an empty YAML section provides the same explicit polling opt-in:

```yaml
wendougee_data: {}
```

After a validated restart, HA imports a single supported machine already in its
shared Bluetooth cache. If discovery arrives later, the same explicit YAML
opt-in accepts that matching discovery without requiring a browser session. A
cached import with multiple matches aborts without choosing a target. The
imported entry uses the conservative 30-second interval. Remove this YAML
section before deleting the entry if it must not be recreated on a later
restart. At startup the importer allows up to five minutes for a remote proxy
to populate HA's shared discovery cache; it sends no machine request while
waiting.

For a separately approved headless evidence session, use:

```yaml
wendougee_data:
  capture_baseline: true
```

Before the entry's first complete four-read refresh, this atomically creates
`.wendougee_data_baseline_attempted`. After that refresh succeeds, it creates an
owner-only `wendougee_data_private_baseline.json` in the HA configuration
directory with the same private response schema as the action. Presence of
either private file prevents another automatic capture after a reload or
restart. Routine entity refreshes may still issue the same fixed read
operations; only the private raw capture is one-shot. A failed capture is not
retried. This opt-in does not affect the manual response-only action.

This is a manual experimental package, not a published HACS release. Copying only the tracked source component directory will omit generated protocol files; use the build output. The package requires the Bluetooth integration and its matching `bleak-retry-connector==4.7.0` dependency. Do not claim compatibility with an HA version that requires a different dependency set without testing it.

## Development and verification

Keep two separate environments:

```sh
# Python 3.13: independent protocol/CLI tests
python -m pip install -e ".[test]"
python -m pytest

# Separate Python 3.14 environment: actual Home Assistant tests
python -m pip install -r requirements-ha-test.txt
python scripts/build_integration.py
python -m pytest -c pytest-ha.ini
```

Do not install the standalone package's constrained Bleak dependencies into the HA test environment. HA tests import the generated bundled protocol package, use HA's real config-flow/coordinator/entity machinery, fake all Bluetooth connections and disable network sockets. CI has separate protocol and HA jobs; adding a CI job does not mean the remote workflow has already run.

Test coverage includes confirmation, duplicate/unsupported discovery, manual selection, all 30 entity registrations, disabled defaults, stable IDs across reloads, persistent activity restoration, conservative transition counting, failure/recovery, setup retry, unload cancellation, split runtime/configuration polling, GATT validation, the fixed four-read baseline, serialized fast sampling, fail-closed rate selection, private owner-only trace storage, subscription cleanup and privacy-safe diagnostics. Packaging tests compare generated code with its original source, include the original project artwork and exclude capture/scanner files.

The matching source-controlled dashboard is documented in [DASHBOARD.md](DASHBOARD.md). Its schedule helpers are inert; the boiler transaction and schedule requirements are in [CONTROL_DESIGN.md](CONTROL_DESIGN.md).

The next meaningful gate is an attended, read-only physical comparison followed by deliberate disconnect, app-contention and extended soak testing. This document does not grant approval for any control write.
