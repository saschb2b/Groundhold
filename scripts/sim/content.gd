## The rules as data, in the simulation's integer units (design 4.2): ticks (1/60 s),
## millimetres for positions and ranges, micrometres for progress along the road and
## micrometres per tick for speeds, hundredths for health, damage and armour, per mille
## for shares. Names, models and icons of towers, creeps, checks, roles and perks live in
## game.gd under the same ids. A Builder's name, title and home sit in BUILDERS beside
## its kit so the hub reads one table; rules_hash() leaves them out with the Builder's
## other labels (BUILDER_DISPLAY_KEYS), so no name is part of the rules hash. What the
## simulation reads (the kit, the perk, the plan and the checks a Builder covers, which
## the caretaker's forks follow) is hashed.
##
## Four presets: `classic`, M1's solo game kept as it was (eight waves, the three towers,
## today's upgrade standing in for fork branch A; no armour, no perks, no Help),
## `high_water`, the co-op mode of design 1.2 on Wickhollow's `hollow12` (a wave list is
## named after its map, not its mode) with flat armour, boss control resistance, the
## Builders' perks and Help, both for one to four seats on one shared hollow, (M6)
## `tide_race`, High Water for two teams of one or two, each on its own hollow (design 1.3),
## and (M7) `undertow`, the duel: one seat on each of two hollows under one clock, with the
## Drift, corked packs, the Seawall and the Surge (design 1.4, SimUndertow).
##
## The M2/M3 contract (docs/design/contract-m2m3.md) fixes the id lists, the BUILDERS
## fields and the tower and creep keys documented below. M2 tunes the numbers and makes
## the simulation honour the keys marked (M2); M3 reads BUILDERS and the helpers at the
## end of this file and writes nothing here.
class_name SimContent
extends RefCounted

const SIM_VERSION := 1
## How the caretaker plays a seat, outside the tables (caretaker.gd): 2 since M4, which takes
## a seat over mid-match at its plan cursor, over the towers its player built; 3 since M6,
## which calls the waves of a race (its plan's `ready` hints); 4 since M7, which corks,
## uncorks and raises the Seawall in a duel; 5 since M8, which stacks the waves of its plan's
## `stack` list where it calls waves itself (a race), at Normal only; 6 since the sends'
## pass (the owner's decision of 2 November 2026), which in a duel sends what the rival's
## defence has shown (SimUndertow.pick_pack: what has leaked, fliers against a weak sky,
## then kill time) where it sent the longest kill alone. The rules hash covers it, so
## builds whose caretakers decide differently never share a match; SIM_VERSION, which the
## codec writes, does not move for it, since that would move every recorded state hash.
const CARETAKER_VERSION := 6
## How the simulation takes a seat's orders, outside the tables: 2 since M8's review, which
## takes a READY 1 only for the wave its `b` names (0 names none; SimMatch._set_ready). The
## rules hash covers it, as it does CARETAKER_VERSION, so builds that take a late Ready
## differently never share a match; SIM_VERSION does not move for it.
const ORDERS_VERSION := 2

