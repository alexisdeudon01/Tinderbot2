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

The add-on does **not** require your Tinder token in its config. Authentication happens via the HA integration UI:

1. Enter your phone number (e.g. `+33612345678`)
2. Tinder sends you an SMS with a 6-digit OTP
3. Enter the OTP in HA → session is opened automatically

The `api_token` is stored securely inside the add-on's `/data/` directory and refreshed automatically.

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
