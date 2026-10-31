#!/usr/bin/env bash
# The deployment's checks: .github/workflows/server.yml runs them, and so can
# you, from anywhere in the repository, with Docker and Compose 2.24 or newer.
#
# 1. Both Compose files resolve: the Coolify one as Coolify reads it (the
#    repository's root as the project directory), the self-host one with a
#    DOMAIN, and the self-host one refuses to resolve without one.
# 2. The image's build context is exactly server/Dockerfile.dockerignore's
#    allowlist (the Dockerfile's `sources` stage, exported).
# 3. The image builds; /app holds the zipapp and its files alone; it runs as
#    10001.
# 4. Started bare, hardened as the Compose files run it (read-only root,
#    every capability dropped, no new privileges, an 8 MB /tmp), it answers
#    /health, says it runs in a container (and sends no beacon), turns
#    healthy by its own HEALTHCHECK, finds its state for --admin, makes a
#    backup with the state read-only, and stops cleanly on `docker stop`.
# 5. The Coolify stack comes up with both services healthy: server.ini read
#    (the official name and line of welcome), the backup's first archive made,
#    and server/README.md's restore from the server's Terminal works: the
#    archive restored from /backups, the server healthy after its restart with
#    the same identity key.
# 6. The self-host stack's server and backup come up healthy from the image
#    of step 3, and the README's `docker compose exec groundhold` commands
#    work there: --admin list, a restore from /backups and the restart (Caddy
#    needs the domain and ports 80 and 443: with GROUNDHOLD_CHECK_PULL=1, as
#    CI sets it, its Caddyfile is validated by caddy:2 instead).
#
# Health checks run every 2 s here instead of 30 s and 1 min (an override
# file; the commands are the files' own). Every wait is bounded, and every
# container, volume and image made here is removed on the way out.
set -euo pipefail

cd "$(dirname "$0")/.."
run="check$$"
image="groundhold-server-check:$run"
work="$(mktemp -d)"
coolify=(docker compose --project-directory . -f deploy/coolify/compose.yaml -f "$work/coolify.override.yaml"
         -p "groundhold-$run-coolify")
selfhost=(docker compose -f deploy/selfhost/compose.yaml -f "$work/selfhost.override.yaml"
          -p "groundhold-$run-selfhost")

cleanup() {
    set +e
    docker rm -f "$run-bare" >/dev/null 2>&1
    "${coolify[@]}" down -v --rmi local --remove-orphans >/dev/null 2>&1
    DOMAIN=groundhold.example.com CHECK_IMAGE="$image" "${selfhost[@]}" down -v --remove-orphans >/dev/null 2>&1
    docker volume rm -f "$run-state" "$run-backups" >/dev/null 2>&1
    docker image rm -f "$image" >/dev/null 2>&1
    rm -rf "$work"
}
trap cleanup EXIT

fail() {
    echo "deploy/check.sh: $*" >&2
    exit 1
}

step() {
    echo "== $*"
}

# (seconds, then a command: true once it succeeds, false past the deadline)
within() {
    local deadline=$((SECONDS + $1))
    shift
    until "$@" >/dev/null 2>&1; do
        [ "$SECONDS" -lt "$deadline" ] || return 1
        sleep 1
    done
}

# (a name for messages, then a stack's compose command: server/README.md's restore in the server's
# container, as its Terminal or `docker compose exec groundhold` runs it, then a restart; the key the
# same before and after, the server healthy again)
restore_in() {
    local name="$1" key archive
    shift
    local stack=("$@")
    key="$("${stack[@]}" exec -T groundhold python3 -c "print(open('/data/identity.key', 'rb').read().hex())")"
    within 60 "${stack[@]}" exec -T groundhold sh -c 'ls /backups | grep -q groundhold-state-' \
        || fail "$name: no archive in the server's /backups"
    archive="$("${stack[@]}" exec -T groundhold ls /backups | grep -m 1 'groundhold-state-')"
    "${stack[@]}" exec -T groundhold python3 /app/groundhold-server.pyz --restore "/backups/$archive" \
        | python3 -c "import json, sys; assert 'identity.key' in json.load(sys.stdin)['restored']" \
        || fail "$name: the README's restore from /backups/$archive failed"
    "${stack[@]}" restart groundhold >/dev/null 2>&1
    within 60 "${stack[@]}" exec -T groundhold python3 -c "
import json, urllib.request
assert json.load(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=4))['status'] == 'ok'
" || fail "$name: the server did not come back after the restore"
    [ "$("${stack[@]}" exec -T groundhold python3 -c "print(open('/data/identity.key', 'rb').read().hex())")" = "$key" ] \
        || fail "$name: the restore changed the identity key"
}

protocol="$(python3 -c "import json; print(json.load(open('shared/net/protocol.json'))['version'])")"

step "1. The Compose files resolve"
docker compose --project-directory . -f deploy/coolify/compose.yaml config --quiet
DOMAIN=groundhold.example.com docker compose -f deploy/selfhost/compose.yaml config --quiet
if env -u DOMAIN docker compose -f deploy/selfhost/compose.yaml config --quiet >/dev/null 2>&1; then
    fail "deploy/selfhost/compose.yaml resolves without a DOMAIN"
fi

