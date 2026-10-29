"""Turns seal on absolute deadlines (docs/design/core-loop.md §6.3, §7.3):
no drift over ten minutes of a loop that always wakes late, a stalled loop
seals the missed turns in a burst, and a real server's turns keep pace with
the wall clock."""

import asyncio
import random
import time
import unittest

from support import MS, RULES, TICK0, Client, ManualClock, server
from groundhold_server.match import TURN_NS, TurnClock, TurnLoop
from groundhold_server.protocol import SPEC

TEN_MINUTES = 600_000 * MS


class LateClock:
    """A loop that oversleeps every sleep by 0 to 9 ms (seeded), as an event
    loop under load does; time moves only by sleeping. `stall` adds a
    one-off jump of that many ms at the given wake."""

    def __init__(self, seed=1, stall=None):
        self.time = 0
        self.random = random.Random(seed)
        self.wakes = 0
        self.stall = stall

    def now(self):
        return self.time

    async def sleep_until(self, deadline):
        self.wakes += 1
        self.time = max(self.time, deadline) + self.random.randrange(0, 10 * MS)
        if self.stall and self.wakes == self.stall[0]:
            self.time += self.stall[1] * MS
        await asyncio.sleep(0)


async def naive_loop(clock, seal, until):
    """Cyberworld's tick loop, for contrast: sleep a turn's length, then
    seal one turn. Each wake-up's lateness is added to the next."""
    turn = 0
    while clock.now() < until:
        await clock.sleep_until(clock.now() + TURN_NS)
        seal(turn, clock.now())
        turn += 1


class TurnClockTests(unittest.IsolatedAsyncioTestCase):
    def test_deadlines_are_exact_integers(self):
        clock = TurnClock(origin=1_000_000_123)
        self.assertEqual(clock.deadline(0), 1_000_000_123 + 50 * MS)
        self.assertEqual(clock.deadline(11_999), 1_000_000_123 + 600_000 * MS)
        self.assertEqual(clock.due(1_000_000_123), 0)
        self.assertEqual(clock.due(1_000_000_123 + 50 * MS - 1), 0)
        self.assertEqual(clock.due(1_000_000_123 + 50 * MS), 1)
        self.assertEqual(clock.due(0), 0)       # (before the origin: none)
        for value in (clock.deadline(7), clock.due(10 ** 12)):
            self.assertIsInstance(value, int)

    async def run_ten_minutes(self, clock):
        """Turns until the one that closes at ten minutes (turn 11,999) is sealed."""
        sealed = []
        loop = None

        def seal(turn, now):
            sealed.append((turn, now))
            if turn == 11_999:
                loop.running = False
        loop = TurnLoop(clock, 0, seal)
        await loop.run()
        return sealed, loop

    async def test_no_drift_over_ten_minutes_of_late_wakes(self):
        clock = LateClock(seed=1)
        sealed, loop = await self.run_ten_minutes(clock)
        # Every turn sealed, in order, none early, and the lateness never adds
        # up: the 12,000th turn closes within one wake's oversleep of 10:00.
        self.assertEqual([turn for turn, _ in sealed], list(range(12_000)))
        lateness = [now - loop.turns.deadline(turn) for turn, now in sealed]
        self.assertGreaterEqual(min(lateness), 0)
        self.assertLess(max(lateness), 10 * MS)
        self.assertEqual(loop.turns.deadline(11_999), TEN_MINUTES)
        self.assertLess(sealed[-1][1], TEN_MINUTES + 10 * MS)
        self.assertEqual(loop.turns.due(clock.now()), len(sealed))

    async def test_the_same_late_wakes_make_cyberworlds_loop_drift(self):
        # (why the deadlines are absolute: the same clock, a relative sleep)
        clock = LateClock(seed=1)
        sealed = []
        await naive_loop(clock, lambda turn, now: sealed.append(turn), TEN_MINUTES)
        self.assertLess(len(sealed), 11_500)

    async def test_a_stalled_loop_seals_the_missed_turns_in_a_burst(self):
        # A one-second stall on the 101st wake: the next wake seals the twenty
        # turns it missed at once, then the loop is back on its deadlines.
        clock = LateClock(seed=2, stall=(101, 1000))
        sealed, loop = await self.run_ten_minutes(clock)
        self.assertEqual([turn for turn, _ in sealed], list(range(12_000)))
        self.assertLess(sealed[-1][1], TEN_MINUTES + 10 * MS)
        times = {}
        for turn, now in sealed:
            times.setdefault(now, []).append(turn)
        bursts = [turns for turns in times.values() if len(turns) > 1]
        self.assertEqual(len(bursts), 1)
        self.assertGreaterEqual(len(bursts[0]), 20)
        self.assertEqual(bursts[0], list(range(bursts[0][0], bursts[0][0] + len(bursts[0]))))
        self.assertEqual(loop.turns.due(clock.now()), len(sealed))

    async def test_a_stalled_server_sends_the_missed_turns_in_order(self):
        clock = ManualClock()
        game = server(dev_match="classic:2", clock=clock)
        port = await game.start("127.0.0.1", 0)
        try:
            one, two = Client(), Client()
            await one.hello(port, "Tamsin")
            await two.hello(port, "Edda", token=b"\x02" * 16)
            for client in (one, two):
                await client.until("MATCH_CONFIG")
                await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
            await clock.advance(SPEC["loading_min_ms"])
            for client in (one, two):
                await client.until("START", skip=("LOAD_STATE",))
            await clock.advance(1500)
            await clock.turns(3)
            await clock.advance(1000)       # a one-second stall
            for client in (one, two):
                turns = [(await client.until("TURN"))["turn"] for _ in range(23)]
                self.assertEqual(turns, list(range(23)))
                self.assertTrue(await client.quiet())
            await one.bye()
            await two.bye()
        finally:
            await game.close()

    async def test_a_real_servers_turns_keep_pace_with_the_wall_clock(self):
        game = server(dev_match="classic:1", start_delay_ms=0, loading_min_ms=0)
        port = await game.start("127.0.0.1", 0)
        try:
            client = Client()
            await client.hello(port)
            await client.until("MATCH_CONFIG")
            await client.send_message("LOADED", rules_hash=RULES, tick0_hash=TICK0)
            await client.until("START", skip=("LOAD_STATE",))
            started = time.monotonic()
            turns = []
            while time.monotonic() - started < 1.0:
                fields = await client.until("TURN", skip=("LINKS",))
                turns.append(fields["turn"])
            elapsed = time.monotonic() - started
            self.assertEqual(turns, list(range(len(turns))))
            self.assertLessEqual(abs(len(turns) - elapsed / 0.05), 3)
            await client.bye()
        finally:
            await game.close()


if __name__ == "__main__":
    unittest.main()
