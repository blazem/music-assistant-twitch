"""Small async client for the Twitch Helix API."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from music_assistant_models.errors import (
    LoginFailed,
    ProviderUnavailableError,
    RateLimited,
    ResourceTemporarilyUnavailable,
)

from music_assistant.helpers.throttle_retry import Throttler

from .constants import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    TWITCH_API_URL,
    TWITCH_SCOPE,
    TWITCH_TOKEN_URL,
    TWITCH_VALIDATE_URL,
)

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from .provider import TwitchProvider


class TwitchApiClient:
    """Authenticated Twitch API client with rotating device-flow refresh tokens."""

    def __init__(self, provider: TwitchProvider) -> None:
        """Initialize the client."""
        self.provider = provider
        # Twitch currently allows far more, but this leaves generous shared-account headroom.
        self._throttler = Throttler(rate_limit=10, period=1)
        self._refresh_lock = asyncio.Lock()

    async def validate(self) -> dict[str, Any]:
        """Validate the current token and return Twitch's token metadata."""
        token = await self._access_token()
        async with self.provider.mass.http_session.get(
            TWITCH_VALIDATE_URL,
            headers={"Authorization": f"OAuth {token}"},
        ) as response:
            if response.status == 401:
                token = await self._refresh_access_token(force=True)
                async with self.provider.mass.http_session.get(
                    TWITCH_VALIDATE_URL,
                    headers={"Authorization": f"OAuth {token}"},
                ) as retry_response:
                    return await self._validated_payload(retry_response)
            return await self._validated_payload(response)

    async def get_followed_streams(self, user_id: str) -> list[dict[str, Any]]:
        """Return every live stream followed by the authenticated user."""
        return await self._paginated_get("streams/followed", {"user_id": user_id})

    async def search_live_channels(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Search Twitch channels, retaining only channels that are currently live."""
        payload = await self._get(
            "search/channels",
            {"query": query, "first": str(min(max(limit * 2, limit), 100)), "live_only": "true"},
        )
        return [item for item in payload.get("data", []) if item.get("is_live")][:limit]

    async def get_live_stream(self, user_login: str) -> dict[str, Any] | None:
        """Return live stream metadata for one channel, or None when it is offline."""
        payload = await self._get("streams", {"user_login": user_login})
        data = payload.get("data", [])
        return data[0] if data else None

    async def _paginated_get(self, endpoint: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Read all pages from a Twitch Helix collection."""
        items: list[dict[str, Any]] = []
        page_params = {**params, "first": "100"}
        while True:
            payload = await self._get(endpoint, page_params)
            items.extend(payload.get("data", []))
            cursor = payload.get("pagination", {}).get("cursor")
            if not cursor:
                return items
            page_params["after"] = str(cursor)

    async def _get(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Perform one Helix GET, refreshing and retrying once on an expired token."""
        token = await self._access_token()
        response_data, status = await self._get_once(endpoint, params, token)
        if status == 401:
            token = await self._refresh_access_token(force=True)
            response_data, status = await self._get_once(endpoint, params, token)
        if status != 200:
            message = str(response_data.get("message") or f"Twitch returned HTTP {status}")
            raise ProviderUnavailableError(message)
        return response_data

    async def _get_once(
        self, endpoint: str, params: dict[str, str], token: str
    ) -> tuple[dict[str, Any], int]:
        """Perform one rate-limited Helix request."""
        client_id = str(self.provider.get_setup_value(CONF_CLIENT_ID) or "")
        async with (
            self._throttler,
            self.provider.mass.http_session.get(
                f"{TWITCH_API_URL}/{endpoint}",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Client-Id": client_id,
                },
            ) as response,
        ):
            payload: dict[str, Any] = await response.json()
            if response.status == 429:
                reset_at = int(response.headers.get("Ratelimit-Reset", "0") or 0)
                backoff = max(1, reset_at - int(time.time()))
                raise RateLimited("Twitch API rate limit reached", backoff_time=backoff)
            if response.status >= 500:
                raise ResourceTemporarilyUnavailable(
                    f"Twitch returned HTTP {response.status}", backoff_time=5
                )
            return payload, response.status

    async def _access_token(self) -> str:
        """Return a usable access token, refreshing before expiry."""
        expires_at = int(self.provider.get_setup_value(CONF_TOKEN_EXPIRES_AT, 0) or 0)
        token = str(self.provider.get_setup_value(CONF_ACCESS_TOKEN) or "")
        if token and expires_at > int(time.time()) + 60:
            return token
        return await self._refresh_access_token()

    async def _refresh_access_token(self, *, force: bool = False) -> str:
        """Refresh a public-client device token and persist the rotated credentials."""
        async with self._refresh_lock:
            expires_at = int(self.provider.get_setup_value(CONF_TOKEN_EXPIRES_AT, 0) or 0)
            token = str(self.provider.get_setup_value(CONF_ACCESS_TOKEN) or "")
            if not force and token and expires_at > int(time.time()) + 60:
                return token

            refresh_token = str(self.provider.get_setup_value(CONF_REFRESH_TOKEN) or "")
            client_id = str(self.provider.get_setup_value(CONF_CLIENT_ID) or "")
            if not refresh_token or not client_id:
                raise LoginFailed("Twitch authentication is missing; reconfigure the provider")
            async with self.provider.mass.http_session.post(
                TWITCH_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            ) as response:
                payload: dict[str, Any] = await response.json()
                if response.status != 200:
                    raise LoginFailed(
                        "Twitch authentication expired or was revoked; reconfigure the provider"
                    )
            new_token = str(payload.get("access_token") or "")
            new_refresh = str(payload.get("refresh_token") or "")
            if not new_token or not new_refresh:
                raise LoginFailed("Twitch returned incomplete refresh credentials")
            self.provider._update_setup_data(CONF_ACCESS_TOKEN, new_token, immediate=False)
            self.provider._update_setup_data(CONF_REFRESH_TOKEN, new_refresh, immediate=False)
            self.provider._update_setup_data(
                CONF_TOKEN_EXPIRES_AT,
                int(time.time()) + int(payload.get("expires_in") or 0),
            )
            return new_token

    @staticmethod
    async def _validated_payload(response: ClientResponse) -> dict[str, Any]:
        """Parse a successful validation response and enforce the required scope."""
        payload: dict[str, Any] = await response.json()
        if response.status != 200:
            raise LoginFailed("Twitch authentication expired or was revoked")
        if TWITCH_SCOPE not in payload.get("scopes", []):
            raise LoginFailed(f"Twitch token is missing the {TWITCH_SCOPE} scope")
        return payload
