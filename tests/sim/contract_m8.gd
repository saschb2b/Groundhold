## The M8 contract (docs/design/contract-m8.md) as checks a scenario runs: the levels are
## append-only ids that agree with the wire, Normal lays nothing over a preset, NO_STACK is
## refusal 16 and M8 adds no event number, protocol.json says which modes take a level and
## changes no layout while it is still version 1, and, as each track writes its part, the
## presets' stacking and level keys (agreeing with the wire), the DIFFICULTIES table, the
## plans' `stack` lists, the caretaker's version, the rules hash's reach and the protocol's
## version-2 layouts (contract §1, §3 and §5).
##   {"eval": "resource('res://tests/sim/contract_m8.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

const M2M3 := preload("res://tests/sim/contract_m2m3.gd")

const DIFFICULTY_IDS := ["normal", "hard", "very_hard"]
## Which modes take a level (§1): protocol.json's `levels`, and RULES' once the rules track
## adds the key. A mode not named here is a later milestone's.
const LEVELS := {"classic": false, "high_water": true, "tide_race": true, "undertow": false}
## The modes that stack (§1's table: `stack_max` 3, *tunable*, and a `stake_pm`).
const STACKING := ["high_water", "tide_race"]
## What a level lays over a preset (§3): lives replaced, the rest added.
const LEVEL_KEYS := ["lives", "hp_pm", "boss_hp_pm", "boss_armor_c"]
## Normal's numbers, the base a harder level is held against.
const NORMAL := {"hp_pm": 1000, "boss_hp_pm": 1000, "boss_armor_c": 0}
const NO_STACK := 16
## M7's last event number: M8 adds none (§1).
const LAST_EVENT := 27
## The caretaker's version before M8, and the one that stacks (§1).
const M7_CARETAKER := 4
const M8_CARETAKER := 5
## A plan's stack list names waves 2 to 12 (§1).
const STACK_WAVES := [2, 12]
## The commands, which M8 leaves as they are (§5).
const COMMANDS := {"BUILD": 1, "FORK": 2, "SELL": 3, "READY": 4, "SIGNAL": 5, "CORK": 6, "UNCORK": 7, "SEAWALL": 8}
const SYSTEM_COMMANDS := {"AWAY": 64, "BACK": 65, "LEFT": 66, "TIMEOUT": 67}
## The messages §5 keeps unchanged: none ever carries the level.
const UNCHANGED := ["HELLO", "LOADED", "MATCH_FOUND", "QUEUE", "QUEUE_STATE", "ACCEPT", "RESULT", "MATCH_END"]
## Track C's layouts (§5): the PARTY op and the two messages that carry the level after `mode`.
const PARTY_OP := 12
const LEVEL_FIELD := ["difficulty", "u8"]
const CARRIERS := ["PARTY_STATE", "MATCH_CONFIG"]


## Every way the code breaks the contract, as readable lines; [] when it keeps it.
static func problems() -> Array:
	var out := []
	_ids(out)
	_levels(out)
	_types(out)
	_wire(out)
	_layouts(out)
	_presets(out)
	_plans(out)
	_hash(out)
	return out


static func _ids(out: Array) -> void:
	if SimContent.DIFFICULTY_IDS.slice(0, DIFFICULTY_IDS.size()) != DIFFICULTY_IDS:
		out.append("DIFFICULTY_IDS does not begin %s" % [DIFFICULTY_IDS])
	var wire: Dictionary = NetProtocol.spec().get("difficulties", {})
	for i in SimContent.DIFFICULTY_IDS.size():
		var level: String = SimContent.DIFFICULTY_IDS[i]
		if int(wire.get(level, -1)) != i:
			out.append("level %s is index %d in DIFFICULTY_IDS but not id %d in protocol.json's difficulties" % [level, i, i])
	for level: String in wire:
		if not SimContent.DIFFICULTY_IDS.has(level):
			out.append("protocol.json's difficulties has %s, which DIFFICULTY_IDS lacks" % level)


