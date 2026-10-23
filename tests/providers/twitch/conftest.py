"""Shared fixtures for Twitch provider tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from music_assistant.providers.twitch import SUPPORTED_FEATURES
from music_assistant.providers.twitch.provider import TwitchProvider


@pytest.fixture
def provider() -> TwitchProvider:
    """Create a Twitch provider with mocked Music Assistant dependencies."""
    mass = Mock()
    mass.get_provider_icon_data.return_value = "data:image/svg+xml;base64,dHdpdGNo"
    manifest = Mock()
    manifest.domain = "twitch"
    config = Mock()
    config.instance_id = "twitch--test123"
    config.name = "Twitch Test"
    config.enabled = True
    values = {
        "log_level": "GLOBAL",
        "client_id": "public-client-id",
        "user_id": "1234",
        "user_login": "listener",
    }
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    provider = TwitchProvider(mass, manifest, config, SUPPORTED_FEATURES)
    provider.get_setup_value = Mock(side_effect=lambda key, default=None: values.get(key, default))
    provider.api = Mock()
    return provider

