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
##   the hash referee (all equal, or with three voters or more a strict majority of the
##   seats present, agree, a tick waiting while the voters still to report could make
##   one; two seats apart or no majority end the match "desynced");
##   the result referee (a RESULT a strict majority of the present seats sent ends the
##   match; short of that it plays on while the present seats still playing, a HASH in
##   the last 10 s, could still form one: on their way to a claimed tick, or on an end of
##   their own); TURN_REQUEST answered from the turn log, a window at most, at most once
##   per half of the game's own asking interval; the CMD bucket (ERROR 8 when empty);
##   match messages that were on their way when MATCH_END went out are let pass.
## Resilience (M4, shared/net/README.md Resilience; `resilience = false` keeps M1's
## server, which only logs a minority's hashes):
##   checkpoints: once the seats agree on a tick a HASH flagged, CHECKPOINT_ASK goes to one
##   seat in rotation (present, shown, not catching up); its CHECKPOINT_PARTs are checked
##   in order and kept (the last two) only when their digest is the agreed hash, else
##   dropped and the next seat asked, as after checkpoint_wait frames without them;
##   RESYNC (rejoin, desync, behind) from the latest kept checkpoint (tick 0 without one):
##   RESYNC, the parts, the turns since, then the live turns, all paced from the next
##   catchup_ms boundary as catchup.py does (whole messages within catchup_bytes a pump, the
##   first always, while the link's unsent output, its bytes in flight, stays within
##   catchup_output); after it the seat's HASHes count from the checkpoint tick, and
##   a desync's from the first one the re-run sends (tick + 60), so the reports still on
##   their way from before it are not taken for a second desync;
##   VISIBILITY: hidden and catching_up in LINKS; either holds BACK until shown, and
##   brings RESYNC(behind) when a kept checkpoint is past the seat's last HASH tick (for a
##   seat started without, once its LOADED came);
##   a minority's desync: RESYNC(desync) once (max_resyncs), then MATCH_END(desynced,
##   desynced_twice) to that seat alone, LEFT in the turns;
##   rejoin: a resume HELLO naming a seat its token holds takes it back (ERROR 12 to an old
##   link still open; PARTY_STATE in lobby mode, MATCH_CONFIG(rejoin), RESYNC(rejoin); while
##   the match still loads, MATCH_CONFIG as at the start, and it loads like any seat); a
##   seat not held gets NOTICE no_held_seat. A dropped link holds its seat (AWAY after its
##   silence), as the server does; a goodbye is LEFT.
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
## BACK. The party keeps open seats (PARTY open, PARTY_STATE's flag; a one-team mode's, so
## a switch to a race turns them off) and, in a two-team mode, teams (a joiner on the
## smaller team, the leader's PARTY team, a mode change laying them out alternately), as
## party.py does; a member's Ready is refused while queued or in a match, as lobby.py's.
##
## The queue in lobby mode (M6, as queue.py, shared/net/README.md The queue): the leader's
## QUEUE enter queues the party where it may (High Water: open seats on and free; a race:
## one team of 1 or 2; every other member Ready), PARTY_STATE queued and QUEUE_STATE to
## every member; anything else answers the asker with the state as it is. Strangers are
## scripted (add_stranger: each a party of one in the queue, in the order they came) and
## fill the open seats, or a race's rival team, in that order: MATCH_FOUND (accept_frames,
## the server's 15 s) to the party, again at every accept; strangers made with `accepts`
## accept at once, the others when a test says (stranger_answer). Everyone's ACCEPT forms a
## match of strangers (MATCH_CONFIG with the found match's id; each stranger's Builder
## unclashed: the main where the party and the strangers before do not play it, else the
## backup, else the first free one, where queue.py draws from Server.queue_rng: past the
## backups the Builders a scenario reads are this fake's, and smoke.py --flow --queue checks
## the server's own with real games; the party is always the earliest ticket here, so its
## seats come first); a decline, a leave, or the time running out dissolves it: the party
## back to forming if one of its members refused, else NOTICE match_dissolved
## and QUEUE_STATE queued, at the front; a refusing stranger leaves the queue. After
## offer_frames (60 s) queued: NOTICE caretakers_offered and the offer in QUEUE_STATE; then
## start_with_caretakers forms the party's match with caretaker seats (High Water: covering
## what the party lacks; a race: a mirror on team 1), each listed "gone" in LOAD_STATE.
## A duel (Undertow, M7) is a two-team mode of one seat a side, served by the race's rules: a
## party of one queues, one stranger is its rival, start_with_caretakers sets a caretaker of
## its Builder on team 1, and finish(result, per_team) ends it with one outcome a side.
## The level (M8, as party.py and queue.py): the party has one, Normal at first, in its
## PARTY_STATE; the leader's PARTY difficulty sets it (every Ready cleared, a countdown
## stopped), a member's, one while queued or in a match and the level it has are answered to
## the asker alone, one past the last is ERROR 6; a mode change keeps it. MATCH_CONFIG says the
## level the match plays (MatchRules.level_of: Normal in a mode without levels), a dev match's
## `difficulty` outside lobby mode. A stranger queues at a level of its own (add_stranger) and
## fills the party's seats or its rival team only at the level the party's match plays.
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
## A dev match's level (by name; it plays MatchRules.level_of(mode, difficulty)).
var difficulty := MatchRules.NORMAL
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
## {"team": 7}; {"flags": 1} makes every seat the caretaker's).
var seat_override := {}
## The dev match's Builders by seat (default: Lamplighters).
var seat_builders: Array = []
## TURN_REQUESTs answered, and ignored for coming too soon after the last answer.
var resends := 0
var resends_ignored := 0

# Resilience (M4; see the top of this file).
var resilience := true
## Checkpoints kept: their ticks, oldest first, and tick -> bytes.
var checkpoint_ticks: Array = []
var checkpoints := {}
## The upload asked for now: {"tick", "seat", "at" (frame), "data", "parts", "tried"}; {}.
var asking := {}
## Every upload dropped, as [tick, wire seat, why ("digest", "timeout")].
var uploads_dropped: Array = []
## Every upload kept, as [tick, wire seat].
var uploads_kept: Array = []
## Every RESYNC sent, as [open turn, wire seat, reason, checkpoint tick].
var resync_log: Array = []
## Rejoins taken (resume HELLOs that got their seat back), and no_held_seat notices.
var rejoins := 0
var no_held_seat := 0
## Seats ended alone (MATCH_END desynced_twice), by wire seat.
var ended_alone: Array = []
var checkpoint_wait := 300
var catchup_every := 3
var catchup_bytes := 2048
var catchup_output := 4096
var max_resyncs := 1
## The MATCH_CONFIG each seat was sent, by wire seat (a rejoin gets it again).
var configs := {}
## The tick-0 hash the seats LOADED with (the agreed hash of tick 0).
var tick0 := PackedByteArray()
var _ask_next := 0

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
## ... and one whose last VISIBILITY was hidden after this many (hidden_silence_ms).
var hidden_silence_frames := NetProtocol.number("hidden_silence_ms") * FRAMES_PER_SECOND / 1000
## The members whose connection was closed for silence, by name, for assertions.
var silenced: Array = []
## Frames of loading after which the leader may start without the slow seats (§6.6).
var start_without_frames := 30 * FRAMES_PER_SECOND
## A match of strangers (a dev match, not lobby mode) starts by itself with the seats
## loaded after this many frames of loading (§6.6's 45 s); -1 never.
var strangers_start_frames := 45 * FRAMES_PER_SECOND
## The leader started without the seats still loading (or the strangers' timer did).
var started_without := false
var load_every := 60
## The build_seq scripted members count from (add_member's build_offset); a test sets it to
## the game's own (Session.build_seq()).
var build_base := 0
## Members told NOTICE needs_reload, by name, in order.
var reload_notices: Array = []
## Every PARTY op received, as [member, op name], for assertions.
var party_log: Array = []
## PARTY_STATEs sent, by the connection's name: a broadcast counts one to each member, an
## answer to the asker alone (_send_party: an op the party's rules refuse) one to it.
var party_states_sent := {}
var _next_load_state := 0
## The queue (lobby mode, M6): the party's ticket {"since" (frame), "offered", "told"} while
## it is queued, {} otherwise; the strangers queued beside it (scripted conns) in the order
## they came; the match found waiting for its accepts {"id", "players" (conns, the party's
## first), "accepted" (conns), "deadline" (frame)}, {} while none; every QUEUE op received
## by name; the MATCH_FOUNDs sent; the id of the last match the queue found.
var ticket := {}
var strangers: Array = []
var found := {}
var queue_log: Array = []
var founds_sent := 0
var found_ids := 0
var accept_frames := NetProtocol.number("accept_ms") * FRAMES_PER_SECOND / 1000
var offer_frames := NetProtocol.number("caretaker_offer_ms") * FRAMES_PER_SECOND / 1000
## The match id MATCH_CONFIG carries (1, or the queue's found match's).
var match_number := 1
## The match now loading or playing came from the queue (its strangers' barrier: 45 s).
var queue_match := false
## Caretaker seats of the match ({"seat", "team", "builder", "flags", "name"}), no conn.
var caretaker_seats: Array = []

