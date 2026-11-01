#!/usr/bin/env python3
"""Writes the balance gates (design 4.4) as scenarios in tests/balance/.

Each gate is one bare simulation in tests/sim/sim_harness.tscn, played to its end in
about a second: the bots are the caretaker (scripts/sim/caretaker.gd) following each
Builder's plan in data/plans/, so the gates test the code that holds an absent player's
seat. Every gate keeps the match's summary and its leak table (lives lost per wave, by
creep; a race's second hollow as "hollow 1 wave N") in its watches, which is what a
balance pass reads. High Water's gates play one hollow; Tide Race's (M6) play two, one
team on each, and read the race's decision (SimMatch.outcomes(), decided_by()).
Undertow's (M7, the duel: design 4.4) play two hollows under one clock, one seat each, in
the duel's play styles (tests/sim/sim_harness.gd duel_out: turtle, balanced, reckless,
counter_cork, random), most of them as a series over seeds 1 to 5 (duel_series), and keep
one line per match in the watches.

    python3 tools/gen_balance_scenarios.py          # rewrite tests/balance/*.json
    python3 tools/gen_balance_scenarios.py --check  # exit 1 if a file is out of date
    godot-agent scenario . tests/balance --headless

Edit the CASES below, not the generated files. AGENTS.md's balance rule: every
bot_wins* wins with half the lives left, every idle_* and *_loses loses, every
coverage_* holds, every race_* holds, every duel_* holds. The two kept gates, bot_wins and
idle_player_loses, live in tests/scenarios/ (bot_wins sends its plan as commands).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "balance"
PLANS = ROOT / "data" / "plans"
MODE = "high_water"
DUEL_LAST_WAVE = 15  # Undertow: hollow12's twelve, then the Surge's three
# The duel gates' Builders by seed (seeds 1 to 5): both seats the same Builder in each
# match, a mirror of Builders, so a gate measures the play style alone, and a different
# one from seed to seed, so the rival's weak checks change (the Lamplighter's are armoured
# and winged, the Lookout's swarm and swift, ...) and no two seeds play one match: the
# match's SimRng feeds only the Drift, and two Lamplighter duels of two seeds often played
# out alike. Each series gate also holds its matches to being all different.
DUEL_ROSTER = ["lamplighter", "lookout", "bellfounder", "beekeeper", "lamplighter"]
TICKS_PER_MINUTE = 3600
WON, FALLEN = 2, 3  # SimTypes.PHASE_DONE, PHASE_FALLEN
KITS = {  # content.gd's BUILDERS "towers", for the idle seats' first builds
    "lamplighter": ["arrow", "cannon", "frost"],
    "lookout": ["perch_ballista", "hawk_roost", "owls_eye"],
    "bellfounder": ["clapper_tower", "toll_tower", "chime_post"],
    "beekeeper": ["clay_hive", "apiary", "hive_hum"],
}

# Each case: the seats' Builders (and, for a race, their teams), who plays (caretaker:
# every seat a bot from tick 0; idle: every seat builds its plan's first two towers, as it
# can pay for them, and nothing else; one_idle: seat 1 a bot, seat 2 present and idle;
# ready_vs_wait: a race of seat 1, a bot that calls every wave as soon as its window's
# builds are done, against seat 2 playing the same plan by command and never pressing
# Ready, so it waits out every window; duel: an Undertow duel played by the seats' styles
# ("styles", seat number: style, "caretaker" for a seat the caretaker plays from tick 0)
# once per seed of "seeds", "options" for duel_out, and "compare" for a second series the
# same but for its options; "roster" gives each seed's Builder to both seats instead of
# "builders"), harness options, and what must hold.
CASES = [
    {
        "name": "bot_wins_solo_lamplighter",
        "about": "The Lamplighter alone, forking for the checks she lacks (the sky and armour), wins High Water with at least half the lives.",
        "builders": ["lamplighter"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_solo_lookout",
        "about": "The Lookout alone, forking for the checks she lacks (swarms and swift creeps), wins High Water with at least half the lives.",
        "builders": ["lookout"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_solo_bellfounder",
        "about": "The Bellfounder alone, forking for the checks she lacks (Sky Tolls for the sky, a Ringing Clapper for swarms), wins High Water with at least half the lives.",
        "builders": ["bellfounder"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_solo_beekeeper",
        "about": "The Beekeeper alone, forking for the checks she lacks (a Drowsy Clay Hive for swift creeps, Queen's Guards for armour), wins High Water with at least half the lives.",
        "builders": ["beekeeper"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_high_water_2p",
        "about": "The complementary pair, the Lamplighter and the Lookout, at two-player scaling, wins with at least half the lives; each deepens where the other covers.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_lamplighter_bellfounder",
        "about": "The Lamplighter and the Bellfounder, whose plans share five build cells on the lower stretches (whoever builds a shared cell first keeps it; the other takes the step's alt cell or skips the step), win with at least half the lives.",
        "builders": ["lamplighter", "bellfounder"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_lamplighter_beekeeper",
        "about": "The Lamplighter and the Beekeeper, whose plans share three build cells, win with at least half the lives.",
        "builders": ["lamplighter", "beekeeper"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_lookout_bellfounder",
        "about": "The Lookout and the Bellfounder, whose plans share two build cells, win with at least half the lives.",
        "builders": ["lookout", "bellfounder"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_lookout_beekeeper",
        "about": "The Lookout and the Beekeeper, whose plans share six build cells in the middle of the hollow (the Beekeeper's opening Apiary stands on the Lookout's eighth step), win with at least half the lives.",
        "builders": ["lookout", "beekeeper"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_high_water_3p",
        "about": "The Lamplighter, the Lookout and the Bellfounder at three-player scaling win with at least half the lives.",
        "builders": ["lamplighter", "lookout", "bellfounder"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "bot_wins_high_water_4p",
        "about": "All four Builders at four-player scaling win with at least half the lives.",
        "builders": ["lamplighter", "lookout", "bellfounder", "beekeeper"],
        "play": "caretaker",
        "must": ["won", "lives>=10"],
    },
    {
        "name": "idle_team_loses_2p",
        "about": "A Lamplighter and a Lookout who each place their plan's first two towers and nothing else lose before the twelfth wave.",
        "builders": ["lamplighter", "lookout"],
        "play": "idle",
        "must": ["fallen", "wave<12"],
    },
    {
        "name": "idle_team_loses_3p",
        "about": "A Lamplighter, a Lookout and a Bellfounder who each place their plan's first two towers and nothing else lose before the twelfth wave.",
        "builders": ["lamplighter", "lookout", "bellfounder"],
        "play": "idle",
        "must": ["fallen", "wave<12"],
    },
    {
        "name": "idle_team_loses_4p",
        "about": "All four Builders, each placing its plan's first two towers and nothing else, lose before the twelfth wave.",
        "builders": ["lamplighter", "lookout", "bellfounder", "beekeeper"],
        "play": "idle",
        "must": ["fallen", "wave<12"],
    },
    {
        "name": "one_idle_of_two_loses",
        "about": "One Lamplighter bot carrying an idle partner at two-player scaling loses: every seat matters.",
        "builders": ["lamplighter", "lamplighter"],
        "play": "one_idle",
        "must": ["fallen"],
    },
    {
        "name": "coverage_matters_winged",
        "about": "Two Lamplighters that never fork for the sky (their plan's Skyward Lofts and Rime Spires deepen instead) lose at least 4 lives to the Duskmoths of waves 5 and 8.",
        "builders": ["lamplighter", "lamplighter"],
        "play": "caretaker",
        "options": {"never_patch": {"lamplighter": ["winged"]}},
        "must": ["lost(5)+lost(8)>=4"],
    },
    {
        "name": "coverage_holds_complementary_lo",
        "about": "The complementary pair, the Lamplighter and the Lookout, loses at most 2 lives over waves 5 to 10, the first Duskmoths, the Bristlesow and each Builder's strong pair.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "must": ["lost(5..10)<=2"],
    },
    {
        "name": "coverage_holds_complementary_bb",
        "about": "The other complementary pair, the Bellfounder and the Beekeeper, loses at most 2 lives over waves 5 to 10: the Beekeeper's Apiaries take the sky, so the Bellfounder deepens into Great Tolls and Great Clappers where she would patch alone.",
        "builders": ["bellfounder", "beekeeper"],
        "play": "caretaker",
        "must": ["lost(5..10)<=2"],
    },
    {
        "name": "high_water_length_2p",
        "about": "The two-player bot match (the Lamplighter and the Lookout, waiting out every window) lasts 11 to 15 minutes of match time.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "must": ["won", "minutes 11..15"],
    },
    {
        "name": "race_mirror_is_fair",
        "about": "Tide Race, the same plan on both hollows: two Lamplighter bots, one a team, each calling its waves as its builds are done, lose the same lives and clear wave 12 on the same tick of their own clocks, a draw.",
        "mode": "tide_race",
        "builders": ["lamplighter", "lamplighter"],
        "teams": [0, 1],
        "play": "caretaker",
        "must": ["race_mirror"],
    },
    {
        "name": "race_bots_both_finish",
        "about": "Tide Race: a Lamplighter bot that calls every wave at once races a Lamplighter playing the same plan that waits out every window. Played on past the decision, both clear wave 12, and the decision, taken as soon as it was certain, is the race-time rule's: the lower race time won.",
        "mode": "tide_race",
        "builders": ["lamplighter", "lamplighter"],
        "teams": [0, 1],
        "play": "ready_vs_wait",
        "options": {"play_on": True},
        "must": ["race_both_finish"],
    },
    # M7, the duel's gates (design 4.4). Every duel here is a mirror of Builders, so a gate
    # measures the play style alone: two Lamplighters where one seed is enough, and over a
    # series each seed's Builder of DUEL_ROSTER on both seats, so the seeds play different
    # matches against rivals with different weak checks.
    {
        "name": "duel_mirror_is_draw",
        "about": "Undertow, the same Builder and the caretaker's play on both hollows: two caretakers of one Builder cork, uncork and raise their Seawalls alike, the Drift brings both the same packs, and each of four seeds, with the Lamplighter, the Lookout, the Bellfounder and the Beekeeper on both seats in turn, ends a draw with both seats' records equal.",
        "mode": "undertow",
        "roster": DUEL_ROSTER[:4],
        "play": "duel",
        "styles": {1: "caretaker", 2: "caretaker"},
        "seeds": [1, 2, 3, 4],
        "must": ["duel_mirror", "duel_distinct"],
    },
    {
        "name": "duel_turtle_holds",
        "about": "Undertow: a Lamplighter that only defends (its plan, never a cork) against a passive rival that does the same holds to the end of the Surge with at least 10 lives.",
        "mode": "undertow",
        "builders": ["lamplighter", "lamplighter"],
        "play": "duel",
        "styles": {1: "turtle", 2: "turtle"},
        "seeds": [1],
        "must": ["duel_holds(0)>=10"],
    },
    {
        "name": "duel_balanced_beats_turtle",
        "about": "Undertow: a seat playing the caretaker's policy (the cheapest cork while its corks stay within a fifth of what it holds, the pack its rival's towers take longest to kill) beats one of the same Builder that only defends in at least 3 of seeds 1 to 5, each seed another Builder on both seats (DUEL_ROSTER), every match a different one.",
        "mode": "undertow",
        "roster": DUEL_ROSTER,
        "play": "duel",
        "styles": {1: "balanced", 2: "turtle"},
        "must": ["duel_wins(0)>=3", "duel_distinct"],
    },
    {
        "name": "duel_turtle_beats_reckless",
        "about": "Undertow: a seat that only defends beats one of the same Builder that corks the most it can every window, before it builds, in at least 3 of seeds 1 to 5 (each seed another Builder on both seats, every match a different one): the packs it kills pay it, and the reckless one's defence starves.",
        "mode": "undertow",
        "roster": DUEL_ROSTER,
        "play": "duel",
        "styles": {1: "turtle", 2: "reckless"},
        "must": ["duel_wins(0)>=3", "duel_distinct"],
    },
    {
        "name": "duel_counter_cork_beats_random",
        "about": "Undertow: corking the pack the rival's towers take longest to kill beats corking an offered pack at random, with the same budget, in at least 3 of seeds 1 to 5. Each seed puts another Builder on both seats, so the rival's weak checks change from match to match, every match is a different one, and the counter-corker's most-uncorked pack is not the same in every match: it corks the rival's weakness, not one pack.",
        "mode": "undertow",
        "roster": DUEL_ROSTER,
        "play": "duel",
        "styles": {1: "counter_cork", 2: "random"},
        "must": ["duel_wins(0)>=3", "duel_distinct", "duel_picks_vary(1)>=2"],
    },
    {
        "name": "duel_seawall_saves",
        "about": "Undertow: the Seawall is the comeback. A seat that only defends, raising its Seawall as the caretaker would (with a charge, once the creeps near its Holdfast would take 3 lives or a boss stands there), beats a reckless corker of the same Builder in at least 3 of seeds 1 to 5 (each seed another Builder on both seats, every match a different one), and in more of them than the same defender that never raises it.",
        "mode": "undertow",
        "roster": DUEL_ROSTER,
        "play": "duel",
        "styles": {1: "reckless", 2: "turtle"},
        "compare": {"no_seawall": [2]},
        "must": ["duel_wins(1)>=3", "duel_wins(1)>compare_wins(1)", "duel_walls(2)>0", "duel_distinct"],
    },
]


def plan_steps(builder):
    plan = json.loads((PLANS / f"{builder}.json").read_text())
    section = plan.get(MODE)
    return section["steps"] if isinstance(section, dict) else plan["steps"]


def first_two_builds(builder):
    """The first two build steps of a Builder's High Water plan, as plan entries."""
    out = [step for step in plan_steps(builder) if "build" in step][:2]
    if len(out) < 2:
        raise SystemExit(f"{builder}'s plan has fewer than two builds")
    for step in out:
        if step["build"] not in KITS[builder]:
            raise SystemExit(f"{builder}'s plan builds {step['build']}, outside its kit")
    return out


