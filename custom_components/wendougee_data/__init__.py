"""Read-only Wendougee DATA integration."""

import asyncio
import json
import logging
import os
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
    DOMAIN,
    PRIVATE_BASELINE_FILE,
    PRIVATE_BASELINE_MARKER,
    SERVICE_CAPTURE_BASELINE,
)
from .coordinator import WendougeeCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
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
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or not hasattr(entry, "runtime_data")
        ):
            raise HomeAssistantError("Wendougee DATA entry is not loaded")
        coordinator: WendougeeCoordinator = entry.runtime_data
        try:
            frames = await coordinator.async_read_baseline()
        except Exception:
            # Bluetooth backend errors can contain private discovery identifiers.
            raise HomeAssistantError(
                "Unable to complete the read-only baseline"
            ) from None
        return _private_baseline_response(frames)

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
    if DOMAIN in _config:
        hass.async_create_background_task(
            _async_import_when_discovered(hass),
            "import Wendougee DATA YAML configuration",
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Require a valid first sample before loading entities; let HA retry failures."""
    coordinator = WendougeeCoordinator(hass, entry)
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
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop polling only after platforms unload; preserve a failed unload's runtime."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        return True
    return False
