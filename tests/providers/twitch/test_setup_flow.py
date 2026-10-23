"""Tests for Twitch device-flow token validation."""

from __future__ import annotations

from typing import Self
from unittest.mock import Mock

import pytest

from music_assistant.models.setup_flow import SetupFlowError
from music_assistant.providers.twitch.setup_flow import _validate_token


class FakeResponse:
    """Minimal async response context used by setup-flow tests."""

    def __init__(self, status: int, payload: dict[str, object]) -> None:
        """Initialize a response with a status and JSON payload."""
        self.status = status
        self.payload = payload

    async def __aenter__(self) -> Self:
        """Enter the fake response context."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit the fake response context."""
        return

    async def json(self) -> dict[str, object]:
        """Return the canned JSON payload."""
        return self.payload


async def test_validate_token_accepts_matching_least_privilege_token() -> None:
    """The setup accepts the required user scope and matching public client."""
    session = Mock()
    session.mass.http_session.get.return_value = FakeResponse(
        200,
        {
            "client_id": "public-client-id",
            "user_id": "1234",
            "login": "listener",
            "scopes": ["user:read:follows"],
        },
    )

    result = await _validate_token(session, "access-token", "public-client-id")

    assert result["user_id"] == "1234"


async def test_validate_token_rejects_wrong_client() -> None:
    """A token minted for another application cannot be stored."""
    session = Mock()
    session.mass.http_session.get.return_value = FakeResponse(
        200,
        {
            "client_id": "other-client",
            "user_id": "1234",
            "scopes": ["user:read:follows"],
        },
    )

    with pytest.raises(SetupFlowError, match="did not match"):
        await _validate_token(session, "access-token", "public-client-id")


async def test_validate_token_rejects_missing_scope() -> None:
    """Setup refuses a token without followed-channel permission."""
    session = Mock()
    session.mass.http_session.get.return_value = FakeResponse(
        200,
        {"client_id": "public-client-id", "user_id": "1234", "scopes": []},
    )

    with pytest.raises(SetupFlowError, match=r"missing|did not grant"):
        await _validate_token(session, "access-token", "public-client-id")
