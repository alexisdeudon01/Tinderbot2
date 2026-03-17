"""Tests for custom_components/tinder_mcp/config_flow.py

Runs without a real Home Assistant instance by providing lightweight stubs
for every HA symbol used by the module under test.
"""
from __future__ import annotations

import asyncio
import sys
import types
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs (must come before any import of the module)
# ---------------------------------------------------------------------------

_ce_mod = types.ModuleType("homeassistant.config_entries")


class _FlowResult(dict):
    pass


class _ConfigFlow:
    """Stub for homeassistant.config_entries.ConfigFlow."""

    DOMAIN = None

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if domain:
            cls.DOMAIN = domain

    # Subclasses may override __init__ without calling super(), so we do NOT
    # set _entries here. Tests inject _async_current_entries per-instance.
    def _async_current_entries(self):
        return []  # default: no existing entries

    def async_abort(self, *, reason: str) -> _FlowResult:
        return _FlowResult(type="abort", reason=reason)

    def async_show_form(self, *, step_id, data_schema=None, errors=None,
                        description_placeholders=None) -> _FlowResult:
        return _FlowResult(type="form", step_id=step_id, errors=errors or {})

    def async_create_entry(self, *, title: str, data: dict) -> _FlowResult:
        return _FlowResult(type="create_entry", title=title, data=data)


_ce_mod.ConfigFlow = _ConfigFlow
_ce_mod.FlowResult = _FlowResult

_ha_mod = types.ModuleType("homeassistant")
_core_mod = types.ModuleType("homeassistant.core")
_core_mod.HomeAssistant = MagicMock
_helpers_mod = types.ModuleType("homeassistant.helpers")
_aiohttp_client_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
_aiohttp_client_mod.async_get_clientsession = MagicMock()

sys.modules.setdefault("homeassistant", _ha_mod)
sys.modules["homeassistant.config_entries"] = _ce_mod
sys.modules["homeassistant.core"] = _core_mod
sys.modules["homeassistant.helpers"] = _helpers_mod
sys.modules["homeassistant.helpers.aiohttp_client"] = _aiohttp_client_mod

# ---------------------------------------------------------------------------
# Load const.py then config_flow.py as a proper package so relative imports work
# ---------------------------------------------------------------------------

import importlib.util
import pathlib

_BASE = pathlib.Path(
    "/home/runner/work/Tinderbot2/Tinderbot2/custom_components/tinder_mcp"
)

# 1. Register the tinder_mcp package namespace
_pkg = types.ModuleType("tinder_mcp")
_pkg.__path__ = [str(_BASE)]
_pkg.__package__ = "tinder_mcp"
sys.modules["tinder_mcp"] = _pkg

# 2. Load tinder_mcp.const
_const_spec = importlib.util.spec_from_file_location(
    "tinder_mcp.const", str(_BASE / "const.py"),
    submodule_search_locations=None,
)
_const_mod = importlib.util.module_from_spec(_const_spec)
_const_mod.__package__ = "tinder_mcp"
sys.modules["tinder_mcp.const"] = _const_mod
_const_spec.loader.exec_module(_const_mod)

# 3. Load tinder_mcp.config_flow
_cf_spec = importlib.util.spec_from_file_location(
    "tinder_mcp.config_flow", str(_BASE / "config_flow.py"),
    submodule_search_locations=None,
)
_cf_mod = importlib.util.module_from_spec(_cf_spec)
_cf_mod.__package__ = "tinder_mcp"
sys.modules["tinder_mcp.config_flow"] = _cf_mod
_cf_spec.loader.exec_module(_cf_mod)

# ---------------------------------------------------------------------------
# Convenient aliases
# ---------------------------------------------------------------------------

_send_sms = _cf_mod._send_sms
_validate_otp = _cf_mod._validate_otp
_validate_token = _cf_mod._validate_token
TinderMcpConfigFlow = _cf_mod.TinderMcpConfigFlow
TINDER_API_BASE = _const_mod.TINDER_API_BASE

# Endpoint URLs (for clarity in test assertions)
_SEND_URL = f"{TINDER_API_BASE}/v2/auth/sms/send"
_VAL_URL = f"{TINDER_API_BASE}/v2/auth/sms/validate"
_LOGIN_URL = f"{TINDER_API_BASE}/v2/auth/login/sms"
_RECS_URL = f"{TINDER_API_BASE}/v2/recs/core"


# ---------------------------------------------------------------------------
# Helpers: fake HTTP responses and sessions
# ---------------------------------------------------------------------------

class _MockHA:
    """Minimal stand-in for HomeAssistant."""


