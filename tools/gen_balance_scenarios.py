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
one line per match in the watches. M8's play stacked waves (the plan bot by command, Ready
at once, stacking its plan's list or every wave it may) and the levels (caretakers at Hard
and Very Hard), some as several runs of one set-up compared (sim_harness.gd report()), and
one a series of races over the Builders (race_series).

    python3 tools/gen_balance_scenarios.py          # rewrite tests/balance/*.json
    python3 tools/gen_balance_scenarios.py --check  # exit 1 if a file is out of date
    python3 tools/gen_balance_scenarios.py --held DIR  # write the held gates (HELD) to DIR
    godot-agent scenario . tests/balance --headless

Edit the CASES below, not the generated files. AGENTS.md's balance rule: every
bot_wins* wins with half the lives left (Hard's with a third), every bot_kills_bristlesow_*
kills it at Normal, every idle_* and *_loses loses, every coverage_* holds, every race_*,
duel_*, stacking_* and difficulty_* holds, every bot_reaches_crest_* ends close (the Crest dies or leaks with at most a quarter of its
health, and a win keeps at most half the lives), and fork_pairs_apart (the fork bench, M8) holds. The
two kept gates, bot_wins and idle_player_loses, live in tests/scenarios/ (bot_wins sends its
plan as commands).
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
# The packs' matrix (M8, after the sends' pass): the four checks in CHECK_IDS order, the
# Drift's pack of each on Wickhollow (Game.PACKS, for the gates' words) and the checks each
# Builder covers (content.gd's BUILDERS "covers"); a Builder is weak to every check it does
# not cover, as the Builders screen says.
CHECKS = ["swarm", "swift", "armored", "winged"]
PACK_NAMES = {"swarm": "Gourd Rush", "swift": "Scuttle", "armored": "Thorn Herd", "winged": "Moth Cloud"}
COVERS = {
    "lamplighter": ["swarm", "swift"], "lookout": ["armored", "winged"],
    "bellfounder": ["swift", "armored"], "beekeeper": ["swarm", "winged"],
}
WEAK = {check: [b for b in COVERS if check not in COVERS[b]] for check in CHECKS}
# The packs' gates' bars, per mille of the uncorked packs that breach: the two Builders weak
# to a pack's check together, and each of them. Measured against the caretaker: the Gourd
# Rush 44% (the Lookout 52%, the Bellfounder 35%), the Scuttle 48% (the Beekeeper 73%, the
# Lookout 36%), the Thorn Herd 52% (the Beekeeper 60%, the Lamplighter 33%), the Moth Cloud
# 83%; after the sends' pass and before the packs' matrix 0 of 46, 2 of 44, 11 of 37 and 18 of 23.
PACK_WEAK_PM = 400
PACK_EACH_WEAK_PM = 300
TICKS_PER_MINUTE = 3600
# (M8) Very Hard's crews, each played by its own bot_reaches_crest_very_hard_* gate and all
# together by difficulty_very_hard_half_win: each Builder alone, then the two complementary pairs.
VERY_HARD_CREWS = [["lamplighter"], ["lookout"], ["bellfounder"], ["beekeeper"],
                   ["lamplighter", "lookout"], ["bellfounder", "beekeeper"]]
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
    # The sends' pass (the owner's decision of 2 November 2026, "Stronger packs, fairer
    # stipend"): how often an uncorked pack breaches, one of its creeps taking a life, in
    # the four Builders' mirrors under the caretaker's play and the balanced style's, over
    # seeds 1 to 5 (sim_harness.gd sends_table). On m8 it was a quarter (tier I 65%, II 32%,
    # III 11%; the Beekeeper's mirror 0 to 3%), and corking felt like a tax, not a send.
    {
        "name": "duel_sends_breach",
        "about": "Undertow: a sent pack is a threat. In the four Builders' mirrors, played by the caretaker and by the balanced style over seeds 1 to 5, a third to a half of the uncorked packs breach (one of their creeps takes a life), more than a fifth of each tier's, at most four in five of tier I's, and some in every mirror.",
        "mode": "undertow",
        "play": "sends",
        "styles": ["caretaker", "balanced"],
        "seeds": [1, 2, 3, 4, 5],
        "must": ["sends_total_pm>=333", "sends_total_pm<=500", "sends_tiers_pm>200", "sends_tier1_pm<=800", "sends_mirrors_pm>0"],
    },
] + [
    # The packs' matrix (the Veteran's third session, H3-01: only the Moth Cloud breached):
    # each pack corked wherever the Drift offers it, against each Builder's mirror defended
    # by the caretaker (sim_harness.gd pack_matrix), one gate a pack; the bars are
    # PACK_WEAK_PM and PACK_EACH_WEAK_PM (above, with what they measure).
    {
        "name": f"duel_{check}_pack_breaches_the_weak",
        "about": f"Undertow: the {PACK_NAMES[check]}, the {check} pack, is a send read from the rival's defence, not a tax. Corked by the balanced style wherever the Drift offers it, in each Builder's mirror against the caretaker over seeds 1 to 5, it breaches the two Builders weak to {check} (the {WEAK[check][0].capitalize()} and the {WEAK[check][1].capitalize()}) in at least {PACK_WEAK_PM // 10}% of its uncorkings together and each of them in at least {PACK_EACH_WEAK_PM // 10}%, and the two that cover it less often than the two weak to it.",
        "mode": "undertow",
        "play": "pack_matrix",
        "pack": check,
        "styles": ["caretaker"],
        "seeds": [1, 2, 3, 4, 5],
        "must": [f"pack_weak_pm({check})>={PACK_WEAK_PM}", f"pack_each_weak_pm({check})>={PACK_EACH_WEAK_PM}", f"pack_weak_over_covered({check})"],
    }
    for check in CHECKS
]

