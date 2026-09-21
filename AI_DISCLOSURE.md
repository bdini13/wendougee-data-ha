# AI-assisted development disclosure

## Scope

This repository has been developed with substantial AI assistance, including **OpenAI Codex and Hermes**. Assistance has included source research, protocol synthesis, architecture, code generation and editing, test development, review assistance, documentation and development-tool execution. It should not be represented as entirely hand-written software.

The maintainer sets the goals, directs development and approves hardware/deployment work. That is not a claim that every line has received independent human review. No independent safety certification or complete protocol audit is claimed.

## Verification and limits

- Tests use known protocol examples, synthetic fixtures and fake transports; HA tests exercise the real framework while substituting Bluetooth responses.
- Passing tests establish behavior under those inputs, not physical correctness or comprehensive compatibility.
- The earlier native-helper telemetry observation does not validate the Python/HA client, sensor calibration, controls or all firmware behavior.
- AI-assisted review can miss bugs and misunderstand undocumented protocols. Independent review, sanitized real fixtures and supervised physical validation remain necessary.
- Evidence levels, unresolved assumptions and upstream revisions are recorded in [CAPABILITIES.md](CAPABILITIES.md) and the [research inventory](research/UPSTREAM_SOURCES.md).

At the 2026-09-20 checkpoint, the read-only HA package is offline-tested and installed on the target HA host after a full backup. It has not created a config entry or completed a proxy-to-machine read because no matching advertisement was visible during validation. No control path is implemented. Current support claims belong in the README and capability map, not in model-generated confidence statements.

## Runtime and data

The integration itself does not call an AI model or require an AI account. Telemetry parsing and device communication run locally through Home Assistant/Bluetooth; there is no AI telemetry-upload feature. Dependency installation, GitHub and development tools have their own network behavior—this statement is about the integration's runtime, not every tool used to develop it.

Never put credentials, raw device identifiers, unredacted captures or private HA state in public issues, commits or AI prompts intended for public sharing. Review third-party logs manually before sharing. Address-derived hashes are not a guarantee of anonymity.

## Authorship, licensing and contributions

AI involvement does not remove the obligation to respect upstream licenses, preserve attribution or review generated output. The project's protocol implementation is independently expressed; restricted/unlicensed upstream source is research material, not code to copy into this MIT repository.

Contributors should disclose material AI assistance in their change description, explain what they verified, and identify assumptions or areas requiring human/hardware review. Avoid claiming “human reviewed,” “safe,” or “hardware verified” unless that specific verification actually occurred.
