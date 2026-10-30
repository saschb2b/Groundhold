## This install's identity for servers (design 6.12): a device key of 16 random bytes
## kept in user://net.cfg, made once and then read back every launch, so a server knows a
## returning player without an account. Two windows on one computer share it. The key
## never leaves the device: each server gets its own token, token_for(url) =
## HMAC-SHA1(key, "Groundhold identity v1\n" + origin(url))[:16] (shared/net/README.md,
## The token), only in HELLO, never in a URL or a log. One server cannot replay what it
## got as the player on another, and two servers cannot link a player by it; the server
## derives the public identity it shows others from the token (WELCOME).
class_name Identity
extends RefCounted

const PATH := "user://net.cfg"
const SECTION := "identity"
const TOKEN_DOMAIN := "Groundhold identity v1\n"

static var _key := PackedByteArray()


## The device key: read from disk once, made and saved on the first launch. It stays on
## this computer (the first name is made from it there); servers get token_for().
static func device_key() -> PackedByteArray:
	if _key.size() == NetProtocol.number("token_bytes"):
		return _key
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	var hex := str(cfg.get_value(SECTION, "token", ""))
	if hex.length() == NetProtocol.number("token_bytes") * 2:
		_key = hex.hex_decode()
		return _key
	_key = Crypto.new().generate_random_bytes(NetProtocol.number("token_bytes"))
	cfg.set_value(SECTION, "token", _key.hex_encode())
	cfg.save(PATH)
	return _key


## The token HELLO carries to the server at `url` (a ws:// or wss:// URL, NetAddress.url):
## stable for one origin, another for every other, never the key. `key` stands in for
## the device key (the reference vectors); an empty result where `url` has no origin.
static func token_for(url: String, key := PackedByteArray()) -> PackedByteArray:
	var where := origin(url)
	var device := key if not key.is_empty() else device_key()
	if where == "" or device.size() != NetProtocol.number("token_bytes"):
		return PackedByteArray()
	var digest := Crypto.new().hmac_digest(
		HashingContext.HASH_SHA1, device, (TOKEN_DOMAIN + where).to_utf8_buffer()
	)
	return digest.slice(0, NetProtocol.number("token_bytes"))


## A server's origin as its token is keyed by, exactly as the server's identity.origin()
## reads it: scheme://host:port, ws and wss kept apart, the host in lower case without a
## trailing dot (an IPv6 address in brackets), the port numeric, 80 for ws and 443 for
## wss where the URL names none. "" where `url` is no ws:// or wss:// URL.
static func origin(url: String) -> String:
	var scheme := "wss" if url.begins_with("wss://") else ("ws" if url.begins_with("ws://") else "")
	if scheme == "":
		return ""
	var rest := url.substr(scheme.length() + 3)
	var end := rest.length()
	for mark: String in ["/", "?", "#"]:
		var at := rest.find(mark)
		if at >= 0 and at < end:
			end = at
	var authority := rest.substr(0, end)
	authority = authority.substr(authority.rfind("@") + 1)
	var host := authority
	var port_text := ""
	if authority.begins_with("["):
		var close := authority.find("]")
		if close < 0:
			return ""
		host = authority.substr(1, close - 1)
		var after := authority.substr(close + 1)
		if after.begins_with(":"):
			port_text = after.substr(1)
		elif after != "":
			return ""
	elif authority.contains(":"):
		host = authority.substr(0, authority.rfind(":"))
		port_text = authority.substr(authority.rfind(":") + 1)
	host = host.to_lower()
	while host.ends_with("."):
		host = host.left(-1)
	if host == "":
		return ""
	var port := 443 if scheme == "wss" else 80
	if port_text != "":
		if not port_text.is_valid_int() or port_text.begins_with("-") or port_text.begins_with("+"):
			return ""
		port = port_text.to_int()
		if port <= 0 or port > 65535:
			return ""
	if host.contains(":"):
		host = "[" + host + "]"
	return "%s://%s:%d" % [scheme, host, port]


## The key as user://net.cfg holds it now, read past the copy in memory; empty without one.
static func stored() -> PackedByteArray:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return PackedByteArray()
	return str(cfg.get_value(SECTION, "token", "")).hex_decode()


## Forgets the copy in memory, so the next device_key() reads the disk again (tests).
static func forget_cache() -> void:
	_key = PackedByteArray()