const RULES := {
	"classic":
	{
		"teams": 1,
		"seats": [1, 4],
		"map": "hollow",
		"waves": "classic8",
		"clock": "hollow",
		"start_gold": 120,
		"lives": 20,
		"hp_growth_pm": 220,
		"hp_by_seats_pm": [1000, 1850, 2650, 3400],
		"window_first_t": [900, 1500, 1500, 1500],
		"window_t": [600, 900, 900, 900],
		"sell_pm": 700,
		"clear_bonus": [8, 2],
		"ready_pays": true,
		"armor": false,
		"control_resist": false,
		"perks": false,
		"help": false,
		"cap_t": 0,
		"signals": [3, 300],
	},
	# Design 1.2, 2.1 and 2.5. The keys classic turns off:
	#   armor           creeps keep their armour (the flat rule of design 3.2)
	#   control_resist  a boss's control_resist_pm shrinks every slow on it
	#   perks           each Builder's passive (BUILDERS "perk") applies to its seat
	#   help            a hit on a creep another seat's tower slowed or marked counts as
	#                   that seat's Help (EV_HELP, SimSeat.help_c)
	# And the keys of M8 (contract-m8 §1 to §3, design 2.6 and 2.7), which classic lacks:
	#   stack_max       how many waves a hollow's road holds at once; 1 or absent, none
	#                   stack. Above 1, a present seat's Ready is taken during a wave too, and
	#                   on the tick every present seat is Ready the next wave sets out at once,
	#                   among what the older is still sending (SimWaves.stack_wave): no window
	#                   comes between
	#   stake_pm        what that stacked horn pays each seat for each life the waves on the
	#                   road could still take (the tolls of their creeps walking and still to
	#                   come), per mille of a gold, besides the whole window it skips
	#                   (SimMatch.stack_pay)
	#   levels          the preset takes a level (DIFFICULTIES, rules(mode, difficulty))
	# stack_max is 3, not the design's first 2, and stake_pm 400, not its 1000, tuned by the
	# stacking gates once stacked waves truly overlap (the owner's decision of 2 November
	# 2026): with two waves at most, a plan bot alone holds two waves at once with lives to
	# spare, so stacking every wave cost the Lamplighter 1 life against her list's at 400 (14
	# against 15) and none at 0, 200 or 1000, where its gold bought the towers that killed
	# the Bristlesow (20 against 15), and the Beekeeper nothing at any stake: stacking every
	# wave was still free. With three, it costs every Builder alone at least 5 lives against
	# its list, or its Holdfast (stacking_every_wave_costs_lives*: the Lamplighter 6 against
	# 15, the Beekeeper 15 against 20, the Bellfounder falls on wave 4, the Lookout on wave
	# 1), while the lists still pay: the Lamplighter's two calls 14 and 21 (stacking_pays
	# asks 13 on average) and wave 12 cleared 45 s sooner than calling from every window. At
	# 700 or more the stake's gold buys the Lamplighter back her lives again (14 at 700, 15 at
	# 1000), and at 200 her calls pay 13.5, so 400 stays.
	# Tuned by the balance gates (tests/balance, M2) from the design's starting values:
	# health grows 25% a wave, not 20% (at 20% every bot lost nothing but the Bristlesow),
	# and two seats face 2000 per mille, not 1850 (a Lamplighter and a Lookout cleared
	# the waves so fast that their match fell short of eleven minutes).
	"high_water":
	{
		"teams": 1,
		"seats": [1, 4],
		"map": "hollow",
		"waves": "hollow12",
		"clock": "hollow",
		"start_gold": 120,
		"lives": 20,
		"hp_growth_pm": 250,
		"hp_by_seats_pm": [1000, 2000, 2650, 3400],
		"window_first_t": [900, 1500, 1500, 1500],
		"window_t": [600, 900, 900, 900],
		"sell_pm": 700,
		"clear_bonus": [8, 2],
		"ready_pays": true,
		"armor": true,
		"control_resist": true,
		"perks": true,
		"help": true,
		"cap_t": 0,
		"signals": [3, 300],
		"stack_max": 3,
		"stake_pm": 400,
		"levels": true,
	},
	# Design 1.3 and 2.1 (M6): High Water's rules for two teams of one or two, each on a
	# hollow of its own built from the same map text (SimHollow.id = its team), with the
	# same waves on the same ticks of its own clock; windows, Ready, the horn and health
	# scaling go by its own seats. The keys High Water lacks:
	#   race   {"life_t": ticks a lost life adds to the team's race time}: the clear tick
	#          of the last wave plus life_t per life lost; SimMatch decides the race by the
	#          win order of design 1.3 (outcomes(), race_time(), decided_by())
	#   cap_t  the hard cap, 20 minutes of match time: at the cap the waves cleared decide,
	#          then the lives, then the race time
	# life_t is 3600 (a minute a life), not M6's 600, by the owner's decision of 2 November
	# 2026 ("Raise the cost of a life"): once stacked waves truly overlap, a crew that stacks
	# every wave saves 170 to 230 s on wave 12's clear, which 10 s a life never paid for, so
	# stacking every wave won a race whatever it cost the Holdfast (crews of two by about
	# 2x: the Lamplighter and the Lookout 13,220 against 26,597, the Bellfounder and the
	# Beekeeper 17,233 against 26,545). Measured after the fork pass and its review, the crews
	# of two that stack every wave and still lose lives to it need at least 2,527 ticks a life
	# to lose to the same crew calling its lists (the Bellfounder and the Beekeeper: wave 12
	# cleared at 14,269 with 5 lives lost against 26,903 with none; the Lookout and the
	# Beekeeper 14,342 and 5 against 23,915 and none), and the Lamplighter alone more than
	# 1,547 (14,546 and 15 lost against 30,020 and 5). At 3600 those all lose by a minute and
	# a half or more (race_pair_stacking_every_wave_not_dominant: 3 of the 6 crews of two win
	# by stacking every wave, the three whose defence holds three waves without a leak;
	# race_stacking_every_wave_not_dominant: none of the 4 crews of one), while a race
	# between crews that lose the same lives is still decided by time alone
	# (race_stacking_beats_calling, race_bots_both_finish)
	"tide_race":
	{
		"teams": 2,
		"seats": [2, 4],
		"map": "hollow",
		"waves": "hollow12",
		"clock": "hollow",
		"start_gold": 120,
		"lives": 20,
		"hp_growth_pm": 250,
		"hp_by_seats_pm": [1000, 2000, 2650, 3400],
		"window_first_t": [900, 1500, 1500, 1500],
		"window_t": [600, 900, 900, 900],
		"sell_pm": 700,
		"clear_bonus": [8, 2],
		"ready_pays": true,
		"armor": true,
		"control_resist": true,
		"perks": true,
		"help": true,
		"cap_t": 72000,
		"signals": [3, 300],
		"race": {"life_t": 3600},
		# (M8) each hollow stacks on its own clock, as High Water's does, to the same three
		"stack_max": 3,
		"stake_pm": 400,
		"levels": true,
	},
	# Design 1.4 and the M7 contract (docs/design/contract-m7.md §2): High Water's rules for
	# two teams of one, each on a hollow of its own (the race's layout), under one clock.
	# The keys High Water lacks:
	#   clock  "shared": both hollows' windows, Ready and horn are one (SimUndertow.run_clock):
	#          the window counts down once both hollows have cleared their wave, and the horn
	#          sounds for both when every seat present is Ready or the countdown ends
	#   duel   the Drift, corks, stipends, breaches, the Seawall and the Surge
	#          (SimUndertow), all of it tunable against the duel's balance gates:
	#     drift_from       the first window the Drift brings packs to
	#     offered          how many of the four packs (SimContent.PACKS) each window offers
	#     tiers            by window ([first, last], the wave it precedes; a Surge window
	#                      counts as the wave it repeats): a cork's price and the stipend an
	#                      uncorking adds for the rest of the match
	#     corks            corks a seat may make in a window, corks_two from corks_two_from
	#     uncork_after_t   ticks after the horn before a bottle may be uncorked
	#     auto_uncork_t    ticks after the horn the client uncorks by itself (the client's)
	#     fizzle_t         ticks after the horn a bottle with no valid reveal fizzles
	#     pack_interval_t  ticks between an uncorked pack's creeps on the rival's road (not
	#                      the contract's: a pack all on one tick is one splash's worth)
	#     breach_pay       an uncorked creep that leaks pays its sender this many bounties
	#     send_hp_pm       an uncorked creep's health, per mille of the wave's own of its
	#                      kind (SimUndertow.send_health_c), as a mercenary is stronger
	#     pack_hp_pm       {check: per mille}: a pack's own premium in place of send_hp_pm
	#                      (SimUndertow.send_hp_pm(m, check); the caretaker's pack_threat
	#                      counts it too)
	#     pack_gap_t       {check: ticks}: a pack's own spacing in place of pack_interval_t
	#                      (SimUndertow.pack_gap_t)
	#     seawall          a charge every every_lives lives lost, at most charges; it
	#                      stuns every creep within radius_mm of the Holdfast stun_t and
	#                      takes hp_pm of its maximum health, a boss's boss_hp_pm and a
	#                      boss_slow_pm slow instead; cooldown_t between two
	#     surge            after wave 12 with both standing: waves again (with hp_pm
	#                      health), windows of window_t, stipends that no longer grow, corks
	#                      at cork_price_pm of their price
	"undertow":
	{
		"teams": 2,
		"seats": [2, 2],
		"map": "hollow",
		"waves": "hollow12",
		"clock": "shared",
		"start_gold": 120,
		"lives": 20,
		"hp_growth_pm": 250,
		"hp_by_seats_pm": [1000, 2000, 2650, 3400],
		"window_first_t": [900, 1500, 1500, 1500],
		"window_t": [600, 900, 900, 900],
		"sell_pm": 700,
		"clear_bonus": [8, 2],
		"ready_pays": true,
		"armor": true,
		"control_resist": true,
		"perks": true,
		"help": true,
		"cap_t": 0,
		"signals": [3, 300],
		# (M8) never stacked: the shared clock needs a window between waves (the Drift
		# draws in it, corks are made in it), and no level: the duel is tuned to Normal
		"stack_max": 1,
		"duel":
		{
			"drift_from": 2,
			"offered": 3,
			# The sends' pass (the owner's decision of 2 November 2026, "Stronger packs,
			# fairer stipend"; duel_sends_breach): each tier's stipend, paid at every clear
			# from the wave its pack walks to the Surge's last, now pays its price back about
			# once from its first window. Tier I cost 30 and paid back 56 from window 2 and 48
			# from window 4, nearly twice, so a cork in window 2 was free and a corker that
			# never held back (duel_turtle_beats_reckless) sent a Moth Cloud onto the turtle's
			# second wave: at 40 it still does and beats the turtle 4 of 5; at 45 it cannot
			# pay for one after its window's builds, the caretaker's fifth of its worth
			# (Caretaker.CORK_SHARE_PM) first corks in window 3, and the turtle wins 4 of 5,
			# 56 and 48 back (124% and 107%). Tier II is the design's, 66 and 48 (120%, 87%;
			# 7 a wave held the Seawall's gate at 3 of 5, 6 at 4). Tier III paid back 56 from
			# window 9 and 32 from window 12, so a held pack was a loss of about 30 to 50 while
			# the defender took its bounties: at 12, the owner's figure, 84 and 48 (99%, 56%).
			"tiers":
			[
				{"windows": [2, 4], "price": 45, "stipend": 4},
				{"windows": [5, 8], "price": 55, "stipend": 6},
				{"windows": [9, 12], "price": 85, "stipend": 12},
			],
			"corks": 1,
			"corks_two": 2,
			"corks_two_from": 9,
			"uncork_after_t": 180,
			"auto_uncork_t": 1440,
			"fizzle_t": 1500,
			"pack_interval_t": 30,
			"breach_pay": 2,
			# The sends' pass: a sent creep a quarter stronger than the wave's own. With the
			# caretaker's new pick (SimUndertow.pick_pack), the larger packs (the tier II Moth
			# Cloud still 6) and these tiers but no premium, 26.7% of uncorked packs breached
			# in the four mirrors (tier III 17%) and the balanced corker beat the turtle only
			# 2 of 5; a fifth more health, 36.2% (tier III 22%), but the turtle beat the
			# reckless corker 4 of 5 with its Seawall and without it, so the wall saved
			# nothing (duel_seawall_saves); a quarter, 39.5% (tier III 26%) and every duel
			# gate held, the Seawall 4 against 3; 30%, 40.1%, held them with the turtle 3 of
			# 5. With the packs as they stand a quarter breaches 41.5% (tier III 30%), the
			# gates as before. Breach pay and the Seawall stay: halving the pay or a stronger
			# wall (40% health, 3 charges, one every 3 lives) only moved which seed of the
			# five the gates turned on.
			"send_hp_pm": 1250,
			# The packs' matrix (PACKS says what each pack did and does to the Builders weak to
			# it): the Gourd Rush and the Scuttle a premium of their own. A Gourdling or a
			# Scuttler is a small creep that a defence weak to its check still kills in a
			# strike or two, so more of them at a quarter more health broke one weak Builder
			# and never the other: a bunched Gourd Rush of 10, 16, 30 at 1250 breached the
			# Lookout's tier III 17 of 19 times and the Bellfounder's, whose Clapper and Toll
			# Towers hold a swarm late, 0 of 33; 20 at half again (1500) breach her tier III 2
			# of 11, her opening 4 of 4, and the Lookout's tier III 6 of 12. Every pack a
			# defender holds pays it each creep's bounty, so a premium in place of more creeps
			# keeps a held tier III Gourd Rush from paying back its price (20 pay 60 of the 85,
			# 30 would pay 90). 1700 and 1600, with the first trial's counts (8, 11, 24;
			# 8, 15, 32), broke the weak Builders' openings with the waves' own swarms and
			# swift creeps and the reckless corker beat the turtle 4 of 5
			# (duel_turtle_beats_reckless); at 1500 and 1400 and the counts as they stand it
			# loses 4 of 5.
			"pack_hp_pm": {"swarm": 1500, "swift": 1400},
			# The packs' matrix: the Gourd Rush comes a quarter second apart, the Thorn Herd a
			# second apart (pack_interval_t's half second the others). A swarm is many at
			# once: bunched, a splash or a cloud (the Lamplighter's Cannons, the Beekeeper's
			# Clay Hives, who cover it) takes several in a shot while one strike at a time
			# (the Lookout's Ballistas, the Bellfounder's Clapper Towers) falls behind: the
			# Gourd Rush of 6, 10, 14 a tenth of a second apart breached its two weak Builders
			# 6 of 39 times, at the half second none of 46, and those that cover it no more
			# (none of 37). An armoured herd is the other way round: walking a
			# second apart, a splash finds one Thornback where it found three, and only hits
			# that go through armour hold it. The Thorn Herd of 3, 5, 10 breached the
			# Builders that cover armour 34% of the time at the half second (the Lookout's
			# tier III 70%), spread 19%, and its two weak Builders 36% and, spread, 44%.
			"pack_gap_t": {"swarm": 15, "armored": 60},
			"seawall":
			{
				"every_lives": 4,
				"charges": 2,
				"radius_mm": 3000,
				"stun_t": 120,
				"hp_pm": 250,
				"boss_hp_pm": 80,
				"boss_slow_pm": 500,
				"cooldown_t": 900,
			},
			"surge": {"waves": [9, 10, 11], "hp_pm": 1350, "window_t": 480, "cork_price_pm": 500},
		},
	},
}

