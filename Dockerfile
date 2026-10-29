ARG MASS_VERSION=2.10.8
FROM ghcr.io/music-assistant/server:${MASS_VERSION}

COPY music_assistant/providers/twitch /tmp/twitch-provider

RUN SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" \
    && PROVIDER_PATH="${SITE_PACKAGES}/music_assistant/providers/twitch" \
    && test ! -e "${PROVIDER_PATH}" \
    && mkdir -p "${PROVIDER_PATH}" \
    && cp -a /tmp/twitch-provider/. "${PROVIDER_PATH}/" \
    && python -m compileall -q "${PROVIDER_PATH}" \
    && rm -rf /tmp/twitch-provider

LABEL org.opencontainers.image.source="https://github.com/blazem/music-assistant-twitch" \
      org.opencontainers.image.description="Experimental Twitch provider overlay for Music Assistant"
