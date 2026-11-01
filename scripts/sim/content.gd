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
## Three presets: `classic`, M1's solo game kept as it was (eight waves, the three towers,
## today's upgrade standing in for fork branch A; no armour, no perks, no Help),
## `high_water`, the co-op mode of design 1.2 on Wickhollow's `hollow12` (a wave list is
## named after its map, not its mode) with flat armour, boss control resistance, the
## Builders' perks and Help, both for one to four seats on one shared hollow, and (M6)
## `tide_race`, High Water for two teams of one or two, each on its own hollow (design 1.3).
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
## which calls the waves of a race (its plan's `ready` hints). The rules hash covers it, so
## builds whose caretakers decide differently never share a match; SIM_VERSION, which the
## codec writes, does not move for it, since that would move every recorded state hash.
const CARETAKER_VERSION := 3

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
		"race": {"life_t": 600},
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
##                 the M6 balance pass (80%: its 9 is 16.2 to a flier, the ground keeps 9).
##                 A view shows it from this key, never from the form's name
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
		"b":
		{
			"id": "iron_mortar",
			"dmg_c": 4500,
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
		"b": {"id": "kestrel_flock", "dmg_c": 900, "bounces": 2, "bounce_mm": 1200},
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
		"b": {"id": "twin_gaze", "marks": 2},
	},
	# M6: the Bellfounder's kit (design 3.4). Tuned by the M6 balance gates (tests/balance,
	# bot_wins_solo_bellfounder): the Toll Tower's pulse deals 8, not 6 (at 6 a Bellfounder
	# alone left the Gourdlings of wave 7 at a quarter of their health and four got
	# through); the Sky Toll slows a flier for 2 s, not 1, and its 9 grows by 80% against
	# one (air_bonus_pm; the ground keeps the 9): at the design's numbers a Duskmoth of wave
	# 5 crossed the two Sky Tolls she can pay for by then with half its health left, and
	# every one of them got through.
	"clapper_tower":
	{
		"builder": "bellfounder",
		"slot": 0,
		"cost": 75,
		"dmg_c": 3000,
		"cd_t": 84,
		"range_mm": 2600,
		"air": false,
		"shot_um_t": 400000,
		"fork_cost": 85,
		"a": {"id": "great_clapper", "dmg_c": 7200, "cd_t": 96, "range_mm": 2800},
		"b": {"id": "ringing_clapper", "dmg_c": 2400, "cd_t": 78, "splash_mm": 1000},
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
			"air_slow_pm": 500,
			"air_slow_t": 120,
			"air_bonus_pm": 800,
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
		"b": {"id": "long_chime", "range_mm": 3200},
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
		"a": {"id": "great_clay_hive", "dmg_c": 400, "cloud_mm": 1200},
		"b": {"id": "drowsy_clay_hive", "slow_pm": 250, "slow_t": 60},
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
		"a": {"id": "royal_apiary", "dmg_c": 3400},
		# (M6 balance: the design's 40 every 1.2 s did less than the Royal Apiary's 34 every
		# 0.8 s to every armoured creep, so the patch for Armored never patched; 50 that
		# ignores 3 armour does 40.8 a second to a Thornback against the Royal Apiary's 37.5,
		# 39.2 to the Bristlesow against 35, and stays behind it on unarmoured creeps)
		"b": {"id": "queens_guard", "dmg_c": 5000, "cd_t": 72, "pierce_c": 300},
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
		"b": {"id": "long_hum", "range_mm": 3000},
	},
}

## Creeps by id. Keys: hp_c (health in hundredths, before wave growth and seat scaling),
## speed_um_t, armor_c (flat armour per hit, hundredths), bounty (gold to every seat of
## the team), toll (lives a leak costs); optional winged (bool: only `air` towers reach
## it, and it follows the road like any creep), boss (bool) and control_resist_pm (slows
## on it shrink by this share where the rules turn control_resist on; on a boss a stun
## becomes a slow, M6). Balance (M2, against the bots of tests/balance): the Bristlesow
## has 500 health, not the design's 900, which no team could take down at wave 6.
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

## Undertow's Drift (design 1.4, M7 contract): the packs a duel's window offers, by map,
## then by the CHECK_IDS id a pack tests, which is also its id on the wire and in the codec
## (UNCORK's `a` is its CHECK_IDS index). Each names the creep it sends and how many at each
## tier (I, II, III); the tiers' windows, prices and stipends are the undertow preset's.
## Display names ("Gourd Rush" on Wickhollow) are Game's, so no map's flavour reaches an id.
const PACKS := {
	"hollow":
	{
		"swarm": {"creep": "gourdling", "counts": [6, 10, 14]},
		"swift": {"creep": "scuttler", "counts": [6, 10, 14]},
		"armored": {"creep": "thornback", "counts": [2, 3, 5]},
		"winged": {"creep": "duskmoth", "counts": [4, 6, 9]},
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


## A mode's rules with its name, ready for SimMatch.
static func rules(mode: String) -> Dictionary:
	var preset: Dictionary = RULES[mode].duplicate(true)
	preset["mode"] = mode
	return preset


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
## tests/bot.gd, the README's shots and the classic scenarios play.
static func plan(builder: String, mode := "classic") -> Array:
	var path := PLAN_DIR + str(BUILDERS[builder]["plan"]) + ".json"
	if not FileAccess.file_exists(path):
		return []  # (a Builder whose plan is not written yet: its caretaker only stands Ready)
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return []
	var file: Dictionary = parsed
	if file.get(mode) is Dictionary:
		return (file[mode] as Dictionary).get("steps", [])
	return file.get("steps", [])


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
## for any mode. JSON with sorted keys is the dump.
static func rules_hash(caretaker := CARETAKER_VERSION) -> PackedByteArray:
	var plans := []
	var maps := []
	for mode: String in MODE_IDS:
		if not RULES.has(mode):
			continue
		for builder: String in BUILDER_IDS:
			plans.append(plan(builder, mode))
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
			caretaker
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
