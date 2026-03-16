"""Config flow for Tinder MCP integration — SMS authentication (2 steps)."""
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
    CONF_MCP_URL,
    CONF_PHONE_NUMBER,
    CONF_USER_ID,
    DEFAULT_MCP_URL,
    DOMAIN,
    ENDPOINT_INFO,
    ENDPOINT_TOOLS,
    HTTP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MCP_URL, default=DEFAULT_MCP_URL): str,
        vol.Required(CONF_PHONE_NUMBER): str,
    }
)

STEP_OTP_SCHEMA = vol.Schema(
    {
        vol.Required("otp_code"): vol.All(
            str, vol.Length(min=6, max=6), vol.Match(r"^\d{6}$")
        ),
    }
)


async def _check_server_reachable(hass: HomeAssistant, mcp_url: str) -> bool:
    """Return True if the MCP server answers on /mcp/info."""
    session = async_get_clientsession(hass)
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with session.get(f"{mcp_url}{ENDPOINT_INFO}", timeout=timeout) as resp:
            return resp.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def _send_otp(hass: HomeAssistant, mcp_url: str, phone_number: str) -> str | None:
    """
    Step 1 of SMS auth: ask the MCP server to send an OTP to the given phone number.
    Returns an error key string on failure, None on success.
    """
    session = async_get_clientsession(hass)
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        # Use /mcp/tools to avoid broken /mcp/auth/* validation schemas upstream.
        async with session.post(
            f"{mcp_url}{ENDPOINT_TOOLS}",
            json={
                "tool": "authenticate_sms",
                "params": {"phoneNumber": phone_number},
            },
            timeout=timeout,
        ) as resp:
            body_text = await resp.text()
            if resp.status != 200:
                _LOGGER.warning("MCP tools authenticate_sms HTTP %s: %s", resp.status, body_text[:500])
                return "auth_failed"

            try:
                data = aiohttp.helpers.json_loads(body_text)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("MCP tools authenticate_sms invalid JSON: %s", body_text[:500])
                return "auth_failed"

            if not data.get("success", False):
                _LOGGER.warning("MCP tools authenticate_sms failed: %s", body_text[:500])
                return "auth_failed"

            # Expected: { success: true, data: { status: "otp_sent", otpLength: 6 } }
            status = (data.get("data") or {}).get("status")
            if status != "otp_sent":
                _LOGGER.warning("Unexpected authenticate_sms status: %s", status)
                return "auth_failed"

            return None
    except asyncio.TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"


async def _validate_otp(
    hass: HomeAssistant, mcp_url: str, phone_number: str, otp_code: str
) -> tuple[str | None, str | None]:
    """
    Step 2 of SMS auth: validate OTP and open session.
    Returns (user_id, None) on success, or (None, error_key) on failure.
    """
    session = async_get_clientsession(hass)
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with session.post(
            f"{mcp_url}{ENDPOINT_TOOLS}",
            json={
                "tool": "authenticate_sms",
                "params": {"phoneNumber": phone_number, "otpCode": otp_code},
            },
            timeout=timeout,
        ) as resp:
            body_text = await resp.text()
            if resp.status == 400:
                return None, "invalid_otp"
            if resp.status == 401:
                return None, "invalid_otp"
            if resp.status != 200:
                _LOGGER.warning("MCP tools authenticate_sms OTP HTTP %s: %s", resp.status, body_text[:500])
                return None, "auth_failed"

            try:
                data = aiohttp.helpers.json_loads(body_text)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("MCP tools authenticate_sms OTP invalid JSON: %s", body_text[:500])
                return None, "auth_failed"

            if not data.get("success", False):
                _LOGGER.warning("MCP tools authenticate_sms OTP failed: %s", body_text[:500])
                return None, "invalid_otp"

            payload = data.get("data") or {}
            user_id: str | None = payload.get("userId")
            if not user_id:
                return None, "auth_failed"

            return user_id, None
    except asyncio.TimeoutError:
        return None, "timeout"
    except aiohttp.ClientError:
        return None, "cannot_connect"


class TinderMcpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Tinder MCP."""

    VERSION = 1

    def __init__(self) -> None:
        self._mcp_url: str = DEFAULT_MCP_URL
        self._phone_number: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: enter MCP server URL + phone number."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            mcp_url = user_input[CONF_MCP_URL].rstrip("/")
            phone_number = user_input[CONF_PHONE_NUMBER].strip()

            if not await _check_server_reachable(self.hass, mcp_url):
                errors["base"] = "cannot_connect"
            else:
                error = await _send_otp(self.hass, mcp_url, phone_number)
                if error:
                    errors["base"] = error
                else:
                    self._mcp_url = mcp_url
                    self._phone_number = phone_number
                    return await self.async_step_otp()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: enter the 6-digit OTP received by SMS."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp_code = user_input["otp_code"].strip()
            user_id, error = await _validate_otp(
                self.hass, self._mcp_url, self._phone_number, otp_code
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Tinder ({self._phone_number})",
                    data={
                        CONF_MCP_URL: self._mcp_url,
                        CONF_PHONE_NUMBER: self._phone_number,
                        CONF_USER_ID: user_id,
                    },
                )

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_SCHEMA,
            errors=errors,
            description_placeholders={"phone_number": self._phone_number},
        )
