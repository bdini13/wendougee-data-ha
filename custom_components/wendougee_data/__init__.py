"""Read-only WENDOUGEE DATA S integration."""

import asyncio
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

import voluptuous as vol
from homeassistant.components import bluetooth as ha_bluetooth
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from ._protocol.reads import ReadOperation, build_read_request
from .const import (
    CONF_CAPTURE_BASELINE,
    DEVICE_DISPLAY_NAME,
    DOMAIN,
    PRIVATE_BASELINE_FILE,
    PRIVATE_BASELINE_MARKER,
    PRIVATE_TRACE_DIRECTORY,
    SERVICE_BENCHMARK_SAMPLING,
    SERVICE_CAPTURE_BASELINE,
    SERVICE_CAPTURE_TRACE,
)
from .coordinator import WendougeeCoordinator
from .fast_capture import RuntimeTrace, SamplingBenchmark

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {vol.Optional(CONF_CAPTURE_BASELINE, default=False): bool}
        )
    },
    extra=vol.ALLOW_EXTRA,
)
_LOGGER = logging.getLogger(__name__)


def _private_baseline_response(frames: dict[ReadOperation, bytes]) -> dict:
    """Format raw frames without discovery or config-entry identifiers."""
    return {
        "schema": "wendougee-data-private-baseline/v1",
        "privacy_status": "private_unreviewed",
        "records": [
            {
                "operation": operation.name.lower(),
                "request_hex": build_read_request(operation).hex(),
                "response_hex": frames[operation].hex(),
            }
            for operation in ReadOperation
        ],
    }


def _sampling_benchmark_response(result: SamplingBenchmark) -> dict:
    """Expose timing metrics only; never include a discovery identifier."""
    return {
        "schema": "wendougee-data-sampling-benchmark/v1",
        "read_only": True,
        "selected_hz": result.selected_hz,
        "stages": [asdict(stage) for stage in result.stages],
    }


def _private_trace_document(trace: RuntimeTrace) -> dict:
    """Format decoded samples and raw replies for private protocol analysis."""
    return {
        "schema": "wendougee-data-private-trace/v1",
        "privacy_status": "private_unreviewed",
        "read_only": True,
        "started_at_utc": trace.started_at_utc.isoformat(),
        "ended_at_utc": trace.ended_at_utc.isoformat(),
        "target_hz": trace.target_hz,
        "achieved_hz": trace.achieved_hz,
        "elapsed_seconds": trace.elapsed_seconds,
        "sample_count": len(trace.samples),
        "samples": [
            {
                "observed_at_utc": sample.observed_at_utc.isoformat(),
                "offset_seconds": sample.offset_seconds,
                "round_trip_ms": sample.round_trip_ms,
                "telemetry": asdict(sample.telemetry),
                "operating_state": {
                    **asdict(sample.operating_state),
                    "state": sample.operating_state.state,
                },
                "private_raw": {
                    "telemetry_response_hex": sample.telemetry_frame.hex(),
                    "operating_state_response_hex": (
                        sample.operating_state_frame.hex()
                    ),
                },
            }
            for sample in trace.samples
        ],
    }


def _claim_private_capture(config_dir: Path) -> bool:
    """Create an attempt marker atomically so restarts cannot repeat a read."""
    destination = config_dir / PRIVATE_BASELINE_FILE
    marker = config_dir / PRIVATE_BASELINE_MARKER
    if destination.exists() or marker.exists():
        return False
    descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    return True


def _write_private_capture(config_dir: Path, document: dict) -> None:
    """Write a new private response file with owner-only permissions."""
    destination = config_dir / PRIVATE_BASELINE_FILE
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(document, output, indent=2, sort_keys=True)
        output.write("\n")


def _write_private_trace(config_dir: Path, document: dict) -> str:
    """Create a unique owner-only trace file outside the integration source."""
    directory = config_dir / PRIVATE_TRACE_DIRECTORY
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    timestamp = document["started_at_utc"].replace("+00:00", "Z").replace(":", "")
    file_name = f"trace-{timestamp}.json"
    destination = directory / file_name
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(document, output, indent=2, sort_keys=True)
        output.write("\n")
    return file_name


def _loaded_coordinator(hass: HomeAssistant, config_entry_id: str):
    """Resolve only a loaded entry belonging to this integration."""
    entry = hass.config_entries.async_get_entry(config_entry_id)
    if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
        raise HomeAssistantError(f"{DEVICE_DISPLAY_NAME} entry is not loaded")
    return entry.runtime_data


async def _async_capture_private_baseline(
    hass: HomeAssistant, coordinator: WendougeeCoordinator
) -> None:
    """Write the YAML-approved, already completed baseline once."""
    config_dir = Path(hass.config.config_dir)
    try:
        frames = coordinator.take_cached_baseline_frames()
        if frames is None:
            raise RuntimeError("No completed baseline available")
        document = _private_baseline_response(frames)
        await hass.async_add_executor_job(_write_private_capture, config_dir, document)
    except Exception:
        # Never log backend text or raw frames; the marker deliberately prevents retry.
        _LOGGER.warning("Read-only private baseline attempt did not complete")


