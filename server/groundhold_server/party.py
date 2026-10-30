"""A party on the server (docs/design/core-loop.md §5.2, §6.10): who plays
together, as whom, in which mode, and whether they are ready.

The rules, all the server's:

- The creator leads. If the leader leaves, the member who joined earliest
  leads. The leader picks the mode, open seats and teams, and can remove a
  member, who cannot rejoin that code. Members change only their own
  Builders (main and backup) and Ready; the leader's Ready is its Start.
- Changing the mode clears every Ready; changing your Builders clears
  yours; moving a member to another team clears theirs.
- Start, with every other member Ready, everyone on one rules hash, and the
  party a size the mode takes (two equal teams for a Race), counts 3 s down;
  anyone can cancel, and anything that breaks the rule stops it.
- A member who drops keeps the row for 40 s ("reconnecting", holds.py).
- An empty party's code lives 15 minutes, then expires.

`rules_hash` is a matchmaking key, not a refusal (§6.9): a member whose
hash differs from the newest build's (the highest `build_seq`, the leader's
on a tie) "needs to reload", and the party cannot start until they do.

This module holds a party's state and its rules; lobby.py runs the ops,
the countdown and the matches. Its in-memory ask, answer and expiry follow
the pattern of Cyberworld Endless's teams.py (MIT, Sascha Becker).
"""

import dataclasses

from . import codes, protocol
from .protocol import SPEC

PHASES = SPEC["party_phases"]
FORMING, COUNTDOWN, QUEUED, LOADING, IN_MATCH, RESULTS = (
    PHASES[name] for name in ("forming", "countdown", "queued", "loading", "in_match", "results"))
STATES = SPEC["member_states"]
FLAGS = SPEC["party_flags"]
MODES = {spec["id"]: (name, spec) for name, spec in SPEC["modes"].items()}
BUILDERS = frozenset(SPEC["builders"].values())
MAX_MEMBERS = SPEC["max_seats"]
NOBODY = 255                    # PARTY_STATE's leader (or you) where there is no such member
COUNTDOWN_MS = 3000
EXPIRY_MS = 15 * 60 * 1000
MS = 1_000_000


@dataclasses.dataclass(eq=False)
class Member:
    number: int                 # the row, 0 to 3, kept while the member stays
    order: int                  # when it joined: the earliest leads after the leader
    player: object              # its connection; None while the row is held (holds.py)
    identity: bytes
    name: str
    build_seq: int
    rules_hash: bytes
    party: object = None
    team: int = 0
    main: int = SPEC["builders"]["lamplighter"]
    backup: int = SPEC["builders"]["lookout"]
    ready: bool = False
    in_match: bool = False      # in the party's match, or on its results plate
    rtt_shown: int = 0          # its round trip as the last PARTY_STATE showed it


