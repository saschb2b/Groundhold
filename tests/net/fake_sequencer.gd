## The server's match side in GDScript (test level 1, design 7.1): a port of
## server/groundhold_server/match.py and the dev match of app.py that counts frames instead
## of milliseconds, so N MatchClients in one SceneTree play a whole match through it
## deterministically. It speaks the real bytes (NetProtocol) over FakeLinks.
##
## What it does, as the Python server does it:
##   HELLO -> WELCOME; the first `seats` HELLOs form a dev match: MATCH_CONFIG, LOAD_STATE;
##   every LOADED compared (rules hash, tick-0 hash); START after the loading minimum;
##   turn k sealed at frame origin + 3(k + 1): system commands first, then the seats in
##   rotation from seat (k mod seats), then by sequence number; PING -> PONG; LINKS every
##   2 s; AWAY after 5 s of silence and BACK on the next message; LEAVE_MATCH -> LEFT;
##   the hash referee (all equal, or with three seats or more a strict majority, agree;
##   two seats apart or no majority end the match "desynced", a minority is only logged);
##   the result referee (a RESULT a strict majority of the present seats sent ends the
##   match; short of that it plays on while the present seats still playing, a HASH in
##   the last 10 s, could still form one: on their way to a claimed tick, or on an end of
##   their own); TURN_REQUEST answered from the turn log, a window at most, at most once
##   per half of the game's own asking interval; the CMD bucket (ERROR 8 when empty);
##   match messages that were on their way when MATCH_END went out are let pass.
## Not here (as in M1's server): the queue, checkpoints, RESYNC, resume.
##
## Lobby mode (`lobby = true`, M3: the hub and loading scripting, design 5.2 and 6.6):
## HELLO only welcomes; PARTY makes the one party (code `party_code`) or joins it, sets the
## mode, Builders and Ready, and the leader's start counts 3 s down (countdown_frames)
## while everyone else is Ready, then forms the match from the members in joining order
## with their mains as Builders. Loading reports each seat as the server does: connecting
## until its first LOADING, loading with its per mille, checking once LOADED while others
## still load, ready when all have, and slow from 15 s (slow_after) while not loaded; every
## second (load_every) it says the seconds again. After MATCH_END the party is back,
## forming, Ready cleared, every link kept. Members without a client (add_member) are
## scripted: set_member(), script_load(); in a match they never speak, so they go AWAY.
## As the server does, it closes a connection that said nothing for 15 s (silence_ms) and
## frees its party row (the server holds it 40 s first; nothing here comes back for it).
## From 30 s of loading the leader's PARTY start starts the seats loaded without the rest
## (start_without_frames): those begin AWAY in turn 0, and only their LOADED brings them
## BACK.
@warning_ignore_start("integer_division")
extends RefCounted


## A scripted member's connection: nobody reads it, it never drops.
class QuietLink:
	extends RefCounted
	var conn: Variant = null

	func push_down(_message: PackedByteArray) -> void:
		pass

	func take_up() -> Array[PackedByteArray]:
		return []

	func is_dropped() -> bool:
		return false

	func drop(_reason: String, _code := 1008) -> void:
		pass

const FRAMES_PER_SECOND := 60

var world
var seats := 2
var mode := "classic"
var match_seed := 1
var phase := "waiting"
## The open turn: the next to seal.
var turn := 0
## The frame turn 0 opened at; -1 before START.
var origin := -1
var configured_at := 0
var start_delay := 90
var loading_min := 240
var away_after := 300
var links_every := 120
var hash_wait := 120
## A present seat without a RESULT counts while its last HASH is this recent (result_wait_ms).
var result_wait := 600
## The CMD bucket (protocol.json buckets.cmd): burst, and refill a second.
var cmd_burst := 10
var cmd_refill := 5
## TURN_REQUEST: frames between answers, and turns per answer.
var resend_every := 15
var resend_turns := 100

## Connections in HELLO order; each a Dictionary (see accept()).
var conns: Array = []
## Sealed turns as the wire lists them: turn -> [[seat, seq, type, a, b, c], ...].
var turns: Array = []
## tick -> {seat: hash hex} still being decided, and tick -> agreed hash hex.
var hashes := {}
var agreed := {}
## Every [tick, {seat: hex}] where the seats disagreed.
var disagreements: Array = []
## How many hash ticks were compared with two or more seats reporting.
var compared := 0
var outcome := ""
var end_reason := ""
var final_tick := 0
## System commands injected, as [turn, name, seat], for assertions.
var system_log: Array = []
## Fields written over every seat's entry of MATCH_CONFIG (a broken or hostile server's
## {"team": 7}).
var seat_override := {}
## TURN_REQUESTs answered, and ignored for coming too soon after the last answer.
var resends := 0
var resends_ignored := 0

