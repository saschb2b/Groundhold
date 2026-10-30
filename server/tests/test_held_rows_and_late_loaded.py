"""Two edges of the hub found in review round 1.

A row held through a running match stays findable after its 40 s (holds.py):
a resume HELLO, or a join by the party's code, takes it back instead of adding
a second row with the same identity.

A LOADED that crossed the loading ceiling's MATCH_END (its seat was put out
just as the game finished loading) is let pass like any other match message
after MATCH_END, so the hub connection, and with it the party row, stays."""

import unittest

from support import MEMBER, PHASES, RULES, TICK0, Client, HubTest, party, state, states
from groundhold_server.protocol import SPEC

RESUME = SPEC["hello_flags"]["resume"]
SKIP = ("TURN", "LINKS", "PARTY_STATE", "LOAD_STATE", "PONG")


class HeldRowsAndLateLoaded(HubTest, unittest.IsolatedAsyncioTestCase):
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

    async def test_a_row_held_through_a_long_match_is_still_found_after_forty_seconds(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await self.playing((tamsin, edda))
        await edda.drop()
        for _ in range(25):                     # 50 s of the match; Tamsin pings
            await self.clock.advance(2000)
            await tamsin.send_message("PING", client_ms=0, rtt_ms=5)
            await tamsin.until("PONG", skip=SKIP[:4])
        again = Client()
        self.clients.append(again)
        welcome = await again.hello(self.port, "Edda", token=bytes((2,)) * 16, flags=RESUME)
        self.assertEqual(welcome[0], "WELCOME")
        await party(again, "join", code=code)
        joined = await state(again)
        names = [m["name"] for m in joined["members"]]
        self.assertEqual(names, ["Tamsin", "Edda"], f"one row per identity, not {names}")
        self.assertEqual(states(joined)["Edda"], MEMBER["in_match"])

    async def test_a_loaded_that_crossed_the_ceiling_keeps_the_hub_connection(self):
        await self.start()
        (tamsin, edda), code = await self.party_of("Tamsin", "Edda")
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        await tamsin.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await tamsin.until("LOAD_STATE")
        await self.clock.advance(120_000)
        await edda.until("MATCH_END", skip=("LOAD_STATE",))
        # (her game finished loading just as the ceiling came: its LOADED was on the wire)
        await edda.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        got = []
        for _ in range(4):
            try:
                got.append(await edda.next(0.3))
            except Exception:
                break
        self.assertFalse(any(name == "ERROR" for name, _ in got), f"refused for a late LOADED: {got}")
        self.assertIn(code, self.server.lobby.parties)
        self.assertEqual(len(self.server.lobby.parties[code].members), 2, "her party row stays")


if __name__ == "__main__":
    unittest.main()
