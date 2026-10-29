# Groundhold server

The multiplayer server. It never runs a match: every 50 ms it closes a turn and sends every seat the
commands that arrived, each stamped with its sender's seat, and every game simulates the same match
from (seed, rules, turns). It also keeps the loading barrier and compares the games' state hashes and
results. Python 3.11 or newer is its only dependency. The design is `docs/design/core-loop.md` §6;
the wire contract is `shared/net/protocol.json`, documented in `shared/net/README.md`.

## Milestone 1: a dev match on one computer

M1 has no hub yet. `--dev-match MODE:SEATS` forms a match from the first `SEATS` games that connect
with the same rules hash:

```text
python3 server/main.py --dev-match classic:2
godot --path . -- --join=127.0.0.1        # twice, one window per player
```

The first line on standard output is for scripts and harnesses, the rest is for people:

```text
listening port=8766 host=* path=/causeway
The Groundhold server "Groundhold" is open on port 8766.
Players type this in Groundhold's Join panel, on this network:
  192.168.1.20    (ws://192.168.1.20:8766/causeway)
  127.0.0.1    (a game on this computer)
...
Dev match: the first 2 players to connect play classic together (start each game with -- --join=ADDRESS).
```

`--port 0` lets the system pick a free port and prints it on that line (godot-agent's topology
scenarios match it with `listening.*port\D*(?P<port>\d+)`). `--event-log FILE` appends one JSON
line per event (`listening` with the port, `join`, `match`, `start`, `away`, `back`, `left`,
`desync`, `end`, ...); it contains display names. The console log on standard error is the same
events without names or identities. `--seed N` gives every dev match the same seed. `--host
127.0.0.1` keeps other computers out. `--turn-ms MS` (dev matches only, 5 to 1000) shortens the
turn: `WELCOME` tells the games, which pace by it, so `--turn-ms 10` plays a match five times
faster (`tools/net/smoke.py --turn-ms 10` finishes a whole classic match in about 80 s).

`GET /health` on the same port answers status, protocol, name, players, running matches, the
maintenance line and the dev match.

### Settings

None are needed. A `server.ini` in the folder the server starts in or beside the program (or
`--config FILE`) changes them; `server.example.ini` lists each with its default. Any key can be set
in the environment instead, which wins: `GROUNDHOLD_SERVER_PORT=9000`. `free_text = true` refuses to
start: there is no chat, only names and in-game signals.

## What exists and what comes

| Milestone | Server work |
|---|---|
| M1 (this) | the WebSocket port, `/health`, `HELLO` and its refusals, rate buckets, the turn clock on absolute deadlines, seat stamping, `--dev-match`, the loading barrier, a hash and result referee (a minority of three is outvoted), `AWAY`/`BACK`/`LEFT`/`TIMEOUT`, `LINKS`, `TURN_REQUEST` |
| M3 | parties with codes, the lobby and its barrier timers, the identity key on disk, moderation, holds, the LAN beacon, retention and `/stats` |
| M4 | checkpoints, `RESYNC` for a minority desync, reconnect with the resume bit, paced catch-up, `ERROR` 12 |
| M5 | Dockerfile, Coolify and self-host Compose files, native binaries, the release workflows, the policy page |

## Tests

```text
python3 -m unittest discover -s server/tests -t server/tests
```

Each test runs a real server on `127.0.0.1:0` and talks to it over real sockets with a minimal game
client (`tests/support.py`); the turns run on a clock the test moves by hand, so they are exact.