# M8 (design 2.6, 2.7 and 4.4; contract-m8 §2 and §3): the gates of stacked waves and of the
# levels. No gate above calls a wave during a wave (High Water's are played by caretakers,
# which wait out their windows, or by seats that never press Ready) and all play Normal, so
# their summaries are the same as before M8's rules; the two race gates' caretakers now stack
# their plans' lists. The stacking gates play the plan bot by command ("command": its plan
# through orders, Ready at once in every window, and "stacking": "plan" its plan's stack list
# as the caretaker would call it, "all" every wave it may, each call the moment the hollow
# can take it, so the waves truly overlap: design 2.7); the level gates play caretakers from
# tick 0 at a "difficulty", which never stack. A gate of "runs" plays the same set-up once
# per run and compares the runs' reports (sim_harness.gd report()); "race_series" plays one
# race a crew of `crews` (sim_harness.gd race_series), since a race plays alike under every
# seed (the match's SimRng feeds only a duel's Drift), so the Builders are what varies.
BUILDERS = ["lamplighter", "lookout", "bellfounder", "beekeeper"]
STACKS = {  # each plan's stack list (data/plans), for the gates' words
    "lamplighter": "waves 2 and 3", "lookout": "wave 5", "bellfounder": "wave 4", "beekeeper": "wave 2",
}
WINDOW_GOLD = 10  # high_water's window_t solo (600 ticks) in whole seconds: what a stacked call skips
M8_CASES = [
    {
        "name": f"bot_wins_stacking_{builder}",
        "about": f"Stacked waves (M8): the {builder.capitalize()}'s plan bot alone, by command, Ready at once in every window and calling {STACKS[builder]} during the wave before as its plan's stack list says, wins High Water with at least half the lives.",
        "builders": [builder],
        "play": "command",
        "stacking": "plan",
        "must": ["won", "lives>=10", "stacked"],
    }
    for builder in BUILDERS
] + [
    {
        "name": "stacking_pays",
        "about": "Stacked waves pay for the risk (M8): the Lamplighter's plan bot alone, Ready at once in every window and stacking its list (waves 2 and 3, each called as soon as the wave before has sounded, so waves 1 to 3 set out together), clears wave 12 at least 30 s of match time sooner than the same bot that never stacks, and its stacked calls pay each on average at least the window they skip (10 gold) plus 3 for the lives the waves on the road could still take.",
        "builders": ["lamplighter"],
        "play": "runs",
        "runs": [{"as": "stacking", "stacking": "plan"}, {"as": "calling", "stacking": None}],
        "must": ["stacking_pays"],
    },
] + [
    {
        "name": "stacking_every_wave_costs_lives" + ("" if builder == "lamplighter" else f"_{builder}"),
        "about": f"Stacking is a decision, not free gold (M8): the {builder.capitalize()}'s plan bot alone, Ready at once in every window, stacking every wave it may the moment its hollow can take it (behind the bosses too, so up to three waves walk at once) loses at least 5 lives more than when it stacks only its list ({STACKS[builder]}), or falls.",
        "builders": [builder],
        "play": "runs",
        "runs": [{"as": "listed", "stacking": "plan"}, {"as": "every", "stacking": "all"}],
        "must": ["every_wave_costs"],
    }
    for builder in BUILDERS
] + [
    {
        "name": "race_stacking_every_wave_not_dominant",
        "about": "Tide Race (M8): stacking every wave does not reliably win a race. For each Builder, a mirror of crews of one, both plan bots by command and Ready at once in every window, played on past the decision: team 0 stacks every wave it may, team 1 only its plan's list. The crew stacking every wave wins at most two of the four races (it wins where its Builder holds three waves at once, and falls where it does not), and the crew stacking its list wins the others.",
        "mode": "tide_race",
        "play": "race_series",
        "crews": [[builder] for builder in BUILDERS],
        "stacking": ["all", "plan"],
        "must": ["race_every_wave_not_dominant"],
    },
    {
        "name": "race_pair_stacking_every_wave_not_dominant",
        "about": "Tide Race (M8), crews of two: stacking every wave does not reliably win a race for a crew of two either, now that a life costs a race what the tide_race preset's life_t says. For each pair of the complementary two (the Lamplighter and the Lookout, the Bellfounder and the Beekeeper) and of each M2 Builder beside each M6 one, a mirror of crews, every plan bot by command and Ready at once in every window, played on past the decision: team 0's two stack every wave they may, team 1's each only its own plan's list (beside a present partner a seat calls only its own list, so most crews of two never stack: the lists share a wave only for the Lamplighter and the Beekeeper). The crew stacking every wave wins at most half the six races (those whose defence holds three waves at once and loses no life to it), the crews stacking their lists win the others, and in every race the first crew stacked more.",
        "mode": "tide_race",
        "play": "race_series",
        "crews": [["lamplighter", "lookout"], ["bellfounder", "beekeeper"], ["lamplighter", "bellfounder"], ["lamplighter", "beekeeper"], ["lookout", "bellfounder"], ["lookout", "beekeeper"]],
        "stacking": ["all", "plan"],
        "must": ["race_pairs_every_wave_not_dominant(6)"],
    },
    {
        "name": "race_stacking_beats_calling",
        "about": "Tide Race (M8): a Lamplighter stacking its list (waves 2 and 3) against a Lamplighter that calls every wave at once from its windows, both plan bots by command, the same plan on each hollow. Played on past the decision, both clear wave 12, and the stacker's race time is the lower: it won by the race-time rule.",
        "mode": "tide_race",
        "builders": ["lamplighter", "lamplighter"],
        "teams": [0, 1],
        "play": "race_stack_vs_call",
        "options": {"play_on": True},
        "must": ["race_stacker_first"],
    },
] + [
    # The owner's decision of 2 November 2026 (core-loop §10, item 19): at Normal every Builder's
    # plan alone kills the wave-6 boss, which a playtester leaked in every match of three sessions
    # (a sure 5 lives read as a tax); at Hard and Very Hard it stays a toll a strong opening can
    # come near. The Lamplighter's and the Lookout's openings answer it (data/plans).
    {
        "name": f"bot_kills_bristlesow_solo_{builder}",
        "about": f"Normal (M8, the owner's decision of 2 November 2026): the {builder.capitalize()} alone, the caretaker playing her plan, kills wave 6's Bristlesow before it reaches the Holdfast.",
        "builders": [builder],
        "play": "caretaker",
        "must": ["boss_dies(bristlesow)"],
    }
    for builder in BUILDERS
] + [
    {
        "name": f"bot_wins_hard_solo_{builder}",
        "about": f"Hard (M8): the {builder.capitalize()} alone, the caretaker playing her plan as at Normal, wins High Water at Hard with at least a third of the 15 lives.",
        "builders": [builder],
        "play": "caretaker",
        "difficulty": "hard",
        "must": ["won", "lives>=5"],
    }
    for builder in BUILDERS
] + [
    {
        "name": "bot_wins_hard_2p",
        "about": "Hard (M8): the complementary pair, the Lamplighter and the Lookout, at two-player scaling, wins High Water at Hard with at least a third of the 15 lives.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "difficulty": "hard",
        "must": ["won", "lives>=5"],
    },
] + [
    # Very Hard's bar (design 2.6, the owner's decision 16 of 1 November 2026: "a close wave 12"),
    # measured on the Crest since the second Very Hard pass: it dies, or reaches the Holdfast with
    # at most a quarter of its health left (sim_harness.gd boss_left_pm), and a win keeps at most
    # half the lives. Before, any fall to wave 12 passed: every solo plan fell to the Crest and no
    # solo plan won, the Lamplighter's Crest walking in with 26% of its health, and the gates held.
    # difficulty_very_hard_half_win holds that at least half the crews win.
    {
        "name": f"bot_reaches_crest_very_hard_solo_{builder}",
        "about": f"Very Hard (M8), a close wave 12: the {builder.capitalize()} alone stands until wave 12's Crest, which dies or reaches the Holdfast with at most a quarter of its health left, and if it wins it keeps at most 5 of its 10 lives.",
        "builders": [builder],
        "play": "caretaker",
        "difficulty": "very_hard",
        "must": ["crest_close"],
    }
    for builder in BUILDERS
] + [
    {
        "name": "bot_reaches_crest_very_hard_2p_lo",
        "about": "Very Hard (M8), a close wave 12: the complementary pair, the Lamplighter and the Lookout, stands until wave 12's Crest, which dies or reaches the Holdfast with at most a quarter of its health left, and if it wins it keeps at most 5 of its 10 lives.",
        "builders": ["lamplighter", "lookout"],
        "play": "caretaker",
        "difficulty": "very_hard",
        "must": ["crest_close"],
    },
    {
        "name": "bot_reaches_crest_very_hard_2p_bb",
        "about": "Very Hard (M8), a close wave 12: the other complementary pair, the Bellfounder and the Beekeeper, stands until wave 12's Crest, which dies or reaches the Holdfast with at most a quarter of its health left, and if it wins it keeps at most 5 of its 10 lives.",
        "builders": ["bellfounder", "beekeeper"],
        "play": "caretaker",
        "difficulty": "very_hard",
        "must": ["crest_close"],
    },
    {
        "name": "difficulty_very_hard_half_win",
        "about": "Very Hard (M8) is a close wave 12 a plan can win (design 2.6, the owner's decision 16): of the six crews the bot_reaches_crest_very_hard_* gates play, each Builder alone and the two complementary pairs, the caretaker playing their plans at Very Hard, at least half win.",
        "builders": ["lamplighter"],
        "play": "runs",
        "runs": [
            {"as": "_".join(crew), "play": "caretaker", "difficulty": "very_hard", "builders": crew}
            for crew in VERY_HARD_CREWS
        ],
        "must": ["half_won(%s)" % ",".join("_".join(crew) for crew in VERY_HARD_CREWS)],
    },
    {
        "name": "idle_player_loses_hard",
        "about": "Hard (M8): a Lamplighter who places her plan's first two towers and nothing else loses before the twelfth wave.",
        "builders": ["lamplighter"],
        "play": "idle",
        "difficulty": "hard",
        "must": ["fallen", "wave<12"],
    },
    {
        "name": "idle_player_loses_very_hard",
        "about": "Very Hard (M8): a Lamplighter who places her plan's first two towers and nothing else loses before the twelfth wave.",
        "builders": ["lamplighter"],
        "play": "idle",
        "difficulty": "very_hard",
        "must": ["fallen", "wave<12"],
    },
    {
        "name": "difficulty_orders_the_levels",
        "about": "The levels are in order (M8): the Lamplighter alone, the caretaker playing the same plan at each, keeps more lives at Normal than at Hard, and at Hard than at Very Hard (a fall counts below any lives, an earlier fall below a later).",
        "builders": ["lamplighter"],
        "play": "runs",
        "runs": [
            {"as": "normal", "play": "caretaker", "difficulty": "normal"},
            {"as": "hard", "play": "caretaker", "difficulty": "hard"},
            {"as": "very_hard", "play": "caretaker", "difficulty": "very_hard"},
        ],
        "must": ["levels_in_order"],
    },
    {
        "name": "race_mirror_is_fair_hard",
        "about": "Tide Race at Hard (M8): the same plan on both hollows, two Lamplighter bots, one a team, each calling its waves as its builds are done (at Hard the caretaker never stacks), lose the same lives and clear wave 12 on the same tick of their own clocks, a draw.",
        "mode": "tide_race",
        "builders": ["lamplighter", "lamplighter"],
        "teams": [0, 1],
        "play": "caretaker",
        "difficulty": "hard",
        "must": ["race_mirror"],
    },
    {
        "name": "fork_pairs_apart",
        "about": "The fork pass (M8, design 3.8): on the fork bench (tests/sim/fork_bench.gd: one seat of the form's Builder with its perk, the form built and forked on the bench cell (8, 11), health removed read from the HIT events less the killing hit's overkill), every fork pair's branches are apart. On each measure of its own job (one ground creep, one flier, armour at 4 and at 6, a crowd, holding ground creeps or fliers, lifting a battery of another seat's towers; the Sky Toll's a flier's damage and its hold on fliers), a one-creep measure at every creep health the game plays (one to four seats at every level) and a crowd or a hold on every cell its Builder's plan builds the base on, each branch does at least 25% more than its sibling (JOB_MARGIN_PM), or its sibling cannot do it at all; no branch is 10% ahead of its sibling on both jobs; and a patching branch does at most 90% of the best form, base or branch, of a Builder strong against the check it patches, at the same health or on the same cell. The watches hold one FORK_BENCH line a pair, each branch's numbers on both jobs with their range, its least lead and a patch's largest share.",
        "play": "fork_bench",
    },
]
# Gates of design 4.4 that cannot stand yet, held out of tests/balance (so every gate there
# passes) until a plan or a tower moves, each with why; `--held DIR` writes them to DIR, as
# they would stand, for the pass that means to make them stand. Empty since the fork pass
# (track D of M8): the four held there (the Bellfounder's and the Lookout's alone at Hard and
# Very Hard, whose openings leaked wave 2 at any creep health above Normal's) stand since the
# Clapper Tower deals 35, the Great Clapper 80 every 1.4 s and the Sky Toll +130% to fliers,
# the Bellfounder's plan builds her fourth Clapper before her third Toll Tower, and the
# Lookout's forks her first Kestrel Flock and her first Siege Perch before wave 2 and wave 8
# (content.gd, data/plans).
HELD = {}
HELD_CASES = [case for case in M8_CASES if case["name"] in HELD]
CASES += [case for case in M8_CASES if case["name"] not in HELD]


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
    if rule.startswith("sends_total_pm"):
        op, n = (">=", rule.split(">=")[1]) if ">=" in rule else ("<=", rule.split("<=")[1])
        word = "at least" if op == ">=" else "at most"
        return (
            f"table['total_pm'] {op} {n}",
            f"{word} {int(n) / 10:g}% of the uncorked packs breach",
        )
    if rule == "sends_tiers_pm>200":
        return (
            "table['tiers_pm'][0] > 200 and table['tiers_pm'][1] > 200 and table['tiers_pm'][2] > 200",
            "more than a fifth of each tier's packs breach",
        )
    if rule == "sends_tier1_pm<=800":
        return "table['tiers_pm'][0] <= 800", "at most four in five of tier I's packs breach"
    if rule == "sends_mirrors_pm>0":
        return "table['mirrors_pm'].values().min() > 0", "packs breach in every Builder's mirror, in both styles"
    if rule.startswith("pack_weak_pm("):
        check = rule[len("pack_weak_pm("):rule.index(")")]
        n = int(rule.split(">=")[1])
        return (
            f"matrix['weak_pm'].get('{check}', 0) >= {n}",
            f"at least {n / 10:g}% of the uncorked {PACK_NAMES[check]} packs breach the Builders weak to {check}",
        )
    if rule.startswith("pack_each_weak_pm("):
        check = rule[len("pack_each_weak_pm("):rule.index(")")]
        n = int(rule.split(">=")[1])
        return (
            " and ".join(f"matrix['packs_pm'].get('{b} {check}', 0) >= {n}" for b in WEAK[check]),
            f"at least {n / 10:g}% of them breach each: " + " and ".join(f"the {b.capitalize()}" for b in WEAK[check]),
        )
    if rule.startswith("pack_weak_over_covered("):
        check = rule[len("pack_weak_over_covered("):rule.index(")")]
        return (
            f"matrix['weak_pm'].get('{check}', 0) > matrix['covered_pm'].get('{check}', 0)",
            f"the Builders that cover {check} let fewer of them through than the two weak to it",
        )
    if rule.startswith("duel_walls("):
        seat = int(rule[len("duel_walls("):rule.index(")")])
        return (
            f"scene.duel_count({seat}, 'seawall') > 0",
            f"seat {seat} raised its Seawall",
        )
    # M8's (stacked waves and the levels)
    if rule == "stacked":
        return "scene.stack_summary(0)['count'] > 0", "it called a wave during a wave at least once"
    if rule == "crest_close":
        return (
            f"{m}.hollows[0].wave == 12 and crest_left >= 0 and crest_left <= 250"
            f" and ({m}.hollows[0].phase == {FALLEN}"
            f" or ({m}.hollows[0].phase == {WON} and {m}.teams[0].lives * 2 <= int({m}.rules['lives'])))",
            "it stands until wave 12's Crest, which dies or reaches the Holdfast with at most a quarter of its"
            " health left, and a win keeps at most half the lives: a close wave 12",
        )
    if rule.startswith("boss_dies("):
        kind = rule[len("boss_dies("):rule.index(")")]
        return f"{kind}_left == 0", f"the {kind.replace('_', ' ').capitalize()} dies on the road"
    if rule.startswith("half_won("):
        names = rule[len("half_won("):rule.index(")")].split(",")
        won = ", ".join(f"{name}['won']" for name in names)
        return (
            f"[{won}].count(true) * 2 >= {len(names)}",
            f"at least half of the {len(names)} crews win",
        )
    if rule == "race_stacker_first":
        return (
            f"{m}.hollows[0].phase == {WON} and {m}.hollows[1].phase == {WON}"
            f" and {m}.race_time(0) >= 0 and {m}.race_time(0) < {m}.race_time(1)"
            f" and {m}.decided_by() == 'time' and {m}.outcomes() == [0, 1]"
            f" and scene.stack_summary(0)['count'] > 0 and scene.stack_summary(1)['count'] == 0",
            "both clear wave 12; the stacker (team 0) stacked, the other never did, and the stacker's lower race time won",
        )
    if rule == "stacking_pays":
        return (
            "stacking['won'] and calling['won'] and stacking['stacked'] > 0 and calling['stacked'] == 0"
            " and stacking['clear_tick'] + 30 * 60 <= calling['clear_tick']"
            f" and stacking['stack_paid'] >= ({WINDOW_GOLD} + 3) * stacking['stacked']",
            f"stacking its list clears wave 12 at least 30 s sooner, and its calls pay on average at least {WINDOW_GOLD} + 3",
        )
    if rule == "every_wave_costs":
        return (
            "listed['won'] and every['stacked'] > listed['stacked']"
            " and (every['fallen'] or every['lives'] + 5 <= listed['lives'])",
            "stacking every wave it may loses at least 5 lives more than stacking its list, or falls",
        )
    if rule == "race_every_wave_not_dominant":
        return (
            "series['wins'][0] * 2 <= series['rows'].size() and series['wins'][0] + series['wins'][1] == series['rows'].size()"
            " and series['stacked_more'] == series['rows'].size()",
            "the crew stacking every wave wins at most half the races and the crew stacking its list the rest; both stacked, the first more",
        )
    if rule.startswith("race_pairs_every_wave_not_dominant("):
        n = int(rule[len("race_pairs_every_wave_not_dominant("):rule.index(")")])
        more = " and ".join(f"series['rows'][{i}]['stacked'][0] > series['rows'][{i}]['stacked'][1]" for i in range(n))
        return (
            f"series['rows'].size() == {n} and series['wins'][0] * 2 <= {n} and series['wins'][0] + series['wins'][1] == {n}"
            f" and {more}",
            "the crew of two stacking every wave wins at most half the races and the crews stacking their lists the rest; the first stacked more in every race",
        )
    if rule == "levels_in_order":
        return (
            "normal['standing'] > hard['standing'] and hard['standing'] > very_hard['standing']"
            " and normal['level'] == 'normal' and hard['level'] == 'hard' and very_hard['level'] == 'very_hard'",
            "more lives kept at Normal than at Hard, and at Hard than at Very Hard (a fall below any lives)",
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


def sends_scenario(case):
    """(The sends' pass) The breach table of uncorked packs over the four Builders' mirrors
    (sim_harness.gd sends_table): its shares per tier and per mirror, one line per duel."""
    run = "scene.sends_table(%s, %s, %s)" % (json.dumps(case["styles"]), json.dumps(BUILDERS), json.dumps(case["seeds"]))
    steps = [
        {"eval": run, "as": "table"},
        {"eval": "table['lines']", "as": "lines"},
        {"eval": "[table['total'], table['tiers'], table['mirrors'], table['windows'], table['picks']]", "as": "shares"},
    ]
    for rule in case["must"]:
        expr, msg = assertion(rule)
        steps.append({"assert": expr, "msg": msg})
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"duel": "scene.duel_line()"},
        "steps": steps,
    }