def assertion(rule):
    m = "scene.client(1)"
    if rule == "won":
        return f"{m}.hollows[0].phase == {WON} and {m}.hollows[0].wave == 12", "the Holdfast stands after wave 12"
    if rule == "fallen":
        return f"{m}.hollows[0].phase == {FALLEN}", "the Holdfast falls"
    if rule.startswith("lives>="):
        n = int(rule.split(">=")[1])
        return f"{m}.teams[0].lives >= {n}", f"with at least {n} lives left"
    if rule.startswith("wave<"):
        n = int(rule.split("<")[1])
        return f"{m}.hollows[0].wave < {n}", f"before wave {n}"
    if rule == "lost(5)+lost(8)>=4":
        return "scene.lives_lost(5, 5) + scene.lives_lost(8, 8) >= 4", "waves 5 and 8 cost at least 4 lives"
    if rule == "lost(5..10)<=2":
        return "scene.lives_lost(5, 10) <= 2", "waves 5 to 10 cost at most 2 lives"
    if rule == "minutes 11..15":
        lo, hi = 11 * TICKS_PER_MINUTE, 15 * TICKS_PER_MINUTE
        return f"{m}.tick >= {lo} and {m}.tick <= {hi}", "the match lasts 11 to 15 minutes"
    if rule == "race_mirror":
        return (
            f"{m}.teams[0].clear_tick >= 0 and {m}.teams[0].clear_tick == {m}.teams[1].clear_tick"
            f" and {m}.teams[0].lives == {m}.teams[1].lives and {m}.teams[0].lives > 0"
            f" and {m}.decided_by() == 'draw' and {m}.outcomes() == [2, 2]",
            "both hollows clear wave 12 on the same tick with the same lives: a draw",
        )
    if rule == "race_both_finish":
        return (
            f"{m}.hollows[0].phase == {WON} and {m}.hollows[1].phase == {WON}"
            f" and {m}.race_time(0) >= 0 and {m}.race_time(1) >= 0 and {m}.decided_by() == 'time'"
            f" and (({m}.race_time(0) < {m}.race_time(1) and {m}.outcomes() == [0, 1])"
            f" or ({m}.race_time(1) < {m}.race_time(0) and {m}.outcomes() == [1, 0]))"
            f" and scene.decided_tick() >= 0"
            f" and (scene.decided_tick() < {m}.teams[0].clear_tick or scene.decided_tick() < {m}.teams[1].clear_tick)",
            "both clear wave 12; the lower race time won, decided before the slower team finished",
        )
    if rule == "duel_mirror":
        return (
            "series['draws'] == series['matches'].size() and series['mirrors'] == series['matches'].size()"
            " and series['lines'].size() > 0",
            "every seed a draw, both seats' records equal",
        )
    if rule.startswith("duel_holds("):
        team = int(rule[len("duel_holds("):rule.index(")")])
        n = int(rule.split(">=")[1])
        return (
            f"series['matches'][0]['teams'][{team}]['lives'] >= {n}"
            f" and series['matches'][0]['wave'] == {DUEL_LAST_WAVE}"
            f" and series['matches'][0]['teams'][{team}]['phase'] == {WON}",
            f"it stands after the Surge's last wave with at least {n} lives",
        )
    if rule.startswith("duel_wins("):
        team = int(rule[len("duel_wins("):rule.index(")")])
        if ">=" in rule:
            n = int(rule.split(">=")[1])
            return f"series['wins'][{team}] >= {n}", f"team {team} wins at least {n} of the seeds"
        other = rule.split(">")[1]
        assert other.startswith("compare_wins(")
        return (
            f"series['wins'][{team}] > compare['wins'][{team}]",
            f"team {team} wins more seeds than in the compared series (the same duel but for its options)",
        )
    if rule == "duel_distinct":
        return (
            "series['distinct'] == series['matches'].size()",
            "every seed played a different match",
        )
    if rule.startswith("duel_picks_vary("):
        seat = int(rule[len("duel_picks_vary("):rule.index(")")])
        n = int(rule.split(">=")[1])
        return (
            f"series['leading_picks'].get({seat}, 0) >= {n}",
            f"seat {seat}'s most-uncorked pack differs between the matches: at least {n} different ones",
        )
    if rule.startswith("duel_walls("):
        seat = int(rule[len("duel_walls("):rule.index(")")])
        return (
            f"scene.duel_count({seat}, 'seawall') > 0",
            f"seat {seat} raised its Seawall",
        )
    raise SystemExit(f"unknown rule {rule}")


