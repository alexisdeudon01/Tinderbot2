"""Camera platform for Tinder MCP — displays the current recommended profile photo."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TinderCoordinator
from .const import ATTR_COORDINATOR, DOMAIN, ENTITY_PROFILE_PHOTO, HTTP_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tinder profile photo camera."""
    coordinator: TinderCoordinator = hass.data[DOMAIN][entry.entry_id][ATTR_COORDINATOR]
    async_add_entities([TinderProfileCamera(coordinator, entry)])


class TinderProfileCamera(CoordinatorEntity[TinderCoordinator], Camera):
    """Camera entity that streams the current Tinder recommendation photo."""

    _attr_has_entity_name = True
    _attr_name = "Tinder Profile Photo"
    _attr_icon = "mdi:camera-account"

    def __init__(self, coordinator: TinderCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{entry.entry_id}_{ENTITY_PROFILE_PHOTO}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Tinder MCP",
            "manufacturer": "glassBead-tc",
            "model": "Tinder API MCP Server",
        }
        self._cached_image: bytes | None = None
        self._cached_url: str = ""

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None  # noqa: ARG002
    ) -> bytes | None:
        """Return current recommendation photo as JPEG bytes."""
        if self.coordinator.data is None:
            return None

        photo_url: str = self.coordinator.data.get("current_photo_url", "")

        if not photo_url:
            return None

        # Only re-download if the URL changed (i.e. new profile loaded)
        if photo_url == self._cached_url and self._cached_image:
            return self._cached_image

        session = async_get_clientsession(self.hass)
        try:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            async with session.get(photo_url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Impossible de charger la photo Tinder (HTTP %s)", resp.status
                    )
                    return self._cached_image
                image_bytes = await resp.read()
                self._cached_image = image_bytes
                self._cached_url = photo_url
                return image_bytes
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout lors du téléchargement de la photo Tinder")
        except aiohttp.ClientError as err:
            _LOGGER.warning("Erreur réseau photo Tinder: %s", err)

        return self._cached_image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw photo URL as an attribute."""
        if self.coordinator.data is None:
            return {}
        return {"photo_url": self.coordinator.data.get("current_photo_url", "")}
