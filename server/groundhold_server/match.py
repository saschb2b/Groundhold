"""One match on the server: a sequencer, never a simulator.

Every 50 ms the server closes a turn and sends every seat `TURN(k)`: the
commands that reached it while turn k was open, each stamped with its
sender's seat (taken from the connection, so it cannot be forged) and the
sender's sequence number. Every game runs the same integer simulation from
(seed, rules, turns), executing TURN(k) at the start of tick 3k. The server
also keeps the loading barrier, a light hash and result referee, and the
system commands AWAY, BACK, LEFT and TIMEOUT. docs/design/core-loop.md
§6.1, §6.3, §6.5 to §6.7. A party's match (M3) takes its seats' teams and
Builders from the party and tells the lobby as it starts and ends; the
barrier's timers are lobby.py's.

Turns close on **absolute deadlines**: turn k closes at origin + (k + 1) ×
50 ms, in integer nanoseconds of a monotonic clock. A loop that wakes late
closes every turn whose deadline has passed at once, so the turn count
always tracks wall time. Cyberworld's `asyncio.sleep(1 / tick_hz)` tick
loop adds each wake-up's lateness to the next and drifts; it is not copied.

**Resilience (M4; shared/net/README.md, Resilience).** The server never
decodes a state, but it keeps two. Once the seats agree on a hash tick a
game flagged as a checkpoint, one seat in rotation (present, not hidden,
not catching up, and one that reported the agreed hash with the flag, so
it keeps the bytes) is asked to upload it (CHECKPOINT_ASK). The bytes are
kept only if their SHA-256[:8] is the agreed hash, the last
`checkpoints_kept` of them; an upload with another digest, or not whole
`checkpoint_wait_ms` after the ask, goes to the next seat. From the latest
kept (tick 0 when none) a seat is brought to the open turn with RESYNC, the
parts and every turn since, paced by catchup.py:

- a rejoin: a resume HELLO took its held seat back (lobby.py), and the old
  connection, if still open, got ERROR 12;
- a minority desync with three seats or more; the same seat apart again is
  `MATCH_END desynced_twice` for it alone, and LEFT in the turns;
- a game catching up from further back than the latest checkpoint.

While a connection says `catching_up` or `hidden`, only its `shown` brings
its seat BACK, so the simulation hands it back at a build window the game
has seen.

Adapted from the structure of Cyberworld Endless's arena.py (MIT, Sascha
Becker): matches formed by the server, seats, an end that tells everyone;
the relay became this sequencer.
"""

import asyncio
import collections
import dataclasses
import logging
import time

from . import protocol, websocket
from .catchup import CatchUp
from .protocol import ProtocolError, SPEC

LOG = logging.getLogger("groundhold.server")
MS = 1_000_000
TURN_NS = SPEC["turn_ms"] * MS
TURN_TICKS = SPEC["turn_ticks"]
SYSTEM = SPEC["system_commands"]
SIGNAL = SPEC["commands"]["SIGNAL"]["type"]
LOADING, PLAYING, ENDED = "loading", "playing", "ended"
PRESENT, AWAY, LEFT = "present", "away", "left"
AGREED_KEPT = 600       # agreed hashes remembered for late reports: ten minutes of them
CHECKPOINT_FLAG = SPEC["hash_flags"]["checkpoint"]
CATCHUP_NS = SPEC["catchup_ms"] * MS


class MonotonicClock:
    """The server's clock: integer nanoseconds of time.monotonic_ns, the
    clock asyncio's own timers use, and a sleep until a deadline on it."""

    def now(self):
        return time.monotonic_ns()

    async def sleep_until(self, deadline):
        delay = deadline - time.monotonic_ns()
        await asyncio.sleep(max(0, delay) / 1e9)