## Towers by base id. A base is placed from its Builder's kit slot; a fork lays branch
## "a" (deepen) or "b" (patch) over it for good (design 3.4). Every value is an int in
## the unit its key names unless said otherwise; a branch lists only the keys it changes,
## plus its "id". Keys marked (M2) are the contract's and honoured since M2: whom a tower
## picks and where a bounce goes are SimTargeting's, marks and slows SimEffects'.
##   builder       the BUILDERS id whose kit holds it
##   slot          its kit slot: 0, 1, 2, on Q, W, E
##   cost          gold to build it
##   dmg_c         damage per hit, hundredths; 0 deals none
##   cd_t          ticks between shots, or between a team-effect tower's re-picks
##   range_mm      reach from the cell centre (Keen Sight adds to it where perks are on)
##   air           bool: it may target winged creeps; without it, its splash skips them
##   shot_um_t     projectile speed, micrometres per tick; 0 fires no shot: the tower
##                 works by its team effect alone (the Owl's Eye; M6's pulses and auras)
##   min_flight_t  optional: a shell's shortest flight in ticks
##   splash_mm     optional: burst radius; every ground creep inside takes falling damage
##   slow_pm       optional: each hit slows by this much ...
##   slow_t        ... for this many ticks
##   pierce_c      optional: armour each hit ignores, hundredths
##   aim           (M2) optional, a string: whom it picks. "first" (the default: furthest
##                 along the road), "winged" (winged creeps first, then "first"),
##                 "most_hp" (highest current health)
##   bounces       (M2) optional: creeps each strike bounces on to ...
##   bounce_mm     (M2) ... each within this distance of the creep before
##   team          optional, a string: the team effect it brings, "slow" or "mark" (M6
##                 adds "stun", "crack", "haste"); effects never stack, the strongest
##                 applies (design 3.2)
##   mark_pm       (M2) extra damage a marked creep takes from every tower, per mille
##   marks         (M2) how many creeps it marks at once
##   mark_t        (M2) ticks a mark lasts after its creep leaves the tower's reach
##   fork_cost     gold to fork it, the same for either branch
##   a, b          its branches: {"id": the branch's TOWER_IDS id, then what it changes}
## Keys marked (M6) are the M6 contract's (docs/design/contract-m6.md), honoured since M6
## (pulses and clouds in SimMatch, the stun, the auras and Help in SimEffects):
##   pulse         (M6) bool: no shot; every cd_t it strikes every creep within range_mm
##                 at once (fliers too only where `air`): dmg_c and its stun or slow
##   stun_t        (M6) ticks a hit stuns (speed 0); on a boss, where the rules turn
##                 control_resist on, a 50% slow of the same length instead
##   stun_immune_t (M6) ticks after a stun ends in which no stun takes (stuns never chain)
##   air_slow_pm   (M6) what a hit does to a winged creep instead of stunning it: a slow ...
##   air_slow_t    (M6) ... for this many ticks (the Sky Toll)
##   cloud_mm      (M6) a bee cloud: every cd_t, over the creep it aims at (ground or air
##                 per `air`), it stings every creep, ground or air, within cloud_mm of that
##                 creep: dmg_c, and slow_pm for slow_t where set. No shot
##   crack_c       (M6) an aura: creeps inside range_mm have this much less armour,
##                 hundredths, for every tower's hits; the strongest crack applies
##   haste_pm      (M6) an aura: every tower whose cell centre lies within range_mm of
##                 this one, whoever built it, fires this much faster, per mille; the
##                 strongest applies; recomputed when any tower is built, forked or sold
##   air_bonus_pm  (M6) extra damage against winged creeps, per mille, on any form that
##                 has it: the Apiary's (the contract's), and the Sky Toll's pulse since
##                 the M6 balance pass (now 160%: its 9 is 23.4 to a flier, the ground keeps
##                 9). A view shows it from this key, never from the form's name
## (M8) The fork pass (contract-m8 §6, design 3.8) set the branches marked "fork pass" below
## against the fork bench (tests/sim/fork_bench.gd, the fork_pairs_apart gate): on its own job
## each branch does at least 25% more than its sibling, none is 10% ahead on both jobs, and a
## patch stays under 90% of the best form of a Builder strong against its check, at every
## creep health the game plays (one to four seats at every level) and on every cell its
## Builder's plan builds the base on. Design 3.8 tables every pair's measures before and
## after. The numbers classic plays never change: the Lamplighter's three bases and her three
## A branches.
const TOWERS := {
	"arrow":
	{
		"builder": "lamplighter",
		"slot": 0,
		"cost": 40,
		"dmg_c": 800,
		"cd_t": 30,
		"range_mm": 3200,
		"air": false,
		"shot_um_t": 233333,
		"fork_cost": 60,
		"a": {"id": "longbow_loft", "dmg_c": 1600, "cd_t": 24, "range_mm": 3600},
		"b": {"id": "skyward_loft", "dmg_c": 1200, "cd_t": 27, "range_mm": 3600, "air": true},
	},
	"cannon":
	{
		"builder": "lamplighter",
		"slot": 1,
		"cost": 70,
		"dmg_c": 2000,
		"cd_t": 90,
		"range_mm": 3000,
		"air": false,
		"shot_um_t": 100000,
		"min_flight_t": 21,
		"splash_mm": 1100,
		"fork_cost": 80,
		"a": {"id": "great_cannon", "dmg_c": 4000, "cd_t": 78, "range_mm": 3300, "splash_mm": 1350},
		# (fork pass) 52 a shell, not 45, every 1.4 s with M2's burst of 0.6. At 45 every 1.4 s it
		# led the Great Cannon on a Thornback by 20% (30.8 a second against 25.6), and every 1.3 s
		# by 29% at Normal's creep health but 21% at two seats' (33.0 against 27.2: 14 shells a
		# kill against 17); 52 leads by 32% at worst over every health the game plays (33.9
		# against 25.6 at Hard's), and the Great Cannon leads its crowd by 31% at worst over the
		# cannon's cells (743 per mille against 534 at the bench). Not faster, nor a narrower
		# burst: every 1.3 s the Lamplighter stacking every wave kept 10 lives against her list's
		# 15, where stacking_every_wave_costs_lives asks 5 more lost, and a burst of 0.4 bought
		# one back with a third of the Mortar's crowd; at 52 every 1.4 s she keeps 5
		"b":
		{
			"id": "iron_mortar",
			"dmg_c": 5200,
			"cd_t": 84,
			"range_mm": 3300,
			"splash_mm": 600,
			"pierce_c": 400,
		},
	},
	"frost":
	{
		"builder": "lamplighter",
		"slot": 2,
		"cost": 60,
		"dmg_c": 400,
		"cd_t": 54,
		"range_mm": 2800,
		"air": false,
		"shot_um_t": 150000,
		"slow_pm": 450,
		"slow_t": 120,
		"team": "slow",
		"fork_cost": 60,
		"a": {"id": "deep_frost", "dmg_c": 800, "range_mm": 3200, "slow_pm": 600},
		"b": {"id": "rime_spire", "dmg_c": 600, "range_mm": 3200, "slow_pm": 400, "air": true},
	},
	"perch_ballista":
	{
		"builder": "lookout",
		"slot": 0,
		"cost": 75,
		"dmg_c": 3200,
		"cd_t": 96,
		"range_mm": 4000,
		"air": true,
		"shot_um_t": 300000,
		"pierce_c": 300,
		"fork_cost": 90,
		"a": {"id": "siege_perch", "dmg_c": 6400, "cd_t": 90, "pierce_c": 600},
		"b": {"id": "pinning_ballista", "dmg_c": 3600, "slow_pm": 500, "slow_t": 60},
	},
	"hawk_roost":
	{
		"builder": "lookout",
		"slot": 1,
		"cost": 55,
		"dmg_c": 1000,
		"cd_t": 42,
		"range_mm": 3400,
		"air": true,
		"shot_um_t": 200000,
		"aim": "winged",
		"fork_cost": 70,
		"a": {"id": "falcon_roost", "dmg_c": 1800, "cd_t": 33},
		# (fork pass) a third bounce, at the 9 a strike it had before the pass: with two bounces at
		# 9 its crowd was 21% above the Falcon Roost's on the bench cell, and at 9.5 27% there but
		# 24% and 22% on (12, 8) and (6, 12), where the Lookout's plan forks it; three bounces
		# lead by 47% at worst over her Hawk Roosts' cells (429 per mille against 291 on (13, 12)),
		# at most 66% of the Great Cannon. Not more damage: the design's 10 took wave 2's
		# Gourdling in three strikes and made a Lookout turtle hold the duel's corks so well that
		# the balanced corker only drew it (duel_balanced_beats_turtle, 2 of 5); 9 takes Very
		# Hard's (34.50) in four, as 9.5 did
		"b": {"id": "kestrel_flock", "dmg_c": 900, "bounces": 3, "bounce_mm": 1200},
	},
	"owls_eye":
	{
		"builder": "lookout",
		"slot": 2,
		"cost": 65,
		"dmg_c": 0,
		"cd_t": 30,
		"range_mm": 3600,
		"air": true,
		"shot_um_t": 0,
		"aim": "most_hp",
		"team": "mark",
		"mark_pm": 200,
		"marks": 1,
		"mark_t": 60,
		"fork_cost": 70,
		"a": {"id": "owls_glare", "mark_pm": 350},
		# (fork pass) +25% on each of two, not +20%: on a line of Thornbacks two marks at 20% lifted
		# the battery 98 per mille against Owl's Glare's 93 (now 122, +31%), and on one boss Owl's
		# Glare's +35% stays ahead, 999 against 709
		"b": {"id": "twin_gaze", "mark_pm": 250, "marks": 2},
	},
	# M6: the Bellfounder's kit (design 3.4). Tuned by the M6 balance gates (tests/balance,
	# bot_wins_solo_bellfounder): the Toll Tower's pulse deals 8, not 6 (at 6 a Bellfounder
	# alone left the Gourdlings of wave 7 at a quarter of their health and four got
	# through); the Sky Toll slows a flier for 2 s, not 1, and its 9 grows by 80% against
	# one (air_bonus_pm; the ground keeps the 9; 160% and a third slower since M8, below): at the design's numbers
	# a Duskmoth of wave 5 crossed the two Sky Tolls she can pay for by then with half its
	# health left, and every one of them got through.
	"clapper_tower":
	{
		"builder": "bellfounder",
		"slot": 0,
		"cost": 75,
		# (M8) 35, not 30: wave 2's Gourdling has 30.00 at Normal, 33.00 at Hard and 34.50 at Very
		# Hard, so at 30 any level above Normal took two strikes and the Bellfounder alone leaked
		# 10 of wave 2's 18 (bot_wins_hard_solo_bellfounder, held out of tests/balance until now)
		"dmg_c": 3500,
		"cd_t": 84,
		"range_mm": 2600,
		"air": false,
		"shot_um_t": 400000,
		"fork_cost": 85,
		# (fork pass) the Great Clapper 80 every 1.4 s, not 72 every 1.6 s: with her opening fixed
		# the Bellfounder alone still lost Hard to the Crest (2,792 of its 3,937 health dealt at
		# 72 every 1.6 s, 3,295 at 80 every 1.5 s); on the bench 53.9 and 54.0 a second to a
		# Thornback and the Bristlesow. At Hard the Crest dies 80 s into its walk, about 8 s
		# before it would reach the Holdfast (at Very Hard it does, at 88 s). No faster: every
		# 1.33 s the Ringing Clapper is under 25% ahead of it on a crowd on (13, 8) and (5, 12)
		# (436 per mille against 351), and the Ringing Clapper cannot rise more than 3% before it
		# passes 90% of the Great Cannon on (6, 12). The Ringing Clapper 32 in a burst of 1.2, not
		# 24 in 1.0: its crowd of 308 per mille was behind the Great Clapper's 350, a patch that
		# did not patch (now 549 against 425 at the bench, 25% ahead at worst, 394 against 314 on
		# (5, 12), and at most 87% of the Great Cannon, 532 against 609 on (6, 12))
		"a": {"id": "great_clapper", "dmg_c": 8000, "cd_t": 84, "range_mm": 2800},
		"b": {"id": "ringing_clapper", "dmg_c": 3200, "cd_t": 78, "splash_mm": 1200},
	},
	"toll_tower":
	{
		"builder": "bellfounder",
		"slot": 1,
		"cost": 65,
		"dmg_c": 800,
		"cd_t": 144,
		"range_mm": 2200,
		"air": false,
		"shot_um_t": 0,
		"pulse": true,
		"team": "stun",
		"stun_t": 36,
		"stun_immune_t": 60,
		"fork_cost": 70,
		"a": {"id": "great_toll", "dmg_c": 1000, "stun_t": 54, "range_mm": 2600},
		"b":
		{
			"id": "sky_toll",
			"dmg_c": 900,
			"range_mm": 2400,
			"air": true,
			"air_slow_pm": 330,
			"air_slow_t": 120,
			# (M8) a third slower for 2 s, not half, and +160% to fliers, not +80%: at half its pulse
			# held a flier in its reach 3.50 s on (14, 8), where her plan builds it, against the
			# Drowsy Clay Hive's 2.30 there, a patch past a strong Builder's best (the fork bench
			# holds the slow since the pass's review); a third holds one at most 1.84 s, 83% of
			# the Drowsy Clay Hive's 2.16 on (4, 11). A Duskmoth then takes a pulse less, so its
			# damage rose to keep the Bellfounder's Hard: three pulses of 23.4 take wave 5's (66.00
			# at Hard, 69.00 at Very Hard), where at +130% her one Sky Toll by then let 4 of them
			# through, at +80% four pulses of 16.2 left them standing, and at +100% six of wave
			# 11's 18 (115.50) stood and 4 got through. On a flock at its bends it does what the
			# Royal Apiary does (346 per mille against 354 on (14, 8)): the Bellfounder's one tower
			# for the sky, the exception design 3.8 records
			"air_bonus_pm": 1600,
		},
	},
	"chime_post":
	{
		"builder": "bellfounder",
		"slot": 2,
		"cost": 60,
		"dmg_c": 0,
		"cd_t": 30,
		"range_mm": 2500,
		"air": false,
		"shot_um_t": 0,
		"team": "crack",
		"crack_c": 200,
		"fork_cost": 60,
		"a": {"id": "deep_chime", "crack_c": 400},
		# (fork pass) the Long Chime cracks 3 within 4.0, not 2 within 3.2: a battery on a line of
		# Thornbacks gained 249 per mille from it against the Deep Chime's 359, a crack of 2 over a
		# little more road being worth less than one of 4 (now 481, +34%), while the Deep Chime's 4
		# still lifts a held Bristlesow more, 1,238 against 937 (+32%)
		"b": {"id": "long_chime", "crack_c": 300, "range_mm": 4000},
	},
	# M6: the Beekeeper's kit (design 3.4)
	"clay_hive":
	{
		"builder": "beekeeper",
		"slot": 0,
		"cost": 60,
		"dmg_c": 300,
		"cd_t": 18,
		"range_mm": 3000,
		"air": true,
		"shot_um_t": 0,
		"cloud_mm": 900,
		"fork_cost": 70,
		# (fork pass) the Great Clay Hive stings 5, not 4, and the Drowsy Clay Hive 1.5, not 3,
		# slowing 35%, not 25%: the Drowsy one only added its slow, which kept a crowd in its
		# cloud long enough to out-damage the Great one (429 per mille against 405), and at 2 it
		# still did on (4, 12), where her plan builds a Clay Hive (312 against 347, 11% behind);
		# at 1.5 the Great one leads by 48% at worst (347 against 234 there, 504 against 271 at
		# the bench), and the Drowsy one holds a line of Scuttlers 1.35 s each against none. 40%
		# for 1.5 s held 1.92 s, past 90% of the Great Toll's 2.06, a patch too strong
		"a": {"id": "great_clay_hive", "dmg_c": 500, "cloud_mm": 1200},
		"b": {"id": "drowsy_clay_hive", "dmg_c": 150, "slow_pm": 350, "slow_t": 60},
	},
	"apiary":
	{
		"builder": "beekeeper",
		"slot": 1,
		"cost": 85,
		"dmg_c": 1800,
		"cd_t": 48,
		"range_mm": 4200,
		"air": true,
		"shot_um_t": 180000,
		"aim": "winged",
		"air_bonus_pm": 500,
		"fork_cost": 80,
		# (fork pass) the Royal Apiary 24 with +135% to fliers, not 34 with +50%: the playtest's
		# "not a real choice", both branches doing 46.9 a second to a flier of wave 12 (two bolts of
		# 75 or three of 51 for its 112.50) and within 10% at armour. 56.4 takes that Duskmoth in two
		# bolts, 70.3 a second against the Queen's Guard's 26.2. It is the Apiary's anti-air and
		# stays one (design 3.8): at the pass's first 27 with +110% the Queen's Guard led it on a
		# Thornback by 20% at Hard's creep health (33.0 a second against 27.5: 7 stings a kill
		# against 15 bolts), and a faster Guard (every 1.3 s) killed the Bristlesow while the
		# Beekeeper stacked every wave, so stacking cost her 2 lives against her list's none
		# (stacking_every_wave_costs_lives_beekeeper asks 5); at 24 the Guard leads by 35% at
		# worst (33.0 against 24.3 at Hard's), and on unarmoured ground too (31.5 a second against
		# 28.2 on a Gourdling, a crowd's 341 per mille against 277)
		"a": {"id": "royal_apiary", "dmg_c": 2400, "air_bonus_pm": 1350},
		# (M6 balance: the design's 40 every 1.2 s did less than the Royal Apiary's 34 every
		# 0.8 s to every armoured creep, so the patch for Armored never patched; 50 that
		# ignores 3 armour does 40.8 a second to a Thornback against the Royal Apiary's 37.5,
		# 39.2 to the Bristlesow against 35, and stays behind it on unarmoured creeps)
		# (fork pass) 54 every 86 ticks (1.43 s) piercing 4, no flier bonus, at the most health in
		# reach (queens_guard_aims_at_most_health): 35.0 and 35.6 a second to a Thornback and the
		# Bristlesow against the Royal Apiary's 25.0 and 22.5, and at most 71% of the Great
		# Clapper (37.6 against 52.3 at four seats' health); at the design's 1.4 s it did 35.7 to a
		# Thornback, within a hair of 90% of the Siege Perch's 40.0, the best a strong Builder had
		# before the Great Clapper's rise
		"b":
		{
			"id": "queens_guard",
			"dmg_c": 5400,
			"cd_t": 86,
			"pierce_c": 400,
			"aim": "most_hp",
			"air_bonus_pm": 0,
		},
	},
	"hive_hum":
	{
		"builder": "beekeeper",
		"slot": 2,
		"cost": 60,
		"dmg_c": 0,
		"cd_t": 30,
		"range_mm": 2200,
		"air": false,
		"shot_um_t": 0,
		"team": "haste",
		"haste_pm": 150,
		"fork_cost": 70,
		"a": {"id": "great_hum", "haste_pm": 250},
		# (fork pass) 18%, not 15%: on a wide battery (six Arrow Towers, three of them 2.2 to 3.0
		# away) it lifted 130 per mille against the Great Hum's 115 (now 173, +50%), while the
		# Great Hum keeps a tight battery, 224 against 177 (+27%). A 30-tick Arrow Tower fires every
		# 25 ticks under any haste from 16% to 20%, so 17% measures as 18%
		"b": {"id": "long_hum", "haste_pm": 180, "range_mm": 3000},
	},
}