def pack_matrix_scenario(case):
    """(The packs' matrix) One pack corked wherever the Drift offers it, against each
    Builder's mirror defended in case["styles"] (sim_harness.gd pack_matrix): its share of
    breaches over the Builders weak to its check, each of them, and those that cover it."""
    run = "scene.pack_matrix(%s, %s, %s, %s)" % (
        json.dumps(case["styles"]), json.dumps(BUILDERS), json.dumps(case["seeds"]), json.dumps([case["pack"]])
    )
    steps = [
        {"eval": run, "as": "matrix"},
        {"eval": "matrix['lines']", "as": "lines"},
        {"eval": "[matrix['cells'], matrix['packs'], matrix['weak'], matrix['covered']]", "as": "shares"},
    ]
    for rule in case["must"]:
        expr, msg = assertion(rule)
        steps.append({"assert": expr, "msg": msg})
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"duel": "scene.duel_line()"},
        "steps": steps,
    }


def play_steps(case, play, difficulty=None, stacking=None):
    """One match of `case` played as `play`: its start and play_out steps, and whether it is
    played by command (M8's "command", "race_stack_vs_call")."""
    builders = case["builders"]
    n = len(builders)
    mode = case.get("mode", MODE)
    cfg = {"mode": mode, "seats": n, "builders": builders, "events": False}
    if "teams" in case:
        cfg["teams"] = case["teams"]
    if difficulty:
        cfg["difficulty"] = difficulty
    cfg.update(case.get("options", {}))
    by_command = []
    ready = []
    stacks = {}
    if play == "caretaker":
        cfg["caretakers"] = list(range(1, n + 1))
    elif play == "one_idle":
        cfg["caretakers"] = [1]
    elif play == "idle":
        cfg["plans"] = {b: first_two_builds(b) for b in dict.fromkeys(builders)}
        by_command = list(range(1, n + 1))
    elif play == "ready_vs_wait":
        cfg["caretakers"] = [1]
        by_command = [2]
    elif play == "command":
        by_command = list(range(1, n + 1))
        ready = list(range(1, n + 1))
        if stacking:
            stacks = {str(seat): stacking for seat in by_command}
    elif play == "race_stack_vs_call":
        by_command = [1, 2]
        ready = [1, 2]
        stacks = {"1": "plan"}
    else:
        raise SystemExit(f"{case['name']}: unknown play {play}")
    steps = [{"eval": "scene.start(%s)" % json.dumps(cfg, sort_keys=True)}]
    if ready or stacks:
        run = "scene.play_out(%s, 30, 120000, %s, %s)" % (json.dumps(by_command), json.dumps(ready), json.dumps(stacks, sort_keys=True))
    else:
        run = "scene.play_out(%s)" % json.dumps(by_command)
    steps.append({"eval": run, "as": "end"})
    return steps


