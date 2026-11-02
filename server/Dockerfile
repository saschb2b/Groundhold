# The Groundhold server's image (server/README.md, Container): the zipapp
# server/build.py makes from server/groundhold_server/ and
# shared/net/protocol.json, on Python's slim image, run as UID 10001. It holds
# no game. Build it from the repository's root:
#
#   docker build -f server/Dockerfile -t groundhold-server .
#   docker run --rm -p 8766:8766 -v groundhold-state:/data groundhold-server
#
# It writes only to /data (the state: identity.key, moderation.json, the
# roster and the daily totals) and, as the backup sidecar, to /backups, so it
# runs on a read-only root filesystem with every capability dropped and a
# small tmpfs on /tmp (deploy/coolify/compose.yaml, deploy/selfhost/).
#
# Reused from Cyberworld Endless's server/Dockerfile (MIT, Sascha Becker):
# two stages and the non-root user; the `sources` stage, the health check and
# the state directory in the environment are new.

# The build context exactly as server/Dockerfile.dockerignore lets it in;
# deploy/check.sh exports this stage and compares it with that allowlist.
FROM scratch AS sources
COPY . /

FROM python:3.13-slim AS build
# (the commit /health names: Coolify and server-image.yml pass it; without it the build names none)
ARG SOURCE_COMMIT=""
COPY --from=sources / /workspace/
WORKDIR /workspace
RUN python3 server/build.py --output /dist/groundhold-server.pyz --commit "$SOURCE_COMMIT"

FROM python:3.13-slim
# (GROUNDHOLD_SERVER_STATE_DIR: every command, --admin and --backup too, finds
# the state at /data; like any GROUNDHOLD_SERVER_ setting it wins over the INI)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GROUNDHOLD_SERVER_STATE_DIR=/data
# (/data and /backups owned by the server's user: an empty named volume
# mounted on one takes this owner and mode)
RUN groupadd --system --gid 10001 groundhold \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin groundhold \
    && mkdir -p /data /backups \
    && chown 10001:10001 /data /backups \
    && chmod 700 /data /backups
COPY --from=build /dist/ /app/
USER 10001:10001
EXPOSE 8766
# (the port GROUNDHOLD_SERVER_PORT names, 8766 by default; the backup sidecar
# serves nothing, and the Compose files give it its own check)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "-c", "import json, os, urllib.request as r; port = os.environ.get('GROUNDHOLD_SERVER_PORT') or '8766'; answer = r.build_opener(r.ProxyHandler({})).open('http://127.0.0.1:' + port + '/health', timeout=4); raise SystemExit(json.load(answer).get('status') != 'ok')"]
ENTRYPOINT ["python3", "/app/groundhold-server.pyz"]
CMD ["--host", "0.0.0.0"]