## Creeps by id. Keys: hp_c (health in hundredths, before wave growth and seat scaling),
## speed_um_t, armor_c (flat armour per hit, hundredths), bounty (gold to every seat of
## the team), toll (lives a leak costs); optional winged (bool: only `air` towers reach
## it, and it follows the road like any creep), boss (bool) and control_resist_pm (slows
## on it shrink by this share where the rules turn control_resist on; on a boss a stun
## becomes a slow, M6). Balance (M2, against the bots of tests/balance): the Bristlesow
## has 500 health, not the design's 900, which no team could take down at wave 6. (M8) At
## Normal every Builder's plan alone kills it (the owner's decision of 2 November 2026,
## bot_kills_bristlesow_solo_*): its numbers stay, and the Lamplighter's and the Lookout's
## openings answer it with an Iron Mortar and a Siege Perch before wave 6 (data/plans).
const CREEPS := {
	"gourdling": {"hp_c": 2400, "speed_um_t": 21667, "armor_c": 0, "bounty": 3, "toll": 1},
	"scuttler": {"hp_c": 1600, "speed_um_t": 33333, "armor_c": 0, "bounty": 2, "toll": 1},
	"thornback": {"hp_c": 8000, "speed_um_t": 14167, "armor_c": 400, "bounty": 6, "toll": 2},
	"hollowtide_crest":
	{
		"hp_c": 70000,
		"speed_um_t": 10000,
		"armor_c": 400,
		"bounty": 60,
		"toll": 10,
		"boss": true,
		"control_resist_pm": 500,
	},
	"duskmoth":
	{"hp_c": 3000, "speed_um_t": 25000, "armor_c": 0, "bounty": 3, "toll": 1, "winged": true},
	"bristlesow":
	{
		"hp_c": 50000,
		"speed_um_t": 11667,
		"armor_c": 600,
		"bounty": 50,
		"toll": 5,
		"boss": true,
		"control_resist_pm": 300,
	},
}

