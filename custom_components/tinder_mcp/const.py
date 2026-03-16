"""Constants for the Tinder MCP integration."""
from datetime import timedelta

DOMAIN = "tinder_mcp"

# Configuration keys stored in ConfigEntry
CONF_MCP_URL = "mcp_url"
CONF_USER_ID = "user_id"
CONF_PHONE_NUMBER = "phone_number"

# Default MCP server URL (add-on hostname within HAOS supervisor network)
DEFAULT_MCP_URL = "http://tinder_mcp_server:3000"

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

# MCP server HTTP endpoints
ENDPOINT_AUTH_SMS_SEND = "/mcp/auth/sms/send"
ENDPOINT_AUTH_SMS_VALIDATE = "/mcp/auth/sms/validate"
ENDPOINT_INFO = "/mcp/info"
ENDPOINT_RECOMMENDATIONS = "/mcp/user/recommendations"
ENDPOINT_MATCHES = "/mcp/user/matches"
ENDPOINT_LIKE = "/mcp/interaction/like/{user_id}"
ENDPOINT_PASS = "/mcp/interaction/pass/{user_id}"
ENDPOINT_SUPERLIKE = "/mcp/interaction/superlike/{user_id}"

# HTTP timeout (seconds)
HTTP_TIMEOUT = 15
