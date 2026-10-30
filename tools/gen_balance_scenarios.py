#!/usr/bin/env python3
"""Writes the High Water balance gates (design 4.4) as scenarios in tests/balance/.

Each gate is one bare simulation in tests/sim/sim_harness.tscn, played to its end in
about a second: the bots are the caretaker (scripts/sim/caretaker.gd) following each
Builder's plan in data/plans/, so the gates test the code that holds an absent player's
seat. Every gate keeps the match's summary and its leak table (lives lost per wave, by
creep) in its watches, which is what a balance pass reads.

    python3 tools/gen_balance_scenarios.py          # rewrite tests/balance/*.json
    python3 tools/gen_balance_scenarios.py --check  # exit 1 if a file is out of date
    godot-agent scenario . tests/balance --headless

Edit the CASES below, not the generated files. AGENTS.md's balance rule: every
bot_wins* wins with half the lives left, every idle_* and *_loses loses, every
coverage_* holds. The two kept gates, bot_wins and idle_player_loses, live in
tests/scenarios/ (bot_wins sends its plan as commands).
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

# Each case: the seats' Builders, who plays (caretaker: every seat a bot from tick 0;
# idle: every seat orders its plan's first two towers and nothing else; one_idle: seat 1
# a bot, seat 2 present and idle), harness options, and what must hold.
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
        "name": "bot_wins_high_water_2p",
        "about": "The complementary pair, the Lamplighter and the Lookout, at two-player scaling, wins with at least half the lives; each deepens where the other covers.",
        "builders": ["lamplighter", "lookout"],
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
        "name": "high_water_length_2p",
        "about": "The two-player bot match (the Lamplighter and the Lookout, waiting out every window) lasts 11 to 15 minutes of match time.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "must": ["won", "minutes 11..15"],
    },
]


def first_two_builds(builder):
    """The first two build steps of a Builder's High Water plan: [slot, x, z] each."""
    plan = json.loads((PLANS / f"{builder}.json").read_text())
    section = plan.get(MODE)
    steps = section["steps"] if isinstance(section, dict) else plan["steps"]
    kit = {"lamplighter": ["arrow", "cannon", "frost"], "lookout": ["perch_ballista", "hawk_roost", "owls_eye"]}[builder]
    out = []
    for step in steps:
        if "build" in step:
            out.append([kit.index(step["build"]), step["cell"][0], step["cell"][1]])
        if len(out) == 2:
            return out
    raise SystemExit(f"{builder}'s plan has fewer than two builds")


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
    raise SystemExit(f"unknown rule {rule}")


def scenario(case):
    builders = case["builders"]
    n = len(builders)
    cfg = {"mode": MODE, "seats": n, "builders": builders, "events": False}
    cfg.update(case.get("options", {}))
    steps = []
    if case["play"] == "caretaker":
        cfg["caretakers"] = list(range(1, n + 1))
    elif case["play"] == "one_idle":
        cfg["caretakers"] = [1]
    steps.append({"eval": "scene.start(%s)" % json.dumps(cfg, sort_keys=True)})
    if case["play"] == "idle":
        orders = []
        for seat, builder in enumerate(builders, start=1):
            for slot, x, z in first_two_builds(builder):
                orders.append(f"scene.cmd({seat}, 'BUILD', {slot}, {x}, {z})")
        steps.append({"eval": "[%s]" % ", ".join(orders)})
        steps.append({"eval": "scene.run_ticks(6)"})
        steps.append({"assert": f"scene.client(1).towers.size() == {2 * n}",
                      "msg": "each seat's two towers stand"})
    steps.append({"eval": "scene.play_out([])", "as": "end"})
    steps.append({"eval": "scene.summary()", "as": "summary"})
    steps.append({"eval": "scene.leak_table()", "as": "leaks"})
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
