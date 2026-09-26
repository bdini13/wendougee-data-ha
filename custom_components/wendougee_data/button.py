"""Explicit start of the machine's selected stored mode-2 profile."""

from homeassistant.components.button import ButtonEntity

from .entity import WendougeeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("allow_profile_start") is True:
        async_add_entities([StoredProfileButton(entry)])


class StoredProfileButton(WendougeeEntity, ButtonEntity):
    _attr_name = "Start stored profile"
    _attr_icon = "mdi:coffee-maker"

    def __init__(self, entry):
        super().__init__(entry, "start_stored_profile")

    @property
    def extra_state_attributes(self):
        return {"start_locked": self.coordinator.profile_start_locked}

    async def async_press(self):
        await self.coordinator.async_start_profile()
