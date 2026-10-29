## The golden transcripts against the GDScript codec (design 7.4): every record of
## shared/net/transcripts/<name>.bin is decoded by NetProtocol, compared with the values
## the .json beside it lists (recorded from the Python server), and encoded back to the
## same bytes. Used by the protocol_golden_* scenarios:
##   {"eval": "resource('res://tests/net/golden.gd').check(['m1_handshake'])", "as": "report"}
## The .bin format: "LHTX", u8 format, u16 protocol version, u8 clients, u32 records; each
## record u8 direction, u8 client, u16 length, then the message without its frame.
extends RefCounted

const DIR := "res://shared/net/transcripts/"


## {"records", "decoded", "reencoded", "mismatches": [first few], "types": {name: count},
## "version"} over the named transcripts.
static func check(transcripts: Array) -> Dictionary:
	var report := {
		"records": 0, "decoded": 0, "reencoded": 0, "mismatches": [], "types": {}, "version": -1
	}
	for name: String in transcripts:
		var bytes := FileAccess.get_file_as_bytes(DIR + name + ".bin")
		var listing: Variant = JSON.parse_string(FileAccess.get_file_as_string(DIR + name + ".json"))
		if bytes.is_empty() or not listing is Dictionary:
			report["mismatches"].append("%s: cannot read the transcript" % name)
			continue
		var expected: Array = (listing as Dictionary)["records"]
		var reader := StreamPeerBuffer.new()
		reader.big_endian = true
		reader.data_array = bytes
		var magic: PackedByteArray = reader.get_data(4)[1]
		if magic.get_string_from_ascii() != "LHTX" or reader.get_u8() != 1:
			report["mismatches"].append("%s: not a format-1 transcript" % name)
			continue
		report["version"] = reader.get_u16()
		reader.get_u8()  # clients
		var count := reader.get_u32()
		if count != expected.size():
			report["mismatches"].append("%s: %d records, the listing has %d" % [name, count, expected.size()])
			continue
		for i in count:
			var direction := reader.get_u8()
			reader.get_u8()  # client
			var length := reader.get_u16()
			var message: PackedByteArray = reader.get_data(length)[1]
			report["records"] += 1
			var want: Dictionary = expected[i]
			var where := "%s #%d (%s)" % [name, i, want.get("type", "?")]
			if direction != (0 if want["dir"] == "c2s" else 1):
				_miss(report, where + ": direction")
			var decoded := NetProtocol.decode(message)
			if decoded.has("error"):
				_miss(report, "%s: %s" % [where, decoded["error"]])
				continue
			if decoded["type"] != want["type"] or not same(decoded["fields"], want["fields"]):
				_miss(report, "%s: decoded %s" % [where, decoded])
				continue
			report["decoded"] += 1
			var types: Dictionary = report["types"]
			types[decoded["type"]] = int(types.get(decoded["type"], 0)) + 1
			var again := NetProtocol.encode(decoded["type"], decoded["fields"])
			if again != message:
				_miss(report, "%s: re-encoded to %s, not %s" % [where, again.hex_encode(), message.hex_encode()])
				continue
			report["reencoded"] += 1
	return report


## A decoded value against the listing's: bytes as hex, numbers by value.
static func same(got: Variant, want: Variant) -> bool:
	if got is Dictionary:
		if not want is Dictionary or (got as Dictionary).size() != (want as Dictionary).size():
			return false
		for key: Variant in got:
			if not (want as Dictionary).has(key) or not same(got[key], want[key]):
				return false
		return true
	if got is Array:
		if not want is Array or (got as Array).size() != (want as Array).size():
			return false
		for i in (got as Array).size():
			if not same(got[i], want[i]):
				return false
		return true
	if got is PackedByteArray:
		return want is String and (got as PackedByteArray).hex_encode() == want
	if got is int:
		return (want is float or want is int) and got == int(want)
	return got == want


static func _miss(report: Dictionary, text: String) -> void:
	var list: Array = report["mismatches"]
	if list.size() < 5:
		list.append(text)
	else:
		list[4] = "... and more"


## Where the simulation's numbers (sim_types.gd) and the wire's (protocol.json) differ:
## command and system types, the server's seat, turn length and hash interval.
static func sim_type_mismatches() -> Array:
	var spec := NetProtocol.spec()
	var out := []
	var named := 0
	for table: String in ["commands", "system_commands"]:
		var entries: Dictionary = spec[table]
		for name: String in entries:
			named += 1
			var wire := int(entries[name]["type"])
			if SimTypes.command_type(name) != wire:
				out.append("%s is %d on the wire, %d in SimTypes" % [name, wire, SimTypes.command_type(name)])
	if SimTypes.COMMAND_TYPES.size() != named:
		out.append("SimTypes and protocol.json name different command sets")
	for pair: Array in [
		["system_seat", SimTypes.SYSTEM_SEAT],
		["turn_ticks", SimTypes.TURN_TICKS],
		["hash_every", SimTypes.HASH_EVERY],
		["tick_hz", SimTypes.TICKS_PER_SECOND],
	]:
		if int(spec[pair[0]]) != int(pair[1]):
			out.append("%s is %d on the wire, %d in SimTypes" % [pair[0], int(spec[pair[0]]), int(pair[1])])
	return out