# Lobby mode (see the top of this file).
var lobby := false
var party_code := "K7Q4M"
## {"mode": wire id, "leader": member id, "phase": a party_phases name, "countdown_at":
## frame, "members": [conn, ...] in joining order}; {} without a party.
var party := {}
var countdown_frames := 180
var slow_after := 900
## Frames of silence after which a hub connection is closed, as the server does it.
var silence_frames := NetProtocol.number("silence_ms") * FRAMES_PER_SECOND / 1000
## The members whose connection was closed for silence, by name, for assertions.
var silenced: Array = []
## Frames of loading after which the leader may start without the slow seats (§6.6).
var start_without_frames := 30 * FRAMES_PER_SECOND
## The leader started without the seats still loading.
var started_without := false
var load_every := 60
## Every PARTY op received, as [member, op name], for assertions.
var party_log: Array = []
var _next_load_state := 0

var _pending: Array = []
var _system: Array = []
var _system_seq := 0
var _next_links := 0


func _init(owner_world: Variant, seat_count := 2, match_mode := "classic", seed_value := 1) -> void:
	world = owner_world
	seats = seat_count
	mode = match_mode
	match_seed = seed_value
	var bucket: Dictionary = NetProtocol.spec()["buckets"]["cmd"]
	cmd_burst = int(bucket["burst"])
	cmd_refill = int(bucket["refill"])
	resend_every = NetProtocol.number("turn_request_ms") / 2 * FRAMES_PER_SECOND / 1000
	resend_turns = NetProtocol.number("turn_request_turns")
	result_wait = NetProtocol.number("result_wait_ms") * FRAMES_PER_SECOND / 1000


## A client's link opened.
func accept(link: Variant) -> void:
	var conn := {
		"link": link,
		"seat": -1,
		"name": "",
		"rules_hash": PackedByteArray(),
		"state": "present",
		"heard": world.frame,
		"loaded": [],
		"hash_tick": -1,
		# (the frame of its last HASH; turn 0's opening before its first)
		"hashed": 0,
		"result": [],
		"rtt": 0,
		"last_seq": -1,
		"hello": false,
		# (the CMD bucket in 60ths of a command, as of frame "filled")
		"tokens": cmd_burst * FRAMES_PER_SECOND,
		"filled": world.frame,
		"resent": -1,
		# (lobby mode: the party member it is, its row 0 to 3 as the server numbers them,
		# -1 outside the party; its Builders, Ready, a scripted member's load and whether it
		# runs another version)
		"member": -1,
		"main": 0,
		"backup": 1,
		"ready": false,
		# (after a party's match: false while its game shows the results plate)
		"back": true,
		"virtual": false,
		"reload": false,
		"per_mille": 0,
		"virtual_loaded": false,
	}
	link.conn = conn
	conns.append(conn)


## A client closed its link.
func closed(link: Variant) -> void:
	var conn: Dictionary = link.conn
	if conn.is_empty() or conn["seat"] < 0 or phase == "ended":
		return
	_leave(conn)


## Once a frame, before the clients: read what arrived, seal the turns that are due.
func step() -> void:
	for conn: Dictionary in conns:
		var link = conn["link"]
		if link.is_dropped():
			continue
		for bytes: PackedByteArray in link.take_up():
			_receive(conn, bytes)
	if lobby:
		_close_silent()
	if lobby and not party.is_empty() and party["phase"] == "countdown" and world.frame >= int(party["countdown_at"]):
		_begin_party()
	if phase == "loading":
		if lobby and world.frame >= _next_load_state:
			_next_load_state = world.frame + load_every
			_broadcast_load_state()
		_check_start()
	if phase != "playing":
		return
	_tend()
	while phase == "playing" and world.frame >= origin + (turn + 1) * 3:
		_seal(turn)
		turn += 1


## Every hash two or more seats sent agreed, and there was at least one.
func hashes_agree() -> bool:
	return compared > 0 and disagreements.is_empty()


func seat_conn(seat: int) -> Dictionary:
	for conn: Dictionary in conns:
		if conn["seat"] == seat:
			return conn
	return {}


# ── Messages ──


