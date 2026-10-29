"""The Lantern Hollow server: one bounded asyncio WebSocket port for the
hub's connections and the matches' turn clocks. It never runs a match:
every game simulates it from the turns the server seals (match.py).

Adapted from Cyberworld Endless's server/cyberworld_server/app.py (MIT,
Sascha Becker): the pending-handshake cap and deadline, the ERROR-then-close
refusals, the per-connection token buckets, the 15 s silence, the output
cap, the maintenance line, /health and the --event-log JSONL with its
`listening` event are its. Channels, snapshots, cards, trades and the
Arena's relay are gone; the tick loop became one turn clock per match on
absolute deadlines. M1 forms matches with --dev-match only; parties, the
queue, identity.py's persistent key and moderation come in M3.
"""

import asyncio
import contextlib
import dataclasses
import hashlib
import hmac
import json
import logging
import secrets
import struct
import time

from . import protocol, websocket
from .match import Match, MonotonicClock
from .protocol import ProtocolError, SPEC

LOG = logging.getLogger("lantern.server")
# (fields the console's log never shows: they name a player)
PERSONAL = ("identity", "name")
# (messages a seat sends its match; any other from a game outside one is out of order)
MATCH_MESSAGES = ("LOADING", "LOADED", "CMD", "HASH", "RESULT", "LEAVE_MATCH", "TURN_REQUEST", "CHECKPOINT_PART")


@dataclasses.dataclass(eq=False)
class Player:
    id: int
    name: str
    writer: asyncio.StreamWriter
    identity: bytes
    build_seq: int
    rules_hash: bytes
    web: bool = False
    round_trip: int = 0         # its round trip in ms as its PING says it (LINKS)
    hidden: bool = False        # VISIBILITY: a browser tab in the background
    match: object = None
    seat: int = -1
    after_match: bool = False   # its match ended: in-flight match messages are let pass
    refused: bool = False


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
    def __init__(self, name="Lantern Hollow", motd="", origins=(), event_log=None, player_cap=64,
                 pending_cap=SPEC["pending_cap"], handshake_timeout=SPEC["handshake_ms"] / 1000,
                 silence_timeout=SPEC["silence_ms"] / 1000, maintenance="", dev_match=None, seed=None,
                 identity_key=None, clock=None, start_delay_ms=SPEC["start_delay_ms"],
                 loading_min_ms=SPEC["loading_min_ms"], match_cap_ms=SPEC["match_cap_ms"],
                 output_cap=SPEC["output_cap"], observer=None, turn_ms=SPEC["turn_ms"]):
        if not 1 <= player_cap <= 4096:
            raise ValueError("player_cap must be 1..4096")
        if seed is not None and not 0 <= seed <= 0xffffffff:
            raise ValueError("seed must be uint32")
        self.name = protocol.printable(name, SPEC["server_name_bytes"])
        self.motd = protocol.printable(motd, SPEC["motd_bytes"])
        self.origins, self.event_log = tuple(origins), event_log
        self.player_cap = player_cap
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
        # (a public identity is HMAC-SHA256(key, token)[:16]: stable on this
        # server, unlinkable across servers. M1 keeps the key in memory for
        # the process's life; identity.py keeps it on disk from M3.)
        self.identity_key = identity_key or secrets.token_bytes(32)
        self.clock = clock or MonotonicClock()
        self.match_options = dict(start_delay_ms=start_delay_ms, loading_min_ms=loading_min_ms,
                                  match_cap_ms=match_cap_ms, output_cap=output_cap, observer=observer,
                                  turn_ms=turn_ms)
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
        """An event in the console's log (never a name or an identity) and,
        whole, in --event-log's JSONL."""
        entry = dict(event=kind, **fields)
        LOG.info("%s", json.dumps({key: value for key, value in entry.items() if key not in PERSONAL},
                                  separators=(",", ":")))
        if self.event_log:
            self.event_log.write(json.dumps(dict(time=time.time(), **entry)) + "\n")
            self.event_log.flush()

    async def start(self, host, port, ssl=None):
        self.listener = await asyncio.start_server(self.handle, host, port, ssl=ssl, limit=8192)
        port = self.listener.sockets[0].getsockname()[1]
        self.event("listening", host=host or "*", port=port, path=SPEC["path"], protocol=SPEC["version"],
                   dev_match=self.dev_match_text())
        return port

    async def close(self):
        if self.listener:
            self.listener.close()
        for match in list(self.matches.values()):
            match.close()
        tasks = list(self.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
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
                    if not await websocket.upgrade(reader, writer, self.origins, self.health()):
                        return
                    upgraded = True
                    opcode, data = await websocket.receive(reader)
            finally:
                self.pending.discard(task)
            if opcode != 2:
                raise ProtocolError("Expected binary HELLO")
            player = self.join(writer, protocol.read_hello(data))
            await self.welcome(player)
            if self.dev_match:
                self.dev_join(player)
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
        if len(self.players) >= self.player_cap:
            raise ProtocolError("The server is full", protocol.ERRORS["full"])
        identity = hmac.new(self.identity_key, hello["token"], hashlib.sha256).digest()[:SPEC["identity_bytes"]]
        # (M1 lets one profile in twice: two windows on one computer share
        # their user:// key; "replaced" (12) and the resume bit come with M4)
        player = Player(self.next_id, hello["name"], writer, identity, hello["build_seq"], hello["rules_hash"],
                        web=bool(hello["flags"] & SPEC["hello_flags"]["web"]))
        self.next_id = self.next_id % 0xffffffff + 1
        self.players[player.id] = player
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
        match_id = self.next_match
        self.next_match = self.next_match % 0xffffffff + 1
        seed = self.seed if self.seed is not None else secrets.randbits(32)
        match = Match(self, match_id, mode, seed, player.rules_hash, chosen, self.clock, **self.match_options)
        self.matches[match_id] = match
        match.begin()

    def ended(self, match):
        self.matches.pop(match.id, None)

    def gone(self, player, goodbye):
        """A connection ended: out of the dev pool, and its seat left or held."""
        if self.players.get(player.id) is player:
            del self.players[player.id]
        pool = self.waiting.get(player.rules_hash)
        if pool and player in pool:
            pool.remove(player)
            if not pool:
                del self.waiting[player.rules_hash]
        if player.match:
            player.match.disconnected(player, goodbye)
        self.event("leave", id=player.id, players=len(self.players))

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
        elif name == "VISIBILITY":
            if fields["hidden"] > 1:
                raise ProtocolError("VISIBILITY outside its limits", protocol.ERRORS["out_of_limits"])
            player.hidden = bool(fields["hidden"])
        elif name in MATCH_MESSAGES and match:
            await match.receive(player, name, fields)
        elif name in MATCH_MESSAGES and player.after_match and name != "LOADED":
            pass    # (sent before its MATCH_END arrived)
        else:
            raise ProtocolError("Unknown or out-of-order message")

    def health(self):
        return {"status": "ok", "protocol": SPEC["version"], "name": self.name, "motd": self.motd,
                "players": len(self.players), "player_cap": self.player_cap, "matches": len(self.matches),
                "maintenance": self.maintenance or None, "dev_match": self.dev_match_text(),
                "turn_ms": self.turn_ms}
