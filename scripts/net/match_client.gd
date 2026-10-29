## One networked seat: the conversation with the server from HELLO to MATCH_END, and the
## simulation it feeds (design 6.3 to 6.7).
##
##   HELLO -> WELCOME -> (the server forms the match) MATCH_CONFIG -> the simulation is
##   built at tick 0 -> LOADED(rules hash, tick-0 hash) -> LOAD_STATE ... -> START ->
##   TURN(0), TURN(1), ... -> RESULT -> MATCH_END -> BYE
##
## The host drives it once a frame: poll() reads the link and answers the server, then
## the host steps the simulation by ticks_this_frame() ticks through `source` (a
## RemoteSequencer) and calls after_tick() after each, which sends HASH every 60 ticks
## and RESULT when the match is over. main.gd does that with its views; advance() does it
## alone for headless clients (tests/net/loopback_match.gd). The link is a NetLink, or a
## FakeLink in tests; the clock is milliseconds of any monotonic clock, so tests can
## count frames instead.
@warning_ignore_start("integer_division")
class_name MatchClient
extends RefCounted

## MATCH_CONFIG arrived: `sim`, `seat`, `seat_list` and `names` are set.
signal configured
## START arrived: turn 0 opens shortly.
signal started
## MATCH_END arrived (outcome and reason are named as in protocol.json).
signal ended(outcome: String, reason: String)
## The server refused us (ERROR) or the link dropped before the match ended.
signal failed(text: String)
## LINKS or LOAD_STATE changed what the party strip shows.
signal party_changed

enum Phase { IDLE, CONNECTING, HELLO, WAITING, LOADING, STARTING, PLAYING, ENDED, FAILED }

## Why orders go nowhere, for the player's notice (RemoteSequencer.closed_note).
const NOT_STARTED := "The match has not started"
const NO_LINK := "No link to the server"
const OVER := "The match is over"

const PHASE_NAMES := [
	"IDLE", "CONNECTING", "HELLO", "WAITING", "LOADING", "STARTING", "IN_MATCH", "ENDED", "FAILED"
]
## How a refused HELLO reads (ERROR codes, protocol.json).
const ERROR_TEXT := {
	"game_older": "A newer version is out: update the game",
	"server_older": "This server is older than the game",
	"bad_name": "Use 1-16 letters, digits, spaces, _ or -",
	"full": "The server is full",
	"rate": "Too many messages",
	"maintenance": "The server is closed for maintenance",
}

var link: NetLink
var source := RemoteSequencer.new()
var playout := Playout.new()
var sim: SimMatch
var phase := Phase.IDLE
## Milliseconds of a monotonic clock; Time.get_ticks_msec unless a test counts frames.
var clock := Callable()
## Whether a frame may also be cut short by real time (the 8 ms catch-up budget).
var timed := true

# What HELLO says.
var player_name := "Player"
var token := PackedByteArray()
var build_seq := 0
var hello_mode := "classic"
var web := false

# What the server said.
var session := 0
var identity := PackedByteArray()
var server_name := ""
var motd := ""
var hash_every := 60
var config := {}
var match_id := 0
var mode := ""
var match_seed := 0
## My seat in the simulation (1-based); 0 before MATCH_CONFIG.
var seat := 0
## The simulation's seat list ({"team", "builder", "caretaker"}), by seat - 1.
var seat_list := []
## Display names, round trips (ms) and link flags (hidden 1, silent 2), by seat - 1.
var names: Array[String] = []
var rtts: Array[int] = []
var link_flags: Array[int] = []
## LOAD_STATE: [per mille, state] by seat - 1.
var load_states: Array = []
## My own round trip to the server (ms) and the server's open turn as PONG said it.
var rtt_ms := 0
var server_turn := 0
var outcome := ""
var end_reason := ""
var final_tick := -1
var error_code := 0
var error_text := ""
var notices: Array = []
var result_sent := false
var hashes_sent := 0
## Every HASH sent: tick -> hash hex.
var sent_hashes := {}
## My seat's refused commands as [seq, command type, reason], oldest first.
var refusals: Array = []
## Frames left during which this client neither reads its link nor steps (a test's stall).
var stalled_frames := 0

var _ping_every := 2000
var _last_ping_at := -1
var _ping_slow := false
var _last_frame_at := -1
var _gap_asked := -1
var _gap_asked_at := 0
## Asking again for the same missing turn waits this long (protocol.json turn_request_ms).
var _turn_request_ms := 500
var _frozen := false


func _init() -> void:
	source.send = _send_command
	source.open = false
	source.closed_note = NOT_STARTED
	source.clock = _now


