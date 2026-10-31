"""tools/net/smoke.py's own checks on made-up logs: the tick rate over its window, and the
RESULT a client may miss when the majority ends the match first.

    python3 -m unittest tools/net/test_smoke.py

Nothing here starts a server or a game.
"""

import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import smoke  # noqa: E402


def stream(rate, seconds, every=60, jitter_ms=1, seed=1, stall=None):
    """HASH stamps [wall s, tick] of a client running `rate` ticks a second, one every
    `every` ticks, each printed a few ms late; `stall` = (from s, for s) stops it there,
    after which it runs the missed ticks at once."""
    rng = random.Random(seed)
    stamps, tick = [], every
    while True:
        t = tick / rate
        if stall and t >= stall[0]:
            t += stall[1]
        if t > seconds:
            return stamps
        stamps.append([1000.0 + t + rng.uniform(0, jitter_ms / 1000), tick])
        tick += every


class TickRateTests(unittest.TestCase):
    def test_a_steady_60_a_second_measures_60_at_the_protocols_hash_pace(self):
        # (50 ms turns: one HASH a second, so a 3 s window holds 3 or 4 of them by a few ms)
        for seed in range(20):
            rate, _ = smoke.rate_floor(stream(60, 120, seed=seed), smoke.RATE_WINDOW)
            self.assertAlmostEqual(rate, 60, delta=1, msg=f"seed {seed}")

    def test_59_and_61_a_second_measure_as_themselves(self):
        for steady in (59, 61):
            rate, _ = smoke.rate_floor(stream(steady, 120), smoke.RATE_WINDOW)
            self.assertAlmostEqual(rate, steady, delta=1)

    def test_a_dev_matchs_faster_hashes_measure_the_same(self):
        rate, _ = smoke.rate_floor(stream(300, 60), smoke.RATE_WINDOW)
        self.assertAlmostEqual(rate, 300, delta=3)

    def test_a_real_3_s_stall_is_seen_and_placed(self):
        rate, at = smoke.rate_floor(stream(60, 120, stall=(40, 3)), smoke.RATE_WINDOW)
        self.assertLess(rate, 48, "a 3 s stall drops the rate below the floor")
        self.assertTrue(35 <= at <= 41, at)

    def test_too_few_stamps_measure_nothing(self):
        self.assertIsNone(smoke.rate_floor(stream(60, 2), smoke.RATE_WINDOW))


class ResultTests(unittest.TestCase):
    def test_a_client_a_few_ticks_short_of_the_majoritys_result_may_miss_its_own(self):
        ends = {1: ("won", "result", "23216"), 2: ("won", "result", "23216"), 3: ("won", "result", "23216")}
        results = {1: "RESULT 23216 ab won", 3: "RESULT 23216 ab won"}
        self.assertEqual(smoke.missing_results(ends, results), [])

    def test_a_client_without_result_is_named_when_nobody_ended_it(self):
        ends = {1: ("desynced", "desync", "600"), 2: ("desynced", "desync", "600")}
        self.assertEqual(smoke.missing_results(ends, {}), [1, 2])
        ends = {1: ("won", "result", "900"), 2: ("won", "result", "900")}
        self.assertEqual(smoke.missing_results(ends, {1: "RESULT 840 ab won"}), [2])


if __name__ == "__main__":
    unittest.main()
