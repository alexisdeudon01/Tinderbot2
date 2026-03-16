"""Button platform for Tinder MCP — Like, Pass, Super Like, and Refresh."""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TinderApiClient, TinderAuthError, TinderConnectionError, TinderCoordinator
from .const import (
    ATTR_CLIENT,
    ATTR_COORDINATOR,
    DOMAIN,
    ENTITY_BUTTON_LIKE,
    ENTITY_BUTTON_PASS,
    ENTITY_BUTTON_REFRESH,
    ENTITY_BUTTON_SUPERLIKE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TinderButtonEntityDescription(ButtonEntityDescription):
    """Extend ButtonEntityDescription with a press handler factory."""

    press_fn: Callable[
        [TinderApiClient, TinderCoordinator, str],
        Coroutine[Any, Any, None],
    ] = field(default=lambda c, coord, uid: coord.async_request_refresh())


async def _press_like(
    client: TinderApiClient, coordinator: TinderCoordinator, user_id: str
) -> None:
    await client.async_like(user_id)
    await coordinator.async_request_refresh()


async def _press_pass(
    client: TinderApiClient, coordinator: TinderCoordinator, user_id: str
) -> None:
    await client.async_pass(user_id)
    await coordinator.async_request_refresh()


async def _press_superlike(
    client: TinderApiClient, coordinator: TinderCoordinator, user_id: str
) -> None:
    await client.async_superlike(user_id)
    await coordinator.async_request_refresh()


async def _press_refresh(
    client: TinderApiClient,  # noqa: ARG001
    coordinator: TinderCoordinator,
    user_id: str,  # noqa: ARG001
) -> None:
    await coordinator.async_request_refresh()


BUTTON_DESCRIPTIONS: tuple[TinderButtonEntityDescription, ...] = (
    TinderButtonEntityDescription(
        key=ENTITY_BUTTON_LIKE,
        name="Tinder Like",
        icon="mdi:heart",
        press_fn=_press_like,
    ),
    TinderButtonEntityDescription(
        key=ENTITY_BUTTON_PASS,
        name="Tinder Pass",
        icon="mdi:close-circle",
        press_fn=_press_pass,
    ),
    TinderButtonEntityDescription(
        key=ENTITY_BUTTON_SUPERLIKE,
        name="Tinder Super Like",
        icon="mdi:star",
        press_fn=_press_superlike,
    ),
    TinderButtonEntityDescription(
        key=ENTITY_BUTTON_REFRESH,
        name="Tinder Refresh",
        icon="mdi:refresh",
        press_fn=_press_refresh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tinder MCP buttons from a config entry."""
    coordinator: TinderCoordinator = hass.data[DOMAIN][entry.entry_id][ATTR_COORDINATOR]
    client: TinderApiClient = hass.data[DOMAIN][entry.entry_id][ATTR_CLIENT]
    async_add_entities(
        TinderButton(coordinator, client, entry, description)
        for description in BUTTON_DESCRIPTIONS
    )


class TinderButton(CoordinatorEntity[TinderCoordinator], ButtonEntity):
    """A Tinder action button backed by the DataUpdateCoordinator."""

    entity_description: TinderButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TinderCoordinator,
        client: TinderApiClient,
        entry: ConfigEntry,
        description: TinderButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Tinder MCP",
            "manufacturer": "glassBead-tc",
            "model": "Tinder API MCP Server",
        }

    async def async_press(self) -> None:
        """Execute button action with full error handling."""
        current_user_id: str = ""
        if self.coordinator.data:
            current_user_id = self.coordinator.data.get("current_user_id", "")

        if not current_user_id and self.entity_description.key != ENTITY_BUTTON_REFRESH:
            _LOGGER.warning(
                "%s: aucun profil courant disponible, action ignorée",
                self.entity_description.name,
            )
            return

        try:
            await self.entity_description.press_fn(
                self._client, self.coordinator, current_user_id
            )
        except TinderAuthError:
            _LOGGER.error(
                "%s: token Tinder expiré (401) — reconfigurez l'intégration",
                self.entity_description.name,
            )
        except TinderConnectionError as err:
            _LOGGER.error(
                "%s: serveur MCP inaccessible — %s",
                self.entity_description.name,
                err,
            )