def race_series_scenario(case):
    """(M8) One race a crew of case["crews"], each a mirror, team 0 stacking as
    case["stacking"][0] says and team 1 as [1] (sim_harness.gd race_series)."""
    cfg = {"mode": case["mode"], "events": False}
    if "difficulty" in case:
        cfg["difficulty"] = case["difficulty"]
    stacking = ["" if how is None else how for how in case["stacking"]]
    run = "scene.race_series(%s, %s, %s)" % (json.dumps(cfg, sort_keys=True), json.dumps(stacking), json.dumps(case["crews"]))
    steps = [{"eval": run, "as": "series"}, {"eval": "series['lines']", "as": "lines"}]
    for rule in case["must"]:
        expr, msg = assertion(rule)
        steps.append({"assert": expr, "msg": msg})
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"stacks": "scene.stack_summary()"},
        "steps": steps,
    }


def fork_bench_scenario(case):
    """(M8, the fork pass) The fork bench (tests/sim/fork_bench.gd): every fork pair's
    branches on both jobs, one FORK_BENCH line a pair in the watches, and its problems()."""
    bench = "resource('res://tests/sim/fork_bench.gd')"
    return {
        "name": case["name"],
        "description": case["about"] + " Generated by tools/gen_balance_scenarios.py: edit the generator, not this file.",
        "scene": "res://tests/sim/sim_harness.tscn",
        "seed": 1,
        "timeout_frames": 60,
        "watch": {"bench": bench + ".table()"},
        "steps": [
            {"eval": bench + ".lines()", "as": "lines"},
            {"eval": bench + ".problems()", "as": "found"},
            {"assert": "found == []", "msg": "every fork pair is apart: each branch 25% ahead at its own job, none 10% ahead at both, every patch at most 90% of a strong Builder's best"},
        ],
    }


