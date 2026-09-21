"""Read-only Wendougee DATA integration."""

import asyncio

import voluptuous as vol
from homeassistant.components import bluetooth as ha_bluetooth
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from ._protocol.reads import ReadOperation, build_read_request
from .const import DOMAIN, SERVICE_CAPTURE_BASELINE
from .coordinator import WendougeeCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({})}, extra=vol.ALLOW_EXTRA
)


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
    hass.data.setdefault(DOMAIN, {})["yaml_import"] = DOMAIN in _config

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
    try:
        await coordinator.async_config_entry_first_refresh()
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
