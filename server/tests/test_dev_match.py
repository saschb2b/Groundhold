"""--dev-match (docs/design/core-loop.md §8 M1): the first HELLOs with one
rules hash form a match; the loading barrier, the tick-0 check, hashes,
results, silence and leaving; the golden transcripts; and the real program
with --port 0, its `listening port=N` line and /health."""

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.request

from support import RULES, ROOT, TICK0, Client, ManualClock, server, start_match, until
from groundhold_server import protocol
from groundhold_server.app import dev_match_spec
from groundhold_server.protocol import SPEC

sys.path.insert(0, str(ROOT / "server" / "tools"))
import record_transcripts   # noqa: E402

OUTCOMES, REASONS, STATES = SPEC["outcomes"], SPEC["end_reasons"], SPEC["load_states"]
SYSTEM = SPEC["system_commands"]
KIT_READY = r"listening.*port\D*(?P<port>\d+)"


class DevMatchSpecTests(unittest.TestCase):
    def test_mode_and_seats(self):
        self.assertEqual(dev_match_spec("classic:2"), ("classic", 2))
        self.assertEqual(dev_match_spec("tide_race:4"), ("tide_race", 4))
        for text in ("classic", "classic:", "nope:2", "classic:5", "classic:0", "tide_race:1", "undertow:3", ":2", "classic:x",
                     "race:2", "duel:2"):
            with self.assertRaises(ValueError):
                dev_match_spec(text)


class DevMatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = ManualClock()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.drop()
        await self.server.close()

    async def start(self, dev_match="classic:2", **options):
        self.server = server(dev_match=dev_match, clock=self.clock, **options)
        self.port = await self.server.start("127.0.0.1", 0)

    async def join(self, name, number, **options):
        client = Client()
        self.clients.append(client)
        welcome = await client.hello(self.port, name, token=bytes((number,)) * 16, **options)
        self.assertEqual(welcome[0], "WELCOME")
        self.assertEqual(welcome[1]["flags"], SPEC["welcome_flags"]["dev_match"])
        return client

    def match(self):
        return next(iter(self.server.matches.values()))

    async def talk(self, turns, *clients):
        """`turns` turns while each of `clients` pings every 2 s, as a game
        does, so none of them goes AWAY."""
        step = SPEC["ping_ms"] // SPEC["turn_ms"]
        while turns > 0:
            await self.clock.turns(min(step, turns))
            turns -= step
            for client in clients:
                await client.send_message("PING", client_ms=0, rtt_ms=5)
                # (a minority of three gets RESYNC among its turns: M4)
                await client.until("PONG", skip=("TURN", "LINKS", "RESYNC"))

    async def test_the_first_two_hellos_form_a_match_and_the_next_two_another(self):
        await self.start()
        one = await self.join("Tamsin", 1)
        self.assertTrue(await one.quiet())
        two = await self.join("Edda", 2)
        configs = [await client.until("MATCH_CONFIG") for client in (one, two)]
        seats = [dict(seat=0, team=0, builder=0, flags=0, name="Tamsin"), dict(seat=1, team=0, builder=0, flags=0, name="Edda")]
        for seat, config in enumerate(configs):
            self.assertEqual(config, dict(match=1, mode=SPEC["modes"]["classic"]["id"], map=0, seed=20261029,
                                          rules_hash=RULES, your_seat=seat, seats=seats, flags=0))
        three = await self.join("Ottilie", 3)
        self.assertTrue(await three.quiet())
        four = await self.join("Sefa", 4)
        for seat, client in enumerate((three, four)):
            config = await client.until("MATCH_CONFIG")
            self.assertEqual((config["match"], config["your_seat"], [s["name"] for s in config["seats"]]),
                             (2, seat, ["Ottilie", "Sefa"]))
        self.assertEqual(sorted(self.server.matches), [1, 2])
        self.assertEqual(self.server.health()["matches"], 2)

    async def test_only_one_rules_hash_plays_together(self):
        await self.start()
        # (one who waited and went is out of the pool)
        gone = await self.join("Gone", 5)
        await gone.drop()
        await until(lambda: not self.server.players)
        one = await self.join("Tamsin", 1)
        other = await self.join("Stale", 2, rules_hash=bytes(8))
        self.assertTrue(await one.quiet())
        three = await self.join("Edda", 3)
        for client in (one, three):
            config = await client.until("MATCH_CONFIG")
            self.assertEqual([s["name"] for s in config["seats"]], ["Tamsin", "Edda"])
        self.assertTrue(await other.quiet())
        self.assertEqual(list(self.server.waiting), [bytes(8)])

    async def test_a_tide_race_puts_half_the_seats_on_each_team(self):
        await self.start("tide_race:4")
        clients = [await self.join(name, i + 1) for i, name in enumerate(("A", "B", "C", "D"))]
        config = await clients[0].until("MATCH_CONFIG")
        self.assertEqual(config["mode"], SPEC["modes"]["tide_race"]["id"])
        self.assertEqual([s["team"] for s in config["seats"]], [0, 0, 1, 1])

    async def test_the_barrier_waits_for_every_seat_and_the_minimum(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for client in (one, two):
            await client.until("MATCH_CONFIG")
            await client.until("LOAD_STATE")
        await one.send_message("LOADING", per_mille=250)
        state = await two.until("LOAD_STATE")
        self.assertEqual(state["seats"][0], dict(seat=0, per_mille=250, state=STATES["loading"]))
        await one.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        state = await two.until("LOAD_STATE")
        self.assertEqual(state["seats"][0], dict(seat=0, per_mille=1000, state=STATES["checking"]))
        await self.clock.advance(SPEC["loading_min_ms"] + 1000)
        await asyncio.sleep(0.05)
        self.assertFalse(self.server.matches[1].loop)           # (seat 1 still loading)
        await two.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        for client in (one, two):
            start = await client.until("START", skip=("LOAD_STATE",))
            self.assertEqual(start, dict(ms_until_turn0=SPEC["start_delay_ms"]))

    async def test_the_loading_minimum_shows_even_when_everyone_is_ready_at_once(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for client in (one, two):
            await client.until("MATCH_CONFIG")
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(SPEC["loading_min_ms"] - 1)
        for client in (one, two):
            await client.until("LOAD_STATE")
            await client.until("LOAD_STATE")
            await client.until("LOAD_STATE")
            await client.until("LOAD_STATE")
            self.assertTrue(await client.quiet())
        await self.clock.advance(1)
        for client in (one, two):
            await client.until("START")

    async def test_tick0_hashes_apart_abort_before_anyone_plays(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        for client, tick0 in ((one, TICK0), (two, bytes(8))):
            await client.until("MATCH_CONFIG")
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=tick0)
        for client in (one, two):
            notice = await client.until("NOTICE", skip=("LOAD_STATE",))
            self.assertEqual(notice, dict(code=SPEC["notices"]["tick0_mismatch"], argument=SPEC["system_seat"]))
            end = await client.until("MATCH_END")
            self.assertEqual(end, dict(outcome=OUTCOMES["aborted"], reason=REASONS["tick0_mismatch"], final_tick=0))
        self.assertFalse(self.server.matches)
        # (still connected, out of the match: a late LOADING is let pass)
        await one.send_message("LOADING", per_mille=1000)
        await one.send_message("PING", client_ms=1, rtt_ms=0)
        self.assertEqual(await one.until("PONG"), dict(client_ms=1, turn=0))

    async def test_a_seat_dropped_while_loading_starts_away(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await two.until("MATCH_CONFIG")
        await two.drop()
        await one.until("MATCH_CONFIG")
        await one.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
        await self.clock.advance(0)
        await one.until("START", skip=("LOAD_STATE",))
        await self.clock.advance(SPEC["start_delay_ms"])
        await self.clock.turns(1)
        turn = await one.until("TURN")
        self.assertEqual(turn["commands"], [dict(seat=255, seq=1, type=SYSTEM["AWAY"]["type"], a=1, b=0, c=0)])

    async def test_hashes_that_agree_pass_and_two_seats_apart_end_desynced(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(40)
        for tick, digests in ((60, (b"a" * 8, b"a" * 8)), (120, (b"b" * 8, b"c" * 8))):
            for client, digest in zip((one, two), digests):
                await client.send_message("HASH", tick=tick, hash=digest, flags=0)
            if tick == 60:
                await until(lambda: 60 in self.match().agreed)
        for client in (one, two):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["desynced"], reason=REASONS["desync"], final_tick=120))
        self.assertFalse(self.server.matches)

    async def test_a_dev_match_may_keep_shorter_turns(self):
        # (tools/net/smoke.py --turn-ms 10: games pace by WELCOME's turn_ms)
        await self.start(turn_ms=10)
        one = Client()
        self.clients.append(one)
        name, welcome = await one.hello(self.port, "Tamsin", token=b"\x01" * 16)
        self.assertEqual((name, welcome["turn_ms"]), ("WELCOME", 10))
        two = await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.advance(10)
        self.assertEqual(await one.until("TURN", skip=("LOAD_STATE",)), dict(turn=0, commands=[]))
        await self.clock.advance(10)
        self.assertEqual((await one.until("TURN"))["turn"], 1)
        await self.clock.advance(9)
        self.assertTrue(await one.quiet())
        self.assertEqual(self.server.health()["turn_ms"], 10)
        with self.assertRaises(ValueError):
            server(turn_ms=10)          # (only a dev match may)
        with self.assertRaises(ValueError):
            server(dev_match="classic:2", turn_ms=1)

    async def test_a_hash_from_beyond_the_sealed_turns_is_refused(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(19)
        await one.send_message("HASH", tick=60, hash=b"a" * 8, flags=0)
        error = await one.until("ERROR", skip=("TURN",))
        self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])

    async def test_a_late_hash_is_waited_for_and_compared(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(20)
        await one.send_message("HASH", tick=60, hash=b"a" * 8, flags=0)
        await until(lambda: 60 in self.match().hashes)
        # (Edda is late, but present: one report of two seats is no majority, so it waits)
        await self.clock.advance(SPEC["hash_wait_ms"])
        self.assertNotIn(60, self.match().agreed)
        self.assertIn(60, self.match().hashes)
        await two.send_message("HASH", tick=60, hash=b"z" * 8, flags=0)
        end = await two.until("MATCH_END", skip=("TURN", "LINKS"))
        self.assertEqual((end["outcome"], end["final_tick"]), (OUTCOMES["desynced"], 60))

    async def test_results_agreed_end_the_match_with_each_teams_outcome(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(5)
        for client in (one, two):
            await client.send_message("RESULT", tick=15, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        for client in (one, two):
            end = await client.until("MATCH_END", skip=("TURN",))
            self.assertEqual(end, dict(outcome=OUTCOMES["won"], reason=REASONS["result"], final_tick=15))
        self.assertFalse(self.server.matches)
        # (a hash already on its way when MATCH_END came is let pass)
        await one.send_message("HASH", tick=60, hash=b"r" * 8, flags=0)
        await one.send_message("PING", client_ms=2, rtt_ms=0)
        await one.until("PONG")

    async def test_results_apart_end_desynced(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(5)
        await one.send_message("RESULT", tick=15, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await two.send_message("RESULT", tick=15, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        end = await one.until("MATCH_END", skip=("TURN",))
        self.assertEqual(end["outcome"], OUTCOMES["desynced"])

    async def test_a_lone_early_result_does_not_decide_for_a_seat_still_playing(self):
        # A modified game passes the barrier honestly and claims the match at
        # once; the other seat plays on. Its simulation runs past the claimed
        # end, so it disagrees: with two seats the match ends "desynced", never
        # with the claimer's "won" (§6.1, §6.10; review M1 protocol 1).
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await one.send_message("RESULT", tick=0, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await until(lambda: self.match().seats[0].result is not None)
        await self.clock.turns(20)
        self.assertTrue(self.server.matches, "nothing is decided while Edda is still on her way to tick 0")
        await two.send_message("HASH", tick=60, hash=b"h" * 8, flags=0)
        for client in (one, two):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["desynced"], reason=REASONS["desync"], final_tick=0))

    async def test_a_result_is_bounded_like_a_hash(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(20)
        # (no later than the sealed turns reach: 20 turns are 60 ticks)
        await one.send_message("RESULT", tick=0xffffffff, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        error = await one.until("ERROR", skip=("TURN",))
        self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])
        # (and no earlier than the seat's own last HASH)
        await two.send_message("HASH", tick=60, hash=b"h" * 8, flags=0)
        await two.send_message("RESULT", tick=30, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        error = await two.until("ERROR", skip=("TURN", "LINKS"))
        self.assertEqual(error["code"], SPEC["errors"]["out_of_limits"])

    async def test_a_slow_seat_is_waited_for_and_then_agrees(self):
        # Edda's game is far behind (a slow window catching up) when Tamsin's
        # match ends: it is waited for past result_wait_ms while it is present,
        # short of the claimed tick and still hashing, and its own RESULT
        # decides with hers.
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.play(60, 300, ((one, 0), (two, 1)))
        await self.play(360, 600, ((one, 0),), talking=(two,))
        await one.send_message("RESULT", tick=600, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await until(lambda: self.match().seats[0].result is not None)
        for tick in (360, 420, 480, 540):
            await self.talk(60, one, two)                   # (3 s a hash: slow, but on her way)
            await two.send_message("HASH", tick=tick, hash=b"h" * 8, flags=0)
            await until(lambda: self.match().seats[1].hash_tick == tick)
        self.assertTrue(self.server.matches, "Edda is present, short of tick 600 and still hashing: she is waited for")
        self.assertEqual([seat.state for seat in self.match().seats], ["present", "present"])
        await two.send_message("HASH", tick=600, hash=b"h" * 8, flags=0)
        await two.send_message("RESULT", tick=600, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        for client in (one, two):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS", "PONG"))
            self.assertEqual(end, dict(outcome=OUTCOMES["won"], reason=REASONS["result"], final_tick=600))

    async def test_three_seats_end_on_a_majority(self):
        await self.start("classic:3")
        one, two, three = await self.join("Tamsin", 1), await self.join("Edda", 2), await self.join("Ottilie", 3)
        await start_match(self.clock, (one, two, three))
        await self.clock.turns(50)
        await one.send_message("RESULT", tick=150, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        await until(lambda: self.match().seats[0].result is not None)
        self.assertTrue(self.server.matches, "one of three is no majority")
        await two.send_message("RESULT", tick=150, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        for client in (one, two, three):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["lost"], reason=REASONS["result"], final_tick=150))

    async def play(self, first, last, hashing, talking=(), digests=None):
        """Seats playing ticks `first` to `last`: a second of turns before each
        hash tick (every client pinging, as games do), then each of `hashing`
        ((client, seat index) pairs) sends its HASH, `digests(index, tick)` or
        b"h" * 8, and the server has them all before the next second."""
        clients = list(dict.fromkeys([client for client, _ in hashing] + list(talking)))
        for tick in range(first, last + 1, SPEC["hash_every"]):
            await self.talk(SPEC["hash_every"] // SPEC["turn_ticks"], *clients)
            for client, index in hashing:
                await client.send_message("HASH", tick=tick, hash=digests(index, tick) if digests else b"h" * 8, flags=0)
            await until(lambda: not self.server.matches
                        or all(self.match().seats[index].hash_tick == tick for _, index in hashing))

    async def test_a_modified_seat_of_three_is_outvoted(self):
        # Tamsin's modified game claims the match won at tick 0, right after
        # START; Edda and Ottilie play on. They ran past her claimed end, but
        # they are two of three and may agree on an end of their own: she is
        # outvoted, and the match plays on (§6.1; review M1 protocol 2, must-fix 2).
        await self.start("classic:3")
        one, two, three = await self.join("Tamsin", 1), await self.join("Edda", 2), await self.join("Ottilie", 3)
        await start_match(self.clock, (one, two, three))
        await one.send_message("RESULT", tick=0, hash=b"x" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await until(lambda: self.match().seats[0].result is not None)
        await self.play(60, 720, ((two, 1), (three, 2)), talking=(one,))  # (12 s: past result_wait_ms)
        self.assertTrue(self.server.matches, "one modified seat of three ends nothing")
        self.assertEqual([seat.state for seat in self.match().seats], ["present"] * 3)
        for client in (two, three):
            await client.send_message("RESULT", tick=720, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        for client in (one, two, three):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["lost"], reason=REASONS["result"], final_tick=720))

    async def test_a_desynced_seat_of_three_does_not_end_the_majoritys_match(self):
        # Ottilie's simulation parts from the others at tick 1,080 (a minority:
        # RESYNC since M4, which her game here never acts on) and thinks the
        # hollow fell at 1,190. Tamsin and Edda agree with each other and play
        # on past it; their agreed end decides (§6.7; review M1 protocol 2,
        # must-fix 2).
        await self.start("classic:3")
        one, two, three = await self.join("Tamsin", 1), await self.join("Edda", 2), await self.join("Ottilie", 3)
        await start_match(self.clock, (one, two, three))
        everyone = ((one, 0), (two, 1), (three, 2))
        await self.play(60, 1140, everyone, digests=lambda index, tick: b"z" * 8 if index == 2 and tick >= 1080 else b"a" * 8)
        self.assertTrue(self.server.matches, "a minority's hashes end nothing")
        self.assertEqual((self.match().seats[2].resyncs, self.match().seats[2].muted), (1, True))
        await self.talk(20, one, two, three)
        await three.send_message("RESULT", tick=1190, hash=b"z" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        await three.send_message("PING", client_ms=0, rtt_ms=5)
        await three.until("PONG", skip=("TURN", "LINKS", "RESYNC"))
        # (her claim comes from the simulation that parted, before her RESYNC: let pass)
        self.assertIsNone(self.match().seats[2].result)
        await self.play(1200, 1260, ((one, 0), (two, 1)), talking=(three,), digests=lambda index, tick: b"a" * 8)
        self.assertTrue(self.server.matches, "the majority ran past the minority's end and plays on")
        for client in (one, two):
            await client.send_message("RESULT", tick=1260, hash=b"a" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        for client in (one, two, three):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["won"], reason=REASONS["result"], final_tick=1260))

    async def test_a_seat_that_talks_but_stops_hashing_holds_the_end_up_result_wait_at_most(self):
        # Edda's game keeps its link (a PING every 2 s) but its simulation
        # stops: no HASH after tick 300. Tamsin's ends at 600. Edda is waited
        # for until her last HASH is result_wait_ms old, then the match ends
        # "desynced", never with Tamsin's "won" alone (review M1 protocol 2).
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.play(60, 300, ((one, 0), (two, 1)))
        await self.play(360, 600, ((one, 0),), talking=(two,))         # (5 s with no HASH from Edda)
        await one.send_message("RESULT", tick=600, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await until(lambda: self.match().seats[0].result is not None)
        await self.talk(80, one, two)                                   # (9 s)
        self.assertTrue(self.server.matches, "Edda's last HASH is not result_wait_ms old yet")
        await self.clock.turns(SPEC["ping_ms"] // SPEC["turn_ms"])     # (11 s)
        for client in (one, two):
            end = await client.until("MATCH_END", skip=("TURN", "LINKS"))
            self.assertEqual(end, dict(outcome=OUTCOMES["desynced"], reason=REASONS["desync"], final_tick=600))

    async def test_a_result_from_a_seat_that_went_away_does_not_count(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await self.clock.turns(20)
        # (Edda claims the end and falls silent: AWAY 5 s after her last word)
        await two.send_message("RESULT", tick=60, hash=b"r" * 8, outcomes=[dict(outcome=OUTCOMES["won"])])
        await self.talk(SPEC["away_ms"] // SPEC["turn_ms"] + 40, one)
        await until(lambda: self.match().seats[1].state == "away")
        self.assertTrue(self.server.matches, "an away seat's claim decides nothing")
        await one.send_message("RESULT", tick=300, hash=b"q" * 8, outcomes=[dict(outcome=OUTCOMES["lost"])])
        end = await one.until("MATCH_END", skip=("TURN", "LINKS", "PONG"))
        self.assertEqual(end, dict(outcome=OUTCOMES["lost"], reason=REASONS["result"], final_tick=300))

    async def test_a_silent_seat_is_away_and_comes_back(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        for _ in range(3):
            # (Tamsin pings every 2 s, as a game does)
            await self.clock.turns(40)
            await one.send_message("PING", client_ms=0, rtt_ms=5)
            await one.until("PONG", skip=("TURN", "LINKS"))
        # Not a word from Edda since START: AWAY in the turn sealed 5 s after
        # it (START, 1.5 s to turn 0's opening, then 3.5 s of turns).
        turns = [await two.until("TURN", skip=("LINKS",)) for _ in range(120)]
        marked = [(t["turn"], [c["type"] for c in t["commands"]]) for t in turns if t["commands"]]
        away_turn = (SPEC["away_ms"] - SPEC["start_delay_ms"]) // SPEC["turn_ms"] - 1
        self.assertEqual(marked, [(away_turn, [SYSTEM["AWAY"]["type"]])])
        self.assertEqual([seat.state for seat in self.match().seats], ["present", "away"])
        # Any word from her hands the seat BACK (the simulation waits for the next window).
        await two.send_message("VISIBILITY", state=0)
        await until(lambda: self.match().sequencer.system)
        await self.clock.turns(1)
        turn = await two.until("TURN")
        self.assertEqual((turn["turn"], [c["type"] for c in turn["commands"]]), (120, [SYSTEM["BACK"]["type"]]))

    async def test_everyone_gone_ends_the_match(self):
        await self.start()
        one, two = await self.join("Tamsin", 1), await self.join("Edda", 2)
        await start_match(self.clock, (one, two))
        await one.send_message("LEAVE_MATCH")
        await until(lambda: self.match().seats[0].state == "left")
        self.assertEqual(len(self.server.matches), 1)
        await two.drop()
        await until(lambda: not self.server.matches)

    async def test_the_cap_sends_timeout_and_ends_without_results(self):
        await self.start("classic:1", match_cap_ms=500)
        one = await self.join("Tamsin", 1)
        await start_match(self.clock, (one,))
        await self.clock.turns(11)
        turns = [await one.until("TURN") for _ in range(11)]
        self.assertEqual(turns[10], dict(turn=10, commands=[dict(seat=255, seq=1, type=SYSTEM["TIMEOUT"]["type"],
                                                                  a=0, b=0, c=0)]))
        await self.clock.turns(5)
        self.assertTrue(await one.quiet())        # (nothing sealed after TIMEOUT)
        await self.clock.advance(SPEC["result_wait_ms"])
        end = await one.until("MATCH_END")
        self.assertEqual(end, dict(outcome=OUTCOMES["aborted"], reason=REASONS["timeout"], final_tick=30))


class GoldenTranscriptTests(unittest.TestCase):
    def test_the_transcripts_are_current(self):
        """Re-recorded now, every transcript is byte for byte the committed
        one: the server and the codec still say exactly what the GDScript
        codec is tested against (python3 server/tools/record_transcripts.py)."""
        with tempfile.TemporaryDirectory() as temporary:
            fresh = Path(temporary)
            names = asyncio.run(record_transcripts.record_all(fresh))
            self.assertEqual(names, ["m1_codec.bin", "m1_codec.json", "m1_dev_match.bin", "m1_dev_match.json",
                                     "m1_handshake.bin", "m1_handshake.json", "m3_back.bin", "m3_back.json",
                                     "m3_barrier.bin", "m3_barrier.json", "m3_party.bin", "m3_party.json",
                                     "m4_resilience.bin", "m4_resilience.json"])
            for name in names:
                committed = record_transcripts.TRANSCRIPTS / name
                self.assertEqual(committed.read_bytes(), (fresh / name).read_bytes(), name + " changed: re-record it")

    def test_every_record_decodes_to_its_json_and_encodes_back(self):
        seen = set()
        for path in sorted(record_transcripts.TRANSCRIPTS.glob("m[134]_*.bin")):
            records = record_transcripts.read(path)
            listed = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))["records"]
            self.assertEqual(len(records), len(listed))
            for (direction, client, data), entry in zip(records, listed):
                kind, fields = protocol.decode(data)
                self.assertEqual((("c2s", "s2c")[direction], client, kind), (entry["dir"], entry["client"], entry["type"]))
                self.assertEqual(record_transcripts.plain(fields), entry["fields"])
                self.assertEqual(protocol.encode(kind, **fields), data)
                seen.add(kind)
        self.assertEqual(seen, set(SPEC["messages"]))


    def test_m4_resilience_is_what_the_server_says_of_resilience(self):
        """README, Resilience, as the server served it: a checkpoint asked
        and uploaded, each RESYNC reason with the parts behind it, a rejoin's
        MATCH_CONFIG and ERROR 12 to the link it replaced, LINKS catching_up,
        AWAY, BACK and LEFT, desynced_twice and no_held_seat."""
        records = record_transcripts.read(record_transcripts.TRANSCRIPTS / "m4_resilience.bin")
        said = [(("c2s", "s2c")[direction], client, *protocol.decode(data)) for direction, client, data in records]

        def sent(name, side="s2c"):
            return [(client, fields) for direction, client, kind, fields in said if kind == name and direction == side]
        reasons = SPEC["resync_reasons"]
        self.assertEqual([(client, f["reason"], f["checkpoint_tick"], f["parts"]) for client, f in sent("RESYNC")],
                         [(2, reasons["desync"], 0, 0), (3, reasons["rejoin"], 360, 2), (2, reasons["behind"], 360, 2)])
        self.assertEqual([(client, f["tick"]) for client, f in sent("CHECKPOINT_ASK")], [(0, 60), (0, 360)])
        self.assertEqual(len(sent("CHECKPOINT_PART", "c2s")), 4)
        self.assertEqual([(client, f["tick"], f["part"]) for client, f in sent("CHECKPOINT_PART")],
                         [(3, 360, 0), (3, 360, 1), (2, 360, 0), (2, 360, 1)])
        self.assertEqual([(c, f["your_seat"], f["flags"]) for c, f in sent("MATCH_CONFIG") if f["flags"]],
                         [(3, 1, SPEC["config_flags"]["rejoin"])])
        self.assertEqual([(client, f["code"]) for client, f in sent("ERROR")], [(1, SPEC["errors"]["replaced"])])
        self.assertEqual([(client, f["code"]) for client, f in sent("NOTICE")], [(4, SPEC["notices"]["no_held_seat"])])
        self.assertEqual([(client, f["outcome"], f["reason"]) for client, f in sent("MATCH_END")],
                         [(2, SPEC["outcomes"]["desynced"], SPEC["end_reasons"]["desynced_twice"])])
        self.assertTrue(any(seat["flags"] & SPEC["link_flags"]["catching_up"]
                            for _, f in sent("LINKS") for seat in f["seats"]))
        system = {spec["type"]: name for name, spec in SPEC["system_commands"].items()}
        commands = [(system[c["type"]], c["a"]) for client, f in sent("TURN") if client == 0 for c in f["commands"]]
        self.assertEqual(commands, [("AWAY", 1), ("AWAY", 2), ("BACK", 1), ("BACK", 2), ("LEFT", 2)])


class ProgramTests(unittest.TestCase):
    def test_dev_match_from_the_command_line_on_port_0(self):
        with tempfile.TemporaryDirectory() as temporary:
            events = Path(temporary) / "events.jsonl"
            # (a folder of its own: no server.ini of the checkout's is read)
            process = subprocess.Popen([sys.executable, str(ROOT / "server" / "main.py"), "--dev-match", "classic:2",
                                        "--host", "127.0.0.1", "--port", "0", "--event-log", str(events)],
                                       cwd=temporary, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                       env=dict(os.environ, PYTHONUNBUFFERED="1"))
            try:
                line = process.stdout.readline()
                self.assertRegex(line, r"^listening port=\d+ host=127\.0\.0\.1 path=/causeway$")
                port = int(line.split()[1].split("=")[1])
                self.assertNotEqual(port, 0)
                # (godot-agent's topology waits for this pattern on the server's output)
                self.assertEqual(re.search(KIT_READY, line)["port"], str(port))
                listening = json.loads(events.read_text().splitlines()[0])
                self.assertEqual((listening["event"], listening["port"], listening["dev_match"]),
                                 ("listening", port, "classic:2"))
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                    health = json.loads(response.read())
                self.assertEqual((health["status"], health["dev_match"], health["protocol"]), ("ok", "classic:2", 1))
                self.assertEqual(asyncio.run(self.two_players(port)), [0, 1])
                banner = "".join(process.stdout.readline() for _ in range(3))
                self.assertIn('The Groundhold server "Groundhold" is open on port', banner)
            finally:
                process.terminate()
                process.wait(timeout=10)
                process.stdout.close()
            self.assertEqual(process.returncode, 0)

    async def two_players(self, port):
        one, two = Client(), Client()
        await one.hello(port, "Tamsin", token=b"\x01" * 16)
        await two.hello(port, "Edda", token=b"\x02" * 16)
        seats = [(await client.until("MATCH_CONFIG", timeout=5))["your_seat"] for client in (one, two)]
        await one.bye()
        await two.bye()
        return seats


if __name__ == "__main__":
    unittest.main()