def _fake_resp(status: int, body: Any = None, is_json: bool = True):
    """Return a *callable* that, when called, yields a fake aiohttp response.

    Usage in url_map:  ``{url: _fake_resp(200, {})}``
    The returned object is an @asynccontextmanager-decorated function; calling
    it produces an async context manager — exactly what aiohttp's session
    methods return.
    """
    resp = MagicMock()
    resp.status = status
    if is_json and body is not None:
        resp.json = AsyncMock(return_value=body)
    else:
        resp.text = AsyncMock(return_value=body if isinstance(body, str) else "")

    @asynccontextmanager
    async def _ctx(*_a, **_kw):
        yield resp

    return _ctx   # caller is responsible for calling _ctx() to get the CM


def _make_session(**url_map):
    """Build a mock aiohttp session.

    *url_map* maps URL → a callable that returns an async context manager
    (i.e. the value returned by ``_fake_resp(...)``).

    Unknown URLs default to a 200 empty-JSON response.
    """
    _default_factory = _fake_resp(200, {})
    session = MagicMock()

    def _dispatch(url, **kw):
        factory = url_map.get(url, _default_factory)
        return factory()   # factory is the @asynccontextmanager fn; calling it returns the CM

    session.get = lambda url, **kw: _dispatch(url, **kw)
    session.post = lambda url, **kw: _dispatch(url, **kw)
    return session


def _patch_session(session):
    return patch(
        "tinder_mcp.config_flow.async_get_clientsession",
        return_value=session,
    )


# Commonly-used response factories
_GOOD_VALIDATE = _fake_resp(200, {"data": {"refresh_token": "RTOKEN"}})
_GOOD_LOGIN = _fake_resp(200, {"data": {"api_token": "ATOKEN"}})


def _flow(has_entries: bool = False) -> TinderMcpConfigFlow:
    """Create a fresh flow instance with optional existing-entry simulation."""
    f = TinderMcpConfigFlow()
    f.hass = _MockHA()
    if has_entries:
        f._async_current_entries = lambda: ["existing"]
    return f


# ===========================================================================
# _send_sms
# ===========================================================================

@pytest.mark.asyncio
async def test_send_sms_success_200():
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(200, {})})):
        assert await _send_sms(_MockHA(), "+33612345678") is None


@pytest.mark.asyncio
async def test_send_sms_success_201():
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(201, {})})):
        assert await _send_sms(_MockHA(), "+33612345678") is None


@pytest.mark.asyncio
async def test_send_sms_404_returns_sms_unavailable():
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(404, is_json=False, body="NF")})):
        assert await _send_sms(_MockHA(), "+33612345678") == "sms_unavailable"


@pytest.mark.asyncio
async def test_send_sms_500_returns_cannot_connect():
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(500, is_json=False, body="err")})):
        assert await _send_sms(_MockHA(), "+33612345678") == "cannot_connect"


@pytest.mark.asyncio
async def test_send_sms_timeout():
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise asyncio.TimeoutError()
        yield  # unreachable but required for @asynccontextmanager

    session.post = lambda *a, **k: _raises()
    with _patch_session(session):
        assert await _send_sms(_MockHA(), "+33612345678") == "timeout"


@pytest.mark.asyncio
async def test_send_sms_client_error():
    import aiohttp
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise aiohttp.ClientError("boom")
        yield

    session.post = lambda *a, **k: _raises()
    with _patch_session(session):
        assert await _send_sms(_MockHA(), "+33612345678") == "cannot_connect"


# ===========================================================================
# _validate_otp
# ===========================================================================

@pytest.mark.asyncio
async def test_validate_otp_happy_path_nested():
    """Successful flow: data.refresh_token → data.api_token (nested response)."""
    session = _make_session(**{_VAL_URL: _GOOD_VALIDATE, _LOGIN_URL: _GOOD_LOGIN})
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "123456")
    assert err is None and token == "ATOKEN"


@pytest.mark.asyncio
async def test_validate_otp_happy_path_flat():
    """Successful flow: fields at top level (flat response)."""
    session = _make_session(**{
        _VAL_URL: _fake_resp(200, {"refresh_token": "RF"}),
        _LOGIN_URL: _fake_resp(200, {"api_token": "AF"}),
    })
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "123456")
    assert err is None and token == "AF"


@pytest.mark.asyncio
async def test_validate_otp_validate_404():
    session = _make_session(**{_VAL_URL: _fake_resp(404, is_json=False, body="NF")})
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "sms_unavailable"


