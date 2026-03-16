"""Tinder MCP integration for Home Assistant.

Communicates with a local glassbead/tinder-mcp-server add-on via HTTP.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CLIENT,
    ATTR_COORDINATOR,
    ATTR_DIRECTION,
    ATTR_TARGET_USER_ID,
    CONF_MCP_URL,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DOMAIN,
    ENDPOINT_LIKE,
    ENDPOINT_MATCHES,
    ENDPOINT_PASS,
    ENDPOINT_RECOMMENDATIONS,
    ENDPOINT_SUPERLIKE,
    HTTP_TIMEOUT,
    SERVICE_SWIPE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "camera", "button"]


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class TinderAuthError(Exception):
    """Raised when the Tinder session token is expired or invalid (HTTP 401)."""


class TinderConnectionError(Exception):
    """Raised when the MCP server is unreachable (timeout / network error)."""


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class TinderApiClient:
    """Thin async wrapper around the glassbead tinder-mcp-server HTTP API."""

    def __init__(self, hass: HomeAssistant, mcp_url: str, user_id: str) -> None:
        self._hass = hass
        self._base = mcp_url.rstrip("/")
        self._user_id = user_id
        self._timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and return the parsed JSON body."""
        session = async_get_clientsession(self._hass)
        url = f"{self._base}{path}"
        try:
            async with session.request(
                method,
                url,
                json=json,
                # glassbead routes expect x-auth-user-id (not x-user-id)
                headers={"x-auth-user-id": self._user_id},
                timeout=self._timeout,
            ) as resp:
                if resp.status == 401:
                    raise TinderAuthError(f"401 from {url}")
                if resp.status >= 400:
                    text = await resp.text()
                    raise TinderConnectionError(
                        f"HTTP {resp.status} from {url}: {text[:200]}"
                    )
                return await resp.json()
        except asyncio.TimeoutError as err:
            raise TinderConnectionError(f"Timeout calling {url}") from err
        except aiohttp.ClientError as err:
            raise TinderConnectionError(f"Connection error: {err}") from err

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def async_get_recommendations(self) -> list[dict[str, Any]]:
        """GET /mcp/user/recommendations — return list of recommended profiles."""
        data = await self._request("GET", ENDPOINT_RECOMMENDATIONS)
        return _extract_recs(data)

    async def async_get_matches(self) -> list[dict[str, Any]]:
        """GET /mcp/user/matches — return list of current matches."""
        data = await self._request("GET", ENDPOINT_MATCHES)
        return _extract_matches(data)

    async def async_like(self, target_user_id: str) -> dict[str, Any]:
        """POST /mcp/interaction/like/{user_id}."""
        path = ENDPOINT_LIKE.format(user_id=target_user_id)
        return await self._request("POST", path)

    async def async_pass(self, target_user_id: str) -> dict[str, Any]:
        """POST /mcp/interaction/pass/{user_id}."""
        path = ENDPOINT_PASS.format(user_id=target_user_id)
        return await self._request("POST", path)

    async def async_superlike(self, target_user_id: str) -> dict[str, Any]:
        """POST /mcp/interaction/superlike/{user_id}."""
        path = ENDPOINT_SUPERLIKE.format(user_id=target_user_id)
        return await self._request("POST", path)


# ---------------------------------------------------------------------------
# DataUpdateCoordinator
# ---------------------------------------------------------------------------

class TinderCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Tinder data every 30 seconds and distribute to all entities."""

    def __init__(self, hass: HomeAssistant, client: TinderApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Pull fresh data from the MCP server."""
        try:
            recs = await self.client.async_get_recommendations()
            matches = await self.client.async_get_matches()
        except TinderAuthError as err:
            raise UpdateFailed(
                f"Session Tinder expirée (401). Reconfigurez l'intégration: {err}"
            ) from err
        except TinderConnectionError as err:
            raise UpdateFailed(
                f"Serveur MCP inaccessible: {err}"
            ) from err

        current: dict[str, Any] = recs[0] if recs else {}
        person: dict[str, Any] = current.get("user", {})

        return {
            "recommendations": recs,
            "matches": matches,
            "match_count": len(matches),
            "current_user_id": person.get("_id", ""),
            "current_name": person.get("name", "—"),
            "current_age": _compute_age(person.get("birth_date")),
            "current_bio": person.get("bio", ""),
            "current_photo_url": _extract_photo_url(current),
        }


