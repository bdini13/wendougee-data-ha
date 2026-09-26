"""Explicit start of the machine's selected stored mode-2 profile."""

from homeassistant.components.button import ButtonEntity

from .entity import WendougeeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("allow_profile_start") is True:
        async_add_entities([StoredProfileButton(entry)])
    if entry.options.get("allow_cleaning_control") is True:
        async_add_entities([CleaningButton(entry)])


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


class CleaningButton(WendougeeEntity, ButtonEntity):
    """Run the currently stored cleaning settings, never rewrite the program."""

    _attr_name = "Start cleaning"
    _attr_icon = "mdi:shimmer"

    def __init__(self, entry):
        super().__init__(entry, "start_cleaning")

    @property
    def extra_state_attributes(self):
        configuration = self.coordinator.configuration
        return {
            "start_locked": self.coordinator.cleaning_start_locked,
            "last_read_cleaning_seconds": configuration.cleaning_time_seconds
            if configuration
            else None,
            "last_read_standing_seconds": configuration.cleaning_rest_seconds
            if configuration
            else None,
            "last_read_cleaning_count": configuration.cleaning_repetitions
            if configuration
            else None,
        }

    async def async_press(self):
        await self.coordinator.async_start_cleaning()
