"""Independent, feedback-driven boiler enable switches."""

from homeassistant.components.switch import SwitchEntity

from ._protocol.controls import BoilerSetting
from .entity import WendougeeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("allow_boiler_control") is True:
        async_add_entities(
            [
                BoilerSwitch(entry, BoilerSetting.STEAM_ENABLED, "Steam boiler"),
                BoilerSwitch(entry, BoilerSetting.BREW_ENABLED, "Brew boiler"),
            ]
        )


class BoilerSwitch(WendougeeEntity, SwitchEntity):
    _attr_icon = "mdi:radiator"

    def __init__(self, entry, setting, name):
        super().__init__(entry, f"control_{setting.name.lower()}")
        self.setting = setting
        self._attr_name = name

    @property
    def is_on(self):
        configuration = self.coordinator.configuration
        if configuration is None:
            return None
        return (
            configuration.steam_heating_enabled
            if self.setting is BoilerSetting.STEAM_ENABLED
            else configuration.brew_heating_enabled
        )

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_boiler(self.setting, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_boiler(self.setting, False)