def gd_seats(styles):
    """A {seat: style} dictionary as a GDScript Expression writes it (int keys)."""
    return "{" + ", ".join(f"{seat}: '{style}'" for seat, style in styles.items()) + "}"


def duel_scenario(case):
    seeds = case.get("seeds", [1, 2, 3, 4, 5])
    if "roster" in case:
        by_seed = [[builder, builder] for builder in case["roster"]]
        if len(by_seed) != len(seeds):
            raise SystemExit(f"{case['name']}: the roster gives {len(by_seed)} Builders for {len(seeds)} seeds")
        builders = by_seed[0]
    else:
        by_seed, builders = None, case["builders"]
    styles = {seat: s for seat, s in case["styles"].items() if s != "caretaker"}
    cfg = {"mode": case["mode"], "seats": len(builders), "builders": builders, "events": False}
    if by_seed:
        cfg["builders_by_seed"] = by_seed
    caretakers = [seat for seat, s in case["styles"].items() if s == "caretaker"]
    if caretakers:
        cfg["caretakers"] = caretakers
    cfg.update(case.get("options", {}))
    run = "scene.duel_series(%s, %s, %s, %s)" % (
        json.dumps(cfg, sort_keys=True), gd_seats(styles), json.dumps(seeds), json.dumps(case.get("duel_options", {}))
    )
    steps = []
    if "compare" in case:
        steps.append({"eval": run.replace(json.dumps(case.get("duel_options", {})) + ")", json.dumps(case["compare"]) + ")"), "as": "compare"})
        steps.append({"eval": "compare['lines']", "as": "compare_lines"})
    steps.append({"eval": run, "as": "series"})
    steps.append({"eval": "series['lines']", "as": "lines"})
    for rule in case["must"]:
        expr, msg = assertion(rule)
        steps.append({"assert": expr, "msg": msg})
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"duel": "scene.duel_line()", "leaks": "scene.leak_table()"},
        "steps": steps,
    }


