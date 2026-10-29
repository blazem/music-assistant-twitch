# Twitch provider for Music Assistant

An experimental Music Assistant music provider that represents live Twitch channels as radio
items. It signs in with Twitch's device-code OAuth flow, lists live channels followed by the
signed-in user, searches live channels, and resolves playback through Streamlink.

## Status

This repository is a live-validated proof of concept targeting Music Assistant **2.10.7** and the
current development provider API. On 24 October 2026, the following gates passed on an isolated
Music Assistant server:

1. Twitch device authorization using a real public Client ID and only `user:read:follows`.
2. Followed-channel browse and live-channel search against Twitch Helix.
3. Streamlink resolution of Twitch's `audio_only` rendition and playback through Music
   Assistant's web player.

The focused test suite, Ruff, formatting, and mypy checks also pass in GitHub Actions. This remains
experimental because Music Assistant does not yet have a supported external-provider loader.

Do not install this into a production Home Assistant Music Assistant App. Music Assistant does not
currently load providers from an external custom-provider directory, so the supported development
path is an isolated container image that layers this provider over the official server image.

## Features

- Least-privilege Twitch OAuth (`user:read:follows` only).
- No Client Secret: device authorization uses a public Twitch Client ID.
- Live followed channels under **Browse → Twitch → Live followed channels**.
- Live followed channels in the **Radio** library tab, re-synced within 3 minutes of a channel
  going live or offline.
- Search of currently live Twitch channels.
- Fresh HLS resolution with Streamlink when playback starts.
- Access and refresh tokens stay in Music Assistant setup data and are never logged or returned in
  media items.

Twitch video is discarded by Music Assistant/ffmpeg. Streamlink prefers an `audio_only` rendition
when Twitch exposes one and otherwise returns the best muxed HLS rendition.

## Twitch Developer Console setup

You must perform this part because Twitch requires the developer account owner to register the
application and complete its anti-bot check.

1. Open the [Twitch Developer Console](https://dev.twitch.tv/console/apps).
2. Choose **Register Your Application**.
3. Give it a unique name, for example `Music Assistant Twitch - <your name>`.
4. Add `https://localhost:3000` as the OAuth redirect URL if the form requires one. The provider's
   device-code flow does not redirect to it, but Twitch's registration form requires a URL.
5. Choose the closest available application category.
6. Create the application and open **Manage**.
7. Configure it as a **public client** if Twitch shows a client-type setting. Device-code public
   clients do not use a Client Secret.
8. Copy only the **Client ID**. Do not generate, paste, commit, or share a Client Secret.

When the provider setup asks, paste the Client ID. Twitch will then display a device authorization
page asking for only the `user:read:follows` permission.

## Isolated development server

The compose project maps host port `8096` to Music Assistant's internal port `8095`
and stores its data in `./dev-data`, separate from a normal server on `8095`.

```bash
docker compose build
docker compose up -d
```

Open `http://<dev-host>:8096`, add the Twitch provider, and complete the three live gates above.
This proof-of-concept stack uses Docker bridge networking so it cannot collide with a Music
Assistant server already listening on host port `8095`. Multicast player discovery is not a goal
of this isolated provider test; use a dedicated host-network deployment for that later gate.

Stop and remove only this dev stack with:

```bash
docker compose down
```

The `dev-data` directory remains so test configuration can be reused. Never mount a production
Music Assistant `/data` directory into this container.

## Development and tests

The source tree mirrors the upstream provider location. The CI workflow checks out the matching
Music Assistant tag, overlays this provider and its focused tests, and runs those tests in the
upstream environment.

```bash
git clone https://github.com/music-assistant/server.git
cd server
git checkout 2.10.7
cp -a ../music-assistant-twitch/music_assistant/providers/twitch music_assistant/providers/
cp -a ../music-assistant-twitch/tests/providers/twitch tests/providers/
scripts/setup.sh
.venv/bin/pytest tests/providers/twitch
```

## Known limitations

- Only live channels are exposed; VODs and clips are out of scope.
- Twitch ads, availability, geo restrictions, and broadcaster settings remain governed by Twitch.
- Public-client refresh tokens rotate and expire after prolonged inactivity; reconfigure the
  provider when Twitch revokes or expires authorization.
- Streamlink follows Twitch's web playback behavior and can require maintenance when Twitch changes
  its player interfaces.
- External provider loading is not yet a supported Music Assistant feature. The custom image is a
  development vehicle; the preferred community distribution is an upstream Music Assistant PR.

## Security and privacy

- Never open an issue containing access tokens, refresh tokens, Client Secrets, Music Assistant
  diagnostics, or full debug logs without reviewing and redacting them.
- The Client ID is public by Twitch's design, but each installation should use its own registered
  application.
- The provider never persists decoded audio or a resolved HLS URL.

## License

Apache-2.0. See `LICENSE`.

