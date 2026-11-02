"""tools/net/smoke.py's own checks on made-up logs: the tick rate over its window, the
RESULT a client may miss when the majority ends the match first, --mode tide_race's
arguments and its race check, --mode undertow's (the duel, one a side, and what each game's
plan bot says it corked, uncorked and sent down the rival's road), a build without the
mode's rules named first, --flow --queue's check and its games (and M7's duellists finding
each other with --mode undertow), and when the project is imported before its games start.

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
                                      godot="godot", out=out, difficulty=None)
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


class DuelModeTests(unittest.TestCase):
    """--mode undertow (M7): the duel as a dev match, one client a side, checked as a race."""

    def error(self, *argv):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as said:
            smoke.main(list(argv))
        return said.getvalue()

    def test_two_clients_one_a_side(self):
        for clients in ("1", "3", "4"):
            self.assertIn("takes 2 to 2 clients", self.error("--mode", "undertow", "--clients", clients))
        self.assertEqual(smoke.mode_problem("undertow", 2), "")
        self.assertEqual(smoke.parse_args(["--mode", "undertow"]).clients, 2)

    def test_the_server_runs_the_duel_as_a_dev_match(self):
        import argparse
        with tempfile.TemporaryDirectory() as out:
            duel = smoke.Smoke(argparse.Namespace(mode="undertow", clients=2, seed=1, turn_ms=10, out=out, server=None))
            command = duel.server_command()
            self.assertIn("undertow:2", command)
            self.assertEqual(command[command.index("--turn-ms") + 1], "10")
            self.assertTrue(duel.race() and duel.duel())
            race = smoke.Smoke(argparse.Namespace(mode="tide_race", clients=2, seed=1, turn_ms=10, out=out, server=None))
            self.assertTrue(race.race())
            self.assertFalse(race.duel())

    def logs(self, folder, outcomes, seats=(1, 2), duels=None):
        for k, (outcome, seat) in enumerate(zip(outcomes, seats), start=1):
            played = "\n".join(duel_lines(seat) if duels is None else duels[k - 1])
            (folder / f"client{k}.log").write_text(
                f"MATCH 1 seat {seat} of 2 seed 1\nHASH 0 aa\nHASH 60 bb\n{played}\nHASH 120 cc\n"
                f"RESULT 150 dd {outcome}\nMATCH_END {outcome} result 150\n", encoding="utf-8")
        (folder / "server.log").write_text("", encoding="utf-8")

    def check(self, outcomes, seats=(1, 2), duels=None, no_bot=False):
        import argparse
        with tempfile.TemporaryDirectory() as out:
            folder = pathlib.Path(out)
            self.logs(folder, outcomes, seats, duels)
            args = argparse.Namespace(mode="undertow", clients=2, seed=1, turn_ms=10, out=out, server=None,
                                      rate_floor=0.8, shaper=False, faults=False, no_bot=no_bot)
            done = argparse.Namespace(returncode=0)
            return smoke.Smoke(args).check([(1, done, folder / "client1.hashes"), (2, done, folder / "client2.hashes")])

    def test_a_duel_ends_won_against_lost_or_a_draw_for_both(self):
        self.assertEqual(self.check(("won", "lost"))["problems"], [])
        self.assertEqual(self.check(("draw", "draw"))["problems"], [])
        self.assertTrue(any("one wins and one loses" in p for p in self.check(("won", "won"))["problems"]))
        # (both games in one seat are no duel)
        self.assertTrue(any("a duel is seat 1 of 2" in p for p in self.check(("won", "lost"), (1, 1))["problems"]))

    def test_what_a_duelling_bot_says(self):
        seen = smoke.duel_game(duel_lines(1) + ["BOT bottle 120 window 3 fizzled", "BOT seawall wave 6 seq 10",
                                                "BOT seawall rose wave 6 charges 1", "HASH 60 aa"])
        self.assertEqual((seen["corks"], seen["uncorks"], seen["seawalls"], seen["rose"]), (1, 1, 1, 1))
        self.assertEqual(seen["corked"], [(90, 2, 0)])
        self.assertEqual(seen["uncorked"], [(90, 2, "winged", "bot")])
        self.assertEqual(seen["fizzled"], [120])
        self.assertEqual(seen["walking"], [(2, 1, 3)])

    def test_each_side_corks_and_uncorks_and_a_pack_walks_across(self):
        # (CORK, UNCORK and SEAWALL cross the server: the duel's check reads what each game's
        # simulation did with them, from its plan bot's BOT lines)
        report = self.check(("won", "lost"))
        self.assertTrue(report["ok"])
        self.assertIn("client 1: 1 corked, 1 uncorked by the bot", report["duel"])
        uncorked_by_the_client = [line.replace("by bot", "by client") for line in duel_lines(2)]
        never_corked = [line for line in duel_lines(1) if " cork" not in line and "uncork" not in line]
        problems = self.check(("won", "lost"), duels=[never_corked, uncorked_by_the_client])["problems"]
        self.assertTrue(any(p.startswith("client 1 never corked") for p in problems), problems)
        self.assertTrue(any(p.startswith("client 2's bot never uncorked a bottle itself") for p in problems), problems)
        nowhere = [[line for line in duel_lines(seat) if "walking" not in line] for seat in (1, 2)]
        self.assertIn("no uncorked pack walked a rival's road",
                      self.check(("draw", "draw"), duels=nowhere)["problems"])
        # (--no-bot: nobody corks, and only the race's check is made)
        self.assertEqual(self.check(("draw", "draw"), duels=[[], []], no_bot=True)["problems"], [])


def duel_lines(seat):
    """A duelling plan bot's BOT lines (tests/bot.gd) for one corked and uncorked pack."""
    return [f"BOT cork winged window 2 seq {seat + 2}", f"BOT bottle {88 + 2 * seat} window 2 tier 0 corked",
            f"BOT uncork bottle {88 + 2 * seat} window 2 seq {seat + 3}",
            f"BOT bottle {88 + 2 * seat} window 2 uncorked winged by bot",
            f"BOT walking wave 2 hollow {2 - seat} creeps 3"]


