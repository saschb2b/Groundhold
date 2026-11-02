"""The public queue (docs/design/core-loop.md §5.1, §5.2, §5.5, §3.6;
contract-m6.md §6): parties that want strangers, Match Found, and the
caretakers offered after a minute.

**Who queues.** The leader of a forming party with every other member
Ready, nobody away, in a match or on another rules hash (the start's rule,
less the size): `QUEUE enter`. In a one-team mode (High Water) the party
has open seats on and a seat free, and the queue fills them with strangers
up to the mode's most seats (**Find players**). In a two-team mode (Tide
Race, Undertow) the party is one team of at most half the seats (1 or 2 in
a race; 1 in Undertow's duel, M7, whose seats are [2, 2]), and the queue
finds one rival team of the same size (**Find a rival**). Parties
merge only with the same mode, the same rules hash (the newest build's,
`Party.reference`) and the same level (M8, contract-m8.md §3: the level the
match plays, `Party.level`, so every duellist meets at Normal whatever its
party chose). The party's phase is `queued`; every member hears
`QUEUE_STATE queued` with the time since it queued.

**The order.** Tickets wait in the order they came; a ticket requeued after
a match dissolved goes to the **front**, before every ticket waiting, and
keeps its time ("You keep your place"). Each time a ticket comes the queue
looks for matches from the front: High Water takes each ticket in turn as
the first and adds the tickets after it that fit (first fit) until the seats
are full: of the ways to fill them, the one whose tickets came earliest; a
Race pairs the first ticket with the next of the same size. The front
ticket goes first whenever its match can be made; one that cannot be
completed yet lets those behind it match.

**Match Found.** A match of strangers always asks first: `MATCH_FOUND`
(its match id, mode, seats, how many accepted and the ms left of
`accept_ms`, 15 s by the server's clock) to every player, again at every
accept. Everyone's `ACCEPT yes` forms the match (`MATCH_CONFIG`; a strangers'
barrier: 45 s start with the seats loaded, 120 s ceiling). An `ACCEPT no`
(or `QUEUE leave`, a leave or a drop) or the 15 s running out dissolves it:
each party with a player who did not accept goes back to `forming` (those
players' Ready cleared, `QUEUE_STATE idle`); the others go back to the front
of the queue with `NOTICE match_dissolved` and `QUEUE_STATE queued`.

**Builders between strangers** (§3.6). Duplicates are allowed inside a
party and avoided between strangers who share a team: whoever queued first
keeps their main, a later stranger whose main is taken plays their backup,
and one whose backup is taken too a free Builder drawn from the server's
random number generator (`Server.queue_rng`). The server writes the result
into `MATCH_CONFIG`; no game rolls. (In a Race or a duel each team is one
party and plays its own hollow, so every seat keeps its main: a clash never
crosses the sides.)

**Caretakers.** `caretaker_offer_ms` (60 s) after a ticket came,
`QUEUE_STATE` sets `caretaker_offer` and every member hears `NOTICE
caretakers_offered`. Then the leader's `QUEUE start_with_caretakers` starts
at once, the party's own match: High Water fills the free seats with
caretakers whose Builders cover the checks the party lacks (the most lacking
covered first, then a Builder not yet on the team, ties in BUILDER_IDS
order); a Race sets a caretaker rival team against it with the same
Builders, a mirror, and a duel so one caretaker of the duellist's own
Builder on team 1 (Duel the caretaker). A caretaker's seat has the `caretaker` flag in
`MATCH_CONFIG`: nobody plays it, the simulation's caretaker does from tick 0. The
match plays the party's level, as a match the queue found plays its key's.

**Afterwards** each party is its own again on its results plate (lobby.py).
A strangers' match nobody loaded within the 120 s ceiling is dissolved
(`NOTICE match_dissolved`), and the parties all of whose members are still
connected go back to the front of the queue.

Every timer runs on `server.clock` (server.timers), so a test moves it by
hand. New in Groundhold: Cyberworld has no matchmaking.
"""

import dataclasses
import itertools
import secrets

from . import protocol
from .party import FORMING, LOADING, MODES, QUEUED
from .protocol import ProtocolError, SPEC