## Joins the server at a typed address (see NetAddress) or a ws:// URL.
func join(address: String) -> bool:
	var url := NetAddress.url(address)
	if url == "":
		_fail("Not a server address: " + address)
		return false
	return connect_with(NetLink.new(), url)


## Opens `with_link` (a NetLink, or a FakeLink in tests) to `url` and says HELLO once open.
func connect_with(with_link: NetLink, url: String) -> bool:
	link = with_link
	if token.is_empty():
		token = Crypto.new().generate_random_bytes(NetProtocol.number("token_bytes"))
	_ping_every = NetProtocol.number("ping_ms")
	_turn_request_ms = NetProtocol.number("turn_request_ms")
	phase = Phase.CONNECTING
	if link.open(url) != OK:
		_fail(link.close_reason)
		return false
	return true


## The phase as scenarios read it: "WAITING", "IN_MATCH", "ENDED", ... (design 7.2's
## `phase()`; `phase` itself is the enum).
func phase_name() -> String:
	return PHASE_NAMES[phase]


## Reads the link and answers it: once a frame, before stepping.
func poll() -> void:
	var now := _now()
	if _last_frame_at >= 0 and now - _last_frame_at > Playout.SLOW_FRAME_MS:
		_ping_slow = true
	_last_frame_at = now
	_frozen = stalled_frames > 0
	if _frozen:
		stalled_frames -= 1
		return
	if link == null:
		return
	link.poll()
	if phase == Phase.CONNECTING and link.is_open():
		_say_hello()
	for message: PackedByteArray in link.receive():
		_handle(message, now)
	if link.is_closed() and phase not in [Phase.ENDED, Phase.FAILED, Phase.IDLE]:
		if phase == Phase.CONNECTING:
			_fail("No server answers at " + link.url)
		elif link.close_code == 1008:
			# (a refusal whose ERROR did not arrive: the server closes with 1008)
			_fail("The server refused a message from this game")
		else:
			_fail(link.close_reason if link.close_reason != "" else "The connection closed")
		return
	if not link.is_open():
		return
	if phase >= Phase.WAITING and phase <= Phase.PLAYING:
		if _last_ping_at < 0 or now - _last_ping_at >= _ping_every:
			_ping(now)
	if phase == Phase.PLAYING:
		_ask_for_gaps(now)


## Ticks the host should run this frame.
func ticks_this_frame() -> int:
	if phase != Phase.PLAYING or sim == null or sim.over or _frozen:
		return 0
	return playout.ticks_for_frame(source.ticks_available(sim))


## After each simulated tick: HASH every hash_every ticks, RESULT once the match is over.
func after_tick(tick: int) -> void:
	if sim == null or phase != Phase.PLAYING:
		return
	if tick % hash_every == 0:
		var digest := sim.state_hash()
		_send("HASH", {"tick": tick, "hash": digest, "flags": 0})
		sent_hashes[tick] = digest.hex_encode()
		hashes_sent += 1
	if sim.over and not result_sent and not sim.aborted:
		result_sent = true
		_send("RESULT", {"tick": tick, "hash": sim.state_hash(), "outcomes": _outcomes()})


## Steps the simulation alone (a headless client): poll, run this frame's ticks, read
## the events. Returns the ticks run.
func advance() -> int:
	poll()
	if sim == null:
		return 0
	var budget := ticks_this_frame()
	var ran := 0
	# (one tick at a time: the match's last tick is the last one run, as in main.gd)
	while ran < budget and not sim.over and source.advance(sim, 1, after_tick) == 1:
		ran += 1
	observe(sim.drain_events())
	return ran


## Notes my seat's refusals from the simulation's events (the host drains them).
func observe(events: Array) -> void:
	for e: Dictionary in events:
		if int(e["type"]) == SimTypes.EV_REJECTED and int(e["seat"]) == seat:
			refusals.append([int(e["seq"]), int(e["cmd"]), int(e["reason"])])


## Sends a command from my seat: `type` is a SimTypes number or a name ("BUILD").
## Returns its sequence number, or -1 when the match takes no commands now.
func cmd(type: Variant, a := 0, b := 0, c := 0) -> int:
	var number: int = SimTypes.command_type(type) if type is String else int(type)
	return source.submit(number, a, b, c)


## The name of my last refused command's reason ("NOT_YOURS"), or "".
func last_refusal() -> String:
	return SimTypes.refusal_name(int(refusals[-1][2])) if not refusals.is_empty() else ""


## Leaves the match (the caretaker keeps the seat) and says goodbye.
func leave() -> void:
	if phase in [Phase.LOADING, Phase.STARTING, Phase.PLAYING]:
		_send("LEAVE_MATCH")
	close()