func _receive(conn: Dictionary, bytes: PackedByteArray) -> void:
	var message := NetProtocol.decode(bytes)
	if message.has("error"):
		_refuse(conn, 1, str(message["error"]))
		return
	var fields: Dictionary = message["fields"]
	var type: String = message["type"]
	conn["heard"] = world.frame
	if conn["seat"] >= 0:
		_heard(conn)
	match type:
		"HELLO":
			_hello(conn, fields)
		"PING":
			conn["rtt"] = int(fields["rtt_ms"])
			_send(conn, "PONG", {"client_ms": fields["client_ms"], "turn": turn if origin >= 0 else 0})
		"LOADING":
			conn["per_mille"] = int(fields["per_mille"])
			if lobby and phase == "loading":
				_broadcast_load_state()
		"LOADED":
			conn["loaded"] = [fields["rules_hash"], fields["tick0_hash"]]
			if conn.get("late", false) and phase == "playing":
				conn["late"] = false  # (started without it: its LOADED brings it back)
				conn["state"] = "present"
				_inject("BACK", conn["seat"])
			_broadcast_load_state()
		"PARTY":
			if lobby:
				_party_op(conn, fields)
			else:
				_refuse(conn, 1, "Unknown or out-of-order message")
		"CMD":
			_command(conn, fields)
		"HASH":
			if phase == "ended":
				return  # (sent before its MATCH_END arrived: let pass)
			if int(fields["flags"]) & ~1:
				_refuse(conn, 6, "HASH outside its limits")
				return
			_hash(conn, int(fields["tick"]), (fields["hash"] as PackedByteArray).hex_encode())
			_judge()
		"RESULT":
			_result(conn, fields)
		"TURN_REQUEST":
			if phase != "ended":
				_resend(conn, int(fields["first_missing"]))
		"LEAVE_MATCH":
			if lobby and phase == "ended":
				_back(conn)  # (Play again or Hub from the results plate)
			else:
				_leave(conn)
		"BYE":
			conn["link"].drop("Goodbye", 1000)
			if conn["seat"] >= 0 and phase != "ended":
				_leave(conn)
		"VISIBILITY":
			pass


func _hello(conn: Dictionary, fields: Dictionary) -> void:
	if conn["hello"]:
		_refuse(conn, 1, "Expected one HELLO")
		return
	conn["hello"] = true
	conn["name"] = fields["name"]
	conn["rules_hash"] = fields["rules_hash"]
	_send(
		conn,
		"WELCOME",
		{
			"session": conns.find(conn) + 1,
			"identity": fields["token"],
			"turn_ms": NetProtocol.number("turn_ms"),
			"turn_ticks": NetProtocol.number("turn_ticks"),
			"hash_every": NetProtocol.number("hash_every"),
			"flags": 0 if lobby else 2,
			"server_name": "Loopback",
			"motd": "",
		}
	)
	if lobby:
		return  # (parties form matches)
	var waiting := conns.filter(func(c: Dictionary) -> bool: return c["hello"] and c["seat"] < 0)
	if phase == "waiting" and waiting.size() >= seats:
		_begin(waiting.slice(0, seats))


func _begin(players: Array) -> void:
	phase = "loading"
	configured_at = world.frame
	started_without = false
	var listed := []
	for i in players.size():
		var conn: Dictionary = players[i]
		conn["seat"] = i
		conn["heard"] = world.frame
		var builder: int = conn["main"] if lobby else 0
		var entry := {"seat": i, "team": 0, "builder": builder, "flags": 0, "name": conn["name"]}
		entry.merge(seat_override, true)
		listed.append(entry)
	for conn: Dictionary in players:
		_send(
			conn,
			"MATCH_CONFIG",
			{
				"match": 1,
				"mode": int(party["mode"]) if lobby else int(NetProtocol.spec()["modes"][mode]["id"]),
				"map": 0,
				"seed": match_seed,
				"rules_hash": _rules_of(players),
				"your_seat": conn["seat"],
				"seats": listed,
			}
		)
	_broadcast_load_state()