## Ticks a HASH flagged as checkpoint ticks.
var flagged := {}
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
	checkpoint_wait = NetProtocol.number("checkpoint_wait_ms") * FRAMES_PER_SECOND / 1000
	catchup_every = maxi(1, NetProtocol.number("catchup_ms") * FRAMES_PER_SECOND / 1000)
	catchup_bytes = NetProtocol.number("catchup_bytes")
	catchup_output = NetProtocol.number("catchup_output")
	max_resyncs = NetProtocol.number("max_resyncs")


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
		# (lobby mode: its team in a two-team mode; a stranger of the queue (M6): queued,
		# whether it accepts at once, its seat's team and Builder in the match formed)
		"team": 0,
		"stranger": false,
		"accepts": true,
		"match_team": 0,
		"match_builder": -1,
		# (the HELLO's build; whether it was told NOTICE needs_reload since it last did not need one)
		"build_seq": 0,
		"told_reload": false,
		"per_mille": 0,
		"virtual_loaded": false,
		# (M4: the HELLO's token; VISIBILITY's last state; the catch-up queue of whole
		# messages; RESYNCs taken; the tick whose HASH the re-run after a desync's RESYNC
		# sends first, -1 none; out of the match alone after desynced_twice)
		"token": PackedByteArray(),
		"visibility": 0,
		"catchup": [],
		"resyncs": 0,
		"restart_at": -1,
		# (the checkpoint tick of its last RESYNC(behind): never the same one twice, as
		# match.py's behind_from)
		"behind_from": 0,
		"asked": [],
		"out": false,
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
	if lobby:
		_tend_queue()
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
	if type == "VISIBILITY":
		if int(fields["state"]) > 2:
			_refuse(conn, 6, "VISIBILITY outside its limits")
			return
		# (the state counts before the word does: catching_up holds BACK back)
		conn["visibility"] = int(fields["state"])
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
				if resilience and int(conn["visibility"]) == 2:
					# (catching up: shown brings it BACK; a kept checkpoint gets it there)
					if _latest_kept() > maxi(0, int(conn["behind_from"])):
						_resync(conn, "behind")
				else:
					conn["state"] = "present"
					_inject("BACK", conn["seat"])
			_broadcast_load_state()
		"PARTY":
			if lobby:
				_party_op(conn, fields)
			else:
				_refuse(conn, 1, "Unknown or out-of-order message")
		"QUEUE":
			if lobby:
				_queue_op(conn, fields)
			else:
				_refuse(conn, 1, "Unknown or out-of-order message")
		"ACCEPT":
			if lobby:
				_accept(conn, int(fields["match"]), int(fields["yes"]) == 1)
		"CMD":
			_command(conn, fields)
		"HASH":
			if phase == "ended" or conn["out"]:
				return  # (sent before its MATCH_END arrived: let pass)
			if int(fields["flags"]) & ~1:
				_refuse(conn, 6, "HASH outside its limits")
				return
			var tick := int(fields["tick"])
			if int(conn["restart_at"]) >= 0:
				if tick != int(conn["restart_at"]):
					return  # (a report from before the RESYNC, still on its way)
				conn["restart_at"] = -1
			if int(fields["flags"]) & 1 and tick > 0:
				flagged[tick] = true
			_hash(conn, tick, (fields["hash"] as PackedByteArray).hex_encode())
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
			if resilience and int(fields["state"]) == 2 and phase == "playing":
				var waits: bool = conn.get("late", false)
				var past := maxi(int(conn["hash_tick"]), int(conn["behind_from"]))
				if not waits and _latest_kept() > past and (conn["catchup"] as Array).is_empty():
					_resync(conn, "behind")
		"CHECKPOINT_PART":
			_part(conn, fields)


func _hello(conn: Dictionary, fields: Dictionary) -> void:
	if conn["hello"]:
		_refuse(conn, 1, "Expected one HELLO")
		return
	var held_seat := int(fields["seat"])
	if (held_seat > 3 and held_seat != 255) or (held_seat <= 3 and int(fields["match"]) == 0):
		_refuse(conn, 1, "HELLO names no seat")
		return
	conn["hello"] = true
	conn["name"] = fields["name"]
	conn["rules_hash"] = fields["rules_hash"]
	conn["build_seq"] = int(fields["build_seq"])
	conn["token"] = fields["token"]
	if resilience and int(fields["flags"]) & 1 and held_seat <= 3:
		_welcome(conn, fields)
		_rejoin(conn, int(fields["match"]), held_seat)
		return
	_welcome(conn, fields)
	if lobby:
		return  # (parties form matches)
	var waiting := conns.filter(func(c: Dictionary) -> bool: return c["hello"] and c["seat"] < 0 and not c.get("replaced", false))
	if phase == "waiting" and waiting.size() >= seats:
		_begin(waiting.slice(0, seats))


func _welcome(conn: Dictionary, fields: Dictionary) -> void:
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


