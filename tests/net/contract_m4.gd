## The M4 contract (docs/design/contract-m4.md) as checks a scenario runs: what
## protocol.json appended for resilience, as the GDScript codec reads it; the seat states
## and the checkpoint interval in SimTypes; the shared rules the client's seams implement
## now (a checkpoint tick, a checkpoint's digest and parts, a dump's path), the same as
## protocol.py's (server/tests/test_contract_m4.py checks the same digests); and the
## seams' signatures, inert on desktop.
##   {"eval": "resource('res://tests/net/contract_m4.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
@warning_ignore_start("integer_division")
extends RefCounted

const NUMBERS := {
	"checkpoint_ticks": 1800, "checkpoints_kept": 2, "max_checkpoint_parts": 64,
	"checkpoint_wait_ms": 5000, "catchup_bytes": 2048, "catchup_ms": 50,
	"catchup_output": 4096, "max_resyncs": 1, "reconnect_ms": 2000,
}
const VALUES := {
	"config_flags": {"rejoin": 1},
	"visibility_states": {"shown": 0, "hidden": 1, "catching_up": 2},
	"resync_reasons": {"rejoin": 0, "desync": 1, "behind": 2},
}
## Message ids M1 to M3 fixed, which M4 keeps.
const IDS := {
	"HELLO": 1, "MATCH_CONFIG": 30, "HASH": 42, "CHECKPOINT_ASK": 43, "CHECKPOINT_PART": 44,
	"RESYNC": 45, "TURN_REQUEST": 46, "VISIBILITY": 47, "MATCH_END": 49, "LINKS": 52,
}
## SHA-256's first 8 bytes, as protocol.py's digest() gives them.
const DIGESTS := {"": "e3b0c44298fc1c14", "Groundhold": "948c7975fbd6b867"}
## Each seam's methods and how many arguments each takes.
const SEAMS := {
	"res://scripts/net/checkpointing.gd": {
		"is_checkpoint_tick": 3, "waves_of": 1, "digest": 1, "split": 2, "at_hash_tick": 2,
		"has_tick": 1, "bytes_at": 1, "upload": 1, "begin_download": 3, "add_part": 1,
		"download_done": 0, "downloaded": 0,
	},
	"res://scripts/net/desync_dump.gd": {"path_for": 2, "write": 3, "read": 1},
	"res://scripts/net/web_bridge.gd": {
		"is_web": 0, "start": 0, "stop": 0, "flash_title": 1, "stop_flash": 0, "poll": 1,
		"query": 1,
	},
	"res://scripts/ui/connection_overlay.gd": {"show_state": 3, "text": 0},
}


## Every way the build breaks the M4 contract, as readable lines; [] when it keeps it.
static func problems() -> Array:
	var out := []
	_wire(out)
	_sim_types(out)
	_rules(out)
	_seams(out)
	return out


static func _wire(out: Array) -> void:
	var spec := NetProtocol.spec()
	for key: String in NUMBERS:
		if int(spec.get(key, -1)) != int(NUMBERS[key]):
			out.append("protocol.json %s is %s, the contract says %d" % [key, spec.get(key), NUMBERS[key]])
	for table: String in VALUES:
		var have: Dictionary = spec.get(table, {})
		for key: String in VALUES[table]:
			if int(have.get(key, -1)) != int(VALUES[table][key]):
				out.append("protocol.json %s.%s is not %d" % [table, key, VALUES[table][key]])
	for pair: Array in [
		["notices", "no_held_seat", 9], ["end_reasons", "desynced_twice", 7],
		["link_flags", "catching_up", 4], ["link_flags", "hidden", 1], ["hash_flags", "checkpoint", 1],
		["hello_flags", "resume", 1], ["errors", "replaced", 12],
	]:
		if NetProtocol.enum_value(pair[0], pair[1]) != int(pair[2]):
			out.append("%s.%s is not %d" % pair)
	for name: String in IDS:
		if NetProtocol.message_id(name) != int(IDS[name]):
			out.append("%s moved off id %d" % [name, IDS[name]])
	for pair: Array in [
		["HELLO", Vector2i(38, 54)], ["MATCH_CONFIG", Vector2i(22, 106)], ["RESYNC", Vector2i(24, 24)],
		["VISIBILITY", Vector2i(2, 2)],
	]:
		if NetProtocol.sizes(pair[0]) != pair[1]:
			out.append("%s takes %s bytes, not %s" % [pair[0], NetProtocol.sizes(pair[0]), pair[1]])
	var messages := [
		["RESYNC", {
			"checkpoint_tick": 1800, "first_turn": 600, "reason": 0, "open_turn": 1234,
			"checkpoint_hash": PackedByteArray([1, 2, 3, 4, 5, 6, 7, 8]), "parts": 3,
		}],
		["VISIBILITY", {"state": 2}],
		["HELLO", {
			"version": 1, "build_seq": 7, "rules_hash": PackedByteArray([0, 0, 0, 0, 0, 0, 0, 1]),
			"token": PackedByteArray([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]), "flags": 1,
			"name": "Edda", "match": 9, "seat": 1,
		}],
	]
	for entry: Array in messages:
		var bytes := NetProtocol.encode(entry[0], entry[1])
		var back := NetProtocol.decode(bytes)
		if bytes.is_empty() or back.get("type", "") != entry[0] or str(back["fields"]) != str(entry[1]):
			out.append("%s does not round-trip: %s" % [entry[0], NetProtocol.last_error])
	var client := MatchClient.new()
	if client.held_match != 0 or client.held_seat != NetProtocol.number("system_seat"):
		out.append("a MatchClient's HELLO names a held seat before it held one")


