## The M7 contract (docs/design/contract-m7.md) as checks a scenario runs: undertow is the
## mode after tide_race and its wire id, the Drift's packs are the four checks with the
## hollow's creeps and counts, the duel's events and refusals have their numbers, the
## commitment's bytes are the contract's (once track A writes SimUndertow.commit), and the
## undertow preset, once track A adds it, is the contract's.
##   {"eval": "resource('res://tests/sim/contract_m7.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

const PACK_COUNTS := {
	"swarm": ["gourdling", [6, 14, 20]],
	"swift": ["scuttler", [8, 17, 28]],
	"armored": ["thornback", [3, 5, 9]],
	"winged": ["duskmoth", [4, 5, 7]],
}
const EVENTS := {"DRIFT": 21, "CORK": 22, "UNCORK": 23, "FIZZLE": 24, "BREACH": 25, "SEAWALL": 26, "SURGE": 27}
const REFUSALS := {
	"NO_CORKS_LEFT": 7, "TOO_EARLY": 8, "NOTHING_CORKED": 9, "BAD_REVEAL": 10, "NO_CHARGE": 11,
	"SEAWALL_STANDING": 12,
}


## Every way the code breaks the contract, as readable lines; [] when it keeps it.
static func problems() -> Array:
	var out := []
	_ids(out)
	_packs(out)
	_types(out)
	_commit(out)
	_preset(out)
	return out


static func _ids(out: Array) -> void:
	if SimContent.MODE_IDS.slice(3, 4) != ["undertow"]:
		out.append("MODE_IDS does not continue with undertow")
	var wire: Dictionary = NetProtocol.spec()["modes"].get("undertow", {})
	if int(wire.get("id", -1)) != SimContent.MODE_IDS.find("undertow"):
		out.append("undertow is not its wire id")
	var seats: Array = wire.get("seats", [])
	if int(wire.get("teams", 0)) != 2 or seats.size() != 2 or int(seats[0]) != 2 or int(seats[1]) != 2:
		out.append("protocol.json's undertow is not one seat on each of two teams")


static func _packs(out: Array) -> void:
	var packs: Dictionary = SimContent.PACKS.get("hollow", {})
	for check: String in SimContent.CHECK_IDS:
		var pack: Dictionary = packs.get(check, {})
		var want: Array = PACK_COUNTS[check]
		if str(pack.get("creep", "")) != want[0] or pack.get("counts", []) != want[1]:
			out.append("the hollow's %s pack is not %s %s" % [check, want[0], want[1]])
		if not SimContent.CREEPS.has(str(pack.get("creep", ""))):
			out.append("the hollow's %s pack sends a creep CREEPS lacks" % check)
	for check: String in packs:
		if not SimContent.CHECK_IDS.has(check):
			out.append("PACKS.hollow has %s, which is not a check" % check)


static func _types(out: Array) -> void:
	for name: String in EVENTS:
		if int(SimTypes.EVENT_TYPES.get(name, -1)) != EVENTS[name]:
			out.append("EV_%s is not %d" % [name, EVENTS[name]])
	for name: String in REFUSALS:
		if SimTypes.REFUSAL_NAMES.find(name) != REFUSALS[name]:
			out.append("refusal %s is not %d" % [name, REFUSALS[name]])
	var commands := {"CORK": 6, "UNCORK": 7, "SEAWALL": 8}
	for name: String in commands:
		if int(NetProtocol.spec()["commands"][name]["type"]) != commands[name]:
			out.append("command %s is not type %d on the wire" % [name, commands[name]])


## SimUndertow.commit, once track A writes it, against the contract's bytes computed here.
static func _commit(out: Array) -> void:
	var undertow: Variant = load("res://scripts/sim/sim_undertow.gd") if ResourceLoader.exists("res://scripts/sim/sim_undertow.gd") else null
	if undertow == null:
		return
	var cases := [[20261101, 1, 5, 2, 0x89ABCDEF, 0x01234567], [7, 2, 12, 0, 0, 0], [1, 1, 2, 3, 0xFFFFFFFF, 0x80000000]]
	for c: Array in cases:
		var want := _expected(int(c[0]), int(c[1]), int(c[2]), int(c[3]), int(c[4]), int(c[5]))
		var got: Array = undertow.commit(int(c[0]), int(c[1]), int(c[2]), int(c[3]), _signed(int(c[4])), _signed(int(c[5])))
		if got != want:
			out.append("SimUndertow.commit%s gives %s, not the contract's %s" % [c, got, want])


static func _expected(seed_value: int, seat: int, window: int, pack: int, salt_hi: int, salt_lo: int) -> Array:
	var bytes := PackedByteArray()
	for value: int in [seed_value]:
		bytes.append_array(_be32(value))
	bytes.append(seat & 0xFF)
	bytes.append(window & 0xFF)
	bytes.append(pack & 0xFF)
	bytes.append_array(_be32(salt_hi))
	bytes.append_array(_be32(salt_lo))
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	var digest := ctx.finish()
	var hi := (digest[0] << 24) | (digest[1] << 16) | (digest[2] << 8) | digest[3]
	var lo := (digest[4] << 24) | (digest[5] << 16) | (digest[6] << 8) | digest[7]
	return [_signed(hi), _signed(lo)]


static func _be32(value: int) -> PackedByteArray:
	var v := value & 0xFFFFFFFF
	return PackedByteArray([(v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF])


static func _signed(u32: int) -> int:
	var v := u32 & 0xFFFFFFFF
	return v - 0x100000000 if v >= 0x80000000 else v


## The undertow preset, once track A adds it (contract §2).
static func _preset(out: Array) -> void:
	var r: Dictionary = SimContent.RULES.get("undertow", {})
	if r.is_empty():
		return
	if int(r.get("teams", 0)) != 2 or r.get("seats", []) != [2, 2] or str(r.get("clock", "")) != "shared":
		out.append("RULES.undertow is not two teams of one with a shared clock")
	var duel: Dictionary = r.get("duel", {})
	for key: String in ["drift_from", "offered", "tiers", "corks", "corks_two_from", "uncork_after_t", "auto_uncork_t", "fizzle_t", "breach_pay", "send_hp_pm", "seawall", "surge"]:
		if not duel.has(key):
			out.append("RULES.undertow.duel lacks %s" % key)
	if int(duel.get("send_hp_pm", 1000)) < 1000:
		out.append("a sent creep is weaker than the wave's own (send_hp_pm under 1000)")
	# (the packs' matrix) a pack's own premium and spacing, keyed by the check it tests
	for key: String in ["pack_hp_pm", "pack_gap_t"]:
		var by_pack: Dictionary = duel.get(key, {})
		for check: String in by_pack:
			if not SimContent.CHECK_IDS.has(check):
				out.append("RULES.undertow.duel.%s names %s, which is not a check" % [key, check])
			elif key == "pack_hp_pm" and int(by_pack[check]) < 1000:
				out.append("a sent %s creep is weaker than the wave's own (pack_hp_pm under 1000)" % check)
			elif key == "pack_gap_t" and int(by_pack[check]) < 1:
				out.append("the %s pack's creeps would set out on one tick (pack_gap_t under 1)" % check)
	if int(duel.get("auto_uncork_t", 0)) >= int(duel.get("fizzle_t", 0)):
		out.append("the client's auto uncork does not come before the fizzle")
