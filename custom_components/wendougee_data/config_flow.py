"""Shared Bluetooth discovery with explicit read-only polling consent."""

from typing import Any

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import (
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    device_id,
)


def _supported(info: bluetooth.BluetoothServiceInfoBleak) -> bool:
    return info.connectable and info.name.startswith("WDG_Data_")


class WendougeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Do not connect or send any command during discovery/confirmation."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._choices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Filter advertisements and deduplicate without contacting the device."""
        if not _supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._address = discovery_info.address
        await self.async_set_unique_id(device_id(self._address))
        self._abort_if_unique_id_configured()
        if self.hass.data.get(DOMAIN, {}).get("yaml_import") is True:
            return self.async_create_entry(
                title="Wendougee DATA",
                data={
                    CONF_ADDRESS: self._address,
                    "poll_interval": DEFAULT_POLL_INTERVAL,
                },
            )
        self.context["title_placeholders"] = {"name": "Wendougee DATA"}
        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select only from HA's cached connectable discoveries; never scan here."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address not in self._choices:
                return self.async_abort(reason="no_devices_found")
            self._address = address
            await self.async_set_unique_id(device_id(address))
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()
        configured = self._async_current_ids()
        self._choices = {
            info.address: info.name
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if _supported(info) and device_id(info.address) not in configured
        }
        if not self._choices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._choices)}),
        )

    async def async_step_import(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import headless YAML only when exactly one supported machine is known."""
        matches = [
            info
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if _supported(info)
        ]
        if not matches:
            return self.async_abort(reason="no_devices_found")
        if len(matches) > 1:
            return self.async_abort(reason="multiple_devices_found")
        self._address = matches[0].address
        await self.async_set_unique_id(device_id(self._address))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Wendougee DATA",
            data={
                CONF_ADDRESS: self._address,
                "poll_interval": DEFAULT_POLL_INTERVAL,
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry only after the user explicitly consents to polling."""
        errors = {}
        if user_input is not None:
            if user_input.get("confirm") is True:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Wendougee DATA",
                    data={
                        CONF_ADDRESS: self._address,
                        "poll_interval": user_input["poll_interval"],
                    },
                )
            errors["base"] = "confirmation_required"
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                    vol.Required(
                        "poll_interval", default=DEFAULT_POLL_INTERVAL
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                    ),
                }
            ),
        )