## MATCH_CONFIG to `players` (conns, in seat order), then `extra` caretaker seats, which
## no conn plays ({"team", "builder", "flags", "name"}: the queue's caretakers).
func _begin(players: Array, extra := []) -> void:
	phase = "loading"
	configured_at = world.frame
	started_without = false
	var listed := []
	for i in players.size():
		var conn: Dictionary = players[i]
		conn["seat"] = i
		conn["heard"] = world.frame
		var builder: int = conn["main"] if lobby else 0
		if lobby and int(conn["match_builder"]) >= 0:
			builder = int(conn["match_builder"])
		if not lobby and i < seat_builders.size():
			builder = NetProtocol.enum_value("builders", str(seat_builders[i]))
		if not lobby:
			# (a dev match's seats split over the mode's teams in order, as the server's
			# Match does: a 1v1 race is seat 0 on team 0 and seat 1 on team 1)
			conn["match_team"] = i * _match_teams() / players.size()
		var entry := {"seat": i, "team": int(conn["match_team"]), "builder": builder, "flags": 0, "name": conn["name"]}
		entry.merge(seat_override, true)
		listed.append(entry)
	caretaker_seats = []
	for spec: Dictionary in extra:
		var entry := {"seat": listed.size(), "team": int(spec["team"]), "builder": int(spec["builder"]), "flags": 1, "name": spec["name"]}
		caretaker_seats.append(entry)
		listed.append(entry)
	for conn: Dictionary in players:
		var config := {
			"match": match_number,
			"mode": int(party["mode"]) if lobby else int(NetProtocol.spec()["modes"][mode]["id"]),
			"difficulty": _match_level(),
			"map": 0,
			"seed": match_seed,
			"rules_hash": _rules_of(players),
			"your_seat": conn["seat"],
			"seats": listed,
			"flags": 0,
		}
		configs[int(conn["seat"])] = config
		_send(conn, "MATCH_CONFIG", config)
	_broadcast_load_state()


func _check_start() -> void:
	var players := _seated()
	var ready := players.filter(func(c: Dictionary) -> bool: return not _loaded_of(c).is_empty())
	var strangers_wait := (not lobby or queue_match) and strangers_start_frames >= 0
	if strangers_wait and world.frame - configured_at >= strangers_start_frames:
		started_without = true  # (45 s: a strangers' match starts with the seats loaded)
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
	tick0 = first[1]
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
			_desync(tick, [conn])
		return
	if not hashes.has(tick):
		hashes[tick] = [world.frame, {}]
	var by: Dictionary = hashes[tick][1]
	by[conn["seat"]] = hex
	if _voters(tick, by).all(func(c: Dictionary) -> bool: return by.has(c["seat"])):
		_decide(tick)


## The server's Match.voters: the seats whose word decides `tick`, the present ones that
## reported it and the present ones that may still (their last HASH below it, and in the
## last result_wait frames); a minority on its way back from a RESYNC does not vote.
func _voters(tick: int, by: Dictionary) -> Array:
	return _present().filter(
		func(c: Dictionary) -> bool:
			if int(c["restart_at"]) >= 0:
				return false
			return by.has(c["seat"]) or (int(c["hash_tick"]) < tick and world.frame - int(c["hashed"]) < result_wait)
	)


## The server's Match.decide: every voter reported the tick (or 2 s passed): all equal, or
## with three voters or more a strict majority of the voters (not of the reports so far),
## is agreement, and the seats that differ from it are a desync. Short of that the tick
## waits while the voters still to report could make one; when none can, the match ends
## "desynced".
func _decide(tick: int) -> void:
	var entry: Array = hashes[tick]
	var by: Dictionary = entry[1]
	hashes.erase(tick)
	var voting := []
	for c: Dictionary in _voters(tick, by):
		voting.append(int(c["seat"]))
	if voting.is_empty():
		voting = by.keys()  # (nobody votes any more: the reports there decide)
	var votes := []
	for seat_no: int in voting:
		if by.has(seat_no):
			votes.append(by[seat_no])
	if votes.is_empty():
		hashes[tick] = entry  # (only seats that do not vote reported it: it waits)
		return
	var best := ""
	var most := 0
	for value: String in votes:
		var count := votes.count(value)
		if count > most:
			best = value
			most = count
	var missing := voting.size() - votes.size()
	if most == voting.size() or (voting.size() >= 3 and most * 2 > voting.size()):
		if by.size() >= 2:
			compared += 1
		agreed[tick] = best
		var minority := []
		for seat_no: int in by:
			if by[seat_no] != best:
				minority.append(seat_conn(seat_no))
		if not minority.is_empty():
			disagreements.append([tick, by])
			_desync(tick, minority)
		if resilience and flagged.has(tick) and phase == "playing":
			_ask_checkpoint(tick, [])
		return
	if missing > 0:
		var need := voting.size() / 2 + 1 if voting.size() >= 3 else voting.size()
		if most == votes.size() or (voting.size() >= 3 and most + missing >= need):
			hashes[tick] = entry
			return
	if by.size() >= 2:
		compared += 1
	disagreements.append([tick, by])
	_end("desynced", "desync", tick)


## Seats whose hash differs from the agreed one: with three seats or more a minority,
## resynced once and then ended alone (M1's server only logged it), with two the match
## ends "desynced".
func _desync(tick: int, minority: Array) -> void:
	if seats < 3:
		_end("desynced", "desync", tick)
		return
	if not resilience:
		return
	for conn: Dictionary in minority:
		if conn.is_empty() or conn["out"] or conn["state"] == "left":
			continue
		if int(conn["resyncs"]) < max_resyncs:
			conn["resyncs"] = int(conn["resyncs"]) + 1
			_drop_reports(conn)
			_resync(conn, "desync")
		else:
			_end_alone(conn, tick)


## A seat's reports still waiting to be decided are its parted simulation's (a desync's
## RESYNC), or its old connection's (a rejoin): let go, as the server does.
func _drop_reports(conn: Dictionary) -> void:
	for tick: int in hashes.keys():
		var by: Dictionary = hashes[tick][1]
		by.erase(conn["seat"])
		if by.is_empty():
			hashes.erase(tick)


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
		or outcomes.size() != _match_teams()
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
			_end(NetProtocol.enum_name("outcomes", int(outcomes[0])), "result", tick, outcomes)
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
	if not (conn["catchup"] as Array).is_empty():
		return  # (a seat catching up is not answered: its catch-up brings every turn, in order)
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
	if not asking.is_empty() and world.frame - int(asking["at"]) >= checkpoint_wait:
		uploads_dropped.append([asking["tick"], asking["seat"], "timeout"])
		_ask_checkpoint(int(asking["tick"]), asking["tried"])
	if (world.frame - origin) % catchup_every == 0:
		for conn: Dictionary in _seated():
			_pump(conn)
	for tick: int in hashes.keys():
		if phase == "playing" and hashes.has(tick) and world.frame - int(hashes[tick][0]) >= hash_wait:
			_decide(tick)
	# (a seat gone AWAY or LEFT no longer holds the results up)
	_judge()
	if phase == "playing" and world.frame >= _next_links:
		_next_links += links_every
		var listed := []
		for conn: Dictionary in _seated():
			var silent := 2 if conn["state"] != "present" or conn["link"].is_dropped() else 0
			var shown := int(conn["visibility"])
			var flags := silent | (1 if shown == 1 else 0) | (4 if shown == 2 else 0)
			listed.append({"seat": conn["seat"], "rtt_ms": int(conn["rtt"]), "flags": flags})
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
	var bytes := _turn_bytes(k, entries)
	for conn: Dictionary in _seated():
		if (conn["catchup"] as Array).is_empty():
			_send_bytes(conn, bytes)
		else:
			(conn["catchup"] as Array).append(bytes)  # (behind its catch-up, in order)


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
		if resilience and int(conn["visibility"]) != 0:
			return  # (catching up, or hidden: only shown brings it BACK)
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