MS = 1_000_000
OPS = SPEC["queue_ops"]
STATES = SPEC["queue_states"]
NOTICES = SPEC["notices"]
CARETAKER = SPEC["seat_flags"]["caretaker"]
BUILDER_IDS = sorted(SPEC["builders"], key=SPEC["builders"].get)
# (each Builder's covers, the checks it is strong against: scripts/sim/content.gd BUILDERS,
# which test_queue holds this to)
COVERS = {
    "lamplighter": ("swarm", "swift"),
    "lookout": ("armored", "winged"),
    "bellfounder": ("swift", "armored"),
    "beekeeper": ("swarm", "winged"),
}
CHECKS = ("swarm", "swift", "armored", "winged")


@dataclasses.dataclass(eq=False)
class Ticket:
    """A party waiting in the queue."""
    party: object
    mode: str                   # the mode's name (protocol.json "modes")
    rules: bytes                # the party's rules hash as it queued: the key, with the mode
    level: int                  # the level the party's match plays (Party.level): the key's third part
    since: int                  # the server clock's ns it queued; kept when it is requeued
    order: int                  # its place: lower first (a requeue at the front is negative)
    offered: bool = False       # caretaker_offer_ms passed
    told: bool = False          # NOTICE caretakers_offered sent
    timer: object = None        # the caretaker offer's
    found: object = None        # the Found it waits on, if any

    def size(self):
        return len(self.party.members)


@dataclasses.dataclass(eq=False)
class Found:
    """A match the queue found, waiting for every player's accept."""
    id: int                     # the match id MATCH_FOUND and ACCEPT name, and MATCH_CONFIG then
    mode: str
    rules: bytes
    level: int
    tickets: list               # in seat order: the earliest queued first
    deadline: int               # the server clock's ns accept_ms after it was found
    accepted: set = dataclasses.field(default_factory=set)     # the members (party.Member) who accepted
    timer: object = None

    def members(self):
        return [member for ticket in self.tickets for member in ticket.party.ordered()]