## The DIFFICULTIES table: Normal is {} from day 0; each harder level, once the rules track
## adds it, lays exactly §3's keys, each an int, and is harder than the level before it in
## every one: fewer lives, more creep and boss health, no less boss armour.
static func _levels(out: Array) -> void:
	var table: Dictionary = SimContent.DIFFICULTIES
	if not table.has("normal") or not (table["normal"] as Dictionary).is_empty():
		out.append("DIFFICULTIES.normal is not {}")
	for level: String in table:
		if not SimContent.DIFFICULTY_IDS.has(level):
			out.append("DIFFICULTIES has %s, which is not a level" % level)
	var before := NORMAL.duplicate()
	before["lives"] = int(SimContent.RULES["high_water"]["lives"])
	for i in range(1, SimContent.DIFFICULTY_IDS.size()):
		var level: String = SimContent.DIFFICULTY_IDS[i]
		if not table.has(level):
			continue
		var keys: Dictionary = table[level]
		for key: String in keys:
			if not LEVEL_KEYS.has(key):
				out.append("DIFFICULTIES.%s lays %s, which is not a level's key" % [level, key])
		var whole := true
		for key: String in LEVEL_KEYS:
			if not keys.has(key) or typeof(keys[key]) != TYPE_INT:
				out.append("DIFFICULTIES.%s lacks %s as an int" % [level, key])
				whole = false
		if not whole:
			continue
		if int(keys["lives"]) < 1 or int(keys["lives"]) >= int(before["lives"]):
			out.append("DIFFICULTIES.%s's %d lives are not fewer than the level before's %d, and at least 1" % [level, keys["lives"], before["lives"]])
		for key: String in ["hp_pm", "boss_hp_pm"]:
			if int(keys[key]) <= int(before[key]):
				out.append("DIFFICULTIES.%s's %s %d is not above the level before's %d" % [level, key, keys[key], before[key]])
		if int(keys["boss_armor_c"]) < int(before["boss_armor_c"]):
			out.append("DIFFICULTIES.%s's boss armour is below the level before's" % level)
		before = keys.duplicate()


static func _types(out: Array) -> void:
	if SimTypes.REFUSE_NO_STACK != NO_STACK or SimTypes.REFUSAL_NAMES.find("NO_STACK") != NO_STACK:
		out.append("refusal NO_STACK is not %d" % NO_STACK)
	if SimTypes.refusal_name(NO_STACK) != "NO_STACK":
		out.append("refusal %d is not named NO_STACK" % NO_STACK)
	for name: String in SimTypes.EVENT_TYPES:
		if int(SimTypes.EVENT_TYPES[name]) > LAST_EVENT:
			out.append("EV_%s is %d: M8 adds no event number past %d" % [name, SimTypes.EVENT_TYPES[name], LAST_EVENT])
	for table: Array in [["commands", COMMANDS], ["system_commands", SYSTEM_COMMANDS]]:
		var wire: Dictionary = NetProtocol.spec()[table[0]]
		var want: Dictionary = table[1]
		if wire.size() != want.size():
			out.append("protocol.json's %s are not M7's %d" % [table[0], want.size()])
		for name: String in want:
			if int(wire.get(name, {}).get("type", -1)) != int(want[name]):
				out.append("command %s is not type %d on the wire" % [name, want[name]])
	var ready: Array = NetProtocol.spec()["commands"].get("READY", {}).get("args", [])
	if ready.size() != 3 or int(ready[0][0]) != 0 or int(ready[0][1]) != 1:
		out.append("READY's arguments changed on the wire: its new refusal is the simulation's")
	elif int(ready[1][0]) != 0 or int(ready[1][1]) < SimContent.WAVES.get("hollow12", []).size() + 3:
		# (M8's review: b names the wave a READY 1 calls, 0 none, up to a duel's Surge and past)
		out.append("READY's b cannot name every wave a Ready calls")


## protocol.json's numbered values and the modes' `levels` flags (§1, §5), from day 0.
static func _wire(out: Array) -> void:
	var modes: Dictionary = NetProtocol.spec()["modes"]
	for mode: String in LEVELS:
		var spec: Dictionary = modes.get(mode, {})
		if spec.is_empty():
			out.append("protocol.json's modes lack %s" % mode)
		elif bool(spec.get("levels", false)) != LEVELS[mode]:
			out.append("protocol.json's %s %s a level" % [mode, "does not take" if LEVELS[mode] else "takes"])
	for mode: String in modes:
		var levels: Variant = (modes[mode] as Dictionary).get("levels", false)
		if typeof(levels) != TYPE_BOOL:
			out.append("protocol.json's %s.levels is not true or false" % mode)


