## What a player types into the Join field (or --join=) becomes a server URL (design
## 6.10, adapted from Cyberworld's network_address.c): a private or loopback address, a
## single-label name or a .local/.lan/.home/... name means a server on this network, so
## it becomes ws://host:8766/causeway; anything else is an online server behind TLS,
## wss://host/causeway. A typed port or path is kept; a whole ws:// or wss:// URL is taken
## as it is, with the path added when it has none.
class_name NetAddress
extends RefCounted

const LOCAL_SUFFIXES := [
	".localhost", ".local", ".lan", ".home", ".home.arpa", ".internal", ".localdomain"
]
const MAX_URL := 256


## The URL for a typed address, or "" when it cannot be one.
static func url(typed: String) -> String:
	var text := typed.strip_edges()
	var path := str(NetProtocol.spec()["path"])
	var result := ""
	if text.begins_with("ws://") or text.begins_with("wss://"):
		var after := text.substr(text.find("://") + 3)
		result = text if after.contains("/") else text + path
	else:
		var slash := text.find("/")
		var host := text if slash < 0 else text.substr(0, slash)
		var rest := "" if slash < 0 else text.substr(slash)
		# Where the name ends and a port begins: after an IPv6 address's bracket, or at a
		# name's one colon.
		var name_end := host.length()
		if host.begins_with("["):
			var close := host.find("]")
			if close >= 0:
				name_end = close + 1
		elif host.count(":") == 1:
			name_end = host.find(":")
		var name := host.substr(0, name_end)
		var local := is_local(name)
		var port := ""
		if local and name_end == host.length():
			port = ":%d" % NetProtocol.number("port")
		result = ("ws://" if local else "wss://") + host + port + (rest if rest != "" else path)
	return result if valid(result) else ""


## Whether a host name or address is on this computer or its network.
static func is_local(host: String) -> bool:
	var name := host.to_lower()
	if name.begins_with("["):
		return name.length() > 2 and name.ends_with("]") and _ipv6_local(name.substr(1, name.length() - 2))
	if name.length() > 1 and name.ends_with("."):
		name = name.substr(0, name.length() - 1)  # a fully qualified name's root
	if name == "":
		return false
	var parts := _ipv4(name)
	if not parts.is_empty():
		return _ipv4_local(parts)
	if not name.contains(".") or name == "localhost":
		return true
	for suffix: String in LOCAL_SUFFIXES:
		if name.length() > suffix.length() and name.ends_with(suffix):
			return true
	return false


## A ws:// or wss:// URL with a host of letters, digits, dots, dashes, colons and
## brackets, and a path.
static func valid(text: String) -> bool:
	if text.length() >= MAX_URL:
		return false
	var start := 6 if text.begins_with("wss://") else (5 if text.begins_with("ws://") else -1)
	if start < 0:
		return false
	var slash := text.find("/", start)
	if slash <= start:
		return false
	for i in range(start, slash):
		var c := text.unicode_at(i)
		var letter := (c >= 97 and c <= 122) or (c >= 65 and c <= 90)
		var digit := c >= 48 and c <= 57
		if not (letter or digit or c in [46, 45, 58, 91, 93]):
			return false
	return true


## A dotted IPv4 address's four numbers, or [] where `host` is none.
static func _ipv4(host: String) -> PackedInt32Array:
	var parts := host.split(".")
	if parts.size() != 4:
		return PackedInt32Array()
	var out := PackedInt32Array()
	for part in parts:
		if part == "" or part.length() > 3 or not part.is_valid_int() or part.begins_with("-"):
			return PackedInt32Array()
		var n := part.to_int()
		if n > 255:
			return PackedInt32Array()
		out.append(n)
	return out


## The private, shared (a carrier's or a VPN's), loopback and link-local blocks.
static func _ipv4_local(b: PackedInt32Array) -> bool:
	return (
		b[0] == 10
		or b[0] == 127
		or (b[0] == 172 and (b[1] & 0xF0) == 16)
		or (b[0] == 192 and b[1] == 168)
		or (b[0] == 169 and b[1] == 254)
		or (b[0] == 100 and (b[1] & 0xC0) == 64)
	)


## An IPv6 address between its brackets: loopback, unique local (fc00::/7) or link-local
## (fe80::/10), read from its first group.
static func _ipv6_local(inner: String) -> bool:
	if inner == "::1":
		return true
	var group := 0
	var i := 0
	while i < inner.length() and i < 4 and inner[i].is_valid_hex_number():
		group = group * 16 + inner[i].hex_to_int()
		i += 1
	if i == 0 or i >= inner.length() or inner[i] != ":":
		return false
	return (group & 0xFE00) == 0xFC00 or (group & 0xFFC0) == 0xFE80