class TurnClock:
    """Turn k is open from origin + k × turn and closes at origin + (k + 1) ×
    turn, all integers: no float is ever added to another, so nothing drifts."""

    def __init__(self, origin, turn_ns=TURN_NS):
        self.origin, self.turn_ns = origin, turn_ns

    def deadline(self, turn):
        return self.origin + (turn + 1) * self.turn_ns

    def due(self, now):
        """How many turns have closed by `now`: every turn whose deadline has passed."""
        return max(0, (now - self.origin) // self.turn_ns)


class TurnLoop:
    """Wakes at the open turn's deadline and seals every turn whose deadline
    has passed, then sleeps until the next one. `tend(now)` runs first on
    each wake (silences, waits), so what it injects lands in the first turn
    sealed. With `sealing` off (after TIMEOUT) it keeps waking once a turn
    for `tend` but seals nothing."""

    def __init__(self, clock, origin, seal, tend=None, turn_ns=TURN_NS):
        self.clock, self.turns = clock, TurnClock(origin, turn_ns)
        self.seal, self.tend = seal, tend
        self.turn = 0           # the open turn: the next to seal
        self.sealing = True
        self.running = True

    async def run(self):
        wake = 0
        while self.running:
            await self.clock.sleep_until(self.turns.deadline(wake))
            now = self.clock.now()
            due = self.turns.due(now)
            if self.tend:
                self.tend(now)
            while self.running and self.sealing and self.turn < due:
                self.seal(self.turn, now)
                self.turn += 1
            wake = max(wake, due)


class Sequencer:
    """The commands of the open turn, and their order when it is sealed:
    system commands first, in the order the server made them; then the
    seats in rotation from seat `turn mod seats`, so nobody always wins a
    contested cell; each seat's by its sequence number."""

    def __init__(self, seats):
        self.seats = seats
        self.pending = []           # (seat, seq, type, a, b, c), as they came
        self.system = []
        self.last_seq = [-1] * seats
        self.system_seq = 0

    def command(self, seat, seq, kind, a, b, c):
        self.skip(seat, seq)
        self.pending.append((seat, seq, kind, a, b, c))

    def skip(self, seat, seq):
        """A command's sequence number taken without listing it (a muted signal)."""
        if seq <= self.last_seq[seat]:
            raise ProtocolError("Command sequence numbers must increase")
        self.last_seq[seat] = seq

    def inject(self, name, seat=0):
        """A system command (seat 255), its seq the match's own count."""
        self.system_seq = self.system_seq % 0xffff + 1
        self.system.append((protocol.SYSTEM_SEAT, self.system_seq, SYSTEM[name]["type"], seat, 0, 0))

    def seal(self, turn):
        """The turn's commands in order, at most max_turn_commands (more wait
        for the next turn, in their order)."""
        first = turn % self.seats
        ordered = self.system + sorted(self.pending, key=lambda entry: ((entry[0] - first) % self.seats, entry[1]))
        most = SPEC["max_turn_commands"]
        taken, rest = ordered[:most], ordered[most:]
        self.system = [entry for entry in rest if entry[0] == protocol.SYSTEM_SEAT]
        self.pending = [entry for entry in rest if entry[0] != protocol.SYSTEM_SEAT]
        return taken


@dataclasses.dataclass(eq=False)
class Seat:
    index: int
    team: int
    builder: int
    flags: int
    name: str
    player: object = None           # the connection playing it; None while dropped
    state: str = PRESENT            # PRESENT, AWAY (the caretaker plays it) or LEFT
    heard: int = 0                  # clock ns of its connection's last message
    per_mille: int = 0
    load_state: int = protocol.LOAD_STATES["connecting"]
    loaded: tuple = None            # LOADED's (rules_hash, tick-0 hash)
    hash_tick: int = -1             # its last HASH's tick
    hashed: int = 0                 # clock ns of its last HASH (of turn 0's opening before its first)
    result: tuple = None            # RESULT's (tick, hash, outcomes)
    resent: int = None              # clock ns of its last TURN_REQUEST answered
    cared: bool = False             # the caretaker has played it this match (/stats counts it once)
    identity: bytes = None          # the public identity that holds it: a rejoin must be the same
    member: object = None           # its party row (party.Member) as the match formed; None in a dev match
    catchup: object = None          # a CatchUp while RESYNC and the turns behind it go out (catchup.py)
    cursor: int = 0                 # ... and the next turn to queue behind them
    restart: int = None             # the last RESYNC's checkpoint tick: a HASH from there may go back once
    muted: bool = False             # RESYNC(desync) sent: its HASHes are the parted simulation's until it goes back
    resyncs: int = 0                # RESYNC(desync)s this match (max_resyncs; apart once more: desynced_twice)
    behind_from: int = 0            # the checkpoint tick of its last RESYNC(behind): never the same one twice
    asked: set = dataclasses.field(default_factory=set)     # checkpoint ticks asked of it (CHECKPOINT_PART)


@dataclasses.dataclass(eq=False)
class Upload:
    """A checkpoint the server waits for: its tick, the agreed hash its bytes
    must have, the seats that flagged it with that hash (they keep it), the
    seats asked so far, the one asked now and when, and its parts so far."""
    tick: int
    digest: bytes
    keepers: tuple
    tried: set = dataclasses.field(default_factory=set)
    seat: int = -1
    asked_at: int = 0
    parts: int = 0
    chunks: list = dataclasses.field(default_factory=list)


class Match:
    """A match the server formed (a party's, or `--dev-match`'s), from MATCH_CONFIG to MATCH_END."""

    def __init__(self, server, match_id, mode, seed, rules_hash, players, clock,
                 start_delay_ms=SPEC["start_delay_ms"], loading_min_ms=SPEC["loading_min_ms"],
                 match_cap_ms=SPEC["match_cap_ms"], output_cap=SPEC["output_cap"], observer=None,
                 turn_ms=SPEC["turn_ms"], seats=None, party=None):
        from .lobby import Barrier     # (lobby.py forms matches: imported here, not at the top)
        self.server, self.id, self.mode, self.seed, self.rules_hash = server, match_id, mode, seed, rules_hash
        self.spec = SPEC["modes"][mode]
        self.clock = clock
        self.start_delay_ms, self.loading_min_ms, self.output_cap = start_delay_ms, loading_min_ms, output_cap
        # (turn_ms differs from the protocol's only in a dev match: --turn-ms)
        self.turn_ns = turn_ms * MS
        self.cap_turn = match_cap_ms // turn_ms
        self.observer = observer        # (tests: each sealed turn as (turn, now, entries))
        teams, count = self.spec["teams"], len(players)
        # (a party gives each seat its team and its member's main Builder;
        # a dev match puts half the seats on each team, every seat a Lamplighter)
        seats = seats or [dict(team=index * teams // count, builder=SPEC["builders"]["lamplighter"], flags=0)
                          for index in range(count)]
        self.seats = [Seat(index, spec["team"], spec["builder"], spec["flags"], player.name, player,
                           identity=player.identity, member=player.member)
                      for index, (spec, player) in enumerate(zip(seats, players))]
        self.party = party
        for seat in self.seats:
            seat.player.match, seat.player.seat, seat.player.after_match = self, seat.index, False
        self.sequencer = Sequencer(count)
        self.phase = LOADING
        self.loop = None
        self.task = None
        self.ready = asyncio.Event()
        self.configured = 0
        self.log = {}                   # turn -> TURN bytes, the turns with commands (TURN_REQUEST, RESYNC)
        self.hashes = {}                # tick -> [first report's clock ns, {seat: hash}, {seats that flagged it}]
        self.agreed = collections.OrderedDict()
        self.forgotten = -1             # the latest agreed tick let go (AGREED_KEPT): too old to judge
        self.checkpoints = []           # (tick, bytes, digest), the last checkpoints_kept kept, oldest first
        self.upload = None              # the checkpoint being asked for (Upload)
        self.next_ask = 0               # the seat the rotation asks first next time
        self.config_seats = []          # MATCH_CONFIG's seats as the match began (a rejoin gets them again)
        self.timed_out = None
        self.next_links = 0
        self.next_feed = 0              # the next catchup_ms boundary a catch-up's share goes out at (feed)
        self.tick0 = None               # the tick-0 hash the seats agreed at the start
        self.finishers = []             # the connections MATCH_END went to
        self.barrier = Barrier(self, strangers=party is None)

    # -- what the server and its connections call

    def begin(self):
        """MATCH_CONFIG to every seat, then the barrier and the turns, in a task."""
        now = self.clock.now()
        self.configured = now
        self.config_seats = [dict(seat=s.index, team=s.team, builder=s.builder, flags=s.flags, name=s.name)
                             for s in self.seats]
        for seat in self.seats:
            seat.heard = now
            self.write(seat, self.config(seat, 0))
        self.broadcast(self.load_state())
        self.task = asyncio.create_task(self.run())
        self.server.event("match", match=self.id, mode=self.mode, seats=len(self.seats), seed=self.seed)

    def config(self, seat, flags):
        """MATCH_CONFIG for `seat`, the match as it began."""
        return protocol.encode("MATCH_CONFIG", match=self.id, mode=self.spec["id"], map=SPEC["maps"]["hollow"],
                               seed=self.seed, rules_hash=self.rules_hash, your_seat=seat.index,
                               seats=self.config_seats, flags=flags)

    def current_turn(self):
        """The open turn, as PONG says it (0 before turn 0 opens)."""
        return self.loop.turn if self.loop else 0

    def heard(self, player, back=True):
        """Any message from a seat's connection: its silence ends, and a seat
        the caretaker took is handed BACK (the simulation gives it control at
        the next build window), unless its connection's last VISIBILITY says
        it is catching up or hidden: then only `shown` does. A tab back from
        the background may send a PING or a TURN_REQUEST before it says
        catching_up or shown; neither brings the seat back before its game
        has seen the turns. (`back` is False for the VISIBILITY that says
        catching_up or hidden, which must not bring it back on its way in.)"""
        seat = self.seats[player.seat]
        if seat.player is not player:
            return
        seat.heard = self.clock.now()
        # (a seat started without its player comes BACK with its LOADED, not
        # with the LOADING and PINGs it sends while it still loads)
        if (back and not player.catching_up and not player.hidden and seat.state == AWAY and self.phase == PLAYING
                and self.loop.sealing and seat.loaded is not None):
            seat.state = PRESENT
            self.sequencer.inject("BACK", seat.index)
            self.server.event("back", match=self.id, seat=seat.index)

    def visibility(self, player, state):
        """VISIBILITY, its flags already on the connection (app.py): `shown`
        hands a seat its catching up held BACK; `catching_up` resyncs it
        from the latest checkpoint where that is further on."""
        seat = self.seats[player.seat]
        if seat.player is not player:
            return
        if state == protocol.VISIBILITY["shown"]:
            self.heard(player)
        elif state == protocol.VISIBILITY["catching_up"]:
            self.behind(seat)

    async def receive(self, player, name, fields):
        seat = self.seats[player.seat]
        if seat.player is not player:
            raise ProtocolError("Unknown or out-of-order message")
        if name == "LOADING":
            if fields["per_mille"] > 1000:
                raise ProtocolError("LOADING outside its limits", protocol.ERRORS["out_of_limits"])
            if self.phase == LOADING and seat.loaded is None:
                # (a seat shown slow stays slow until its LOADED: §5.6)
                if seat.load_state != protocol.LOAD_STATES["slow"]:
                    seat.load_state = protocol.LOAD_STATES["loading"]
                seat.per_mille = fields["per_mille"]
                self.broadcast(self.load_state())
        elif name == "LOADED":
            if self.phase == PLAYING and seat.loaded is None and seat.state == AWAY:
                self.late_loaded(seat, fields["rules_hash"], fields["tick0_hash"])
                return
            if self.phase != LOADING or seat.loaded is not None:
                raise ProtocolError("Unknown or out-of-order message")
            seat.loaded = (fields["rules_hash"], fields["tick0_hash"])
            seat.per_mille, seat.load_state = 1000, protocol.LOAD_STATES["checking"]
            if fields["rules_hash"] != self.rules_hash:
                self.end("rules_mismatch", "aborted")
                return
            self.broadcast(self.load_state())
            self.check_loaded()
        elif name == "CMD":
            if self.phase == LOADING:
                raise ProtocolError("Unknown or out-of-order message")
            protocol.check_command(fields["type"], fields["a"], fields["b"], fields["c"])
            if self.loop.sealing and seat.state != LEFT:
                if fields["type"] == SIGNAL and self.server.muted(player):
                    # (a muted profile's signals reach no one: admin.py)
                    self.sequencer.skip(seat.index, fields["seq"])
                    return
                self.sequencer.command(seat.index, fields["seq"], fields["type"], fields["a"], fields["b"], fields["c"])
        elif name == "HASH":
            self.hash(seat, fields["tick"], fields["hash"], fields["flags"])
        elif name == "RESULT":
            self.result(seat, fields["tick"], fields["hash"], tuple(entry["outcome"] for entry in fields["outcomes"]))
        elif name == "LEAVE_MATCH":
            self.leave(seat)
        elif name == "TURN_REQUEST":
            self.resend(seat, fields["first_missing"])
        elif name == "CHECKPOINT_PART":
            self.checkpoint_part(seat, fields["tick"], fields["part"], fields["parts"], fields["data"])
        else:
            raise ProtocolError("Unknown or out-of-order message")

    def disconnected(self, player, goodbye):
        """A seat's connection ended: with a goodbye (BYE, a close) the seat
        is LEFT; dropped, it is held until the match ends (AWAY after its
        silence, the caretaker playing it), and a resume HELLO naming it
        takes it back (rejoin)."""
        seat = self.seats[player.seat]
        if seat.player is not player:
            return
        if goodbye:
            self.leave(seat)
            return
        seat.player, seat.catchup = None, None
        self.server.event("drop", match=self.id, seat=seat.index)
        self.reask(seat)
        if self.phase == LOADING:
            seat.load_state = protocol.LOAD_STATES["gone"]
            self.broadcast(self.load_state())
            self.check_loaded()
        self.check_empty()

    def close(self):
        self.end("server_closing", "aborted")

    # -- a held seat taken back (lobby.py finds it from a resume HELLO)

    def holds(self, identity, rules_hash, index):
        """The seat `index` if `identity` holds it and a game of `rules_hash`
        can play it: not left, the match not over. Else None."""
        if self.phase == ENDED or not 0 <= index < len(self.seats) or rules_hash != self.rules_hash:
            return None
        seat = self.seats[index]
        return seat if seat.identity == identity and seat.state != LEFT else None

    def rejoin(self, seat, player):
        """`player`, a resume HELLO of the identity that holds `seat`, takes
        it: an old connection still open gets ERROR 12 and closes. During the
        match the game gets MATCH_CONFIG with the rejoin flag, then
        RESYNC(rejoin) and the catch-up, and counts as catching up until it
        says `shown` (which brings the seat BACK). While the match still
        loads it gets MATCH_CONFIG as at the start and loads like any seat."""
        old = seat.player
        if old is not None and old is not player:
            old.match = None
            self.server.drop(old, ProtocolError("Replaced by another session of this profile",
                                                protocol.ERRORS["replaced"]))
        seat.player, seat.catchup, seat.heard = player, None, self.clock.now()
        player.match, player.seat, player.after_match = self, seat.index, False
        # (reports the old connection sent that wait to be decided are the old
        # simulation's: compared now, they would resync the new one again)
        self.forget_reports(seat.index)
        self.server.daily.count("rejoins")
        self.server.event("rejoin", match=self.id, seat=seat.index, phase=self.phase)
        if self.phase == LOADING:
            seat.loaded, seat.per_mille, seat.load_state = None, 0, protocol.LOAD_STATES["connecting"]
            self.write(seat, self.config(seat, 0))
            self.broadcast(self.load_state())
            return
        player.catching_up = True
        # (the old connection's checkpoint upload will not come: the next seat is asked)
        self.reask(seat)
        # (its RESYNC's checkpoint proves its state: a seat started without
        # its player needs no LOADED to come BACK any more)
        seat.loaded = (self.rules_hash, self.tick0)
        seat.per_mille, seat.load_state = 1000, protocol.LOAD_STATES["ready"]
        self.write(seat, self.config(seat, SPEC["config_flags"]["rejoin"]))
        self.resync(seat, "rejoin")

    # -- the barrier

    def load_state(self):
        seconds = min(0xffff, (self.clock.now() - self.configured) // (1000 * MS))
        return protocol.encode("LOAD_STATE", seconds=seconds, seats=[
            dict(seat=s.index, per_mille=s.per_mille, state=s.load_state) for s in self.seats])

    def check_loaded(self):
        """Every connected seat LOADED: their tick-0 hashes compared, and the
        match starts (a seat whose player is gone starts AWAY or LEFT)."""
        if self.phase != LOADING or any(s.player and s.loaded is None for s in self.seats):
            return
        if not any(s.loaded for s in self.seats) or not self.agree_loaded():
            return
        self.broadcast(self.load_state())
        self.ready.set()
        self.barrier.poke()

    def agree_loaded(self):
        """The loaded seats' tick-0 hashes compared: all equal marks them
        ready (True); apart, the match is aborted before anyone plays."""
        loaded = [s for s in self.seats if s.loaded]
        votes = collections.Counter(s.loaded[1] for s in loaded)
        best, count = votes.most_common(1)[0]
        if count != len(loaded):
            # (a strict majority names the seats that differ; two seats name none: 255)
            odd = [s.index for s in loaded if s.loaded[1] != best] if count * 2 > len(loaded) else []
            for seat in self.seats:
                if seat.player:
                    self.write(seat, protocol.encode("NOTICE", code=protocol.NOTICES["tick0_mismatch"],
                                                     argument=odd[0] if odd else protocol.SYSTEM_SEAT))
            self.end("tick0_mismatch", "aborted")
            return False
        self.tick0 = best
        for seat in loaded:
            seat.load_state = protocol.LOAD_STATES["ready"]
        return True

    def late_loaded(self, seat, rules_hash, tick0):
        """LOADED from a seat the match started without: the same hashes
        hand it BACK (the caretaker gives it control at the next build
        window; while its game says catching_up, at its `shown`); others put
        it out of the match, as at the start."""
        if rules_hash != self.rules_hash or tick0 != self.tick0:
            self.write(seat, protocol.encode("NOTICE", code=protocol.NOTICES["tick0_mismatch"], argument=seat.index))
            self.drop_late(seat, "rules_mismatch" if rules_hash != self.rules_hash else "tick0_mismatch")
            return
        seat.loaded = (rules_hash, tick0)
        seat.per_mille, seat.load_state = 1000, protocol.LOAD_STATES["ready"]
        self.heard(seat.player)
        # (a game that knows it was started without says catching_up: from a
        # checkpoint past tick 0 it need not run the match from its start)
        self.behind(seat)

    def drop_late(self, seat, reason="timeout"):
        """A seat out of the match before it played (the ceiling, or tick-0
        hashes apart after a start without it): its game told the match
        ended for it (aborted), and the caretaker keeps the seat (LEFT)."""
        if seat.player:
            self.write(seat, protocol.encode("MATCH_END", outcome=protocol.OUTCOMES["aborted"],
                                             reason=protocol.END_REASONS[reason], final_tick=0))
        self.leave(seat)

    async def run(self):
        try:
            # (the loading screen shows at least loading_min_ms, 0 for one
            # human, and the barrier's timers run: lobby.Barrier, §6.6)
            if not await self.barrier.wait() or self.phase != LOADING:
                return
            if not self.ready.is_set():
                # (started without the seats still loading: those loaded must agree)
                if not self.agree_loaded():
                    return
                self.broadcast(self.load_state())
            self.start()
            await self.loop.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception("Match %s failed", self.id)
            self.end("server_closing", "aborted")

    def start(self):
        now = self.clock.now()
        origin = now + self.start_delay_ms * MS
        self.loop = TurnLoop(self.clock, origin, self.seal, self.tend, self.turn_ns)
        self.phase = PLAYING
        self.next_links = origin + SPEC["links_ms"] * MS
        self.next_feed = origin + CATCHUP_NS
        for seat in self.seats:
            seat.heard, seat.hashed = now, origin
            if seat.state == LEFT:
                self.sequencer.inject("LEFT", seat.index)
                self.cared(seat)
            elif seat.player is None or seat.loaded is None:
                # (gone, or started without while it still loads: the caretaker plays it)
                seat.state = AWAY
                self.sequencer.inject("AWAY", seat.index)
                self.cared(seat)
        self.broadcast(protocol.encode("START", ms_until_turn0=self.start_delay_ms))
        self.server.event("start", match=self.id, mode=self.mode)
        self.server.daily.tally("started", self.mode)
        self.server.lobby.started(self)

    def cared(self, seat):
        """The caretaker took `seat`: counted once a match (/stats)."""
        if not seat.cared:
            seat.cared = True
            self.server.daily.count("caretaker_seats")

    # -- the turns

    def seal(self, turn, now):
        if turn == self.cap_turn:
            self.sequencer.inject("TIMEOUT")
        entries = self.sequencer.seal(turn)
        data = protocol.turn(turn, entries)
        if entries:
            self.log[turn] = data
        for seat in self.seats:
            # (a seat catching up gets it behind the turns before it: feed)
            if seat.catchup is None:
                self.write(seat, data)
        if self.observer:
            self.observer(turn, now, entries)
        if turn == self.cap_turn:
            # (the simulation ends the match at TIMEOUT's tick: nothing more to seal)
            self.loop.sealing = False
            self.timed_out = now
            self.server.event("timeout", match=self.id, turn=turn)

    def sealed(self, turn):
        """TURN(turn) again: from the log, or empty (only turns with commands are kept)."""
        return self.log.get(turn) or protocol.turn(turn, ())

    def tend(self, now):
        """Once a wake: silences become AWAY, waits run out, LINKS every 2 s,
        a checkpoint not uploaded in time is asked of the next seat, and the
        seats catching up get their next share (feed)."""
        for seat in self.seats:
            if seat.state == PRESENT and self.loop.sealing and now - seat.heard >= SPEC["away_ms"] * MS:
                seat.state = AWAY
                self.sequencer.inject("AWAY", seat.index)
                self.cared(seat)
                self.server.event("away", match=self.id, seat=seat.index)
        self.barrier.tend(now)
        if self.phase != PLAYING:
            return
        for tick in [tick for tick, (first, _, _) in self.hashes.items() if now - first >= SPEC["hash_wait_ms"] * MS]:
            if tick in self.hashes and self.phase == PLAYING:
                self.decide(tick)
        # (a seat gone AWAY or LEFT no longer holds the results up)
        self.judge()
        if self.phase != PLAYING:
            return
        if self.timed_out is not None and now - self.timed_out >= SPEC["result_wait_ms"] * MS:
            self.end("timeout", "aborted", self.cap_turn * TURN_TICKS)
        if self.phase != PLAYING:
            return
        if now >= self.next_links:
            self.next_links = max(self.next_links + SPEC["links_ms"] * MS, now)
            self.broadcast(self.links())
        if self.upload and now - self.upload.asked_at >= SPEC["checkpoint_wait_ms"] * MS:
            # (not whole in time: dropped, and the next seat is asked)
            self.server.event("checkpoint_late", match=self.id, seat=self.upload.seat, tick=self.upload.tick)
            self.ask(self.upload)
        self.feed(now)

    def links(self):
        flags = SPEC["link_flags"]
        return protocol.encode("LINKS", seats=[dict(
            seat=s.index, rtt_ms=min(0xffff, s.player.round_trip) if s.player else 0,
            flags=(flags["hidden"] if s.player and s.player.hidden else 0)
            | (flags["silent"] if s.state != PRESENT or not s.player else 0)
            | (flags["catching_up"] if s.player and s.player.catching_up else 0)) for s in self.seats])

    def resend(self, seat, first):
        """TURN_REQUEST: the sealed turns from `first` again, at most
        turn_request_turns of them (5 s), and at most one answer per half of
        the game's own turn_request_ms: a game asks again for the next gap.
        A seat that hashed tick T holds every turn below T / 3 already, so
        those are never sent again. This bounds the work one message causes.
        A seat catching up is not answered: its catch-up brings every turn,
        in order (catchup.py)."""
        if not self.loop:
            raise ProtocolError("Unknown or out-of-order message")
        if seat.catchup is not None:
            return
        now = self.clock.now()
        if seat.resent is not None and now - seat.resent < SPEC["turn_request_ms"] * MS // 2:
            return
        seat.resent = now
        first = max(first, (seat.hash_tick + 1) // TURN_TICKS)
        for turn in range(first, min(self.loop.turn, first + SPEC["turn_request_turns"])):
            self.write(seat, self.sealed(turn))

    # -- hashes and results

    def present(self):
        """The seats that vote: a connection, not away or left, and not a
        minority whose RESYNC is on its way (muted)."""
        return [s for s in self.seats if s.player and s.state == PRESENT and not s.muted]

    def hash(self, seat, tick, digest, flags=0):
        """HASH: bounded (a multiple of hash_every, no later than the sealed
        turns reach, only the checkpoint flag) and increasing per seat; after
        a RESYNC the seat counts again from its checkpoint tick, so one HASH
        at or after it may go back. A minority's HASHes on their way before
        it went back are its parted simulation's: not compared."""
        if self.phase == LOADING:
            raise ProtocolError("Unknown or out-of-order message")
        if tick % SPEC["hash_every"] or tick > TURN_TICKS * self.loop.turn or flags & ~sum(SPEC["hash_flags"].values()):
            raise ProtocolError("HASH outside its limits", protocol.ERRORS["out_of_limits"])
        if tick <= seat.hash_tick:
            if seat.restart is None or tick < seat.restart:
                raise ProtocolError("HASH ticks must increase")
            # (it went back to the checkpoint: compared again from here)
            seat.restart, seat.muted = None, False
        elif seat.restart is not None and not seat.muted:
            # (behind: its HASHes from the checkpoint came past its last one, so none
            # need go back any more; a desync's minority still may, its RESYNC on its way)
            seat.restart = None
        seat.hash_tick, seat.hashed = tick, self.clock.now()
        if seat.muted:
            return
        self.compare(seat, tick, digest, flags)
        # (a seat whose simulation runs past a claimed end disagrees with it)
        self.judge()

    def compare(self, seat, tick, digest, flags=0):
        if tick <= self.forgotten:
            return          # (older than the agreed hashes kept: nothing to judge it by)
        agreed = self.agreed.get(tick)
        if agreed is not None:
            if digest != agreed:
                self.desync([seat.index], tick)
            return
        entry = self.hashes.setdefault(tick, [self.clock.now(), {}, set()])
        entry[1][seat.index] = digest
        if flags & CHECKPOINT_FLAG:
            entry[2].add(seat.index)
        if all(s.index in entry[1] for s in self.voters(tick, entry[1])):
            self.decide(tick)

    def voters(self, tick, by):
        """The seats whose word decides `tick`: the present ones that reported
        it, and the present ones that may still: their last HASH is below it
        and came in the last result_wait_ms (a seat that talks but stopped
        hashing holds a tick up that long at most)."""
        now = self.clock.now()
        return [s for s in self.present() if s.index in by
                or (s.hash_tick < tick and now - s.hashed < SPEC["result_wait_ms"] * MS)]

    def decide(self, tick):
        """Every voter reported the tick, or 2 s passed: all equal, or with
        three voters or more a strict majority of the voters (not of the
        reports so far), is agreement. Short of that the tick stays open while
        the voters still to report could make one, until they do or stop
        voting (away, gone, left, silent hashes); when none can form any more,
        the match ends "desynced". A report from a seat that does not vote (a
        game catching up while its seat is away) is held to the agreed hash.
        An agreed tick a game flagged as a checkpoint is asked for."""
        entry = self.hashes.pop(tick)
        _, by, flagged = entry
        voters = self.voters(tick, by)
        # (nobody votes any more, every seat away say: the reports there decide)
        voting = [s.index for s in voters] or list(by)
        votes = [by[index] for index in voting if index in by]
        if not votes:
            self.hashes[tick] = entry       # (only seats that do not vote reported it: it waits)
            return
        best, count = collections.Counter(votes).most_common(1)[0]
        missing = len(voting) - len(votes)
        if count == len(voting) or (len(voting) >= 3 and count * 2 > len(voting)):
            self.agreed[tick] = best
            while len(self.agreed) > AGREED_KEPT:
                self.forgotten = max(self.forgotten, self.agreed.popitem(last=False)[0])
            apart = [index for index, digest in by.items() if digest != best]
            if apart:
                self.desync(apart, tick)
            keepers = tuple(sorted(index for index in flagged if by.get(index) == best))
            if keepers and tick > 0 and self.phase == PLAYING:
                self.want(tick, best, keepers)
            return
        if missing:
            # (all equal so far with one or two voters, or a strict majority still in reach)
            need = len(voting) // 2 + 1 if len(voting) >= 3 else len(voting)
            if count == len(votes) or (len(voting) >= 3 and count + missing >= need):
                self.hashes[tick] = entry
                return
        self.end("desync", "desynced", tick)

    def desync(self, indices, tick):
        """Seats whose hash differs from the agreed one: with three seats or
        more a minority, each resynced from the latest checkpoint before its
        last HASH (RESYNC desync), or, apart again after max_resyncs, out of
        the match (desynced_twice); with two the match ends "desynced"."""
        self.server.event("desync", match=self.id, seats=indices, tick=tick)
        if len(self.seats) < 3:
            self.end("desync", "desynced", tick)
            return
        self.server.daily.count("desyncs")     # (a match ended desynced counts at its end)
        for index in indices:
            seat = self.seats[index]
            if not seat.player or seat.muted or seat.state == LEFT:
                continue
            if seat.resyncs >= SPEC["max_resyncs"]:
                self.desynced_twice(seat, tick)
                continue
            seat.resyncs += 1
            # (its reports still waiting are its parted simulation's)
            self.forget_reports(index)
            self.resync(seat, "desync", below=seat.hash_tick)

    def forget_reports(self, index):
        """Seat `index`'s reports still waiting to be decided, let go."""
        for waiting in list(self.hashes):
            _, by, flagged = self.hashes[waiting]
            by.pop(index, None)
            flagged.discard(index)
            if not by:
                del self.hashes[waiting]

    def desynced_twice(self, seat, tick):
        """The same seat apart again after its resync: MATCH_END(desynced,
        desynced_twice) to it alone, back in the hub as after LEAVE_MATCH
        (its game writes the dump), and LEFT in the turns: the caretaker
        keeps the seat."""
        self.write(seat, protocol.encode("MATCH_END", outcome=protocol.OUTCOMES["desynced"],
                                         reason=protocol.END_REASONS["desynced_twice"], final_tick=tick))
        self.server.event("desynced_twice", match=self.id, seat=seat.index, tick=tick)
        self.leave(seat)

    def result(self, seat, tick, digest, outcomes):
        """RESULT: the seat's final tick, its hash there and each team's
        outcome. Bounded like HASH: no later than the sealed turns reach, and
        no earlier than the seat's own last HASH. A minority's on its way
        before its RESYNC is its parted simulation's: let pass."""
        if self.phase == LOADING or seat.result is not None:
            raise ProtocolError("Unknown or out-of-order message")
        if (len(outcomes) != self.spec["teams"] or any(value > protocol.OUTCOMES["draw"] for value in outcomes)
                or tick > TURN_TICKS * self.loop.turn or tick < seat.hash_tick):
            raise ProtocolError("RESULT outside its limits", protocol.ERRORS["out_of_limits"])
        if seat.muted:
            return
        seat.result = (tick, digest, outcomes)
        self.judge()

    def judge(self):
        """The end by the hashes' rule, among the seats present now (a seat
        AWAY or LEFT neither votes nor holds the end up): a RESULT that a
        strict majority of them sent (all of them, with one or two) ends the
        match with its outcomes. Short of that, the match plays on while a
        majority can still form from the present seats with no RESULT yet
        that are still playing (a HASH in the last result_wait_ms):

        - one whose last HASH is at or before a claimed final tick is on its
          way there (slow, or catching up) and may yet agree with the claim;
          once it hashes past the tick, its simulation ran past the claimed
          end, and it disagrees;
        - together they may agree on an end of their own. So with three
          seats or more, a claim the others ran past is outvoted while they
          play on (§6.1, §6.7); with two, one seat is never a majority, and a
          lone claim the other ran past ends the match "desynced".

        When no majority can form any more, the match ends "desynced" at the
        earliest claimed tick, never with a claim's outcomes: one seat's
        word never decides for another that is present. A seat that talks
        but stops hashing stops counting result_wait_ms after its last HASH,
        so it holds the end up that long at most."""
        if self.phase != PLAYING:
            return
        voters = self.present()
        claims = collections.Counter(s.result for s in voters if s.result)
        if not claims:
            return
        now = self.clock.now()
        need = len(voters) // 2 + 1
        playing = [s for s in voters if s.result is None and now - s.hashed < SPEC["result_wait_ms"] * MS]
        possible = len(playing) >= need
        for claim, count in claims.most_common():
            if count >= need:
                self.end("result", None, claim[0], claim[2])
                return
            possible = possible or count + sum(1 for s in playing if s.hash_tick <= claim[0]) >= need
        if not possible:
            self.server.event("desync", match=self.id, seats=[s.index for s in voters], tick=min(claims)[0])
            self.end("desync", "desynced", min(claims)[0])

    # -- checkpoints

    def can_upload(self, seat):
        """A seat that may be asked for a checkpoint: present, not hidden,
        not catching up (its own catch-up, or its word for it)."""
        player = seat.player
        return (player is not None and seat.state == PRESENT and not seat.muted and seat.catchup is None
                and not player.hidden and not player.catching_up)

    def want(self, tick, digest, keepers):
        """An agreed checkpoint tick: asked of a seat in rotation. A newer
        one takes the place of one still being uploaded (the latest is the
        one a RESYNC starts from); the older one's parts are let pass."""
        if self.upload and self.upload.tick >= tick:
            return
        if self.checkpoints and self.checkpoints[-1][0] >= tick:
            return
        self.upload = Upload(tick, digest, keepers)
        self.ask(self.upload)

    def ask(self, upload):
        """CHECKPOINT_ASK to the next seat in rotation that keeps the tick and
        may upload, not asked for it yet; none left, the tick is given up."""
        count = len(self.seats)
        order = [self.seats[(self.next_ask + step) % count] for step in range(count)]
        seat = next((s for s in order if s.index in upload.keepers and s.index not in upload.tried
                     and self.can_upload(s)), None)
        if seat is None:
            self.server.event("checkpoint_unkept", match=self.id, tick=upload.tick)
            self.upload = None
            return
        upload.tried.add(seat.index)
        upload.seat, upload.asked_at, upload.parts, upload.chunks = seat.index, self.clock.now(), 0, []
        seat.asked.add(upload.tick)
        self.next_ask = (seat.index + 1) % count
        self.write(seat, protocol.encode("CHECKPOINT_ASK", tick=upload.tick))

    def reask(self, seat):
        """The connection a checkpoint was asked of is gone (dropped, left,
        replaced by a rejoin): its parts will not come, so the next seat is
        asked now rather than checkpoint_wait_ms after the ask."""
        if self.upload and self.upload.seat == seat.index and self.phase == PLAYING:
            self.server.event("checkpoint_gone", match=self.id, seat=seat.index, tick=self.upload.tick)
            self.ask(self.upload)

    def checkpoint_part(self, seat, tick, part, parts, data):
        """CHECKPOINT_PART: parts 0 to n − 1 in order, all but the last
        checkpoint_part bytes, at most max_checkpoint_parts. Whole, it is kept
        if its digest is the agreed hash; else the next seat is asked. Parts
        for a tick the server stopped waiting for are let pass; for a tick
        never asked of this seat they are ERROR 1."""
        upload = self.upload
        if upload is None or upload.tick != tick or upload.seat != seat.index:
            if tick in seat.asked:
                return
            raise ProtocolError("Unknown or out-of-order message")
        size = SPEC["checkpoint_part"]
        if (not 0 < parts <= SPEC["max_checkpoint_parts"] or part != len(upload.chunks)
                or (upload.chunks and parts != upload.parts) or not data
                or (part < parts - 1 and len(data) != size)):
            raise ProtocolError("CHECKPOINT_PART outside its limits", protocol.ERRORS["out_of_limits"])
        upload.parts = parts
        upload.chunks.append(bytes(data))
        if len(upload.chunks) < parts:
            return
        whole = b"".join(upload.chunks)
        if protocol.digest(whole) != upload.digest:
            # (not the state the seats agreed: never kept, and the next seat is asked)
            self.server.event("checkpoint_refused", match=self.id, seat=seat.index, tick=tick)
            self.ask(upload)
            return
        self.upload = None
        self.checkpoints = (self.checkpoints + [(tick, whole, upload.digest)])[-SPEC["checkpoints_kept"]:]
        self.server.event("checkpoint", match=self.id, seat=seat.index, tick=tick, bytes=len(whole))

    def checkpoint(self, below=None):
        """The latest checkpoint kept (below tick `below`, where given), as
        (tick, bytes, digest); tick 0 when none, which every game builds
        from MATCH_CONFIG (its hash the tick-0 hash the seats agreed)."""
        for tick, data, digest in reversed(self.checkpoints):
            if below is None or tick < below:
                return tick, data, digest
        return 0, b"", self.tick0

    # -- RESYNC and the catch-up

    def resync(self, seat, reason, below=None):
        """RESYNC(reason) from the latest checkpoint (below tick `below`),
        then its parts, then every turn from it to the open turn and the
        live turns behind them, all paced (feed, catchup.py)."""
        tick, data, digest = self.checkpoint(below)
        first = tick // TURN_TICKS
        parts = protocol.checkpoint_parts(tick, data) if tick else []
        pacer = CatchUp(lambda message: self.write(seat, message), lambda: self.unsent(seat))
        pacer.queue(protocol.encode("RESYNC", checkpoint_tick=tick, first_turn=first,
                                    reason=protocol.RESYNC_REASONS[reason], open_turn=self.loop.turn,
                                    checkpoint_hash=digest, parts=len(parts)))
        for message in parts:
            pacer.queue(message)
        seat.catchup, seat.cursor = pacer, first
        seat.result, seat.resent = None, None
        if reason == "rejoin":
            # (a new connection: nothing of the old simulation is on its way)
            seat.hash_tick, seat.restart, seat.muted = tick - 1, None, False
        else:
            seat.restart, seat.muted = tick, reason == "desync"
        self.server.daily.count("resyncs")
        self.server.event("resync", match=self.id, seat=seat.index, reason=reason, tick=tick, turn=self.loop.turn)

    def behind(self, seat):
        """A game catching up (VISIBILITY catching_up, or LOADED after a start
        without it, while it says so) is resynced from the latest checkpoint
        when that is past its last HASH: a catch-up starts at most about
        checkpoint_ticks back."""
        player = seat.player
        if (self.phase != PLAYING or player is None or not player.catching_up or seat.catchup is not None
                or seat.loaded is None or seat.state == LEFT):
            return
        tick = self.checkpoint()[0]
        if tick <= max(seat.hash_tick, seat.behind_from, 0):
            return
        seat.behind_from = tick
        self.resync(seat, "behind")

    def feed(self, now):
        """Once every catchup_ms of the server's clock (each wake at the
        protocol's 50 ms turns; every few wakes with a dev match's shorter
        ones), each seat catching up gets its next share. The boundaries lie
        on a grid from turn 0's opening, so a wake a little late still counts
        for its own boundary. Its turns are queued from the log a little
        ahead of the pacing; once nothing is left and the cursor reached the
        open turn, its turns go out directly again."""
        if now < self.next_feed:
            return
        self.next_feed += ((now - self.next_feed) // CATCHUP_NS + 1) * CATCHUP_NS
        for seat in self.seats:
            pacer = seat.catchup
            if pacer is None:
                continue
            while seat.cursor < self.loop.turn and pacer.waiting < 2 * pacer.budget:
                pacer.queue(self.sealed(seat.cursor))
                seat.cursor += 1
            pacer.pump()
            if pacer.done and seat.cursor >= self.loop.turn:
                seat.catchup = None
                self.server.event("caught_up", match=self.id, seat=seat.index, turn=self.loop.turn)

    def unsent(self, seat):
        """The seat's connection's unsent output in bytes (0 without one)."""
        transport = seat.player.writer.transport if seat.player else None
        return transport.get_write_buffer_size() if transport is not None else 0

    # -- leaving and the end

    def leave(self, seat):
        """LEAVE_MATCH or a goodbye: LEFT, and the caretaker keeps the seat to the end."""
        player = seat.player
        seat.player, seat.catchup = None, None
        self.reask(seat)
        if player:
            player.match, player.after_match = None, True
            self.server.lobby.left_match(self, player)
        if seat.state != LEFT:
            if self.phase == PLAYING and self.loop.sealing:
                self.sequencer.inject("LEFT", seat.index)
                self.cared(seat)
            seat.state = LEFT
            self.server.event("left", match=self.id, seat=seat.index)
        if self.phase == LOADING:
            seat.load_state = protocol.LOAD_STATES["gone"]
            self.broadcast(self.load_state())
            self.check_loaded()
        self.check_empty()

    def check_empty(self):
        if self.phase != ENDED and not any(s.player for s in self.seats):
            self.end("everyone_left", "aborted", self.loop.turn * TURN_TICKS if self.loop else 0)

    def end(self, reason, outcome, final_tick=0, per_team=None):
        """MATCH_END to every connected seat (its team's outcome from the
        agreed RESULT, else `outcome`), and the match forgotten."""
        if self.phase == ENDED:
            return
        self.phase = ENDED
        self.ready.set()
        self.barrier.poke()
        if self.loop:
            self.loop.running = False
        for seat in self.seats:
            player = seat.player
            if not player:
                continue
            value = per_team[seat.team] if per_team else protocol.OUTCOMES[outcome]
            self.write(seat, protocol.encode("MATCH_END", outcome=value, reason=protocol.END_REASONS[reason],
                                             final_tick=final_tick))
            seat.player, seat.catchup = None, None
            player.match, player.after_match = None, True
            self.finishers.append(player)
        if reason == "result":
            self.server.daily.tally("finished", self.mode)
        elif reason == "desync":
            self.server.daily.count("desyncs")
        self.server.ended(self)
        self.server.event("end", match=self.id, reason=reason, final_tick=final_tick)
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()

    # -- writing

    def write(self, seat, data):
        player = seat.player
        if not player or player.writer.is_closing():
            return
        player.writer.write(websocket.frame(data))
        transport = player.writer.transport
        # (a reader that never catches up never grows the server's memory: it
        # is dropped, and its seat is held; a seat's paced catch-up keeps its
        # own output small, so the cap is not its)
        if transport is not None and seat.catchup is None and transport.get_write_buffer_size() > self.output_cap:
            self.server.event("slow_reader", match=self.id, seat=seat.index)
            # (aborted, not closed: close() waits to flush, and this reader may never read)
            transport.abort()

    def broadcast(self, data):
        for seat in self.seats:
            self.write(seat, data)
