"""Offline tests for the approval-gated baseline capture command."""

from __future__ import annotations

import argparse
import json
from unittest.mock import AsyncMock, patch

import pytest

from wendougee_data.crc import append_crc
from wendougee_data.evidence import bundle_from_dict
from wendougee_data.evidence_cli import capture_baseline
from wendougee_data.reads import ReadOperation

from .test_telemetry import TELEMETRY_RESPONSE


def baseline_frames():
    return {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.CONFIGURATION: append_crc(b"\x01\x03\x4a" + bytes(74)),
        ReadOperation.WATER_ALARM_ENABLED: append_crc(b"\x01\x03\x02\x00\x01"),
        ReadOperation.OPERATING_STATE: append_crc(b"\x01\x01\x03\x00\x00\x00"),
    }


def arguments(tmp_path):
    private_root = tmp_path / "research" / "artifacts" / "private"
    return argparse.Namespace(
        model="DATA S",
        firmware="unknown",
        official_app_version="unknown",
        notes="Supervised read-only baseline.",
        output=private_root / "evidence" / "baseline.json",
        private_root=private_root,
    )


def test_declining_confirmation_performs_no_bluetooth_or_file_io(tmp_path):
    args = arguments(tmp_path)
    with (
        patch("builtins.input", return_value="no"),
        patch(
            "wendougee_data.evidence_cli.read_live_baseline",
            new_callable=AsyncMock,
        ) as read,
        pytest.raises(SystemExit, match="cancelled"),
    ):
        capture_baseline(args)
    read.assert_not_awaited()
    assert not args.output.exists()


def test_approved_capture_writes_valid_private_bundle_without_device_identity(
    tmp_path,
):
    args = arguments(tmp_path)
    with (
        patch("builtins.input", return_value="READ ONLY"),
        patch(
            "wendougee_data.evidence_cli.read_live_baseline",
            new=AsyncMock(return_value=baseline_frames()),
        ),
    ):
        capture_baseline(args)

    document = json.loads(args.output.read_text())
    bundle = bundle_from_dict(document)
    assert len(bundle.records) == 4
    serialized = args.output.read_text()
    assert "WDG_Data_" not in serialized
    assert "bluetooth_address" not in serialized


def test_existing_destination_fails_before_confirmation_or_bluetooth(tmp_path):
    args = arguments(tmp_path)
    args.output.parent.mkdir(parents=True)
    args.output.write_text("existing")
    with (
        patch("builtins.input") as confirmation,
        patch(
            "wendougee_data.evidence_cli.read_live_baseline",
            new_callable=AsyncMock,
        ) as read,
        pytest.raises(FileExistsError),
    ):
        capture_baseline(args)
    confirmation.assert_not_called()
    read.assert_not_awaited()
