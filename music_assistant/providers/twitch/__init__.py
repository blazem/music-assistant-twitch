"""Twitch music provider for Music Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from music_assistant_models.enums import ProviderFeature

from .provider import TwitchProvider

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType


SUPPORTED_FEATURES = {
    ProviderFeature.BROWSE,
    ProviderFeature.SEARCH,
    ProviderFeature.LIBRARY_RADIOS,
}


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize the Twitch provider."""
    return TwitchProvider(mass, manifest, config, SUPPORTED_FEATURES)
