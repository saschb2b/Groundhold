## The M2/M3 contract (docs/design/contract-m2m3.md) as checks a scenario runs: the id
## lists start with what the contract fixed and agree with the wire, every BUILDERS entry
## has exactly the fixed fields and they hold together with TOWERS, every id has its
## display entry and icon path in Game, the rules hash leaves display fields out, and
## the new event and effect numbers are what the contract says.
##   {"eval": "resource('res://tests/sim/contract_m2m3.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

## What the contract fixed, in order. Later milestones append after these.
const TOWER_IDS := [
	"arrow", "cannon", "frost",
	"longbow_loft", "skyward_loft", "great_cannon", "iron_mortar", "deep_frost", "rime_spire",
	"perch_ballista", "hawk_roost", "owls_eye",
	"siege_perch", "pinning_ballista", "falcon_roost", "kestrel_flock", "owls_glare", "twin_gaze",
]
const CREEP_IDS := [
	"gourdling", "scuttler", "thornback", "hollowtide_crest", "duskmoth", "bristlesow"
]
const BUILDER_IDS := ["lamplighter", "lookout"]
const MODE_IDS := ["classic", "high_water"]
const CHECK_IDS := ["swarm", "swift", "armored", "winged"]
const ROLE_IDS := ["warden", "marksman", "breaker", "sweeper"]
const PERK_IDS := ["thrifty", "keen_sight"]
const BUILDER_FIELDS := [
	"name", "title", "home", "role", "difficulty", "covers", "patches", "towers", "branches",
	"perk", "plan", "glyph", "accent",
]
const GLYPH_PATHS := {
	"swarm": "res://ui/icons/check_swarm.png",
	"swift": "res://ui/icons/check_swift.png",
	"armored": "res://ui/icons/check_armored.png",
	"winged": "res://ui/icons/check_winged.png",
}
## The most a Builder's accent may be saturated (HSV), so it never reads as a seat colour.
const ACCENT_MAX_SATURATION := 0.35


## Every way the tables break the contract, as readable lines; [] when they keep it.
static func problems() -> Array:
	var out := []
	_ids(out)
	_wire(out)
	_builders(out)
	_towers(out)
	_creeps(out)
	_display(out)
	_hash(out)
	_helpers(out)
	_types(out)
	return out


static func _prefix(out: Array, name: String, have: Array, fixed: Array) -> void:
	if have.slice(0, fixed.size()) != fixed:
		out.append("%s does not start with the contract's %s (has %s)" % [name, fixed, have])


static func _ids(out: Array) -> void:
	_prefix(out, "TOWER_IDS", SimContent.TOWER_IDS, TOWER_IDS)
	_prefix(out, "CREEP_IDS", SimContent.CREEP_IDS, CREEP_IDS)
	_prefix(out, "BUILDER_IDS", SimContent.BUILDER_IDS, BUILDER_IDS)
	_prefix(out, "MODE_IDS", SimContent.MODE_IDS, MODE_IDS)
	_prefix(out, "CHECK_IDS", SimContent.CHECK_IDS, CHECK_IDS)
	_prefix(out, "ROLE_IDS", SimContent.ROLE_IDS, ROLE_IDS)
	_prefix(out, "PERK_IDS", SimContent.PERK_IDS, PERK_IDS)
	if SimContent.BUILDER_FIELDS != BUILDER_FIELDS:
		out.append("BUILDER_FIELDS changed: %s" % [SimContent.BUILDER_FIELDS])


## A mode's and a Builder's codec index is its id on the wire.
static func _wire(out: Array) -> void:
	var spec := NetProtocol.spec()
	for i in SimContent.MODE_IDS.size():
		var mode: String = SimContent.MODE_IDS[i]
		var modes: Dictionary = spec["modes"]
		if not modes.has(mode) or int(modes[mode]["id"]) != i:
			out.append("mode %s is index %d in MODE_IDS but not id %d on the wire" % [mode, i, i])
	for i in SimContent.BUILDER_IDS.size():
		var builder: String = SimContent.BUILDER_IDS[i]
		var builders: Dictionary = spec["builders"]
		if not builders.has(builder) or int(builders[builder]) != i:
			out.append("Builder %s is index %d in BUILDER_IDS but not id %d on the wire" % [builder, i, i])