| File | Covers |
|---|---|
| `test_turn_clock.py` | deadlines in integer nanoseconds; no drift over ten minutes of late wake-ups (and that Cyberworld's relative sleep drifts under the same clock); a stalled loop seals the missed turns in a burst; a real server keeps pace with the wall clock |
| `test_turn_stamping.py` | the seat comes from the connection; the open turn lists the command; rotation from `turn mod seats`; system commands first; increasing sequence numbers; command shapes; a full turn carries over |
| `test_dev_match.py` | matches from the first `HELLO`s, pooled by rules hash; the barrier and its 4 s minimum; tick-0 mismatch; hashes agreed or apart; the result referee (a lone early `RESULT` against a seat that hashes past it ends "desynced"; a slow seat is waited for while it hashes; a seat that talks but stops hashing holds the end up 10 s at most; a majority of three; one modified or desynced seat of three is outvoted while the others play on; an away seat's result does not count; results bounded like hashes); silence, `AWAY` and `BACK`; leaving; the hard cap; the golden transcripts are current and round-trip; the real program on `--port 0` |
| `test_hardening.py` | `WELCOME` and identities; version refusals through another version's subprotocol; `HELLO`'s token, name and shape; full and maintenance; unmasked, fragmented, text and oversized frames; path, subprotocol and origin, and Godot's native handshake; `/health`; idle sockets; silence; each rate bucket; a refused game reads `ERROR` before the close, and one that keeps sending is read a hub burst at most; a burst of `TURN_REQUEST`s costs one window of turns; `HASH` flags; the output cap; NUL and BOM strings; the contract's sizes, its path and subprotocol, and the README's tables; the `GROUNDHOLD_SERVER_*` environment |

`python3 server/tools/record_transcripts.py` re-records `shared/net/transcripts/` (a deliberate step,
reviewed like any change; `--check` says whether it would change anything).
`python3 server/tools/protocol_tables.py` rewrites the byte tables in `shared/net/README.md` after an
edit to `protocol.json`.

## Build

```text
python3 server/build.py      # build/server/groundhold-server.pyz, then: python3 groundhold-server.pyz
```

The zipapp is deterministic (fixed entry order, times and modes) and holds only `groundhold_server/*.py`,
`protocol.json` and the licence.

### Origins

`origins` in `server.ini` is the allowlist of browser pages (the game's web build). Only a request
that carries an `Origin` header is checked against it. Godot 4.7.1's native WebSocket client sends
none: its upgrade is exactly `Host`, `Upgrade`, `Connection`, `Sec-WebSocket-Key`,
`Sec-WebSocket-Version` and `Sec-WebSocket-Protocol: groundhold.v1` (recorded for design §6.2;
`test_godot_native_handshake_is_accepted_with_origins_set` replays it). So desktop games are never
refused by the allowlist, and the allowlist is no player authentication.

## Privacy

The server writes no IP address anywhere and, in M1, nothing to disk unless `--event-log` is given.
The console log never names a player. Public identities are `HMAC-SHA256(key, token)[:16]`: the
game's token is derived per server, so identities are stable on one server and unlinkable across
servers. In M1 the key lives in memory for the life of the process.

## Provenance

This server is a fork of the presence server of
[Cyberworld Endless](https://github.com/saschb2b/Mega-Man-Battle-Network-Cyberworld-Endless)
(`server/cyberworld_server/`, at commit `3d8d0d54`), copied rather than shared so the two projects
release separately (`docs/design/core-loop.md` §6.10). Both are by Sascha Becker under the MIT
licence (Copyright (c) 2026 Sascha Becker), whose text is this repository's `LICENSE`; each reused
or adapted module says what it took in its docstring.

| Here | From Cyberworld | How |
|---|---|---|
| `groundhold_server/websocket.py` | `websocket.py` | reused: path `/causeway`, subprotocol `groundhold.vN`, `max_message` 1,100; frames over 125 bytes from the server |
| `groundhold_server/hosting.py` | `hosting.py` | reused: `GROUNDHOLD_SERVER_` environment, the banner's words |
| `groundhold_server/cli.py` | `cli.py` | reused: INI, TLS, banner, signals; new `--dev-match` and the `listening port=N` line; no admin or backups yet |
| `build.py`, `main.py` | `build.py`, `main.py` | reused with the renames |
| `groundhold_server/protocol.py` | `protocol.py` | adapted: the spec from JSON, `ProtocolError`, `hello_version`, the name rule and the maintenance line kept; a codec built from `protocol.json`'s layouts replaces the hand-written `struct`s |
| `groundhold_server/app.py` | `app.py` | adapted: the handshake cap and deadline, refusals, token buckets, silence, output cap, `/health`, the event log; channels, snapshots, cards, trades and the Arena removed |
| `groundhold_server/match.py` | `arena.py` | adapted: a match formed by the server with seats; the relay became the sequencer; the server compares hashes and results itself. The tick loop's `asyncio.sleep(1 / tick_hz)` was not copied: it drifts |
| `tests/support.py`, `tests/test_hardening.py` | `tests/test_server.py`, `tests/test_hardening.py` | adapted: a real server on port 0 and a minimal client; moderation cases return with `identity.py` |
| `tests/test_turn_clock.py`, `test_turn_stamping.py`, `test_dev_match.py`, `tools/` | | new |