def scenario(case):
    if case["play"] == "duel":
        return duel_scenario(case)
    builders = case["builders"]
    n = len(builders)
    mode = case.get("mode", MODE)
    cfg = {"mode": mode, "seats": n, "builders": builders, "events": False}
    if "teams" in case:
        cfg["teams"] = case["teams"]
    cfg.update(case.get("options", {}))
    by_command = []
    if case["play"] == "caretaker":
        cfg["caretakers"] = list(range(1, n + 1))
    elif case["play"] == "one_idle":
        cfg["caretakers"] = [1]
    elif case["play"] == "idle":
        cfg["plans"] = {b: first_two_builds(b) for b in dict.fromkeys(builders)}
        by_command = list(range(1, n + 1))
    elif case["play"] == "ready_vs_wait":
        cfg["caretakers"] = [1]
        by_command = [2]
    steps = [{"eval": "scene.start(%s)" % json.dumps(cfg, sort_keys=True)}]
    steps.append({"eval": "scene.play_out(%s)" % json.dumps(by_command), "as": "end"})
    steps.append({"eval": "scene.summary()", "as": "summary"})
    steps.append({"eval": "scene.leak_table()", "as": "leaks"})
    if case["play"] == "idle":
        steps.append({"assert": f"scene.client(1).towers.size() == {2 * n}",
                      "msg": "each seat's two towers stood"})
    for rule in case["must"]:
        expr, msg = assertion(rule)
        steps.append({"assert": expr, "msg": msg})
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"summary": "scene.summary()", "leaks": "scene.leak_table()"},
        "steps": steps,
    }


def render(case):
    return json.dumps(scenario(case), indent=2, ensure_ascii=False) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    names = set()
    for case in CASES:
        path = OUT / f"{case['name']}.json"
        names.add(path.name)
        text = render(case)
        if path.exists() and path.read_text() == text:
            continue
        stale.append(path.name)
        if not check:
            path.write_text(text)
    extra = sorted(p.name for p in OUT.glob("*.json") if p.name not in names)
    if check:
        if stale or extra:
            print("out of date: %s; not generated: %s" % (", ".join(stale) or "-", ", ".join(extra) or "-"))
            return 1
        print("tests/balance is up to date (%d gates)" % len(CASES))
        return 0
    print("wrote %d of %d gates to %s%s" % (len(stale), len(CASES), OUT.relative_to(ROOT),
                                           ("; not generated here: " + ", ".join(extra)) if extra else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
