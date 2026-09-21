# Experimental read-only Home Assistant integration

Implemented and tested offline on 2026-09-20 using **Home Assistant 2026.9.3 / Python 3.14.7**. Bobby's HA 2026.9.1 host and its registered ESPHome Bluetooth proxy were inspected read-only, but this integration was not installed or run there. No four-read capture or physical comparison was performed. Compatibility with HA 2026.9.1 and the real proxy remains unverified.

## Included

- Shared Bluetooth discovery for connectable `WDG_Data_*` advertisements, manual selection from HA's discovery cache, explicit polling confirmation and duplicate prevention.
- Nine measurement sensors plus water shortage and last-poll reachability binary sensors.
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

Enabled does not mean physically validated. Every value still inherits the evidence limits in [CAPABILITIES.md](../CAPABILITIES.md). Pumped volume is not cup yield, and pump pressure is not necessarily puck pressure. Unknown scale connectivity means zero weight cannot be treated as proof of an empty cup.

Reachable means the **last poll succeeded**, not that a BLE connection is currently held. All other entities become unavailable after a failed poll. Diagnostics omit the previous sample after failure rather than present it as current.

## Polling and safety behavior

Confirmation starts polling every 30 seconds by default (10–300 seconds selectable during setup). Each poll resolves a connectable BLE device through HA, opens a short session, subscribes, sends exactly one request `01 03 05 7c 00 16 05 10`, and disconnects. Configuration/status reads are never part of scheduled polling.

The separate `wendougee_data.capture_read_only_baseline` action is intended only for an explicitly approved evidence session. It requires selecting a loaded integration entry, typing `READ ONLY`, and requesting the action response. The action serializes against polling, opens one bounded session, sends telemetry, configuration, water-alarm-setting and operating-state reads exactly once each, and returns request/response hex marked `private_unreviewed`. It does not retry an uncertain transaction. Keep the response private until it has passed the evidence review in [EVIDENCE_COLLECTION.md](EVIDENCE_COLLECTION.md).

There is one connection attempt per poll and no automatic resend of an uncertain request. A later poll starts a fresh session. HA's normal setup-retry mechanism handles initial connection failure. Malformed replies, timeout or disconnect invalidate that sample. Unloading cancels scheduled/in-flight reads and awaits cleanup.

The cadence is conservative, not hardware-validated. It is intended for basic monitoring, **not full shot graphs or safety-critical automation**. A 30-second interval can miss an entire shot or a short alarm. The official app may contend for the single-central connection; close other clients during live validation. Bounded disconnect attempts cannot guarantee radio cleanup if the platform/backend itself fails.

Unknown fields, detailed faults, boiler configuration, operating-state entities and controls are not exposed in this milestone. Disable/remove the integration to stop polling. Changing the interval currently requires removing/re-adding the entry; IDs remain the same for the same address.

## Packaging and later installation

Build locally without connecting to hardware:

```sh
python scripts/build_integration.py
```

This generates `dist/wendougee_data.zip`, containing `custom_components/wendougee_data/` and the project's MIT license. The build copies only named **original project** protocol modules into a generated `_protocol/` package. The source of truth remains `src/wendougee_data/`; do not edit generated copies. The standalone scanner is excluded. There is no dependency on an unpublished `wendougee-data` PyPI package.

The ZIP can be inspected without running it. Installing, restarting HA, and confirming polling are **future approval-gated steps**, not actions performed by this build. Before installation, back up the HA configuration and inspect any existing component directory; do not blindly overwrite it. Extract the generated `custom_components/wendougee_data/` into the HA configuration directory, restart HA, then use Settings → Devices & services to discover/add Wendougee DATA. Keep the machine attended for its first approved validation.

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

Test coverage includes confirmation, duplicate/unsupported discovery, manual selection, all entity values/units, disabled defaults, stable IDs across reloads, failure/recovery, setup retry, unload cancellation, scheduled polling, GATT validation, telemetry-only enforcement for normal sessions, the fixed four-read baseline, subscription cleanup and privacy-safe diagnostics. Packaging tests compare generated code with its original source and exclude capture/scanner files.

The next meaningful gate is an approved live read and physical comparison, followed by an explicitly approved test deployment. This document does not grant either approval.
