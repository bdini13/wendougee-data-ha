"""Versioned, privacy-conscious evidence records for read-only validation.

The envelope preserves enough information to replay and audit a read while
keeping device discovery metadata out of the document. Hardware captures are
private and unreviewed by default; nothing here makes a fixture safe to publish.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .reads import ReadOperation, build_read_request, validate_read_response
from .state import (
    decode_configuration,
    decode_operating_state,
    decode_water_alarm_enabled,
)
from .telemetry import parse_telemetry_response

SCHEMA = "wendougee-data-evidence/v1"
_CAPABILITY_PATTERN = re.compile(r"^[A-Z][0-9]{2}$")
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}"),
    re.compile(r"(?i)\bWDG_Data_[^\s]+"),
    re.compile(
        r"(?i)\b(?:serial(?:_number)?|access[_ -]?token|password|secret)\s*[:=]"
    ),
)


class EvidenceSource(Enum):
    """How the response bytes were obtained."""

    SYNTHETIC = "synthetic"
    HARDWARE_CAPTURE = "hardware_capture"


class PrivacyStatus(Enum):
    """Whether the evidence has received a deliberate publication review."""

    PRIVATE_UNREVIEWED = "private_unreviewed"
    PUBLIC_SANITIZED = "public_sanitized"


@dataclass(frozen=True)
class EvidenceRecord:
    """One validated allowlisted request and its complete response."""

    operation: ReadOperation
    capability_ids: tuple[str, ...]
    request: bytes
    response: bytes
    decoded: dict[str, bool | float | int | str | None]
    units: dict[str, str]
    known_limitations: tuple[str, ...]
    physical_comparison: str = "not_performed"


@dataclass(frozen=True)
class EvidenceBundle:
    """Provenance and one or more replayable evidence records."""

    source: EvidenceSource
    privacy_status: PrivacyStatus
    captured_at: datetime
    model: str
    firmware: str
    official_app_version: str
    records: tuple[EvidenceRecord, ...]
    notes: str
    privacy_reviewed_at: datetime | None = None
    privacy_reviewer: str | None = None


_CAPABILITIES = {
    ReadOperation.TELEMETRY: (
        "T02",
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "S06",
        "S07",
        "S08",
        "S09",
        "S10",
    ),
    ReadOperation.CONFIGURATION: ("T03", "B01", "B02", "B03", "B04", "B05"),
    ReadOperation.WATER_ALARM_ENABLED: ("B06",),
    ReadOperation.OPERATING_STATE: ("T04", "S11"),
}

_LIMITATIONS = {
    ReadOperation.TELEMETRY: (
        "CRC and decoding do not independently validate units or physical meaning.",
        "Flow, scale, elapsed-time, and pump-time semantics require comparison.",
    ),
    ReadOperation.CONFIGURATION: (
        "Unknown registers are retained only in the private response frame.",
        "Upstream ranges are not manufacturer-validated safety limits.",
    ),
    ReadOperation.WATER_ALARM_ENABLED: (
        "This setting is distinct from the current water-shortage alarm state.",
    ),
    ReadOperation.OPERATING_STATE: (
        "Bit meanings are provisional and conflicting flags remain ambiguous.",
    ),
}


def _check_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError(f"{field} must be a non-empty bounded string")
    if any(pattern.search(value) for pattern in _SENSITIVE_TEXT_PATTERNS):
        raise ValueError(f"{field} contains likely sensitive data")


def _require_timestamp(value: datetime, field: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must include a timezone")
    return value.astimezone(UTC)


def _decoded_values(
    operation: ReadOperation, frame: bytes
) -> tuple[dict[str, bool | float | int | str | None], dict[str, str]]:
    if operation is ReadOperation.TELEMETRY:
        telemetry = parse_telemetry_response(frame)
        values = {
            "elapsed_brew_time_seconds": telemetry.elapsed_brew_time_seconds,
            "water_level_alarm": telemetry.water_level_alarm,
            "steam_temperature_celsius": (telemetry.steam_boiler_temperature_celsius),
            "brew_temperature_celsius": telemetry.brew_boiler_temperature_celsius,
            "pressure_bar": telemetry.pressure_bar,
            "pumped_volume_ml": telemetry.dispensed_volume_ml,
            "scale_weight_grams": telemetry.scale_weight_grams,
            "pump_active_time_seconds": telemetry.pump_active_time_seconds,
            "flow_ml_per_second": telemetry.instantaneous_flow_ml_per_second,
            "weight_rate_grams_per_second": (telemetry.weight_rate_grams_per_second),
        }
        return values, {
            "elapsed_brew_time_seconds": "s",
            "steam_temperature_celsius": "°C",
            "brew_temperature_celsius": "°C",
            "pressure_bar": "bar",
            "pumped_volume_ml": "mL",
            "scale_weight_grams": "g",
            "pump_active_time_seconds": "s",
            "flow_ml_per_second": "mL/s",
            "weight_rate_grams_per_second": "g/s",
        }
    if operation is ReadOperation.CONFIGURATION:
        configuration = decode_configuration(frame)
        values = asdict(configuration)
        del values["raw_registers"]
        return values, {
            "cleaning_time_seconds": "s",
            "cleaning_rest_seconds": "s",
            "steam_target_celsius": "°C",
            "brew_target_celsius": "°C",
            "manual_time_seconds": "s",
            "manual_pressure_bar": "bar",
        }
    if operation is ReadOperation.WATER_ALARM_ENABLED:
        return {"water_alarm_enabled": decode_water_alarm_enabled(frame)}, {}
    state = decode_operating_state(frame)
    return {
        "state": state.state,
        "profile_active": state.profile_active,
        "manual_active": state.manual_active,
        "cleaning_active": state.cleaning_active,
        "free_variable_active": state.free_variable_active,
        "unknown_bits": state.unknown_bits,
    }, {}


def create_evidence_record(operation: ReadOperation, frame: bytes) -> EvidenceRecord:
    """Validate a response and derive all claims from its bytes."""
    validate_read_response(frame, operation)
    decoded, units = _decoded_values(operation, frame)
    capabilities = _CAPABILITIES[operation]
    if not all(_CAPABILITY_PATTERN.fullmatch(item) for item in capabilities):
        raise ValueError("invalid capability identifier")
    return EvidenceRecord(
        operation=operation,
        capability_ids=capabilities,
        request=build_read_request(operation),
        response=bytes(frame),
        decoded=decoded,
        units=units,
        known_limitations=_LIMITATIONS[operation],
    )


def create_evidence_bundle(
    *,
    source: EvidenceSource,
    privacy_status: PrivacyStatus,
    captured_at: datetime,
    model: str,
    firmware: str,
    official_app_version: str,
    frames: dict[ReadOperation, bytes],
    notes: str,
    privacy_reviewed_at: datetime | None = None,
    privacy_reviewer: str | None = None,
) -> EvidenceBundle:
    """Create a validated bundle without discovery names or Bluetooth addresses."""
    if not isinstance(source, EvidenceSource) or not isinstance(
        privacy_status, PrivacyStatus
    ):
        raise ValueError("source and privacy status must use their enums")
    timestamp = _require_timestamp(captured_at, "captured_at")
    for field, value in (
        ("model", model),
        ("firmware", firmware),
        ("official_app_version", official_app_version),
        ("notes", notes),
    ):
        _check_text(value, field)
    if not isinstance(frames, dict) or not frames:
        raise ValueError("at least one evidence record is required")
    if any(not isinstance(operation, ReadOperation) for operation in frames):
        raise ValueError("all operations must be allowlisted")
    reviewed_at = None
    if privacy_status is PrivacyStatus.PUBLIC_SANITIZED:
        if privacy_reviewed_at is None or privacy_reviewer is None:
            raise ValueError("public evidence requires privacy review metadata")
        reviewed_at = _require_timestamp(privacy_reviewed_at, "privacy_reviewed_at")
        _check_text(privacy_reviewer, "privacy_reviewer")
    elif privacy_reviewed_at is not None or privacy_reviewer is not None:
        raise ValueError("private evidence must not claim completed privacy review")
    return EvidenceBundle(
        source=source,
        privacy_status=privacy_status,
        captured_at=timestamp,
        model=model,
        firmware=firmware,
        official_app_version=official_app_version,
        records=tuple(
            create_evidence_record(operation, frames[operation])
            for operation in ReadOperation
            if operation in frames
        ),
        notes=notes,
        privacy_reviewed_at=reviewed_at,
        privacy_reviewer=privacy_reviewer,
    )


def _format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def bundle_to_dict(bundle: EvidenceBundle) -> dict[str, Any]:
    """Return a deterministic JSON-compatible representation."""
    return {
        "schema": SCHEMA,
        "source": bundle.source.value,
        "privacy_status": bundle.privacy_status.value,
        "captured_at": _format_timestamp(bundle.captured_at),
        "model": bundle.model,
        "firmware": bundle.firmware,
        "official_app_version": bundle.official_app_version,
        "notes": bundle.notes,
        "privacy_reviewed_at": _format_timestamp(bundle.privacy_reviewed_at),
        "privacy_reviewer": bundle.privacy_reviewer,
        "records": [
            {
                "operation": record.operation.name.lower(),
                "capability_ids": list(record.capability_ids),
                "request_hex": record.request.hex(),
                "response_hex": record.response.hex(),
                "decoded": record.decoded,
                "units": record.units,
                "known_limitations": list(record.known_limitations),
                "physical_comparison": record.physical_comparison,
            }
            for record in bundle.records
        ],
    }


def _parse_timestamp(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an RFC 3339 string") from error
    return _require_timestamp(parsed, field)


def bundle_from_dict(document: dict[str, Any]) -> EvidenceBundle:
    """Strictly validate a parsed evidence document and all derived claims."""
    expected_keys = {
        "schema",
        "source",
        "privacy_status",
        "captured_at",
        "model",
        "firmware",
        "official_app_version",
        "notes",
        "privacy_reviewed_at",
        "privacy_reviewer",
        "records",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise ValueError("unexpected evidence document fields")
    if document["schema"] != SCHEMA:
        raise ValueError("unsupported evidence schema")
    if not isinstance(document["records"], list):
        raise ValueError("records must be a list")
    frames: dict[ReadOperation, bytes] = {}
    supplied_records: dict[ReadOperation, dict[str, Any]] = {}
    record_keys = {
        "operation",
        "capability_ids",
        "request_hex",
        "response_hex",
        "decoded",
        "units",
        "known_limitations",
        "physical_comparison",
    }
    for supplied in document["records"]:
        if not isinstance(supplied, dict) or set(supplied) != record_keys:
            raise ValueError("unexpected evidence record fields")
        try:
            operation = ReadOperation[supplied["operation"].upper()]
            response = bytes.fromhex(supplied["response_hex"])
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid operation or response hex") from error
        if operation in frames:
            raise ValueError("duplicate evidence operation")
        frames[operation] = response
        supplied_records[operation] = supplied
    captured_at = _parse_timestamp(document["captured_at"], "captured_at")
    if captured_at is None:
        raise ValueError("captured_at is required")
    bundle = create_evidence_bundle(
        source=EvidenceSource(document["source"]),
        privacy_status=PrivacyStatus(document["privacy_status"]),
        captured_at=captured_at,
        model=document["model"],
        firmware=document["firmware"],
        official_app_version=document["official_app_version"],
        frames=frames,
        notes=document["notes"],
        privacy_reviewed_at=_parse_timestamp(
            document["privacy_reviewed_at"], "privacy_reviewed_at"
        ),
        privacy_reviewer=document["privacy_reviewer"],
    )
    for record in bundle.records:
        supplied = supplied_records[record.operation]
        if supplied["request_hex"] != record.request.hex():
            raise ValueError("request does not match allowlisted operation")
        if supplied["decoded"] != record.decoded:
            raise ValueError("decoded claims do not match response")
        if supplied["units"] != record.units:
            raise ValueError("units do not match the schema")
        if supplied["capability_ids"] != list(record.capability_ids):
            raise ValueError("capability identifiers do not match the operation")
        if supplied["known_limitations"] != list(record.known_limitations):
            raise ValueError("known limitations do not match the schema")
        if supplied["physical_comparison"] != record.physical_comparison:
            raise ValueError("unsupported physical comparison claim")
    return bundle


def validate_private_destination(destination: Path, *, private_root: Path) -> Path:
    """Resolve a new destination beneath the private root without touching it."""
    root = private_root.resolve()
    target = destination.resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError("destination must remain under the private root") from error
    if target.exists():
        raise FileExistsError(target)
    return target


def write_private_bundle(
    bundle: EvidenceBundle, destination: Path, *, private_root: Path
) -> None:
    """Write a new unreviewed document only beneath an explicit private root."""
    if bundle.privacy_status is not PrivacyStatus.PRIVATE_UNREVIEWED:
        raise ValueError("private writer requires private_unreviewed evidence")
    target = validate_private_destination(destination, private_root=private_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        json.dump(bundle_to_dict(bundle), output, indent=2, sort_keys=True)
        output.write("\n")


def render_markdown_report(bundle: EvidenceBundle) -> str:
    """Summarize coverage without treating transport validity as physical proof."""
    present = {record.operation: record for record in bundle.records}
    lines = [
        f"# {bundle.model} evidence report",
        "",
        f"- Source: `{bundle.source.value}`",
        f"- Privacy: `{bundle.privacy_status.value}`",
        f"- Captured: `{_format_timestamp(bundle.captured_at)}`",
        f"- Firmware: `{bundle.firmware}`",
        f"- Official app: `{bundle.official_app_version}`",
        "- Physical comparison: Not performed",
        "",
        "| Operation | Coverage | Capability IDs |",
        "| --- | --- | --- |",
    ]
    for operation in ReadOperation:
        record = present.get(operation)
        label = operation.name.replace("_", " ").title()
        status = "Present" if record else "Missing"
        capabilities = ", ".join(record.capability_ids) if record else "—"
        lines.append(f"| {label} | {status} | {capabilities} |")
    lines.extend(
        [
            "",
            "> Valid framing and CRC prove transport integrity only. Units, field",
            "> semantics, calibration, and physical behavior require attended",
            "> comparison.",
            "",
        ]
    )
    return "\n".join(lines)