static func _builders(out: Array) -> void:
	for builder: String in SimContent.BUILDERS:
		if not SimContent.BUILDER_IDS.has(builder):
			out.append("BUILDERS has %s, which BUILDER_IDS does not list" % builder)
	for builder: String in SimContent.BUILDER_IDS:
		if not SimContent.BUILDERS.has(builder):
			out.append("BUILDER_IDS lists %s without a BUILDERS entry" % builder)
			continue
		var b: Dictionary = SimContent.BUILDERS[builder]
		var where := "BUILDERS.%s" % builder
		if b.size() != BUILDER_FIELDS.size():
			out.append("%s has %d fields, the contract %d" % [where, b.size(), BUILDER_FIELDS.size()])
		for field: String in BUILDER_FIELDS:
			if not b.has(field):
				out.append("%s lacks %s" % [where, field])
		if not b.has_all(BUILDER_FIELDS):
			continue
		for field: String in ["name", "title", "home", "plan", "glyph"]:
			if not b[field] is String or str(b[field]) == "":
				out.append("%s.%s is not a name" % [where, field])
		if not SimContent.ROLE_IDS.has(b["role"]):
			out.append("%s.role %s is not a ROLE_IDS id" % [where, b["role"]])
		if not b["difficulty"] is int or int(b["difficulty"]) < 1 or int(b["difficulty"]) > 3:
			out.append("%s.difficulty is not 1 to 3" % where)
		var covers: Array = b["covers"]
		var ordered := SimContent.CHECK_IDS.filter(func(c: String) -> bool: return covers.has(c))
		if covers != ordered or covers.is_empty():
			out.append("%s.covers %s are not CHECK_IDS in their order" % [where, covers])
		var towers: Array = b["towers"]
		var branches: Array = b["branches"]
		if towers.size() != 3 or branches.size() != 3:
			out.append("%s has %d towers and %d branch pairs, not 3 and 3" % [where, towers.size(), branches.size()])
			continue
		var kit_branches := []
		for slot in 3:
			var kind := str(towers[slot])
			if not SimContent.TOWERS.has(kind):
				out.append("%s.towers[%d] %s is not a TOWERS base" % [where, slot, kind])
				continue
			var t: Dictionary = SimContent.TOWERS[kind]
			if str(t["builder"]) != builder or int(t["slot"]) != slot:
				out.append("TOWERS.%s says builder %s slot %d, the kit %s slot %d" % [kind, t["builder"], t["slot"], builder, slot])
			var pair := [str(t["a"]["id"]), str(t["b"]["id"])] if t.has("a") and t.has("b") else []
			if branches[slot] != pair:
				out.append("%s.branches[%d] %s are not TOWERS.%s's a and b %s" % [where, slot, branches[slot], kind, pair])
			kit_branches.append_array(pair)
			if SimContent.kit_tower(builder, slot) != kind:
				out.append("kit_tower(%s, %d) is not %s" % [builder, slot, kind])
		var patches: Dictionary = b["patches"]
		for check: String in patches:
			if not SimContent.CHECK_IDS.has(check) or covers.has(check):
				out.append("%s.patches names %s, not one of its weak checks" % [where, check])
			for branch: Variant in patches[check]:
				if not kit_branches.has(branch):
					out.append("%s.patches.%s names %s, not a branch of its kit" % [where, check, branch])
		var perk: Dictionary = b["perk"]
		if not SimContent.PERK_IDS.has(perk.get("id", "")) or perk.size() < 2:
			out.append("%s.perk %s is not a PERK_IDS id with its numbers" % [where, perk])
		var accent: Variant = b["accent"]
		if not accent is int or int(accent) < 0 or int(accent) > 0xFFFFFF:
			out.append("%s.accent is not 0xRRGGBB" % where)
		elif Color.hex((int(accent) << 8) | 0xFF).s > ACCENT_MAX_SATURATION:
			out.append("%s.accent is saturated like a seat colour" % where)