func _check_start() -> void:
	var players := _seated()
	var ready := players.filter(func(c: Dictionary) -> bool: return not _loaded_of(c).is_empty())
	if ready.is_empty() or (ready.size() < players.size() and not started_without):
		return
	var first: Array = _loaded_of(ready[0])
	for conn: Dictionary in ready:
		var loaded: Array = _loaded_of(conn)
		if loaded[0] != _rules_of(players):
			_end("aborted", "rules_mismatch", 0)
			return
		if loaded[1] != first[1]:
			for c: Dictionary in players:
				_send(c, "NOTICE", {"code": NetProtocol.enum_value("notices", "tick0_mismatch"), "argument": 255})
			_end("aborted", "tick0_mismatch", 0)
			return
	if world.frame < configured_at + (loading_min if players.size() > 1 else 0):
		return
	phase = "playing"
	origin = world.frame + start_delay
	_next_links = origin + links_every
	for conn: Dictionary in players:
		conn["heard"] = world.frame
		conn["hashed"] = origin
		if not ready.has(conn):
			# (started without it: AWAY in turn 0, the caretaker plays it)
			conn["late"] = true
			conn["state"] = "away"
			_inject("AWAY", conn["seat"])
	_broadcast("START", {"ms_until_turn0": start_delay * 1000 / FRAMES_PER_SECOND})


func _command(conn: Dictionary, fields: Dictionary) -> void:
	# (the bucket is taken before anything else, as the server's is)
	var tokens := mini(
		cmd_burst * FRAMES_PER_SECOND,
		int(conn["tokens"]) + (world.frame - int(conn["filled"])) * cmd_refill
	)
	conn["filled"] = world.frame
	if tokens < FRAMES_PER_SECOND:
		conn["tokens"] = tokens
		_refuse(conn, 8, "Message rate exceeded")
		return
	conn["tokens"] = tokens - FRAMES_PER_SECOND
	if phase == "ended" and conn["seat"] >= 0:
		return  # (sent before its MATCH_END arrived: let pass, as the server does)
	if phase != "playing" or conn["seat"] < 0:
		_refuse(conn, 1, "Unknown or out-of-order message")
		return
	var type := int(fields["type"])
	var name := SimTypes.COMMAND_NAMES.get(type, "") as String
	var spec: Dictionary = NetProtocol.spec()["commands"]
	if not spec.has(name):
		_refuse(conn, 6, "Unknown command type")
		return
	var ranges: Array = spec[name]["args"]
	var args := [int(fields["a"]), int(fields["b"]), int(fields["c"])]
	for i in 3:
		if args[i] < int(ranges[i][0]) or args[i] > int(ranges[i][1]):
			_refuse(conn, 6, name + " argument outside its limits")
			return
	if int(fields["seq"]) <= int(conn["last_seq"]):
		_refuse(conn, 1, "Command sequence numbers must increase")
		return
	conn["last_seq"] = int(fields["seq"])
	if conn["state"] != "left":
		_pending.append([conn["seat"], int(fields["seq"]), type, args[0], args[1], args[2]])


func _hash(conn: Dictionary, tick: int, hex: String) -> void:
	if tick % 60 != 0 or tick > 3 * turn or tick <= int(conn["hash_tick"]):
		_refuse(conn, 6, "HASH outside its limits")
		return
	conn["hash_tick"] = tick
	conn["hashed"] = world.frame
	if agreed.has(tick):
		if agreed[tick] != hex:
			disagreements.append([tick, {conn["seat"]: hex, -1: agreed[tick]}])
			_desync(tick)
		return
	if not hashes.has(tick):
		hashes[tick] = [world.frame, {}]
	hashes[tick][1][conn["seat"]] = hex
	if _present().all(func(c: Dictionary) -> bool: return (hashes[tick][1] as Dictionary).has(c["seat"])):
		_decide(tick)


## Every present seat reported the tick (or 2 s passed): all equal, or with three seats or
## more a strict majority, is agreement; the seats that differ from it are a desync.
func _decide(tick: int) -> void:
	var by: Dictionary = hashes[tick][1]
	hashes.erase(tick)
	if by.size() >= 2:
		compared += 1
	var best := ""
	var most := 0
	for value: String in by.values():
		var count := by.values().count(value)
		if count > most:
			best = value
			most = count
	if most == by.size() or (by.size() >= 3 and most * 2 > by.size()):
		agreed[tick] = best
		if most != by.size():
			disagreements.append([tick, by])
			_desync(tick)
		return
	disagreements.append([tick, by])
	_end("desynced", "desync", tick)


## Seats whose hash differs from the agreed one: with three seats or more a minority (only
## logged, as in M1's server; M4 resyncs it), with two the match ends "desynced".
func _desync(tick: int) -> void:
	if seats < 3:
		_end("desynced", "desync", tick)