## The match ends: MATCH_END to every seat, each with its own team's outcome where a RESULT
## gave one per team (a race: `per_team`, as the server's Match.end), else `result`.
func _end(result: String, reason: String, tick: int, per_team := []) -> void:
	if phase == "ended":
		return
	phase = "ended"
	outcome = result
	end_reason = reason
	final_tick = tick
	for conn: Dictionary in _seated():
		if conn["out"]:
			continue
		var mine := result
		var team := _team_of(int(conn["seat"]))
		if team < per_team.size():
			mine = NetProtocol.enum_name("outcomes", int(per_team[team]))
		_send(
			conn,
			"MATCH_END",
			{
				"outcome": NetProtocol.enum_value("outcomes", mine),
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


## Ends the match now with `result` (a test's way to the results); `per_team` gives each team
## its own outcome by name, as a race's or a duel's RESULT does (["won", "lost"]: team 0 won).
func finish(result := "won", per_team := []) -> void:
	var outcomes := []
	for name: Variant in per_team:
		outcomes.append(NetProtocol.enum_value("outcomes", str(name)))
	_end(str(per_team[0]) if not per_team.is_empty() else result, "result", turn * 3, outcomes)


# ── Resilience (M4) ──


## The latest checkpoint tick kept, 0 for none.
func _latest_kept() -> int:
	return int(checkpoint_ticks[-1]) if not checkpoint_ticks.is_empty() else 0


## CHECKPOINT_ASK(tick) to the next seat in rotation that is present, shown and not
## catching up, and not among `tried`; none left: nothing is kept for that tick.
func _ask_checkpoint(tick: int, tried: Array) -> void:
	asking = {}
	if tick <= _latest_kept():
		return
	var order := _seated()
	for i in order.size():
		var conn: Dictionary = order[(_ask_next + i) % order.size()]
		var seat_no := int(conn["seat"])
		if tried.has(seat_no) or conn["state"] != "present" or conn["out"] or conn["link"].is_dropped():
			continue
		if int(conn["visibility"]) != 0 or not (conn["catchup"] as Array).is_empty():
			continue
		_ask_next = (_ask_next + i + 1) % order.size()
		asking = {"tick": tick, "seat": seat_no, "at": world.frame, "data": PackedByteArray(), "parts": 0, "tried": tried + [seat_no]}
		(conn["asked"] as Array).append(tick)
		_send(conn, "CHECKPOINT_ASK", {"tick": tick})
		return


## A CHECKPOINT_PART from a seat: in order, whole, then kept only if its digest is the
## agreed hash (shared/net/README.md Resilience).
func _part(conn: Dictionary, fields: Dictionary) -> void:
	var tick := int(fields["tick"])
	var mine := not asking.is_empty() and int(asking["tick"]) == tick and int(asking["seat"]) == int(conn["seat"])
	if not mine:
		if not (conn["asked"] as Array).has(tick):
			_refuse(conn, 1, "Unknown or out-of-order message")
		return  # (a tick it stopped waiting for: let pass)
	var data: PackedByteArray = fields["data"]
	var parts := int(fields["parts"])
	var got: PackedByteArray = asking["data"]
	var size := NetProtocol.number("checkpoint_part")
	if (
		int(fields["part"]) * size != got.size()
		or parts > NetProtocol.number("max_checkpoint_parts")
		or int(fields["part"]) >= parts
		or (int(asking["parts"]) > 0 and parts != int(asking["parts"]))
	):
		_refuse(conn, 6, "CHECKPOINT_PART outside its limits")
		return
	got.append_array(data)
	asking["data"] = got
	asking["parts"] = parts
	if int(fields["part"]) < parts - 1:
		return
	if Checkpointing.digest(got).hex_encode() != str(agreed.get(tick, "")):
		uploads_dropped.append([tick, int(conn["seat"]), "digest"])
		_ask_checkpoint(tick, asking["tried"])
		return
	uploads_kept.append([tick, int(conn["seat"])])
	checkpoints[tick] = got
	checkpoint_ticks.append(tick)
	while checkpoint_ticks.size() > NetProtocol.number("checkpoints_kept"):
		checkpoints.erase(checkpoint_ticks.pop_front())
	asking = {}


## RESYNC to one seat from the latest kept checkpoint (tick 0 without one), its parts and
## the turns since, behind which its live turns queue until the catch-up drains.
func _resync(conn: Dictionary, reason: String) -> void:
	var tick := _latest_kept()
	var bytes: PackedByteArray = checkpoints.get(tick, PackedByteArray())
	var digest: PackedByteArray = tick0 if tick == 0 else str(agreed[tick]).hex_decode()
	var parts := Checkpointing.split(tick, bytes)
	var first := tick / SimTypes.TURN_TICKS
	var queue := [
		NetProtocol.encode(
			"RESYNC",
			{
				"checkpoint_tick": tick,
				"first_turn": first,
				"reason": NetProtocol.enum_value("resync_reasons", reason),
				"open_turn": turn,
				"checkpoint_hash": digest,
				"parts": parts.size(),
			}
		)
	]
	for part: Dictionary in parts:
		queue.append(NetProtocol.encode("CHECKPOINT_PART", part))
	for k in range(first, turn):
		queue.append(_turn_bytes(k, turns[k]))
	conn["catchup"] = queue
	# (a rejoin's new connection counts from the checkpoint tick itself, as match.py's
	# tick - 1; the others from it, their reports on the way from before it let pass)
	conn["hash_tick"] = tick - 1 if reason == "rejoin" else tick
	conn["result"] = []
	conn["restart_at"] = tick + 60 if reason == "desync" else -1
	if reason == "behind":
		conn["behind_from"] = tick
	resync_log.append([turn, int(conn["seat"]), reason, tick])
	# (nothing goes before the next catchup_ms boundary: match.py's feed pumps it there)


## Once per catchup_ms, as catchup.py's pump: whole messages in order while this pump's
## bytes stay within catchup_bytes (the first message always goes) and the link's unsent
## output with the message, its bytes in flight, stays within catchup_output (a message
## larger than that only into an empty output).
func _pump(conn: Dictionary) -> void:
	var queue: Array = conn["catchup"]
	if queue.is_empty() or conn["link"].is_dropped():
		return
	var link = conn["link"]
	var spent := 0
	while not queue.is_empty():
		var message: PackedByteArray = queue[0]
		if spent > 0 and spent + message.size() > catchup_bytes:
			break
		var unsent: int = link.in_flight() if link.has_method("in_flight") else 0
		if unsent > 0 and unsent + message.size() > catchup_output:
			break
		queue.pop_front()
		spent += message.size()
		_send_bytes(conn, message)


## The same seat desynced again past max_resyncs: MATCH_END(desynced, desynced_twice) to
## it alone, LEFT in the turns, the caretaker keeps it; the others play on.
func _end_alone(conn: Dictionary, tick: int) -> void:
	_send(
		conn,
		"MATCH_END",
		{
			"outcome": NetProtocol.enum_value("outcomes", "desynced"),
			"reason": NetProtocol.enum_value("end_reasons", "desynced_twice"),
			"final_tick": tick,
		}
	)
	ended_alone.append(int(conn["seat"]))
	_leave(conn)
	conn["out"] = true
	conn["catchup"] = []


## A resume HELLO naming `seat` of match `match_id`: the seat back if this token holds it
## and it has not left; else NOTICE no_held_seat.
func _rejoin(conn: Dictionary, match_id: int, seat_no: int) -> void:
	var held := {}
	for c: Dictionary in conns:
		if c != conn and int(c["seat"]) == seat_no and c["token"] == conn["token"]:
			held = c
	if match_id != match_number or held.is_empty() or held["state"] == "left" or held["out"] or phase not in ["loading", "playing"]:
		no_held_seat += 1
		_send(conn, "NOTICE", {"code": NetProtocol.enum_value("notices", "no_held_seat"), "argument": 0})
		return
	if not held["link"].is_dropped():
		_send(held, "ERROR", {"code": NetProtocol.enum_value("errors", "replaced"), "text": "Replaced by another session"})
		held["link"].drop("Replaced by another session", 1008)
	for key: String in held:
		if key not in ["link", "hello", "token", "name"]:
			conn[key] = held[key]
	held["seat"] = -1
	held["replaced"] = true
	if lobby and not party.is_empty():
		var members: Array = party["members"]
		var i := members.find(held)
		if i >= 0:
			members[i] = conn
	conn["heard"] = world.frame
	conn["catchup"] = []
	_drop_reports(conn)  # (the old connection's, still waiting: its old simulation's)
	rejoins += 1
	if lobby:
		_broadcast_party()
	if phase == "loading":
		# (the match still loads: MATCH_CONFIG as at the start, and it loads like any seat)
		conn["loaded"] = []
		conn["per_mille"] = 0
		conn["visibility"] = 0
		_send(conn, "MATCH_CONFIG", configs[seat_no])
		_broadcast_load_state()
		return
	conn["visibility"] = 2  # (a rejoin counts as catching up until it says shown)
	# (its RESYNC's checkpoint proves its state, as the server's match.rejoin says: a seat
	# started without its player needs no LOADED to come BACK any more)
	conn["late"] = false
	conn["loaded"] = [_rules_of(_seated()), tick0]
	var config: Dictionary = (configs[seat_no] as Dictionary).duplicate()
	config["flags"] = NetProtocol.enum_value("config_flags", "rejoin")
	_send(conn, "MATCH_CONFIG", config)
	_resync(conn, "rejoin")


# ── The lobby (lobby mode) ──


## A member without a client, named `who`, with `main` as its Builder: it hosts the party
## when there is none, otherwise joins it. Its build is `build_base` + `build_offset`, and
## its rules hash this game's (`other_rules` 0) or another build's (1, 2, ...: each its own
## hash). Returns its record.
func add_member(who: String, main := "lamplighter", build_offset := 0, other_rules := 0) -> Dictionary:
	var link := QuietLink.new()
	accept(link)
	var conn: Dictionary = link.conn
	conn["virtual"] = true
	conn["hello"] = true
	conn["name"] = who
	conn["main"] = NetProtocol.enum_value("builders", main)
	conn["build_seq"] = maxi(0, build_base + build_offset)
	conn["rules_hash"] = rules_hash_of(other_rules)
	if party.is_empty():
		_create_party(conn, int(NetProtocol.spec()["modes"][mode]["id"]))
	else:
		conn["team"] = _smaller_team()
		conn["member"] = _free_row()
		(party["members"] as Array).append(conn)
	_broadcast_party()
	return conn


## Sets a member's "ready", "reload" (needs to reload, whatever its build), "main" (a
## Builder id) or "build" ([offset from build_base, other_rules]: it reloaded another build).
func set_member(who: String, key: String, value: Variant) -> void:
	var conn := member_conn(who)
	if conn.is_empty():
		return
	if key == "main":
		conn["main"] = NetProtocol.enum_value("builders", str(value))
	elif key == "build":
		conn["build_seq"] = maxi(0, build_base + int(value[0]))
		conn["rules_hash"] = rules_hash_of(int(value[1]))
	else:
		conn[key] = value
	_broadcast_party()


## A build's rules hash: this game's for 0, another for each other number.
func rules_hash_of(other_rules: int) -> PackedByteArray:
	if other_rules == 0:
		return SimContent.rules_hash()
	return PackedByteArray([0xEE, 0xEE, 0xEE, 0xEE, 0x0D, 0x0D, 0x0D, other_rules & 0xFF])


## A scripted member says goodbye: out of the party at once.
func remove_member(who: String) -> void:
	var conn := member_conn(who)
	if conn.is_empty():
		return
	_drop_member(conn)
	_interrupt_queue()
	conns.erase(conn)
	_broadcast_party()


## The rules hash the party plays: the newest build's (the highest build_seq, the leader's
## on a tie, then the earliest to join), as party.py's reference().
func _reference() -> PackedByteArray:
	var best := {}
	var members: Array = party.get("members", [])
	for m: Dictionary in members:  # (in joining order: the earlier wins a tie)
		if best.is_empty() or int(m["build_seq"]) > int(best["build_seq"]):
			best = m
		elif int(m["build_seq"]) == int(best["build_seq"]) and int(m["member"]) == int(party["leader"]):
			best = m
	return best.get("rules_hash", PackedByteArray())


## Whether a member needs to reload: another rules hash than the newest build's (or a
## test's "reload").
func _needs_reload(conn: Dictionary) -> bool:
	return bool(conn["reload"]) or (conn["rules_hash"] as PackedByteArray) != _reference()


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
			_interrupt_queue()
			conn["member"] = _free_row()
			conn["team"] = _smaller_team()
			members.append(conn)
			conn["ready"] = false
		"leave":
			_drop_member(conn)
			_interrupt_queue()
			_send_no_party(conn)
		"mode":
			if not leads or party["phase"] != "forming":
				return
			set_party_mode(NetProtocol.enum_name("modes", int(fields["mode"])))
			return
		"team":
			if not leads or party["phase"] != "forming" or _teams() < 2:
				return
			for m: Dictionary in members:
				if int(m["member"]) == int(fields["member"]):
					m["team"] = int(fields["team"])
					m["ready"] = false
		"open":
			if not leads or (int(fields["on"]) == 1 and _teams() > 1):
				return  # (open seats are a one-team mode's: a race's queue finds a rival team)
			if int(fields["on"]) == 0 and _teams() == 1:
				_interrupt_queue()
			party["open"] = int(fields["on"]) == 1
		"builders":
			conn["main"] = int(fields["main"])
			conn["backup"] = int(fields["backup"])
			if party.get("phase", "") != "queued":
				conn["ready"] = false  # (queued, a change is for the match found: it keeps the queue)
			_back(conn)
		"ready":
			_back(conn)
			if str(party.get("phase", "")) in ["queued", "loading"]:
				return  # (refused while queued or in the match, as on the server: the queue stays)
			conn["ready"] = int(fields["on"]) == 1
		"start":
			if phase == "loading":
				var waited: bool = world.frame - configured_at >= start_without_frames
				# (strangers never start without a seat: their barrier's timers decide, as the
				# server's Barrier.start_without refuses for them)
				if queue_match:
					return
				if leads and waited and _seated().any(func(c: Dictionary) -> bool: return not _loaded_of(c).is_empty()):
					started_without = true
				return
			var others_ready := members.all(
				func(m: Dictionary) -> bool: return m == conn or (m["ready"] and not _needs_reload(m))
			)
			if not leads or party["phase"] != "forming" or not others_ready or _needs_reload(conn):
				return
			party["phase"] = "countdown"
			party["countdown_at"] = world.frame + countdown_frames
		"cancel":
			if party.get("phase", "") == "countdown" and members.has(conn):
				party["phase"] = "forming"
		"difficulty":
			var level := int(fields["difficulty"])
			if MatchRules.level_name(level) == "":
				_refuse(conn, NetProtocol.enum_value("errors", "out_of_limits"), "PARTY difficulty outside its limits")
				return
			if (
				not leads
				or not str(party["phase"]) in ["forming", "countdown", "results"]
				or level == int(party.get("difficulty", 0))
			):
				_send_party(conn)  # (the party as it is, to the asker alone, as lobby.py's refuse)
				return
			party["difficulty"] = level
			if party["phase"] == "countdown":
				party["phase"] = "forming"
			for m: Dictionary in members:
				m["ready"] = false
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
		if resilience and int(conn["visibility"]) == 1 and world.frame - int(conn["heard"]) < hidden_silence_frames:
			continue  # (a hidden tab's loop sleeps: its link is kept, design 6.8, hidden_silence_ms)
		silenced.append(conn["name"])
		conn["link"].drop("Silent too long", 1001)
		if conn["seat"] >= 0 and phase == "playing" and resilience:
			continue  # (a dropped seat is held, AWAY after its silence: a resume takes it back)
		if conn["seat"] >= 0 and phase == "playing":
			_leave(conn)
		_drop_member(conn)
		_interrupt_queue()
		_broadcast_party()


# ── The queue (lobby mode, M6) ──


## A stranger in the queue, named `who`: a scripted party of one of its own with `main` and
## `backup`, queued now, after the strangers before it. `accepts`: it accepts a match found
## at once (else it waits for stranger_answer). Returns its record.
func add_stranger(
	who: String, main := "lamplighter", backup := "lookout", accepts := true, level := MatchRules.NORMAL
) -> Dictionary:
	var link := QuietLink.new()
	accept(link)
	var conn: Dictionary = link.conn
	conn["virtual"] = true
	conn["stranger"] = true
	conn["hello"] = true
	conn["name"] = who
	conn["main"] = NetProtocol.enum_value("builders", main)
	conn["backup"] = NetProtocol.enum_value("builders", backup)
	conn["accepts"] = accepts
	conn["difficulty"] = maxi(0, MatchRules.level_id(level))
	conn["build_seq"] = build_base
	conn["rules_hash"] = rules_hash_of(0)
	strangers.append(conn)
	_look()
	return conn


## Open seats on or off as the leader's PARTY open would (a scripted leader's).
func set_party_open(on: bool) -> void:
	if party.is_empty() or (on and _teams() > 1):
		return
	if not on and _teams() == 1:
		_interrupt_queue()
	party["open"] = on
	_broadcast_party()


## The party queues as its leader's QUEUE enter would (a scripted leader's, which sends
## nothing itself); false where the party may not queue.
func queue_party() -> bool:
	if not ticket.is_empty() or _queue_refusal() != "":
		return false
	ticket = {"since": world.frame, "offered": false, "told": false}
	party["phase"] = "queued"
	_broadcast_party()
	_tell_queue()
	_look()
	return true


## A scripted party member's answer to the match found.
func member_answer(who: String, yes := true) -> void:
	var conn := member_conn(who)
	if not conn.is_empty() and not found.is_empty():
		_accept(conn, int(found["id"]), yes)


## A stranger's answer to the match found (`yes`: accept; else decline).
func stranger_answer(who: String, yes := true) -> void:
	for conn: Dictionary in strangers:
		if conn["name"] == who and not found.is_empty():
			_accept(conn, int(found["id"]), yes)
			return


func _queue_op(conn: Dictionary, fields: Dictionary) -> void:
	var op := NetProtocol.enum_name("queue_ops", int(fields["op"]))
	if op == "":
		_refuse(conn, 6, "QUEUE outside its limits")
		return
	queue_log.append(op)
	var members: Array = party.get("members", [])
	var leads := members.has(conn) and int(party["leader"]) == int(conn["member"])
	match op:
		"enter":
			if leads and ticket.is_empty() and _queue_refusal() == "":
				ticket = {"since": world.frame, "offered": false, "told": false}
				party["phase"] = "queued"
				_broadcast_party()
				_tell_queue()
				_look()
				return
		"leave":
			if leads and not ticket.is_empty():
				if not found.is_empty():
					_dissolve([conn])  # (a leave in Match Found is a decline)
				else:
					_unqueue()
				return
		"start_with_caretakers":
			if leads and not ticket.is_empty() and found.is_empty() and bool(ticket["offered"]):
				_start_with_caretakers()
				return
	_send(conn, "QUEUE_STATE", _queue_fields())


## Why the party may not queue ("" where it may), as queue.py's refusal.
func _queue_refusal() -> String:
	if party.is_empty() or party["phase"] != "forming":
		return "phase"
	var members: Array = party["members"]
	for m: Dictionary in members:
		if _needs_reload(m):
			return "needs to reload"
		if int(m["member"]) != int(party["leader"]) and not m["ready"]:
			return "not ready"
	var most := int(NetProtocol.spec()["modes"][NetProtocol.enum_name("modes", int(party["mode"]))]["seats"][1])
	if _teams() == 1:
		if not bool(party.get("open", false)):
			return "open seats off"
		if members.size() >= most:
			return "no seat free"
		return ""
	var teams := {}
	for m: Dictionary in members:
		teams[int(m["team"])] = true
	if teams.size() != 1 or members.size() * 2 > most:
		return "team size"
	return ""


func _queue_fields() -> Dictionary:
	if ticket.is_empty():
		return {"state": NetProtocol.enum_value("queue_states", "idle"), "elapsed_ms": 0, "caretaker_offer": 0}
	return {
		"state": NetProtocol.enum_value("queue_states", "queued"),
		"elapsed_ms": (world.frame - int(ticket["since"])) * 1000 / FRAMES_PER_SECOND,
		"caretaker_offer": 1 if bool(ticket["offered"]) else 0,
	}


func _tell_queue() -> void:
	for m: Dictionary in party.get("members", []):
		_send(m, "QUEUE_STATE", _queue_fields())


func _notice_party(key: String) -> void:
	for m: Dictionary in party.get("members", []):
		_notice(m, key)


## Out of the queue, back to forming: QUEUE_STATE idle, then PARTY_STATE.
func _unqueue() -> void:
	ticket = {}
	if not party.is_empty() and party["phase"] == "queued":
		party["phase"] = "forming"
	_tell_queue()
	_broadcast_party()


## A join, a leave or open seats off: out of the queue (in Match Found, the party declines).
func _interrupt_queue() -> void:
	if ticket.is_empty():
		return
	if not found.is_empty():
		_dissolve([], true)
	else:
		ticket = {}
		if party["phase"] == "queued":
			party["phase"] = "forming"
		_tell_queue()


## Once a frame: the caretakers offered at offer_frames, Match Found's time running out.
func _tend_queue() -> void:
	if not ticket.is_empty() and not bool(ticket["offered"]) and world.frame - int(ticket["since"]) >= offer_frames:
		ticket["offered"] = true
		if found.is_empty():
			_say_offer()
	if not found.is_empty() and world.frame >= int(found["deadline"]):
		var late := (found["players"] as Array).filter(func(c: Dictionary) -> bool: return not (found["accepted"] as Array).has(c))
		_dissolve(late)


func _say_offer() -> void:
	if bool(ticket["offered"]) and not bool(ticket["told"]):
		ticket["told"] = true
		_notice_party("caretakers_offered")
	_tell_queue()


## The waiting strangers fill the party's open seats, or its race's rival team: Match Found.
func _look() -> void:
	if ticket.is_empty() or not found.is_empty():
		return
	var members: Array = party["members"]
	var most := int(NetProtocol.spec()["modes"][NetProtocol.enum_name("modes", int(party["mode"]))]["seats"][1])
	var need := members.size() if _teams() > 1 else most - members.size()
	# (the level is the queue's key with the mode and the rules hash: a stranger at another
	# level than the party's match plays waits for its own)
	var fitting := strangers.filter(func(c: Dictionary) -> bool: return _level_for(int(c["difficulty"])) == _match_level())
	if fitting.size() < need:
		return
	found_ids += 1
	found = {
		"id": found_ids, "players": members + fitting.slice(0, need), "accepted": [],
		"deadline": world.frame + accept_frames,
	}
	_tell_found()
	for c: Dictionary in fitting.slice(0, need):
		if c["accepts"]:
			_accept(c, found_ids, true)


func _tell_found() -> void:
	var fields := {
		"match": int(found["id"]), "mode": int(party["mode"]), "seats": (found["players"] as Array).size(),
		"accepted": (found["accepted"] as Array).size(),
		"ms_left": maxi(0, int(found["deadline"]) - world.frame) * 1000 / FRAMES_PER_SECOND,
	}
	founds_sent += 1
	for m: Dictionary in party.get("members", []):
		_send(m, "MATCH_FOUND", fields)


func _accept(conn: Dictionary, match_id: int, yes: bool) -> void:
	if found.is_empty() or int(found["id"]) != match_id or not (found["players"] as Array).has(conn):
		return  # (an answer to a match gone, or not this player's: let pass)
	if not yes:
		_dissolve([conn])
		return
	var accepted: Array = found["accepted"]
	if accepted.has(conn):
		return
	accepted.append(conn)
	if accepted.size() == (found["players"] as Array).size():
		_launch()
	else:
		_tell_found()


## The match found is off: `refusers` (and with `party_refused` the party itself) did not
## accept. The party back to forming if it refused, else to the front with NOTICE
## match_dissolved; a refusing stranger leaves the queue.
func _dissolve(refusers: Array, party_refused := false) -> void:
	var members: Array = party.get("members", [])
	for c: Dictionary in refusers:
		if members.has(c):
			party_refused = true
			c["ready"] = false
		else:
			strangers.erase(c)
	found = {}
	if party_refused:
		_unqueue()
		return
	_notice_party("match_dissolved")
	_say_offer()
	_look()


## Everyone accepted: a match of strangers, the party's seats first.
func _launch() -> void:
	var players: Array = (found["players"] as Array).duplicate()
	match_number = int(found["id"])
	found = {}
	ticket = {}
	var race := _teams() > 1
	var taken := []
	for c: Dictionary in players:
		strangers.erase(c)
		c["match_team"] = 1 if race and c["stranger"] else 0
		c["match_builder"] = int(c["main"])
		if not c["stranger"]:
			taken.append(int(c["main"]))  # (inside the party duplicates stay)
	# (strangers on one team never share a Builder: each in turn sees the party's and the
	# earlier strangers' taken, and plays its main, else its backup, else the first free one)
	for c: Dictionary in players:
		if not c["stranger"] or race:
			continue
		var builder := int(c["main"])
		if taken.has(builder):
			builder = int(c["backup"])
		if taken.has(builder):
			for id: String in SimContent.BUILDER_IDS:
				if not taken.has(NetProtocol.enum_value("builders", id)):
					builder = NetProtocol.enum_value("builders", id)
					break
		c["match_builder"] = builder
		taken.append(builder)
	_start_queue_match(players, [])


func _start_with_caretakers() -> void:
	ticket = {}
	match_number = found_ids + 1
	found_ids += 1
	var members := _party_seats()
	var race := _teams() > 1
	var extra := []
	var mains := []
	for c: Dictionary in members:
		c["match_team"] = 0
		c["match_builder"] = int(c["main"])
		mains.append(int(c["main"]))
	if race:
		for i in mains.size():
			extra.append({"team": 1, "builder": mains[i], "name": "Caretaker %d" % (i + 1)})
	else:
		var builders := caretaker_builders(mains, NetProtocol.number("max_seats") - members.size())
		for i in builders.size():
			extra.append({"team": 0, "builder": builders[i], "name": "Caretaker %d" % (i + 1)})
	_start_queue_match(members, extra)


func _start_queue_match(players: Array, extra: Array) -> void:
	party["phase"] = "loading"
	turns = []
	turn = 0
	origin = -1
	hashes = {}
	agreed = {}
	flagged = {}
	checkpoint_ticks = []
	checkpoints = {}
	asking = {}
	configs = {}
	disagreements = []
	compared = 0
	outcome = ""
	end_reason = ""
	final_tick = 0
	system_log = []
	_pending = []
	_system = []
	queue_match = extra.is_empty()
	for conn: Dictionary in conns:
		conn["seat"] = -1
	for conn: Dictionary in players:
		_reset_seat(conn)
	for conn: Dictionary in party["members"]:
		conn["ready"] = false
	seats = players.size() + extra.size()
	_next_load_state = world.frame + load_every
	_broadcast_party()
	_begin(players, extra)


## Caretakers' Builders (wire ids) for a team of `mains`, as queue.py's: each in turn the
## one covering most of the checks the team lacks, then one not on the team, ties in
## BUILDER_IDS order.
static func caretaker_builders(mains: Array, count: int) -> Array:
	var team := []
	for b: Variant in mains:
		team.append(SimContent.BUILDER_IDS[int(b)])
	var out := []
	for k in count:
		var lacking := []
		for check: String in SimContent.CHECK_IDS:
			var covered := false
			for name: String in team:
				if (SimContent.BUILDERS[name]["covers"] as Array).has(check):
					covered = true
			if not covered:
				lacking.append(check)
		var best := ""
		var best_key := []
		for i in SimContent.BUILDER_IDS.size():
			var name: String = SimContent.BUILDER_IDS[i]
			var covers := 0
			for check: String in lacking:
				if (SimContent.BUILDERS[name]["covers"] as Array).has(check):
					covers += 1
			var key := [-covers, 1 if team.has(name) else 0, i]
			if best == "" or key < best_key:
				best = name
				best_key = key
		team.append(best)
		out.append(NetProtocol.enum_value("builders", best))
	return out


func _create_party(conn: Dictionary, wire_mode: int) -> void:
	conn["member"] = 0
	conn["team"] = 0
	party = {
		"mode": wire_mode, "difficulty": MatchRules.level_id(MatchRules.NORMAL), "leader": conn["member"],
		"phase": "forming", "countdown_at": 0, "members": [conn], "open": false,
	}
	conn["ready"] = false


## The party's mode by name (a test's way to a race party the hub cannot pick yet): every
## Ready cleared, a two-team mode's teams laid out alternately by joining order.
func set_party_mode(mode_name: String) -> void:
	if party.is_empty():
		return
	party["mode"] = int(NetProtocol.spec()["modes"][mode_name]["id"])
	if _teams() > 1:
		party["open"] = false  # (a two-team mode has no open seats, as party.py's set_mode)
	var members: Array = party["members"]
	for i in members.size():
		members[i]["ready"] = false
		members[i]["team"] = i % 2 if _teams() > 1 else 0
	_broadcast_party()


## The party's level by name, sent as its leader's PARTY difficulty (a scripted leader's):
## the op's own rules, as lobby.py's, so every Ready is cleared and a countdown stopped, and
## while queued, loading or in a match, or at the level the party has, nothing changes and
## the leader alone hears the party as it is.
func set_party_difficulty(level: String) -> void:
	if party.is_empty() or not MatchRules.known(level):
		return
	for conn: Dictionary in party["members"]:
		if int(conn["member"]) == int(party["leader"]):
			_party_op(conn, {"op": "difficulty", "difficulty": MatchRules.level_id(level)})
			return


## The level (wire id) the match plays: the party's where its mode takes one (lobby mode),
## the dev match's otherwise; Normal in a mode without levels.
func _match_level() -> int:
	if lobby and not party.is_empty():
		return _level_for(int(party.get("difficulty", 0)))
	return MatchRules.level_id(MatchRules.level_of(mode, difficulty))


## The level (wire id) a match of the party's mode plays when `wire` is asked.
func _level_for(wire: int) -> int:
	var mode_name := NetProtocol.enum_name("modes", int(party.get("mode", 0)))
	return MatchRules.level_id(MatchRules.level_of(mode_name, MatchRules.level_name(wire)))


func _teams() -> int:
	return int(NetProtocol.spec()["modes"][NetProtocol.enum_name("modes", int(party.get("mode", 0)))]["teams"])


## The team a newcomer joins: the smaller (team 0 on a tie, and in a one-team mode).
func _smaller_team() -> int:
	if party.is_empty() or _teams() < 2:
		return 0
	var sizes := [0, 0]
	for m: Dictionary in party["members"]:
		sizes[clampi(int(m["team"]), 0, 1)] += 1
	return 0 if sizes[0] <= sizes[1] else 1


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
	flagged = {}
	checkpoint_ticks = []
	checkpoints = {}
	asking = {}
	configs = {}
	disagreements = []
	compared = 0
	outcome = ""
	end_reason = ""
	final_tick = 0
	system_log = []
	_pending = []
	_system = []
	match_number = 1
	queue_match = false
	for conn: Dictionary in conns:
		conn["seat"] = -1
	var players := _party_seats()
	for conn: Dictionary in players:
		_reset_seat(conn)
		conn["match_team"] = int(conn["team"]) if _teams() > 1 else 0
		conn["match_builder"] = -1
	_next_load_state = world.frame + load_every
	_broadcast_party()
	_begin(players)


## The party's members in seat order: by team, then by row in a two-team mode (party.py's
## seats()), in joining order otherwise (as the fake has always seated them).
func _party_seats() -> Array:
	var players: Array = (party["members"] as Array).duplicate()
	if _teams() > 1:
		players.sort_custom(
			func(a: Dictionary, b: Dictionary) -> bool:
				return [int(a["team"]), int(a["member"])] < [int(b["team"]), int(b["member"])]
		)
	return players


## A seat's state from before cleared, as a new match begins.
func _reset_seat(conn: Dictionary) -> void:
	conn["loaded"] = []
	conn["virtual_loaded"] = bool(conn["stranger"])  # (a stranger loads at once)
	if not conn["virtual"]:
		conn["per_mille"] = 0
	conn["hash_tick"] = -1
	conn["hashed"] = 0
	conn["result"] = []
	conn["last_seq"] = -1
	conn["state"] = "present"
	conn["resent"] = -1
	conn["catchup"] = []
	conn["resyncs"] = 0
	conn["restart_at"] = -1
	conn["behind_from"] = 0
	conn["asked"] = []
	conn["out"] = false


func _broadcast_party() -> void:
	if party.is_empty():
		return
	var fields := _party_fields()
	for conn: Dictionary in party["members"]:
		fields["you"] = conn["member"]  # (each member told its own row, as the server does)
		_send_bytes(conn, NetProtocol.encode("PARTY_STATE", fields))
		_count_party_state(conn)
	# NOTICE needs_reload (its member number) to each member that needs it now and did not
	# at the last change, as lobby.py's tell_reload
	for conn: Dictionary in party["members"]:
		var needs := _needs_reload(conn)
		if needs and not conn["told_reload"]:
			reload_notices.append(str(conn["name"]))
			var code := NetProtocol.enum_value("notices", "needs_reload")
			_send(conn, "NOTICE", {"code": code, "argument": int(conn["member"])})
		conn["told_reload"] = needs


## The party as it is, to `conn` alone (an op the party's rules refuse now, as lobby.py's refuse).
func _send_party(conn: Dictionary) -> void:
	if party.is_empty() or not (party["members"] as Array).has(conn):
		_send_no_party(conn)
		return
	var fields := _party_fields()
	fields["you"] = conn["member"]
	_send_bytes(conn, NetProtocol.encode("PARTY_STATE", fields))
	_count_party_state(conn)


func _count_party_state(conn: Dictionary) -> void:
	var who := str(conn["name"])
	party_states_sent[who] = int(party_states_sent.get(who, 0)) + 1


## PARTY_STATE's fields for the party as it is, `you` left for each member.
func _party_fields() -> Dictionary:
	var listed := []
	for conn: Dictionary in party["members"]:
		var state := "here"
		if _needs_reload(conn):
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
				"team": int(conn["team"]),
				"main": conn["main"],
				"backup": conn["backup"],
				"state": NetProtocol.enum_value("member_states", state),
				"rtt_ms": int(conn["rtt"]),
				"build_seq": int(conn["build_seq"]),
				"rules_hash": hash_bytes,
				"name": conn["name"],
			}
		)
	var left := maxi(0, int(party["countdown_at"]) - world.frame) * 1000 / FRAMES_PER_SECOND
	return {
		"code": party_code.to_ascii_buffer(),
		"mode": party["mode"],
		"difficulty": int(party.get("difficulty", 0)),
		"flags": NetProtocol.enum_value("party_flags", "open") if bool(party.get("open", false)) else 0,
		"leader": party["leader"],
		"you": 255,
		"phase": NetProtocol.enum_value("party_phases", party["phase"]),
		"countdown_ms": left if party["phase"] == "countdown" else 0,
		"members": listed,
	}