class Party:
    def __init__(self, code, mode, lan=False):
        self.code, self.mode, self.lan = code, mode, lan
        self.open = False
        self.members = {}           # number -> Member
        self.leader = None
        self.phase = FORMING
        self.countdown_end = None   # the server clock's ns when the countdown ends
        self.removed = set()        # identities the leader removed: they cannot rejoin
        self.match = None
        self.joins = 0
        self.timer = None           # the countdown's or the empty code's expiry
        self.emptied_by = None      # the identity that left it empty, while it is
        self.rtt_sent = 0           # the clock's ns of the last state sent for round trips alone

    # -- who

    def mode_spec(self):
        return MODES[self.mode][1]

    def teams(self):
        return self.mode_spec()["teams"]

    def connected(self):
        return [member for member in self.ordered() if member.player is not None]

    def ordered(self):
        return [self.members[number] for number in sorted(self.members)]

    def add(self, player, identity, name, build_seq, rules_hash):
        number = min(set(range(MAX_MEMBERS)) - set(self.members))
        member = Member(number, self.joins, player, identity, name, build_seq, rules_hash, party=self)
        self.joins += 1
        if self.teams() > 1:
            sizes = [sum(1 for m in self.members.values() if m.team == team) for team in range(self.teams())]
            member.team = sizes.index(min(sizes))
        self.members[number] = member
        if self.leader is None:
            self.leader = member
        return member

    def remove(self, member):
        """The member out; the earliest to join leads if it led."""
        del self.members[member.number]
        member.party = None
        if self.leader is member:
            self.leader = min(self.members.values(), key=lambda m: m.order) if self.members else None

    def reference(self):
        """The rules hash the party plays: the newest build's."""
        if not self.members:
            return None
        newest = max(self.members.values(), key=lambda m: (m.build_seq, m is self.leader, -m.order))
        return newest.rules_hash

    def needs_reload(self, member):
        return member.rules_hash != self.reference()

    def state(self, member):
        if member.player is None:
            return STATES["away"]
        if member.in_match:
            return STATES["in_match"]
        if self.needs_reload(member):
            return STATES["needs_reload"]
        return STATES["ready"] if member.ready else STATES["here"]

    # -- the rules

    def set_mode(self, mode):
        """The mode changed: every Ready cleared, the teams laid out again."""
        self.mode = mode
        for member in self.members.values():
            member.ready = False
        self.lay_out_teams()

    def lay_out_teams(self):
        """One team: everyone on it. Two: alternate by when they joined."""
        teams = self.teams()
        for index, member in enumerate(sorted(self.members.values(), key=lambda m: m.order)):
            member.team = index % teams if teams > 1 else 0

    def startable(self):
        """Why the party cannot start now ("" where it can)."""
        members = self.ordered()
        low, high = self.mode_spec()["seats"]
        if any(member.player is None for member in members):
            return "reconnecting"
        if any(member.in_match for member in members):
            return "in a match"
        if any(self.needs_reload(member) for member in members):
            return "needs to reload"
        if any(not member.ready for member in members if member is not self.leader):
            return "not ready"
        if not low <= len(members) <= high:
            return "seats"
        if self.teams() > 1:
            sizes = [sum(1 for m in members if m.team == team) for team in range(self.teams())]
            if min(sizes) == 0 or len(set(sizes)) != 1:
                return "teams"
        return ""

    def seats(self):
        """The members in seat order: by team, then by row (a Race of four is
        seats 0 and 1 against 2 and 3, as the wire's seat rule has it)."""
        return sorted(self.members.values(), key=lambda m: (m.team, m.number))

    def open_seat(self):
        """Open seats on and a seat free (the beacon's count)."""
        return self.open and len(self.members) < MAX_MEMBERS and self.phase in (FORMING, COUNTDOWN, QUEUED)

    # -- the wire

    def encode(self, now, you=NOBODY):
        """PARTY_STATE: the whole party as it is now, for the member numbered `you` (its
        game finds its own row by it; NOBODY for someone outside the party)."""
        left = max(0, -((now - self.countdown_end) // MS)) if self.phase == COUNTDOWN and self.countdown_end else 0
        members = [dict(member=m.number, team=m.team, main=m.main, backup=m.backup, state=self.state(m),
                        rtt_ms=min(0xffff, m.player.round_trip) if m.player else 0, build_seq=m.build_seq,
                        rules_hash=m.rules_hash, name=m.name) for m in self.ordered()]
        return protocol.encode("PARTY_STATE", code=self.code, mode=self.mode,
                               flags=(FLAGS["open"] if self.open else 0) | (FLAGS["lan"] if self.lan else 0),
                               leader=self.leader.number if self.leader else NOBODY, you=you, phase=self.phase,
                               countdown_ms=min(0xffffffff, left), members=members)


def no_party():
    """PARTY_STATE for a player in no party: five zero bytes for the code, no members."""
    return protocol.encode("PARTY_STATE", code=codes.NONE, mode=0, flags=0, leader=NOBODY, you=NOBODY, phase=FORMING,
                           countdown_ms=0, members=[])