## RESULT: bounded like HASH (no later than the sealed turns, no earlier than the seat's
## own last HASH), then judged.
func _result(conn: Dictionary, fields: Dictionary) -> void:
	var tick := int(fields["tick"])
	var outcomes := []
	for entry: Dictionary in fields["outcomes"]:
		outcomes.append(int(entry["outcome"]))
	if phase == "ended":
		return  # (sent before its MATCH_END arrived: let pass)
	if phase != "playing" or not (conn["result"] as Array).is_empty():
		_refuse(conn, 1, "Unknown or out-of-order message")
		return
	if (
		tick > 3 * turn
		or tick < int(conn["hash_tick"])
		or outcomes.size() != 1
		or outcomes.any(func(o: int) -> bool: return o > 2)
	):
		_refuse(conn, 6, "RESULT outside its limits")
		return
	conn["result"] = [tick, (fields["hash"] as PackedByteArray).hex_encode(), outcomes]
	_judge()


## The server's Match.judge: among the seats present now, a RESULT a strict majority sent
## (all of them, with one or two) ends the match. Short of that it plays on while a majority
## can still form from the present seats with no RESULT that are still playing (a HASH in
## the last result_wait frames): one whose last HASH is at or before a claimed tick may yet
## agree with that claim, and together they may agree on an end of their own (so with three
## seats a claim the other two ran past is outvoted). When none can, the match ends
## "desynced" at the earliest claimed tick.
func _judge() -> void:
	if phase != "playing":
		return
	var voters := _present()
	var claims := []  # [result, count], in the order first sent
	for conn: Dictionary in voters:
		var result: Array = conn["result"]
		if result.is_empty():
			continue
		var found := false
		for claim: Array in claims:
			if claim[0] == result:
				claim[1] += 1
				found = true
		if not found:
			claims.append([result, 1])
	if claims.is_empty():
		return
	var need := voters.size() / 2 + 1
	var playing := voters.filter(
		func(c: Dictionary) -> bool:
			return (c["result"] as Array).is_empty() and world.frame - int(c["hashed"]) < result_wait
	)
	var possible := playing.size() >= need
	var earliest := -1
	for claim: Array in claims:
		var result: Array = claim[0]
		var tick := int(result[0])
		earliest = tick if earliest < 0 else mini(earliest, tick)
		if int(claim[1]) >= need:
			var outcomes: Array = result[2]
			_end(NetProtocol.enum_name("outcomes", int(outcomes[0])), "result", tick)
			return
		var on_the_way := playing.filter(func(c: Dictionary) -> bool: return int(c["hash_tick"]) <= tick)
		possible = possible or int(claim[1]) + on_the_way.size() >= need
	if not possible:
		_end("desynced", "desync", earliest)


## TURN_REQUEST: the sealed turns from `first` again, at most resend_turns of them, never
## one below the seat's last HASH tick / 3, and at most once per resend_every frames.
func _resend(conn: Dictionary, first: int) -> void:
	if origin < 0:
		_refuse(conn, 1, "Unknown or out-of-order message")
		return
	if int(conn["resent"]) >= 0 and world.frame - int(conn["resent"]) < resend_every:
		resends_ignored += 1
		return
	conn["resent"] = world.frame
	resends += 1
	var start := maxi(first, (int(conn["hash_tick"]) + 1) / 3)
	for k in range(start, mini(turn, start + resend_turns)):
		_send_bytes(conn, _turn_bytes(k, turns[k]))


# ── The clock's work ──


func _tend() -> void:
	for conn: Dictionary in _seated():
		if conn["state"] == "present" and world.frame - int(conn["heard"]) >= away_after:
			conn["state"] = "away"
			_inject("AWAY", conn["seat"])
	for tick: int in hashes.keys():
		if world.frame - int(hashes[tick][0]) >= hash_wait:
			_decide(tick)
	# (a seat gone AWAY or LEFT no longer holds the results up)
	_judge()
	if phase == "playing" and world.frame >= _next_links:
		_next_links += links_every
		var listed := []
		for conn: Dictionary in _seated():
			var silent := 2 if conn["state"] != "present" else 0
			listed.append({"seat": conn["seat"], "rtt_ms": int(conn["rtt"]), "flags": silent})
		_broadcast("LINKS", {"seats": listed})


func _seal(k: int) -> void:
	var first := k % seats
	var players := _pending.duplicate()
	players.sort_custom(
		func(x: Array, y: Array) -> bool:
			var px := posmod(int(x[0]) - first, seats)
			var py := posmod(int(y[0]) - first, seats)
			return px < py or (px == py and int(x[1]) < int(y[1]))
	)
	var entries: Array = _system + players
	_system = []
	_pending = []
	while turns.size() < k:
		turns.append([])
	turns.append(entries)
	_broadcast_bytes(_turn_bytes(k, entries))


