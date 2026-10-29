"""Constants for the Twitch music provider."""

from typing import Final

CONF_CLIENT_ID: Final = "client_id"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_TOKEN_EXPIRES_AT: Final = "token_expires_at"
CONF_USER_ID: Final = "user_id"
CONF_USER_LOGIN: Final = "user_login"

TWITCH_API_URL: Final = "https://api.twitch.tv/helix"
TWITCH_DEVICE_URL: Final = "https://id.twitch.tv/oauth2/device"
TWITCH_TOKEN_URL: Final = "https://id.twitch.tv/oauth2/token"
TWITCH_VALIDATE_URL: Final = "https://id.twitch.tv/oauth2/validate"
TWITCH_SCOPE: Final = "user:read:follows"

BROWSE_FOLLOWED_LIVE: Final = "followed-live"

# How often to check which followed channels are live, so the Radio library
# tracks channels going live or offline without waiting for the full library sync.
LIVE_POLL_INTERVAL: Final = 180
