## The M6 contract (docs/design/contract-m6.md) as checks a scenario runs: the id lists
## grew by exactly what the contract appends and still agree with the wire, the two new
## Builders and their kits are the contract's, every M6 tower key is one the contract
## names, the new event numbers and the queue's numbers are fixed, every new id has its
## display entry, a model not built yet loads as a stand-in, and once the rules track adds
## the tide_race preset it is the contract's.
##   {"eval": "resource('res://tests/sim/contract_m6.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

## What M6 appends, in order, after the M2/M3 contract's lists.
const TOWER_IDS := [
	"clapper_tower", "toll_tower", "chime_post",
	"great_clapper", "ringing_clapper", "great_toll", "sky_toll", "deep_chime", "long_chime",
	"clay_hive", "apiary", "hive_hum",
	"great_clay_hive", "drowsy_clay_hive", "royal_apiary", "queens_guard", "great_hum", "long_hum",
]
const BUILDER_IDS := ["bellfounder", "beekeeper"]
const MODE_IDS := ["tide_race"]
const PERK_IDS := ["bronze_hand", "hive_tithe"]
const M2_TOWERS := 18

## The kits (design 3.4): Builder -> [towers, covers, patches, perk id].
const KITS := {
	"bellfounder":
	[
		["clapper_tower", "toll_tower", "chime_post"],
		["swift", "armored"],
		{"swarm": ["ringing_clapper"], "winged": ["sky_toll"]},
		"bronze_hand",
	],
	"beekeeper":
	[
		["clay_hive", "apiary", "hive_hum"],
		["swarm", "winged"],
		{"swift": ["drowsy_clay_hive"], "armored": ["queens_guard"]},
		"hive_tithe",
	],
}
## Every key a tower or branch may carry: the M2/M3 contract's and M6's.
const TOWER_KEYS := [
	"id", "builder", "slot", "cost", "dmg_c", "cd_t", "range_mm", "air", "shot_um_t",
	"min_flight_t", "splash_mm", "slow_pm", "slow_t", "pierce_c", "aim", "bounces", "bounce_mm",
	"team", "mark_pm", "marks", "mark_t", "fork_cost", "a", "b",
	# M6
	"pulse", "stun_t", "stun_immune_t", "air_slow_pm", "air_slow_t", "cloud_mm", "crack_c",
	"haste_pm", "air_bonus_pm",
]
const TEAM_EFFECTS := ["slow", "mark", "stun", "crack", "haste"]


## Every way the code breaks the contract, as readable lines; [] when it keeps it.
static func problems() -> Array:
	var out := []
	_ids(out)
	_kits(out)
	_tower_keys(out)
	_types(out)
	_protocol(out)
	_display(out)
	_race(out)
	return out


static func _ids(out: Array) -> void:
	var towers := SimContent.TOWER_IDS
	if towers.size() < M2_TOWERS + TOWER_IDS.size() or towers.slice(M2_TOWERS, M2_TOWERS + TOWER_IDS.size()) != TOWER_IDS:
		out.append("TOWER_IDS does not continue with M6's %s" % [TOWER_IDS])
	if SimContent.BUILDER_IDS.slice(2, 4) != BUILDER_IDS:
		out.append("BUILDER_IDS does not continue with %s" % [BUILDER_IDS])
	if SimContent.MODE_IDS.slice(2, 3) != MODE_IDS:
		out.append("MODE_IDS does not continue with %s" % [MODE_IDS])
	if SimContent.PERK_IDS.slice(2, 4) != PERK_IDS:
		out.append("PERK_IDS does not continue with %s" % [PERK_IDS])
	var wire: Dictionary = NetProtocol.spec()
	for builder: String in BUILDER_IDS:
		if int(wire["builders"].get(builder, -1)) != SimContent.BUILDER_IDS.find(builder):
			out.append("Builder %s is not its wire id" % builder)
	for mode: String in MODE_IDS:
		if int(wire["modes"].get(mode, {}).get("id", -1)) != SimContent.MODE_IDS.find(mode):
			out.append("mode %s is not its wire id" % mode)


static func _kits(out: Array) -> void:
	for builder: String in KITS:
		var b: Dictionary = SimContent.BUILDERS.get(builder, {})
		var kit: Array = KITS[builder]
		if b.get("towers", []) != kit[0]:
			out.append("%s's towers are not %s" % [builder, kit[0]])
		if b.get("covers", []) != kit[1]:
			out.append("%s covers %s, not %s" % [builder, b.get("covers", []), kit[1]])
		if b.get("patches", {}) != kit[2]:
			out.append("%s's patches are not %s" % [builder, kit[2]])
		if str(b.get("perk", {}).get("id", "")) != kit[3]:
			out.append("%s's perk is not %s" % [builder, kit[3]])
		if str(b.get("plan", "")) != builder:
			out.append("%s's plan is not data/plans/%s.json" % [builder, builder])
		for tower: String in kit[0]:
			if str(SimContent.TOWERS.get(tower, {}).get("builder", "")) != builder:
				out.append("TOWERS.%s does not belong to %s" % [tower, builder])