static func _sim_types(out: Array) -> void:
	var fixed := [
		[SimTypes.SEAT_PRESENT, 0], [SimTypes.SEAT_AWAY, 1], [SimTypes.SEAT_RETURNING, 2],
		[SimTypes.SEAT_CARETAKER, 3], [SimTypes.SEAT_LEFT, 4],
		[SimTypes.seat_state_name(SimTypes.SEAT_RETURNING), "returning"],
		[SimTypes.seat_state_name(SimTypes.SEAT_CARETAKER), "caretaker"],
		[SimTypes.seat_state_name(9), ""], [SimTypes.seat_state("left"), SimTypes.SEAT_LEFT],
		[SimTypes.seat_state("nobody"), -1], [SimTypes.CHECKPOINT_EVERY, 1800],
		[SimTypes.REFUSE_CARETAKEN, 15],
		[Game.NOTICES[SimTypes.REFUSE_CARETAKEN], "The caretaker hands back at the next build window"],
		[SimTypes.EV_SEAT, 15],
	]
	for i in fixed.size():
		if fixed[i][0] != fixed[i][1]:
			out.append("SimTypes check %d gave %s, not %s" % [i, fixed[i][0], fixed[i][1]])


static func _rules(out: Array) -> void:
	for text: String in DIGESTS:
		var got := Checkpointing.digest(text.to_utf8_buffer()).hex_encode()
		if got != DIGESTS[text]:
			out.append("the digest of '%s' is %s, protocol.py's is %s" % [text, got, DIGESTS[text]])
	# A checkpoint's digest is the state hash HASH sends, at tick 0 and in play.
	var sim := SimMatch.create("high_water", 2, 7)
	for _i in 2:
		if Checkpointing.digest(sim.serialize()) != sim.state_hash():
			out.append("a checkpoint's digest is not the state hash at tick %d" % sim.tick)
		while sim.tick < 600:
			if sim.tick % SimTypes.TURN_TICKS == 0:
				sim.apply_turn(sim.tick / SimTypes.TURN_TICKS, [])
			sim.step()
	var ticks := [
		[60, [0], [0], false], [1800, [1], [1], true], [3600, [], [], true], [120, [2], [1], true],
		[120, [2, 1], [2, 1], false], [60, [1], [], false], [0, [0], [0], false], [61, [2], [1], false],
	]
	for row: Array in ticks:
		var now := PackedInt32Array(row[1])
		var then := PackedInt32Array(row[2])
		if Checkpointing.is_checkpoint_tick(row[0], now, then) != row[3]:
			out.append("tick %d with waves %s after %s is a checkpoint: %s" % [row[0], now, then, not row[3]])
	if Checkpointing.waves_of(sim) != PackedInt32Array([sim.hollows[0].wave]):
		out.append("waves_of does not list the hollows' waves")
	var bytes := PackedByteArray()
	bytes.resize(2308)
	var parts := Checkpointing.split(1800, bytes)
	var shape := parts.map(func(p: Dictionary) -> Array: return [p["tick"], p["part"], p["parts"], p["data"].size()])
	if shape != [[1800, 0, 3, 1024], [1800, 1, 3, 1024], [1800, 2, 3, 260]]:
		out.append("2,308 bytes split as %s" % [shape])
	bytes.resize(64 * 1024 + 1)
	if not Checkpointing.split(60, bytes).is_empty() or not Checkpointing.split(60, PackedByteArray()).is_empty():
		out.append("a checkpoint past max_checkpoint_parts, or of no bytes, has parts")
	if DesyncDump.path_for(9, 2) != "user://desync/9-2.bin":
		out.append("the dump of match 9's seat 2 goes to %s" % DesyncDump.path_for(9, 2))


static func _seams(out: Array) -> void:
	for path: String in SEAMS:
		var script: Script = load(path)
		if script == null:
			out.append("%s does not load" % path)
			continue
		var have := {}
		for method: Dictionary in script.get_script_method_list():
			have[method["name"]] = (method["args"] as Array).size()
		for name: String in SEAMS[path]:
			if not have.has(name):
				out.append("%s has no %s" % [path.get_file(), name])
			elif int(have[name]) != int(SEAMS[path][name]):
				out.append("%s.%s takes %d arguments, not %d" % [path.get_file(), name, have[name], SEAMS[path][name]])
	if WebBridge.is_web() or WebBridge.query("join") != "" or WebBridge.new().hidden:
		out.append("the web bridge is not inert on desktop")
	# (M4's caretaker takes a seat over mid-match where the player left it, unlike M3's: two
	# builds whose caretakers decide differently must not agree at HELLO)
	if SimContent.CARETAKER_VERSION < 2 or SimContent.rules_hash(1) == SimContent.rules_hash():
		out.append("the rules hash does not cover the caretaker's version")
	var overlay := ConnectionOverlay.new()
	if overlay.visible or overlay.state != ConnectionOverlay.State.NONE or overlay.text() != "":
		out.append("a new connection overlay shows something")
	overlay.show_state(ConnectionOverlay.State.CATCHING_UP, 620)
	if overlay.text() != "Catching up 62%":
		out.append("catching up reads '%s'" % overlay.text())
	overlay.show_state(ConnectionOverlay.State.RECONNECTING)
	if overlay.text() != "Reconnecting...  your towers keep firing":
		out.append("reconnecting reads '%s'" % overlay.text())
	var names: Array = ConnectionOverlay.State.keys()
	if names != ["NONE", "RECONNECTING", "CATCHING_UP", "IN_ANOTHER_TAB", "DESYNCED", "BACK"]:
		out.append("the overlay's states are %s" % [names])
	overlay.free()
