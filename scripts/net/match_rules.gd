## The rules a match plays (contract-m8 §3): its mode and the level it is played at. Wherever
## a mode travels its level travels with it (MATCH_CONFIG's `difficulty`, the session's
## match_spec, the replay record, the desync dump), and this is where the two become
## SimMatch's rules, so every client of a match builds the same ones.
##
## The level a mode plays is protocol.json's rule (`levels` on the modes that take one), the
## one the server applies too; contract_m8_tables holds SimContent's presets to agree with it.
class_name MatchRules
extends RefCounted

const NORMAL := "normal"


## Whether `mode` takes a level (protocol.json's `levels`: High Water and Tide Race).
static func takes_level(mode: String) -> bool:
	var modes: Dictionary = NetProtocol.spec()["modes"]
	return modes.has(mode) and bool((modes[mode] as Dictionary).get("levels", false))


## The level a match of `mode` plays when `difficulty` is asked: that level where the mode
## takes one, else Normal (a duel, classic); an unknown level is Normal too.
static func level_of(mode: String, difficulty: String) -> String:
	if not takes_level(mode) or not known(difficulty):
		return NORMAL
	return difficulty


## Whether `difficulty` is one of protocol.json's levels.
static func known(difficulty: String) -> bool:
	return (NetProtocol.spec()["difficulties"] as Dictionary).has(difficulty)


## A level's wire id (protocol.json's `difficulties`), -1 for none.
static func level_id(difficulty: String) -> int:
	return NetProtocol.enum_value("difficulties", difficulty)


## The level a wire id names ("" for none).
static func level_name(wire: int) -> String:
	return NetProtocol.enum_name("difficulties", wire)


## SimMatch's rules for a match of `mode` at `difficulty` (the level it plays, level_of):
## SimContent.rules(mode, level), which lays the level's keys over the preset and names it
## under "difficulty" (contract-m8 §3; level_problem holds them to the table's numbers).
static func of(mode: String, difficulty := NORMAL) -> Dictionary:
	return SimContent.rules(mode, level_of(mode, difficulty))


## `preset` (a mode's rules) at `level`, as contract-m8 §3 lays a level over a preset: the
## keys `levels` (SimContent.DIFFICULTIES) gives the level, `lives` replaced and the others
## added, and the level named under "difficulty". `level` is the one the mode plays
## (level_of); a level the table has no keys for changes no number.
static func laid_over(preset: Dictionary, level: String, levels: Dictionary) -> Dictionary:
	var out := preset.duplicate(true)
	out.merge(levels.get(level, {}) as Dictionary, true)
	out["difficulty"] = level
	return out


## What differs between `rules` (a built match's) and its level by `levels`' numbers (by
## default SimContent.DIFFICULTIES, the rules track's table): "" when the level they name
## is the one their mode plays and every key any level lays (lives, creep and boss health,
## boss armour) has that level's value, the preset's where the level lays none; else each
## key that does not. A check on the numbers, not on the name alone: rules named Hard with
## Normal's lives say so.
static func level_problem(rules: Dictionary, levels: Dictionary = SimContent.DIFFICULTIES) -> String:
	var mode := str(rules.get("mode", ""))
	if not SimContent.RULES.has(mode):
		return "no mode the game plays (%s)" % mode
	var named := str(rules.get("difficulty", NORMAL))
	var want := laid_over(SimContent.rules(mode), level_of(mode, named), levels)
	var keys := ["difficulty"]
	for level: String in levels:
		for key: String in levels[level] as Dictionary:
			if not keys.has(key):
				keys.append(key)
	var wrong := []
	for key: String in keys:
		var have: Variant = rules.get(key)
		var should: Variant = want.get(key)
		if typeof(have) != typeof(should) or have != should:
			wrong.append("%s %s, not %s" % [key, have, should])
	return "" if wrong.is_empty() else "%s: %s" % [named, ", ".join(wrong)]


## The level a built match plays: its rules' "difficulty" (Normal for rules without one).
static func level_played(rules: Dictionary) -> String:
	var level := str(rules.get("difficulty", NORMAL))
	return level if known(level) else NORMAL