static func _tower_keys(out: Array) -> void:
	for kind: String in SimContent.TOWERS:
		var t: Dictionary = SimContent.TOWERS[kind]
		for part: Dictionary in [t, t.get("a", {}), t.get("b", {})]:
			for key: String in part:
				if not TOWER_KEYS.has(key):
					out.append("TOWERS.%s carries %s, which no contract names" % [kind, key])
		if t.has("team") and not TEAM_EFFECTS.has(str(t["team"])):
			out.append("TOWERS.%s brings team %s" % [kind, t["team"]])
	var expect := {"toll_tower": "stun", "chime_post": "crack", "hive_hum": "haste"}
	for kind: String in expect:
		if str(SimContent.TOWERS.get(kind, {}).get("team", "")) != expect[kind]:
			out.append("TOWERS.%s does not bring team %s" % [kind, expect[kind]])
	if not bool(SimContent.TOWERS.get("toll_tower", {}).get("pulse", false)):
		out.append("the Toll Tower does not pulse")
	if int(SimContent.TOWERS.get("clay_hive", {}).get("cloud_mm", 0)) <= 0:
		out.append("the Clay Hive has no cloud")


static func _types(out: Array) -> void:
	if SimTypes.EV_PULSE != 19 or SimTypes.EVENT_TYPES.get("PULSE", -1) != 19:
		out.append("EV_PULSE is not 19")
	if SimTypes.EV_RACE != 20 or SimTypes.EVENT_TYPES.get("RACE", -1) != 20:
		out.append("EV_RACE is not 20")
	var effects := {"stun": 2, "crack": 4, "haste": 5}
	for name: String in effects:
		if SimTypes.effect(name) != effects[name]:
			out.append("effect %s is not %d" % [name, effects[name]])


static func _protocol(out: Array) -> void:
	if NetProtocol.number("accept_ms") != 15000:
		out.append("protocol.json's accept_ms is not 15000")
	if NetProtocol.number("caretaker_offer_ms") != 60000:
		out.append("protocol.json's caretaker_offer_ms is not 60000")
	var race: Dictionary = NetProtocol.spec()["modes"].get("tide_race", {})
	var seats: Array = race.get("seats", [])
	if int(race.get("teams", 0)) != 2 or seats.size() != 2 or int(seats[0]) != 2 or int(seats[1]) != 4:
		out.append("protocol.json's tide_race is not two teams of 2 to 4 seats")


static func _display(out: Array) -> void:
	for id: String in TOWER_IDS:
		var d: Dictionary = Game.TOWERS.get(id, {})
		if str(d.get("icon", "")) != Game.ICON_DIR + id + ".png":
			out.append("Game.TOWERS.%s.icon is not ui/icons/%s.png" % [id, id])
	for builder: String in BUILDER_IDS:
		var d: Dictionary = Game.BUILDERS.get(builder, {})
		for key: String in ["bust", "emblem"]:
			if str(d.get(key, "")) == "":
				out.append("Game.BUILDERS.%s lacks its %s" % [builder, key])
	for perk: String in PERK_IDS:
		if not Game.PERKS.has(perk):
			out.append("Game.PERKS lacks %s" % perk)
	var stand_in := Models.instance("res://models/never_built.glb")
	if stand_in == null or stand_in.name != "Placeholder":
		out.append("a model not built yet does not load as the placeholder")
	if stand_in:
		stand_in.free()


## The tide_race preset, once the rules track adds it (design 2.1, 1.3).
static func _race(out: Array) -> void:
	if not SimContent.RULES.has("tide_race"):
		return
	var r: Dictionary = SimContent.RULES.get("tide_race", {})
	if int(r.get("teams", 0)) != 2 or r.get("seats", []) != [2, 4]:
		out.append("RULES.tide_race is not two teams of 2 to 4 seats")
	if str(r.get("waves", "")) != "hollow12" or str(r.get("map", "")) != "hollow":
		out.append("RULES.tide_race does not play hollow12 on the hollow")
	if int(r.get("cap_t", 0)) != 72000:
		out.append("RULES.tide_race's cap is not 20 minutes (72000 ticks)")
	# (contract-m6 §4's 600 ticks a life, raised to 3600 in M8 by the owner's decision of
	# 2 November 2026, "Raise the cost of a life": design 1.3, content.gd)
	if int(r.get("race", {}).get("life_t", 0)) != 3600:
		out.append("RULES.tide_race does not cost 3600 ticks (a minute) a life")
