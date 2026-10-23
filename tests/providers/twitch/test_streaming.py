"""Tests for the Streamlink boundary."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from music_assistant.providers.twitch.streaming import resolve_stream_url


def test_resolve_stream_url_prefers_audio_only() -> None:
    """An audio-only rendition avoids unnecessary video transfer when available."""
    audio = Mock(url="https://video.example/audio.m3u8")
    best = Mock(url="https://video.example/best.m3u8")
    with patch("music_assistant.providers.twitch.streaming.Streamlink") as streamlink:
        streamlink.return_value.streams.return_value = {"audio_only": audio, "best": best}
        result = resolve_stream_url("channel")

    assert result == "https://video.example/audio.m3u8"


def test_resolve_stream_url_falls_back_to_best() -> None:
    """Twitch's normal muxed HLS is used when no audio-only rendition exists."""
    best = Mock(url="https://video.example/best.m3u8")
    with patch("music_assistant.providers.twitch.streaming.Streamlink") as streamlink:
        streamlink.return_value.streams.return_value = {"best": best}
        result = resolve_stream_url("channel")

    assert result == "https://video.example/best.m3u8"


def test_resolve_stream_url_rejects_empty_result() -> None:
    """An empty Streamlink result is reported as an offline/unplayable channel."""
    with patch("music_assistant.providers.twitch.streaming.Streamlink") as streamlink:
        streamlink.return_value.streams.return_value = {}
        with pytest.raises(LookupError, match="no playable HLS stream"):
            resolve_stream_url("channel")
