"""The daily totals and GET /stats (docs/design/core-loop.md §6.10, §6.12):
joins, identities as a count, the peak, matches started and finished per
mode, desyncs, reconnects, resyncs, rejoins, caretaker seats and HELLOs per
protocol version; a day written at its end and as the server stops, taken up
again after a restart the same day, and kept stats_days.

Adapted from Cyberworld Endless's server/tests/test_stats.py (MIT, Sascha
Becker), with Groundhold's counts."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from support import RULES, TICK0, Client, HubTest, start_match, sync, until
from groundhold_server import stats
from groundhold_server.protocol import SPEC
from groundhold_server.retention import Retention

NOW = 1792627200 + 12 * 3600       # Thursday 22 October 2026, 12:00 UTC
FINAL = bytes.fromhex("fedcba9876543210")


class Wall:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class StatsTests(HubTest, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.temporary = tempfile.TemporaryDirectory(prefix="groundhold-stats-")
        self.dir = Path(self.temporary.name)
        self.wall = Wall()

    async def asyncTearDown(self):
        await super().asyncTearDown()
        self.temporary.cleanup()

    async def start(self, **options):
        options.setdefault("state_dir", self.dir)
        return await super().start(identity_key=None, wall=self.wall, **options)

    async def served(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /stats HTTP/1.1\r\nHost: x\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 2)
        writer.close()
        self.assertTrue(response.startswith(b"HTTP/1.1 200"), response)
        return json.loads(response.split(b"\r\n\r\n", 1)[1])

    async def test_a_days_counts_at_stats(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await self.join("Tamsin again", 1)                 # (the same token: one identity)
        old = Client()
        self.clients.append(old)
        await old.hello(self.port, "Old", version=0, subprotocol="groundhold.v0")
        # (a match played through, its seat 1 silent so the caretaker takes it)
        await self.ready_all((tamsin, edda))
        await self.to_loading((tamsin, edda))
        for client in (tamsin, edda):
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        await self.clock.advance(SPEC["start_delay_ms"])
        for _ in range(3):
            await self.clock.advance(2000)
            await tamsin.send_message("PING", client_ms=0, rtt_ms=5)
            await tamsin.until("PONG", skip=("START", "TURN", "LINKS", "PARTY_STATE", "LOAD_STATE"))
        await until(lambda: self.match().seats[1].state == "away")
        await tamsin.send_message("RESULT", tick=60, hash=FINAL, outcomes=[dict(outcome=0)])
        await tamsin.until("MATCH_END", skip=("TURN", "LINKS"))
        today = (await self.served())["today"]
        self.assertEqual({key: today[key] for key in ("day", "joins", "identities", "peak", "started", "finished",
                                                     "desyncs", "reconnects", "caretaker_seats", "versions")},
                         {"day": "2026-10-22", "joins": 3, "identities": 2, "peak": 3,
                          "started": {"high_water": 1}, "finished": {"high_water": 1}, "desyncs": 0,
                          "reconnects": 0, "caretaker_seats": 1, "versions": {"0": 1, "1": 3}})
        # (no identity, name or address anywhere in it)
        text = json.dumps(await self.served())
        for secret in (tamsin.welcome["identity"].hex(), "Tamsin", "127.0.0.1"):
            self.assertNotIn(secret, text)

    async def test_desyncs_count(self):
        await self.start(dev_match="classic:2")
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for client in (one, two):
            await client.until("MATCH_CONFIG")
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"])
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(20)
        for client, digest in ((one, b"a" * 8), (two, b"b" * 8)):
            await client.send_message("HASH", tick=60, hash=digest, flags=0)
        await one.until("MATCH_END", skip=("LOAD_STATE", "START", "TURN", "LINKS"))
        today = (await self.served())["today"]
        self.assertEqual((today["desyncs"], today["started"], today["finished"]), (1, {"classic": 1}, {}))

    async def test_a_day_is_written_at_its_end_and_as_the_server_stops(self):
        await self.start()
        await self.join("Tamsin", 1)
        self.wall.now += 12 * 3600          # (midnight: the day ends at the next housekeeping)
        await self.clock.advance(1000)
        await until(lambda: (self.dir / stats.LOG).exists() and (self.dir / stats.LOG).read_text().strip())
        written = [json.loads(line) for line in (self.dir / stats.LOG).read_text().splitlines()]
        self.assertEqual([(day["day"], day["joins"], day["identities"]) for day in written], [("2026-10-22", 1, 1)])
        await self.join("Edda", 2)
        served = await self.served()
        self.assertEqual((served["today"]["day"], served["today"]["joins"]), ("2026-10-23", 1))
        self.assertEqual([day["day"] for day in served["days"]], ["2026-10-22"])
        await self.server.close()
        self.server = None
        days = [json.loads(line) for line in (self.dir / stats.LOG).read_text().splitlines()]
        self.assertEqual([(day["day"], day["joins"]) for day in days], [("2026-10-22", 1), ("2026-10-23", 1)])
        # (a restart the same day takes its line up again: a player seen
        # before and after counts twice among the identities)
        await self.start()
        await self.join("Edda", 2)
        today = (await self.served())["today"]
        self.assertEqual((today["joins"], today["identities"]), (2, 2))

    async def test_no_state_directory_writes_nothing_and_stats_days_bounds_the_file(self):
        await self.start(state_dir=None)
        await self.join("Tamsin", 1)
        self.assertEqual((await self.served())["today"]["joins"], 1)
        await self.server.close()
        self.server = None
        self.assertFalse(any(self.dir.iterdir()))
        lines = [json.dumps(dict(stats.fresh(day), joins=1)) for day in ("2025-01-01", "2026-10-01", "2026-10-21")]
        (self.dir / stats.LOG).write_text("\n".join(lines + ["not json"]) + "\n")
        self.assertEqual(stats.prune(self.dir, NOW, 30), 2)
        self.assertEqual([json.loads(line)["day"] for line in (self.dir / stats.LOG).read_text().splitlines()],
                         ["2026-10-01", "2026-10-21"])
        daily = stats.Daily(self.dir, 365, self.wall)
        self.assertEqual([day["day"] for day in daily.public()["days"]], ["2026-10-01", "2026-10-21"])
        self.assertEqual(Retention().stats_days, 365)

    def test_the_identities_held_in_memory_are_bounded(self):
        # (anyone can mint tokens: a flood of fresh ones grows the day's set to
        # SEEN_MAX and no further, and each join past it counts as a new identity)
        daily = stats.Daily(None, 365, self.wall)
        old, stats.SEEN_MAX = stats.SEEN_MAX, 3
        try:
            for n in range(10):
                daily.join(bytes((n,)) * 32, 1)
            daily.join(bytes((1,)) * 32, 1)     # (one already held: not counted again)
        finally:
            stats.SEEN_MAX = old
        self.assertEqual(len(daily.seen), 3)
        self.assertEqual((daily.snapshot()["joins"], daily.snapshot()["identities"]), (11, 10))
        self.wall.now += 86400
        self.assertEqual(daily.rollover()["identities"], 10)
        self.assertEqual((len(daily.seen), daily.snapshot()["identities"]), (0, 0))

    async def test_a_reconnect_counts(self):
        await self.start()
        (tamsin, edda), _ = await self.party_of("Tamsin", "Edda")
        await edda.drop()
        await tamsin.until("PARTY_STATE")
        again = Client()
        self.clients.append(again)
        await again.hello(self.port, "Edda", token=bytes((2,)) * 16, flags=SPEC["hello_flags"]["resume"])
        await again.until("PARTY_STATE")
        self.assertEqual((await self.served())["today"]["reconnects"], 1)

    async def test_resyncs_and_rejoins_count(self):
        # (M4: a minority of three is resynced, a dropped seat taken back by a
        # resume HELLO, whose own RESYNC counts too)
        await self.start(dev_match="classic:3")
        games = [await self.join(name, number) for number, name in enumerate(("Tamsin", "Edda", "Ottilie"), 1)]
        await start_match(self.clock, games)
        await self.clock.turns(20)
        for game, digest in zip(games, (b"a" * 8, b"a" * 8, b"b" * 8)):
            await game.send_message("HASH", tick=60, hash=digest, flags=0)
        for game in games:
            await sync(game)
        await games[1].drop()
        await until(lambda: next(iter(self.server.matches.values())).seats[1].player is None)
        match = next(iter(self.server.matches.values()))
        await self.join("Edda", 2, flags=SPEC["hello_flags"]["resume"], match=match.id, seat=1)
        today = (await self.served())["today"]
        self.assertEqual((today["desyncs"], today["resyncs"], today["rejoins"]), (1, 2, 1))
        self.assertEqual(stats.checked(dict(stats.fresh("2026-10-22"), resyncs=3, rejoins=-1))["rejoins"], 0)


if __name__ == "__main__":
    unittest.main()
