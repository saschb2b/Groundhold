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


## The match seats this install's games hold on servers (M4, design 6.7: a game killed or
## closed mid-match takes its seat back when it starts again). user://net.cfg keeps a list
## under [seats] of [origin, match, wire seat, process id, unix time held, sequence floor],
## newest last, at most SEATS_KEPT, none older than SEAT_HOURS (a match lasts an hour at
## most). The floor is above every CMD sequence number the game sent from that seat
## (MatchClient raises it a block at a time, note_floor), so the game started again goes
## on above them: the server wants a seat's numbers strictly increasing. A game holds
## its seat from MATCH_CONFIG to MATCH_END (MatchClient.remember_seat) and gives it up when
## the match ends, the seat left or it was refused; a lost link that gave up keeps it, since
## the server holds the seat until the match ends. Two windows of one install share this
## file, and so the identity: held_seat() skips a seat whose game still runs where that can
## be told (Linux, /proc), and a resume naming a seat a live window plays only replaces it
## (ERROR 12) elsewhere.
const SEATS := "seats"
const SEATS_KEPT := 8
const SEAT_HOURS := 2


## Notes that a game of this process plays wire seat `wire_seat` of `match_id` on `url`'s
## server, its commands numbered below `floor` (once per match and seat: a second note
## replaces the first).
static func hold_seat(url: String, match_id: int, wire_seat: int, floor := 0) -> void:
	var where := origin(url)
	if where == "" or match_id <= 0:
		return
	var kept: Array = []
	for entry: Array in _seats():
		if not (str(entry[0]) == where and int(entry[1]) == match_id and int(entry[2]) == wire_seat):
			kept.append(entry)
	kept.append([where, match_id, wire_seat, _pid(), int(Time.get_unix_time_from_system()), floor])
	_save_seats(kept.slice(maxi(0, kept.size() - SEATS_KEPT)))


## Gives up this process's seat in `match_id` on `url`'s server (the match ended, the seat
## left, the game was refused).
static func release_seat(url: String, match_id: int) -> void:
	var where := origin(url)
	var kept: Array = []
	for entry: Array in _seats():
		if not (str(entry[0]) == where and int(entry[1]) == match_id and int(entry[3]) == _pid()):
			kept.append(entry)
	_save_seats(kept)


## [match, wire seat, sequence floor] of the newest seat held on `url`'s server whose game
## no longer runs, for a resume HELLO; [] when there is none.
static func held_seat(url: String) -> Array:
	var where := origin(url)
	var list := _seats()
	for i in range(list.size() - 1, -1, -1):
		var entry: Array = list[i]
		if str(entry[0]) == where and not _still_running(int(entry[3])):
			return [int(entry[1]), int(entry[2]), int(entry[5])]
	return []


## Raises this process's note for `match_id`'s wire seat `wire_seat` on `url`'s server to
## `floor`: every command it numbers below that may have gone out.
static func note_floor(url: String, match_id: int, wire_seat: int, floor: int) -> void:
	var where := origin(url)
	var list := _seats()
	for entry: Array in list:
		if str(entry[0]) == where and int(entry[1]) == match_id and int(entry[2]) == wire_seat:
			entry[5] = maxi(int(entry[5]), floor)
	_save_seats(list)


## The held seats as net.cfg keeps them, the stale and the malformed left out.
static func _seats() -> Array:
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	var listed: Variant = cfg.get_value(SEATS, "held", [])
	var now := int(Time.get_unix_time_from_system())
	var out: Array = []
	if listed is Array:
		for entry: Variant in listed:
			if entry is Array and (entry as Array).size() == 6 and now - int(entry[4]) < SEAT_HOURS * 3600:
				out.append(entry)
	return out


static func _save_seats(list: Array) -> void:
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	cfg.set_value(SEATS, "held", list)
	cfg.save(PATH)


## This process's id (0 in the browser, where there is one game per tab).
static func _pid() -> int:
	return 0 if OS.has_feature("web") else OS.get_process_id()


## Whether another game of this install still runs as `pid` (only Linux can tell, by /proc).
static func _still_running(pid: int) -> bool:
	if pid <= 0 or pid == _pid() or not DirAccess.dir_exists_absolute("/proc/self"):
		return false
	return DirAccess.dir_exists_absolute("/proc/%d" % pid)


## The key as user://net.cfg holds it now, read past the copy in memory; empty without one.
static func stored() -> PackedByteArray:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return PackedByteArray()
	return str(cfg.get_value(SECTION, "token", "")).hex_decode()


## Forgets the copy in memory, so the next device_key() reads the disk again (tests).
static func forget_cache() -> void:
	_key = PackedByteArray()
