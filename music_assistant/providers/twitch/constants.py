"""Constants for the Twitch music provider."""

from typing import Final

CONF_CLIENT_ID: Final = "client_id"
CONF_ACCESS_TOKEN: Final = "access_token"  # noqa: S105 - configuration key, not a token
CONF_REFRESH_TOKEN: Final = "refresh_token"  # noqa: S105 - configuration key, not a token
CONF_TOKEN_EXPIRES_AT: Final = "token_expires_at"  # noqa: S105 - configuration key
CONF_USER_ID: Final = "user_id"
CONF_USER_LOGIN: Final = "user_login"

TWITCH_API_URL: Final = "https://api.twitch.tv/helix"
TWITCH_DEVICE_URL: Final = "https://id.twitch.tv/oauth2/device"
TWITCH_TOKEN_URL: Final = "https://id.twitch.tv/oauth2/token"  # noqa: S105
TWITCH_VALIDATE_URL: Final = "https://id.twitch.tv/oauth2/validate"
TWITCH_SCOPE: Final = "user:read:follows"

BROWSE_FOLLOWED_LIVE: Final = "followed-live"
