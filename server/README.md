# Groundhold server

The multiplayer server. It never runs a match: every 50 ms it closes a turn and sends every seat the
commands that arrived, each stamped with its sender's seat, and every game simulates the same match
from (seed, rules, turns). It also keeps the hub (parties by code, their countdown and the way back
from a match), the loading barrier, and compares the games' state hashes and results. Python 3.11 or
newer is its only dependency. The design is `docs/design/core-loop.md` §6; the wire contract is
`shared/net/protocol.json`, documented in `shared/net/README.md`.

`wss://groundhold.saschb2b.com/causeway` is the official server, which the game offers first; its
policy is [The official server](#the-official-server). Anyone can run one of their own, and its host
sets its rules.

## Host your own

A server of your own is one small program with nothing to set. It never simulates, so any computer
that runs the game runs it, and a small one serves many parties. Pick how far it should reach.

### On your computer, for players on your network

A LAN party, or friends on the same Wi-Fi. On the
[newest release's page](https://github.com/saschb2b/Groundhold/releases/latest), take the server for
the computer that hosts:

| Archive | Runs on |
|---|---|
| `groundhold-server-windows-x64.zip` | 64-bit Windows 10 or 11 |
| `groundhold-server-macos-arm64.zip`, `groundhold-server-macos-x64.zip` | an Apple silicon or an Intel Mac, macOS 15 or newer |
| `groundhold-server-linux-x64.zip`, `groundhold-server-linux-arm64.zip` | Linux on x86-64 or ARM64 with glibc 2.35 or newer (Ubuntu 22.04, Debian 12, a 64-bit Raspberry Pi OS) |
| `groundhold-server-python.zip` | any computer with Python 3.11 or newer: `python3 groundhold-server.pyz` |

Unpack it anywhere and double-click `groundhold-server` (`groundhold-server.exe` on Windows), or start
it from a terminal in its folder. Nothing else is installed and none of the game is in it. The native
builds are not signed: the first time, macOS refuses one until `xattr -d com.apple.quarantine
groundhold-server` in its folder (or open it, choose Done, then **System Settings › Privacy & Security
› Open Anyway**), and Windows SmartScreen asks for **More info › Run anyway**. Each archive's
`README.txt` says this for its own system. From a checkout of this repository the same server is:

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
once everyone is Ready. `--port 0` lets the system pick a free port, one for IPv4 and IPv6 alike, and
prints it on the first line (godot-agent's topology scenarios match it with
`listening.*port\D*(?P<port>\d+)`). `--host 127.0.0.1`
keeps other computers out. `--event-log FILE` appends one JSON line per event (`listening` with the
port, `join`, `party`, `party_join`, `countdown`, `match`, `start`, `start_without`, `away`, `back`,
`left`, `hold`, `resume`, `desync`, `end`, `hello_timeout`, ...); it contains display names. Requests
refused before they became a game's socket (a wrong path, no WebSocket: scanners, mostly) are summed into
one `refused_requests` line a minute, by reason. The console log on standard
error is the same events without names or identities.

`GET /health` on the same port answers status, protocol, the release's version and the commit it was
built from (`build`; none in a checkout), name, players, running matches, the maintenance line and the
dev match, and nothing else about the build or the host; `GET /stats` the day's totals (below).

The hosting computer's firewall must let TCP port 8766 in; Nearby needs the server's broadcasts to UDP
port 8767 to reach the others (a firewall that drops them only hides it from Nearby, and players can
still type its address). The browser game cannot join a server of your own: the published one joins only
the official server (it has no address field, and a page served over `https://` could not open `ws://` to
your network anyway). Desktop builds of the game for Windows, macOS and Linux are on the same release page
(the repository's README, Play together).

### On your computer, for friends over the internet

Without a server on the internet, a private network between your computers does: with
[Tailscale](https://tailscale.com) or [ZeroTier](https://www.zerotier.com) on every computer, start the
server as above and give your friends its address on that network. The desktop game counts those
addresses (Tailscale's `100.64.0.0/10`, ZeroTier's private ranges) as local and connects over plain
`ws://`, as on a LAN; Nearby does not reach across, so they type the address. The browser game cannot.

### On a server, with a domain

For a server that stays up, which desktop games reach from anywhere over `wss://`: a computer with
Docker (a small VPS does), a domain or subdomain whose DNS record points at it, and ports 80 and 443 open
to the internet. The published browser game joins only the official server, whatever is typed: its Join
panel has no address field, and a party code or a `play/?join=` link goes to the official server
`data/net.json` names. Browser players come to your server through a web build you publish yourself,
with `data/net.json` naming `wss://groundhold.example.com/causeway` and that page's origin in
[`origins`](#origins). From the first release on (its image made public; before it, neither the image nor
the `release` branch exists to pull or build from), in an empty folder on it:

```sh
curl -fsSLO https://raw.githubusercontent.com/saschb2b/Groundhold/main/deploy/selfhost/compose.yaml
echo "DOMAIN=groundhold.example.com" > .env
docker compose up -d
```

Desktop players type `groundhold.example.com` into the Join panel, and
`https://groundhold.example.com/health` says it is up.
[`deploy/selfhost/compose.yaml`](../deploy/selfhost/compose.yaml) starts three containers: the server
from the newest release's image, `ghcr.io/saschb2b/groundhold-server`; its daily backup
([Backups and restores](#backups-and-restores)); and [Caddy](https://caddyserver.com) 2, which gets the
certificate from Let's Encrypt, renews it, and forwards `wss://groundhold.example.com/causeway` to the
server. Caddy keeps no access log. Its own log, capped at three files of 5 MB like the server's, holds
its errors, and an error about a request (a 502 while the server restarts, say) names that request's
address. The other lines `.env` takes, each optional, are in
[`deploy/selfhost/.env.example`](../deploy/selfhost/.env.example):

| Line | What it does |
|---|---|
| `SERVER_NAME=Flats`, `SERVER_MOTD=...` | the server's name and line of welcome, in the Join panel and `/health` |
| `PLAYER_CAP=16` | players at once (64) |
| `VERSION=1.0.0` | that release's image (`1.0`: its newest patch) rather than the newest release's |

`docker compose pull && docker compose up -d` updates it; the state stays in its volume. Compose 2.23.1
or newer is needed (the Caddyfile is inline). Where the image cannot be pulled, Compose builds it from
the repository's `release` branch, which is the newest release (a few minutes, the first time).

The server's tools run in its container, from the same folder: every `--admin` command of
[Identity and moderation](#identity-and-moderation), and a restore from the daily archives, which the
server's container sees read-only at `/backups`:

```sh
docker compose exec groundhold python3 /app/groundhold-server.pyz --admin list
docker compose exec groundhold python3 /app/groundhold-server.pyz --admin ban --identity PUBLIC_ID --reason "Repeated disruption"
docker compose exec groundhold ls /backups
docker compose exec groundhold python3 /app/groundhold-server.pyz --restore /backups/groundhold-state-YYYYMMDD-HHMMSS.tar.gz
docker compose restart groundhold     # (after a restore: the server reads its key as it starts)
```

Without Compose, the image alone serves plain `ws://` on port 8766, for a network of your own:

```sh
docker run -d --name groundhold --restart unless-stopped -p 8766:8766 -v groundhold-state:/data ghcr.io/saschb2b/groundhold-server
```

A web build of your own (its `data/net.json` naming your server) reaches it once its page's origin is
in `origins` ([Origins](#origins)), in `server.ini` or as `GROUNDHOLD_SERVER_ORIGINS`;
`https://saschb2b.github.io`, the published game's page, is the default, though that game joins only the
official server.

### Settings

None are needed. A `server.ini` in the folder the server starts in or beside the program (or
`--config FILE`) changes them; `server.example.ini` lists each with its default. Any key can be set
in the environment instead, which wins: `GROUNDHOLD_SERVER_PORT=9000`. `free_text = true` refuses to
start: there is no chat, only names and in-game signals.

### A dev match (M1)

`--dev-match MODE:SEATS` forms a match from the first `SEATS` games that connect with the same rules
hash, with no hub (the hub's messages are refused), for development and the smoke test:

```text
python3 server/main.py --dev-match classic:2
godot --headless --path . --import        # once, after a clone
godot --path . -- --join=127.0.0.1        # twice, one window per player
```

`--seed N` gives every dev match the same seed. `--turn-ms MS` (dev matches only, 5 to 1000) shortens
the turn: `WELCOME` tells the games, which pace by it, so `--turn-ms 10` plays a match five times
faster (`tools/net/smoke.py --turn-ms 10` finishes a whole classic match in about 80 s). A dev match is
a match of strangers: it starts by itself 45 s after `MATCH_CONFIG` with the seats loaded. Unless
`--state-dir` names one, a dev match keeps its identity key in memory and writes nothing.

## The official server

`wss://groundhold.saschb2b.com/causeway` is the server the game offers first: Join's Official row, a
party code typed alone and a `play/?join=` link all connect there. This is its policy, also published
at <https://saschb2b.github.io/Groundhold/policy.html>. Anyone can run a server of their own
([Host your own](#host-your-own)); its host sets its rules. This page answers what a player may ask
of a service that handles names and connections; it is not legal advice.

### Who runs it

Saschb2b, who makes Groundhold, runs it on a private server, beside the server of
Cyberworld Endless. It is a hobby server with no guarantees: no company behind it, and no promise that
it is up, that it is fast, or that it is still there tomorrow. It restarts at a release, which ends
the matches running on it, and it can go down for a fault or for good without notice. Nothing you
build depends on it: the game plays alone and on your own network without it.

### Moderators

Saschb2b is its moderator. A moderator is whoever is given the server's command line (its
container's terminal); anyone given it later is named here first, by their GitHub name, with the date.

### The rules

- **Names and signals only.** There is no chat and no free text, and the server refuses to start with
  it on. You choose the name the others see: 1 to 16 letters, digits, spaces, `-` and `_`, starting
  with a letter or a digit. In a match the one thing you send the others is a signal, a ring on the
  map that says "look here": at most three in five seconds.
- **Parties are by invitation; strangers only when you look for them.** A party is joined by its code
  or its link, which only those you give it have. Its leader can remove a member, who cannot come back
  with that code. Strangers play with you only when a party's leader looks for them (Find players, Find
  a rival) and every player accepts the match they are offered; for that match they see your name, your
  Builder and your signals. There is no list of strangers to browse.
- **What gets a player muted, kicked or banned:** a name meant to offend, or to pass for Saschb2b or a
  moderator; signals sent to flood a match or to pester someone; a modified game (orders the game
  could not have sent, a state or a result changed on purpose, matches broken on purpose); coming back
  with a new key after a ban. A moderator picks the least that stops it: a mute (your signals reach
  nobody; you still play), a kick (out for ten minutes, or up to 7 days), and last a ban (out until
  lifted).

### Blocking, and no reports

With nothing written but a name, there is little to report. To stop playing with someone, leave the
party or, as its leader, remove them; a new party gets a new code. There is no block list in the game
yet: every party is one you were invited to. The moderator acts only on what they see themselves (a name in the
roster of who is connected) and keeps no log of who came under which name.

### What is kept, and for how long

The server has no accounts. Your game makes a random key on your device (`net.cfg` in the game's data
folder) and sends the server a token made from it for this server's address, never the key itself.
The server turns that token into a public identity with a secret of its own: a number that means
nothing on another server and cannot be turned back into your key. It sees your connection's IP
address, as every server must, and writes it nowhere; the proxy in front of it is set to keep no
access log either.

| What | What it holds | Why | Kept |
| --- | --- | --- | --- |
| The server's secret, `identity.key` | 32 random bytes, nothing of yours | your public identity stays the same across restarts | the server's life |
| The roster, `players.json` | the public identity, name and party code of each player connected | moderators see who is on | while you are connected; emptied when the server stops |
| The players' log, `logs/` | when you came, under which name and public identity | a host who takes reports can match a name with its identity | not kept on the official server (`log_days = 0`) |
| Moderation, `moderation.json` | public identity, when, and the moderator's note, for each ban, mute and kick | the server enforces them | a ban or a mute until lifted, a kick until it ends |
| The server's console log | when the server started, its events without names or public identities: connections by number, parties and matches starting and ending, refusals; no IP addresses | running the server | 3 files of 5 MB, the oldest written over |
| The daily totals, `stats.jsonl` | a line a UTC day: joins, how many different players (a count: the day's public identities are held in memory and dropped at its end), the most online at once, matches started and finished per mode, desyncs, reconnects, resyncs, rejoins, seats the caretaker played, and joins by protocol version; no names, public identities or IPs. Anyone can read today's and the last 30 days' at `/stats` | how many play and when, so the server and the game are sized and tuned for them | 365 days (`stats_days = 365`) |
| Backups | the server's secret and moderation | to bring the server back after a fault | 14 days (`backup_days = 14`) |

Everything else stays in memory and goes when you leave, when the match ends or when the server
restarts: your party and its code, your Builders, Ready and the countdown, a match's turns, its state
hashes and its checkpoints, and a party row held 40 seconds after your link drops. That you came today
is counted for the day's totals, then forgotten at the day's end. The server prunes each record itself,
at its start and every hour. These are the official server's settings
([`deploy/coolify/server.ini`](../deploy/coolify/server.ini); [What the state keeps](#what-the-state-keeps));
another server may keep more or less.

### Removing your data

The server knows you only by your public identity, so it cannot look you up by anything else. Two
ways:

- **Yourself:** delete `net.cfg` from the game's data folder (on Windows
  `%APPDATA%\Godot\app_userdata\Groundhold\`, on macOS
  `~/Library/Application Support/Godot/app_userdata/Groundhold/`, on Linux
  `~/.local/share/godot/app_userdata/Groundhold/`; in the browser, clear the site data of
  `saschb2b.github.io`, which clears every page of that site). Your game makes a new key, so you are a
  new identity on every server. The old one left nothing on the official server's disk but a ban, a
  mute or a kick, if it had one, which stays with it; the backups age out within 14 days.
- **On request:** open an issue on the project's
  [GitHub page](https://github.com/saschb2b/Groundhold/issues/new) titled "Groundhold server: remove my
  data", with the name you play under (never your `net.cfg`). While you are connected the moderator
  finds your public identity in the roster and runs `forget`
  ([Identity and moderation](#identity-and-moderation)), which takes it out of the players' log (there
  is none on the official server) and out of any kick. A ban or a mute stays while it lasts. The
  backups are not edited: they age out within 14 days. While you are not connected the roster does not
  list you, and there is nothing else to find you by.

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
- **The queue** (`groundhold_server/queue.py`, M6; `shared/net/README.md`, The queue): a forming
  party's leader, everyone Ready, queues for strangers. High Water fills the open seats up to four;
  Tide Race finds one rival team of the same size (1 or 2), and Undertow (M7) a rival for a duel, one
  player a side. Parties merge only by mode and rules
  hash, earliest first; Match Found gives everyone 15 s to accept; a decline or the time running out
  sends the decliner's party back to forming and the others to the front of the queue. Strangers on
  one team never share a Builder (the first queued keeps the main, the next takes the backup, then a
  free one is drawn); the two sides of a race or a duel never clash. After 60 s queued the leader may
  start with caretakers in the free seats (High Water: Builders covering what the party lacks; a
  Race: a mirror of the party; a duel: a caretaker of the duellist's own Builder).

## Resilience (M4)

A match (`groundhold_server/match.py`, `catchup.py`; `shared/net/README.md`, Resilience) never
decodes a state, but it keeps two:

- **Hashes**: once every present seat reported a tick, or 2 s after the first report, all equal or a
  strict majority of three or more is agreement. A minority of three or more is resynced; the same
  seat apart again is out of the match (`desynced_twice`), back in the hub, its seat the caretaker's.
  Two seats apart, or no majority, end the match `desynced`.
- **Checkpoints**: an agreed tick a game flagged is asked of one seat in rotation (present, not
  hidden, not catching up, one that flagged that hash). Its parts are kept only if `SHA-256[:8]` of the
  bytes is the agreed hash; the last two are kept; a wrong digest, 5 s without the whole upload, or the
  seat's link gone sends the ask to the next seat.
- **Rejoin**: a dropped seat is held until the match ends. A resume `HELLO` naming it (match id and
  seat) from the same identity takes it back, during maintenance and on a full server too: `ERROR`
  12 to an old link still open, `PARTY_STATE`, `MATCH_CONFIG` with `rejoin`, then `RESYNC(rejoin)`
  from the latest checkpoint, its parts and every turn since. A seat not held hears `NOTICE
  no_held_seat`.
- **Catch-up**: a `RESYNC` and everything behind it go out at most 2 KB per 50 ms of the server's
  clock while the connection's unsent output is under 4 KB; live turns queue behind. A seat catching
  up comes `BACK` only with its `VISIBILITY shown`; one that says `catching_up` from further back than
  the latest checkpoint (a tab back from the background, a seat loaded after a start without it) is
  resynced from there (`RESYNC(behind)`).

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
| `resyncs` | `RESYNC`s sent: a rejoin's, a minority's after a desync, a game's catching up from further back than the latest checkpoint |
| `rejoins` | match seats taken back by a resume `HELLO` naming them |
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

`--backup` makes its folder when there is none yet. `--restore ARCHIVE` checks the archive (regular
files, a 32-byte `identity.key`; nothing else in it is ever extracted), writes its files into the state
directory whole, and removes those it lacks. The server reads the key only as it starts: restart it
after a restore.

In both Compose stacks the archives are the `backup` service's volume, which the `groundhold`
container mounts read-only at `/backups` for a restore, and the image finds its state at `/data` by
itself. In Coolify, **Terminal**, container `groundhold`:

```sh
ls -l /backups
python3 /app/groundhold-server.pyz --restore /backups/groundhold-state-YYYYMMDD-HHMMSS.tar.gz
```

then the app's **Restart**. On a self-host, the same after `docker compose exec groundhold`, then
`docker compose restart groundhold` ([On a server, with a domain](#on-a-server-with-a-domain)).

The archives sit on the same host as the state, so a lost host loses both: copying them off is the
owner's job (design §6.11). From the Compose folder, `docker compose cp backup:/backups ./backups` copies
them out (in Coolify, the same with `docker cp` and the `backup` container's name, or a scheduled backup
of the `groundhold-backups` volume to another machine); then `rsync` or any copy to another machine.

## What exists and what comes

| Milestone | Server work |
|---|---|
| M1 | the WebSocket port, `/health`, `HELLO` and its refusals, rate buckets, the turn clock on absolute deadlines, seat stamping, `--dev-match`, the loading barrier, a hash and result referee (a minority of three is outvoted), `AWAY`/`BACK`/`LEFT`/`TIMEOUT`, `LINKS`, `TURN_REQUEST` |
| M3 | parties with codes, Ready and the countdown, the barrier's timers, results and back to the party, held party rows and the resume bit, the identity key on disk, moderation, retention, `/stats`, backups, the LAN beacon |
| M4 | checkpoints asked, checked and kept, `RESYNC` for a minority desync, a rejoin and a game behind, `desynced_twice`, a match seat's reconnect (`ERROR` 12, `no_held_seat`, through maintenance), paced catch-up, `/stats` resyncs and rejoins |
| M5 (this) | the image and its build context, the Coolify and self-host Compose files, the zipapp's and five native release archives smoke-tested outside the checkout, the release workflows, the deploy on a release tag, the official server's policy |
| M6 | the public queue (open seats and a rival found by mode and rules hash), Match Found and its requeue at the front, Builder clashes between strangers, caretakers offered at 60 s and caretaker seats |
| M7 | the queue serves Undertow's duel: a rival found one player a side, the duel's caretaker of the duellist's own Builder, a duel's `RESULT` judged one outcome a side; no new message, mode or field (`undertow` was in `protocol.json` from M1) |

## Tests

```text
python3 -m unittest discover -s server/tests -t server/tests
```

Each test runs a real server on `127.0.0.1:0` and talks to it over real sockets with a minimal game
client (`tests/support.py`); every timer runs on a clock the test moves by hand, so they are exact and
nothing waits on the wall. A test that waits for something the code never does fails rather than runs
the machine out of memory: the test process may use at most 4 GB (`GROUNDHOLD_TEST_MEMORY_GB`), the
helpers that read until a message comes read at most `MOST_MESSAGES`, and every loop that waits on a
condition stops after a bound and fails. Run new tests against the code before a change inside
`(ulimit -v 4000000; timeout 300 ...)`.

| File | Covers |
|---|---|
| `test_turn_clock.py` | deadlines in integer nanoseconds; no drift over ten minutes of late wake-ups (and that Cyberworld's relative sleep drifts under the same clock); a stalled loop seals the missed turns in a burst; a real server keeps pace with the wall clock |
| `test_turn_stamping.py` | the seat comes from the connection; the open turn lists the command; rotation from `turn mod seats`; system commands first; increasing sequence numbers; command shapes; a full turn carries over |
| `test_dev_match.py` | matches from the first `HELLO`s, pooled by rules hash; the barrier and its 4 s minimum; tick-0 mismatch; hashes agreed or apart; the result referee; a race's and an undertow duel's teams, a duel's outcome one a side; silence, `AWAY` and `BACK`; leaving; the hard cap; the golden transcripts are current and round-trip; the real program on `--port 0` |
| `test_hardening.py` | `WELCOME` and identities; version refusals; `HELLO`'s checks; full and maintenance; malformed frames; path, subprotocol, origin and Godot's native handshake; `/health`; idle sockets; silence; each rate bucket; refusals read before the close; `TURN_REQUEST` bursts; `HASH` flags; the output cap; NUL and BOM strings; the contract's sizes and the README's tables |
| `test_party_codes.py` | 10,000 codes keep to the alphabet; lenient input; a lower-case code joins; unknown codes; rate-limited lookups; an empty party's code expires after 15 minutes |
| `test_party_flow.py` | create and join; Ready, the 3 s countdown and its cancel; what stops it; Builders per member reach the match; a mode change clears Ready; leader handover; removal; four at most; needs to reload; Race teams; open seats and a queue request the party cannot make; limits; no party; a dev server has no hub |
| `test_queue.py` | who may queue and what is refused; the leader's leave; a join, a leave, a drop or open seats off taking a party out, a Builder change keeping it in; open seats a one-team mode's (off on a switch to a race, refused in one); merging open parties up to four, the earliest fill, a party too large waiting; keying on the mode and the rules hash; a race team and its rival of one size, 1v1 and 2v2; Match Found and every accept, a decline and a leave or a drop requeueing the others at the front, the 15 s timeout; Builder clashes between strangers, never in a race; the caretakers offered at 60 s, High Water's covering the party, a race's mirror; a strangers' match and each party its own after it, Play again queueing again; nobody loaded at the ceiling requeueing, the caretakers' offer not told twice; the m6 transcripts; Undertow's duel (M7): a duellist alone queues and two in a party start, two duellists meet one a side with their mains kept, never with a race's ticket, the duel's caretaker of the duellist's Builder, a RESULT of one outcome a side (one outcome alone is out of limits) and Play again queueing again; the m7 transcript |
| `test_barrier.py` | the 4 s minimum (none alone); Slow at 15 s; the leader's start without at 30 s, `AWAY` and `BACK` on the late `LOADED`; a late seat with another hash is out; strangers start at 45 s; the 120 s ceiling (seats out, nobody loaded, strangers dissolved, after a start without); tick-0 apart back to the party naming the seat |
| `test_holds.py` | a dropped row held 40 s; a resume `HELLO` takes it back; a join by code does too; a goodbye frees it; a drop stops the countdown; a row whose match runs waits for the match |
| `test_back_to_party.py` | the results plate, Play again, the party as it was and the next match; a member who left mid-match; a match that never started; the mode kept |
| `test_identity.py` | origins normalised; a token stable per origin, unlinkable across; the public identity stable per server and across a restart, unlinkable across servers; bans, the allowlist and kicks refuse; a ban drops a connected player; a bad moderation file; a mute drops signals |
| `test_beacon.py` | the datagram's layout; a mismatched version is not listed; no beacon in a container, on 127.0.0.1 or behind TLS; a real server once a second of its clock, with its open parties |
| `test_retention.py` | the policy; the pass at the start and hourly; ended kicks go, bans stay; the players' log (none by default); forget; the admin CLI; backups and restores, a backup folder made when there is none; the real program keeping its state, `--admin`, `--backup`, `--restore`; an empty path refused, never a server started |
| `test_stats.py` | every count at `/stats`, with no identity, name or address; desyncs; the day written at its end and at the stop, taken up after a restart; no state, no file; reconnects; resyncs and rejoins |
| `test_hash_referee.py` | all equal or a strict majority of three; the 2 s window; a minority resynced from tick 0; its hashes on their way not compared; apart again is `desynced_twice`; two seats apart and no majority end `desynced` |
| `test_checkpoint_accept.py` | an agreed checkpoint asked of one seat and kept by its digest; another digest, 5 s, or the link gone ask the next; rotation and the last two kept; who may be asked; tick 0 never; the parts' rules (`ERROR` 1 and 6) |
| `test_catchup_budget.py` | the pacer: whole messages, 2 KB a share, a large message alone, never over 4 KB unsent; a rejoin's catch-up on the wire with the live turns behind; a dev match's shorter turns paced alike; nothing while 4 KB wait, and the output cap only after |
| `test_away_back.py` | silence and `AWAY`, the next word `BACK`; `catching_up` holding `BACK` until `shown`; a dropped seat held and resumed from a checkpoint; a seat that left not held; a tab behind resynced once; a seat started without catching up from the latest checkpoint |
| `test_rejoin.py` | two windows of one identity; a rejoin from tick 0; hashes counted again from the checkpoint; a rejoin while loading; a party member's row then its seat; a resume after the end |
| `test_resync.py` | a minority from the latest checkpoint before its last hash, or tick 0; a member apart twice back in the hub |
| `test_versions.py` | older and newer games resuming (2, 17); another rules hash cannot take its seat back; maintenance and a full server let in only a resume for a held seat; a member on another rules hash needs to reload |
| `test_support_bounds.py` | the harness's own bounds: the 4 GB cap, and `until`, `drain` and `sync` failing after `MOST_MESSAGES` rather than reading for ever |
| `test_contract_m4.py` | the M4 contract: numbers appended, the new layouts, the digest and parts, a resume's seat, `VISIBILITY` and `LINKS`, `CatchUp`'s interface, the rejoin naming its seat |
| `test_packaging.py` | the zipapp reproducible and its allowlist alone; a release archive's files in one folder (the smoke refuses one without), its README for each system (the macOS quarantine steps, TCP 8766 and UDP 8767), BUILD.json; the zipapp's archive smoke-tested outside the checkout, a package that needs the checkout failed, a failed smoke leaving no archive; another computer's target refused, the pinned PyInstaller, the hashes; the notices from the build host, a system's Python counting its standard library alone |
| `test_deploy.py` | the Dockerfile's stages, user, port and health check; the ignore file's allowlist enough to build; the health checks run against a real server and real archives (the backup's unhealthy past 26 hours); both Compose files as Compose resolves them (hardening, no host port, the volumes, the read-only `server.ini`, the image, Caddy without an access log, a `DOMAIN` required); the official settings, which the real program starts with; `.env.example` naming every setting; the README's commands for each stack's container; Caddy's error log not said to hold no address; the server's state and archives ignored by git |
| `test_release.py` | the server's workflows' shape (with PyYAML): a server change runs the unit tests, the release tools' tests, the zipapp's archive and `deploy/check.sh`; the native builds are the five targets, the zipapp's archive once, uploaded as `server-<target>`; the image for both architectures, tagged by version, `X.Y` and `latest` only for the newest release, pushed only when told, one push at a time; every action pinned and every local workflow there |
| `test_listen.py` | `--port 0` on every interface (the one test that listens beyond `127.0.0.1`, for a moment) is one port for IPv4 and IPv6 alike, the one printed, and both answer on it; a named host and port kept as given |
| `test_policy.py` | [The official server](#the-official-server) and `web/policy.html` say what `deploy/coolify/server.ini` keeps and for how long, who runs and moderates it, its address and how to be forgotten; the official `motd` names the policy page; the proxy's access log is checked, and the policy's text decided, before the merge that brings the page to `main` |

The release's own steps (`release.yml`: its gate and plan, the desktop zips, the files and their
checksums, the notes, the deploy to Coolify) are `tools/release/`'s, tested with
`python3 -m unittest discover -s tools/release -t tools/release`.

`python3 server/tools/record_transcripts.py` re-records `shared/net/transcripts/` (a deliberate step,
reviewed like any change; `--check` says whether it would change anything).
`python3 server/tools/protocol_tables.py` rewrites the byte tables in `shared/net/README.md` after an
edit to `protocol.json`.

## Build and packages

```text
python3 server/build.py      # build/server/groundhold-server.pyz, then: python3 groundhold-server.pyz
```

The zipapp is deterministic (fixed entry order, times and modes) and holds only `groundhold_server/*.py`,
`protocol.json` and the licence.

### Release archives

A release carries the server six ways, none with any of the game: the five native archives and the
zipapp's, `groundhold-server-<target>.zip` and `groundhold-server-python.zip`
([Host your own](#on-your-computer-for-players-on-your-network) lists what each runs on;
`tools/release/assemble.py`'s `SERVER` is the list a release checks). Each holds one folder,
`groundhold-server-<version>-<target>/` as the game's zips hold theirs, with the program, a short
`README.txt` for its system, `LICENSE`, `server.example.ini` and `BUILD.json` (target, version, Python,
protocol). A native one needs no Python: it is a PyInstaller
one-file build, and its `licenses/` holds the notices of what was frozen into it, written at build time
from the build host's own files (`notices.py`; none are committed): CPython's from the building
interpreter's `LICENSE`, each native library frozen from outside that interpreter's install from its
Debian or Ubuntu package's copyright file or the licence file beside it, and PyInstaller's from its
wheel; `licenses/README.md` says which file covers which library. A frozen library with no licence file
on the build host fails the build.

```sh
python3 server/release.py                 # build/release/groundhold-server-python.zip
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r server/requirements-build.txt
.venv/bin/python server/release.py --native --target linux-x64
```

`--native` builds for the computer it runs on, since PyInstaller does not cross-compile (`--target`
refuses any other), with PyInstaller 6.16.0, which `requirements-build.txt` pins with every dependency
by hash, as Cyberworld Endless does. Every archive is then extracted into a temporary folder outside
the checkout and must pass `smoke.py` there: `--help`; a real process serving `/health` with this
checkout's protocol and `/stats`; a game's upgrade, `HELLO` and `WELCOME`; the game in the roster through
`--admin list`; `--backup --once`; a clean exit on SIGTERM. An archive that fails is deleted. The five
native builds are `.github/workflows/server-native.yml`, each on its own runner with Python 3.13; a
release runs it, and so does the Server workflow run by hand.

**Unsigned builds.** The native builds are not signed. macOS refuses to open one the first time
("Apple could not verify..."): once, in Terminal in its folder, `xattr -d com.apple.quarantine
groundhold-server`; or open it, choose Done, then **System Settings › Privacy & Security › Open
Anyway**. Double-clicked on a Mac it starts in the home folder, so its state is `~/server-data`. On
Windows, SmartScreen may say it protected the PC: **More info › Run anyway**. Each archive's
`README.txt` says this for its own system.

### Container

```sh
docker build -f server/Dockerfile -t groundhold-server .
docker run --rm -p 127.0.0.1:8766:8766 -v groundhold-state:/data groundhold-server
```

[`server/Dockerfile`](Dockerfile) builds the zipapp in one stage and runs it on `python:3.13-slim` as
UID 10001 in the next. Its build context is exactly what `server/Dockerfile.dockerignore` lets in: the
server's modules, `build.py` and the files it copies, `protocol.json` and the licence; a state
directory, a key or the game never enter. The image writes only to `/data` (the state) and, as the
backup sidecar, `/backups`, so it runs on a read-only root filesystem with every capability dropped and
a small tmpfs on `/tmp`. `GROUNDHOLD_SERVER_STATE_DIR=/data` is set in it, so every command finds the
state there (`docker exec groundhold python3 /app/groundhold-server.pyz --admin list`); like any
`GROUNDHOLD_SERVER_` setting it wins over `server.ini`. `-e GROUNDHOLD_SERVER_NAME=...` sets a setting,
and a `server.ini` mounted read-only at `/app/server.ini` is read by itself. Its `HEALTHCHECK` asks
`/health` every 30 s on the port `GROUNDHOLD_SERVER_PORT` names (8766). A state directory bind-mounted
from the host must belong to UID 10001. In a container the server sends no LAN beacon, and its banner
says players reach it at the host's address or at a proxy's domain.

Each release publishes the image for x86-64 and ARM64 as `ghcr.io/saschb2b/groundhold-server`, tagged
`1.2.3`, and `1.2` and `latest` while it is the newest release of its 1.2 and of all, asked of the
repository's tags before the build, one release's push at a time, so a later job asks once the earlier
one's tags are out (`.github/workflows/server-image.yml`, which `release.yml` calls once the release's
desktop exports and native archives have passed; a dry run builds both and pushes neither). The
package is private when first pushed: its settings on GitHub make it public, once
([At a release](#at-a-release)).

`bash deploy/check.sh` checks the deployment end to end with Docker and Compose 2.24 or newer: both
Compose files resolve; the build context is the allowlist; the image runs as 10001 and, started bare and
hardened, answers `/health`, turns healthy by its own check, takes `--admin` and a backup and stops
cleanly; the Coolify stack comes up with both services healthy, `server.ini` read and a first archive
made; the self-host server and backup come up healthy; in each stack the restore from `/backups` this
page gives (and, on the self-host, `--admin list`) works and the server comes back with its key; and,
where `caddy:2` is pulled (`GROUNDHOLD_CHECK_PULL=1`), Caddy validates the Caddyfile. It removes
everything it made. The Server workflow (`.github/workflows/server.yml`) runs it, the unit tests on
Python 3.11 and the zipapp's archive on every change to `server/`, `shared/net/` or `deploy/`.

### Origins

`origins` in `server.ini` is the allowlist of browser pages (the game's web build). Only a request
that carries an `Origin` header is checked against it. Godot 4.7.1's native WebSocket client sends
none: its upgrade is exactly `Host`, `Upgrade`, `Connection`, `Sec-WebSocket-Key`,
`Sec-WebSocket-Version` and `Sec-WebSocket-Protocol: groundhold.v1` (recorded for design §6.2;
`test_godot_native_handshake_is_accepted_with_origins_set` replays it). So desktop games are never
refused by the allowlist, and the allowlist is no player authentication.

## Coolify deployment

The official server, `wss://groundhold.saschb2b.com/causeway` (and
`https://groundhold.saschb2b.com/health`), is a second app in the Coolify project that runs Cyberworld
Endless's server, on the same host: Coolify's proxy gives it the certificate and forwards the
WebSocket upgrade, and nothing new is needed but a DNS record. Its files are in
[`deploy/coolify/`](../deploy/coolify): `compose.yaml` and the official `server.ini`. The app
(design §6.11):

| Setting | Value |
|---|---|
| Project and app | the existing project that runs Cyberworld's `cyberworld-net-square`; a new app, `groundhold-server` |
| Source | this repository, **Branch** `release` (the newest release; [Deploy on a release tag](#deploy-on-a-release-tag)) |
| Build | **Build Pack** Docker Compose; **Base Directory** `/`; **Docker Compose Location** `/deploy/coolify/compose.yaml`; **Preserve repository during deployment** on |
| Domain | `https://groundhold.saschb2b.com` to container port 8766 on the `groundhold` service; no host port published |
| Services | `groundhold` and `backup`, both from one image, UID 10001, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`, an 8 MB tmpfs `/tmp`, json-file logs capped |
| Health | `GET /health` every 30 s; the backup turns unhealthy when its newest archive is older than 26 h |
| Players connect to | `wss://groundhold.saschb2b.com/causeway`, the game's default (`data/net.json`) |

Set up once:

1. **DNS**: a record for `groundhold.saschb2b.com` pointing at the Coolify host, before the
   certificate is asked for.
2. **+ New › Application** from this repository (through the GitHub App, or as a public repository),
   **Branch** `release`, **Build Pack** Docker Compose, **Base Directory** `/`, **Docker Compose
   Location** `/deploy/coolify/compose.yaml`. Coolify passes the Base Directory as Compose's project
   directory, so the build context `.` and the bind source `./deploy/coolify/server.ini` are the
   repository's root and that file. Until the first release has made the `release` branch, use
   `main` for a first deployment and switch to `release` after it.
3. **Preserve repository during deployment** on, so the read-only `server.ini` stays on the host;
   raw compose deployment and custom build or start commands off.
4. The `groundhold` service: the domain `https://groundhold.saschb2b.com` on container port 8766 (in
   Coolify's domain field, `https://groundhold.saschb2b.com:8766`: the port is the container's; players
   still come in on 443). The `backup` service: no domain. Publish no host port.
5. **Auto Deploy** off if the repository has the Coolify secrets below, else on (it then deploys each
   move of `release`).
6. **The proxy's access log off.** The server writes no IP address anywhere, and the policy says so;
   Coolify's proxy sees every connection first. **Servers ›** the Coolify host **› Proxy**: Traefik's
   configuration must have no `--accesslog` line (or, with Caddy as Coolify's proxy, no `log`
   directive for the domain). If it has one, it writes every visitor's address: remove it and restart
   the proxy, which Cyberworld's server shares. Then `docker logs` of the proxy container after a game
   connected names no address of the game's.

The Compose file has two services from one image, each as UID 10001 on a read-only root filesystem
with every capability dropped, no new privileges and an 8 MB tmpfs `/tmp`:

- `groundhold`, the server: its state in the volume `groundhold-state` at `/data`, the backups
  read-only at `/backups` for a restore from its terminal, `server.ini` read-only at `/app/server.ini`.
  Docker restarts it when it exits (`unless-stopped`); its health check asks `/health` every 30 s and
  calls it unhealthy after three misses, which Coolify shows (its Restart restarts it). Its log keeps
  three files of 5 MB and names no player.
- `backup`, the state's daily archive: the state read-only, its own volume `groundhold-backups` at
  `/backups`, no port, no domain. It starts once the server is healthy; its health check is unhealthy
  once the newest archive is more than 26 hours old; its log keeps two files of 1 MB.

`server.ini` is the official server's: its name and line of welcome, the published game's origin
`https://saschb2b.github.io`, no players' log, archives kept 14 days, the daily totals a year. Locally,
from the repository's root, `docker compose --project-directory . -f deploy/coolify/compose.yaml config`
shows the stack as Coolify reads it, and `bash deploy/check.sh` brings it up and checks it.

### Deploy on a release tag

The app follows the branch `release`, and only a release moves it: once a tag `vX.Y.Z` has built and
published everything (`.github/workflows/release.yml`), its last job force-pushes the tagged commit to
`refs/heads/release` with the workflow's own token (`contents: write`; `tools/release/deploy.py push`).
A tag push moves it only forward: the job first asks the repository for its tags (`--newest-only`), and
when a higher `vX.Y.Z` is there it leaves the branch, and Coolify, alone with a notice. Two tags pushed
close together release in parallel, and the older one's deploy may finish last; it never takes the
official server back. A push to `main` never touches the official server, and the server it runs always
speaks the newest release's protocol. Then, after a move, where the repository has these three secrets,
the job asks Coolify to deploy (`tools/release/deploy.py coolify`):

| Secret | Value |
|---|---|
| `COOLIFY_API_URL` | the Coolify instance's address, `https://coolify.example.com` |
| `COOLIFY_TOKEN` | an API token of that instance (**Keys & Tokens › API tokens**) with the `deploy` permission; Coolify's API must be enabled in its settings |
| `COOLIFY_APP_UUID` | the app's UUID, the last part of its page's address in Coolify |

It sends `GET $COOLIFY_API_URL/api/v1/deploy?uuid=$COOLIFY_APP_UUID&force=false` with `Authorization:
Bearer $COOLIFY_TOKEN` and prints the deployment Coolify queued. The address must be `https://` (plain
`http://` only to this computer), and a redirect is not followed: it would carry the token elsewhere. An
error from Coolify (a wrong token, an unknown app), a host it cannot reach, or an answer that queued
nothing fails the job; some of the secrets without the others fail it too. Without any, the job prints a
notice and succeeds: Coolify's Auto Deploy, or its Deploy button, takes the moved branch from there. Use
the secrets or Auto Deploy, not both, or a release deploys twice. The deploy does not wait for Coolify
to finish: the steps below check it.

GitHub refuses a push that changes `.github/workflows/` between the branch's old and new commit from a
token without the `workflows` permission, which a workflow's own token never has. If the push fails
with "refusing to allow a GitHub App to create or update workflow", add a fine-grained token for this
repository with Contents and Workflows read and write as the secret `RELEASE_BRANCH_TOKEN` (the job
uses it in place of its own) and re-run the job. Whoever can push `release` deploys the official
server: a branch ruleset on `release` (**Settings › Rules › Rulesets**: restrict updates and force
pushes) keeps it to the releases, with what the deploy pushes as (GitHub Actions, or the owner of
`RELEASE_BRANCH_TOKEN`) on its bypass list so the job's force-push still goes through.

The deploy jobs run one at a time (`concurrency: official-server`), and GitHub keeps only one waiting:
with three releases in flight, the third to queue cancels the one waiting before it. When that
cancelled one was the newest, the official server stays on the one before: on the newest tag's run
in **Actions**, re-run its cancelled jobs. The image's job has the same limit (one push at a time): a
tag whose image job was cancelled is re-run the same way, and its deploy follows.

A restart ends the matches running on the server, so the server is restarted at releases alone;
balance changes never need one (the server never simulates). To go back to an older release, run
**Actions › Release › Run workflow** with its tag and dry run off: its files are published again and
`release` moves back to it (a run by hand forces the push, newest or not); or redeploy an earlier
deployment from Coolify's **Deployments**, which leaves the branch where it is.

## At a release

A release is a tag `vX.Y.Z` on `main`. `.github/workflows/release.yml` then runs, in order:

1. **gate**: what the run releases (`tools/release/gate.py plan`), and `gate.py check`: the tag is
   `vX.Y.Z`, `project.godot`'s `config/version` is `X.Y.Z`, and `CHANGELOG.md` has a section
   `## X.Y.Z · YYYY-MM-DD` with text in it; and `gate.py on-main`: the tag is on `main`; or nothing is
   built (a dry run of a tag elsewhere only warns). The release tools' tests; the build
   number of the Pages build of the same commit, which the desktop builds carry.
2. **desktop**: the Linux, Windows and macOS exports, the Linux one booted headless to the hub
   (`desktop_smoke.py`), each packed with its `README-first.txt` (`package.py`); **server-native**:
   the five native archives and the zipapp's (`server-native.yml`), each smoke-tested outside the
   checkout; then **server-image**: the image for both architectures (`server-image.yml`), once
   both have passed, so a tag whose build fails pushes no image either (self-hosts pull `latest`).
3. **publish**: exactly the release's files (`assemble.py`: the three game zips, the six server
   archives) and `SHA256SUMS.txt`, attached to the GitHub release `vX.Y.Z`, whose notes are the
   CHANGELOG's section and the files' table (`gate.py notes`).
4. **deploy**, last: `release` moved to the tag when it is the newest release, and Coolify asked
   ([Deploy on a release tag](#deploy-on-a-release-tag)).

Run by hand (**Actions › Release › Run workflow**) it is a dry run unless dry run is unticked: every
job but the deploy runs as for a tag, the image is built but not pushed, nothing is published, and the
files and notes are kept as the run's `release-dry-run` artifact. With no tag it dry-runs the branch
it is run on at `project.godot`'s version, where a heading still without its date only warns. With an
existing tag and dry run off it releases that tag again.

Before the merge into `main` that brings this milestone (and with it `web/policy.html`, which Pages
publishes at once), once, outside the repository:

1. The proxy's access log checked off ([Coolify deployment](#coolify-deployment), step 6) before the
   policy page goes live: `web/policy.html` says the proxy keeps no access log, and Pages publishes
   it with the first build of `main` that has it, which is that merge, not the first tag.
2. The policy's text decided (design §6.13): who runs and moderates the server, how a player reaches
   the moderator, and whether an imprint is needed. [The official server](#the-official-server) and
   `web/policy.html` say the same (`server/tests/test_policy.py` holds them together).

Before the first release, once (on GitHub and in Coolify):

1. The DNS record and the Coolify app, as in [Coolify deployment](#coolify-deployment), steps 1 to 5:
   a first deployment from `main` shows both containers healthy; then the app's branch is `release`.
2. Either Coolify's Auto Deploy on, or the repository's secrets `COOLIFY_API_URL`, `COOLIFY_TOKEN` and
   `COOLIFY_APP_UUID` set with Auto Deploy off ([Deploy on a release tag](#deploy-on-a-release-tag)).
   `RELEASE_BRANCH_TOKEN` only if the deploy's push is refused; a ruleset on `release` if wanted.
3. After the first release has pushed the image: the repository's **Packages › groundhold-server ›
   Package settings › Change visibility › Public**, so self-hosts can pull it.

Each release:

1. On `main`, in one commit: `project.godot`'s `config/version` is `X.Y.Z`, and `CHANGELOG.md`'s
   section for it is headed `## X.Y.Z · YYYY-MM-DD`, the release's date (the Unreleased heading
   becomes it). `python3 tools/release/gate.py check vX.Y.Z` says they agree. A release being prepared
   is headed `## X.Y.Z · TBD`, and the date goes over `TBD`.
2. The release gate (design §7.6): `godot-agent scenario . --determinism` and the native-against-web
   replay check.
3. A dry run if anything in the release's build changed: **Actions › Release › Run workflow** on
   `main`, no tag, dry run on. Its `release-dry-run` artifact holds every file and the notes.
4. An archive to come back to: Coolify **› Terminal**, container `backup`:
   `python3 /app/groundhold-server.pyz --config /app/server.ini --state-dir /data --backup /backups --once`.
5. `git tag vX.Y.Z && git push origin vX.Y.Z`. The Release workflow builds the server's six archives, its
   image and the desktop games, publishes the GitHub release, then moves `release` and asks Coolify.
6. Coolify's **Deployments** shows the deployment; both containers turn healthy.
7. `curl -s https://groundhold.saschb2b.com/health`: `"status": "ok"`, and `"protocol"` the release's
   (`version` in [`shared/net/protocol.json`](../shared/net/protocol.json)).
8. A browser on the Pages site and a desktop build of the release join one party by code and finish a
   High Water match; `/stats` counts the match and no desync.
9. **Terminal**, container `groundhold`: `python3 /app/groundhold-server.pyz --admin list` names those
   games; a **Restart**, and the same games come back with the same public identities (the key kept).
10. **Terminal**, container `backup`: `ls -l /backups` has today's archive. The `groundhold`
    container's logs name no player, and the proxy's no game's address.
11. A new `## Unreleased` heading on top of `CHANGELOG.md` for what comes next.

A change of the protocol's `version` reaches the browser game with the next Pages build of `main`, and
the official server only with the next tag: in between the published browser game is refused there
("This server is older than the game"). Tag promptly after merging a protocol change, or merge it with
the release's own commit.

Where a step fails, Coolify's **Deployments** has the last good deployment to redeploy, and a
`--restore` of step 4's archive, in the `groundhold` container's **Terminal**, puts the state back
([Backups and restores](#backups-and-restores)): `python3 /app/groundhold-server.pyz --restore
/backups/groundhold-state-YYYYMMDD-HHMMSS.tar.gz`, then **Restart**.

## Privacy

The server writes no IP address anywhere. The console log never names a player. Public identities are
`HMAC-SHA256(key, token)[:16]`: the game's token is derived per server, so identities are stable on
one server and unlinkable across servers. On disk, in the state directory: the key, the moderation
lists, the roster of who is connected now, the daily totals (no names), and the players' log only if
`log_days` asks for one. The official server's policy, what it keeps and for how long, is
[The official server](#the-official-server).

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
| `release.py`, `smoke.py`, `notices.py`, `requirements-build.txt` | the same | adapted: the targets named as the workflows name them, a README per system, the archive itself smoke-tested outside the checkout with a game's handshake, a backup and a clean stop; a system's Python counts its standard library alone |
| `Dockerfile`, `Dockerfile.dockerignore`, `../deploy/` | `server/Dockerfile`, `deploy/` | reused: port 8766, the `sources` stage (the build context), the health check and the state directory in the environment; the backup starts once the server is healthy; `deploy/check.sh` and the deploy on a release tag (`tools/release/deploy.py`) are new |
| `groundhold_server/protocol.py` | `protocol.py` | adapted: the spec from JSON, `ProtocolError`, `hello_version`, the name rule and the maintenance line kept; a codec built from `protocol.json`'s layouts replaces the hand-written `struct`s |
| `groundhold_server/app.py` | `app.py` | adapted: the handshake cap and deadline, refusals, token buckets, silence, output cap, `/health`, `/stats`, the event log, moderation housekeeping, the roster; channels, snapshots, cards, trades and the Arena removed |
| `groundhold_server/match.py` | `arena.py` | adapted: a match formed by the server with seats; the relay became the sequencer; the server compares hashes and results itself. The tick loop's `asyncio.sleep(1 / tick_hz)` was not copied: it drifts |
| `tests/support.py`, `test_hardening.py`, `test_holds.py`, `test_retention.py`, `test_stats.py` | `tests/test_server.py` and the same names | adapted: a real server on port 0 and a minimal client, a clock moved by hand |
| `tests/test_turn_clock.py`, `test_turn_stamping.py`, `test_dev_match.py`, `test_party_*.py`, `test_barrier.py`, `test_back_to_party.py`, `test_identity.py`, `test_beacon.py`, `tools/` | | new |