## Every TOWER_IDS id is a base or exactly one base's branch, and every id TOWERS names
## is listed.
static func _towers(out: Array) -> void:
	var named := {}
	for kind: String in SimContent.TOWERS:
		named[kind] = named.get(kind, 0) + 1
		var t: Dictionary = SimContent.TOWERS[kind]
		for key: String in ["a", "b"]:
			if not t.has(key):
				out.append("TOWERS.%s has no branch %s" % [kind, key])
				continue
			var id := str(t[key]["id"])
			named[id] = named.get(id, 0) + 1
			var branch := 0 if key == "a" else 1
			if SimContent.tower_form(kind, branch) != id:
				out.append("tower_form(%s, %d) is not %s" % [kind, branch, id])
		if SimContent.tower_form(kind, -1) != kind:
			out.append("tower_form(%s, -1) is not %s" % [kind, kind])
		for key: String in ["builder", "slot", "cost", "dmg_c", "cd_t", "range_mm", "air", "shot_um_t", "fork_cost"]:
			if not t.has(key):
				out.append("TOWERS.%s lacks %s" % [kind, key])
		if t.has("team") and SimTypes.effect(str(t["team"])) == 0:
			out.append("TOWERS.%s.team %s is not an effect" % [kind, t["team"]])
	for id: String in named:
		if int(named[id]) != 1:
			out.append("tower id %s is named %d times" % [id, named[id]])
		if not SimContent.TOWER_IDS.has(id):
			out.append("TOWERS names %s, which TOWER_IDS does not list" % id)
	for id: String in SimContent.TOWER_IDS:
		if not named.has(id):
			out.append("TOWER_IDS lists %s, which no tower or branch is" % id)


static func _creeps(out: Array) -> void:
	for id: String in SimContent.CREEP_IDS:
		if not SimContent.CREEPS.has(id):
			out.append("CREEP_IDS lists %s without a CREEPS entry" % id)
	for id: String in SimContent.CREEPS:
		if not SimContent.CREEP_IDS.has(id):
			out.append("CREEPS has %s, which CREEP_IDS does not list" % id)
	if not bool(SimContent.CREEPS.get("duskmoth", {}).get("winged", false)):
		out.append("the Duskmoth is not winged")
	if not bool(SimContent.CREEPS.get("bristlesow", {}).get("boss", false)):
		out.append("the Bristlesow is not a boss")


