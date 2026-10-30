# Groundhold server

The multiplayer server. It never runs a match: every 50 ms it closes a turn and sends every seat the
commands that arrived, each stamped with its sender's seat, and every game simulates the same match
from (seed, rules, turns). It also keeps the hub (parties by code, their countdown and the way back
from a match), the loading barrier, and compares the games' state hashes and results. Python 3.11 or
newer is its only dependency. The design is `docs/design/core-loop.md` §6; the wire contract is
`shared/net/protocol.json`, documented in `shared/net/README.md`.

## On your computer, for players on your network

```text
python3 server/main.py
```

The first line on standard output is for scripts and harnesses, the rest is for people:

```text
listening port=8766 host=* path=/causeway
The Groundhold server "Groundhold" is open on port 8766.
Players type this in Groundhold's Join panel, on this network:
  192.168.1.20    (ws://192.168.1.20:8766/causeway)
  127.0.0.1    (a game on this computer)
...
The LAN beacon is on: games on this network list it under Nearby (UDP port 8767).
Settings: the defaults (server.ini beside the server changes them).
State: server-data (the identity key and moderation: keep it, never publish it).
```

Games on the same network find it under **Nearby** in the Join panel (the beacon, below) or by its
address. One player creates a party and the others join with its code (`K7Q-4M`); the leader starts
once everyone is Ready. `--port 0` lets the system pick a free port and prints it on the first line
(godot-agent's topology scenarios match it with `listening.*port\D*(?P<port>\d+)`). `--host 127.0.0.1`
keeps other computers out. `--event-log FILE` appends one JSON line per event (`listening` with the
port, `join`, `party`, `party_join`, `countdown`, `match`, `start`, `start_without`, `away`, `back`,
`left`, `hold`, `resume`, `desync`, `end`, ...); it contains display names. The console log on standard
error is the same events without names or identities.

`GET /health` on the same port answers status, protocol, name, players, running matches, the
maintenance line and the dev match; `GET /stats` the day's totals (below).

### A dev match (M1)

`--dev-match MODE:SEATS` forms a match from the first `SEATS` games that connect with the same rules
hash, with no hub (the hub's messages are refused), for development and the smoke test:

```text
python3 server/main.py --dev-match classic:2
godot --path . -- --join=127.0.0.1        # twice, one window per player
```

`--seed N` gives every dev match the same seed. `--turn-ms MS` (dev matches only, 5 to 1000) shortens
the turn: `WELCOME` tells the games, which pace by it, so `--turn-ms 10` plays a match five times
faster (`tools/net/smoke.py --turn-ms 10` finishes a whole classic match in about 80 s). A dev match is
a match of strangers: it starts by itself 45 s after `MATCH_CONFIG` with the seats loaded. Unless
`--state-dir` names one, a dev match keeps its identity key in memory and writes nothing.

### Settings

None are needed. A `server.ini` in the folder the server starts in or beside the program (or
`--config FILE`) changes them; `server.example.ini` lists each with its default. Any key can be set
in the environment instead, which wins: `GROUNDHOLD_SERVER_PORT=9000`. `free_text = true` refuses to
start: there is no chat, only names and in-game signals.

## The hub

The lobby (`groundhold_server/lobby.py`, `party.py`, `codes.py`, `holds.py`) keeps every party in
memory. Its rules (design §5.2, §6.6; `shared/net/README.md`, The hub, has them message by message):

- **Codes** are five symbols from `23456789BCDFGHJKMNPQRSTVWXYZ`, read leniently (`k7q-4m`). Each
  connection may look up five codes at once and one more every 5 s. A party whose last member left
  keeps its code 15 minutes.
- **The leader** (the creator; then whoever joined earliest) picks the mode, open seats and teams and
  can remove a member, who cannot rejoin that code. Members change their own Builders (main and
  backup) and Ready. A member on another rules hash than the newest build "needs to reload", and the
  party cannot start.
- **Start** with every other member Ready counts 3 s down; anyone can cancel. The match's seats take
  their teams and their members' main Builders from the party.
- **The loading barrier**: at least 4 s; a seat not loaded at 15 s is slow; from 30 s the leader may
  start without it (the caretaker plays its seat until its game loads); at 120 s a seat still not
  loaded is out, and a match with nobody loaded ends.
- **Back to the party**: after a match each player sees the results until Play again (`LEAVE_MATCH`),
  and the party, mode, teams and Builders are as they were, with Ready cleared.
- **A dropped link** keeps its party row 40 s ("reconnecting"); the game's resume `HELLO` takes it
  back. A row whose match still runs is kept until 40 s after the match.

There is no public queue yet: `QUEUE` is answered idle and Match Found never comes (M6).

## The LAN beacon

Unless it runs in a container, behind TLS, on `127.0.0.1` alone or with `beacon = false`, the server
broadcasts one small UDP datagram a second to port 8767 of its network (`beacon.py`; the layout is in
`shared/net/README.md`): `GHB1`, the protocol version, its WebSocket port, how many parties have open
seats, and its name. Desktop games list the servers they hear under Nearby, those of their own
protocol version only. Nothing in it names a player. A firewall that blocks outgoing broadcasts only
hides the server from Nearby; players can still type its address.

## Identity and moderation

Games keep a random private key on the device and derive a separate token for each server address;
the key is never sent. The server makes the public identity `HMAC-SHA256(identity.key, token)[:16]`,
so an identity is stable on one server and is no cross-server tracking identifier. `identity.key` and
the moderation lists live in the private state directory (`server-data/` in the folder the server
starts in; `--state-dir` or `state_dir` names another). The key is made once. Keep the directory
across upgrades: losing the key changes every public identity and voids the bans and players' local
block lists. Never publish it.

There is no remote administration endpoint: file access to the state directory is authority. The
roster `players.json` lists the players connected now with their public identities; commands take
effect within a second:

```sh
python3 server/main.py --state-dir server-data --admin list
python3 server/main.py --state-dir server-data --admin ban --identity PUBLIC_ID --reason "Repeated disruption"
python3 server/main.py --state-dir server-data --admin kick --identity PUBLIC_ID --minutes 30
python3 server/main.py --state-dir server-data --admin mute --identity PUBLIC_ID
python3 server/main.py --state-dir server-data --admin forget --identity PUBLIC_ID
python3 server/admin.py unban PUBLIC_ID --state-dir server-data
```

A ban refuses the profile (`ERROR` 10) and drops its sessions until `unban`. A kick drops them and
refuses the profile for ten minutes, or `--minutes` (1 to 10,080), then ends by itself (`unkick` ends
it early). A mute drops the profile's signals: its `SIGNAL` commands never reach the turns, the one
thing a player shows others besides a name. `allowlist` in `server.ini` lists the public identities a
stricter host lets in (`ERROR` 11 for the rest). Profiles stay anonymous: resetting the device key
evades a ban. `forget` answers a player's request to be removed: its public identity out of the
players' log and the kicks; a ban or a mute stays while it lasts.

`moderation.json` is read again when it changes. A hand edit that leaves it unreadable keeps the last
good rules, logged once; a server does not start with one. Every write of the state's files holds the
directory's lock, `moderation.lock`, so the CLI and the running server never meet in a half-written
file.

### What the state keeps

Keys of `server.ini`'s `[server]` section, at these defaults; a pass prunes each thing to them at the
start and every hour (`retention.py`):

| Key | Default | What it bounds |
| --- | --- | --- |
| `log_days` | 0 | `logs/players-YYYY-MM-DD.jsonl`, the players' log of who came under which name, a file a UTC day; 0 writes none |
| `backup_days` | 14 | the archives `--backup` keeps |
| `stats_days` | 365 | `stats.jsonl`, the daily totals, a line a UTC day; 0 writes none |

`identity.key` and the bans and mutes stay until the host or a moderator removes them; kicks go when
they end; `players.json` holds the players connected now and is emptied when the server stops. No
match is written to disk: a match's turns live in memory and go with it. The console's log never
names a player and no IP address is written anywhere.

### The daily totals

Each UTC day the server counts, with no personal data (`stats.py`), and serves at `GET /stats` as
`{"today": {...}, "days": [...]}` (today so far and up to 30 days before it):

| Field | What it counts |
| --- | --- |
| `joins` | sessions that joined |
| `identities` | different public identities among them, a number only: the set is in memory for the day and never written or served (a restart the same day starts it afresh) |
| `peak` | the most players online at once |
| `started`, `finished` | matches begun, and those ended by an agreed result, per mode |
| `desyncs` | disagreements the hash and result referee found (a minority of three, or a match ended desynced): the health gauge of lockstep |
| `reconnects` | party rows taken back after a drop |
| `caretaker_seats` | seats the caretaker played, once a match each |
| `versions` | HELLOs by the protocol version they carry, those refused included (16 apart, the rest as `other`) |

A day is written once, a line of `stats.jsonl`, when the next begins or as the server stops.

## Backups and restores

`--backup DIR` archives the state directory into `DIR` in the first hour of each UTC day that has no
archive yet, as `groundhold-state-YYYYMMDD-HHMMSS.tar.gz` (UTC), deletes the archives older than
`backup_days`, and looks again every hour; a failure is logged and tried again a minute later.
`--once` makes one archive now and exits. An archive holds `identity.key` and `moderation.json`: what
the server needs to come back as it was. It reads the state under its lock, shared, so it never holds
half a moderator's edit.

```sh
python3 server/main.py --state-dir server-data --backup server-backups --once
python3 server/main.py --state-dir server-data --restore server-backups/groundhold-state-20261030-001500.tar.gz
```

`--restore ARCHIVE` checks the archive (regular files, a 32-byte `identity.key`; nothing else in it
is ever extracted), writes its files into the state directory whole, and removes those it lacks. The
server reads the key only as it starts: restart it after a restore.

## What exists and what comes

| Milestone | Server work |
|---|---|
| M1 | the WebSocket port, `/health`, `HELLO` and its refusals, rate buckets, the turn clock on absolute deadlines, seat stamping, `--dev-match`, the loading barrier, a hash and result referee (a minority of three is outvoted), `AWAY`/`BACK`/`LEFT`/`TIMEOUT`, `LINKS`, `TURN_REQUEST` |
| M3 (this) | parties with codes, Ready and the countdown, the barrier's timers, results and back to the party, held party rows and the resume bit, the identity key on disk, moderation, retention, `/stats`, backups, the LAN beacon |
| M4 | checkpoints, `RESYNC` for a minority desync, a match seat's reconnect, paced catch-up, `ERROR` 12 |
| M5 | Dockerfile, Coolify and self-host Compose files, native binaries, the release workflows, the policy page |
| M6 | the public queue, Match Found, caretakers offered |

## Tests

```text
python3 -m unittest discover -s server/tests -t server/tests
```

Each test runs a real server on `127.0.0.1:0` and talks to it over real sockets with a minimal game
client (`tests/support.py`); every timer runs on a clock the test moves by hand, so they are exact and
nothing waits on the wall.

| File | Covers |
|---|---|
| `test_turn_clock.py` | deadlines in integer nanoseconds; no drift over ten minutes of late wake-ups (and that Cyberworld's relative sleep drifts under the same clock); a stalled loop seals the missed turns in a burst; a real server keeps pace with the wall clock |
| `test_turn_stamping.py` | the seat comes from the connection; the open turn lists the command; rotation from `turn mod seats`; system commands first; increasing sequence numbers; command shapes; a full turn carries over |
| `test_dev_match.py` | matches from the first `HELLO`s, pooled by rules hash; the barrier and its 4 s minimum; tick-0 mismatch; hashes agreed or apart; the result referee; silence, `AWAY` and `BACK`; leaving; the hard cap; the golden transcripts are current and round-trip; the real program on `--port 0` |
| `test_hardening.py` | `WELCOME` and identities; version refusals; `HELLO`'s checks; full and maintenance; malformed frames; path, subprotocol, origin and Godot's native handshake; `/health`; idle sockets; silence; each rate bucket; refusals read before the close; `TURN_REQUEST` bursts; `HASH` flags; the output cap; NUL and BOM strings; the contract's sizes and the README's tables |
| `test_party_codes.py` | 10,000 codes keep to the alphabet; lenient input; a lower-case code joins; unknown codes; rate-limited lookups; an empty party's code expires after 15 minutes |
| `test_party_flow.py` | create and join; Ready, the 3 s countdown and its cancel; what stops it; Builders per member reach the match; a mode change clears Ready; leader handover; removal; four at most; needs to reload; Race teams; open seats and the queue answered idle; limits; no party; a dev server has no hub |
| `test_barrier.py` | the 4 s minimum (none alone); Slow at 15 s; the leader's start without at 30 s, `AWAY` and `BACK` on the late `LOADED`; a late seat with another hash is out; strangers start at 45 s; the 120 s ceiling (seats out, nobody loaded, strangers dissolved, after a start without); tick-0 apart back to the party naming the seat |
| `test_holds.py` | a dropped row held 40 s; a resume `HELLO` takes it back; a join by code does too; a goodbye frees it; a drop stops the countdown; a row whose match runs waits for the match |
| `test_back_to_party.py` | the results plate, Play again, the party as it was and the next match; a member who left mid-match; a match that never started; the mode kept |
| `test_identity.py` | origins normalised; a token stable per origin, unlinkable across; the public identity stable per server and across a restart, unlinkable across servers; bans, the allowlist and kicks refuse; a ban drops a connected player; a bad moderation file; a mute drops signals |
| `test_beacon.py` | the datagram's layout; a mismatched version is not listed; no beacon in a container, on 127.0.0.1 or behind TLS; a real server once a second of its clock, with its open parties |
| `test_retention.py` | the policy; the pass at the start and hourly; ended kicks go, bans stay; the players' log (none by default); forget; the admin CLI; backups and restores; the real program keeping its state, `--admin`, `--backup`, `--restore` |
| `test_stats.py` | every count at `/stats`, with no identity, name or address; desyncs; the day written at its end and at the stop, taken up after a restart; no state, no file; reconnects |

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

The server writes no IP address anywhere. The console log never names a player. Public identities are
`HMAC-SHA256(key, token)[:16]`: the game's token is derived per server, so identities are stable on
one server and unlinkable across servers. On disk, in the state directory: the key, the moderation
lists, the roster of who is connected now, the daily totals (no names), and the players' log only if
`log_days` asks for one. The policy page for the official server comes with M5.

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
| `groundhold_server/hosting.py` | `hosting.py` | reused: `GROUNDHOLD_SERVER_` environment, the banner's words, the beacon and state lines |
| `groundhold_server/cli.py` | `cli.py` | reused: INI, TLS, banner, signals, the state directory, `--admin`, `--backup`, `--restore`, the allowlist; new `--dev-match`, the `listening port=N` line and the beacon |
| `groundhold_server/identity.py` | `identity.py` | reused: the salted HMAC identity, `state_lock`, atomic writes, the hot reload, expiring kicks; no Board list; `client_token`, the game's side, from `network_server_identity.c` |
| `groundhold_server/holds.py` | `holds.py` | adapted: a Square's place became a party row, on the server's clock; a row whose match runs waits for it |
| `groundhold_server/retention.py`, `backup.py`, `admin.py` | the same | reused without the trades and the Board; `log_days` 0 by default |
| `groundhold_server/stats.py` | `stats.py` | adapted: the day's line and identities as a count kept; Groundhold's counts |
| `groundhold_server/party.py`, `lobby.py`, `codes.py`, `beacon.py` | `teams.py` (the pattern) | new: parties by code, the countdown, the barrier's timers, back to the party, the LAN beacon |
| `build.py`, `main.py`, `admin.py` | `build.py`, `main.py`, `admin.py` | reused with the renames |
| `groundhold_server/protocol.py` | `protocol.py` | adapted: the spec from JSON, `ProtocolError`, `hello_version`, the name rule and the maintenance line kept; a codec built from `protocol.json`'s layouts replaces the hand-written `struct`s |
| `groundhold_server/app.py` | `app.py` | adapted: the handshake cap and deadline, refusals, token buckets, silence, output cap, `/health`, `/stats`, the event log, moderation housekeeping, the roster; channels, snapshots, cards, trades and the Arena removed |
| `groundhold_server/match.py` | `arena.py` | adapted: a match formed by the server with seats; the relay became the sequencer; the server compares hashes and results itself. The tick loop's `asyncio.sleep(1 / tick_hz)` was not copied: it drifts |
| `tests/support.py`, `test_hardening.py`, `test_holds.py`, `test_retention.py`, `test_stats.py` | `tests/test_server.py` and the same names | adapted: a real server on port 0 and a minimal client, a clock moved by hand |
| `tests/test_turn_clock.py`, `test_turn_stamping.py`, `test_dev_match.py`, `test_party_*.py`, `test_barrier.py`, `test_back_to_party.py`, `test_identity.py`, `test_beacon.py`, `tools/` | | new |