## Each wave is a list of groups spawned one after another. A group's interval is the
## wait before each of its creeps, the first creep of a wave excepted. Counts never
## change with the number of players (design 2.3); hp_by_seats_pm does.
const WAVES := {
	# Wickhollow's twelve (design 2.3): each check taught alone (1 to 5), the first boss
	# (6), each Builder's strong pair (7 to 10), all four at once (11), the Crest (12).
	# The Scuttlers of wave 3 come every 0.7 s and the Duskmoths of wave 5 every 1.2 s
	# (the design's 0.5 and 0.9 ended both waves in about twenty seconds).
	"hollow12":
	[
		[{"creep": "gourdling", "count": 10, "interval_t": 54}],
		[{"creep": "gourdling", "count": 18, "interval_t": 27}],
		[{"creep": "scuttler", "count": 12, "interval_t": 42}],
		[
			{"creep": "gourdling", "count": 8, "interval_t": 42},
			{"creep": "thornback", "count": 4, "interval_t": 84},
		],
		[{"creep": "duskmoth", "count": 8, "interval_t": 72}],
		[
			{"creep": "thornback", "count": 3, "interval_t": 72},
			{"creep": "bristlesow", "count": 1, "interval_t": 120},
		],
		[
			{"creep": "gourdling", "count": 20, "interval_t": 24},
			{"creep": "scuttler", "count": 10, "interval_t": 24},
		],
		[
			{"creep": "thornback", "count": 6, "interval_t": 66},
			{"creep": "duskmoth", "count": 8, "interval_t": 42},
		],
		[
			{"creep": "scuttler", "count": 16, "interval_t": 24},
			{"creep": "thornback", "count": 5, "interval_t": 60},
		],
		[
			{"creep": "duskmoth", "count": 12, "interval_t": 36},
			{"creep": "gourdling", "count": 20, "interval_t": 21},
		],
		[
			{"creep": "gourdling", "count": 16, "interval_t": 21},
			{"creep": "scuttler", "count": 10, "interval_t": 24},
			{"creep": "thornback", "count": 5, "interval_t": 60},
			{"creep": "duskmoth", "count": 8, "interval_t": 36},
		],
		[
			{"creep": "duskmoth", "count": 6, "interval_t": 42},
			{"creep": "thornback", "count": 4, "interval_t": 60},
			{"creep": "hollowtide_crest", "count": 1, "interval_t": 180},
		],
	],
	"classic8":
	[
		[{"creep": "gourdling", "count": 8, "interval_t": 54}],
		[{"creep": "gourdling", "count": 12, "interval_t": 48}],
		[{"creep": "scuttler", "count": 12, "interval_t": 30}],
		[
			{"creep": "gourdling", "count": 8, "interval_t": 42},
			{"creep": "thornback", "count": 4, "interval_t": 84},
		],
		[{"creep": "scuttler", "count": 16, "interval_t": 27}],
		[{"creep": "thornback", "count": 8, "interval_t": 72}],
		[
			{"creep": "gourdling", "count": 12, "interval_t": 30},
			{"creep": "scuttler", "count": 10, "interval_t": 24},
		],
		[
			{"creep": "thornback", "count": 5, "interval_t": 60},
			{"creep": "hollowtide_crest", "count": 1, "interval_t": 180},
		],
	],
}