@pytest.mark.asyncio
async def test_validate_otp_validate_401():
    session = _make_session(**{_VAL_URL: _fake_resp(401, {})})
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "invalid_otp"


@pytest.mark.asyncio
async def test_validate_otp_validate_500():
    session = _make_session(**{_VAL_URL: _fake_resp(500, is_json=False, body="err")})
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_otp_no_refresh_token():
    """validate response with empty data → no_refresh_token error."""
    session = _make_session(**{_VAL_URL: _fake_resp(200, {"data": {}})})
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "no_refresh_token"


@pytest.mark.asyncio
async def test_validate_otp_login_404():
    session = _make_session(**{
        _VAL_URL: _GOOD_VALIDATE,
        _LOGIN_URL: _fake_resp(404, is_json=False, body="NF"),
    })
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "sms_unavailable"


@pytest.mark.asyncio
async def test_validate_otp_login_401():
    session = _make_session(**{
        _VAL_URL: _GOOD_VALIDATE,
        _LOGIN_URL: _fake_resp(401, {}),
    })
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "invalid_auth"


@pytest.mark.asyncio
async def test_validate_otp_no_api_token():
    session = _make_session(**{
        _VAL_URL: _GOOD_VALIDATE,
        _LOGIN_URL: _fake_resp(200, {"data": {}}),
    })
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "no_api_token"


@pytest.mark.asyncio
async def test_validate_otp_timeout_on_validate():
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise asyncio.TimeoutError()
        yield

    session.post = lambda *a, **k: _raises()
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "timeout"


@pytest.mark.asyncio
async def test_validate_otp_client_error_on_login():
    """ClientError raised during the login request (second POST)."""
    import aiohttp

    call_count = {"n": 0}

    @asynccontextmanager
    async def _post(url, **kw):
        call_count["n"] += 1
        if url == _VAL_URL:
            resp = MagicMock()
            resp.status = 200
            resp.json = AsyncMock(return_value={"data": {"refresh_token": "RT"}})
            yield resp
        else:
            raise aiohttp.ClientError("net down")

    session = MagicMock()
    session.post = _post
    with _patch_session(session):
        token, err = await _validate_otp(_MockHA(), "+336", "000000")
    assert token is None and err == "cannot_connect"


# ===========================================================================
# _validate_token
# ===========================================================================

@pytest.mark.asyncio
async def test_validate_token_success():
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(200, {})})):
        assert await _validate_token(_MockHA(), "GOOD") is None


@pytest.mark.asyncio
async def test_validate_token_401():
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(401, {})})):
        assert await _validate_token(_MockHA(), "BAD") == "invalid_auth"


@pytest.mark.asyncio
async def test_validate_token_500():
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(500, is_json=False, body="err")})):
        assert await _validate_token(_MockHA(), "ANY") == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_token_timeout():
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise asyncio.TimeoutError()
        yield

    session.get = lambda *a, **k: _raises()
    with _patch_session(session):
        assert await _validate_token(_MockHA(), "ANY") == "timeout"


@pytest.mark.asyncio
async def test_validate_token_client_error():
    import aiohttp
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise aiohttp.ClientError("net down")
        yield

    session.get = lambda *a, **k: _raises()
    with _patch_session(session):
        assert await _validate_token(_MockHA(), "ANY") == "cannot_connect"


# ===========================================================================
# Config flow steps
# ===========================================================================

@pytest.mark.asyncio
async def test_step_user_shows_form():
    result = await _flow().async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_step_user_already_configured():
    result = await _flow(has_entries=True).async_step_user(None)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_step_user_phone_method_goes_to_phone_step():
    result = await _flow().async_step_user({"method": "phone"})
    assert result["type"] == "form"
    assert result["step_id"] == "phone"


@pytest.mark.asyncio
async def test_step_user_token_method_goes_to_token_step():
    result = await _flow().async_step_user({"method": "token"})
    assert result["type"] == "form"
    assert result["step_id"] == "token"


@pytest.mark.asyncio
async def test_step_phone_shows_form_when_no_input():
    result = await _flow().async_step_phone(None)
    assert result["type"] == "form"
    assert result["step_id"] == "phone"


@pytest.mark.asyncio
async def test_step_phone_success_goes_to_otp():
    flow = _flow()
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(200, {})})):
        result = await flow.async_step_phone({"phone_number": "+33612345678"})
    assert result["type"] == "form"
    assert result["step_id"] == "otp"
    assert flow._phone == "+33612345678"


