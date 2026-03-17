# Tinder MCP Server — Add-on Documentation

## Overview

This add-on runs the [glassbead-tc/tinder-mcp-server](https://github.com/glassbead-tc/tinder-mcp-server) as a Home Assistant add-on. It exposes an HTTP API on port **3000** that the **Tinder MCP** custom integration consumes.

The server handles:
- SMS and Facebook authentication with Tinder
- Rate limiting and caching of API responses
- Secure token storage (tokens are never stored in HA config)

## Installation

1. Add this repository to your HA add-on store
2. Install **Tinder MCP Server**
3. Start the add-on
4. Install the **Tinder MCP** custom integration via *Configuration → Devices & Services*

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `log_level` | `info` | Logging verbosity: `debug`, `info`, `warn`, `error` |
| `port` | `3000` | HTTP port the server listens on |
| `cache_ttl` | `300` | Cache time-to-live in seconds |
| `rate_limit_max` | `100` | Max requests per minute |

## Authentication Flow

The integration offers two authentication methods — choose the one that works for you:

### Method 1 — Phone number / SMS OTP (recommended)

This is the simplest method and requires no manual token extraction:

1. In HA go to *Configuration → Devices & Services → Add Integration → Tinder MCP*
2. Select **Phone number (SMS)**
3. Enter your phone number in international format (e.g. `+33612345678`)
4. Tinder sends a 6-digit code by SMS
5. Enter the code in HA → the session opens automatically

The integration exchanges the OTP for a Tinder `api_token` and stores it securely in the HA config entry. No manual copy-pasting of tokens is needed.

> **Note:** If the SMS endpoint returns a 404 error (Tinder occasionally deprecates or restricts these endpoints), fall back to Method 2.

### Method 2 — Manual X-Auth-Token (fallback)

Use this method if SMS is unavailable or returns errors:

1. Open [tinder.com](https://tinder.com) in your browser and log in
2. Open DevTools (F12) → **Network** tab
3. Reload the page and filter requests by `gotinder.com`
4. Click any request and look at the **Request Headers** for `X-Auth-Token`
5. Copy its value and paste it into HA during integration setup

## Networking

The add-on is accessible from HA Core at:

```
http://tinder_mcp_server:3000
```

or via the exposed host port:

```
http://localhost:3000
```

## Troubleshooting

- **Add-on won't start**: Check the add-on logs for Node.js errors
- **401 errors**: Your Tinder session expired — re-authenticate via the HA integration
- **No recommendations**: Tinder may have rate-limited your account (wait a few minutes)
- **SMS returns 404**: The SMS auth endpoint is unavailable — use the manual token method instead
