# Wendougee DATA Home Assistant

A local-first Home Assistant custom integration for Wendougee DATA-series espresso machines over Bluetooth Low Energy.

> [!IMPORTANT]
> This project is in the protocol-discovery stage. Device control is not implemented yet.

## Confirmed so far

- The Wendougee DATA S communicates with the official E-Bar app over Bluetooth Low Energy.
- A DATA S has been observed advertising with a local name matching `WDG_Data_*`.
- Nordic's nRF Sniffer for Bluetooth LE can capture its advertising traffic.
- A supervised local test verified the expected custom service and both communication characteristics on the DATA S.
- The documented function-03 telemetry request returned a CRC-valid 22-register response from the DATA S.

## Goals

- Local control without a cloud dependency
- Home Assistant config flow and Bluetooth discovery
- Read-only telemetry first
- Explicit, safety-conscious controls for machine state and brewing functions
- A documented BLE protocol with sanitized capture evidence

## Repository layout

- `src/wendougee_data/` — independently implemented read-only protocol library
- `tests/` — byte-fixture protocol tests that do not require hardware
- `custom_components/wendougee_data/` — Home Assistant custom integration
- `docs/protocol.md` — synthesized, sourced BLE protocol knowledge base
- `CODEX_HANDOFF.md` — current implementation brief and safety boundaries
- `research/UPSTREAM_SOURCES.md` — pinned inventory of related projects
- `research/LITALITE_CREMA_REVIEW.md` — focused correctness, safety, testing, and licensing review
- `captures/` — local packet captures (gitignored)

## Development status

1. ✅ Detect DATA S advertisements
2. ✅ Establish the safe telemetry request and register map from corroborated upstream work
3. ✅ Implement and validate the read-only protocol library and standalone BLE client
4. ⬜ Add Home Assistant config flow and entities
5. 🚧 Continue real-hardware validation against display values and operating states

## Development

Python 3.13 is required. Install the test tools and run the offline checks with:

```sh
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

## Privacy

Raw packet captures, Bluetooth addresses, pairing keys, credentials, and device-specific identifiers must not be committed.

## License

MIT
