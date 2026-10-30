"""Back to the party after a match (docs/design/core-loop.md §5.8, §5.9, §8
M3's back-to-party test): the results plate, Play again or Hub
(`LEAVE_MATCH` after `MATCH_END`), the party, mode, teams and Builders kept
and Ready cleared, a member who left mid-match back at once, and the next
match from the same party."""

import unittest

from support import BUILDERS, MEMBER, MODES, PHASES, RULES, TICK0, HubTest, party, state, states, until
from groundhold_server.protocol import SPEC

OUTCOMES = SPEC["outcomes"]
FINAL = bytes.fromhex("fedcba9876543210")


class BackToPartyTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def playing(self, clients):
        """The party's match through its barrier to turn 0."""
        await self.ready_all(clients)
        configs = await self.to_loading(clients)
        for client in clients:
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        for client in clients:
            await client.until("START", skip=("LOAD_STATE",))
        playing = await self.everyone(clients)
        self.assertEqual(playing[0]["phase"], PHASES["in_match"])
        await self.clock.advance(SPEC["start_delay_ms"])
        return configs

    async def finish(self, clients):
        """Twenty turns, then every client's RESULT: a won match."""
        await self.clock.turns(20)
        for client in clients:
            await client.send_message("RESULT", tick=60, hash=FINAL, outcomes=[dict(outcome=OUTCOMES["won"])])
        return [await client.until("MATCH_END", skip=("TURN", "LINKS")) for client in clients]

    async def test_play_again_returns_to_the_party_as_it_was(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await party(edda, "builders", main=BUILDERS["lookout"], backup=BUILDERS["lamplighter"])
        await self.everyone((tamsin, edda))
        await party(tamsin, "open", on=1)
        before = (await self.everyone((tamsin, edda)))[0]
        await self.playing((tamsin, edda))
        ends = await self.finish((tamsin, edda))
        self.assertEqual({end["outcome"] for end in ends}, {OUTCOMES["won"]})
        # (the results plate: both still in the match's results)
        results = await self.everyone((tamsin, edda))
        self.assertEqual((results[0]["phase"], set(states(results[0]).values())), (PHASES["results"], {MEMBER["in_match"]}))
        await tamsin.send_message("LEAVE_MATCH")
        one_back = await self.everyone((tamsin, edda))
        self.assertEqual(states(one_back[0]), {"Tamsin": MEMBER["here"], "Edda": MEMBER["in_match"]})
        self.assertEqual(one_back[0]["phase"], PHASES["results"])
        # (a PARTY op from the results plate brings its member back too)
        await party(edda, "ready", on=1)
        both = await self.everyone((tamsin, edda))
        self.assertEqual(both[0]["phase"], PHASES["forming"])
        self.assertEqual(states(both[0]), {"Tamsin": MEMBER["here"], "Edda": MEMBER["ready"]})
        for key in ("code", "mode", "flags", "leader"):
            self.assertEqual(both[0][key], before[key], key)
        self.assertEqual([(m["member"], m["team"], m["main"], m["backup"]) for m in both[0]["members"]],
                         [(m["member"], m["team"], m["main"], m["backup"]) for m in before["members"]])
        self.assertEqual(both[0]["code"], code)
        # (and the next match from the same party)
        configs = await self.to_loading((tamsin, edda))
        self.assertEqual((configs[0]["match"], [s["builder"] for s in configs[0]["seats"]]),
                         (2, [BUILDERS["lamplighter"], BUILDERS["lookout"]]))

    async def test_a_member_who_left_mid_match_is_back_at_once(self):
        await self.start()
        (tamsin, edda, ottilie), _ = await self.party_of("Tamsin", "Edda", "Ottilie")
        await self.playing((tamsin, edda, ottilie))
        await self.clock.turns(2)
        await ottilie.send_message("LEAVE_MATCH")
        back = await state(ottilie, skip=("TURN", "PONG"))
        self.assertEqual(states(back), {"Tamsin": MEMBER["in_match"], "Edda": MEMBER["in_match"], "Ottilie": MEMBER["here"]})
        self.assertEqual(back["phase"], PHASES["in_match"])
        # (still in the party's hub, it may change its Builders for the next match)
        await party(ottilie, "builders", main=BUILDERS["lookout"], backup=BUILDERS["lamplighter"])
        await state(ottilie)
        await self.clock.turns(20)
        for client in (tamsin, edda):
            await client.send_message("RESULT", tick=60, hash=FINAL, outcomes=[dict(outcome=OUTCOMES["lost"])])
        for client in (tamsin, edda):
            await client.until("MATCH_END", skip=("TURN", "LINKS", "PARTY_STATE"))
        results = await state(ottilie)
        self.assertEqual((results["phase"], states(results)["Ottilie"]), (PHASES["results"], MEMBER["here"]))
        for client in (tamsin, edda):
            await client.send_message("LEAVE_MATCH")
        await until(lambda: next(iter(self.server.lobby.parties.values())).phase == PHASES["forming"])

    async def test_a_match_that_never_started_brings_everyone_back_at_once(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        await tamsin.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await edda.send_message("LOADED", rules_hash=RULES, tick0_hash=bytes(8))
        for client in (tamsin, edda):
            await client.until("MATCH_END", skip=("LOAD_STATE", "NOTICE"))
            back = await state(client)
            self.assertEqual((back["phase"], set(states(back).values())), (PHASES["forming"], {MEMBER["here"]}))

    async def test_leave_match_outside_any_match_changes_nothing(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await tamsin.send_message("LEAVE_MATCH")
        await tamsin.send_message("PING", client_ms=1, rtt_ms=0)
        name, fields = await tamsin.next()
        self.assertEqual(name, "ERROR")     # (out of order: no match and no results to leave)

    async def test_the_party_keeps_its_mode_after_a_classic_match(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda", mode="classic")
        await self.playing((tamsin, edda))
        await self.finish((tamsin, edda))
        await self.everyone((tamsin, edda))
        for client in (tamsin, edda):
            await client.send_message("LEAVE_MATCH")
        await self.everyone((tamsin, edda))
        last = (await self.everyone((tamsin, edda)))[0]
        self.assertEqual((last["mode"], last["phase"]), (MODES["classic"], PHASES["forming"]))


if __name__ == "__main__":
    unittest.main()
