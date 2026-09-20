# Wendougee DATA · Home Assistant

Local-first espresso-machine telemetry over Bluetooth Low Energy. Starting with the **Wendougee DATA S**, working toward a thoroughly documented protocol and carefully validated controls.

[![Validate](https://github.com/bdini13/wendougee-data-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/bdini13/wendougee-data-ha/actions/workflows/validate.yml)
[![Status: experimental](https://img.shields.io/badge/status-experimental-orange)](#project-status)
[![Access: read only](https://img.shields.io/badge/access-read--only-blue)](#what-it-does)
[![HA tested: 2026.9.3](https://img.shields.io/badge/HA%20tested-2026.9.3-18BCF2?logo=homeassistant&logoColor=white)](docs/HOME_ASSISTANT.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Development: AI assisted](https://img.shields.io/badge/development-AI--assisted-8A2BE2)](AI_DISCLOSURE.md)

[Setup guide](docs/HOME_ASSISTANT.md) · [Capability map](CAPABILITIES.md) · [Roadmap](ROADMAP.md) · [Protocol](docs/protocol.md) · [AI disclosure](AI_DISCLOSURE.md)

> [!WARNING]
> **Experimental, not production-ready.** The Home Assistant integration is offline-tested but has not been deployed or validated against the physical machine. Do not use its sensors as safety interlocks. No remote brewing, boiler, cleaning, calibration, reset or firmware-update controls are implemented.

## What it does

- Discovers connectable `WDG_Data_*` machines through **Home Assistant's shared Bluetooth stack**.
- Requires confirmation before starting periodic read-only telemetry requests.
- Registers nine measurement sensors, a water-shortage alarm and last-poll reachability.
- Opens a short connection for each poll and disconnects afterward; default interval is 30 seconds.
- Makes measurements unavailable after a failed read and starts a fresh session on a later poll.
- Rejects unexpected responses and arbitrary commands; cleans up after partial setup, cancellation and unload.
- Exports allowlisted diagnostics without device addresses, names, hashes or raw packets.

**No runtime cloud account, AI service or manufacturer backend is required.** Initial dependency installation may require internet access. The integration only sends the established telemetry request; configuration and operating-state decoders exist in the independent library but are not enabled in HA.

### Available entities

| Measurement | Unit | Default |
|---|---|---|
| Brew / steam temperature | °C | Enabled |
| Pump pressure | bar | Enabled |
| Pumped volume | mL | Enabled |
| Flow rate | mL/s | Disabled pending unit validation |
| Scale weight / weight rate | g / g/s | Disabled pending accessory validation |
| Elapsed brew time / pump active time | s | Disabled pending timing validation |
| Water shortage | Problem | Enabled; not a safety interlock |
| Reachable | Connectivity | Enabled; represents the last poll |

All readings remain provisional until physical comparison. Pumped volume is not cup yield, and pump pressure is not necessarily puck pressure. The default polling interval can miss an entire shot; this is **basic monitoring, not a shot-graph recorder**. Five provisional measurements are disabled by default, not removed.

## Project status

| Area | Evidence / status |
|---|---|
| Local DATA S transport | Expected GATT service/characteristics and one CRC-valid idle telemetry reply observed |
| Physical value comparison | Pending; the native-helper reading was not compared with the machine display |
| Python protocol and session layer | Implemented; synthetic fixtures and fake-transport tests |
| HA integration | Implemented; actual HA framework with simulated Bluetooth |
| Verification baseline | **94 local tests passing:** 75 protocol/package + 19 HA tests, as of 2026-09-20 |
| Tested HA environment | Home Assistant 2026.9.3 / Python 3.14.7; no physical adapter/proxy compatibility claim |
| Deployment / release | Not deployed; experimental manual ZIP build, not a published HACS release |
| Device controls | Not implemented; gated by future evidence and supervised validation |

The previous hardware read used a native CoreBluetooth helper, **not the Python or HA client**. An implementation in another app is useful evidence, not proof that this integration is safe or compatible. See the [59-item capability map](CAPABILITIES.md) for source revisions, conflicts and unknowns.

The CI badge reports GitHub's workflow status, not an assertion that unpublished local changes have already passed remote CI.

## Build and installation

### Build without touching hardware

From a checkout, using Python 3.13 or newer:

```sh
python scripts/build_integration.py
```

Output: `dist/wendougee_data.zip`, containing `custom_components/wendougee_data/`, the original protocol modules and the MIT license. The build does not scan, connect to the machine, or deploy to Home Assistant.

The generated `_protocol/` directory and ZIP are deliberately ignored by Git. Their source and build recipe are committed. **Do not install only the tracked component directory:** it omits the generated protocol bundle.

### Install only for an approved test

1. Read the [HA setup and limitations guide](docs/HOME_ASSISTANT.md), confirm version compatibility and back up the HA configuration.
2. Inspect any existing component directory before extracting the ZIP into the HA configuration directory; do not blindly overwrite an existing installation.
3. Restart HA and add **Wendougee DATA** through Settings → Devices & services.
4. Disconnect E-Bar/other Bluetooth clients, prepare an attended validation session, and explicitly confirm read-only polling.

HA needs a connectable Bluetooth path to the machine. Other HA versions, proxies, firmware versions and Wendougee models remain unverified. Disable or remove the integration to stop polling. No installation or live test is performed by this documentation task.

## Roadmap

- [x] Research existing implementations and document protocol provenance.
- [x] Build the independent read-only protocol/session layer and capability map.
- [x] Implement offline-tested HA discovery, sensors, recovery, diagnostics and packaging.
- [ ] Validate the Python client, readings and connection lifecycle on the actual DATA S.
- [ ] Complete an approved HA deployment, reconnect/soak testing and sanitized fixture collection.
- [ ] Add verified configuration/status entities and complete the official-app feature inventory.
- [ ] Introduce narrowly scoped controls: settings first, profile upload/readback next, attended brewing/cleaning last.
- [ ] Finish release hardening, compatibility documentation and HACS packaging/validation.

The [detailed roadmap](ROADMAP.md) defines acceptance gates rather than promising dates or “100% support.” Calibration, raw valves, reset and OTA are not ordinary integration features and remain outside the initial control roadmap.

## Architecture

```text
HA discovery + confirmed setup
            │
            ▼
Polling coordinator → shared Bluetooth adapter → DATA S
            │           one read; disconnect
            ▼
Independent protocol validation and telemetry decoding
            │
            ▼
Read-only entities + redacted diagnostics
```

The source protocol package has no HA dependency. The build bundles only named original modules; it excludes the standalone BLE scanner. After a timeout or uncertain response, the session refuses further reads and requires a fresh connection. Modbus RTU lacks transaction IDs, so same-shaped unsolicited responses remain a protocol limitation—not something tests can eliminate.

## Development and checks

Keep the environments separate: the standalone client and HA use different Bleak dependency versions.

**Protocol/CLI — Python 3.13**

```sh
python3.13 -m venv .venv313
.venv313/bin/python -m pip install -e ".[test]"
.venv313/bin/python -m pytest
.venv313/bin/python -m ruff check .
.venv313/bin/python -m ruff format --check .
.venv313/bin/python -m compileall -q src custom_components tests scripts
```

**Home Assistant — separate Python 3.14 environment**

```sh
python3.14 -m venv .venv-ha
.venv-ha/bin/python -m pip install -r requirements-ha-test.txt
.venv-ha/bin/python scripts/build_integration.py
.venv-ha/bin/python -m pytest -c pytest-ha.ini
```

HA tests exercise the real framework with simulated Bluetooth and network sockets disabled. The CI workflow runs protocol and HA jobs separately. Passing tests do not establish hardware safety. Use test-driven development for behavior changes, preserve source provenance, and add fixtures before expanding the protocol allowlist.

## Documentation and issue labels

| Document | Purpose |
|---|---|
| [HA guide](docs/HOME_ASSISTANT.md) | Entities, installation, polling and compatibility limits |
| [Capability map](CAPABILITIES.md) | Known, implemented, conflicting and unknown functions |
| [Validation plan](docs/VALIDATION_PLAN.md) | Efficient test batches and evidence requirements |
| [Offline core](docs/OFFLINE_CORE.md) | Framing, session behavior and failure policy |
| [Protocol reference](docs/protocol.md) | BLE/Modbus observations and candidates |
| [Upstream inventory](research/UPSTREAM_SOURCES.md) | Pinned sources and license boundaries |
| [Contributor/agent handoff](CODEX_HANDOFF.md) | Implementation history and safety constraints |

[Issue-label definitions](.github/labels.json) group work by area, evidence and risk—for example `area:protocol`, `area:home-assistant`, `needs:hardware-validation`, and `safety`. This is a checked-in catalog, **not an assertion that these labels have been applied to GitHub**. When reporting a bug, include software/firmware versions, expected versus observed behavior and sanitized diagnostics. Never post credentials or raw captures publicly.

## AI disclosure

This project has been developed with **substantial AI assistance**, including Codex and Hermes, for research, implementation, tests, review assistance and documentation. The maintainer directs the work and authorizes hardware access; this does not imply independent human review of every generated line. Automated tests and AI review are not substitutes for physical validation or an independent safety review.

AI is used in development, **not in the integration's runtime**. See [AI_DISCLOSURE.md](AI_DISCLOSURE.md) for scope, limitations and accountability.

## Privacy, attribution and license

Raw captures, device-specific Bluetooth addresses/names, credentials, tokens, APKs and local HA state must stay out of commits and public reports. Diagnostics use an explicit allowlist; third-party debug logs still need manual review before sharing. Device IDs are address-derived hashes, not a guarantee of anonymity or stability across address changes.

Protocol research builds on [GeeFlow](https://github.com/drobekk/GeeFlow), [LitaLite](https://github.com/dallonby/LitaLite), [Crema](https://github.com/dallonby/Crema) and [DecentEbar](https://github.com/akiskev/DecentEbar). This project's Python implementation is independently written; upstream code with GPL, PolyForm or absent licensing is not bundled. See the [research inventory](research/UPSTREAM_SOURCES.md) for attribution and reuse boundaries.

Original project code is licensed under [MIT](LICENSE). This is an unofficial community project, not affiliated with or endorsed by Wendougee or Home Assistant.
