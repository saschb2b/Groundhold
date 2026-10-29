## The wire contract, read at runtime from shared/net/protocol.json (design 6.5): the
## same file the Python server builds its codec from, so the two codecs cannot drift on a
## layout. Messages are big-endian records with a one-byte type; every reader checks the
## exact length and bounds every field.
##
## A decoded message is {"type": "TURN", "fields": {...}}, or {"error": reason} when the
## bytes are not a valid message. Field values: scalars (u8, u16, u32, u64, i32) are ints;
## raw bytes (b8, b16, d16) are PackedByteArrays; s8 is a String; a counted list (l8) is
## an Array of Dictionaries; PARTY's op is its name ("create", "join", ...), as in the
## Python codec. encode() takes the same shapes and returns an empty array (with
## last_error set) when a value does not fit its field.
class_name NetProtocol
extends RefCounted

const SPEC_PATH := "res://shared/net/protocol.json"
const SCALAR_SIZES := {"u8": 1, "u16": 2, "u32": 4, "u64": 8, "i32": 4}

## Why the last encode() or decode() failed.
static var last_error := ""

static var _spec := {}
static var _by_name := {}
static var _by_id := {}


## The whole of protocol.json, parsed once.
static func spec() -> Dictionary:
	if _spec.is_empty():
		_load()
	return _spec


## A top-level number of the contract (port, turn_ms, hash_every, ...).
static func number(key: String) -> int:
	return int(spec()[key])


## A value from one of the contract's enums: enum_value("errors", "full") is 7.
static func enum_value(table: String, key: String) -> int:
	return int((spec()[table] as Dictionary).get(key, -1))


## The name an enum gives a number: enum_name("outcomes", 3) is "desynced"; "" if none.
static func enum_name(table: String, value: int) -> String:
	var entries: Dictionary = spec()[table]
	for key: String in entries:
		var entry: Variant = entries[key]
		var wire: int = int((entry as Dictionary)["id"]) if entry is Dictionary else int(entry)
		if wire == value:
			return key
	return ""


## A message's one-byte type, or -1.
static func message_id(name: String) -> int:
	spec()
	return int(_by_name[name]["id"]) if _by_name.has(name) else -1


static func message_name(id: int) -> String:
	spec()
	return str(_by_id.get(id, ""))


## A message as bytes: its type, then its fields in layout order.
static func encode(name: String, fields := {}) -> PackedByteArray:
	spec()
	last_error = ""
	if not _by_name.has(name):
		return _encode_failed("unknown message " + name)
	var message: Dictionary = _by_name[name]
	var out := StreamPeerBuffer.new()
	out.big_endian = true
	out.put_u8(int(message["id"]))
	var values := fields
	var cases: Array = []
	if message.has("switch"):
		var switch: Dictionary = message["switch"]
		var key: String = switch["field"]
		var case_name := str(fields.get(key, ""))
		var options: Dictionary = switch["cases"]
		if not options.has(case_name):
			return _encode_failed("%s: unknown %s %s" % [name, key, case_name])
		values = fields.duplicate()
		values[key] = enum_value(str(switch["enum"]), case_name)
		cases = options[case_name]
	if not _write_fields(out, message["fields"], values, name):
		return PackedByteArray()
	if not cases.is_empty() and not _write_fields(out, cases, values, name):
		return PackedByteArray()
	return out.data_array


## A message from bytes, its length exact and every field bounded.
static func decode(data: PackedByteArray) -> Dictionary:
	spec()
	last_error = ""
	if data.is_empty():
		return _decode_failed("Empty message")
	var name := message_name(data[0])
	if name == "":
		return _decode_failed("Unknown message")
	var message: Dictionary = _by_name[name]
	var reader := StreamPeerBuffer.new()
	reader.big_endian = true
	reader.data_array = data
	reader.seek(1)
	var fields := {}
	if not _read_fields(reader, message["fields"], fields):
		return _decode_failed("Malformed " + name)
	if message.has("switch"):
		var switch: Dictionary = message["switch"]
		var key: String = switch["field"]
		var case_name := enum_name(str(switch["enum"]), int(fields[key]))
		var options: Dictionary = switch["cases"]
		if case_name == "" or not options.has(case_name):
			return _decode_failed("Malformed " + name)
		fields[key] = case_name
		if not _read_fields(reader, options[case_name], fields):
			return _decode_failed("Malformed " + name)
	if reader.get_position() != data.size():
		return _decode_failed("Malformed " + name)
	return {"type": name, "fields": fields}