## Track C's change (§5): while protocol.json is version 1 no layout carries the level; at
## version 2 the PARTY op, PARTY_STATE and MATCH_CONFIG do, and nothing else changed.
static func _layouts(out: Array) -> void:
	var spec: Dictionary = NetProtocol.spec()
	var version := int(spec["version"])
	var messages: Dictionary = spec["messages"]
	var party: Dictionary = messages["PARTY"]
	var cases: Dictionary = party["switch"]["cases"]
	var changed := []
	if spec["party_ops"].has("difficulty") or cases.has("difficulty"):
		changed.append("PARTY")
	for name: String in CARRIERS:
		if _names_level(messages[name]["fields"]):
			changed.append(name)
	if str(spec["subprotocol"]) != "groundhold.v%d" % version:
		out.append("protocol.json's subprotocol is not groundhold.v%d" % version)
	if version < 2:
		if not changed.is_empty():
			out.append("protocol.json changes %s but is still version %d: a layout change is version 2" % [changed, version])
	else:
		if int(spec["party_ops"].get("difficulty", -1)) != PARTY_OP:
			out.append("PARTY op difficulty is not %d" % PARTY_OP)
		if cases.get("difficulty", []) != [LEVEL_FIELD]:
			out.append("PARTY difficulty is not [%s]" % [LEVEL_FIELD])
		for name: String in CARRIERS:
			var fields: Array = messages[name]["fields"]
			var at := -1
			for i in fields.size():
				if str(fields[i][0]) == "mode":
					at = i
			if at < 0 or at + 1 >= fields.size() or fields[at + 1] != LEVEL_FIELD:
				out.append("%s does not carry %s right after mode" % [name, LEVEL_FIELD])
	if cases.get("create", []) != [["mode", "u8"]]:
		out.append("PARTY create is no longer [mode u8]: a new party's level follows it as its own op")
	for name: String in UNCHANGED:
		var message: Dictionary = messages.get(name, {})
		var lists: Array = [message.get("fields", [])]
		if message.has("switch"):
			lists.append_array((message["switch"]["cases"] as Dictionary).values())
		for fields: Array in lists:
			if _names_level(fields):
				out.append("%s carries the level, which the M8 contract keeps out of it" % name)


static func _names_level(fields: Array) -> bool:
	for field: Array in fields:
		if str(field[0]) == "difficulty":
			return true
	return false


## The presets' M8 keys (§1's table), each column once the rules track adds it to any
## preset: `stack_max` 2 or more where a mode stacks, 1 or absent in undertow, never in
## classic; `stake_pm` only where a mode stacks; `levels` true where protocol.json says so
## and nowhere else. No preset carries a level's own keys.
static func _presets(out: Array) -> void:
	var rules: Dictionary = SimContent.RULES
	for mode: String in rules:
		for key: String in ["hp_pm", "boss_hp_pm", "boss_armor_c"]:
			if (rules[mode] as Dictionary).has(key):
				out.append("RULES.%s carries %s, which only a level lays over it" % [mode, key])
	if _any_has(rules, "stack_max"):
		for mode: String in rules:
			var r: Dictionary = rules[mode]
			var value: Variant = r.get("stack_max", 1)
			if typeof(value) != TYPE_INT:
				out.append("RULES.%s.stack_max is not an int" % mode)
			elif STACKING.has(mode) and int(value) < 2:
				out.append("RULES.%s does not stack (stack_max %d)" % [mode, value])
			elif not STACKING.has(mode) and int(value) != 1:
				out.append("RULES.%s stacks (stack_max %d), which the contract keeps at 1" % [mode, value])
		if _has(rules, "classic", "stack_max"):
			out.append("RULES.classic carries stack_max: M1's game stays untouched")
	if _any_has(rules, "stake_pm"):
		for mode: String in rules:
			var r: Dictionary = rules[mode]
			if STACKING.has(mode) and (typeof(r.get("stake_pm")) != TYPE_INT or int(r.get("stake_pm", 0)) <= 0):
				out.append("RULES.%s lacks a stake_pm above 0" % mode)
			elif not STACKING.has(mode) and r.has("stake_pm"):
				out.append("RULES.%s carries stake_pm, but never stacks" % mode)
	if _any_has(rules, "levels"):
		var modes: Dictionary = NetProtocol.spec()["modes"]
		for mode: String in rules:
			var r: Dictionary = rules[mode]
			var wire := bool((modes.get(mode, {}) as Dictionary).get("levels", false))
			if r.has("levels") and typeof(r["levels"]) != TYPE_BOOL:
				out.append("RULES.%s.levels is not true or false" % mode)
			elif bool(r.get("levels", false)) != wire:
				out.append("RULES.%s.levels is %s, protocol.json's %s" % [mode, r.get("levels", false), wire])
			if LEVELS.has(mode) and not LEVELS[mode] and r.has("levels"):
				out.append("RULES.%s carries levels, which the contract leaves absent" % mode)


static func _any_has(rules: Dictionary, key: String) -> bool:
	for mode: String in rules:
		if (rules[mode] as Dictionary).has(key):
			return true
	return false


static func _has(rules: Dictionary, mode: String, key: String) -> bool:
	return rules.has(mode) and (rules[mode] as Dictionary).has(key)


