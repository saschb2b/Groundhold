"""The Groundhold server: one bounded asyncio WebSocket port for the hub's
connections, the parties and the matches' turn clocks. It never runs a
match: every game simulates it from the turns the server seals (match.py).

What a connection meets, in order: the handshake (websocket.py, at most
pending_cap unfinished, each within handshake_ms), HELLO and its checks
(the version, the shape, the token, the name; maintenance, a ban, the
allowlist, a kick; room), WELCOME with its public identity (identity.py),
then the hub: PARTY, QUEUE and ACCEPT go to the lobby (lobby.py, party.py),
a match's messages to its match. A connection that drops without a
goodbye keeps its party row 40 s (holds.py) and its match seat to the
match's end. Every timer runs on the server's clock (`clock`), so tests
move it by hand.

Adapted from Cyberworld Endless's server/cyberworld_server/app.py (MIT,
Sascha Becker): the pending-handshake cap and deadline, the ERROR-then-close
refusals, the per-connection token buckets, the 15 s silence, the output
cap, the maintenance line, /health and /stats, the moderation housekeeping
(bans and kicks drop sessions within a second, the roster written off the
loop), the retention's pass and the day's totals, the players' log, and
--event-log's JSONL with its `listening` event are its. Channels,
snapshots, cards, trades and the Arena's relay are gone; the tick loop
became one turn clock per match on absolute deadlines, and parties, the
loading barrier and the LAN beacon are new.
"""

import asyncio
import contextlib
import dataclasses
import json
import logging
import math
import secrets
import struct
import time

from . import protocol, retention, websocket
from .beacon import Beacon
from .holds import HOLD_MS, Holds
from .identity import IdentityStore
from .lobby import LOOKUP_BURST, LOOKUP_REFILL, PARTIES_PER_PLAYER, Lobby, Timers
from .match import Match, MonotonicClock
from .protocol import ProtocolError, SPEC
from .stats import Daily

LOG = logging.getLogger("groundhold.server")
MS = 1_000_000
# (messages a seat sends its match; any other from a game outside one is out of order)
MATCH_MESSAGES = ("LOADING", "LOADED", "CMD", "HASH", "RESULT", "LEAVE_MATCH", "TURN_REQUEST", "CHECKPOINT_PART")
# (the hub's: a dev match has no hub, so it refuses them)
HUB_MESSAGES = ("PARTY", "QUEUE", "ACCEPT")


@dataclasses.dataclass(eq=False)
class Player:
    id: int
    name: str
    writer: asyncio.StreamWriter
    identity: bytes
    build_seq: int
    rules_hash: bytes
    web: bool = False
    resume: bool = False        # HELLO's resume bit: a held party row is taken back (holds.py)
    round_trip: int = 0         # its round trip in ms as its PING says it (LINKS, PARTY_STATE)
    hidden: bool = False        # VISIBILITY: a browser tab in the background
    match: object = None
    seat: int = -1
    after_match: bool = False   # its match ended: in-flight match messages are let pass
    refused: bool = False       # sent away (a refusal, a moderator): no party row held
    member: object = None       # its party row (party.Member), None outside a party
    lookups: object = None      # PARTY join's code lookups (lobby.LOOKUP_BURST)
    joined: float = 0           # the wall clock's time it came (a kick made later drops it)


class Bucket:
    """A token bucket: `burst` deep, refilled `refill` a second (§6.5's rate limits)."""

    def __init__(self, burst, refill, now):
        self.burst, self.refill, self.tokens, self.time = burst, refill, float(burst), now

    def take(self, now):
        self.tokens = min(self.burst, self.tokens + (now - self.time) * self.refill)
        self.time = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


def dev_match_spec(text):
    """--dev-match's MODE:SEATS (classic:2): a mode of protocol.json's and a seat count it allows."""
    mode, _, seats = (text or "").partition(":")
    if mode not in SPEC["modes"] or not seats.isdigit():
        raise ValueError("--dev-match is MODE:SEATS, MODE one of " + ", ".join(SPEC["modes"]))
    low, high = SPEC["modes"][mode]["seats"]
    if not low <= int(seats) <= high:
        raise ValueError(f"--dev-match {mode} takes {low} to {high} seats")
    return mode, int(seats)