## Every id has its display entry, and every icon path loads (as the placeholder while
## its art is not painted).
static func _display(out: Array) -> void:
	for id: String in SimContent.TOWER_IDS:
		var d: Dictionary = Game.TOWERS.get(id, {})
		if str(d.get("name", "")) == "" or not str(d.get("icon", "")).begins_with(Game.ICON_DIR):
			out.append("Game.TOWERS.%s lacks a name or an icon in ui/icons" % id)
	for check: String in SimContent.CHECK_IDS:
		var d: Dictionary = Game.CHECKS.get(check, {})
		if str(d.get("name", "")) == "" or str(d.get("glyph", "")) == "":
			out.append("Game.CHECKS.%s lacks a name or a glyph" % check)
		if str(d.get("icon", "")) != str(GLYPH_PATHS.get(check, "?")):
			out.append("Game.CHECKS.%s.icon is not %s" % [check, GLYPH_PATHS.get(check, "?")])
	for role: String in SimContent.ROLE_IDS:
		var d: Dictionary = Game.ROLES.get(role, {})
		if str(d.get("name", "")) == "" or str(d.get("icon", "")) != Game.ICON_DIR + "role_%s.png" % role:
			out.append("Game.ROLES.%s lacks a name or ui/icons/role_%s.png" % [role, role])
	for builder: String in SimContent.BUILDER_IDS:
		var d: Dictionary = Game.BUILDERS.get(builder, {})
		var glyph: String = Game.ICON_DIR + str(SimContent.BUILDERS[builder]["glyph"]) + ".png"
		if str(d.get("glyph", "")) != glyph:
			out.append("Game.BUILDERS.%s.glyph is not %s" % [builder, glyph])
		if str(d.get("portrait", "")) != "res://models/builders/%s.glb" % builder:
			out.append("Game.BUILDERS.%s.portrait is not models/builders/%s.glb" % [builder, builder])
	for perk: String in SimContent.PERK_IDS:
		var d: Dictionary = Game.PERKS.get(perk, {})
		if str(d.get("name", "")) == "" or str(d.get("text", "")) == "":
			out.append("Game.PERKS.%s lacks a name or a line" % perk)
	if Game.CARD_KEYS != ["Q", "W", "E", "A", "S", "D"]:
		out.append("the card keys are not Q W E / A S D: %s" % [Game.CARD_KEYS])
	var paths := []
	for table: Dictionary in [Game.TOWERS, Game.CHECKS, Game.ROLES, Game.BUILDERS]:
		for id: String in table:
			for key: String in ["icon", "glyph"]:
				if table[id].has(key):
					paths.append(str(table[id][key]))
	for path: String in paths:
		if not Game.icon(path) is Texture2D:
			out.append("Game.icon(%s) gave no texture" % path)
	if Game.icon("res://ui/icons/arrow_tower.png") == Game.placeholder_icon():
		out.append("a painted icon loaded as the placeholder")
	if Game.icon("res://ui/icons/never_painted.png") != Game.placeholder_icon():
		out.append("a missing icon did not load as the placeholder")


## The rules hash leaves out what only labels or shows a Builder, and keeps its kit.
static func _hash(out: Array) -> void:
	var dump := JSON.stringify(SimContent.hashed_builders(), "", true)
	for builder: String in SimContent.BUILDER_IDS:
		var b: Dictionary = SimContent.BUILDERS[builder]
		for key: String in SimContent.BUILDER_DISPLAY_KEYS:
			if dump.contains('"%s"' % key):
				out.append("the rules hash still reads BUILDERS' %s" % key)
		for text: String in [str(b["name"]), str(b["home"])]:
			if dump.contains(text):
				out.append("the rules hash still reads %s" % text)
	for key: String in ["covers", "towers", "branches", "perk", "plan"]:
		if not dump.contains('"%s"' % key):
			out.append("the rules hash lost BUILDERS' %s" % key)
	if SimContent.rules_hash().size() != 8:
		out.append("rules_hash() is not 8 bytes")
	for key: String in sim_reads_of_builders():
		if SimContent.BUILDER_DISPLAY_KEYS.has(key):
			out.append("the simulation reads BUILDERS' %s, which the rules hash leaves out" % key)
	if not sim_reads_of_builders().has("covers"):
		out.append("the caretaker's read of BUILDERS' covers went unseen")


## The BUILDERS fields the simulation reads: those its files index directly, and those
## any SimContent helper it calls reads, following helper to helper. Comments are left
## out, so a field a comment names is not a read.
static func sim_reads_of_builders() -> Array:
	var dir := "res://scripts/sim/"
	var bodies := _helper_bodies(_code(FileAccess.get_file_as_string(dir + "content.gd")))
	var todo := []
	var reads := []
	for file: String in DirAccess.get_files_at(dir):
		if not file.ends_with(".gd") or file == "content.gd":
			continue
		var text := _code(FileAccess.get_file_as_string(dir + file))
		_builder_reads(text, reads)
		for name: String in bodies:
			if text.contains("SimContent.%s(" % name):
				todo.append(name)
	var seen := []
	var call := RegEx.create_from_string("(?<![\\w.])(\\w+)\\(")
	while not todo.is_empty():
		var name: String = todo.pop_back()
		if seen.has(name):
			continue
		seen.append(name)
		_builder_reads(bodies[name], reads)
		for m: RegExMatch in call.search_all(bodies[name]):
			if bodies.has(m.get_string(1)):
				todo.append(m.get_string(1))
	return reads


