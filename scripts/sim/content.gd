## The rules as data, in the simulation's integer units (design 4.2): ticks (1/60 s),
## millimetres for positions and ranges, micrometres for progress along the road and
## micrometres per tick for speeds, hundredths for health, damage and armour, per mille
## for shares. Names, models and icons live in game.gd under the same ids and are not
## part of the rules hash.
##
## M1 carries the `classic` preset: today's solo game (eight waves, the three towers, and
## today's upgrade standing in for fork branch A), playable by one to four seats on one
## shared hollow. M2 replaces it with the Vigil and `vigil12`.
class_name SimContent
extends RefCounted

const SIM_VERSION := 1

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
		"cap_t": 0,
		"signals": [3, 300],
	},
}

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
		"fork_cost": 60,
		"a": {"id": "deep_frost", "dmg_c": 800, "range_mm": 3200, "slow_pm": 600},
	},
}

const CREEPS := {
	"gourdling": {"hp_c": 2400, "speed_um_t": 21667, "armor_c": 0, "bounty": 3, "toll": 1},
	"scuttler": {"hp_c": 1600, "speed_um_t": 33333, "armor_c": 0, "bounty": 2, "toll": 1},
	"thornback": {"hp_c": 8000, "speed_um_t": 14167, "armor_c": 400, "bounty": 6, "toll": 2},
	"hollow_king":
	{
		"hp_c": 70000,
		"speed_um_t": 10000,
		"armor_c": 400,
		"bounty": 60,
		"toll": 10,
		"boss": true,
		"control_resist_pm": 500,
	},
}

## Each wave is a list of groups spawned one after another. A group's interval is the
## wait before each of its creeps, the first creep of a wave excepted.
const WAVES := {
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
			{"creep": "hollow_king", "count": 1, "interval_t": 180},
		],
	],
}

const BUILDERS := {
	"lamplighter": {"towers": ["arrow", "cannon", "frost"], "plan": "lamplighter"},
}

## Stable orders for the codec: a kind is stored as its index here. Append only.
const TOWER_IDS := ["arrow", "cannon", "frost"]
const CREEP_IDS := ["gourdling", "scuttler", "thornback", "hollow_king"]
const BUILDER_IDS := ["lamplighter"]
const MODE_IDS := ["classic"]

const MAP_DIR := "res://data/"
const PLAN_DIR := "res://data/plans/"


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


## The tower a Builder places from slot 0, 1 or 2, or "" when the slot is empty.
static func kit_tower(builder: String, slot: int) -> String:
	var kit: Array = BUILDERS[builder]["towers"]
	return str(kit[slot]) if slot >= 0 and slot < kit.size() else ""


## A Builder's plan for the caretaker and the test bot: an Array of steps
## {"build": kind, "cell": [x, z]} and {"fork": "a" or "b", "cell": [x, z]}.
static func plan(builder: String) -> Array:
	var path := PLAN_DIR + str(BUILDERS[builder]["plan"]) + ".json"
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		return (parsed as Dictionary).get("steps", [])
	return []


## The same plan as integers for the caretaker: one [op, slot or branch, x, z] per step,
## op 0 to build from a kit slot and 1 to fork the tower on that cell. Unknown steps are dropped.
static func plan_steps(builder: String) -> Array:
	var kit: Array = BUILDERS[builder]["towers"]
	var steps := []
	for step: Variant in plan(builder):
		if not step is Dictionary:
			continue
		var entry: Dictionary = step
		var cell: Array = entry.get("cell", [])
		if cell.size() != 2:
			continue
		var x := int(cell[0])
		var z := int(cell[1])
		if entry.has("build") and kit.has(str(entry["build"])):
			steps.append(PackedInt32Array([0, kit.find(str(entry["build"])), x, z]))
		elif entry.has("fork"):
			steps.append(PackedInt32Array([1, 0 if str(entry["fork"]) == "a" else 1, x, z]))
	return steps


## The first 8 bytes of SHA-256 over every table that changes the rules, the plans and
## the map: the matchmaking key (design 6.9). JSON with sorted keys is the canonical dump.
static func rules_hash(mode: String) -> PackedByteArray:
	var preset: Dictionary = RULES[mode]
	var plans := []
	for builder: String in BUILDER_IDS:
		plans.append(plan(builder))
	var dump := JSON.stringify(
		[SIM_VERSION, mode, RULES, TOWERS, CREEPS, WAVES, BUILDERS, plans, map_text(preset["map"])],
		"",
		true
	)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(dump.to_utf8_buffer())
	return ctx.finish().slice(0, 8)
