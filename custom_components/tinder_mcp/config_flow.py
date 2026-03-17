"""Config flow for Tinder MCP — phone/OTP or direct X-Auth-Token."""
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
    AUTH_METHOD_PHONE,
    AUTH_METHOD_TOKEN,
    CONF_AUTH_TOKEN,
    CONF_PHONE_NUMBER,
    DOMAIN,
    ENDPOINT_AUTH_LOGIN_SMS,
    ENDPOINT_AUTH_SMS_SEND,
    ENDPOINT_AUTH_SMS_VALIDATE,
    ENDPOINT_RECOMMENDATIONS,
    HTTP_TIMEOUT,
    TINDER_API_BASE,
)

_LOGGER = logging.getLogger(__name__)

# Shared headers for unauthenticated auth requests
_AUTH_HEADERS = {
    "Content-Type": "application/json",
    "app-version": "1010024",
    "platform": "ios",
    "User-Agent": "Tinder/11.4.0 (iPhone; iOS 12.4.1; Scale/2.00)",
    "X-Supported-Image-Formats": "webp",
}

STEP_METHOD_SCHEMA = vol.Schema(
    {
        vol.Required("method", default=AUTH_METHOD_PHONE): vol.In(
            [AUTH_METHOD_PHONE, AUTH_METHOD_TOKEN]
        ),
    }
)

STEP_PHONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE_NUMBER): str,
    }
)

STEP_OTP_SCHEMA = vol.Schema(
    {
        vol.Required("otp_code"): str,
    }
)

STEP_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_TOKEN): str,
    }
)


async def _send_sms(hass: HomeAssistant, phone: str) -> str | None:
    """POST /v2/auth/sms/send — request an OTP for *phone*.

    Returns an error key string on failure, or ``None`` on success.
    """
    session = async_get_clientsession(hass)
    url = f"{TINDER_API_BASE}{ENDPOINT_AUTH_SMS_SEND}"
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with session.post(
            url,
            json={"phone_number": phone},
            headers=_AUTH_HEADERS,
            timeout=timeout,
        ) as resp:
            if resp.status == 404:
                return "sms_unavailable"
            if resp.status not in (200, 201):
                body = await resp.text()
                _LOGGER.warning("SMS send HTTP %s: %s", resp.status, body[:300])
                return "cannot_connect"
            return None
    except asyncio.TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"


async def _validate_otp(
    hass: HomeAssistant, phone: str, otp: str
) -> tuple[str | None, str | None]:
    """Validate *otp* for *phone* and exchange for an api_token.

    Returns ``(api_token, None)`` on success, or ``(None, error_key)`` on failure.
    """
    session = async_get_clientsession(hass)
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)

    # Step 1 — validate OTP → refresh_token
    validate_url = f"{TINDER_API_BASE}{ENDPOINT_AUTH_SMS_VALIDATE}"
    try:
        async with session.post(
            validate_url,
            json={"phone_number": phone, "otp_code": otp, "is_update": False},
            headers=_AUTH_HEADERS,
            timeout=timeout,
        ) as resp:
            if resp.status == 404:
                return None, "sms_unavailable"
            if resp.status == 401:
                return None, "invalid_otp"
            if resp.status not in (200, 201):
                body = await resp.text()
                _LOGGER.warning("OTP validate HTTP %s: %s", resp.status, body[:300])
                return None, "cannot_connect"
            data = await resp.json()
    except asyncio.TimeoutError:
        return None, "timeout"
    except aiohttp.ClientError:
        return None, "cannot_connect"

    refresh_token: str | None = (
        data.get("data", {}).get("refresh_token")
        or data.get("refresh_token")
    )
    if not refresh_token:
        _LOGGER.warning("No refresh_token in OTP validate response: %s", data)
        return None, "no_refresh_token"

    # Step 2 — exchange refresh_token → api_token
    login_url = f"{TINDER_API_BASE}{ENDPOINT_AUTH_LOGIN_SMS}"
    try:
        async with session.post(
            login_url,
            json={"refresh_token": refresh_token},
            headers=_AUTH_HEADERS,
            timeout=timeout,
        ) as resp:
            if resp.status == 404:
                return None, "sms_unavailable"
            if resp.status == 401:
                return None, "invalid_auth"
            if resp.status not in (200, 201):
                body = await resp.text()
                _LOGGER.warning("SMS login HTTP %s: %s", resp.status, body[:300])
                return None, "cannot_connect"
            login_data = await resp.json()
    except asyncio.TimeoutError:
        return None, "timeout"
    except aiohttp.ClientError:
        return None, "cannot_connect"

    api_token: str | None = (
        login_data.get("data", {}).get("api_token")
        or login_data.get("api_token")
    )
    if not api_token:
        _LOGGER.warning("No api_token in SMS login response: %s", login_data)
        return None, "no_api_token"

    return api_token, None


async def _validate_token(hass: HomeAssistant, auth_token: str) -> str | None:
    """Validate X-Auth-Token by fetching recommendations (200 expected).

    Returns an error key string on failure, or ``None`` on success.
    """
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
    """Multi-step config flow for Tinder MCP.

    Flow options:
      • Phone/OTP — sends an SMS OTP, validates it and exchanges for an
        ``api_token`` automatically (no manual token extraction needed).
      • Manual token — paste an ``X-Auth-Token`` obtained from browser DevTools
        as a fallback if the SMS endpoints are unavailable.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._phone: str = ""

    # ------------------------------------------------------------------
    # Step 0 — choose method
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Let the user choose between phone/OTP and manual token."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            method = user_input.get("method", AUTH_METHOD_PHONE)
            if method == AUTH_METHOD_PHONE:
                return await self.async_step_phone()
            return await self.async_step_token()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_METHOD_SCHEMA,
            errors={},
        )

    # ------------------------------------------------------------------
    # Step 1a — phone number entry + SMS send
    # ------------------------------------------------------------------

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Enter phone number and trigger OTP SMS."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE_NUMBER].strip()
            error = await _send_sms(self.hass, phone)
            if error:
                errors["base"] = error
            else:
                self._phone = phone
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="phone",
            data_schema=STEP_PHONE_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    # ------------------------------------------------------------------
    # Step 1b — OTP validation + token exchange
    # ------------------------------------------------------------------

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Enter the OTP received by SMS and exchange it for an api_token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp = user_input["otp_code"].strip()
            api_token, error = await _validate_otp(self.hass, self._phone, otp)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Tinder MCP",
                    data={CONF_AUTH_TOKEN: api_token},
                )

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_SCHEMA,
            errors=errors,
            description_placeholders={"phone": self._phone},
        )

    # ------------------------------------------------------------------
    # Step 2 — manual X-Auth-Token (fallback)
    # ------------------------------------------------------------------

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Enter an X-Auth-Token obtained manually from browser DevTools."""
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
            step_id="token",
            data_schema=STEP_TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={},
        )
