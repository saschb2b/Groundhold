"""tools/net/smoke.py's own checks on made-up logs: the tick rate over its window, the
RESULT a client may miss when the majority ends the match first, --mode tide_race's
arguments and its race check, a build without the mode's rules named first, --flow
--queue's check and its games, and when the project is imported before its games start.

    python3 -m unittest tools/net/test_smoke.py

Nothing here starts a server or a game.
"""

import contextlib
import io
import pathlib
import random
import sys
import tempfile
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


class LingerTests(unittest.TestCase):
    """--flow --linger S: every game stays S seconds on the results before Play again (review M5
    round 2: past the server's 15 s of silence the plate lost the party)."""

    def commands(self, linger):
        import argparse
        import tempfile
        with tempfile.TemporaryDirectory() as out:
            args = argparse.Namespace(clients=2, builders="lamplighter,lookout", no_bot=True, linger=linger,
                                      godot="godot", out=out)
            flow = smoke.Flow(args)
            spawned = []
            flow.spawn = lambda command, log, **options: spawned.append(command)
            flow.start_clients(8766)
            return spawned

    def test_each_game_is_told_how_long_to_linger(self):
        for command in self.commands(20):
            self.assertIn("--linger=20", command)
            self.assertIn("--flow-bot", command)
        for command in self.commands(0):
            self.assertFalse(any(arg.startswith("--linger") for arg in command))

    def test_only_with_flow(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            smoke.main(["--linger", "20"])


class RaceModeTests(unittest.TestCase):
    """--mode tide_race (M6): a dev match of two teams, its arguments and its check."""

    def error(self, *argv):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as said:
            smoke.main(list(argv))
        return said.getvalue()

    def test_a_mode_the_protocol_knows_and_two_even_teams(self):
        self.assertIn("--mode is one of", self.error("--mode", "duel"))
        self.assertIn("even number of clients", self.error("--mode", "tide_race", "--clients", "3"))
        self.assertIn("takes 2 to 4 clients", self.error("--mode", "tide_race", "--clients", "1"))
        self.assertIn("takes 2 to 2 clients", self.error("--mode", "undertow", "--clients", "4"))
        self.assertIn("--flow plays the hub's mode", self.error("--flow", "--mode", "tide_race"))
        self.assertEqual(smoke.mode_problem("tide_race", 2), "")
        self.assertEqual(smoke.mode_problem("tide_race", 4), "")
        self.assertEqual(smoke.mode_problem("classic", 3), "")

    def test_the_server_runs_the_race_as_a_dev_match(self):
        import argparse
        with tempfile.TemporaryDirectory() as out:
            args = argparse.Namespace(mode="tide_race", clients=2, seed=1, turn_ms=10, out=out, server=None)
            race = smoke.Smoke(args)
            command = race.server_command()
            self.assertIn("tide_race:2", command)
            self.assertEqual(command[command.index("--turn-ms") + 1], "10")
            self.assertTrue(race.race())
            self.assertFalse(smoke.Smoke(argparse.Namespace(mode="classic", out=out)).race())

    def test_results_share_the_tick_and_hash_and_the_teams_answer_each_other(self):
        self.assertEqual(smoke.result_key("RESULT 43200 ab12 won", True), smoke.result_key("RESULT 43200 ab12 lost", True))
        self.assertNotEqual(smoke.result_key("RESULT 43200 ab12 won", False),
                            smoke.result_key("RESULT 43200 ab12 lost", False))
        seats = {1: (1, 2), 2: (2, 2)}
        self.assertEqual(smoke.race_problems({1: ("won", "result", "9"), 2: ("lost", "result", "9")}, seats), [])
        self.assertEqual(smoke.race_problems({1: ("draw", "result", "9"), 2: ("draw", "result", "9")}, seats), [])
        self.assertTrue(smoke.race_problems({1: ("won", "result", "9"), 2: ("won", "result", "9")}, seats))
        # (a 2v2: seats 1 and 2 against 3 and 4, one outcome a team)
        four = {k: (k, 4) for k in range(1, 5)}
        ends = {1: ("lost",), 2: ("lost",), 3: ("won",), 4: ("won",)}
        self.assertEqual(smoke.race_problems(ends, four), [])
        ends[2] = ("won",)
        self.assertTrue(any("team 0" in p for p in smoke.race_problems(ends, four)))
        self.assertTrue(smoke.race_problems({1: ("won",), 2: ("lost",)}, {1: (1, 2), 2: (1, 2)}))


class NoRulesTests(unittest.TestCase):
    """A dev match of a mode this build has no rules for says so first (review M6: --mode
    tide_race before track A's preset failed with three problems that all came from it)."""

    def test_the_missing_rules_lead_the_problems(self):
        import argparse
        with tempfile.TemporaryDirectory() as out:
            folder = pathlib.Path(out)
            for k in (1, 2):
                (folder / f"client{k}.log").write_text(
                    "NET FAILED This game cannot play the server's mode (2)\n", encoding="utf-8")
            (folder / "server.log").write_text("", encoding="utf-8")
            args = argparse.Namespace(mode="tide_race", clients=2, seed=1, turn_ms=10, out=out, server=None,
                                      rate_floor=0.8, shaper=False, faults=False)
            race = smoke.Smoke(args)
            done = argparse.Namespace(returncode=1)
            report = race.check([(1, done, folder / "client1.hashes"), (2, done, folder / "client2.hashes")])
            self.assertFalse(report["ok"])
            self.assertIn("has no tide_race rules", report["problems"][0])


def queue_log(code, match=7, seat=1, config="lamplighter,lookout,beekeeper,bellfounder", back="queued"):
    """A --flow --queue game's FLOW lines, as tests/net/flow_bot.gd prints them."""
    return [f"FLOW party {code} members 1 me 0 leader", "FLOW state HUB", f"FLOW queued {code}",
            "FLOW state MATCH_FOUND", f"FLOW found {match} seats 4", "FLOW state LOADING",
            f"FLOW match high_water seat {seat} of 4 builders lamplighter,lookout,lamplighter,lamplighter",
            f"FLOW config builders {config}", "FLOW state IN_MATCH", "MATCH_END lost result 9000",
            "FLOW state RESULTS", "FLOW results lost The Tide Took the Hearth", "FLOW state HUB",
            "FLOW state MATCH_FOUND", f"FLOW queued {code}", f"FLOW back {code} members 1 phase {back}"]


class QueueFlowTests(unittest.TestCase):
    """--flow --queue (M6, review of track D): four games, each a party of one, meet through the
    real server's queue: the check on their logs, the games' commands and the arguments."""

    def games(self, **changed):
        logs = {k: queue_log(code, seat=k) for k, code in enumerate(["B2C3D", "F4G5H", "J6K7M", "N8P9Q"], start=1)}
        for k, lines in changed.items():
            logs[int(k[1:])] = lines
        return {k: smoke.queue_game(lines) for k, lines in logs.items()}

    def test_a_game_through_the_queue_and_back_into_it(self):
        seen = smoke.queue_game(queue_log("B2C3D"))
        self.assertEqual(seen["steps"], smoke.QUEUE_STEPS)
        self.assertEqual(seen["found"], ("7", "4"))
        self.assertEqual(seen["config"], ["lamplighter", "lookout", "beekeeper", "bellfounder"])
        self.assertEqual(seen["back"], ("B2C3D", "1", "queued"))
        self.assertEqual(smoke.queue_problems(self.games()), [])

    def test_what_the_check_refuses(self):
        shared = queue_log("N8P9Q", seat=4, config="lamplighter,lookout,lamplighter,bellfounder")
        self.assertTrue(any("share one" in p for p in smoke.queue_problems(
            self.games(c1=queue_log("B2C3D", config="lamplighter,lookout,lamplighter,bellfounder"),
                       c2=queue_log("F4G5H", seat=2, config="lamplighter,lookout,lamplighter,bellfounder"),
                       c3=queue_log("J6K7M", seat=3, config="lamplighter,lookout,lamplighter,bellfounder"),
                       c4=shared))))
        self.assertTrue(any("different Builders" in p for p in smoke.queue_problems(self.games(c4=shared))))
        forming = queue_log("N8P9Q", seat=4, back="forming")
        self.assertTrue(any("did not queue it again" in p for p in smoke.queue_problems(self.games(c4=forming))))
        same = queue_log("B2C3D", seat=4)
        self.assertTrue(any("party of its own" in p for p in smoke.queue_problems(self.games(c4=same))))
        apart = queue_log("N8P9Q", seat=4, match=8)
        self.assertTrue(any("one match" in p for p in smoke.queue_problems(self.games(c4=apart))))
        twice = queue_log("N8P9Q", seat=3)
        self.assertTrue(any("one each" in p for p in smoke.queue_problems(self.games(c4=twice))))
        short = [line for line in queue_log("N8P9Q", seat=4) if not line.startswith("FLOW found")]
        self.assertTrue(any("client 4 went" in p for p in smoke.queue_problems(self.games(c4=short))))

    def test_hash_streams_equal_to_the_end(self):
        self.assertEqual(smoke.stream_problems({1: {60: "a", 120: "b"}, 2: {60: "a", 120: "b"}}, 150)[0], [])
        self.assertTrue(smoke.stream_problems({1: {60: "a"}, 2: {60: "x"}}, 60)[0])
        self.assertTrue(smoke.stream_problems({1: {60: "a"}, 2: {60: "a"}}, 900)[0])

    def test_each_game_alone_through_the_queue(self):
        with tempfile.TemporaryDirectory() as out:
            args = smoke.parse_args(["--flow", "--queue", "--no-bot", "--out", out, "--godot", "godot"])
            self.assertEqual((args.clients, args.builders), (4, "lamplighter"))
            flow = smoke.QueueFlow(args)
            spawned = []
            flow.spawn = lambda command, log, **options: spawned.append(command)
            flow.start_clients(8766)
        self.assertEqual(len(spawned), 4)
        for k, command in enumerate(spawned, start=1):
            self.assertIn("--queue", command)
            self.assertIn("--flow-bot", command)
            self.assertIn("--main=lamplighter", command)
            self.assertIn(f"--name=Queue{k}", command)
            self.assertFalse(any(arg.startswith(("--code", "--party")) for arg in command))

    def test_the_arguments(self):
        def error(*argv):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as said:
                smoke.parse_args(list(argv))
            return said.getvalue()
        self.assertIn("--queue is --flow's", error("--queue"))
        self.assertIn("four games", error("--flow", "--queue", "--clients", "2"))
        self.assertEqual(smoke.parse_args([]).clients, 2)
        self.assertEqual(smoke.parse_args(["--flow"]).builders, "lamplighter,lookout")


class ClassCacheTests(unittest.TestCase):
    def tree(self, cache, scripts):
        root = pathlib.Path(tempfile.mkdtemp(prefix="smoke-cache-"))
        for name, text in scripts.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        if cache is not None:
            (root / ".godot").mkdir()
            (root / ".godot" / "global_script_class_cache.cfg").write_text(
                "list=[" + ", ".join('{\n"class": &"%s",\n"path": "res://x.gd"\n}' % c for c in cache) + "]\n",
                encoding="utf-8")
        return root

    def test_a_class_the_cache_lacks_is_missing(self):
        scripts = {"scripts/net/a.gd": "class_name Checkpointing\nextends RefCounted\n",
                   "tests/b.gd": "extends Node\n", "scripts/c.gd": "## x\nclass_name SimTargeting\n"}
        self.assertEqual(smoke.missing_classes(self.tree(["Checkpointing"], scripts)), ["SimTargeting"])
        self.assertEqual(smoke.missing_classes(self.tree(None, scripts)), ["Checkpointing", "SimTargeting"])
        self.assertEqual(smoke.missing_classes(self.tree(["Checkpointing", "SimTargeting"], scripts)), [])


if __name__ == "__main__":
    unittest.main()
