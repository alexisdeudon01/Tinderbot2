"""Constants for the Tinder MCP integration."""
from datetime import timedelta

DOMAIN = "tinder_mcp"

# Configuration keys stored in ConfigEntry
CONF_AUTH_TOKEN = "auth_token"
CONF_PHONE_NUMBER = "phone_number"

# Authentication method choices
AUTH_METHOD_PHONE = "phone"
AUTH_METHOD_TOKEN = "token"

# Tinder API
TINDER_API_BASE = "https://api.gotinder.com"

# DataUpdateCoordinator refresh interval
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# Keys used in hass.data[DOMAIN][entry_id]
ATTR_COORDINATOR = "coordinator"
ATTR_CLIENT = "client"

# Entity unique ID prefixes
ENTITY_PROFILE_NAME = "profile_name"
ENTITY_PROFILE_AGE = "profile_age"
ENTITY_PROFILE_BIO = "profile_bio"
ENTITY_MATCH_COUNT = "match_count"
ENTITY_PROFILE_PHOTO = "profile_photo"
ENTITY_BUTTON_LIKE = "like"
ENTITY_BUTTON_PASS = "pass"
ENTITY_BUTTON_SUPERLIKE = "superlike"
ENTITY_BUTTON_REFRESH = "refresh"

# Service name
SERVICE_SWIPE = "swipe"
ATTR_DIRECTION = "direction"
ATTR_TARGET_USER_ID = "target_user_id"
DIRECTION_RIGHT = "right"
DIRECTION_LEFT = "left"

# Tinder API endpoints (direct calls with X-Auth-Token)
ENDPOINT_RECOMMENDATIONS = "/v2/recs/core"
ENDPOINT_MATCHES = "/v2/matches"
ENDPOINT_LIKE = "/like/{user_id}"
ENDPOINT_PASS = "/pass/{user_id}"
ENDPOINT_SUPERLIKE = "/like/{user_id}/super"

# Tinder SMS authentication endpoints
ENDPOINT_AUTH_SMS_SEND = "/v2/auth/sms/send"
ENDPOINT_AUTH_SMS_VALIDATE = "/v2/auth/sms/validate"
ENDPOINT_AUTH_LOGIN_SMS = "/v2/auth/login/sms"

# HTTP timeout (seconds)
HTTP_TIMEOUT = 15