## (least, most) bytes a message can take, its type byte included.
static func sizes(name: String) -> Vector2i:
	spec()
	var message: Dictionary = _by_name[name]
	var span := _sizes(message["fields"])
	if message.has("switch"):
		var least := 1 << 30
		var most := 0
		for fields: Array in (message["switch"]["cases"] as Dictionary).values():
			var case_span := _sizes(fields)
			least = mini(least, case_span.x)
			most = maxi(most, case_span.y)
		span += Vector2i(least, most)
	return span + Vector2i(1, 1)


# ── Layouts ──


static func _load() -> void:
	var text := FileAccess.get_file_as_string(SPEC_PATH)
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		push_error("NetProtocol: cannot read " + SPEC_PATH)
		_spec = {"messages": {}}
		return
	_spec = parsed
	for name: String in (_spec["messages"] as Dictionary):
		var message: Dictionary = _spec["messages"][name]
		_by_name[name] = message
		_by_id[int(message["id"])] = name


static func _sizes(fields: Array) -> Vector2i:
	var least := 0
	var most := 0
	for field: Array in fields:
		var kind: String = field[1]
		if SCALAR_SIZES.has(kind):
			least += SCALAR_SIZES[kind]
			most += SCALAR_SIZES[kind]
		elif kind == "s8":
			least += 1
			most += 1 + int(field[2])
		elif kind == "d16":
			least += 2
			most += 2 + int(field[2])
		elif kind == "l8":
			least += 1
			most += 1 + int(field[3]) * _sizes(field[2]).y
		else:
			var size := int(kind.substr(1))
			least += size
			most += size
	return Vector2i(least, most)


static func _write_fields(out: StreamPeerBuffer, fields: Array, values: Dictionary, where: String) -> bool:
	for field: Array in fields:
		var key: String = field[0]
		var kind: String = field[1]
		if not values.has(key):
			return _write_failed("%s: %s is missing" % [where, key])
		var value: Variant = values[key]
		match kind:
			"u8", "u16", "u32", "u64", "i32":
				if not (value is int):
					return _write_failed("%s: %s must be an int" % [where, key])
				if not _fits(kind, value):
					return _write_failed("%s: %s = %d does not fit %s" % [where, key, value, kind])
				_put_scalar(out, kind, value)
			"s8":
				var text := str(value).to_utf8_buffer()
				if text.size() > int(field[2]):
					return _write_failed("%s: %s is longer than %d bytes" % [where, key, int(field[2])])
				# (what the decoder and protocol.py refuse is never sent)
				if not _utf8_ok(text):
					return _write_failed("%s: %s holds a NUL or starts with a byte-order mark" % [where, key])
				out.put_u8(text.size())
				out.put_data(text)
			"d16":
				if not (value is PackedByteArray) or (value as PackedByteArray).size() > int(field[2]):
					return _write_failed("%s: %s must be at most %d bytes" % [where, key, int(field[2])])
				out.put_u16((value as PackedByteArray).size())
				out.put_data(value)
			"l8":
				if not (value is Array) or (value as Array).size() > int(field[3]):
					return _write_failed("%s: %s must list at most %d" % [where, key, int(field[3])])
				out.put_u8((value as Array).size())
				for item: Variant in value:
					if not (item is Dictionary) or not _write_fields(out, field[2], item, where):
						return _write_failed(last_error if last_error != "" else where + ": bad entry")
			_:
				var size := int(kind.substr(1))
				if not (value is PackedByteArray) or (value as PackedByteArray).size() != size:
					return _write_failed("%s: %s must be %d bytes" % [where, key, size])
				out.put_data(value)
	return true


