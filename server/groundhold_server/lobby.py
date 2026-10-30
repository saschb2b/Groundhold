"""The lobby: parties by code, their countdown, the matches they play, the
loading barrier's timers, and the way back to the party (docs/design/
core-loop.md §5.2 to §5.9, §6.6, Appendix A).

Every timer here runs on the server's clock (`server.clock`, integer
nanoseconds), so a test moves it by hand and nothing waits on the wall:

| Timer | Value |
|---|---|
| Party countdown | 3 s |
| Party row held after a drop | 40 s (holds.py) |
| Empty party code expiry | 15 min |
| Parties at once | `party_cap`, 4 × `player_cap` by default |
| Loading: minimum, slow, start-without, automatic, ceiling | 4 s, 15 s, 30 s, 45 s, 120 s |

**The loop.** A party's leader presses Start with every other member
Ready: `PARTY_STATE` says `countdown` with 3,000 ms; anyone's cancel, a
member's un-Ready, a Builder change, a drop, a join or a mode change stops
it. At its end the party's match forms: `PARTY_STATE` phase `loading`,
then `MATCH_CONFIG` to each member, one seat each in seat order (by team,
then by row), each seat's Builder its member's main. When the match starts
the phase is `in_match`; when it ends, `results`: each member who was in
it at the end stays `in_match` (on the results plate) until it sends
`LEAVE_MATCH` (Play again, or Hub), which brings it back to the party with
its Ready cleared; when everyone is back the phase is `forming` again, the
party, mode, teams and Builders unchanged. A match that ends before it
starts (a tick-0 mismatch, everyone gone) brings everyone back at once.

**The barrier** (`Barrier`): every seat `LOADED` with equal tick-0 hashes
and at least 4 s since `MATCH_CONFIG` (0 s with one human) starts the match.
At 15 s a seat not yet loaded shows `slow`. From 30 s the leader of a party
match may start without the seats still loading (`PARTY start` while the
phase is `loading`); at 45 s a match of strangers (from the queue, M6, or
`--dev-match`) starts by itself with the seats loaded. A seat started
without its player begins `AWAY` (the caretaker plays it) and is handed
`BACK` when its `LOADED` comes with the same tick-0 hash. At 120 s every
seat still not loaded is out (`MATCH_END` aborted, reason `timeout`, to its
game; `LEFT` in the turns); a match where nobody loaded ends there, and a
match of strangers is dissolved (`NOTICE match_dissolved`).

**Bounded.** A server keeps at most `party_cap` parties, the empty ones
waiting on their code included, and an identity keeps at most one empty
party: when it leaves another party empty, the one it left before goes at
once. A create at the cap makes room by dropping the empty party that has
waited longest; with none empty it is refused (`NOTICE parties_full`) and
the player keeps the party it has. Each PARTY create leaves the party
before it, so without these one connection could pile up parties, each
kept 15 minutes (review round 2).

**No public queue yet** (the queue, Match Found and its accept are M6):
every `QUEUE` is answered with `QUEUE_STATE` idle, and `ACCEPT` is let pass.

New in Groundhold: nothing in Cyberworld has parties with codes, a
countdown or a loading barrier.
"""

import asyncio
import contextlib
import math

from . import codes, protocol
from .party import (BUILDERS, COUNTDOWN, COUNTDOWN_MS, EXPIRY_MS, FORMING, IN_MATCH, LOADING, MAX_MEMBERS,
                    MODES, NOBODY, RESULTS, Party, no_party)
from .protocol import ProtocolError, SPEC

MS = 1_000_000
SECOND = 1000 * MS
SLOW_MS = 15_000
START_WITHOUT_MS = 30_000
# PARTY ops a player in a running match may not make: each would take its
# connection into another party or match while its seat still points at it.
OPS_REFUSED_IN_MATCH = ("create", "join", "leave", "start")
AUTOMATIC_MS = 45_000
CEILING_MS = 120_000
PARTIES_PER_PLAYER = 4                  # party_cap's default, per player_cap
LOOKUP_BURST, LOOKUP_REFILL = 5, 0.2    # PARTY join's code lookups per connection: 5 at once, then one per 5 s
STATES = protocol.LOAD_STATES
NOTICES = protocol.NOTICES