## The plans' `stack` lists (§1), once the rules track writes them: every Builder's plan
## has one at its top level, each a list of distinct waves 2 to 12, none called during a
## boss's wave; a mode block holds its own only for a mode that stacks; and the caretaker
## that plays them is version 5.
static func _plans(out: Array) -> void:
	var stacked := 0
	var plans := 0
	for builder: String in SimContent.BUILDER_IDS:
		var path := SimContent.PLAN_DIR + str(SimContent.BUILDERS[builder]["plan"]) + ".json"
		if not FileAccess.file_exists(path):
			continue
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if not parsed is Dictionary:
			out.append("%s is not a JSON object" % path)
			continue
		var file: Dictionary = parsed
		plans += 1
		if file.has("stack"):
			stacked += 1
			_stack_list(out, path, "", file["stack"], _boss_waves("high_water"))
		for mode: String in file:
			if not SimContent.MODE_IDS.has(mode) or not file[mode] is Dictionary:
				continue
			var block: Dictionary = file[mode]
			if not block.has("stack"):
				continue
			if not SimContent.RULES.has(mode) or int(SimContent.RULES[mode].get("stack_max", 1)) < 2:
				out.append("%s's %s block stacks, but %s never does" % [path, mode, mode])
			else:
				_stack_list(out, path, mode, block["stack"], _boss_waves(mode))
	if stacked > 0 and stacked < plans:
		out.append("only %d of %d plans have a top-level stack list" % [stacked, plans])
	if SimContent.CARETAKER_VERSION < M7_CARETAKER:
		out.append("CARETAKER_VERSION %d is below M7's %d" % [SimContent.CARETAKER_VERSION, M7_CARETAKER])
	if stacked > 0 and SimContent.CARETAKER_VERSION < M8_CARETAKER:
		out.append("the plans stack, but CARETAKER_VERSION is %d, not %d" % [SimContent.CARETAKER_VERSION, M8_CARETAKER])


static func _stack_list(out: Array, path: String, mode: String, list: Variant, bosses: Array) -> void:
	var where := path + (" (%s)" % mode if mode != "" else "")
	if not list is Array:
		out.append("%s's stack is not a list" % where)
		return
	var seen := []
	for value: Variant in list:
		if (typeof(value) != TYPE_FLOAT and typeof(value) != TYPE_INT) or float(value) != floorf(float(value)):
			out.append("%s's stack names %s, which is not a wave" % [where, value])
			continue
		var wave := int(value)
		if wave < STACK_WAVES[0] or wave > STACK_WAVES[1]:
			out.append("%s's stack names wave %d, outside %d to %d" % [where, wave, STACK_WAVES[0], STACK_WAVES[1]])
		if seen.has(wave):
			out.append("%s's stack names wave %d twice" % [where, wave])
		seen.append(wave)
		if bosses.has(wave - 1):
			out.append("%s's stack calls wave %d behind wave %d's boss" % [where, wave, wave - 1])


## The waves (1-based) of a mode's list that send a boss.
static func _boss_waves(mode: String) -> Array:
	var out := []
	var waves: Array = SimContent.WAVES.get(str(SimContent.RULES.get(mode, {}).get("waves", "")), [])
	for i in waves.size():
		for group: Dictionary in waves[i]:
			if bool(SimContent.CREEPS.get(str(group["creep"]), {}).get("boss", false)):
				out.append(i + 1)
				break
	return out


## The rules hash covers DIFFICULTIES and every plan's stack list (§1), once there is more
## than Normal's {} to cover and once a plan stacks: rules_hash() or a helper it calls reads
## them.
static func _hash(out: Array) -> void:
	var reach := _hash_reach()
	if SimContent.DIFFICULTIES.size() > 1 and not reach.contains("DIFFICULTIES"):
		out.append("the rules hash does not cover DIFFICULTIES")
	var stacks := false
	for builder: String in SimContent.BUILDER_IDS:
		var path := SimContent.PLAN_DIR + str(SimContent.BUILDERS[builder]["plan"]) + ".json"
		if FileAccess.file_exists(path) and FileAccess.get_file_as_string(path).contains('"stack"'):
			stacks = true
	if stacks and not reach.contains('"stack"'):
		out.append("the rules hash reads no plan's stack list")
	# (the review's READY that names its wave: builds that take a late Ready otherwise never meet)
	if SimContent.ORDERS_VERSION < 2 or not reach.contains("ORDERS_VERSION"):
		out.append("the rules hash does not cover ORDERS_VERSION 2 (a READY 1 taken only for the wave it names)")


## rules_hash()'s code and that of every content.gd helper it reaches, without comments.
static func _hash_reach() -> String:
	var bodies: Dictionary = M2M3._helper_bodies(M2M3._code(FileAccess.get_file_as_string("res://scripts/sim/content.gd")))
	var call := RegEx.create_from_string("(?<![\\w.])(\\w+)\\(")
	var todo := ["rules_hash"]
	var seen := []
	var text := ""
	while not todo.is_empty():
		var name: String = todo.pop_back()
		if seen.has(name) or not bodies.has(name):
			continue
		seen.append(name)
		text += str(bodies[name])
		for m: RegExMatch in call.search_all(str(bodies[name])):
			todo.append(m.get_string(1))
	return text