static func _read_fields(reader: StreamPeerBuffer, fields: Array, into: Dictionary) -> bool:
	var size := reader.get_size()
	for field: Array in fields:
		var key: String = field[0]
		var kind: String = field[1]
		var left := size - reader.get_position()
		match kind:
			"u8", "u16", "u32", "u64", "i32":
				if left < SCALAR_SIZES[kind]:
					return false
				into[key] = _get_scalar(reader, kind)
			"s8":
				if left < 1:
					return false
				var length := reader.get_u8()
				if length > int(field[2]) or length > left - 1:
					return false
				var text: PackedByteArray = reader.get_data(length)[1] if length > 0 else PackedByteArray()
				# (checked before decoding: the engine prints an error for every bad byte)
				if not _utf8_ok(text):
					return false
				into[key] = text.get_string_from_utf8()
				if into[key].to_utf8_buffer() != text:
					return false  # not UTF-8
			"d16":
				if left < 2:
					return false
				var length := reader.get_u16()
				if length > int(field[2]) or length > left - 2:
					return false
				into[key] = reader.get_data(length)[1] if length > 0 else PackedByteArray()
			"l8":
				if left < 1:
					return false
				var count := reader.get_u8()
				if count > int(field[3]):
					return false
				var items := []
				for i in count:
					var item := {}
					if not _read_fields(reader, field[2], item):
						return false
					items.append(item)
				into[key] = items
			_:
				var length := int(kind.substr(1))
				if left < length:
					return false
				into[key] = reader.get_data(length)[1]
	return true


## Strict UTF-8 (no overlong forms, no surrogates, nothing past U+10FFFF) with no NUL and
## no leading byte-order mark, as protocol.py reads strings.
static func _utf8_ok(bytes: PackedByteArray) -> bool:
	var n := bytes.size()
	if n >= 3 and bytes[0] == 0xEF and bytes[1] == 0xBB and bytes[2] == 0xBF:
		return false
	var i := 0
	while i < n:
		var b := bytes[i]
		if b == 0:
			return false
		if b < 0x80:
			i += 1
			continue
		var more := 0
		var low := 0x80
		var high := 0xBF
		if b >= 0xC2 and b <= 0xDF:
			more = 1
		elif b >= 0xE0 and b <= 0xEF:
			more = 2
			low = 0xA0 if b == 0xE0 else 0x80
			high = 0x9F if b == 0xED else 0xBF
		elif b >= 0xF0 and b <= 0xF4:
			more = 3
			low = 0x90 if b == 0xF0 else 0x80
			high = 0x8F if b == 0xF4 else 0xBF
		else:
			return false
		if i + more >= n:
			return false
		for k in more:
			var c := bytes[i + 1 + k]
			if c < (low if k == 0 else 0x80) or c > (high if k == 0 else 0xBF):
				return false
		i += 1 + more
	return true


static func _fits(kind: String, value: int) -> bool:
	match kind:
		"u8":
			return value >= 0 and value <= 0xFF
		"u16":
			return value >= 0 and value <= 0xFFFF
		"u32":
			return value >= 0 and value <= 0xFFFFFFFF
		"i32":
			return value >= -0x80000000 and value <= 0x7FFFFFFF
	return true


static func _put_scalar(out: StreamPeerBuffer, kind: String, value: int) -> void:
	match kind:
		"u8":
			out.put_u8(value)
		"u16":
			out.put_u16(value)
		"u32":
			out.put_u32(value)
		"u64":
			out.put_u64(value)
		"i32":
			out.put_32(value)


static func _get_scalar(reader: StreamPeerBuffer, kind: String) -> int:
	match kind:
		"u8":
			return reader.get_u8()
		"u16":
			return reader.get_u16()
		"u32":
			return reader.get_u32()
		"u64":
			return reader.get_u64()
	return reader.get_32()


static func _encode_failed(reason: String) -> PackedByteArray:
	last_error = reason
	return PackedByteArray()


static func _write_failed(reason: String) -> bool:
	last_error = reason
	return false


static func _decode_failed(reason: String) -> Dictionary:
	last_error = reason
	return {"error": reason}
