"""Serve a local read-only chart through HA's native image proxy."""

from datetime import UTC, datetime

from homeassistant.components.image import ImageEntity

from .entity import WendougeeEntity
from .shot_chart import render_chart


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ShotImage(hass, entry)])


class ShotImage(WendougeeEntity, ImageEntity):
    """No static public capture files and no extra device reads on image fetch."""

    _attr_name = "Latest captured shot"
    _attr_content_type = "image/svg+xml"

    def __init__(self, hass, entry):
        ImageEntity.__init__(self, hass)
        WendougeeEntity.__init__(self, entry, "latest_captured_shot")
        self._created = datetime.now(UTC)

    @property
    def available(self):
        return not self.coordinator.stopped

    @property
    def image_last_updated(self):
        at = self.coordinator.activity.journal.curve_updated_at
        return datetime.fromisoformat(at) if at else self._created

    async def async_image(self):
        return render_chart(self.coordinator.activity.journal.latest_curve)
