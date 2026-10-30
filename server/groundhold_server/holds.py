"""A party seat held through a dropped link (docs/design/core-loop.md §5.2,
§6.10; Appendix A: 40 s).

A connection that ends without a goodbye (BYE, or a WebSocket close)
keeps its party row for HOLD_MS: the others see it "away" (the hub reads
"reconnecting"), and a countdown under way stops, since a held member
cannot play. A HELLO from the same public identity with the resume bit
takes the row back, or a PARTY join of the same code does: Builders,
team, row and place in the leader's line all as they were (Ready is
cleared: the player was away). A goodbye, a refusal or a moderator's
removal frees the row at once.

A match seat is held until the match ends (match.py: AWAY, the caretaker
plays it). A party row whose match still runs is not let go while the
match runs: it gets HOLD_MS again from the match's end, so a player who
dropped during a long match can still come back to the party after it.

Adapted from Cyberworld Endless's server/cyberworld_server/holds.py (MIT,
Sascha Becker): the 40 s, the resume bit, the goodbye that frees at once;
a Square's place became a party's row, and the deadline runs on the
server's clock (a test moves it by hand).
"""

HOLD_MS = 40_000
MS = 1_000_000


class Holds:
    def __init__(self, server, ms=HOLD_MS):
        self.server, self.ms = server, ms
        self.timers = {}            # member -> its expiry's timer

    def held(self, member):
        return member in self.timers

    def hold(self, member):
        """`member`'s connection dropped: the row kept HOLD_MS."""
        member.player = None
        member.ready = False
        self.arm(member)
        self.server.event("hold", party=member.party.code.decode(), member=member.number, seconds=self.ms // 1000)

    def arm(self, member):
        self.cancel(member)
        deadline = self.server.clock.now() + self.ms * MS
        self.timers[member] = self.server.timers.at(deadline, lambda: self.expired(member))

    def cancel(self, member):
        timer = self.timers.pop(member, None)
        if timer:
            timer.cancel()

    def expired(self, member):
        party = member.party
        if party is not None and member.player is None and member.in_match and party.match is not None:
            # (held through the match: still found by a resume or a join by
            # code, with no timer; the lobby arms it again as the match ends)
            self.timers[member] = None
            return
        self.timers.pop(member, None)
        if party is None or member.player is not None:
            return
        self.server.event("hold_ended", party=party.code.decode(), member=member.number)
        self.server.lobby.leave(member)

    def find(self, identity, party=None):
        """A held row of `identity` (in `party`, where given), else None."""
        for member in self.timers:
            if member.identity == identity and (party is None or member.party is party):
                return member
        return None

    def take_back(self, member, player):
        """`player`, a new connection of the same identity, takes the row."""
        self.cancel(member)
        member.player = player
        player.member = member
        self.server.daily.count("reconnects")
        self.server.event("resume", party=member.party.code.decode(), member=member.number,
                          identity=member.identity.hex())

    def close(self):
        for member in list(self.timers):
            self.cancel(member)
