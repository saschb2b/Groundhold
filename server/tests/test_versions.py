"""Versions (docs/design/core-loop.md §6.9, §7.3): the protocol version is
checked strictly in every HELLO, a resume's too (ERROR 2: the game is older;
17: the server is); the rules hash is a matchmaking key, so a party member on
another one needs to reload, and a game of another rules hash (a reloaded
page that fetched a newer build) cannot take a match seat back; during
maintenance only a resume for a held seat is let in (shared/net/README.md,
Resilience: Rejoin)."""

import unittest

from support import MOST_MESSAGES, RESUME, RULES, HubTest, MatchTest, named, party, state, states, until
from groundhold_server import protocol
from groundhold_server.protocol import SPEC

ERRORS, NOTICES, MEMBER = SPEC["errors"], SPEC["notices"], SPEC["member_states"]
OLDER = bytes.fromhex("47726f756e646830")       # "Groundh0": an older build's rules


class VersionTests(MatchTest, unittest.IsolatedAsyncioTestCase):
    async def dropped(self):
        """Two seats playing, Edda's link dropped: her seat is held."""
        tamsin, edda = await self.seated("Tamsin", "Edda")
        await edda.drop()
        await until(lambda: self.match().seats[1].player is None)
        return tamsin

    async def test_an_older_game_hears_2_and_a_newer_one_17_resuming_too(self):
        await self.start("classic:2")
        for version, code in ((0, ERRORS["game_older"]), (2, ERRORS["server_older"])):
            for held in (dict(), dict(flags=RESUME, match=1, seat=0)):
                game = await self.join("Tamsin", 1, version=version, subprotocol=f"groundhold.v{version}", **held)
                self.assertEqual((game.answer[0], game.answer[1]["code"]), ("ERROR", code), held)
        self.assertEqual(self.server.daily.today["versions"], {"0": 2, "2": 2})
        self.assertFalse(self.server.players)

    async def test_a_game_of_another_rules_hash_cannot_take_its_seat_back(self):
        await self.dropped()
        newer = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1, rules_hash=OLDER)
        self.assertEqual(newer.answer[0], "WELCOME")
        self.assertEqual(await newer.next(), ("NOTICE", dict(code=NOTICES["no_held_seat"], argument=0)))
        self.assertIsNone(self.match().seats[1].player, "the caretaker keeps playing it")
        same = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1, rules_hash=RULES)
        self.assertEqual((await same.until("MATCH_CONFIG"))["flags"], SPEC["config_flags"]["rejoin"])

    async def test_maintenance_lets_in_only_a_resume_for_a_held_seat(self):
        await self.dropped()
        self.server.maintenance = protocol.maintenance_line("until 14:00 UTC")
        match = self.match().id
        for number, held in ((9, dict()), (2, dict(flags=RESUME)), (2, dict(flags=RESUME, match=match, seat=0)),
                             (2, dict(flags=RESUME, match=match + 1, seat=1)), (2, dict(match=match, seat=1))):
            game = await self.join("Edda", number, **held)
            self.assertEqual((game.answer[0], game.answer[1]["code"], game.answer[1]["text"]),
                             ("ERROR", ERRORS["maintenance"], "until 14:00 UTC"), held)
        back = await self.join("Edda", 2, flags=RESUME, match=match, seat=1)
        self.assertEqual(back.answer[0], "WELCOME")
        self.assertEqual((await back.until("MATCH_CONFIG"))["your_seat"], 1)

    async def test_a_resume_for_a_held_seat_passes_a_full_server_and_replaces_the_old_link(self):
        tamsin, edda = await self.seated("Tamsin", "Edda", player_cap=2)
        sefa = await self.join("Sefa", 3)
        self.assertEqual((sefa.answer[0], sefa.answer[1]["code"]), ("ERROR", ERRORS["full"]))
        # (Edda's old link still looks open to the server: her new window takes the seat)
        again = await self.join("Edda", 2, flags=RESUME, match=self.match().id, seat=1)
        self.assertEqual(again.answer[0], "WELCOME")
        self.assertEqual(named(await until_error(edda), "ERROR")[0]["code"], ERRORS["replaced"])
        await until(lambda: len(self.server.players) == 2)
        self.assertIn(self.match().seats[1].player, self.server.players.values())
        self.assertEqual(self.server.daily.today["rejoins"], 1)


async def until_error(game):
    """What `game` reads up to its ERROR (or the close)."""
    out = []
    for _ in range(MOST_MESSAGES):
        name, fields = await game.next()
        out.append((name, fields))
        if name in ("ERROR", "CLOSE"):
            return out
    raise AssertionError(f"no ERROR among {MOST_MESSAGES} messages")


class PartyVersionTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_a_member_on_another_rules_hash_needs_to_reload(self):
        await self.start()
        tamsin = await self.join("Tamsin", 1)
        await party(tamsin, "create", mode=SPEC["modes"]["high_water"]["id"])
        code = (await state(tamsin))["code"]
        older = await self.join("Ottilie", 3, rules_hash=OLDER, build_seq=6)
        await party(older, "join", code=code)
        await older.until("NOTICE", skip=("PARTY_STATE",))
        seen = await state(tamsin)
        self.assertEqual(states(seen)["Ottilie"], MEMBER["needs_reload"])


if __name__ == "__main__":
    unittest.main()