## Says goodbye and closes the link.
func close() -> void:
	if link and link.is_open():
		_send("BYE")
		link.close(1000, "Goodbye")
	source.open = false
	if source.closed_note == "" or source.closed_note == NOT_STARTED:
		source.closed_note = NO_LINK


## A seat's link quality for the party strip: 0 (none) to 3 bars, from its round trip.
static func bars_for(rtt: int, flags: int) -> int:
	if flags & 2:
		return 0
	if rtt <= 0 or rtt < 120:
		return 3
	if rtt < 250:
		return 2
	return 1


# ── Messages ──


func _handle(bytes: PackedByteArray, now: int) -> void:
	var message := NetProtocol.decode(bytes)
	if message.has("error"):
		push_warning("MatchClient: " + str(message["error"]))
		return
	var fields: Dictionary = message["fields"]
	match str(message["type"]):
		"WELCOME":
			_on_welcome(fields)
		"ERROR":
			error_code = int(fields["code"])
			var key := NetProtocol.enum_name("errors", error_code)
			error_text = str(fields["text"])
			_fail(str(ERROR_TEXT.get(key, error_text)))
		"NOTICE":
			notices.append([int(fields["code"]), int(fields["argument"])])
		"PONG":
			_on_pong(fields, now)
		"MATCH_CONFIG":
			_on_config(fields)
		"LOAD_STATE":
			load_states = []
			for entry: Dictionary in fields["seats"]:
				load_states.append([int(entry["per_mille"]), int(entry["state"])])
			party_changed.emit()
		"START":
			if phase == Phase.LOADING:
				phase = Phase.STARTING
				source.open = true
				source.closed_note = ""
				started.emit()
		"TURN":
			if phase == Phase.STARTING or phase == Phase.PLAYING:
				phase = Phase.PLAYING
				if not source.receive_turn(int(fields["turn"]), fields["commands"]):
					_fail("The server sent turn %d, out of reach" % int(fields["turn"]))
		"LINKS":
			for entry: Dictionary in fields["seats"]:
				var i := int(entry["seat"])
				if i < rtts.size():
					rtts[i] = int(entry["rtt_ms"])
					link_flags[i] = int(entry["flags"])
			party_changed.emit()
		"MATCH_END":
			_on_end(fields)
		"BYE":
			link.close(1000, "The server said goodbye")
		"CHECKPOINT_ASK", "RESYNC":
			pass  # M4: checkpoints and resyncs


func _on_welcome(fields: Dictionary) -> void:
	session = int(fields["session"])
	identity = fields["identity"]
	server_name = str(fields["server_name"])
	motd = str(fields["motd"])
	hash_every = int(fields["hash_every"])
	playout.turn_ms = int(fields["turn_ms"])
	playout.turn_ticks = int(fields["turn_ticks"])
	# (a dev match may keep shorter turns, 5 ms at the least; none is longer than 1 s)
	if (
		playout.turn_ticks != SimTypes.TURN_TICKS
		or hash_every != SimTypes.HASH_EVERY
		or playout.turn_ms < 5
		or playout.turn_ms > 1000
	):
		_fail("This server keeps other turns than the game")
		return
	phase = Phase.WAITING


func _on_pong(fields: Dictionary, now: int) -> void:
	server_turn = int(fields["turn"])
	var sent := int(fields["client_ms"])
	var rtt := (now - sent) & 0xFFFFFFFF
	if rtt > 60000:
		return  # not one of ours
	rtt_ms = rtt
	if not _ping_slow:
		playout.add_sample(rtt)