## The Builders (design 3.3 and 3.4; names from world.md). Every entry has exactly the
## fields of BUILDER_FIELDS, no more and no fewer; M2 may tune values, nobody renames a
## field. Ids are SimContent ids unless a field says otherwise.
##   name        display: the Builder's name ("Tamsin Wick")
##   title       display: the epithet with its article ("the Lamplighter")
##   home        display: the land the Builder comes from ("Wickhollow")
##   role        a ROLE_IDS id: the job in a word; a label, never a lock (design 3.1)
##   difficulty  display: 1 to 3 stars
##   covers      the CHECK_IDS it is strong against, in CHECK_IDS order: what lights the
##               team coverage row (team_covers()) and what the caretaker's patching
##               forks follow, so it is part of the rules hash
##   patches     {check id: [branch ids]}: the fork branches that lift one of its weak
##               checks to passable, never to strong (branch_helps())
##   towers      its kit: three base TOWERS ids in slot order, on Q, W and E
##   branches    per kit tower, [branch A id, branch B id], equal to TOWERS[tower].a.id
##               and .b.id; Q and W choose them on a selected, unforked tower of yours
##   perk        its passive: {"id": a PERK_IDS id, then the numbers it uses}. (M2) The
##               simulation applies it: "thrifty" sells the owner's towers at sell_pm,
##               "keen_sight" adds range_mm to the reach of every tower the owner builds;
##               (M6) "bronze_hand" adds pierce_c to every hit the owner's towers deal,
##               "hive_tithe" pays the owner `gold` for each of her towers on one of
##               `bases` at every wave clear, at most `cap`
##   plan        stem of its caretaker plan, data/plans/<plan>.json; until that file is
##               written the Builder's plan is empty (the caretaker only stands Ready)
##   glyph       display: stem of its icon in ui/icons/; Game.BUILDERS spells the path
##   accent      display: its own tint, 0xRRGGBB, at most 35% saturated so it never
##               reads as a seat colour (only seat colours are saturated, design 5.9)
const BUILDERS := {
	"lamplighter":
	{
		"name": "Tamsin Wick",
		"title": "the Lamplighter",
		"home": "Wickhollow",
		"role": "warden",
		"difficulty": 1,
		"covers": ["swarm", "swift"],
		"patches": {"armored": ["iron_mortar"], "winged": ["skyward_loft", "rime_spire"]},
		"towers": ["arrow", "cannon", "frost"],
		"branches":
		[
			["longbow_loft", "skyward_loft"],
			["great_cannon", "iron_mortar"],
			["deep_frost", "rime_spire"],
		],
		"perk": {"id": "thrifty", "sell_pm": 900},
		"plan": "lamplighter",
		"glyph": "builder_lamplighter",
		"accent": 0xD9C49B,
	},
	"lookout":
	{
		"name": "Edda Greyplume",
		"title": "the Lookout",
		"home": "Fogholm",
		"role": "marksman",
		"difficulty": 2,
		"covers": ["armored", "winged"],
		"patches": {"swarm": ["kestrel_flock"], "swift": ["pinning_ballista"]},
		"towers": ["perch_ballista", "hawk_roost", "owls_eye"],
		"branches":
		[
			["siege_perch", "pinning_ballista"],
			["falcon_roost", "kestrel_flock"],
			["owls_glare", "twin_gaze"],
		],
		"perk": {"id": "keen_sight", "range_mm": 400},
		"plan": "lookout",
		"glyph": "builder_lookout",
		"accent": 0xAEB8C2,
	},
	# M6: their plans are data/plans/bellfounder.json and beekeeper.json
	"bellfounder":
	{
		"name": "Ottilie Brass",
		"title": "the Bellfounder",
		"home": "Brackwater",
		"role": "breaker",
		"difficulty": 2,
		"covers": ["swift", "armored"],
		"patches": {"swarm": ["ringing_clapper"], "winged": ["sky_toll"]},
		"towers": ["clapper_tower", "toll_tower", "chime_post"],
		"branches":
		[
			["great_clapper", "ringing_clapper"],
			["great_toll", "sky_toll"],
			["deep_chime", "long_chime"],
		],
		"perk": {"id": "bronze_hand", "pierce_c": 200},
		"plan": "bellfounder",
		"glyph": "builder_bellfounder",
		"accent": 0xC2A98A,
	},
	"beekeeper":
	{
		"name": "Sefa Amberwell",
		"title": "the Beekeeper",
		"home": "Thousandwell",
		"role": "sweeper",
		"difficulty": 3,
		"covers": ["swarm", "winged"],
		"patches": {"swift": ["drowsy_clay_hive"], "armored": ["queens_guard"]},
		"towers": ["clay_hive", "apiary", "hive_hum"],
		"branches":
		[
			["great_clay_hive", "drowsy_clay_hive"],
			["royal_apiary", "queens_guard"],
			["great_hum", "long_hum"],
		],
		"perk": {"id": "hive_tithe", "gold": 2, "cap": 12, "bases": ["clay_hive", "hive_hum"]},
		"plan": "beekeeper",
		"glyph": "builder_beekeeper",
		"accent": 0xD0C294,
	},
}

## The fields of every BUILDERS entry, and those that only label or show a Builder, which
## rules_hash() leaves out (a new field is hashed unless it is listed here). A field the
## simulation reads is never listed: contract_m2m3_tables follows every SimContent helper
## the simulation calls and fails on one that reads a field left out.
const BUILDER_FIELDS := [
	"name",
	"title",
	"home",
	"role",
	"difficulty",
	"covers",
	"patches",
	"towers",
	"branches",
	"perk",
	"plan",
	"glyph",
	"accent",
]
const BUILDER_DISPLAY_KEYS := [
	"name", "title", "home", "role", "difficulty", "patches", "glyph", "accent"
]

## Stable orders for the codec: a mode, Builder, tower or creep is stored as its index
## here, so each list only ever grows at its end (contract_ids_keep_state_hashes).
## MODE_IDS and BUILDER_IDS follow the ids of shared/net/protocol.json's "modes" and
## "builders"; a mode can be named before RULES can play it (RULES.has(mode) says).
## TOWER_IDS names every tower form, bases and branches: a SimTower's and a SimShot's
## kind is the base, and the tower's branch says which form stands (tower_form()).
const TOWER_IDS := [
	"arrow",
	"cannon",
	"frost",
	# M2: the Lamplighter's branches, A then B, for Q, W, E
	"longbow_loft",
	"skyward_loft",
	"great_cannon",
	"iron_mortar",
	"deep_frost",
	"rime_spire",
	# M2: the Lookout's bases, then its branches
	"perch_ballista",
	"hawk_roost",
	"owls_eye",
	"siege_perch",
	"pinning_ballista",
	"falcon_roost",
	"kestrel_flock",
	"owls_glare",
	"twin_gaze",
	# M6: the Bellfounder's bases, then its branches
	"clapper_tower",
	"toll_tower",
	"chime_post",
	"great_clapper",
	"ringing_clapper",
	"great_toll",
	"sky_toll",
	"deep_chime",
	"long_chime",
	# M6: the Beekeeper's bases, then its branches
	"clay_hive",
	"apiary",
	"hive_hum",
	"great_clay_hive",
	"drowsy_clay_hive",
	"royal_apiary",
	"queens_guard",
	"great_hum",
	"long_hum",
]
const CREEP_IDS := [
	"gourdling", "scuttler", "thornback", "hollowtide_crest", "duskmoth", "bristlesow"
]
const BUILDER_IDS := ["lamplighter", "lookout", "bellfounder", "beekeeper"]
const MODE_IDS := ["classic", "high_water", "tide_race", "undertow"]
## (M8) The difficulty levels (design 2.6, contract-m8 §1 and §3), append only like the
## lists above: a level's index is its wire id (protocol.json's "difficulties") and what
## the codec stores. The party picks one as it picks the mode; a preset whose `levels` is
## on takes it, any other plays Normal whatever is asked.
const DIFFICULTY_IDS := ["normal", "hard", "very_hard"]
## (M8) The keys each level lays over a preset that takes levels: `lives` replaced, and
## `hp_pm` (creep health), `boss_hp_pm` (a boss's instead) and `boss_armor_c` added, all
## applied at spawn after the wave growth and the seat scaling (SimWaves.spawn). Normal
## lays nothing, so it changes no number and no state hash. Bounties, tolls, gold, windows,
## waves and counts are the preset's at every level, so only the creeps' health, a boss's
## armour and the lives tell the levels apart. Every number but Normal's is tunable against
## the level gates (bot_wins_hard_*, bot_reaches_crest_very_hard_*,
## difficulty_very_hard_half_win, idle_player_loses_hard, _very_hard,
## difficulty_orders_the_levels, race_mirror_is_fair_hard); their words on screen are
## Game.DIFFICULTIES'.
##
## Tuned by those gates from the design's 1300 and 1600 creep health, which the plan bots
## could not stand: at 1300 the Lamplighter alone fell on wave 10 at Hard and every Builder
## alone fell by wave 7 at Very Hard, the Bellfounder on wave 2. Creep health is the level's
## steepest number, since every creep of every wave has it; the lives and the bosses carry
## the rest. Hard's 1100 keeps the Lamplighter, the Beekeeper and both complementary pairs
## at 10 of 15 lives (at 1200 the Lamplighter kept 9, she and the Lookout together 7);
## Very Hard's 1150 lets the Lamplighter alone reach wave 12 (at 1250 she fell on wave 10).
## Boss health 1250 to 1500 and armour 0 to 1 at Hard made no difference to any gate, so the
## design's stand. Creep health has a cliff at 1167: wave 2's Gourdling has 30.00 health at
## Normal and a Clapper Tower strikes 35, so from 1167 it takes two strikes and the
## Bellfounder alone falls on wave 2 (measured at Very Hard at 1200 and 1250). So
## Very Hard cannot move its weight from the bosses into the creeps without her opening
## changing, and its creeps stay 1150.
##
## Very Hard's bosses (the owner's "a close wave 12", decision 16, read on the Crest after the
## playtest H3-02 found the level "a wall at wave 6"): at the design's 2000 and +2 every
## Builder alone fell to a Crest of 5,250 health and armour 6 it had dealt 74 to 94% of, and
## only the Lamplighter with the Lookout won. 1550 and +1, Hard's armour, give the Crest
## 4,068 and armour 5 alone: the Lamplighter, the Lookout, the Bellfounder (on 1 life) and the
## Beekeeper alone and the Lamplighter with the Lookout kill it 67 to 83 s into a walk of 87 to
## 91 s, the Bellfounder with the Beekeeper leaks it with 4% left, and every win keeps 1 to 5
## lives. At 1575 four of the six won (the Bellfounder alone dealt all but 0.4% of it), at
## 1600 four, the Lamplighter's Crest dying 4 s and the Beekeeper's 1 s from the Holdfast, at
## 1650 two; at +2 with 1550 three, the Lamplighter's Crest leaking with 5% left. The
## Bristlesow (wave 6) stays 5 lives from every plan: its health must stay above Hard's
## (contract-m8 §3), where every plan already leaks it, and the plans' best opening, the
## Beekeeper's, deals 1,508 of its 1,743 (86%), the Lookout's 1,287 (74%), the Bellfounder's
## 1,134 (65%) and the Lamplighter's 1,059 (61%), against 1,440 and 543 of the 2,250 and
## armour 8 it had (the Lookout's and the Lamplighter's openings answer it since it dies at
## Normal, data/plans; before, they dealt 31% and 37% of this one). Had a plan killed it,
## its win would keep more than half the lives, which the gates call no close wave 12. Lives
## stay 10, so the Crest's toll is every life left and it must die on the road.
const DIFFICULTIES := {
	"normal": {},
	"hard": {"lives": 15, "hp_pm": 1100, "boss_hp_pm": 1500, "boss_armor_c": 100},
	"very_hard": {"lives": 10, "hp_pm": 1150, "boss_hp_pm": 1550, "boss_armor_c": 100},
}

