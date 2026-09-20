"""Allowlisted diagnostics: no entries, addresses, names, hashes or raw frames."""

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Export known-safe fields, rather than redact an unrestricted entry dump."""
    coordinator = entry.runtime_data
    return {
        "schema_version": 1,
        "read_only": True,
        "last_update_success": coordinator.last_update_success,
        "last_error": coordinator.last_error,
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
        "telemetry": (
            asdict(coordinator.data)
            if coordinator.last_update_success and coordinator.data is not None
            else None
        ),
    }
