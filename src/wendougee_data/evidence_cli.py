"""Approval-gated private evidence capture and offline report commands."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from .evidence import (
    EvidenceSource,
    PrivacyStatus,
    bundle_from_dict,
    create_evidence_bundle,
    render_markdown_report,
    validate_private_destination,
    write_private_bundle,
)
from .live import read_live_baseline


def capture_baseline(arguments: argparse.Namespace) -> None:
    """Confirm, perform exactly four allowlisted reads, and save privately."""
    validate_private_destination(arguments.output, private_root=arguments.private_root)
    print(
        "This will connect to one WDG_Data_* device and send each of the four "
        "fixed read-only baseline requests exactly once. It sends no control, "
        "provisioning, reset, cleaning, boiler, profile, or brew command."
    )
    if input('Type "READ ONLY" to continue: ').strip() != "READ ONLY":
        raise SystemExit("capture cancelled before Bluetooth access")
    frames = asyncio.run(read_live_baseline())
    bundle = create_evidence_bundle(
        source=EvidenceSource.HARDWARE_CAPTURE,
        privacy_status=PrivacyStatus.PRIVATE_UNREVIEWED,
        captured_at=datetime.now(UTC),
        model=arguments.model,
        firmware=arguments.firmware,
        official_app_version=arguments.official_app_version,
        frames=frames,
        notes=arguments.notes,
    )
    write_private_bundle(bundle, arguments.output, private_root=arguments.private_root)
    print(f"Saved four private, unreviewed evidence records to {arguments.output}")


def validate_document(path: Path) -> None:
    """Validate an existing document offline and print a non-raw coverage report."""
    with path.open(encoding="utf-8") as source:
        bundle = bundle_from_dict(json.load(source))
    print(render_markdown_report(bundle))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture-baseline")
    capture.add_argument("--model", required=True)
    capture.add_argument("--firmware", required=True)
    capture.add_argument("--official-app-version", required=True)
    capture.add_argument(
        "--notes", default="Supervised read-only baseline; no physical comparison."
    )
    capture.add_argument(
        "--private-root",
        type=Path,
        default=Path("research/artifacts/private"),
    )
    capture.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("path", type=Path)
    return parser


def main() -> None:
    """Dispatch the selected evidence command."""
    arguments = _parser().parse_args()
    if arguments.command == "capture-baseline":
        capture_baseline(arguments)
    else:
        validate_document(arguments.path)


if __name__ == "__main__":
    main()
