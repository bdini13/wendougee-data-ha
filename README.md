# Wendougee DATA Home Assistant

A local-first Home Assistant custom integration for Wendougee DATA-series espresso machines over Bluetooth Low Energy.

> [!IMPORTANT]
> This project is in the protocol-discovery stage. Device control is not implemented yet.

## Confirmed so far

- The Wendougee DATA S communicates with the official E-Bar app over Bluetooth Low Energy.
- A DATA S has been observed advertising with a local name matching `WDG_Data_*`.
- Nordic's nRF Sniffer for Bluetooth LE can capture its advertising traffic.

## Goals

- Local control without a cloud dependency
- Home Assistant config flow and Bluetooth discovery
- Read-only telemetry first
- Explicit, safety-conscious controls for machine state and brewing functions
- A documented BLE protocol with sanitized capture evidence

## Repository layout

- `custom_components/wendougee_data/` — Home Assistant custom integration
- `docs/protocol.md` — synthesized, sourced BLE protocol knowledge base
- `CODEX_HANDOFF.md` — current implementation brief and safety boundaries
- `research/UPSTREAM_SOURCES.md` — pinned inventory of related projects
- `captures/` — local packet captures (gitignored)

## Development status

1. ✅ Detect DATA S advertisements
2. 🚧 Capture and map official E-Bar app traffic
3. ⬜ Implement and test a standalone BLE client
4. ⬜ Add Home Assistant config flow and entities
5. ⬜ Validate against real hardware

## Privacy

Raw packet captures, Bluetooth addresses, pairing keys, credentials, and device-specific identifiers must not be committed.

## License

MIT