def scenario(case):
    if case["play"] == "duel":
        return duel_scenario(case)
    if case["play"] == "sends":
        return sends_scenario(case)
    if case["play"] == "pack_matrix":
        return pack_matrix_scenario(case)
    if case["play"] == "race_series":
        return race_series_scenario(case)
    if case["play"] == "fork_bench":
        return fork_bench_scenario(case)
    n = len(case["builders"])
    watch = {"summary": "scene.summary()", "leaks": "scene.leak_table()"}
    if case["play"] == "runs":
        # (M8) the same set-up played once per run, each run's report() kept under its name
        steps = []
        for run in case["runs"]:
            crew = dict(case, builders=run.get("builders", case["builders"]))
            steps += play_steps(crew, run.get("play", "command"), run.get("difficulty", case.get("difficulty")), run.get("stacking"))
            steps.append({"eval": "scene.report()", "as": run["as"]})
            steps.append({"eval": "scene.leak_table()", "as": run["as"] + "_leaks"})
        watch["stacks"] = "scene.stack_summary()"
    else:
        steps = play_steps(case, case["play"], case.get("difficulty"), case.get("stacking"))
        steps.append({"eval": "scene.summary()", "as": "summary"})
        steps.append({"eval": "scene.leak_table()", "as": "leaks"})
        if case["play"] in ("command", "race_stack_vs_call"):
            watch["stacks"] = "scene.stack_summary()"
    if "crest_close" in case.get("must", []):
        steps.append({"eval": "scene.boss_left_pm('hollowtide_crest')", "as": "crest_left"})
    for rule in case.get("must", []):
        if rule.startswith("boss_dies("):
            kind = rule[len("boss_dies("):rule.index(")")]
            steps.append({"eval": f"scene.boss_left_pm('{kind}')", "as": f"{kind}_left"})
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
        "watch": watch,
        "steps": steps,
    }


def render(case):
    return json.dumps(scenario(case), indent=2, ensure_ascii=False) + "\n"


def write_held(folder):
    """Writes the held gates (HELD) to `folder`, outside tests/balance, and says why each is held."""
    out = pathlib.Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    for case in HELD_CASES:
        (out / f"{case['name']}.json").write_text(render(case))
        print("%s: held: %s" % (case["name"], HELD[case["name"]]))
    print("wrote %d held gates to %s" % (len(HELD_CASES), out))
    return 0


def main():
    if "--held" in sys.argv[1:]:
        at = sys.argv.index("--held")
        if at + 1 >= len(sys.argv):
            raise SystemExit("--held needs a folder")
        return write_held(sys.argv[at + 1])
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
