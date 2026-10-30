"""A party row held through a dropped link (docs/design/core-loop.md §5.2,
§6.10, Appendix A: 40 s): the row stays "away", a resume HELLO or a join of
the same code takes it back, a goodbye frees it at once, and a row whose
match still runs is kept until 40 s after the match ends.

Adapted from Cyberworld Endless's server/tests/test_holds.py (MIT, Sascha
Becker): a Square's place became a party's row, on the server's clock."""

import unittest

from support import BUILDERS, MEMBER, PHASES, TICK0, RULES, Client, HubTest, party, state, states, until
from groundhold_server.protocol import SPEC

RESUME = SPEC["hello_flags"]["resume"]


class HoldTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_dropped_member_keeps_its_row_forty_seconds(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        await tamsin.drop()
        held = await self.everyone((edda, ottilie))
        self.assertEqual(states(held[0]), {"Tamsin": MEMBER["away"], "Edda": MEMBER["here"], "Ottilie": MEMBER["here"]})
        self.assertEqual(held[0]["leader"], 0)          # (the leader's row, lead and all, waits for it)
        await self.clock.advance(40_000 - 1)
        self.assertTrue(await edda.quiet())
        await self.clock.advance(1)
        freed = await self.everyone((edda, ottilie))
        self.assertEqual(([m["name"] for m in freed[0]["members"]], freed[0]["leader"]), (["Edda", "Ottilie"], 1))

    async def test_a_resume_hello_takes_the_row_back(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await party(edda, "builders", main=BUILDERS["lookout"], backup=BUILDERS["lamplighter"])
        await self.everyone((tamsin, edda))
        await edda.drop()
        await state(tamsin)
        await self.clock.advance(39_000)
        again = Client()
        self.clients.append(again)
        welcome = await again.hello(self.port, "Edda", token=bytes((2,)) * 16, flags=RESUME)
        self.assertEqual((welcome[0], welcome[1]["identity"]), ("WELCOME", edda.welcome["identity"]))
        back = await state(again)
        self.assertEqual(back["code"], code)
        row = back["members"][1]
        self.assertEqual((row["member"], row["name"], row["main"], row["state"]),
                         (1, "Edda", BUILDERS["lookout"], MEMBER["here"]))
        self.assertEqual(back["you"], 1)                # (the row it took back is its own)
        self.assertEqual(dict(back, you=None), dict(await state(tamsin), you=None))
        await self.clock.advance(10_000)
        self.assertTrue(await tamsin.quiet())           # (the hold's timer is off)
        self.assertEqual(self.server.daily.snapshot()["reconnects"], 1)

    async def test_a_hello_without_the_resume_bit_joins_back_by_its_code(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await edda.drop()
        await state(tamsin)
        again = await self.join("Edda", 2)
        self.assertTrue(await again.quiet())
        await party(again, "join", code=code)
        back = await state(again)
        self.assertEqual([(m["member"], m["state"]) for m in back["members"]], [(0, MEMBER["here"]), (1, MEMBER["here"])])

    async def test_a_goodbye_frees_the_row_at_once(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await edda.bye()
        left = await state(tamsin)
        self.assertEqual([m["name"] for m in left["members"]], ["Tamsin"])
        self.assertFalse(self.server.holds.timers)

    async def test_a_drop_stops_the_countdown(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await party(tamsin, "start")
        await self.everyone((tamsin, edda))
        await edda.drop()
        stopped = await state(tamsin)
        self.assertEqual((stopped["phase"], states(stopped)["Edda"]), (PHASES["forming"], MEMBER["away"]))
        await self.clock.advance(3000)
        self.assertFalse(self.server.matches)

    async def test_a_row_whose_match_runs_waits_for_the_match(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        for client in (tamsin, edda):
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        await tamsin.until("START", skip=("LOAD_STATE",))
        await edda.drop()
        # (a minute of the match: Tamsin pings; Edda's row is kept all along)
        for _ in range(30):
            await self.clock.advance(2000)
            await tamsin.send_message("PING", client_ms=0, rtt_ms=5)
            await tamsin.until("PONG", skip=("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE"))
        party_now = self.server.lobby.parties[next(iter(self.server.lobby.parties))]
        self.assertEqual([m.name for m in party_now.ordered()], ["Tamsin", "Edda"])
        tamsin_ends = self.match()
        tamsin_ends.end("timeout", "aborted")
        await until(lambda: not self.server.matches)
        await self.clock.advance(40_000 - 1)
        self.assertEqual(len(party_now.members), 2)
        await self.clock.advance(1)
        self.assertEqual([m.name for m in party_now.ordered()], ["Tamsin"])


if __name__ == "__main__":
    unittest.main()