def queue_log(code, match=7, seat=1, config="lamplighter,lookout,beekeeper,bellfounder", back="queued",
              mode="high_water", seats=4, fielded="lamplighter,lookout,lamplighter,lamplighter"):
    """A --flow --queue game's FLOW lines, as tests/net/flow_bot.gd prints them."""
    return [f"FLOW party {code} members 1 me 0 leader", "FLOW state HUB", f"FLOW queued {code}",
            "FLOW state MATCH_FOUND", f"FLOW found {match} seats {seats}", "FLOW state LOADING",
            f"FLOW match {mode} seat {seat} of {seats} builders {fielded}",
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
        # (M7: two games find each other as rivals in a two-team mode)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "undertow"]).clients, 2)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "tide_race"]).clients, 2)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "high_water"]).clients, 4)
        self.assertIn("plays two games", error("--flow", "--queue", "--mode", "undertow", "--clients", "4"))
        # (the bots' duel through the queue plays to the Surge's end at 50 ms turns: more time)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "undertow"]).timeout, 1500)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "undertow", "--no-bot"]).timeout, 900)
        self.assertEqual(smoke.parse_args(["--mode", "undertow"]).timeout, 900)
        self.assertEqual(smoke.parse_args(["--flow", "--queue", "--mode", "undertow", "--timeout", "60"]).timeout, 60)
        self.assertIn("--mode is one of", error("--flow", "--queue", "--mode", "duel"))
        self.assertIn("--flow plays the hub's mode", error("--flow", "--mode", "undertow"))


class DuelQueueFlowTests(unittest.TestCase):
    """--flow --queue --mode undertow (M7): two games alone find each other as rivals through the
    real server's queue, one a side, each with its own main."""

    def duellist(self, code, seat, config="lamplighter,lamplighter", mode="undertow"):
        return queue_log(code, seat=seat, config=config, mode=mode, seats=2, fielded="lamplighter,lamplighter")

    def games(self, *logs):
        return {k: smoke.queue_game(lines) for k, lines in enumerate(logs, start=1)}

    def test_two_duellists_one_a_side_and_queued_again(self):
        games = self.games(self.duellist("B2C3D", 1), self.duellist("F4G5H", 2))
        mains = ["lamplighter", "lamplighter"]
        self.assertEqual(smoke.queue_problems(games, 2, "undertow", mains), [])
        # (two Lamplighters keep the Lamplighter: High Water's rule would call that a shared one)
        self.assertTrue(any("share one" in p for p in smoke.queue_problems(games, 2)))

    def test_what_the_duels_check_refuses(self):
        mains = ["lamplighter", "lamplighter"]
        unclashed = self.games(self.duellist("B2C3D", 1, "lamplighter,lookout"),
                               self.duellist("F4G5H", 2, "lamplighter,lookout"))
        self.assertTrue(any("never crosses the sides" in p
                            for p in smoke.queue_problems(unclashed, 2, "undertow", mains)))
        raced = self.games(self.duellist("B2C3D", 1, mode="tide_race"), self.duellist("F4G5H", 2, mode="tide_race"))
        self.assertTrue(any("not undertow" in p for p in smoke.queue_problems(raced, 2, "undertow", mains)))

    def queue_check(self, outcomes=("won", "lost"), duels=None, no_bot=False):
        """QueueFlow.check on two duellists' made-up logs: their FLOW lines with the given
        outcomes, their plan bots' BOT lines (`duels`, else one corked and uncorked pack each)
        and equal hash lines."""
        with tempfile.TemporaryDirectory() as out:
            folder = pathlib.Path(out)
            for k, (code, outcome) in enumerate(zip(("B2C3D", "F4G5H"), outcomes), start=1):
                lines = [line if not line.startswith("MATCH_END") else f"MATCH_END {outcome} result 9000"
                         for line in self.duellist(code, k)]
                played = duel_lines(k) if duels is None else duels[k - 1]
                at = lines.index("FLOW state IN_MATCH") + 1
                lines[at:at] = ["HASH 8940 aa"] + played
                (folder / f"client{k}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
            (folder / "server.log").write_text("", encoding="utf-8")
            argv = ["--flow", "--queue", "--mode", "undertow", "--out", out, "--godot", "godot"]
            flow = smoke.QueueFlow(smoke.parse_args(argv + (["--no-bot"] if no_bot else [])))
            done = type("Done", (), {"returncode": 0})()
            return flow.check([(1, done, folder / "client1.hashes"), (2, done, folder / "client2.hashes")])

    def test_the_bots_duel_through_the_queue_one_outcome_a_side(self):
        report = self.queue_check()
        self.assertEqual(report["problems"], [])
        self.assertIn("client 2: 1 corked, 1 uncorked by the bot", report["duel"])
        self.assertTrue(any("one wins and one loses" in p for p in self.queue_check(("lost", "lost"))["problems"]))
        idle = self.queue_check(duels=[[], []])["problems"]
        self.assertTrue(any(p.startswith("client 1 never corked") for p in idle), idle)
        self.assertIn("no uncorked pack walked a rival's road", idle)
        # (--no-bot: the waves called only, nobody corks)
        self.assertEqual(self.queue_check(duels=[[], []], no_bot=True)["problems"], [])

    def test_each_game_queues_in_the_mode(self):
        with tempfile.TemporaryDirectory() as out:
            args = smoke.parse_args(["--flow", "--queue", "--mode", "undertow", "--no-bot", "--out", out,
                                     "--godot", "godot"])
            flow = smoke.QueueFlow(args)
            spawned = []
            flow.spawn = lambda command, log, **options: spawned.append(command)
            flow.start_clients(8766)
            self.assertIn("undertow", flow.header())
            high = smoke.QueueFlow(smoke.parse_args(["--flow", "--queue", "--out", out, "--godot", "godot"]))
            others = []
            high.spawn = lambda command, log, **options: others.append(command)
            high.start_clients(8766)
        self.assertEqual(len(spawned), 2)
        for command in spawned:
            self.assertIn("--mode=undertow", command)
            self.assertIn("--queue", command)
        self.assertFalse(any(arg.startswith("--mode") for command in others for arg in command))


class DifficultyTests(unittest.TestCase):
    """--flow --difficulty LEVEL (M8): the party's level, or each queued game's, and its check."""

    def spawned(self, *argv):
        with tempfile.TemporaryDirectory() as out:
            args = smoke.parse_args(["--flow", "--no-bot", "--out", out, "--godot", "godot", *argv])
            flow = (smoke.QueueFlow if args.queue else smoke.Flow)(args)
            commands = []
            flow.spawn = lambda command, log, **options: commands.append(command)
            flow.start_clients(8766)
            return commands

    def test_the_leader_makes_the_party_at_it_and_every_queued_game_queues_at_it(self):
        leader, member = self.spawned("--difficulty", "hard")
        self.assertIn("--difficulty=hard", leader)
        self.assertFalse(any(arg.startswith("--difficulty") for arg in member))
        queued = self.spawned("--queue", "--difficulty", "very_hard")
        self.assertEqual(len(queued), 4)
        self.assertTrue(all("--difficulty=very_hard" in command for command in queued))
        self.assertFalse(any(arg.startswith("--difficulty") for command in self.spawned() for arg in command))

    def test_only_with_flow_and_only_a_level(self):
        for argv in (["--difficulty", "hard"], ["--flow", "--difficulty", "brutal"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                smoke.parse_args(argv)

    def test_the_check_reads_every_games_level_and_the_servers(self):
        good = ["FLOW config builders lamplighter,lookout", "FLOW level hard rules hard lives 15 numbers ok"]
        events = '{"event": "match", "match": 1, "mode": "high_water", "level": "hard"}\n'
        self.assertEqual(smoke.level_problems({1: good, 2: good}, events, "hard"), [])
        problems = smoke.level_problems({1: good, 2: ["FLOW level hard rules normal lives 20 numbers ok"], 3: []},
                                        events.replace('"hard"', '"normal"'), "hard")
        self.assertEqual(len(problems), 3)
        self.assertIn("client 2 played", problems[0])
        self.assertIn("client 3 said no FLOW level line", problems[1])
        self.assertIn("not hard", problems[2])
        # (rules named Hard that keep Normal's numbers are no Hard match: the check reads them)
        named_only = ["FLOW level hard rules hard lives 20 numbers hard: lives 20, not 15"]
        problems = smoke.level_problems({1: good, 2: named_only}, events, "hard")
        self.assertEqual(len(problems), 1)
        self.assertIn("client 2's rules named hard but its numbers differ: hard: lives 20, not 15", problems[0])
        # (a duel plays Normal whatever is asked; High Water and Tide Race the level)
        self.assertEqual([smoke.played_level(mode, "hard") for mode in ("high_water", "tide_race", "undertow")],
                         ["hard", "hard", "normal"])


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