class Queue:
    def __init__(self, lobby):
        self.lobby = lobby
        self.tickets = {}           # party -> Ticket, waiting or in a Found
        self.found = {}             # match id -> Found
        self.back = itertools.count(1)
        self.front = itertools.count(-1, -1)

    @property
    def server(self):
        return self.lobby.server

    @property
    def clock(self):
        return self.lobby.server.clock

    # -- the wire

    def state(self, party):
        """QUEUE_STATE for `party`'s members now."""
        ticket = self.tickets.get(party) if party else None
        if ticket is None:
            return protocol.encode("QUEUE_STATE", state=STATES["idle"], elapsed_ms=0, caretaker_offer=0)
        elapsed = (self.clock.now() - ticket.since) // MS
        return protocol.encode("QUEUE_STATE", state=STATES["queued"], elapsed_ms=min(0xffffffff, elapsed),
                               caretaker_offer=int(ticket.offered))

    def tell(self, party, data=None):
        data = data or self.state(party)
        for member in party.ordered():
            if member.player:
                self.lobby.send(member.player, data)

    def notice(self, party, name):
        for member in party.ordered():
            if member.player:
                self.lobby.notice(member.player, name)

    def found_message(self, found):
        left = max(0, (found.deadline - self.clock.now()) // MS)
        return protocol.encode("MATCH_FOUND", match=found.id, mode=SPEC["modes"][found.mode]["id"],
                               seats=len(found.members()), accepted=len(found.accepted), ms_left=left)

    # -- QUEUE

    def op(self, player, fields):
        op = fields["op"]
        if op not in OPS.values():
            raise ProtocolError("QUEUE outside its limits", protocol.ERRORS["out_of_limits"])
        member = player.member
        party = member.party if member else None
        if op == OPS["enter"]:
            self.enter(player, member, party)
        elif op == OPS["leave"]:
            self.leave(player, member, party)
        else:
            self.with_caretakers(player, member, party)

    def refusal(self, party, ready=True):
        """Why `party` cannot queue now ("" where it can); `ready` False
        leaves Ready out (a party the queue takes back after a match that
        never played)."""
        if party.phase != FORMING:
            return "phase"
        members = party.ordered()
        if any(member.player is None for member in members):
            return "reconnecting"
        if any(member.in_match for member in members):
            return "in a match"
        if any(party.needs_reload(member) for member in members):
            return "needs to reload"
        if ready and any(not member.ready for member in members if member is not party.leader):
            return "not ready"
        low, high = party.mode_spec()["seats"]
        if party.teams() == 1:
            if not party.open:
                return "open seats off"
            if len(members) >= high:
                return "no seat free"
        else:
            if len({member.team for member in members}) != 1:
                return "two teams"
            if len(members) * party.teams() > high or len(members) * party.teams() < low:
                return "team size"
        return ""

    def enter(self, player, member, party):
        if party is None or party.leader is not member or party in self.tickets or self.refusal(party):
            # (not the leader's to ask, or not now: the queue as it is, to the asker)
            self.lobby.send(player, self.state(party))
            return
        now = self.clock.now()
        ticket = Ticket(party, MODES[party.mode][0], party.reference(), party.level(), now, next(self.back))
        ticket.timer = self.server.timers.at(now + SPEC["caretaker_offer_ms"] * MS, lambda: self.offer(ticket))
        self.tickets[party] = ticket
        party.phase = QUEUED
        self.server.event("queue", party=party.code.decode(), mode=ticket.mode,
                          level=protocol.DIFFICULTY_NAMES[ticket.level], size=ticket.size())
        self.lobby.broadcast(party)
        self.tell(party)
        self.look()

    def leave(self, player, member, party):
        ticket = self.tickets.get(party) if party else None
        if ticket is None or party.leader is not member:
            self.lobby.send(player, self.state(party))
            return
        if ticket.found:
            self.dissolve(ticket.found, {member})       # (a leave in Match Found is a decline)
            return
        self.out(ticket, "queue_leave")

    def with_caretakers(self, player, member, party):
        ticket = self.tickets.get(party) if party else None
        if ticket is None or party.leader is not member or ticket.found or not ticket.offered:
            self.lobby.send(player, self.state(party))
            return
        self.forget(ticket)
        members = party.seats()
        race = party.teams() > 1
        seats = [dict(team=0 if race else member.team, builder=member.main, flags=0) for member in members]
        if race:
            builders = [member.main for member in members]
            team = 1
        else:
            builders = caretaker_builders([member.main for member in members],
                                          party.mode_spec()["seats"][1] - len(members))
            team = 0
        seats += [dict(team=team, builder=builder, flags=CARETAKER, name="Caretaker %d" % (index + 1))
                  for index, builder in enumerate(builders)]
        self.server.event("caretakers", party=party.code.decode(), mode=ticket.mode, caretakers=len(builders))
        self.lobby.to_loading([party])
        party.match = self.server.form_match(
            ticket.mode, ticket.rules, [member.player for member in members] + [None] * len(builders),
            seats=seats, party=party, level=ticket.level)

    # -- the queue's own

    def offer(self, ticket):
        """caretaker_offer_ms after it came: the caretakers are offered."""
        if self.tickets.get(ticket.party) is not ticket:
            return
        ticket.timer = None
        ticket.offered = True
        if ticket.found is None:
            self.say_offer(ticket)

    def say_offer(self, ticket):
        if ticket.offered and not ticket.told:
            ticket.told = True
            self.notice(ticket.party, "caretakers_offered")
        self.tell(ticket.party)

    def forget(self, ticket):
        """The ticket out of the queue (its party's phase is the caller's)."""
        if self.tickets.get(ticket.party) is ticket:
            del self.tickets[ticket.party]
        if ticket.timer:
            ticket.timer.cancel()
            ticket.timer = None

    def out(self, ticket, event, broadcast=True):
        """The party out of the queue, back to forming: QUEUE_STATE idle to
        its members, then its PARTY_STATE (unless the caller sends that)."""
        party = ticket.party
        self.forget(ticket)
        if party.phase == QUEUED:
            party.phase = FORMING
        self.server.event(event, party=party.code.decode())
        self.tell(party)
        if broadcast:
            self.lobby.broadcast(party)

    def interrupted(self, party, member=None):
        """Something broke the queue's rule for `party` (a join, a leave, a
        drop, open seats off): out of the queue, QUEUE_STATE idle to its
        members; the caller sends its PARTY_STATE. In Match Found it is that
        party's decline (`member`, if one broke it, has its Ready cleared)."""
        ticket = self.tickets.get(party)
        if ticket is None:
            return False
        if ticket.found:
            self.dissolve(ticket.found, {member} if member else set(), refusing={party}, quiet={party})
        else:
            self.out(ticket, "queue_out", broadcast=False)
        return True

    def waiting(self, mode, rules, level):
        """The tickets waiting for a match of `mode`, `rules` and `level`, in the queue's order."""
        return sorted((t for t in self.tickets.values()
                       if t.found is None and (t.mode, t.rules, t.level) == (mode, rules, level)),
                      key=lambda t: t.order)

    def look(self):
        """Matches from the front of the queue, as long as one can be found."""
        while True:
            keys = sorted({(t.mode, t.rules, t.level) for t in self.tickets.values() if t.found is None})
            group = next((g for g in (self.group(*key) for key in keys) if g), None)
            if group is None:
                return
            self.found_match(group)

    def group(self, mode, rules, level):
        """The first match the waiting tickets of a key make, or None: each
        ticket in the queue's order as the first, with the earliest tickets
        after it that fill the seats (High Water) or the next team of its
        size (a Race)."""
        waiting = self.waiting(mode, rules, level)
        spec = SPEC["modes"][mode]
        for index, head in enumerate(waiting):
            later = waiting[index + 1:]
            if spec["teams"] > 1:
                rival = next((t for t in later if t.size() == head.size()), None)
                if rival:
                    return [head, rival]
                continue
            fill = earliest_fill(later, spec["seats"][1] - head.size())
            if fill is not None:
                return [head] + fill
        return None

    def found_match(self, tickets):
        """MATCH_FOUND to everyone in `tickets`; the 15 s begin."""
        tickets = sorted(tickets, key=lambda t: (t.since, t.order))
        found = Found(self.server.reserve_match_id(), tickets[0].mode, tickets[0].rules, tickets[0].level, tickets,
                      self.clock.now() + SPEC["accept_ms"] * MS)
        for ticket in tickets:
            ticket.found = found
        found.timer = self.server.timers.at(found.deadline, lambda: self.timeout(found))
        self.found[found.id] = found
        self.server.event("match_found", match=found.id, mode=found.mode, level=protocol.DIFFICULTY_NAMES[found.level],
                          parties=len(tickets), seats=len(found.members()))
        self.tell_found(found)

    def tell_found(self, found):
        data = self.found_message(found)
        for member in found.members():
            if member.player:
                self.lobby.send(member.player, data)

    # -- ACCEPT

    def accept(self, player, fields):
        if fields["yes"] > 1:
            raise ProtocolError("ACCEPT outside its limits", protocol.ERRORS["out_of_limits"])
        member = player.member
        found = self.found.get(fields["match"])
        if found is None or member is None or member not in found.members():
            return      # (an answer to a match already gone, or not this player's: let pass)
        if not fields["yes"]:
            self.dissolve(found, {member})
            return
        if member in found.accepted:
            return
        found.accepted.add(member)
        self.server.event("accept", match=found.id, accepted=len(found.accepted))
        if len(found.accepted) == len(found.members()):
            self.launch(found)
        else:
            self.tell_found(found)

    def timeout(self, found):
        if self.found.get(found.id) is not found:
            return
        found.timer = None
        self.dissolve(found, set(found.members()) - found.accepted)

    def dissolve(self, found, refusers, refusing=(), quiet=()):
        """The match is off: each party with a refuser (a decline, a leave, a
        member who did not accept in time), and each of `refusing`, back to
        forming, the refusers' Ready cleared; the others to the front of the
        queue, keeping their time, with NOTICE match_dissolved. `quiet`: the
        parties whose PARTY_STATE the caller sends."""
        if self.found.pop(found.id, None) is not found:
            return
        if found.timer:
            found.timer.cancel()
        self.server.event("dissolved", match=found.id)
        kept = []
        for ticket in found.tickets:
            ticket.found = None
            party = ticket.party
            mine = [member for member in party.ordered() if member in refusers]
            if mine or party in refusing:
                for member in mine:
                    member.ready = False
                self.out(ticket, "queue_out", broadcast=party not in quiet)
            else:
                kept.append(ticket)
        for ticket in reversed(kept):
            ticket.order = next(self.front)
        for ticket in kept:
            self.notice(ticket.party, "match_dissolved")
            self.say_offer(ticket)
        self.look()

    def launch(self, found):
        """Everyone accepted: the match forms, a match of strangers."""
        self.found.pop(found.id, None)
        if found.timer:
            found.timer.cancel()
        for ticket in found.tickets:
            self.forget(ticket)
        members, seats = [], []
        race = SPEC["modes"][found.mode]["teams"] > 1
        chosen = builders_for([ticket.party.seats() for ticket in found.tickets], not race, self.server.queue_rng)
        for team, (ticket, picks) in enumerate(zip(found.tickets, chosen)):
            for member, builder in zip(ticket.party.seats(), picks):
                members.append(member)
                seats.append(dict(team=team if race else 0, builder=builder, flags=0))
        parties = [ticket.party for ticket in found.tickets]
        self.lobby.to_loading(parties)
        since = {ticket.party: ticket.since for ticket in found.tickets}
        told = {ticket.party for ticket in found.tickets if ticket.told}
        match = self.server.form_match(found.mode, found.rules, [member.player for member in members],
                                       seats=seats, parties=parties, match_id=found.id, level=found.level)
        match.queued_since, match.queued_told = since, told
        for party in parties:
            party.match = match

    # -- after a match

    def dissolved_unplayed(self, match):
        """A strangers' match from the queue that nobody loaded within the
        ceiling: the parties still whole back to the front of the queue,
        with the time they had (the barrier said match_dissolved); a party
        already told of the caretakers is not told again."""
        since = match.queued_since
        if not since:
            return
        kept = []
        for party in match.parties:
            if (party in self.tickets or self.lobby.parties.get(party.code) is not party
                    or self.refusal(party, ready=False)):
                continue
            ticket = Ticket(party, match.mode, party.reference(), match.level, since[party], 0,
                            told=party in match.queued_told)
            elapsed_ok = self.clock.now() - ticket.since >= SPEC["caretaker_offer_ms"] * MS
            ticket.offered = elapsed_ok
            if not elapsed_ok:
                ticket.timer = self.server.timers.at(ticket.since + SPEC["caretaker_offer_ms"] * MS,
                                                     lambda ticket=ticket: self.offer(ticket))
            self.tickets[party] = ticket
            party.phase = QUEUED
            kept.append(ticket)
        for ticket in reversed(kept):
            ticket.order = next(self.front)
        for ticket in kept:
            self.lobby.broadcast(ticket.party)
            self.say_offer(ticket)
        self.look()


def parts(need, largest=None):
    """Every way to write `need` as a sum of party sizes, largest first: 3 is
    (3,), (2, 1), (1, 1, 1)."""
    largest = need if largest is None else largest
    if need == 0:
        yield ()
        return
    for size in range(min(need, largest), 0, -1):
        for rest in parts(need - size, size):
            yield (size,) + rest


def earliest_fill(tickets, need):
    """The tickets (in their order) whose sizes add up to `need` and came
    earliest: of every way to fill the seats, the one whose places in the
    queue, sorted, come first. None when nothing fills them."""
    if need <= 0:
        return None
    places = {}
    for index, ticket in enumerate(tickets):
        places.setdefault(ticket.size(), []).append(index)
    best = None
    for sizes in parts(need):
        chosen = []
        for size in set(sizes):
            count = sizes.count(size)
            if len(places.get(size, ())) < count:
                break
            chosen += places[size][:count]
        else:
            chosen.sort()
            if best is None or chosen < best:
                best = chosen
    return None if best is None else [tickets[index] for index in best]


def builders_for(teams, avoid, rng=None):
    """Each seat's Builder, per party (`teams`: each party's members in seat
    order, the earliest queued first). With `avoid` (strangers on one team) a
    Builder an earlier party plays is not played again: the main where it is
    free, else the backup, else a free one drawn by `rng` (BUILDER_IDS order
    to draw from). Inside a party duplicates stay."""
    taken, out = set(), []
    choose = (rng or secrets.SystemRandom()).choice
    for members in teams:
        picks = []
        for member in members:
            if not avoid or member.main not in taken:
                picks.append(member.main)
            elif member.backup not in taken:
                picks.append(member.backup)
            else:
                free = [SPEC["builders"][name] for name in BUILDER_IDS if SPEC["builders"][name] not in taken]
                picks.append(choose(free) if free else member.main)
        out.append(picks)
        taken.update(picks)
    return out


def caretaker_builders(mains, count):
    """`count` caretakers' Builders (wire ids) for a team of `mains`: each in
    turn the one covering most of the checks the team lacks, then one not on
    the team yet, ties in BUILDER_IDS order."""
    team = [BUILDER_IDS[builder] for builder in mains]
    out = []
    for _ in range(count):
        lacking = {check for check in CHECKS if not any(check in COVERS[name] for name in team)}
        best = min(BUILDER_IDS, key=lambda name: (-len(lacking.intersection(COVERS[name])), name in team,
                                                  BUILDER_IDS.index(name)))
        team.append(best)
        out.append(SPEC["builders"][best])
    return out