@pytest.mark.asyncio
async def test_step_phone_strips_whitespace():
    """Phone number with surrounding spaces must be stored stripped."""
    flow = _flow()
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(200, {})})):
        await flow.async_step_phone({"phone_number": "  +33612345678  "})
    assert flow._phone == "+33612345678"


@pytest.mark.asyncio
async def test_step_phone_sms_unavailable_shows_error():
    with _patch_session(_make_session(**{_SEND_URL: _fake_resp(404, is_json=False, body="NF")})):
        result = await _flow().async_step_phone({"phone_number": "+336"})
    assert result["type"] == "form" and result["step_id"] == "phone"
    assert result["errors"]["base"] == "sms_unavailable"


@pytest.mark.asyncio
async def test_step_phone_timeout_shows_error():
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise asyncio.TimeoutError()
        yield

    session.post = lambda *a, **k: _raises()
    with _patch_session(session):
        result = await _flow().async_step_phone({"phone_number": "+336"})
    assert result["errors"]["base"] == "timeout"


@pytest.mark.asyncio
async def test_step_otp_shows_form_when_no_input():
    flow = _flow()
    flow._phone = "+336"
    result = await flow.async_step_otp(None)
    assert result["type"] == "form" and result["step_id"] == "otp"


@pytest.mark.asyncio
async def test_step_otp_success_creates_entry():
    flow = _flow()
    flow._phone = "+33612345678"
    session = _make_session(**{_VAL_URL: _GOOD_VALIDATE, _LOGIN_URL: _GOOD_LOGIN})
    with _patch_session(session):
        result = await flow.async_step_otp({"otp_code": "123456"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Tinder MCP"
    assert result["data"]["auth_token"] == "ATOKEN"


@pytest.mark.asyncio
async def test_step_otp_invalid_otp_shows_error():
    flow = _flow()
    flow._phone = "+336"
    with _patch_session(_make_session(**{_VAL_URL: _fake_resp(401, {})})):
        result = await flow.async_step_otp({"otp_code": "000000"})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_otp"


@pytest.mark.asyncio
async def test_step_otp_sms_unavailable_shows_error():
    flow = _flow()
    flow._phone = "+336"
    with _patch_session(_make_session(**{_VAL_URL: _fake_resp(404, is_json=False, body="NF")})):
        result = await flow.async_step_otp({"otp_code": "000000"})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "sms_unavailable"


@pytest.mark.asyncio
async def test_step_otp_strips_whitespace():
    """OTP with surrounding whitespace must be sent to the API stripped."""
    flow = _flow()
    flow._phone = "+33612345678"

    captured = {}

    @asynccontextmanager
    async def _post(url, json=None, **kw):
        if url == _VAL_URL:
            captured["otp"] = (json or {}).get("otp_code")
            resp = MagicMock()
            resp.status = 200
            resp.json = AsyncMock(return_value={"data": {"refresh_token": "RT"}})
            yield resp
        else:
            resp = MagicMock()
            resp.status = 200
            resp.json = AsyncMock(return_value={"data": {"api_token": "AT"}})
            yield resp

    session = MagicMock()
    session.post = _post
    with _patch_session(session):
        await flow.async_step_otp({"otp_code": "  654321  "})
    assert captured["otp"] == "654321"


@pytest.mark.asyncio
async def test_step_token_shows_form_when_no_input():
    result = await _flow().async_step_token(None)
    assert result["type"] == "form" and result["step_id"] == "token"


@pytest.mark.asyncio
async def test_step_token_success_creates_entry():
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(200, {})})):
        result = await _flow().async_step_token({"auth_token": "MYTOKEN"})
    assert result["type"] == "create_entry"
    assert result["data"]["auth_token"] == "MYTOKEN"


@pytest.mark.asyncio
async def test_step_token_strips_whitespace():
    """Tokens with surrounding whitespace must be stored stripped."""
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(200, {})})):
        result = await _flow().async_step_token({"auth_token": "  TOKEN  "})
    assert result["data"]["auth_token"] == "TOKEN"


@pytest.mark.asyncio
async def test_step_token_invalid_shows_error():
    with _patch_session(_make_session(**{_RECS_URL: _fake_resp(401, {})})):
        result = await _flow().async_step_token({"auth_token": "BAD"})
    assert result["type"] == "form" and result["step_id"] == "token"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_step_token_timeout_shows_error():
    session = MagicMock()

    @asynccontextmanager
    async def _raises(*_a, **_kw):
        raise asyncio.TimeoutError()
        yield

    session.get = lambda *a, **k: _raises()
    with _patch_session(session):
        result = await _flow().async_step_token({"auth_token": "ANY"})
    assert result["errors"]["base"] == "timeout"