## content.gd's static helpers by name: each one's text up to the next top-level line.
static func _helper_bodies(text: String) -> Dictionary:
	var out := {}
	var name := ""
	for line: String in text.split("\n"):
		if line.begins_with("static func "):
			name = line.trim_prefix("static func ").get_slice("(", 0)
			out[name] = ""
		elif not line.begins_with("\t") and not line.strip_edges().is_empty():
			name = ""
		if name != "":
			out[name] += line + "\n"
	return out


static func _builder_reads(text: String, reads: Array) -> void:
	var field := RegEx.create_from_string("BUILDERS\\[[^\\]]+\\]\\[\"(\\w+)\"\\]")
	for m: RegExMatch in field.search_all(text):
		if not reads.has(m.get_string(1)):
			reads.append(m.get_string(1))


## GDScript without its comments (a whole-line or a trailing #).
static func _code(text: String) -> String:
	var out := PackedStringArray()
	for line: String in text.split("\n"):
		var cut := line.find("#")
		out.append(line if cut < 0 else line.left(cut))
	return "\n".join(out)


static func _helpers(out: Array) -> void:
	var pairs := [
		[SimContent.team_covers(["lamplighter", "lookout"]), CHECK_IDS],
		[SimContent.team_covers(["lamplighter", "lamplighter"]), ["swarm", "swift"]],
		[SimContent.team_covers(["lookout"]), ["armored", "winged"]],
		[SimContent.team_covers([]), []],
		[SimContent.branch_helps("lamplighter", "iron_mortar"), "armored"],
		[SimContent.branch_helps("lamplighter", "rime_spire"), "winged"],
		[SimContent.branch_helps("lamplighter", "longbow_loft"), ""],
		[SimContent.branch_helps("lookout", "kestrel_flock"), "swarm"],
		[SimContent.branch_helps("lookout", "pinning_ballista"), "swift"],
		[SimContent.covers("lookout", "winged"), true],
		[SimContent.covers("lamplighter", "winged"), false],
	]
	for i in pairs.size():
		if pairs[i][0] != pairs[i][1]:
			out.append("helper check %d gave %s, not %s" % [i, pairs[i][0], pairs[i][1]])


static func _types(out: Array) -> void:
	var fixed := [
		[SimTypes.EV_REJECTED, 16], [SimTypes.EV_STATUS, 17], [SimTypes.EV_HELP, 18],
		[SimTypes.event_type("STATUS"), 17], [SimTypes.event_type("HELP"), 18],
		[SimTypes.REFUSE_CARETAKEN, 15], [SimTypes.refusal_name(15), "CARETAKEN"],
		[SimTypes.EFFECT_SLOW, 1], [SimTypes.EFFECT_STUN, 2], [SimTypes.EFFECT_MARK, 3],
		[SimTypes.EFFECT_CRACK, 4], [SimTypes.EFFECT_HASTE, 5],
		[SimTypes.effect("mark"), SimTypes.EFFECT_MARK], [SimTypes.effect("slow"), SimTypes.EFFECT_SLOW],
		[SimTypes.effect("nothing"), 0], [SimTypes.effect_name(SimTypes.EFFECT_HASTE), "haste"],
	]
	for pair: Array in fixed:
		if pair[0] != pair[1]:
			out.append("a SimTypes number is %s, the contract says %s" % [pair[0], pair[1]])
