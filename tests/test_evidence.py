"""Evidence-envelope tests; all frames here are synthetic."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wendougee_data.evidence import (
    EvidenceSource,
    PrivacyStatus,
    bundle_from_dict,
    bundle_to_dict,
    create_evidence_bundle,
    render_markdown_report,
    write_private_bundle,
)
from wendougee_data.reads import ReadOperation

from .test_telemetry import TELEMETRY_RESPONSE

CAPTURED_AT = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)


def synthetic_bundle():
    return create_evidence_bundle(
        source=EvidenceSource.SYNTHETIC,
        privacy_status=PrivacyStatus.PRIVATE_UNREVIEWED,
        captured_at=CAPTURED_AT,
        model="DATA S",
        firmware="unknown",
        official_app_version="unknown",
        frames={ReadOperation.TELEMETRY: TELEMETRY_RESPONSE},
        notes="Offline test fixture; no machine contact.",
    )


def test_versioned_bundle_round_trips_and_recomputes_decoded_values():
    bundle = synthetic_bundle()
    document = bundle_to_dict(bundle)

    assert document["schema"] == "wendougee-data-evidence/v1"
    assert document["source"] == "synthetic"
    assert document["privacy_status"] == "private_unreviewed"
    assert document["captured_at"] == "2026-09-20T20:00:00Z"
    assert document["records"][0]["operation"] == "telemetry"
    assert document["records"][0]["request_hex"] == "0103057c00160510"
    assert document["records"][0]["decoded"]["brew_temperature_celsius"] == 93.6
    assert document["records"][0]["units"]["brew_temperature_celsius"] == "°C"
    assert bundle_from_dict(document) == bundle


def test_rejects_modified_request_response_or_decoded_claim():
    for field, value in [
        ("request_hex", "01050096ff006c16"),
        ("response_hex", TELEMETRY_RESPONSE[:-1].hex() + "00"),
    ]:
        document = bundle_to_dict(synthetic_bundle())
        document["records"][0][field] = value
        with pytest.raises(ValueError):
            bundle_from_dict(document)

    document = bundle_to_dict(synthetic_bundle())
    document["records"][0]["decoded"]["brew_temperature_celsius"] = 100.0
    with pytest.raises(ValueError, match="decoded"):
        bundle_from_dict(document)


@pytest.mark.parametrize(
    "unsafe",
    [
        "Machine AA:BB:CC:DD:EE:FF",
        "Device WDG_Data_private-name",
        "serial_number=secret-machine-id",
        "access_token=do-not-store-this",
    ],
)
def test_rejects_likely_identifiers_and_credentials_in_text(unsafe):
    with pytest.raises(ValueError, match="sensitive"):
        create_evidence_bundle(
            source=EvidenceSource.SYNTHETIC,
            privacy_status=PrivacyStatus.PRIVATE_UNREVIEWED,
            captured_at=CAPTURED_AT,
            model="DATA S",
            firmware="unknown",
            official_app_version="unknown",
            frames={ReadOperation.TELEMETRY: TELEMETRY_RESPONSE},
            notes=unsafe,
        )


def test_public_status_requires_explicit_review_metadata():
    with pytest.raises(ValueError, match="privacy review"):
        create_evidence_bundle(
            source=EvidenceSource.SYNTHETIC,
            privacy_status=PrivacyStatus.PUBLIC_SANITIZED,
            captured_at=CAPTURED_AT,
            model="DATA S",
            firmware="unknown",
            official_app_version="unknown",
            frames={ReadOperation.TELEMETRY: TELEMETRY_RESPONSE},
            notes="Synthetic public fixture.",
        )


def test_report_marks_missing_operations_and_no_physical_comparison():
    report = render_markdown_report(synthetic_bundle())
    assert "DATA S evidence report" in report
    assert "Telemetry | Present" in report
    assert "Configuration | Missing" in report
    assert "Physical comparison: Not performed" in report
    assert "synthetic" in report


def test_private_writer_stays_under_private_root_and_will_not_overwrite(tmp_path):
    private_root = tmp_path / "private"
    destination = private_root / "evidence" / "baseline.json"
    write_private_bundle(synthetic_bundle(), destination, private_root=private_root)
    assert bundle_from_dict(__import__("json").loads(destination.read_text()))

    with pytest.raises(FileExistsError):
        write_private_bundle(synthetic_bundle(), destination, private_root=private_root)
    with pytest.raises(ValueError, match="private root"):
        write_private_bundle(
            synthetic_bundle(), tmp_path / "public.json", private_root=private_root
        )