## Undertow's Drift (design 1.4, M7 contract): the packs a duel's window offers, by map,
## then by the CHECK_IDS id a pack tests, which is also its id on the wire and in the codec
## (UNCORK's `a` is its CHECK_IDS index). Each names the creep it sends and how many at each
## tier (I, II, III); the tiers' windows, prices and stipends are the undertow preset's.
## Display names ("Gourd Rush" on Wickhollow) are Game's, so no map's flavour reaches an id.
## The sends' pass (the owner's decision of 2 November 2026): the packs that rarely breached
## grow. Corked in every window it was offered, each pack against each Builder's mirror at
## a 40% health premium (the harness's options "packs"), the Scuttle of 6, 10 and 14 breached
## 13% of the time and the Thorn Herd of 2, 3 and 5 25%, beside the Gourd Rush's 26% and
## the Moth Cloud's 27%; on m8 the caretaker's Thorn Herds breached 14 of 278. The Scuttle
## is 8, 13 and 18 now, a third more, and the Thorn Herd 3, 5 and 7 (a tier III herd carries
## 14 lives, as the Gourd Rush's 14 Gourdlings do). The Gourd Rush stays: at 7, 12 and 16 it
## lowered the breach of tier III to 22% (the Beekeeper's and the Lookout's mirrors, which it
## is sent into, hold it better than what it took the place of). The Moth Cloud, the pack
## that breached most, is one smaller at tier II: the caretaker sends it at a weak sky
## (SimUndertow.pick_pack), and 6 a quarter stronger, on wave 8's own 8 Duskmoths, sank every
## Bellfounder mirror in wave 8 with 4 towers standing; with 5 most last to wave 12.
## The packs' matrix (the Veteran's third session, H3-01: only the Moth Cloud breached;
## sim_harness.gd pack_matrix, the duel_<check>_pack_breaches_the_weak gates): each pack
## corked by the balanced style wherever it was offered, against each Builder's mirror. After
## the sends' pass, defended by the caretaker, the balanced style and the turtle over seeds 1
## to 5, the Moth Cloud breached the two Builders weak to the sky 75% of the time (58 of 77),
## the Thorn Herd its two 29%, the Scuttle 7% and the Gourd Rush none in 135, beside 1 to 20%
## against the Builders that cover each: the Moth Cloud was the one send that read the
## rival's defence, the Gourd Rush a tax against every Builder. The Gourd Rush and the Scuttle
## are bigger at tier II and III (and stronger, the duel's pack_hp_pm), the Thorn Herd two
## larger at tier III and spread (pack_gap_t), and the Moth Cloud two smaller at tier III.
## Against the caretaker each now breaches its two weak Builders 44 to 52% of the time and
## those that cover it 15 to 21% (the Moth Cloud 83% and none). Every step is held by the
## duel's gates, which turn on the Lookout's mirror: a pack that breaches a Lookout much more
## than half the time lets the reckless corker beat her turtle (its Gourd Rushes of 24 at 60%
## more health took her by wave 10) and lifts her mirror past what duel_sends_breach's half
## allows (52% and 55% overall where her mirror reached 41 to 53%). Tier I stays as it was: a
## bunched Gourd Rush of 6 at 60% more health broke her opening beside wave 2's own 18
## Gourdlings (9 lives), and the reckless corker sends one every window from 2.
##   swarm   6, 14, 20 (was 6, 10, 14): at tier II 10 the Lookout and the Bellfounder held
##           every one (0 of 10), 14 breaches the Lookout's 5 of 5 and the Bellfounder's 1 of
##           5; at tier III 24 tipped the reckless gate (above), 20 breaches the two 8 of 23.
##   swift   8, 17, 28 (was 8, 13, 18): at tier II 14 the Lookout held every one (0 of 5),
##           17 breaches her 5 of 5; 15 and 32 with 60% more health breached her 8 of 10 and
##           took the reckless and Seawall gates with them, 28 at 40% breaches her tier III 3
##           of 13. The Beekeeper holds no tier I or III Scuttle well (8 of 11).
##   armored 3, 5, 9 (was 3, 5, 7): spread, two more at tier III breach the Beekeeper 10 of
##           18, where 7 breached her 30%; 10 breached her two 44% but the Lookout's tier III,
##           who covers armour, 30%. The Lamplighter holds every tier III herd (0 of 4 here, 0
##           of 22 in the matrix's three styles): by window 9 her plan has forked its Iron
##           Mortar, her patch for armour, and a herd that broke her would sink the Lookout
##           first. A Thorn Herd is a threat to her opening (tiers I and II, 3 of 5), as a Moth
##           Cloud is to hers until her Skyward Lofts.
##   winged  4, 5, 7 (was 4, 5, 9): the Moth Cloud still breaches its two four times in five
##           (a no-sky opening lets any number through at tier I), and two fewer at tier III
##           leave duel_sends_breach the room the other three now take.
const PACKS := {
	"hollow":
	{
		"swarm": {"creep": "gourdling", "counts": [6, 14, 20]},
		"swift": {"creep": "scuttler", "counts": [8, 17, 28]},
		"armored": {"creep": "thornback", "counts": [3, 5, 9]},
		"winged": {"creep": "duskmoth", "counts": [4, 5, 7]},
	},
}

## Display orders, append only: the four checks (design 3.2) as the coverage row shows
## them, the roles (3.1) and the perks (3.4). Game holds their names, glyphs and icons.
const CHECK_IDS := ["swarm", "swift", "armored", "winged"]
const ROLE_IDS := ["warden", "marksman", "breaker", "sweeper"]
const PERK_IDS := ["thrifty", "keen_sight", "bronze_hand", "hive_tithe"]

const MAP_DIR := "res://data/"
const PLAN_DIR := "res://data/plans/"
## plan_steps()'s flags: the step holds the caretaker's Ready in a race ("ready": false).
const STEP_HOLDS_READY := 1


## A mode's rules with its name, ready for SimMatch, at a level (M8, contract-m8 §3): the
## preset with "difficulty" set to the level it plays (level_of) and, where the preset
## takes levels, that level's DIFFICULTIES keys laid over it (`lives` replaced, `hp_pm`,
## `boss_hp_pm` and `boss_armor_c` added). A preset without `levels` plays Normal
## whatever is asked.
static func rules(mode: String, difficulty := "normal") -> Dictionary:
	var preset: Dictionary = RULES[mode].duplicate(true)
	preset["mode"] = mode
	var level := level_of(mode, difficulty)
	preset["difficulty"] = level
	preset.merge(DIFFICULTIES[level], true)
	return preset


## (M8) The level a match of `mode` asked to play `difficulty` plays: the level itself where
## the preset takes levels and knows it, else "normal" (classic and undertow always).
static func level_of(mode: String, difficulty: String) -> String:
	var preset: Dictionary = RULES.get(mode, {})
	if not bool(preset.get("levels", false)) or not DIFFICULTIES.has(difficulty):
		return "normal"
	return difficulty


static func map_text(map_name: String) -> String:
	return FileAccess.get_file_as_string(MAP_DIR + map_name + ".txt")


## A tower's numbers at a branch (-1 unforked, 0 for A, 1 for B): the base table with
## the branch's keys laid over it.
static func tower_stats(kind: String, branch: int) -> Dictionary:
	var base: Dictionary = TOWERS[kind]
	var stats := base.duplicate()
	stats.erase("a")
	stats.erase("b")
	var key := branch_key(branch)
	if key != "" and base.has(key):
		stats.merge(base[key], true)
	return stats


static func branch_key(branch: int) -> String:
	if branch == 0:
		return "a"
	if branch == 1:
		return "b"
	return ""


static func has_branch(kind: String, branch: int) -> bool:
	var key := branch_key(branch)
	return key != "" and (TOWERS[kind] as Dictionary).has(key)