func _turn_bytes(k: int, entries: Array) -> PackedByteArray:
	var commands := []
	for e: Array in entries:
		commands.append({"seat": e[0], "seq": e[1], "type": e[2], "a": e[3], "b": e[4], "c": e[5]})
	return NetProtocol.encode("TURN", {"turn": k, "commands": commands})


func _inject(name: String, seat: int) -> void:
	_system_seq += 1
	var type := int(NetProtocol.spec()["system_commands"][name]["type"])
	_system.append([SimTypes.SYSTEM_SEAT, _system_seq, type, seat, 0, 0])
	system_log.append([turn, name, seat])


func _heard(conn: Dictionary) -> void:
	conn["heard"] = world.frame
	if conn["state"] == "away" and phase == "playing" and not conn.get("late", false):
		conn["state"] = "present"
		_inject("BACK", conn["seat"])


func _leave(conn: Dictionary) -> void:
	if conn["state"] == "left":
		return
	if phase == "playing":
		_inject("LEFT", conn["seat"])
	conn["state"] = "left"
	if _seated().all(func(c: Dictionary) -> bool: return c["state"] == "left"):
		_end("aborted", "everyone_left", turn * 3)


func _end(result: String, reason: String, tick: int) -> void:
	if phase == "ended":
		return
	phase = "ended"
	outcome = result
	end_reason = reason
	final_tick = tick
	_broadcast(
		"MATCH_END",
		{
			"outcome": NetProtocol.enum_value("outcomes", result),
			"reason": NetProtocol.enum_value("end_reasons", reason),
			"final_tick": tick,
		}
	)
	if lobby and not party.is_empty():
		# (the results, as the server keeps them: each member's game stays on its results
		# plate, in_match, until its LEAVE_MATCH (or a PARTY ready or builders) brings it
		# back, Ready cleared; scripted members come back at once; when all are back the
		# party is forming again, its links kept)
		party["phase"] = "results"
		for conn: Dictionary in party["members"]:
			conn["ready"] = false
			conn["back"] = conn["virtual"]
		_all_back()
		_broadcast_party()


## A member's game left the results plate: back in the party, Ready cleared.
func _back(conn: Dictionary) -> void:
	if party.is_empty() or party["phase"] != "results" or conn["back"] or not (party["members"] as Array).has(conn):
		return
	conn["back"] = true
	conn["ready"] = false
	_all_back()
	_broadcast_party()


func _all_back() -> void:
	if (party["members"] as Array).all(func(c: Dictionary) -> bool: return c["back"]):
		party["phase"] = "forming"


## Ends the match now with `result` (a test's way to the results).
func finish(result := "won") -> void:
	_end(result, "result", turn * 3)


# ── The lobby (lobby mode) ──


## A member without a client, named `who`, with `main` as its Builder: it hosts the party
## when there is none, otherwise joins it. Returns its connection record.
func add_member(who: String, main := "lamplighter") -> Dictionary:
	var link := QuietLink.new()
	accept(link)
	var conn: Dictionary = link.conn
	conn["virtual"] = true
	conn["hello"] = true
	conn["name"] = who
	conn["main"] = NetProtocol.enum_value("builders", main)
	if party.is_empty():
		_create_party(conn, int(NetProtocol.spec()["modes"][mode]["id"]))
	else:
		conn["member"] = _free_row()
		(party["members"] as Array).append(conn)
	_broadcast_party()
	return conn


## Sets a member's "ready", "reload" (another rules version) or "main" (a Builder id).
func set_member(who: String, key: String, value: Variant) -> void:
	var conn := member_conn(who)
	if conn.is_empty():
		return
	if key == "main":
		conn["main"] = NetProtocol.enum_value("builders", str(value))
	else:
		conn[key] = value
	_broadcast_party()


## A scripted member's loading: its per mille, and whether it has loaded (with the same
## hashes as the first member with a client).
func script_load(who: String, per_mille: int, loaded := false) -> void:
	var conn := member_conn(who)
	if conn.is_empty():
		return
	conn["per_mille"] = per_mille
	conn["virtual_loaded"] = loaded
	if phase == "loading":
		_broadcast_load_state()


func member_conn(who: String) -> Dictionary:
	for conn: Dictionary in conns:
		if conn["name"] == who:
			return conn
	return {}