class Timers:
    """Callbacks at deadlines of the server's clock, each its own small
    task; `close` cancels those still waiting."""

    def __init__(self, clock):
        self.clock = clock
        self.tasks = set()

    def at(self, deadline, callback):
        task = asyncio.create_task(self._run(deadline, callback))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _run(self, deadline, callback):
        await self.clock.sleep_until(deadline)
        callback()

    async def close(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class Barrier:
    """When a match's loading ends (§6.6): `wait` returns True when the
    match should start, False when it ended before. `strangers`: a match of
    players who did not come as a party (the queue's, `--dev-match`'s),
    which starts by itself at 45 s; a party's waits for its leader."""

    def __init__(self, match, strangers):
        self.match, self.strangers = match, strangers
        self.wake = asyncio.Event()
        self.forced = False         # start with the seats loaded (start-without, automatic, ceiling)
        self.done = set()           # the timers applied: "slow", "without", "automatic", "ceiling"

    def poke(self):
        self.wake.set()

    def elapsed(self, now):
        return now - self.match.configured

    async def wait(self):
        match = self.match
        while match.phase == "loading":
            self.wake.clear()
            now = match.clock.now()
            self.timers(now)
            if match.phase != "loading":
                return False
            deadline = self.next_deadline()
            if self.forced or match.ready.is_set():
                humans = sum(1 for seat in match.seats if seat.player)
                minimum = match.configured + (match.loading_min_ms if humans > 1 else 0) * MS
                if now >= minimum:
                    return True
                deadline = minimum if deadline is None else min(deadline, minimum)
            await self.until(deadline)
        return False

    async def until(self, deadline):
        waiter = asyncio.ensure_future(self.wake.wait())
        tasks = {waiter}
        if deadline is not None:
            tasks.add(asyncio.ensure_future(self.match.clock.sleep_until(deadline)))
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()

    def schedule(self):
        steps = [("slow", SLOW_MS), ("automatic" if self.strangers else "without",
                                     AUTOMATIC_MS if self.strangers else START_WITHOUT_MS), ("ceiling", CEILING_MS)]
        return [(name, self.match.configured + ms * MS) for name, ms in steps]

    def next_deadline(self):
        due = [deadline for name, deadline in self.schedule() if name not in self.done]
        return min(due) if due else None

    def timers(self, now):
        """The barrier's timers that are due, in order."""
        match = self.match
        for name, deadline in self.schedule():
            if name in self.done or now < deadline or match.phase != "loading":
                continue
            self.done.add(name)
            if name == "slow":
                for seat in match.seats:
                    if seat.loaded is None and seat.load_state in (STATES["connecting"], STATES["loading"]):
                        seat.load_state = STATES["slow"]
                match.broadcast(match.load_state())
            elif name == "without":
                # (the leader's Start without Ben is open from here: the
                # LOAD_STATE's seconds say so to every game)
                match.broadcast(match.load_state())
            elif name == "automatic":
                if any(seat.loaded for seat in match.seats):
                    self.forced = True
                match.broadcast(match.load_state())
            elif name == "ceiling":
                self.ceiling()

    def start_without(self, now):
        """The leader's Start without: from 30 s, in a party's match, with a
        seat loaded. Whether it was taken."""
        match = self.match
        if (self.strangers or match.phase != "loading" or self.elapsed(now) < START_WITHOUT_MS * MS
                or not any(seat.loaded for seat in match.seats)):
            return False
        self.forced = True
        match.server.event("start_without", match=match.id)
        self.poke()
        return True

    def ceiling(self):
        """120 s: every seat not loaded is out; the rest start, or the match
        ends where nobody loaded (a match of strangers is dissolved)."""
        match = self.match
        late = [seat for seat in match.seats if seat.loaded is None and seat.state != "left"]
        if match.phase == "loading" and not any(seat.loaded for seat in match.seats):
            if self.strangers:
                for seat in match.seats:
                    if seat.player:
                        match.write(seat, protocol.encode("NOTICE", code=NOTICES["match_dissolved"], argument=0))
            match.end("timeout", "aborted")
            return
        for seat in late:
            match.drop_late(seat)
        if match.phase == "loading":
            self.forced = True

    def tend(self, now):
        """After the start: the ceiling still comes for a seat started without."""
        if "ceiling" not in self.done and now >= self.match.configured + CEILING_MS * MS:
            self.done.add("ceiling")
            self.ceiling()


class Lobby:
    def __init__(self, server):
        self.server = server
        self.parties = {}           # code -> Party
        self.empty = {}             # code -> Party: the empty parties, longest waiting first
        self.left_empty = {}        # identity -> the empty party it left last

    @property
    def clock(self):
        return self.server.clock

    @property
    def holds(self):
        return self.server.holds

    def open_parties(self):
        return sum(1 for party in self.parties.values() if party.open_seat())

    # -- writing

    def send(self, player, data):
        self.server.send(player, data)

    def notice(self, player, name, argument=0):
        self.send(player, protocol.encode("NOTICE", code=NOTICES[name], argument=argument))

    def broadcast(self, party):
        now = self.clock.now()
        party.rtt_sent = now
        for member in party.ordered():
            member.rtt_shown = member.player.round_trip if member.player else 0
            if member.player:
                self.send(member.player, party.encode(now, member.number))

    def refuse(self, player, party):
        """An op the party's rules do not allow now (another took the lead,
        the phase moved on): the party as it is, so the game shows the truth."""
        you = player.member.number if party and player.member and player.member.party is party else NOBODY
        self.send(player, party.encode(self.clock.now(), you) if party else no_party())

    def tell_reload(self, party, before):
        """NOTICE needs_reload to each member that needs it now and did not before."""
        for member in party.ordered():
            if member.player and party.needs_reload(member) and member.number not in before:
                self.notice(member.player, "needs_reload", member.number)

    def reloading(self, party):
        return {member.number for member in party.members.values() if party.needs_reload(member)}

    # -- PARTY

    def party_op(self, player, fields):
        member = player.member
        party = member.party if member else None
        if player.match and fields["op"] in OPS_REFUSED_IN_MATCH and not self.starting_without(player, party, fields):
            # (the match runs: no second party or match for this connection, and
            # no leaving it behind; the game sends LEAVE_MATCH first)
            self.refuse(player, party)
            return
        getattr(self, "op_" + fields["op"])(player, member, party, fields)

    @staticmethod
    def starting_without(player, party, fields):
        """The leader's start without a stuck member, from inside the loading match (§6.6)."""
        return fields["op"] == "start" and party is not None and party.phase == LOADING and party.match is player.match

    def op_create(self, player, member, party, fields):
        mode = self.mode(fields["mode"])
        code = self.room() and codes.generate(self.parties, self.server.code_rng)
        if not code:
            # (no room: the player keeps the party it has)
            self.notice(player, "parties_full")
            return
        if member:
            self.leave(member, tell=False)
        party = Party(code, mode, lan=self.server.lan)
        self.parties[code] = party
        player.member = party.add(player, player.identity, player.name, player.build_seq, player.rules_hash)
        self.server.event("party", party=code.decode(), mode=MODES[mode][0])
        self.broadcast(party)

    def op_join(self, player, member, party, fields):
        bucket = player.lookups
        if not bucket.take(self.clock.now() / 1e9):
            # (no lookup made: a burst of guesses learns nothing)
            self.notice(player, "no_such_party", max(1, math.ceil((1 - bucket.tokens) / bucket.refill)))
            return
        code = codes.parse(fields["code"])
        found = self.parties.get(code) if code else None
        if found is None:
            self.notice(player, "no_such_party")
            return
        if party is found:
            self.refuse(player, party)
            return
        if player.identity in found.removed:
            self.notice(player, "removed")
            return
        before = self.reloading(found)
        held = self.holds.find(player.identity, found)
        if held is None and len(found.members) >= MAX_MEMBERS:
            self.notice(player, "party_full", len(found.members))
            return
        if member:
            self.leave(member, tell=False)
        if held:
            self.take_back(held, player)
        else:
            player.member = found.add(player, player.identity, player.name, player.build_seq, player.rules_hash)
            self.server.event("party_join", party=found.code.decode(), member=player.member.number)
        if found.timer and len(found.members) == 1:
            found.timer.cancel()        # (it was empty: its code's expiry is off)
            found.timer = None
            self.filled(found)
        self.stop_countdown(found)
        self.tell_reload(found, before)
        self.broadcast(found)

    def op_leave(self, player, member, party, fields):
        if member is None:
            self.send(player, no_party())
            return
        self.leave(member)

    def op_remove(self, player, member, party, fields):
        number = self.bounded(fields["member"], MAX_MEMBERS)
        target = party.members.get(number) if party else None
        if not party or party.leader is not member or target is None or target is member:
            self.refuse(player, party)
            return
        party.removed.add(target.identity)
        removed = target.player
        self.leave(target, tell=False)
        if removed:
            self.notice(removed, "removed")
            self.send(removed, no_party())

    def op_mode(self, player, member, party, fields):
        mode = self.mode(fields["mode"])
        if not party or party.leader is not member or party.phase not in (FORMING, COUNTDOWN, RESULTS):
            self.refuse(player, party)
            return
        self.stop_countdown(party)
        party.set_mode(mode)
        self.broadcast(party)

    def op_builders(self, player, member, party, fields):
        main, backup = fields["main"], fields["backup"]
        if main not in BUILDERS or backup not in BUILDERS:
            raise ProtocolError("PARTY builders outside its limits", protocol.ERRORS["out_of_limits"])
        if not party:
            self.refuse(player, party)
            return
        self.back_from_results(member)
        member.main, member.backup, member.ready = main, backup, False
        self.stop_countdown(party)
        self.broadcast(party)

    def op_ready(self, player, member, party, fields):
        on = self.bounded(fields["on"], 2)
        if not party:
            self.refuse(player, party)
            return
        self.back_from_results(member)
        if party.phase not in (FORMING, COUNTDOWN, RESULTS) or member.in_match:
            self.refuse(player, party)
            return
        member.ready = bool(on)
        if not on:
            self.stop_countdown(party)
        self.broadcast(party)

    def op_team(self, player, member, party, fields):
        number = self.bounded(fields["member"], MAX_MEMBERS)
        team = self.bounded(fields["team"], SPEC["max_teams"])
        target = party.members.get(number) if party else None
        if (not party or party.leader is not member or target is None or party.teams() < 2
                or party.phase not in (FORMING, COUNTDOWN, RESULTS)):
            self.refuse(player, party)
            return
        target.team, target.ready = team, False
        self.stop_countdown(party)
        self.broadcast(party)

    def op_open(self, player, member, party, fields):
        on = self.bounded(fields["on"], 2)
        if not party or party.leader is not member:
            self.refuse(player, party)
            return
        party.open = bool(on)
        self.broadcast(party)

    def op_start(self, player, member, party, fields):
        if not party or party.leader is not member:
            self.refuse(player, party)
            return
        if party.phase == LOADING and party.match and party.match.barrier.start_without(self.clock.now()):
            return
        if party.phase != FORMING or party.startable():
            self.refuse(player, party)
            return
        party.phase = COUNTDOWN
        party.countdown_end = self.clock.now() + COUNTDOWN_MS * MS
        party.timer = self.server.timers.at(party.countdown_end, lambda: self.countdown_done(party))
        self.server.event("countdown", party=party.code.decode())
        self.broadcast(party)

    def op_cancel(self, player, member, party, fields):
        if not party or party.phase != COUNTDOWN:
            self.refuse(player, party)
            return
        self.stop_countdown(party)
        self.broadcast(party)

    # -- the rules' helpers

    @staticmethod
    def mode(value):
        if value not in MODES:
            raise ProtocolError("PARTY mode outside its limits", protocol.ERRORS["out_of_limits"])
        return value

    @staticmethod
    def bounded(value, limit):
        if not 0 <= value < limit:
            raise ProtocolError("PARTY outside its limits", protocol.ERRORS["out_of_limits"])
        return value

    def stop_countdown(self, party):
        if party.phase == COUNTDOWN:
            if party.timer:
                party.timer.cancel()
            party.timer, party.countdown_end, party.phase = None, None, FORMING

    def leave(self, member, tell=True):
        """`member` out of its party: its row freed, the lead passed on, an
        empty party's code kept EXPIRY_MS."""
        party = member.party
        if party is None:
            return
        self.holds.cancel(member)
        player = member.player
        before = self.reloading(party)
        party.remove(member)
        if player:
            player.member = None
            if tell:
                self.send(player, no_party())
        self.server.event("party_leave", party=party.code.decode(), member=member.number)
        self.stop_countdown(party)
        if party.phase == RESULTS and not any(m.in_match for m in party.members.values()):
            party.phase = FORMING
        if not party.members:
            self.emptied(party, member.identity)
            return
        self.tell_reload(party, before)
        self.broadcast(party)

    # -- the bound on parties

    def room(self):
        """Whether a new party fits: under the cap, or once the empty party
        that has waited longest is dropped."""
        if len(self.parties) < self.server.party_cap:
            return True
        if not self.empty:
            return False
        self.drop(next(iter(self.empty.values())), "party_evicted")
        return True

    def emptied(self, party, identity):
        """`party`'s last member, of `identity`, left: its code kept EXPIRY_MS,
        and the empty party that identity left before dropped at once."""
        earlier = self.left_empty.get(identity)
        if earlier is not None and earlier is not party and not earlier.members:
            self.drop(earlier, "party_dropped")
        party.timer = self.server.timers.at(self.clock.now() + EXPIRY_MS * MS, lambda: self.expire(party))
        self.empty[party.code] = party
        self.left_empty[identity] = party
        party.emptied_by = identity

    def filled(self, party):
        """An empty party has a member again: it waits on nothing."""
        self.empty.pop(party.code, None)
        if self.left_empty.get(party.emptied_by) is party:
            del self.left_empty[party.emptied_by]
        party.emptied_by = None

    def drop(self, party, event):
        """An empty party gone before its code expires."""
        if party.timer:
            party.timer.cancel()
            party.timer = None
        self.filled(party)
        if self.parties.get(party.code) is party:
            del self.parties[party.code]
        self.server.event(event, party=party.code.decode())

    def expire(self, party):
        if party.members or self.parties.get(party.code) is not party:
            return
        party.timer = None
        self.drop(party, "party_expired")

    def countdown_done(self, party):
        if party.phase != COUNTDOWN or self.parties.get(party.code) is not party:
            return
        party.timer = party.countdown_end = None
        if party.startable():
            party.phase = FORMING
            self.broadcast(party)
            return
        members = party.seats()
        party.phase = LOADING
        for member in members:
            member.in_match, member.ready = True, False
        self.broadcast(party)
        party.match = self.server.form_match(
            MODES[party.mode][0], party.reference(), [member.player for member in members],
            seats=[dict(team=member.team, builder=member.main, flags=0) for member in members], party=party)

    # -- connections

    def hold(self, member):
        """`member`'s connection dropped without a goodbye: the row held."""
        party = member.party
        self.holds.hold(member)
        self.stop_countdown(party)
        self.broadcast(party)

    def take_back(self, member, player):
        self.holds.take_back(member, player)
        member.name, member.build_seq, member.rules_hash = player.name, player.build_seq, player.rules_hash
        member.ready = False
        # (a new connection is not on the results plate of a match that ended)
        self.back_from_results(member)

    def resume(self, player):
        """A resume HELLO: the identity's held row, if one is held, taken back."""
        member = self.holds.find(player.identity)
        if member is None:
            return
        before = self.reloading(member.party)
        self.take_back(member, player)
        self.tell_reload(member.party, before)
        self.broadcast(member.party)

    def heard_ping(self, player):
        """A PING's round trip shown to the party, at most every links_ms."""
        member = player.member
        if not member or member.party.phase in (LOADING, IN_MATCH):
            return
        if (player.round_trip != member.rtt_shown
                and self.clock.now() - member.party.rtt_sent >= SPEC["links_ms"] * MS):
            self.broadcast(member.party)

    def gone(self, player, goodbye):
        member = player.member
        if member is None:
            return
        if goodbye or player.refused or not self.holds.ms:
            self.leave(member, tell=False)
        else:
            self.hold(member)

    # -- the match and back

    def started(self, match):
        party = match.party
        if party and party.match is match:
            party.phase = IN_MATCH
            self.broadcast(party)

    def left_match(self, match, player):
        """A player out of its match before the end (LEAVE_MATCH, or out at
        the ceiling): back in the party's hub at once."""
        member = player.member
        party = match.party
        if not member or member.party is not party or not member.in_match:
            return
        member.in_match = member.ready = False
        self.broadcast(party)

    def ended(self, match):
        party = match.party
        if not party or party.match is not match:
            return
        party.match = None
        played = match.loop is not None
        finishers = set(match.finishers)
        for member in party.ordered():
            if member.in_match and member.player is None and self.holds.ms:
                self.holds.arm(member)      # (held through the match: HOLD_MS from its end)
            if member.in_match and not (played and member.player in finishers):
                member.in_match = member.ready = False
        party.phase = RESULTS if any(m.in_match for m in party.members.values()) else FORMING
        self.broadcast(party)

    def back_from_results(self, member):
        """A member on the results plate of a match that ended is back."""
        party = member.party
        if not member.in_match or party.match is not None:
            return False
        member.in_match = member.ready = False
        if party.phase == RESULTS and not any(m.in_match for m in party.members.values()):
            party.phase = FORMING
        return True

    def back(self, player):
        """LEAVE_MATCH after MATCH_END: Play again (or Hub) from the results."""
        member = player.member
        if member and self.back_from_results(member):
            self.broadcast(member.party)

    # -- the queue (M6)

    def queue(self, player, fields):
        if fields["op"] not in SPEC["queue_ops"].values():
            raise ProtocolError("QUEUE outside its limits", protocol.ERRORS["out_of_limits"])
        self.send(player, protocol.encode("QUEUE_STATE", state=SPEC["queue_states"]["idle"], elapsed_ms=0,
                                          caretaker_offer=0))

    def accept(self, player, fields):
        if fields["yes"] > 1:
            raise ProtocolError("ACCEPT outside its limits", protocol.ERRORS["out_of_limits"])

    async def close(self):
        for party in self.parties.values():
            if party.timer:
                party.timer.cancel()
        with contextlib.suppress(Exception):
            self.holds.close()
