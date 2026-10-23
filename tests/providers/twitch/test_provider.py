"""Tests for Twitch browse, search, parsing, and playback resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from music_assistant_models.enums import MediaType
from music_assistant_models.errors import MediaNotFoundError

from music_assistant.providers.twitch.provider import TwitchProvider

LIVE_STREAM = {
    "user_login": "monstercat",
    "user_name": "Monstercat",
    "title": "Monstercat Radio",
    "game_name": "Music",
    "thumbnail_url": "https://img.example/{width}x{height}.jpg",
    "viewer_count": 321,
}

SEARCH_CHANNEL = {
    "broadcaster_login": "monstercat",
    "display_name": "Monstercat",
    "title": "Monstercat Radio",
    "game_name": "Music",
    "thumbnail_url": "https://img.example/live.jpg",
    "is_live": True,
}


async def test_browse_root_has_followed_live_folder(provider: TwitchProvider) -> None:
    """The provider root exposes one focused browse entry."""
    result = await provider.browse("twitch://")

    assert len(result) == 1
    assert result[0].item_id == "followed-live"
    assert result[0].path == "twitch://followed-live"
    assert result[0].name == "Live followed channels"


async def test_browse_followed_live_returns_radios(provider: TwitchProvider) -> None:
    """Live followed streams become playable radio items."""
    provider.api.get_followed_streams = AsyncMock(return_value=[LIVE_STREAM])

    result = await provider.browse("twitch://followed-live")

    provider.api.get_followed_streams.assert_awaited_once_with("1234")
    assert len(result) == 1
    radio = result[0]
    assert radio.item_id == "monstercat"
    assert radio.name == "Monstercat"
    assert radio.metadata.description == "Monstercat Radio"
    assert radio.metadata.genres == {"Music"}
    assert radio.metadata.images[0].path == "https://img.example/640x360.jpg"


async def test_search_only_returns_radio_results(provider: TwitchProvider) -> None:
    """Search returns current live channels as radios."""
    provider.api.search_live_channels = AsyncMock(return_value=[SEARCH_CHANNEL])

    result = await provider.search("monster", [MediaType.RADIO], limit=5)

    provider.api.search_live_channels.assert_awaited_once_with("monster", 5)
    assert [item.item_id for item in result.radio] == ["monstercat"]


async def test_stream_details_resolve_fresh_hls_url(provider: TwitchProvider) -> None:
    """Playback checks liveness and resolves Streamlink off the event loop."""
    provider.api.get_live_stream = AsyncMock(return_value=LIVE_STREAM)
    with patch(
        "music_assistant.providers.twitch.provider.resolve_stream_url",
        return_value="https://video.example/live.m3u8",
    ):
        details = await provider.get_stream_details("monstercat", MediaType.RADIO)

    assert details.path == "https://video.example/live.m3u8"
    assert details.can_seek is False
    assert details.allow_seek is False


async def test_stream_details_reject_offline_channel(provider: TwitchProvider) -> None:
    """An offline channel fails cleanly before invoking Streamlink."""
    provider.api.get_live_stream = AsyncMock(return_value=None)

    with pytest.raises(MediaNotFoundError, match="offline"):
        await provider.get_stream_details("offline", MediaType.RADIO)