func _party_op(conn: Dictionary, fields: Dictionary) -> void:
	var op := str(fields["op"])  # (the codec gives a switch case by its name)
	party_log.append([conn["member"], op])
	var members: Array = party.get("members", [])
	var leads := members.has(conn) and int(party["leader"]) == int(conn["member"])
	match op:
		"create":
			_drop_member(conn)
			_create_party(conn, int(fields["mode"]))
		"join":
			var code := (fields["code"] as PackedByteArray).get_string_from_ascii()
			if party.is_empty() or code != party_code:
				_notice(conn, "no_such_party")
				return
			if members.has(conn):
				return
			if members.size() >= NetProtocol.number("max_seats"):
				_notice(conn, "party_full")
				return
			_drop_member(conn)
			conn["member"] = _free_row()
			members.append(conn)
			conn["ready"] = false
		"leave":
			_drop_member(conn)
			_send_no_party(conn)
		"mode":
			if not leads or party["phase"] != "forming":
				return
			party["mode"] = int(fields["mode"])
			for m: Dictionary in members:
				m["ready"] = false
		"builders":
			conn["main"] = int(fields["main"])
			conn["backup"] = int(fields["backup"])
			conn["ready"] = false
			_back(conn)
		"ready":
			_back(conn)
			conn["ready"] = int(fields["on"]) == 1
		"start":
			if phase == "loading":
				var waited: bool = world.frame - configured_at >= start_without_frames
				if leads and waited and _seated().any(func(c: Dictionary) -> bool: return not _loaded_of(c).is_empty()):
					started_without = true
				return
			var others_ready := members.all(
				func(m: Dictionary) -> bool: return m == conn or (m["ready"] and not m["reload"])
			)
			if not leads or party["phase"] != "forming" or not others_ready or conn["reload"]:
				return
			party["phase"] = "countdown"
			party["countdown_at"] = world.frame + countdown_frames
		"cancel":
			if party.get("phase", "") == "countdown" and members.has(conn):
				party["phase"] = "forming"
		_:
			return
	_broadcast_party()


## The server's silence rule (shared/net/README.md, the handshake's step 4): a game that
## sent nothing, not even PING, for 15 s is closed, and its party row goes.
func _close_silent() -> void:
	for conn: Dictionary in conns:
		if conn["virtual"] or not conn["hello"] or conn["link"].is_dropped():
			continue
		if world.frame - int(conn["heard"]) < silence_frames:
			continue
		silenced.append(conn["name"])
		conn["link"].drop("Silent too long", 1001)
		if conn["seat"] >= 0 and phase == "playing":
			_leave(conn)
		_drop_member(conn)
		_broadcast_party()


func _create_party(conn: Dictionary, wire_mode: int) -> void:
	conn["member"] = 0
	party = {"mode": wire_mode, "leader": conn["member"], "phase": "forming", "countdown_at": 0, "members": [conn]}
	conn["ready"] = false


## The lowest row (0 to 3) no member of the party holds: a newcomer's, as on the server.
func _free_row() -> int:
	var taken := []
	for m: Dictionary in party.get("members", []):
		taken.append(int(m["member"]))
	var row := 0
	while taken.has(row):
		row += 1
	return row


func _drop_member(conn: Dictionary) -> void:
	if party.is_empty() or not (party["members"] as Array).has(conn):
		return
	(party["members"] as Array).erase(conn)
	if (party["members"] as Array).is_empty():
		party = {}
		return
	if int(party["leader"]) == int(conn["member"]):
		party["leader"] = party["members"][0]["member"]


func _begin_party() -> void:
	party["phase"] = "loading"
	turns = []
	turn = 0
	origin = -1
	hashes = {}
	agreed = {}
	disagreements = []
	compared = 0
	outcome = ""
	end_reason = ""
	final_tick = 0
	system_log = []
	_pending = []
	_system = []
	for conn: Dictionary in conns:
		conn["seat"] = -1
	for conn: Dictionary in party["members"]:
		conn["loaded"] = []
		conn["virtual_loaded"] = false
		if not conn["virtual"]:
			conn["per_mille"] = 0
		conn["hash_tick"] = -1
		conn["hashed"] = 0
		conn["result"] = []
		conn["last_seq"] = -1
		conn["state"] = "present"
		conn["resent"] = -1
	_next_load_state = world.frame + load_every
	_broadcast_party()
	_begin(party["members"])


