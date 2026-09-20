# Codex project instructions

## Goal

Build a safe, local-first Home Assistant integration for Wendougee DATA-family espresso machines, starting with the DATA S.

## Read first

1. `CODEX_HANDOFF.md`
2. `docs/protocol.md`
3. `research/UPSTREAM_SOURCES.md`

## Non-negotiable rules

- Use test-driven development: failing test first, minimal implementation, full-suite verification.
- Implement read-only telemetry before any control path.
- Never send BLE writes to real hardware without Bobby's explicit approval immediately before the test.
- Never send provisioning, reset, OTA, bootloader, raw-valve, boiler, cleaning, or brew commands during discovery work.
- Never commit raw captures, Bluetooth addresses, session tokens, APKs, credentials, or device-specific identifiers.
- Treat `research/upstream/` as read-only reference material; it is gitignored.
- Respect upstream licenses. Do not copy unlicensed, GPL-3.0, or PolyForm source into this MIT repository.
- Use Home Assistant's shared Bluetooth APIs in the integration; do not run an independent permanent Bleak scanner inside HA.
- Keep the protocol/client layer independent of Home Assistant.
- Preserve stable unique IDs and redact identifiers from diagnostics.

## First task

Follow the "First Codex task" section in `CODEX_HANDOFF.md`. Do not connect to hardware during that task.

## Verification before completion

- Run all tests.
- Run Python compilation and JSON validation.
- Run formatting/lint checks configured by the project.
- Show `git diff --check` and `git status --short`.
- State clearly whether any real-hardware test was performed.