class Server:
    def __init__(self, name="Groundhold", motd="", origins=(), event_log=None, player_cap=64,
                 pending_cap=SPEC["pending_cap"], handshake_timeout=SPEC["handshake_ms"] / 1000,
                 silence_timeout=SPEC["silence_ms"] / 1000, maintenance="", dev_match=None, seed=None,
                 identity_key=None, clock=None, start_delay_ms=SPEC["start_delay_ms"],
                 loading_min_ms=SPEC["loading_min_ms"], match_cap_ms=SPEC["match_cap_ms"],
                 output_cap=SPEC["output_cap"], observer=None, turn_ms=SPEC["turn_ms"],
                 state_dir=None, policy=None, allowlist=(), hold_ms=HOLD_MS, wall=time.time, code_rng=None,
                 lan=False, beacon=None, housekeeping_ms=1000, party_cap=None):
        if not 1 <= player_cap <= 4096:
            raise ValueError("player_cap must be 1..4096")
        # (parties at once, empty ones waiting on their code included: four
        # per player by default, so the hub's state stays bounded, lobby.py)
        party_cap = PARTIES_PER_PLAYER * player_cap if party_cap is None else party_cap
        if not 1 <= party_cap <= 65536:
            raise ValueError("party_cap must be 1..65536")
        if seed is not None and not 0 <= seed <= 0xffffffff:
            raise ValueError("seed must be uint32")
        self.name = protocol.printable(name, SPEC["server_name_bytes"])
        self.motd = protocol.printable(motd, SPEC["motd_bytes"])
        self.origins, self.event_log = tuple(origins), event_log
        self.player_cap = player_cap
        self.party_cap = party_cap
        self.pending_cap, self.handshake_timeout, self.silence_timeout = pending_cap, handshake_timeout, silence_timeout
        self.maintenance = protocol.maintenance_line(maintenance)
        self.dev_match = dev_match_spec(dev_match) if isinstance(dev_match, str) else dev_match
        # (a shorter turn plays a dev match faster: games pace by WELCOME's
        # turn_ms, so a smoke run can finish a whole match in a minute)
        if turn_ms != SPEC["turn_ms"] and not self.dev_match:
            raise ValueError("turn_ms differs from the protocol's only in a dev match")
        if not 5 <= turn_ms <= 1000:
            raise ValueError("turn_ms must be 5..1000")
        self.turn_ms = turn_ms
        self.seed = seed
        self.clock = clock or MonotonicClock()
        self.wall = wall
        # (a public identity is HMAC-SHA256(key, token)[:16]: stable on this
        # server, unlinkable across servers; the key is kept in state_dir,
        # in memory without one: identity.py)
        self.store = IdentityStore(state_dir, identity_key)
        self.retention = policy or retention.Retention()
        self.players_log = retention.PlayersLog(state_dir, self.retention.log_days)
        self.players_log_failed = False
        self.daily = Daily(state_dir, self.retention.stats_days, wall)
        self.allowlist = frozenset(allowlist)
        self.match_options = dict(start_delay_ms=start_delay_ms, loading_min_ms=loading_min_ms,
                                  match_cap_ms=match_cap_ms, output_cap=output_cap, observer=observer,
                                  turn_ms=turn_ms)
        self.output_cap = output_cap
        self.code_rng, self.lan = code_rng, lan
        self.timers = Timers(self.clock)
        self.holds = Holds(self, hold_ms)
        self.lobby = Lobby(self)
        self.beacon_target = beacon
        self.beacon = None
        self.housekeeping_ms = housekeeping_ms
        self.housekeeper = None
        self.roster_written = None
        self.roster_task = None
        self.roster_failed = False
        self.retention_time = None      # the last pass, the server clock's ns
        self.retention_task = None
        self.daily_task = None
        self.players = {}
        self.matches = {}
        self.waiting = {}           # rules_hash -> players waiting for a dev match, in HELLO order
        self.next_id = 1
        self.next_match = 1
        self.connections = set()
        # (unfinished handshakes have a small cap and a deadline of their own:
        # idle sockets are dropped and never hold a player's place)
        self.pending = set()
        self.listener = None

    def event(self, kind, **fields):
        """An event in the console's log (never a name or an identity); one
        that names a player goes whole to the players' log (log_days) and
        to --event-log's JSONL."""
        entry = dict(event=kind, **fields)
        LOG.info("%s", retention.console(entry))
        if retention.personal(entry):
            try:
                self.players_log.write(entry, self.wall())
                self.players_log_failed = False
            except OSError as exc:
                if not self.players_log_failed:
                    LOG.error("Could not write the players' log: %s", exc)
                self.players_log_failed = True
        if self.event_log:
            self.event_log.write(json.dumps(dict(time=time.time(), **entry)) + "\n")
            self.event_log.flush()

    async def start(self, host, port, ssl=None):
        self.listener = await asyncio.start_server(self.handle, host, port, ssl=ssl, limit=8192)
        port = self.listener.sockets[0].getsockname()[1]
        self.event("listening", host=host or "*", port=port, path=SPEC["path"], protocol=SPEC["version"],
                   dev_match=self.dev_match_text())
        self.housekeeper = asyncio.create_task(self.housekeeping(self.clock.now()))
        if self.beacon_target:
            self.beacon = Beacon(self, port, None if self.beacon_target is True else self.beacon_target)
            await self.beacon.start()
        return port

    async def close(self):
        if self.listener:
            self.listener.close()
        for task in (self.housekeeper,):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if self.beacon:
            await self.beacon.close()
        for match in list(self.matches.values()):
            match.close()
        tasks = list(self.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.lobby.close()
        await self.timers.close()
        for task in (self.roster_task, self.retention_task, self.daily_task):
            if task:
                await asyncio.gather(task, return_exceptions=True)
        # (the day so far written as the server stops)
        await self.write_day(self.daily.snapshot())
        try:
            self.store.roster([])
        except (OSError, ValueError) as exc:
            LOG.error("Could not clear the local player roster: %s", exc)
        if self.listener:
            await self.listener.wait_closed()

    def dev_match_text(self):
        return f"{self.dev_match[0]}:{self.dev_match[1]}" if self.dev_match else None

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        player = None
        upgraded = False
        goodbye = False
        refused = False
        if len(self.pending) >= self.pending_cap:
            writer.close()
            return
        self.connections.add(task)
        self.pending.add(task)
        try:
            try:
                async with asyncio.timeout(self.handshake_timeout):
                    if not await websocket.upgrade(reader, writer, self.origins, self.health(), stats=self.daily.public):
                        return
                    upgraded = True
                    opcode, data = await websocket.receive(reader)
            finally:
                self.pending.discard(task)
            if opcode != 2:
                raise ProtocolError("Expected binary HELLO")
            version = protocol.hello_version(data)
            if version is not None:
                self.daily.hello(version)
            player = self.join(writer, protocol.read_hello(data))
            await self.welcome(player)
            if self.dev_match:
                self.dev_join(player)
            elif player.resume:
                self.lobby.resume(player)
            goodbye = await self.serve_player(reader, player)
        except ProtocolError as exc:
            if player:
                player.refused = True
            self.event("reject", reason=str(exc), code=exc.code)
            with contextlib.suppress(ConnectionError, asyncio.TimeoutError):
                if upgraded:
                    await websocket.send(writer, protocol.error(exc))
                    refused = True
                else:
                    writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                    await asyncio.wait_for(writer.drain(), 2)
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        except asyncio.CancelledError:
            goodbye = True
            raise
        finally:
            try:
                if player:
                    self.gone(player, goodbye)
                if refused:
                    # (a refused connection that lingers counts as unfinished:
                    # pending_cap bounds how many linger at once)
                    self.pending.add(task)
                    await self.linger(reader, writer)
            finally:
                # (a shutdown's cancel during the linger still closes and forgets it)
                self.pending.discard(task)
                writer.close()
                try:
                    with contextlib.suppress(ConnectionError, asyncio.TimeoutError):
                        await asyncio.wait_for(writer.wait_closed(), 2)
                finally:
                    self.connections.discard(task)

    async def linger(self, reader, writer):
        """After ERROR: the game reads it before the connection goes. A close
        frame right behind it, or a reset because the game's own messages
        were still arriving unread, can take ERROR away unread (Godot drops
        what it buffered when its socket fails), and the player would see
        only "The connection closed". So the server reads and discards what
        the game still sends until it closes (a game closes on ERROR), then
        sends its close frame (1008) and closes. Bounded, since a refused
        connection has no buckets any more: at most linger_ms, and at most
        a hub bucket's burst of frames (more than a game has on its way
        when it is refused), dropped unread rather than unmasked."""
        frames = SPEC["buckets"]["hub"]["burst"]
        with contextlib.suppress(ConnectionError, asyncio.TimeoutError, asyncio.IncompleteReadError, ProtocolError):
            async with asyncio.timeout(SPEC["linger_ms"] / 1000):
                while frames > 0 and await websocket.discard(reader) != 8:
                    frames -= 1
        with contextlib.suppress(ConnectionError, asyncio.TimeoutError, RuntimeError):
            await websocket.send(writer, struct.pack("!H", 1008), 8)

    def join(self, writer, hello):
        if self.maintenance:
            raise ProtocolError(self.maintenance, protocol.ERRORS["maintenance"])
        identity = self.store.identity(hello["token"])
        self.store.refresh()
        if self.store.contains("bans", identity):
            raise ProtocolError("This profile is banned", protocol.ERRORS["banned"])
        if self.allowlist and identity.hex() not in self.allowlist:
            raise ProtocolError("This server uses an allowlist", protocol.ERRORS["allowlist"])
        now = self.wall()
        kick = self.store.kick(identity, now)
        if kick:
            minutes = max(1, math.ceil((kick.get("expires", now) - now) / 60))
            raise ProtocolError(f"Kicked by a moderator; try again in {minutes} min", protocol.ERRORS["kicked"])
        if len(self.players) >= self.player_cap:
            raise ProtocolError("The server is full", protocol.ERRORS["full"])
        # (one profile may come in twice: two windows on one computer share
        # their user:// key; "replaced" (12) comes with M4's reconnect)
        flags = SPEC["hello_flags"]
        player = Player(self.next_id, hello["name"], writer, identity, hello["build_seq"], hello["rules_hash"],
                        web=bool(hello["flags"] & flags["web"]), resume=bool(hello["flags"] & flags["resume"]),
                        lookups=Bucket(LOOKUP_BURST, LOOKUP_REFILL, self.clock.now() / 1e9), joined=now)
        self.next_id = self.next_id % 0xffffffff + 1
        self.players[player.id] = player
        self.daily.join(identity, len(self.players))
        self.event("join", id=player.id, identity=identity.hex(), name=player.name, build_seq=player.build_seq,
                   rules_hash=player.rules_hash.hex(), web=player.web, players=len(self.players))
        return player

    async def welcome(self, player):
        flags = SPEC["welcome_flags"]["dev_match"] if self.dev_match else 0
        await websocket.send(player.writer, protocol.encode(
            "WELCOME", session=player.id, identity=player.identity, turn_ms=self.turn_ms,
            turn_ticks=SPEC["turn_ticks"], hash_every=SPEC["hash_every"], flags=flags,
            server_name=self.name, motd=self.motd))

    def dev_join(self, player):
        """--dev-match: the first HELLOs with one rules hash form a match
        once there are as many as its seats; another hash waits for its own."""
        mode, seats = self.dev_match
        pool = self.waiting.setdefault(player.rules_hash, [])
        pool.append(player)
        if len(pool) < seats:
            return
        chosen = pool[:seats]
        del pool[:seats]
        if not pool:
            del self.waiting[player.rules_hash]
        self.form_match(mode, player.rules_hash, chosen)

    def form_match(self, mode, rules_hash, players, seats=None, party=None):
        """A match of `players` (a party's, or a dev match's), configured at once."""
        assert not any(player.match for player in players), "a player already in a match"
        match_id = self.next_match
        self.next_match = self.next_match % 0xffffffff + 1
        seed = self.seed if self.seed is not None else secrets.randbits(32)
        match = Match(self, match_id, mode, seed, rules_hash, players, self.clock, seats=seats, party=party,
                      **self.match_options)
        self.matches[match_id] = match
        match.begin()
        return match

    def ended(self, match):
        self.matches.pop(match.id, None)
        self.lobby.ended(match)

    def gone(self, player, goodbye):
        """A connection ended: out of the dev pool, its seat left or held,
        its party row freed or held (holds.py)."""
        if self.players.get(player.id) is player:
            del self.players[player.id]
        pool = self.waiting.get(player.rules_hash)
        if pool and player in pool:
            pool.remove(player)
            if not pool:
                del self.waiting[player.rules_hash]
        if player.match:
            player.match.disconnected(player, goodbye)
        self.lobby.gone(player, goodbye)
        self.event("leave", id=player.id, players=len(self.players))

    def muted(self, player):
        return self.store.contains("mutes", player.identity)

    def send(self, player, data):
        """A message to a connection without waiting on it; one whose unsent
        output passed the cap is dropped (its party row is held)."""
        writer = player.writer
        if writer.is_closing():
            return
        writer.write(websocket.frame(data))
        transport = writer.transport
        if transport is not None and transport.get_write_buffer_size() > self.output_cap:
            self.event("slow_reader", id=player.id)
            writer.close()

    def drop(self, player, exc):
        """A moderator's word: ERROR said, then the connection closed; no row held."""
        player.refused = True
        if not player.writer.is_closing():
            player.writer.write(websocket.frame(protocol.error(exc)))
            player.writer.write(websocket.frame(struct.pack("!H", 1008), 8))
        player.writer.close()

    async def serve_player(self, reader, player):
        """A joined game's messages until it says goodbye (True) or its
        connection ends; a bad one raises ProtocolError. The buckets refill on
        the server's clock, so a test's ManualClock holds them still."""
        now = self.clock.now() / 1e9
        buckets = {name: Bucket(spec["burst"], spec["refill"], now) for name, spec in SPEC["buckets"].items()}
        while True:
            opcode, data = await asyncio.wait_for(websocket.receive(reader), self.silence_timeout)
            now = self.clock.now() / 1e9
            message = protocol.BY_ID.get(data[0]) if opcode == 2 and data else None
            if not buckets[(message and message.bucket) or "hub"].take(now):
                raise ProtocolError("Message rate exceeded", protocol.ERRORS["rate"])
            if player.match:
                player.match.heard(player)
            if opcode == 8:
                with contextlib.suppress(ConnectionError, asyncio.TimeoutError):
                    await websocket.send(player.writer, struct.pack("!H", 1000), 8)
                return True
            if opcode == 9:
                await websocket.send(player.writer, data, 10)
                continue
            if opcode == 10:
                continue
            name, fields = protocol.decode_client(data)
            if name == "BYE":
                with contextlib.suppress(ConnectionError, asyncio.TimeoutError):
                    await websocket.send(player.writer, struct.pack("!H", 1000), 8)
                return True
            await self.message(player, name, fields)

    async def message(self, player, name, fields):
        match = player.match
        if name == "PING":
            player.round_trip = fields["rtt_ms"]
            await websocket.send(player.writer, protocol.encode(
                "PONG", client_ms=fields["client_ms"], turn=match.current_turn() if match else 0))
            self.lobby.heard_ping(player)
        elif name == "VISIBILITY":
            if fields["hidden"] > 1:
                raise ProtocolError("VISIBILITY outside its limits", protocol.ERRORS["out_of_limits"])
            player.hidden = bool(fields["hidden"])
        elif name in MATCH_MESSAGES and match:
            await match.receive(player, name, fields)
        elif name == "LEAVE_MATCH" and player.after_match:
            self.lobby.back(player)     # (Play again, or Hub, from the results: lobby.py)
        elif name in MATCH_MESSAGES and player.after_match:
            pass    # (sent before its MATCH_END arrived: a LOADED that crossed the ceiling too)
        elif name in HUB_MESSAGES and not self.dev_match:
            if name == "PARTY":
                self.lobby.party_op(player, fields)
            elif name == "QUEUE":
                self.lobby.queue(player, fields)
            else:
                self.lobby.accept(player, fields)
        else:
            raise ProtocolError("Unknown or out-of-order message")

    def health(self):
        return {"status": "ok", "protocol": SPEC["version"], "name": self.name, "motd": self.motd,
                "players": len(self.players), "player_cap": self.player_cap, "matches": len(self.matches),
                "maintenance": self.maintenance or None, "dev_match": self.dev_match_text(),
                "turn_ms": self.turn_ms}

    # -- housekeeping: once a second of the server's clock

    async def housekeeping(self, beat):
        clock = self.clock
        while True:
            beat += self.housekeeping_ms * MS
            await clock.sleep_until(beat)
            beat = max(beat, clock.now())
            try:
                self.moderation()
                self.keep(clock.now())
                self.day()
            except Exception:       # (housekeeping never ends the server)
                LOG.exception("Housekeeping failed")

    def moderation(self):
        """moderation.json read again where it changed; a banned or newly
        kicked profile's sessions dropped; the roster written."""
        self.store.refresh()
        now = self.wall()
        for player in list(self.players.values()):
            kick = self.store.kick(player.identity, now)
            if self.store.contains("bans", player.identity):
                self.drop(player, ProtocolError("Removed by a moderator", protocol.ERRORS["banned"]))
            elif kick and kick["time"] >= player.joined:
                minutes = max(1, math.ceil((kick.get("expires", now) - now) / 60))
                self.drop(player, ProtocolError(f"Kicked by a moderator for {minutes} min", protocol.ERRORS["kicked"]))
        self.save_roster()

    def save_roster(self):
        """The local roster, where it changed: in a thread, one write at a time."""
        roster = [{"id": p.id, "identity": p.identity.hex(), "name": p.name,
                   "party": p.member.party.code.decode() if p.member else None} for p in self.players.values()]
        if not self.store.directory or roster == self.roster_written:
            return
        if self.roster_task and not self.roster_task.done():
            return
        self.roster_task = asyncio.create_task(self.write_roster(roster))

    async def write_roster(self, roster):
        try:
            await asyncio.to_thread(self.store.roster, roster)
        except (OSError, ValueError) as exc:
            if not self.roster_failed:
                LOG.error("Could not write the local player roster: %s", exc)
            self.roster_failed = True
            return
        self.roster_written, self.roster_failed = roster, False

    def keep(self, now):
        """The retention's pass (retention.py): within a second of the start,
        then every hour, one at a time, in a thread."""
        if not self.store.directory or (self.retention_task and not self.retention_task.done()):
            return
        if self.retention_time is not None and now - self.retention_time < retention.PASS * 1000 * MS:
            return
        self.retention_time = now
        self.retention_task = asyncio.create_task(self.retain())

    async def retain(self):
        try:
            gone = await asyncio.to_thread(retention.apply, self.store.directory, self.retention, self.wall())
        except (OSError, ValueError) as exc:
            LOG.error("The retention's pass failed: %s", exc)
            return {}
        if gone:
            self.event("retention", **gone)
        return gone

    def day(self):
        """A UTC day ended: its totals written, in a thread, as the next begins."""
        ended = self.daily.rollover()
        if ended:
            self.daily_task = asyncio.create_task(self.write_day(ended))

    async def write_day(self, entry):
        try:
            await asyncio.to_thread(self.daily.write, entry)
        except (OSError, ValueError) as exc:
            LOG.error("Could not write the day's totals: %s", exc)