func _broadcast_party() -> void:
	if party.is_empty():
		return
	var listed := []
	for conn: Dictionary in party["members"]:
		var state := "here"
		if conn["reload"]:
			state = "needs_reload"
		elif party["phase"] in ["loading", "in_match"] or not conn["back"]:
			state = "in_match"
		elif conn["ready"]:
			state = "ready"
		var hash_bytes: PackedByteArray = conn["rules_hash"]
		if hash_bytes.size() != 8:
			hash_bytes = PackedByteArray([0, 0, 0, 0, 0, 0, 0, 0])
		listed.append(
			{
				"member": conn["member"],
				"team": 0,
				"main": conn["main"],
				"backup": conn["backup"],
				"state": NetProtocol.enum_value("member_states", state),
				"rtt_ms": int(conn["rtt"]),
				"build_seq": 0,
				"rules_hash": hash_bytes,
				"name": conn["name"],
			}
		)
	var left := maxi(0, int(party["countdown_at"]) - world.frame) * 1000 / FRAMES_PER_SECOND
	var fields := {
		"code": party_code.to_ascii_buffer(),
		"mode": party["mode"],
		"flags": 0,
		"leader": party["leader"],
		"phase": NetProtocol.enum_value("party_phases", party["phase"]),
		"countdown_ms": left if party["phase"] == "countdown" else 0,
		"members": listed,
	}
	for conn: Dictionary in party["members"]:
		fields["you"] = conn["member"]  # (each member told its own row, as the server does)
		_send_bytes(conn, NetProtocol.encode("PARTY_STATE", fields))


## The no-party state the server sends after a leave: five zero bytes, leader 255, nobody.
func _send_no_party(conn: Dictionary) -> void:
	conn["member"] = -1
	var fields := {
		"code": PackedByteArray([0, 0, 0, 0, 0]), "mode": 0, "flags": 0, "leader": 255, "you": 255,
		"phase": 0, "countdown_ms": 0, "members": [],
	}
	_send_bytes(conn, NetProtocol.encode("PARTY_STATE", fields))


func _notice(conn: Dictionary, key: String) -> void:
	_send(conn, "NOTICE", {"code": NetProtocol.enum_value("notices", key), "argument": 0})


## What a seat has LOADED: its own, or for a scripted member that has, the first client's.
func _loaded_of(conn: Dictionary) -> Array:
	if not conn["virtual"]:
		return conn["loaded"]
	if not conn["virtual_loaded"]:
		return []
	for c: Dictionary in _seated():
		if not c["virtual"]:
			return c["loaded"]
	return []


## The rules hash a match is made with: its first member with a client's.
func _rules_of(players: Array) -> PackedByteArray:
	for c: Dictionary in players:
		if not c["virtual"]:
			return c["rules_hash"]
	return players[0]["rules_hash"]


func _refuse(conn: Dictionary, code: int, text: String) -> void:
	_send(conn, "ERROR", {"code": code, "text": text})
	conn["link"].drop(text)


# ── Writing ──


func _seated() -> Array:
	return conns.filter(func(c: Dictionary) -> bool: return c["seat"] >= 0)


func _present() -> Array:
	return _seated().filter(
		func(c: Dictionary) -> bool: return c["state"] == "present" and not c["link"].is_dropped()
	)


func _broadcast_load_state() -> void:
	var listed := []
	var players := _seated()
	var everyone := players.all(func(c: Dictionary) -> bool: return not _loaded_of(c).is_empty())
	var slow: bool = world.frame - configured_at >= slow_after
	for conn: Dictionary in players:
		var loaded := not _loaded_of(conn).is_empty()
		if not lobby:
			listed.append({"seat": conn["seat"], "per_mille": 1000 if loaded else 0, "state": 2 if loaded else 1})
			continue
		var state := "connecting"
		var per_mille := int(conn["per_mille"])
		if loaded:
			state = "ready" if everyone else "checking"
			per_mille = 1000
		elif slow:
			state = "slow"
		elif per_mille > 0:
			state = "loading"
		listed.append({"seat": conn["seat"], "per_mille": per_mille, "state": NetProtocol.enum_value("load_states", state)})
	_broadcast("LOAD_STATE", {"seats": listed, "seconds": (world.frame - configured_at) / FRAMES_PER_SECOND})


func _broadcast(type: String, fields: Dictionary) -> void:
	_broadcast_bytes(NetProtocol.encode(type, fields))


func _broadcast_bytes(bytes: PackedByteArray) -> void:
	for conn: Dictionary in _seated():
		_send_bytes(conn, bytes)


func _send(conn: Dictionary, type: String, fields: Dictionary) -> void:
	_send_bytes(conn, NetProtocol.encode(type, fields))


func _send_bytes(conn: Dictionary, bytes: PackedByteArray) -> void:
	var link = conn["link"]
	link.push_down(bytes)
