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
    configuration = (
        asdict(coordinator.configuration)
        if coordinator.configuration is not None
        else None
    )
    if configuration is not None:
        configuration.pop("raw_registers")
    operating_state = coordinator.operating_state
    return {
        "schema_version": 3,
        "read_only": True,
        "last_update_success": coordinator.last_update_success,
        "last_error": coordinator.last_error,
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
        "poll_health": {
            "successful_polls_since_load": coordinator.successful_polls_since_load,
            "failed_polls_since_load": coordinator.failed_polls_since_load,
            "consecutive_failed_polls": coordinator.consecutive_failed_polls,
            "last_successful_poll_utc": (
                coordinator.last_successful_poll_utc.isoformat()
                if coordinator.last_successful_poll_utc is not None
                else None
            ),
            "last_failed_poll_utc": (
                coordinator.last_failed_poll_utc.isoformat()
                if coordinator.last_failed_poll_utc is not None
                else None
            ),
        },
        "telemetry": (
            asdict(coordinator.data)
            if coordinator.last_update_success and coordinator.data is not None
            else None
        ),
        "configuration": configuration,
        "water_alarm_enabled": coordinator.water_alarm_enabled,
        "operating_state": (
            {
                "state": operating_state.state,
                "profile_active": operating_state.profile_active,
                "manual_active": operating_state.manual_active,
                "cleaning_active": operating_state.cleaning_active,
                "free_variable_active": operating_state.free_variable_active,
                "unknown_bits": operating_state.unknown_bits,
            }
            if operating_state is not None
            else None
        ),
    }
