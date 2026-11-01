#!/usr/bin/env python3
"""Writes the balance gates (design 4.4) as scenarios in tests/balance/.

Each gate is one bare simulation in tests/sim/sim_harness.tscn, played to its end in
about a second: the bots are the caretaker (scripts/sim/caretaker.gd) following each
Builder's plan in data/plans/, so the gates test the code that holds an absent player's
seat. Every gate keeps the match's summary and its leak table (lives lost per wave, by
creep; a race's second hollow as "hollow 1 wave N") in its watches, which is what a
balance pass reads. High Water's gates play one hollow; Tide Race's (M6) play two, one
team on each, and read the race's decision (SimMatch.outcomes(), decided_by()).

    python3 tools/gen_balance_scenarios.py          # rewrite tests/balance/*.json
    python3 tools/gen_balance_scenarios.py --check  # exit 1 if a file is out of date
    godot-agent scenario . tests/balance --headless

Edit the CASES below, not the generated files. AGENTS.md's balance rule: every
bot_wins* wins with half the lives left, every idle_* and *_loses loses, every
coverage_* holds, every race_* holds. The two kept gates, bot_wins and
idle_player_loses, live in tests/scenarios/ (bot_wins sends its plan as commands).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "balance"
PLANS = ROOT / "data" / "plans"
MODE = "high_water"
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
# Ready, so it waits out every window), harness options, and what must hold.
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
    raise SystemExit(f"unknown rule {rule}")


def scenario(case):
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
