"""Tests for exposing live followed Twitch channels in the Radio library."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from music_assistant_models.enums import MediaType, ProviderFeature
from music_assistant_models.errors import ProviderUnavailableError

from music_assistant.providers.twitch import SUPPORTED_FEATURES
from music_assistant.providers.twitch.provider import TwitchProvider


def _stream(login: str) -> dict[str, str]:
    return {"user_login": login, "user_name": login.title(), "title": f"{login} live"}


def test_library_radios_feature_is_declared() -> None:
    """Declaring LIBRARY_RADIOS is what puts Twitch channels in the Radio tab."""
    assert ProviderFeature.LIBRARY_RADIOS in SUPPORTED_FEATURES


async def test_library_radios_are_live_followed_channels(provider: TwitchProvider) -> None:
    """The Radio library holds exactly the followed channels that are live now."""
    provider.api.get_followed_streams = AsyncMock(
        return_value=[_stream("monstercat"), _stream("thewillsee")]
    )

    radios = [radio async for radio in provider.get_library_radios()]

    provider.api.get_followed_streams.assert_awaited_once_with("1234")
    assert [radio.item_id for radio in radios] == ["monstercat", "thewillsee"]


async def test_library_radios_raise_instead_of_emptying_on_api_error(
    provider: TwitchProvider,
) -> None:
    """A Twitch outage must fail the sync, not look like every channel went offline."""
    provider.api.get_followed_streams = AsyncMock(side_effect=ProviderUnavailableError("down"))

    with pytest.raises(ProviderUnavailableError):
        _ = [radio async for radio in provider.get_library_radios()]


async def test_watcher_syncs_radios_only_when_live_set_changes(provider: TwitchProvider) -> None:
    """Going live or offline triggers a Twitch-only radio sync; no change does not."""
    provider.mass.music.start_sync = AsyncMock(return_value=[])
    provider.api.get_followed_streams = AsyncMock(
        side_effect=[
            [_stream("monstercat")],
            [_stream("monstercat")],
            [_stream("monstercat"), _stream("thewillsee")],
            [],
        ]
    )

    for _ in range(4):
        await provider._check_followed_live()

    assert provider.mass.music.start_sync.await_count == 3
    provider.mass.music.start_sync.assert_awaited_with(
        media_types=[MediaType.RADIO], providers=[provider.instance_id]
    )


async def test_watcher_survives_api_errors(provider: TwitchProvider) -> None:
    """A failed poll is skipped without syncing and without killing the watcher."""
    provider.mass.music.start_sync = AsyncMock(return_value=[])
    provider.api.get_followed_streams = AsyncMock(side_effect=ProviderUnavailableError("down"))

    await provider._check_followed_live()

    provider.mass.music.start_sync.assert_not_awaited()


async def test_watcher_task_is_cancelled_on_unload(provider: TwitchProvider) -> None:
    """Unloading the provider stops the background poll."""
    provider.mass.create_task = lambda coro: asyncio.get_running_loop().create_task(coro)
    provider.api.get_followed_streams = AsyncMock(return_value=[])
    provider.mass.music.start_sync = AsyncMock(return_value=[])

    await provider.loaded_in_mass()
    task = provider._live_watch_task
    assert task is not None
    await provider.unload()
    await asyncio.sleep(0)

    assert task.cancelled()
