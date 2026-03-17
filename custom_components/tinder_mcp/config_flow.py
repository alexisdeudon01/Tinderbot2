"""Config flow for Tinder MCP integration — direct X-Auth-Token authentication."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AUTH_TOKEN,
    DOMAIN,
    ENDPOINT_RECOMMENDATIONS,
    HTTP_TIMEOUT,
    TINDER_API_BASE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_TOKEN): str,
    }
)


async def _validate_token(hass: HomeAssistant, auth_token: str) -> str | None:
    """Validate X-Auth-Token by fetching recommendations (200 expected)."""
    session = async_get_clientsession(hass)
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with session.get(
            f"{TINDER_API_BASE}{ENDPOINT_RECOMMENDATIONS}",
            headers={
                "X-Auth-Token": auth_token,
                "Content-Type": "application/json",
                "User-Agent": "Tinder/11.4.0 (iPhone; iOS 12.4.1; Scale/2.00)",
            },
            timeout=timeout,
        ) as resp:
            if resp.status == 401:
                return "invalid_auth"
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.warning("Token validation HTTP %s: %s", resp.status, body[:500])
                return "cannot_connect"
            return None
    except asyncio.TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"


class TinderMcpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Tinder MCP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Enter Tinder X-Auth-Token."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            auth_token = user_input[CONF_AUTH_TOKEN].strip()

            error = await _validate_token(self.hass, auth_token)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Tinder MCP",
                    data={CONF_AUTH_TOKEN: auth_token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={},
        )