## The no-party state the server sends after a leave: five zero bytes, leader 255, nobody.
func _send_no_party(conn: Dictionary) -> void:
	conn["member"] = -1
	var fields := {
		"code": PackedByteArray([0, 0, 0, 0, 0]), "mode": 0, "difficulty": 0, "flags": 0, "leader": 255, "you": 255,
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


## Seat `seat`'s team in the match, from its MATCH_CONFIG's seat list.
func _team_of(seat: int) -> int:
	var seats: Array = configs.get(seat, {}).get("seats", [])
	return int(seats[seat]["team"]) if seat < seats.size() else 0


## The match's teams, as its mode on the wire says (a race has two): the party's mode in
## lobby mode, the dev match's otherwise.
func _match_teams() -> int:
	if lobby and not party.is_empty():
		return _teams()
	return int(NetProtocol.spec()["modes"].get(mode, {}).get("teams", 1))


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
	for entry: Dictionary in caretaker_seats:
		# (a caretaker's seat: nobody loads it, gone from the barrier)
		listed.append({"seat": entry["seat"], "per_mille": 0, "state": NetProtocol.enum_value("load_states", "gone")})
	listed.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["seat"]) < int(b["seat"]))
	_broadcast("LOAD_STATE", {"seats": listed, "seconds": (world.frame - configured_at) / FRAMES_PER_SECOND})


func _broadcast(type: String, fields: Dictionary) -> void:
	_broadcast_bytes(NetProtocol.encode(type, fields))


func _broadcast_bytes(bytes: PackedByteArray) -> void:
	for conn: Dictionary in _seated():
		if not conn["out"]:
			_send_bytes(conn, bytes)


func _send(conn: Dictionary, type: String, fields: Dictionary) -> void:
	_send_bytes(conn, NetProtocol.encode(type, fields))


func _send_bytes(conn: Dictionary, bytes: PackedByteArray) -> void:
	var link = conn["link"]
	link.push_down(bytes)