## The TOWER_IDS id of the form a tower of base `kind` stands as: the base while it is
## unforked (-1), else its branch's id. Display tables, icons and models key by it.
static func tower_form(kind: String, branch: int) -> String:
	if has_branch(kind, branch):
		return str(TOWERS[kind][branch_key(branch)]["id"])
	return kind


## The tower a Builder places from slot 0, 1 or 2, or "" when the slot is empty.
static func kit_tower(builder: String, slot: int) -> String:
	var kit: Array = BUILDERS[builder]["towers"]
	return str(kit[slot]) if slot >= 0 and slot < kit.size() else ""


## A Builder's plan for the caretaker and the test bots: an Array of steps
## {"build": kind, "cell": [x, z]} and {"fork": "a" or "b", "cell": [x, z]}, each with
## two optional keys:
##   "alt"    [[x, z], ...]: cells to use, in order, when "cell" is taken (a build) or
##            holds no unforked tower of the seat's (a fork), so two seats with the same
##            Builder each play the whole plan on cells of their own
##   "patch"  a CHECK_IDS id on a fork that lifts the Builder's weak check: the caretaker
##            takes it only while no Builder of the team covers that check, and the
##            other branch (the deepening one) when one does (design 6.7: it forks for
##            the checks the team lacks)
##   "ready"  (M6) false: in a race, the caretaker does not call the wave while this is
##            the step it waits on (it waits out the window, saving for it); without the
##            hint it calls each wave once the window's build steps are done
## "steps" is the plan for every mode; a mode may have its own under its name,
## {"<mode>": {"steps": [...]}}: the Lamplighter keeps M1's under "classic", which
## tests/bot.gd, the README's shots and the classic scenarios play. (M8) "stack" beside
## "steps" lists the waves the plan calls during the wave before (plan_stack).
static func plan(builder: String, mode := "classic") -> Array:
	return plan_of(plan_file(builder), mode)


## A Builder's plan file as parsed, {} where it is not written yet (its caretaker only stands
## Ready) or is not a JSON object; plan_of() and plan_stack_of() read a mode's part of it, so
## a match reads each file once (SimMatch.setup).
static func plan_file(builder: String) -> Dictionary:
	var path := PLAN_DIR + str(BUILDERS[builder]["plan"]) + ".json"
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


## The steps of plan file `file` (plan_file()) for `mode`: its mode block's where it has one.
static func plan_of(file: Dictionary, mode: String) -> Array:
	if file.get(mode) is Dictionary:
		return (file[mode] as Dictionary).get("steps", [])
	return file.get("steps", [])


## (M8, contract-m8 §1 and §2) The waves a Builder's plan stacks in `mode`, in the order it
## lists them: its caretaker (where it calls waves itself, a race, at Normal) and its plan
## bot say Ready during wave k - 1 for each wave k listed, once the build steps they can pay
## for are done. The list is the plan's top-level "stack", for every preset that stacks; a
## mode block {"<mode>": {"stack": [...]}} may hold its own. [] for a plan that lists none,
## and in a preset that never stacks (stack_max 1 or absent), whatever the file says.
static func plan_stack(builder: String, mode := "classic") -> PackedInt32Array:
	return plan_stack_of(plan_file(builder), mode)


## plan_stack() from a plan file already parsed (plan_file()).
static func plan_stack_of(file: Dictionary, mode: String) -> PackedInt32Array:
	var out := PackedInt32Array()
	if int((RULES.get(mode, {}) as Dictionary).get("stack_max", 1)) < 2:
		return out
	var list: Variant = file.get("stack", [])
	if file.get(mode) is Dictionary and (file[mode] as Dictionary).has("stack"):
		list = (file[mode] as Dictionary)["stack"]
	if list is Array:
		for wave: Variant in list:
			out.append(int(wave))
	return out


## The same plan as integers for the caretaker: one PackedInt32Array per step,
## [op, slot or branch, x, z, patch, flags, then the "alt" cells as x, z pairs]: op 0
## builds from a kit slot and 1 forks the seat's tower on the cell, patch is the
## CHECK_IDS index of the check the fork patches or -1, flags holds STEP_HOLDS_READY for a
## step marked "ready": false. Unknown steps are dropped.
static func plan_steps(builder: String, mode := "classic") -> Array:
	return plan_steps_of(builder, plan(builder, mode))


## plan_steps() for any list of plan entries (a test may hand the caretaker its own).
static func plan_steps_of(builder: String, entries: Array) -> Array:
	var kit: Array = BUILDERS[builder]["towers"]
	var steps := []
	for step: Variant in entries:
		if not step is Dictionary:
			continue
		var entry: Dictionary = step
		var cell: Array = entry.get("cell", [])
		if cell.size() != 2:
			continue
		var head := PackedInt32Array()
		if entry.has("build") and kit.has(str(entry["build"])):
			head = PackedInt32Array([0, kit.find(str(entry["build"]))])
		elif entry.has("fork"):
			head = PackedInt32Array([1, 0 if str(entry["fork"]) == "a" else 1])
		else:
			continue
		head.append(int(cell[0]))
		head.append(int(cell[1]))
		head.append(CHECK_IDS.find(str(entry.get("patch", ""))))
		head.append(STEP_HOLDS_READY if entry.get("ready", true) == false else 0)
		for alt: Variant in entry.get("alt", []):
			if alt is Array and (alt as Array).size() == 2:
				head.append(int(alt[0]))
				head.append(int(alt[1]))
		steps.append(head)
	return steps


## A Builder's passive number `key` ("sell_pm", "range_mm") when its perk is `perk_id`,
## else `otherwise`.
static func perk_value(builder: String, perk_id: String, key: String, otherwise: int) -> int:
	var perk: Dictionary = BUILDERS[builder]["perk"]
	if str(perk.get("id", "")) != perk_id:
		return otherwise
	return int(perk.get(key, otherwise))


## A Builder's passive list `key` (Hive Tithe's "bases") when its perk is `perk_id`, else [].
static func perk_list(builder: String, perk_id: String, key: String) -> Array:
	var perk: Dictionary = BUILDERS[builder]["perk"]
	if str(perk.get("id", "")) != perk_id:
		return []
	return perk.get(key, [])


## The first 8 bytes of SHA-256 over every table that changes the rules, every Builder's
## plans, every mode's map and the caretaker's version (`caretaker`, this build's but for a
## test): the matchmaking key (design 6.9). One per build, whatever the mode: HELLO carries
## it before the party's leader picks a mode, and a party's MATCH_CONFIG and LOADED repeat it
## for any mode. (M8) It covers every level (DIFFICULTIES) and every plan's stack list too,
## still one hash for every mode and level, so HELLO is unchanged. JSON with sorted keys is
## the dump.
static func rules_hash(caretaker := CARETAKER_VERSION) -> PackedByteArray:
	var plans := []
	var stacks := []
	var maps := []
	for mode: String in MODE_IDS:
		if not RULES.has(mode):
			continue
		for builder: String in BUILDER_IDS:
			plans.append(plan(builder, mode))
			stacks.append(Array(plan_stack(builder, mode)))
		maps.append(map_text(RULES[mode]["map"]))
	var dump := JSON.stringify(
		[
			SIM_VERSION,
			RULES,
			TOWERS,
			CREEPS,
			WAVES,
			hashed_builders(),
			plans,
			maps,
			caretaker,
			DIFFICULTIES,
			stacks,
			ORDERS_VERSION
		],
		"",
		true
	)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(dump.to_utf8_buffer())
	return ctx.finish().slice(0, 8)


## BUILDERS as the rules hash sees it: in BUILDER_IDS order, without the fields that only
## label or show a Builder, so renaming one or retinting it never splits matchmaking.
static func hashed_builders() -> Array:
	var out := []
	for builder: String in BUILDER_IDS:
		var entry: Dictionary = (BUILDERS[builder] as Dictionary).duplicate(true)
		for key: String in BUILDER_DISPLAY_KEYS:
			entry.erase(key)
		out.append([builder, entry])
	return out


# ── What the hub, the Builders screen and the loading cards read (M3) ──


## Whether `builder` is strong against `check` (a CHECK_IDS id).
static func covers(builder: String, check: String) -> bool:
	return (BUILDERS[builder]["covers"] as Array).has(check)


## The checks any of `builders` is strong against, in CHECK_IDS order: the lit glyphs of
## the team coverage row. Duplicates count once; an unknown id counts for nothing.
static func team_covers(builders: Array) -> Array:
	var out := []
	for check: String in CHECK_IDS:
		for builder: Variant in builders:
			if BUILDERS.has(str(builder)) and covers(str(builder), check):
				out.append(check)
				break
	return out


## The weak check a branch of `builder`'s lifts to passable (its glyph sits beside the
## branch on the Builders screen and in its tooltip), or "" for a branch that deepens.
static func branch_helps(builder: String, branch_id: String) -> String:
	var patches: Dictionary = BUILDERS[builder]["patches"]
	for check: String in CHECK_IDS:
		if (patches.get(check, []) as Array).has(branch_id):
			return check
	return ""
