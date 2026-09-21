# Experimental read-only Home Assistant integration

Version `0.0.8` is implemented, tested offline using **Home Assistant 2026.9.3 / Python 3.14.7**, and installed on Bobby's HA 2026.9.1 host after a fresh full backup. On 2026-09-21 the target registered all 23 entities, returned schema-2 diagnostics, remained healthy beyond the ten-minute configuration-refresh cadence, and completed a config-entry reload through the active ESPHome proxy. The earlier 0.0.7 session performed the approved one-shot private baseline after the proxy entry's missing API encryption key was restored from its existing ESPHome configuration. See the [sanitized live-validation record](LIVE_VALIDATION_2026-09-21.md). Physical comparison, direct-Python validation, deliberate disconnect/app-contention testing and long-duration soak testing remain pending.

## Included

- Shared Bluetooth discovery for connectable `WDG_Data_*` advertisements, manual selection from HA's discovery cache, explicit polling confirmation and duplicate prevention.
- Nine telemetry sensors, eight decoded-setting sensors, one operating-state sensor and five binary sensors: 23 read-only entities total.
- Bounded, serialized read-only transactions, cleanup on failure/unload, unavailable measurements after a failed poll, and fresh-connection recovery on later polls.
- Stable hashed device/entity identifiers and allowlisted diagnostics with no addresses, names, hashes, raw packets or exception text.
- One response-only `capture_read_only_baseline` action, requiring the literal confirmation `READ ONLY`, for the four fixed evidence reads through HA's shared Bluetooth path.
- No controls, arbitrary command interface, FF55 initialization, standalone scanner, pairing, or cloud backend.

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

Enabled does not mean physically validated. Every value still inherits the evidence limits in [CAPABILITIES.md](../CAPABILITIES.md). Pumped volume is not cup yield, and pump pressure is not necessarily puck pressure. Unknown scale connectivity means zero weight cannot be treated as proof of an empty cup.

Reachable means the **last poll succeeded**, not that a BLE connection is currently held. All other entities become unavailable after a failed poll. Diagnostics omit the previous sample after failure rather than present it as current.

## Polling and safety behavior

Confirmation starts polling every 30 seconds by default (10–300 seconds selectable during setup). Each poll resolves a connectable BLE device through HA, opens a short session, reads telemetry and operating state, and disconnects. Every twentieth poll uses the complete fixed four-read set to refresh configuration and water-alarm-enable state as well. No arbitrary address or write operation is accepted.

The separate `wendougee_data.capture_read_only_baseline` action is intended only for an explicitly approved evidence session. It requires selecting a loaded integration entry, typing `READ ONLY`, and requesting the action response. The action serializes against polling, opens one bounded session, sends telemetry, configuration, water-alarm-setting and operating-state reads exactly once each, and returns request/response hex marked `private_unreviewed`. It does not retry an uncertain transaction. Keep the response private until it has passed the evidence review in [EVIDENCE_COLLECTION.md](EVIDENCE_COLLECTION.md).

There is one connection attempt per poll and no automatic resend of an uncertain request. A later poll starts a fresh session. HA's normal setup-retry mechanism handles initial connection failure. Malformed replies, timeout or disconnect invalidate that sample. Unloading cancels scheduled/in-flight reads and awaits cleanup.

The cadence is conservative, not hardware-validated. It is intended for basic monitoring, **not full shot graphs or safety-critical automation**. A 30-second interval can miss an entire shot or a short alarm. The official app may contend for the single-central connection; close other clients during live validation. Bounded disconnect attempts cannot guarantee radio cleanup if the platform/backend itself fails.

Unknown fields, detailed faults and controls are not exposed in this milestone. Configuration and operating-state entities are read-only and disabled by default; their presence is not evidence that the corresponding write is safe. Disable/remove the integration to stop polling. Changing the interval currently requires removing/re-adding the entry; IDs remain the same for the same address.

## Packaging and later installation

Build locally without connecting to hardware:

```sh
python scripts/build_integration.py
```

This generates `dist/wendougee_data.zip`, containing `custom_components/wendougee_data/` and the project's MIT license. The build copies only named **original project** protocol modules into a generated `_protocol/` package. The source of truth remains `src/wendougee_data/`; do not edit generated copies. The standalone scanner is excluded. There is no dependency on an unpublished `wendougee-data` PyPI package.

The ZIP can be inspected without running it. Installing, restarting HA, and confirming polling are **approval-gated steps**. Before installation, back up the HA configuration and inspect any existing component directory; do not blindly overwrite it. Extract the generated `custom_components/wendougee_data/` into the HA configuration directory, restart HA, then use Settings → Devices & services to discover/add Wendougee DATA. Keep the machine attended for its first approved validation.

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

Test coverage includes confirmation, duplicate/unsupported discovery, manual selection, all 23 entity values/units, disabled defaults, stable IDs across reloads, failure/recovery, setup retry, unload cancellation, split runtime/configuration polling, GATT validation, the fixed four-read baseline, subscription cleanup and privacy-safe diagnostics. Packaging tests compare generated code with its original source and exclude capture/scanner files.

The next meaningful gate is an attended, read-only physical comparison followed by deliberate disconnect, app-contention and extended soak testing. This document does not grant approval for a new hardware session or any control write.
