"""A player whose match is running cannot form, join, leave or start a party
(review round 1): the server refuses PARTY create, join, leave and start with
the party as it is, so one connection never sits in two matches. The shipped
game sends LEAVE_MATCH before any of these; a modified one that does not must
not leave a match sealing turns for nobody until its one-hour cap."""

import unittest

from support import MODES, PHASES, RULES, TICK0, HubTest, party, until
from groundhold_server.protocol import SPEC

SKIP = ("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE", "PONG")


class PartyOpsInMatchTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def playing(self, clients):
        await self.ready_all(clients)
        await self.to_loading(clients)
        for client in clients:
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for client in clients:
            await client.until("START", skip=("LOAD_STATE",))
        await self.everyone(clients)
        await self.clock.advance(SPEC["start_delay_ms"])

    async def solo_match(self, client):
        """A party of one to its running match: create, start, the countdown, LOADED."""
        await party(client, "create", mode=MODES["high_water"])
        await client.until("PARTY_STATE", skip=SKIP[:2])
        await party(client, "start")
        await client.until("PARTY_STATE", skip=SKIP[:2])
        await self.clock.advance(3000)
        await client.until("MATCH_CONFIG", skip=SKIP)
        await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await client.until("START", skip=SKIP)
        await self.clock.advance(SPEC["start_delay_ms"])

    async def test_create_join_leave_and_start_are_refused_while_the_match_runs(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await self.playing((tamsin, edda))
        first = self.match()
        before = self.server.lobby.parties[code]
        for op, fields in (("create", dict(mode=MODES["high_water"])), ("join", dict(code=code)),
                           ("leave", {}), ("start", {})):
            await party(edda, op, **fields)
            refused = await edda.until("PARTY_STATE", skip=SKIP[:2])
            self.assertEqual((refused["code"], refused["phase"]), (code, PHASES["in_match"]),
                             f"PARTY {op} mid-match answers with the party as it is")
        await self.clock.advance(3000)
        self.assertEqual(list(self.server.matches), [first.id], "no second match formed")
        self.assertEqual(list(self.server.lobby.parties), [code], "no second party formed")
        self.assertIs(before.members[1].player.match, first)

    async def test_one_connection_cannot_pile_up_matches(self):
        """The reproduction: create and start again and again from inside a
        match, then drop. Every match must end once nobody is left."""
        await self.start()
        edda = await self.join("Edda", 2)
        await self.solo_match(edda)
        for _ in range(3):
            await party(edda, "create", mode=MODES["high_water"])
            await edda.until("PARTY_STATE", skip=SKIP[:2])
            await party(edda, "start")
            await edda.until("PARTY_STATE", skip=SKIP[:2])
            await self.clock.advance(3000)
        self.assertEqual(len(self.server.matches), 1)
        await edda.drop()
        await until(lambda: not self.server.players)
        await self.clock.turns(5)
        self.assertEqual(self.server.health()["matches"], 0, "no match seals turns for nobody")

    async def test_the_leader_still_starts_without_a_stuck_member(self):
        """Start without (design §6.6) is a PARTY start from inside the loading match: still taken."""
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        await tamsin.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(30_000)
        await party(tamsin, "start")
        await tamsin.until("START", skip=SKIP)
        self.assertEqual(len(self.server.matches), 1)


if __name__ == "__main__":
    unittest.main()