step "2. The build context is the allowlist"
docker build --quiet -f server/Dockerfile --target sources --output "type=local,dest=$work/context" . >/dev/null
(cd "$work/context" && find . -type f | sed 's|^\./||' | LC_ALL=C sort) > "$work/context.txt"
{
    printf '%s\n' LICENSE server/build.py server/README.md server/server.example.ini shared/net/protocol.json
    printf '%s\n' server/groundhold_server/*.py
} | LC_ALL=C sort > "$work/allowlist.txt"
diff -u "$work/allowlist.txt" "$work/context.txt" || fail "the build context differs from the allowlist"

step "3. The image"
docker build --quiet -f server/Dockerfile -t "$image" . >/dev/null
app="$(docker run --rm --entrypoint python3 "$image" -c "import os; print(' '.join(sorted(os.listdir('/app'))))")"
[ "$app" = "LICENSE README.md groundhold-server.pyz server.example.ini" ] || fail "/app holds: $app"
user="$(docker run --rm --entrypoint python3 "$image" -c "import os; print(os.getuid(), os.getgid())")"
[ "$user" = "10001 10001" ] || fail "the image runs as $user"

step "4. A bare, hardened start"
docker volume create "$run-state" >/dev/null
docker volume create "$run-backups" >/dev/null
hardened=(--read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:size=8m,mode=1777)
docker run -d --name "$run-bare" "${hardened[@]}" --health-interval 2s -p 127.0.0.1::8766 \
    -v "$run-state:/data" "$image" >/dev/null
port="$(docker port "$run-bare" 8766/tcp | head -n 1 | sed 's/.*://')"
within 30 curl -fsS "http://127.0.0.1:$port/health" || { docker logs "$run-bare"; fail "no /health within 30 s"; }
curl -fsS "http://127.0.0.1:$port/health" | python3 -c "
import json, sys
health = json.load(sys.stdin)
assert health['status'] == 'ok' and health['protocol'] == $protocol and health['name'] == 'Groundhold', health
"
docker logs "$run-bare" 2>&1 | grep -q 'is open on port 8766' || fail "no banner"
docker logs "$run-bare" 2>&1 | grep -q 'In a container' || fail "the banner does not say it runs in a container"
if docker logs "$run-bare" 2>&1 | grep -q 'beacon is on'; then fail "a container sends the LAN beacon"; fi
healthy() { [ "$(docker inspect -f '{{.State.Health.Status}}' "$1")" = healthy ]; }
within 60 healthy "$run-bare" || fail "the HEALTHCHECK never reported healthy"
docker exec "$run-bare" python3 /app/groundhold-server.pyz --admin list | python3 -c "
import json, sys
assert 'roster' in json.load(sys.stdin)
"
docker run --rm "${hardened[@]}" -v "$run-state:/data:ro" -v "$run-backups:/backups" "$image" \
    --backup /backups --once | grep -q 'groundhold-state-' || fail "no backup with the state read-only"
docker stop -t 10 "$run-bare" >/dev/null
[ "$(docker inspect -f '{{.State.ExitCode}}' "$run-bare")" = 0 ] || fail "docker stop did not end it cleanly"

step "5. The Coolify stack"
cat > "$work/coolify.override.yaml" <<'EOF'
services:
  groundhold:
    healthcheck: {interval: 2s, start_period: 1s}
  backup:
    healthcheck: {interval: 2s, start_period: 1s}
EOF
"${coolify[@]}" up -d --build --quiet-pull --wait --wait-timeout 180 >/dev/null 2>&1 \
    || { "${coolify[@]}" ps; "${coolify[@]}" logs; fail "the Coolify stack did not turn healthy"; }
"${coolify[@]}" exec -T groundhold python3 -c "
import json, urllib.request
health = json.load(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=4))
assert health['name'] == 'Groundhold' and health['motd'].startswith('The official server'), health
"
"${coolify[@]}" exec -T backup python3 -c "
import glob
assert glob.glob('/backups/groundhold-state-*.tar.gz')
"
restore_in "the Coolify stack" "${coolify[@]}"
"${coolify[@]}" down -v --rmi local --remove-orphans >/dev/null 2>&1

step "6. The self-host stack"
cat > "$work/selfhost.override.yaml" <<'EOF'
services:
  groundhold:
    image: ${CHECK_IMAGE}
    pull_policy: never
    build: !reset null
    healthcheck: {interval: 2s, start_period: 1s}
  backup:
    image: ${CHECK_IMAGE}
    pull_policy: never
    build: !reset null
    healthcheck: {interval: 2s, start_period: 1s}
EOF
export DOMAIN=groundhold.example.com CHECK_IMAGE="$image" SERVER_NAME="Check Hold"
"${selfhost[@]}" up -d --wait --wait-timeout 120 groundhold backup >/dev/null 2>&1 \
    || { "${selfhost[@]}" ps; "${selfhost[@]}" logs; fail "the self-host stack did not turn healthy"; }
"${selfhost[@]}" exec -T groundhold python3 -c "
import json, urllib.request
health = json.load(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=4))
assert health['name'] == 'Check Hold', health
"
"${selfhost[@]}" exec -T groundhold python3 /app/groundhold-server.pyz --admin list | python3 -c "
import json, sys
assert 'roster' in json.load(sys.stdin)
" || fail "the self-host: the README's --admin list failed"
restore_in "the self-host" "${selfhost[@]}"
if [ "${GROUNDHOLD_CHECK_PULL:-}" = 1 ] || docker image inspect caddy:2 >/dev/null 2>&1; then
    docker compose -f deploy/selfhost/compose.yaml config --format json \
        | python3 -c "import json, sys; print(json.load(sys.stdin)['configs']['caddyfile']['content'])" \
        > "$work/Caddyfile"
    docker run --rm -v "$work/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 \
        caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
else
    echo "(caddy:2 is not here: its Caddyfile is not validated; GROUNDHOLD_CHECK_PULL=1 pulls it)"
fi

echo "deploy/check.sh: every check passed"