async def _async_import_when_discovered(hass: HomeAssistant) -> None:
    """Wait briefly for remote proxies to populate HA's Bluetooth cache."""
    for _attempt in range(150):
        matches = [
            info
            for info in ha_bluetooth.async_discovered_service_info(
                hass, connectable=True
            )
            if (info.name or "").startswith("WDG_Data_")
        ]
        if matches:
            await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
            return
        await asyncio.sleep(2)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register the explicit read-only baseline action once per HA process."""
    yaml_config = _config.get(DOMAIN)
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data["yaml_import"] = yaml_config is not None
    domain_data[CONF_CAPTURE_BASELINE] = bool(
        yaml_config and yaml_config.get(CONF_CAPTURE_BASELINE)
    )

    async def capture_baseline(call: ServiceCall) -> dict:
        coordinator: WendougeeCoordinator = _loaded_coordinator(
            hass, call.data["config_entry_id"]
        )
        try:
            frames = await coordinator.async_read_baseline()
        except Exception:
            # Bluetooth backend errors can contain private discovery identifiers.
            raise HomeAssistantError(
                "Unable to complete the read-only baseline"
            ) from None
        return _private_baseline_response(frames)

    async def benchmark_sampling(call: ServiceCall) -> dict:
        coordinator: WendougeeCoordinator = _loaded_coordinator(
            hass, call.data["config_entry_id"]
        )
        try:
            result = await coordinator.async_benchmark_sampling()
        except Exception:
            raise HomeAssistantError(
                "Unable to complete the read-only sampling benchmark"
            ) from None
        return _sampling_benchmark_response(result)

    async def capture_trace(call: ServiceCall) -> dict:
        coordinator: WendougeeCoordinator = _loaded_coordinator(
            hass, call.data["config_entry_id"]
        )
        try:
            trace = await coordinator.async_capture_runtime_trace(
                call.data["duration_seconds"]
            )
            document = _private_trace_document(trace)
            file_name = await hass.async_add_executor_job(
                _write_private_trace, Path(hass.config.config_dir), document
            )
        except Exception:
            raise HomeAssistantError(
                "Unable to complete the read-only trace capture"
            ) from None
        return {
            "schema": "wendougee-data-trace-summary/v1",
            "read_only": True,
            "file_name": file_name,
            "target_hz": trace.target_hz,
            "achieved_hz": trace.achieved_hz,
            "sample_count": len(trace.samples),
            "elapsed_seconds": trace.elapsed_seconds,
        }

    async def acknowledge_profile_uncertainty(call: ServiceCall) -> None:
        coordinator = _loaded_coordinator(hass, call.data["config_entry_id"])
        await coordinator.async_acknowledge_profile_uncertainty()

    hass.services.async_register(
        DOMAIN,
        "acknowledge_profile_uncertainty",
        acknowledge_profile_uncertainty,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): str,
                vol.Required("confirmation"): vol.Equal("MACHINE CHECKED"),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_BASELINE,
        capture_baseline,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): str,
                vol.Required("confirmation"): vol.Equal("READ ONLY"),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BENCHMARK_SAMPLING,
        benchmark_sampling,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): str,
                vol.Required("confirmation"): vol.Equal("READ ONLY"),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_TRACE,
        capture_trace,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): str,
                vol.Required("confirmation"): vol.Equal("READ ONLY"),
                vol.Optional("duration_seconds", default=90): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=180)
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    if DOMAIN in _config:
        hass.async_create_background_task(
            _async_import_when_discovered(hass),
            f"import {DEVICE_DISPLAY_NAME} YAML configuration",
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Require a valid first sample before loading entities; let HA retry failures."""
    if entry.title != DEVICE_DISPLAY_NAME:
        hass.config_entries.async_update_entry(entry, title=DEVICE_DISPLAY_NAME)
    coordinator = WendougeeCoordinator(hass, entry)
    await coordinator.activity.async_load()
    await coordinator.async_load_control_state()
    capture_claimed = False
    try:
        if entry.data.get(CONF_CAPTURE_BASELINE) is True:
            capture_claimed = await hass.async_add_executor_job(
                _claim_private_capture, Path(hass.config.config_dir)
            )
        await coordinator.async_config_entry_first_refresh()
        if capture_claimed:
            await _async_capture_private_baseline(hass, coordinator)
        else:
            coordinator.take_cached_baseline_frames()
        entry.runtime_data = coordinator
        entry.async_on_unload(entry.add_update_listener(_async_options_updated))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop polling only after platforms unload; preserve a failed unload's runtime."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        return True
    return False
