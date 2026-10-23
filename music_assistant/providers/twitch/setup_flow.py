"""Interactive device-code setup flow for the Twitch provider."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType

from music_assistant.models.setup_flow import SetupFlowError

from .constants import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    CONF_USER_ID,
    CONF_USER_LOGIN,
    TWITCH_DEVICE_URL,
    TWITCH_SCOPE,
    TWITCH_TOKEN_URL,
    TWITCH_VALIDATE_URL,
)

if TYPE_CHECKING:
    from music_assistant.models.setup_flow import SetupSession


CLIENT_ID_ENTRY = ConfigEntry(key=CONF_CLIENT_ID, type=ConfigEntryType.STRING, required=True)
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


async def run_setup(session: SetupSession) -> None:
    """Collect a public Client ID, authorize Twitch, and create the provider."""
    setup_data = dict(session.context.setup_data)
    errors: dict[str, str] | None = None
    while True:
        submitted = await session.form(
            [replace(CLIENT_ID_ENTRY, value=str(setup_data.get(CONF_CLIENT_ID) or ""))],
            step_id="client",
            errors=errors,
        )
        client_id = str(submitted.get(CONF_CLIENT_ID) or "").strip()
        try:
            device = await _start_device_flow(session, client_id)
            expires_in = int(device.get("expires_in") or 1800)
            token = await session.external_until(
                _poll_device_flow(
                    session,
                    client_id,
                    str(device["device_code"]),
                    int(device.get("interval") or 5),
                ),
                str(device["verification_uri"]),
                step_id="authorize",
                expires_in=expires_in,
                translation_params=[str(device["user_code"])],
            )
            validation = await _validate_token(session, str(token["access_token"]), client_id)
            setup_data.update(
                {
                    CONF_CLIENT_ID: client_id,
                    CONF_ACCESS_TOKEN: str(token["access_token"]),
                    CONF_REFRESH_TOKEN: str(token["refresh_token"]),
                    CONF_TOKEN_EXPIRES_AT: int(time.time()) + int(token.get("expires_in") or 0),
                    CONF_USER_ID: str(validation["user_id"]),
                    CONF_USER_LOGIN: str(validation.get("login") or ""),
                }
            )
            await session.finish(setup_data)
            return
        except SetupFlowError as err:
            errors = {"base": err.translation_key or "auth_failed"}
        except KeyError, ValueError:
            errors = {"base": "auth_failed"}


async def _start_device_flow(session: SetupSession, client_id: str) -> dict[str, Any]:
    """Request a Twitch device code."""
    async with session.mass.http_session.post(
        TWITCH_DEVICE_URL,
        data={"client_id": client_id, "scopes": TWITCH_SCOPE},
    ) as response:
        payload: dict[str, Any] = await response.json()
        if response.status != 200:
            raise SetupFlowError(
                str(payload.get("message") or "Twitch rejected this Client ID"),
                translation_key="auth_failed",
            )
        return payload


async def _poll_device_flow(
    session: SetupSession, client_id: str, device_code: str, interval: int
) -> dict[str, Any]:
    """Poll Twitch until the user completes device authorization."""
    while True:
        await asyncio.sleep(max(interval, 1))
        async with session.mass.http_session.post(
            TWITCH_TOKEN_URL,
            data={
                "client_id": client_id,
                "scopes": TWITCH_SCOPE,
                "device_code": device_code,
                "grant_type": DEVICE_GRANT_TYPE,
            },
        ) as response:
            payload: dict[str, Any] = await response.json()
            if response.status == 200:
                if not payload.get("access_token") or not payload.get("refresh_token"):
                    raise SetupFlowError("Twitch returned incomplete device credentials")
                return payload
            message = str(payload.get("message") or "")
            if response.status == 400 and message == "authorization_pending":
                continue
            raise SetupFlowError(message or "Twitch authorization failed")


async def _validate_token(
    session: SetupSession, access_token: str, client_id: str
) -> dict[str, Any]:
    """Validate the token, account, client, and least-privilege scope."""
    async with session.mass.http_session.get(
        TWITCH_VALIDATE_URL,
        headers={"Authorization": f"OAuth {access_token}"},
    ) as response:
        payload: dict[str, Any] = await response.json()
        if response.status != 200:
            raise SetupFlowError("Twitch could not validate the new token")
        if str(payload.get("client_id") or "") != client_id:
            raise SetupFlowError("Twitch token Client ID did not match the configured app")
        if TWITCH_SCOPE not in payload.get("scopes", []):
            raise SetupFlowError(f"Twitch did not grant the {TWITCH_SCOPE} scope")
        if not payload.get("user_id"):
            raise SetupFlowError("Twitch token did not identify a user")
        return payload
