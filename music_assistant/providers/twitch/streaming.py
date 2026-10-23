"""Twitch playback resolution through Streamlink."""

from __future__ import annotations

from typing import Any

from streamlink.exceptions import NoPluginError, NoStreamsError, PluginError
from streamlink.session.session import Streamlink


def resolve_stream_url(channel_login: str) -> str:
    """Resolve a live Twitch channel to a fresh HLS URL."""
    session = Streamlink()
    try:
        streams: dict[str, Any] = session.streams(f"https://www.twitch.tv/{channel_login}")
    except (NoPluginError, NoStreamsError) as err:
        raise LookupError(f"Twitch channel {channel_login} is not live") from err
    except PluginError as err:
        raise RuntimeError(f"Streamlink could not resolve {channel_login}: {err}") from err

    # Prefer an audio-only rendition when Twitch exposes one. Otherwise use the best
    # normal rendition; Music Assistant/ffmpeg discards video during audio playback.
    stream = streams.get("audio_only") or streams.get("best")
    stream_url = getattr(stream, "url", None)
    if not stream_url:
        raise LookupError(f"Twitch channel {channel_login} has no playable HLS stream")
    return str(stream_url)