# ---------------------------------------------------------------------------
# HA setup / teardown
# ---------------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tinder MCP from a config entry."""
    mcp_url: str = entry.data[CONF_MCP_URL]
    user_id: str = entry.data[CONF_USER_ID]

    client = TinderApiClient(hass, mcp_url, user_id)
    coordinator = TinderCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Impossible de charger les données Tinder: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ATTR_CLIENT: client,
        ATTR_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # -----------------------------------------------------------------------
    # Service: tinder_mcp.swipe
    # -----------------------------------------------------------------------

    async def _handle_swipe(call: ServiceCall) -> None:
        direction: str = call.data[ATTR_DIRECTION]
        target_id: str | None = call.data.get(ATTR_TARGET_USER_ID)

        entry_id = next(iter(hass.data[DOMAIN].keys()))
        c: TinderApiClient = hass.data[DOMAIN][entry_id][ATTR_CLIENT]
        coord: TinderCoordinator = hass.data[DOMAIN][entry_id][ATTR_COORDINATOR]

        if not target_id:
            target_id = coord.data.get("current_user_id", "")

        if not target_id:
            _LOGGER.warning("tinder_mcp.swipe: aucun profil courant disponible")
            return

        try:
            if direction == DIRECTION_RIGHT:
                await c.async_like(target_id)
                _LOGGER.info("Liked user %s", target_id)
            else:
                await c.async_pass(target_id)
                _LOGGER.info("Passed user %s", target_id)
        except TinderAuthError:
            _LOGGER.error("tinder_mcp.swipe: token expiré (401)")
        except TinderConnectionError as err:
            _LOGGER.error("tinder_mcp.swipe: erreur réseau — %s", err)

        await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SWIPE,
        _handle_swipe,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DIRECTION): vol.In([DIRECTION_RIGHT, DIRECTION_LEFT]),
                vol.Optional(ATTR_TARGET_USER_ID): str,
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_age(birth_date: str | None) -> int | None:
    """Compute age from ISO birth_date string (e.g. '1995-06-15T00:00:00.000Z')."""
    if not birth_date:
        return None
    try:
        from datetime import date
        year = int(birth_date[:4])
        month = int(birth_date[5:7])
        day = int(birth_date[8:10])
        today = date.today()
        age = today.year - year - ((today.month, today.day) < (month, day))
        return age
    except (ValueError, IndexError):
        return None


def _extract_photo_url(recommendation: dict[str, Any]) -> str:
    """Extract the first photo URL from a recommendation object."""
    try:
        photos: list[dict] = recommendation.get("user", {}).get("photos", [])
        if photos:
            return photos[0].get("url", "")
    except (KeyError, IndexError, TypeError):
        pass
    return ""


def _extract_recs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle multiple response shapes for recommendations."""
    try:
        # MCP shape: { success: true, data: <tinder_response> }
        data = payload.get("data", payload)
        # Tinder response may be { data: { results: [...] } } or { results: [...] }
        if isinstance(data, dict):
            if isinstance(data.get("results"), list):
                return data["results"]
            inner = data.get("data")
            if isinstance(inner, dict) and isinstance(inner.get("results"), list):
                return inner["results"]
    except Exception:  # noqa: BLE001
        return []
    return []


def _extract_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle multiple response shapes for matches."""
    try:
        data = payload.get("data", payload)
        if isinstance(data, dict):
            if isinstance(data.get("matches"), list):
                return data["matches"]
            inner = data.get("data")
            if isinstance(inner, dict) and isinstance(inner.get("matches"), list):
                return inner["matches"]
    except Exception:  # noqa: BLE001
        return []
    return []
