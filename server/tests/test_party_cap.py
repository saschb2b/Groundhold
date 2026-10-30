"""The server keeps a bounded number of parties (review round 2): each PARTY
create leaves the party before it, so without a bound one connection could
pile up empty parties, each kept 15 minutes, and every create copied the
whole code table. Now a server holds at most `party_cap` parties (four
times `player_cap` by default), an identity keeps at most one empty party,
the oldest empty party makes room for a new one, and a create with no room
is refused with NOTICE parties_full; a code is drawn by asking the table,
never by copying it, with a bounded number of tries."""

import random
import unittest

from support import MODES, NOTICES, HubTest, party, state, until
from groundhold_server import codes


class Table(dict):
    """A party table that fails a test if anything copies or walks it."""

    def __iter__(self):
        raise AssertionError("the code table was walked")

    def keys(self):
        raise AssertionError("the code table was walked")


class Everything:
    """A table that holds every code."""

    def __contains__(self, code):
        return True


class GenerateTests(unittest.TestCase):
    def test_a_code_is_drawn_without_walking_the_table(self):
        rng = random.Random(1)
        table = Table()
        for _ in range(50_000):
            table[codes.generate(table, rng)] = True
        self.assertEqual(len(table), 50_000)

    def test_a_full_table_gives_no_code_rather_than_spinning(self):
        self.assertIsNone(codes.generate(Everything(), random.Random(2)))


class PartyCapTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def test_one_connection_cannot_pile_up_empty_parties(self):
        await self.start()
        mallory = await self.join("Mallory", 7)
        for second in range(60):
            for _ in range(30):
                await party(mallory, "create", mode=MODES["high_water"])
                await state(mallory)
            await self.clock.advance(1000)
        parties = self.server.lobby.parties
        empty = [p for p in parties.values() if not p.members]
        # (the party it is in, and the one empty party it left last)
        self.assertLessEqual(len(parties), 2, f"{len(parties)} parties held, {len(empty)} empty")
        self.assertLessEqual(len(empty), 1)

    async def test_a_create_flood_from_many_identities_stays_under_the_cap(self):
        await self.start(party_cap=4)
        flood = [await self.join(f"Mallory{number}", 40 + number) for number in range(6)]
        for _ in range(20):
            for client in flood:
                await party(client, "create", mode=MODES["classic"])
                await state(client)
                await party(client, "leave")
                await state(client)
                self.assertLessEqual(len(self.server.lobby.parties), 4)
        # (every party is empty now, the oldest ones made way for the newer;
        # a real player's create still finds room: the oldest empty one goes)
        oldest = next(iter(self.server.lobby.empty))
        tamsin = await self.join("Tamsin", 1)
        await party(tamsin, "create", mode=MODES["high_water"])
        made = await state(tamsin)
        self.assertIn(made["code"], self.server.lobby.parties)
        self.assertNotIn(oldest, self.server.lobby.parties)
        self.assertEqual(len(self.server.lobby.parties), 4)

    async def test_no_room_refuses_a_create_and_keeps_the_party(self):
        await self.start(party_cap=3)
        crowd = [await self.join(f"P{number}", number) for number in range(1, 4)]
        for client in crowd:
            await party(client, "create", mode=MODES["classic"])
            await state(client)
        ben = await self.join("Ben", 9)
        await party(ben, "create", mode=MODES["classic"])
        self.assertEqual(await ben.until("NOTICE"), dict(code=NOTICES["parties_full"], argument=0))
        self.assertEqual(len(self.server.lobby.parties), 3)
        # (a member asking for a new party with no room keeps the one it has)
        p1 = next(p for p in self.server.players.values() if p.name == "P1")
        kept = p1.member.party.code
        await party(crowd[0], "create", mode=MODES["high_water"])
        self.assertEqual(await crowd[0].until("NOTICE"), dict(code=NOTICES["parties_full"], argument=0))
        self.assertEqual(p1.member.party.code, kept)
        self.assertEqual(len(self.server.lobby.parties), 3)

    async def test_an_empty_partys_code_still_waits_for_its_player(self):
        # (one empty party per identity: the code it left last still joins back)
        await self.start()
        tamsin = await self.join("Tamsin", 1)
        await party(tamsin, "create", mode=MODES["high_water"])
        first = (await state(tamsin))["code"]
        await party(tamsin, "leave")
        await state(tamsin)
        await party(tamsin, "join", code=first)
        self.assertEqual((await state(tamsin))["code"], first)
        await party(tamsin, "create", mode=MODES["high_water"])
        second = (await state(tamsin))["code"]
        await party(tamsin, "create", mode=MODES["high_water"])
        third = (await state(tamsin))["code"]
        await until(lambda: first not in self.server.lobby.parties)
        self.assertIn(second, self.server.lobby.parties)
        self.assertIn(third, self.server.lobby.parties)

    def test_the_cap_defaults_to_four_times_the_players(self):
        from support import server
        self.assertEqual(server(player_cap=64).party_cap, 256)
        self.assertEqual(server(player_cap=10, party_cap=12).party_cap, 12)
        with self.assertRaises(ValueError):
            server(party_cap=0)


if __name__ == "__main__":
    unittest.main()
