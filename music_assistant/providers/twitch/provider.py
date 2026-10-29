"""Twitch music provider implementation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Sequence
from typing import TYPE_CHECKING, Any

from music_assistant_models.enums import ContentType, ImageType, LinkType, MediaType, StreamType
from music_assistant_models.errors import MediaNotFoundError, ProviderUnavailableError
from music_assistant_models.media_items import (
    AudioFormat,
    BrowseFolder,
    MediaItemImage,
    MediaItemLink,
    MediaItemType,
    ProviderMapping,
    Radio,
    SearchResults,
    UniqueList,
)
from music_assistant_models.streamdetails import StreamDetails

from music_assistant.models.music_provider import MusicProvider

from .api import TwitchApiClient
from .constants import BROWSE_FOLLOWED_LIVE, CONF_USER_ID, CONF_USER_LOGIN, LIVE_POLL_INTERVAL
from .streaming import resolve_stream_url

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigEntry


class TwitchProvider(MusicProvider):
    """Browse and play live Twitch channels as radio streams."""

    _live_watch_task: asyncio.Task[None] | None = None
    _live_logins: frozenset[str] | None = None

    async def get_config_entries(self) -> tuple[ConfigEntry, ...]:
        """Return configurable options for an existing provider instance."""
        return ()

    async def handle_async_init(self) -> None:
        """Validate credentials before making the provider available."""
        self.api = TwitchApiClient(self)
        token_data = await self.api.validate()
        expected_user_id = str(self.get_setup_value(CONF_USER_ID) or "")
        if not expected_user_id or str(token_data.get("user_id") or "") != expected_user_id:
            raise ProviderUnavailableError(
                "Twitch authentication belongs to a different account; reconfigure the provider"
            )

    async def loaded_in_mass(self) -> None:
        """Start watching which followed channels are live."""
        self._live_watch_task = self.mass.create_task(self._watch_followed_live())

    async def unload(self, is_removed: bool = False) -> None:
        """Stop watching followed channels."""
        if self._live_watch_task is not None:
            self._live_watch_task.cancel()
            self._live_watch_task = None
        await super().unload(is_removed)

    async def _watch_followed_live(self) -> None:
        """Poll followed channels until the provider unloads."""
        while True:
            await self._check_followed_live()
            await asyncio.sleep(LIVE_POLL_INTERVAL)

    async def _check_followed_live(self) -> None:
        """Sync this provider's radios when a followed channel goes live or offline."""
        user_id = str(self.get_setup_value(CONF_USER_ID) or "")
        try:
            streams = await self.api.get_followed_streams(user_id)
        except Exception as err:
            self.logger.debug("Skipping Twitch live check: %s", err)
            return
        logins = frozenset(str(item["user_login"]).lower() for item in streams)
        if logins == self._live_logins:
            return
        self._live_logins = logins
        await self.mass.music.start_sync(
            media_types=[MediaType.RADIO], providers=[self.instance_id]
        )

    @property
    def is_streaming_provider(self) -> bool:
        """Return True because Twitch is a remote streaming catalogue."""
        return True

    @property
    def supported_media_types(self) -> set[MediaType]:
        """Twitch channels are represented as live radio items."""
        return {MediaType.RADIO}

    async def browse(self, path: str) -> Sequence[MediaItemType | BrowseFolder]:
        """Browse live followed Twitch channels."""
        subpath = "" if "://" not in path else path.split("://", 1)[1].strip("/")
        if not subpath:
            provider_icon = self.mass.get_provider_icon_data(self.domain)
            return [
                BrowseFolder(
                    item_id=BROWSE_FOLLOWED_LIVE,
                    provider=self.domain,
                    path=f"{path}{BROWSE_FOLLOWED_LIVE}",
                    name="Live followed channels",
                    translation_key="twitch_followed_live",
                    image=(
                        MediaItemImage(
                            type=ImageType.THUMB,
                            path=provider_icon,
                            provider=self.domain,
                            remotely_accessible=True,
                        )
                        if isinstance(provider_icon, str)
                        else None
                    ),
                )
            ]
        if subpath != BROWSE_FOLLOWED_LIVE:
            return []
        user_id = str(self.get_setup_value(CONF_USER_ID) or "")
        return [self._parse_stream(item) for item in await self.api.get_followed_streams(user_id)]

    async def get_library_radios(self) -> AsyncGenerator[Radio]:
        """Yield the followed channels that are live right now."""
        user_id = str(self.get_setup_value(CONF_USER_ID) or "")
        # Fetch every page before yielding so an API failure aborts the sync
        # instead of being mistaken for all channels going offline.
        streams = await self.api.get_followed_streams(user_id)
        for item in streams:
            yield self._parse_stream(item)

    async def search(
        self, search_query: str, media_types: list[MediaType], limit: int = 5
    ) -> SearchResults:
        """Search currently live Twitch channels."""
        results = SearchResults()
        if MediaType.RADIO not in media_types:
            return results
        channels = await self.api.search_live_channels(search_query, limit)
        results.radio = [self._parse_search_channel(item) for item in channels]
        return results

    async def get_radio(self, prov_radio_id: str) -> Radio:
        """Return current metadata for one live Twitch channel."""
        stream = await self.api.get_live_stream(prov_radio_id)
        if stream is None:
            raise MediaNotFoundError(f"Twitch channel {prov_radio_id} is offline")
        return self._parse_stream(stream)

    async def get_stream_details(self, item_id: str, media_type: MediaType) -> StreamDetails:
        """Resolve a Twitch channel to a fresh, non-persisted HLS URL."""
        if media_type is not MediaType.RADIO:
            raise MediaNotFoundError(f"Unsupported Twitch media type: {media_type}")
        if await self.api.get_live_stream(item_id) is None:
            raise MediaNotFoundError(f"Twitch channel {item_id} is offline")
        try:
            stream_url = await asyncio.to_thread(resolve_stream_url, item_id)
        except LookupError as err:
            raise MediaNotFoundError(str(err)) from err
        except RuntimeError as err:
            raise ProviderUnavailableError(str(err)) from err
        return StreamDetails(
            provider=self.domain,
            item_id=item_id,
            audio_format=AudioFormat(content_type=ContentType.AAC),
            media_type=MediaType.RADIO,
            stream_type=StreamType.HTTP,
            path=stream_url,
            can_seek=False,
            allow_seek=False,
        )

    def _parse_stream(self, item: dict[str, Any]) -> Radio:
        """Convert Helix stream metadata into a Music Assistant radio item."""
        login = str(item["user_login"]).lower()
        return self._build_radio(
            login=login,
            name=str(item.get("user_name") or login),
            title=str(item.get("title") or ""),
            game_name=str(item.get("game_name") or ""),
            thumbnail=str(item.get("thumbnail_url") or ""),
            viewer_count=int(item.get("viewer_count") or 0),
        )

    def _parse_search_channel(self, item: dict[str, Any]) -> Radio:
        """Convert a Helix channel-search result into a radio item."""
        login = str(item["broadcaster_login"]).lower()
        return self._build_radio(
            login=login,
            name=str(item.get("display_name") or login),
            title=str(item.get("title") or ""),
            game_name=str(item.get("game_name") or ""),
            thumbnail=str(item.get("thumbnail_url") or ""),
        )

    def _build_radio(
        self,
        *,
        login: str,
        name: str,
        title: str,
        game_name: str,
        thumbnail: str,
        viewer_count: int = 0,
    ) -> Radio:
        """Build a radio item from normalized channel fields."""
        radio = Radio(
            item_id=login,
            provider=self.domain,
            name=name,
            provider_mappings={
                ProviderMapping(
                    item_id=login,
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                    available=True,
                    audio_format=AudioFormat(content_type=ContentType.AAC),
                )
            },
        )
        radio.metadata.description = title or None
        radio.metadata.genres = {game_name} if game_name else set()
        radio.metadata.popularity = viewer_count or None
        radio.metadata.links = {
            MediaItemLink(type=LinkType.WEBSITE, url=f"https://www.twitch.tv/{login}")
        }
        if thumbnail:
            image_url = thumbnail.replace("{width}", "640").replace("{height}", "360")
            radio.metadata.images = UniqueList(
                [
                    MediaItemImage(
                        type=ImageType.THUMB,
                        path=image_url,
                        provider=self.instance_id,
                        remotely_accessible=True,
                    )
                ]
            )
        return radio

    @property
    def account_name(self) -> str:
        """Return the Twitch login connected to this instance."""
        return str(self.get_setup_value(CONF_USER_LOGIN) or "Twitch")