func _on_config(fields: Dictionary) -> void:
	if phase != Phase.WAITING:
		return
	config = fields
	match_id = int(fields["match"])
	mode = NetProtocol.enum_name("modes", int(fields["mode"]))
	match_seed = int(fields["seed"])
	if not SimContent.RULES.has(mode):
		_fail("This game cannot play the server's mode (%d)" % int(fields["mode"]))
		return
	var mine := SimContent.rules_hash(mode)
	if mine != (fields["rules_hash"] as PackedByteArray):
		_fail("The server's rules differ from this game's: update the game")
		return
	seat_list = []
	names = []
	rtts = []
	link_flags = []
	var listed: Array = fields["seats"]
	if int(fields["your_seat"]) >= listed.size():
		_fail("MATCH_CONFIG gives this game no seat")
		return
	# (the mode bounds the seats and their teams, as the simulation assumes: a config
	# outside them fails the link here instead of half-building a simulation)
	var mode_spec: Dictionary = NetProtocol.spec()["modes"][mode]
	var seat_range: Array = mode_spec["seats"]
	if listed.size() < int(seat_range[0]) or listed.size() > int(seat_range[1]):
		_fail("MATCH_CONFIG lists %d seats, outside the mode's" % listed.size())
		return
	var known_flags := 0
	for flag: Variant in NetProtocol.spec()["seat_flags"].values():
		known_flags |= int(flag)
	for i in listed.size():
		var entry: Dictionary = listed[i]
		if int(entry["seat"]) != i:
			_fail("MATCH_CONFIG lists its seats out of order")
			return
		if int(entry["team"]) >= int(mode_spec["teams"]):
			_fail("MATCH_CONFIG puts a seat on team %d, outside the mode" % int(entry["team"]))
			return
		if int(entry["flags"]) & ~known_flags:
			_fail("MATCH_CONFIG gives a seat flags this game does not know")
			return
		var builder := NetProtocol.enum_name("builders", int(entry["builder"]))
		if not SimContent.BUILDERS.has(builder):
			builder = "lamplighter"  # (M1 has one Builder; M2 brings the rest)
		seat_list.append(
			{
				"team": int(entry["team"]),
				"builder": builder,
				"caretaker": (int(entry["flags"]) & 1) != 0,
			}
		)
		names.append(str(entry["name"]))
		rtts.append(0)
		link_flags.append(0)
	seat = int(fields["your_seat"]) + 1
	source.seat = seat
	sim = SimMatch.new(SimContent.rules(mode), seat_list, match_seed)
	phase = Phase.LOADING
	configured.emit()
	# The hollow is already built at boot: loading is done once the simulation stands.
	_send("LOADING", {"per_mille": 1000})
	_send("LOADED", {"rules_hash": mine, "tick0_hash": sim.state_hash()})
	party_changed.emit()


func _on_end(fields: Dictionary) -> void:
	outcome = NetProtocol.enum_name("outcomes", int(fields["outcome"]))
	end_reason = NetProtocol.enum_name("end_reasons", int(fields["reason"]))
	final_tick = int(fields["final_tick"])
	phase = Phase.ENDED
	source.open = false
	source.closed_note = OVER
	close()
	ended.emit(outcome, end_reason)


# ── Sending ──


func _send(type: String, fields := {}) -> void:
	if link == null or not link.is_open():
		return
	var bytes := NetProtocol.encode(type, fields)
	if bytes.is_empty():
		push_error("MatchClient: " + NetProtocol.last_error)
		return
	link.send(bytes)


func _send_command(seq: int, type: int, a: int, b: int, c: int) -> void:
	_send("CMD", {"seq": seq, "type": type, "a": a, "b": b, "c": c})


func _ping(now: int) -> void:
	_last_ping_at = now
	_ping_slow = false
	_send("PING", {"client_ms": now & 0xFFFFFFFF, "rtt_ms": mini(rtt_ms, 0xFFFF)})


## TURN_REQUEST for the first missing turn: the same gap again after turn_request_ms; a
## gap that moved (the last answer came) after half of that and a turn more. The server
## answers a seat at most once per half of turn_request_ms, so a request sooner would be
## ignored and the gap left waiting a whole turn_request_ms (review M1 protocol 2).
func _ask_for_gaps(now: int) -> void:
	var gap := source.first_gap()
	if gap < 0:
		return
	var wait := _turn_request_ms if gap == _gap_asked else _turn_request_ms / 2 + playout.turn_ms
	if _gap_asked >= 0 and now - _gap_asked_at < wait:
		return
	_gap_asked = gap
	_gap_asked_at = now
	_send("TURN_REQUEST", {"first_missing": gap})


func _say_hello() -> void:
	var flags := 2 if web else 0
	_send(
		"HELLO",
		{
			"version": NetProtocol.number("version"),
			"build_seq": build_seq,
			"rules_hash": SimContent.rules_hash(hello_mode),
			"token": token,
			"flags": flags,
			"name": player_name,
		}
	)
	phase = Phase.HELLO


func _outcomes() -> Array:
	var list := []
	for team in sim.teams:
		# (a team's hollow DONE is a win, FALLEN a loss)
		var h := sim.hollows[team.hollows[0]]
		list.append({"outcome": 0 if h.phase == SimTypes.PHASE_DONE else 1})
	return list


func _fail(text: String) -> void:
	if phase == Phase.FAILED:
		return
	phase = Phase.FAILED
	source.open = false
	source.closed_note = NO_LINK
	if error_text == "":
		error_text = text
	if link and not link.is_closed():
		link.close(1000, "")
	failed.emit(text)


func _now() -> int:
	return int(clock.call()) if clock.is_valid() else Time.get_ticks_msec()
