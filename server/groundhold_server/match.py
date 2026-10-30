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
        self.seats = [Seat(index, spec["team"], spec["builder"], spec["flags"], player.name, player)
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
        self.log = {}                   # turn -> TURN bytes, the turns with commands (TURN_REQUEST)
        self.hashes = {}                # tick -> [first report's clock ns, {seat: hash}]
        self.agreed = collections.OrderedDict()
        self.timed_out = None
        self.next_links = 0
        self.tick0 = None               # the tick-0 hash the seats agreed at the start
        self.finishers = []             # the connections MATCH_END went to
        self.barrier = Barrier(self, strangers=party is None)

    # -- what the server and its connections call

    def begin(self):
        """MATCH_CONFIG to every seat, then the barrier and the turns, in a task."""
        now = self.clock.now()
        self.configured = now
        seats = [dict(seat=s.index, team=s.team, builder=s.builder, flags=s.flags, name=s.name) for s in self.seats]
        for seat in self.seats:
            seat.heard = now
            self.write(seat, protocol.encode("MATCH_CONFIG", match=self.id, mode=self.spec["id"], map=SPEC["maps"]["hollow"],
                                             seed=self.seed, rules_hash=self.rules_hash, your_seat=seat.index, seats=seats))
        self.broadcast(self.load_state())
        self.task = asyncio.create_task(self.run())
        self.server.event("match", match=self.id, mode=self.mode, seats=len(self.seats), seed=self.seed)

    def current_turn(self):
        """The open turn, as PONG says it (0 before turn 0 opens)."""
        return self.loop.turn if self.loop else 0

    def heard(self, player):
        """Any message from a seat's connection: its silence ends, and a seat
        the caretaker took is handed BACK (the simulation gives it control at
        the next build window)."""
        seat = self.seats[player.seat]
        if seat.player is not player:
            return
        seat.heard = self.clock.now()
        # (a seat started without its player comes BACK with its LOADED, not
        # with the LOADING and PINGs it sends while it still loads)
        if seat.state == AWAY and self.phase == PLAYING and self.loop.sealing and seat.loaded is not None:
            seat.state = PRESENT
            self.sequencer.inject("BACK", seat.index)
            self.server.event("back", match=self.id, seat=seat.index)

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
        else:
            raise ProtocolError("Unknown or out-of-order message")

    def disconnected(self, player, goodbye):
        """A seat's connection ended: with a goodbye (BYE, a close) the seat
        is LEFT; dropped, it is held (AWAY after its silence, the caretaker
        playing it; M4 brings the resume)."""
        seat = self.seats[player.seat]
        if seat.player is not player:
            return
        if goodbye:
            self.leave(seat)
            return
        seat.player = None
        self.server.event("drop", match=self.id, seat=seat.index)
        if self.phase == LOADING:
            seat.load_state = protocol.LOAD_STATES["gone"]
            self.broadcast(self.load_state())
            self.check_loaded()
        self.check_empty()

    def close(self):
        self.end("server_closing", "aborted")

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
        window); others put it out of the match, as at the start."""
        if rules_hash != self.rules_hash or tick0 != self.tick0:
            self.write(seat, protocol.encode("NOTICE", code=protocol.NOTICES["tick0_mismatch"], argument=seat.index))
            self.drop_late(seat, "rules_mismatch" if rules_hash != self.rules_hash else "tick0_mismatch")
            return
        seat.loaded = (rules_hash, tick0)
        seat.per_mille, seat.load_state = 1000, protocol.LOAD_STATES["ready"]
        self.heard(seat.player)

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
        self.broadcast(data)
        if self.observer:
            self.observer(turn, now, entries)
        if turn == self.cap_turn:
            # (the simulation ends the match at TIMEOUT's tick: nothing more to seal)
            self.loop.sealing = False
            self.timed_out = now
            self.server.event("timeout", match=self.id, turn=turn)

    def tend(self, now):
        """Once a wake: silences become AWAY, waits run out, LINKS every 2 s,
        and a connection whose output passed its cap is dropped."""
        for seat in self.seats:
            if seat.state == PRESENT and self.loop.sealing and now - seat.heard >= SPEC["away_ms"] * MS:
                seat.state = AWAY
                self.sequencer.inject("AWAY", seat.index)
                self.cared(seat)
                self.server.event("away", match=self.id, seat=seat.index)
        self.barrier.tend(now)
        if self.phase != PLAYING:
            return
        for tick in [tick for tick, (first, _) in self.hashes.items() if now - first >= SPEC["hash_wait_ms"] * MS]:
            self.decide(tick)
        # (a seat gone AWAY or LEFT no longer holds the results up)
        self.judge()
        if self.phase != PLAYING:
            return
        if self.timed_out is not None and now - self.timed_out >= SPEC["result_wait_ms"] * MS:
            self.end("timeout", "aborted", self.cap_turn * TURN_TICKS)
        if self.phase == PLAYING and now >= self.next_links:
            self.next_links = max(self.next_links + SPEC["links_ms"] * MS, now)
            self.broadcast(self.links())

    def links(self):
        flags = SPEC["link_flags"]
        return protocol.encode("LINKS", seats=[dict(
            seat=s.index, rtt_ms=min(0xffff, s.player.round_trip) if s.player else 0,
            flags=(flags["hidden"] if s.player and s.player.hidden else 0)
            | (flags["silent"] if s.state != PRESENT or not s.player else 0)) for s in self.seats])

    def resend(self, seat, first):
        """TURN_REQUEST: the sealed turns from `first` again, at most
        turn_request_turns of them (5 s), and at most one answer per half of
        the game's own turn_request_ms: a game asks again for the next gap.
        A seat that hashed tick T holds every turn below T / 3 already, so
        those are never sent again. This bounds the work one message causes
        (M4's catch-up paces a reconnect under a byte budget)."""
        if not self.loop:
            raise ProtocolError("Unknown or out-of-order message")
        now = self.clock.now()
        if seat.resent is not None and now - seat.resent < SPEC["turn_request_ms"] * MS // 2:
            return
        seat.resent = now
        first = max(first, (seat.hash_tick + 1) // TURN_TICKS)
        for turn in range(first, min(self.loop.turn, first + SPEC["turn_request_turns"])):
            self.write(seat, self.log.get(turn) or protocol.turn(turn, ()))

    # -- hashes and results

    def present(self):
        return [s for s in self.seats if s.player and s.state == PRESENT]

    def hash(self, seat, tick, digest, flags=0):
        if self.phase == LOADING:
            raise ProtocolError("Unknown or out-of-order message")
        if tick % SPEC["hash_every"] or tick > TURN_TICKS * self.loop.turn or flags & ~sum(SPEC["hash_flags"].values()):
            raise ProtocolError("HASH outside its limits", protocol.ERRORS["out_of_limits"])
        if tick <= seat.hash_tick:
            raise ProtocolError("HASH ticks must increase")
        seat.hash_tick, seat.hashed = tick, self.clock.now()
        self.compare(seat, tick, digest)
        # (a seat whose simulation runs past a claimed end disagrees with it)
        self.judge()

    def compare(self, seat, tick, digest):
        agreed = self.agreed.get(tick)
        if agreed is not None:
            if digest != agreed:
                self.desync([seat.index], tick)
            return
        entry = self.hashes.setdefault(tick, [self.clock.now(), {}])
        entry[1][seat.index] = digest
        if all(s.index in entry[1] for s in self.present()):
            self.decide(tick)

    def decide(self, tick):
        """Every present seat reported the tick (or 2 s passed): all equal, or
        with three seats or more a strict majority, is agreement."""
        _, by = self.hashes.pop(tick)
        best, count = collections.Counter(by.values()).most_common(1)[0]
        if count == len(by) or (len(by) >= 3 and count * 2 > len(by)):
            self.agreed[tick] = best
            while len(self.agreed) > AGREED_KEPT:
                self.agreed.popitem(last=False)
            if count != len(by):
                self.desync([seat for seat, digest in by.items() if digest != best], tick)
            return
        self.end("desync", "desynced", tick)

    def desync(self, seats, tick):
        """Seats whose hash differs from the agreed one: with three seats or
        more they are a minority (M4: RESYNC from the agreed checkpoint);
        with two the match ends "desynced"."""
        self.server.event("desync", match=self.id, seats=seats, tick=tick)
        if len(self.seats) < 3:
            self.end("desync", "desynced", tick)
        else:
            self.server.daily.count("desyncs")     # (a match ended desynced counts at its end)

    def result(self, seat, tick, digest, outcomes):
        """RESULT: the seat's final tick, its hash there and each team's
        outcome. Bounded like HASH: no later than the sealed turns reach, and
        no earlier than the seat's own last HASH."""
        if self.phase == LOADING or seat.result is not None:
            raise ProtocolError("Unknown or out-of-order message")
        if (len(outcomes) != self.spec["teams"] or any(value > protocol.OUTCOMES["draw"] for value in outcomes)
                or tick > TURN_TICKS * self.loop.turn or tick < seat.hash_tick):
            raise ProtocolError("RESULT outside its limits", protocol.ERRORS["out_of_limits"])
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

    # -- leaving and the end

    def leave(self, seat):
        """LEAVE_MATCH or a goodbye: LEFT, and the caretaker keeps the seat to the end."""
        player = seat.player
        seat.player = None
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
            seat.player = None
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
        # is dropped, and its seat is held)
        if transport is not None and transport.get_write_buffer_size() > self.output_cap:
            self.server.event("slow_reader", match=self.id, seat=seat.index)
            player.writer.close()

    def broadcast(self, data):
        for seat in self.seats:
            self.write(seat, data)
