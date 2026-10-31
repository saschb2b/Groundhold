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
##
## The session (scripts/session/session.gd) keeps one MatchClient as its connection to a
## server for as long as it stays: `keep_link` holds the link open after MATCH_END and
## lets the next MATCH_CONFIG start a new match (rearm), `defer_loaded` waits for the host
## to build the hollow before LOADED (loaded()), and the hub's messages (PARTY_STATE,
## QUEUE_STATE, MATCH_FOUND, NOTICE) go out on `hub_message`. Without them (--join, the
## loopback tests) it plays one match exactly as in M1.
##
## Resilience (M4: design 6.7 and 6.8, shared/net/README.md Resilience):
## - Checkpoints. At every hash tick `checkpoints` (Checkpointing) serializes the state
##   once: its digest is the HASH, and at a checkpoint tick it keeps the bytes (the last
##   two) and flags the HASH; CHECKPOINT_ASK uploads them in parts.
## - RESYNC (rejoin, desync, behind): the parts are put together and checked, the
##   simulation is loaded from them (or built again at tick 0), the turns from the
##   checkpoint's run again, and `resynced` tells the host to rebuild its views.
## - Catching up: more than Playout.CATCH_UP_TURNS behind (after a RESYNC, a hidden tab, a
##   late load) the client says VISIBILITY catching_up, refuses orders ("Catching up") and
##   runs the turns as fast as the playout lets it; at the goal it says shown, which brings
##   its seat BACK, and the caretaker hands it back at the next build window.
## - Reconnect. A link lost mid-match (no ERROR, no goodbye) keeps the simulation and opens
##   a new link every reconnect_ms (2 s; `link_factory` makes it) with a resume HELLO: the
##   same token, the match and the wire seat held. MATCH_CONFIG(rejoin) and RESYNC(rejoin)
##   follow; NOTICE no_held_seat ends the match for this game ("aborted"). A link silent for
##   away_ms (5 s) in a match while the tab shows is lost too (SILENT_LINK): dropped without
##   a close, and reconnected. From the loss to the RESYNC(rejoin) no HASH or RESULT goes out.
## - Holding the words: no HASH or RESULT goes out while a RESYNC may replace what runs
##   (_hash_hold): after a lost link, and after its own catching_up until the server's answer
##   is known (_answer_pending: the PONG behind it names a turn, and a RESYNC comes first).
## - A hidden browser tab (WebBridge, or a test): set_hidden() says VISIBILITY hidden; on
##   return catching_up when behind, else shown.
## - Started without: START before LOADED; it says catching_up, steps nothing until its
##   LOADED went out, and catches up (from a RESYNC(behind), or from tick 0).
## - A match ending desynced writes DesyncDump's file (`dump_path`).
## connection_state() is what the ConnectionOverlay shows.
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
## WELCOME arrived: the server knows us.
signal welcomed
## A hub message for the session: PARTY_STATE, QUEUE_STATE, MATCH_FOUND or NOTICE.
signal hub_message(type: String, fields: Dictionary)
## The simulation was replaced from a RESYNC's checkpoint (or built again at tick 0): the
## host rebuilds its views from `sim`.
signal resynced
## Reconnecting, catching up or hidden changed (the connection overlay).
signal connection_changed

enum Phase { IDLE, CONNECTING, HELLO, WAITING, LOADING, STARTING, PLAYING, ENDED, FAILED }

## Why orders go nowhere, for the player's notice (RemoteSequencer.closed_note).
const NOT_STARTED := "The match has not started"
const NO_LINK := "No link to the server"
const OVER := "The match is over"
const RECONNECTING_NOTE := "Reconnecting to the server"
const CATCHING_UP_NOTE := "Catching up"
## A reconnect that no server has welcomed for this long gives up: the match is lost to
## this game ("The connection closed"), and the session's way back to the hub follows.
const GIVE_UP_MS := 30000
## In a match the server speaks every turn (50 ms), and PONGs and LINKS every 2 s: a link
## that brings nothing for as long as the server waits before it calls a seat AWAY
## (protocol.json away_ms, 5 s) has gone silent without a close (Wi-Fi lost, a stalled
## router), which TCP may take minutes to report. It is dropped and reconnected as a lost
## link. A frame longer than STALL_MS is this game's own stall (a hitch, a laptop waking),
## and its time does not count toward the silence.
const STALL_MS := 1000
const SILENT_LINK := "The server went silent"
## remember_seat: how far ahead of the commands sent the noted sequence floor is raised, so
## user://net.cfg is written once per this many commands.
const SEQ_BLOCK := 64
## VISIBILITY's states (protocol.json visibility_states).
const SHOWN := 0
const HIDDEN := 1
const CATCHING_UP := 2

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
	"replaced": "This seat was taken back from another window",
}

var link: NetLink
var source: RemoteSequencer
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
var web := false
## The seat a resume HELLO asks back (docs/design/contract-m4.md): the match id and the wire
## seat (0-based) this game held when its link dropped; 0 and 255 for none.
var held_match := 0
var held_seat := 255
## This game's seat is noted in user://net.cfg from MATCH_CONFIG to MATCH_END
## (Identity.hold_seat), so the game started again after a kill or a crash asks it back
## (resume_seat); the session sets it for --join games. Off in the loopback tests.
var remember_seat := false
## The first HELLO of this game is a resume naming a seat it held before it was started
## again (resume_seat): MATCH_CONFIG(rejoin) builds the match, RESYNC(rejoin) brings it to
## the open turn. NOTICE no_held_seat forgets the seat, and the game joins afresh.
var boot_resume := false
## The session's connection: the link outlives a match (see the top of this file).
var keep_link := false
## LOADED waits for loaded(), sent once the host has built the hollow.
var defer_loaded := false

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
## LOAD_STATE: [per mille, state] by seat - 1, and the seconds since MATCH_CONFIG it gave.
var load_states: Array = []
var load_seconds := 0
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
## TURN_REQUESTs sent (each asks for the first missing turn again).
var turn_requests := 0
## Every HASH sent: tick -> hash hex.
var sent_hashes := {}
## My seat's refused commands as [seq, command type, reason], oldest first.
var refusals: Array = []
## Frames left during which this client neither reads its link nor steps (a test's stall).
var stalled_frames := 0
## Whether LOADED went out for this match.
var loaded_sent := false

# Resilience (M4; see the top of this file).
var checkpoints := Checkpointing.new()
## () -> NetLink: a new link for a reconnect (NetLink.new() without; tests hand FakeLinks).
var link_factory := Callable()
## The link went mid-match and the client is getting its seat back (until the RESYNC's
## checkpoint is loaded).
var reconnecting := false
## The reconnect gave up (GIVE_UP_MS): the server holds the seat to the match's end, and the
## caretaker plays it there.
var gave_up := false
## Links opened again after a loss, resume HELLOs sent on them, and rejoins completed (a
## RESYNC(rejoin) loaded).
var reconnect_attempts := 0
var resumes := 0
var rejoins := 0
## Running turns it missed: from catch_up_from to catch_up_goal (ticks); orders wait.
var catching_up := false
var catch_up_from := 0
var catch_up_goal := 0
## Every RESYNC loaded, as [reason name, checkpoint tick, open turn], oldest first.
var resyncs: Array = []
## The browser tab is hidden (WebBridge; scene.hide() in tests).
var hidden := false
## The last VISIBILITY state sent (SHOWN, HIDDEN, CATCHING_UP).
var said_visibility := SHOWN
## START came before this game's LOADED: the match started without it.
var started_without := false
## CHECKPOINT_ASKs answered with parts, and asked for a tick no longer kept.
var uploads := 0
var asks_unanswered := 0
## Where the desync dump went (DesyncDump.path_for), "" for none.
var dump_path := ""

var _ping_every := 2000
var _last_ping_at := -1
## When this link last brought a message (silence counted from it, see STALL_MS), and how
## long it may stay silent in a match (away_ms).
var _heard_at := -1
var _silent_ms := 5000
var _ping_slow := false
var _last_frame_at := -1
var _gap_asked := -1
var _gap_asked_at := 0
## Asking again for the same missing turn waits this long (protocol.json turn_request_ms).
var _turn_request_ms := 500
var _frozen := false
var _hello_sent := false
## This link's HELLO is a resume, and WELCOME came on it.
var _resuming := false
var _resume_welcomed := false
## A boot resume got NOTICE no_held_seat: the next poll opens a new link with a plain HELLO.
var _join_afresh := false
## remember_seat: the sequence floor noted for my seat (Identity.note_floor), raised a block
## at a time as my commands go out; for a boot resume, the earlier run's.
var _seq_floor := 0
var _reconnect_ms := 2000
var _reconnect_at := -1
## When the link was lost, and why (the reason a reconnect that gives up says).
var _lost_at := -1
var _lost_reason := ""
var _bye := false
## The RESYNC being loaded (its fields, "reason" named), {} for none.
var _resync := {}
## The tab came back: catching_up or shown is decided after the next read.
var _returning := false
## Back during the match from another tab or a dropped link (a rejoin): once level again,
## the overlay says the caretaker hands back at the next build window while it still
## holds the seat.
var _returned := false
## No HASH and no RESULT go out: what runs now may be replaced by a RESYNC, after which the
## server counts this seat's HASH ticks again from its checkpoint, so a HASH of this run
## reaching it after that would be below the checkpoint tick, out of order ("HASH ticks
## must increase"), and a RESULT of it would take the re-run's place. Set when the client
## says catching_up on its own (a tab back, a late load: a RESYNC(behind) may be on its
## way) and when the link is lost (the RESYNC(rejoin) replaces the run). Held until a
## RESYNC is loaded (its re-run hashes from the checkpoint on), or, for catching_up, until
## the catch-up has ended and the server's answer is known (_answer_pending).
var _hash_hold := false
## The server's answer to this game's own catching_up is not known yet. A PING goes out
## right behind the VISIBILITY (or the LOADED of a game started without); its PONG names
## the server's open turn at that moment (_answer_turn). The server queues every turn
## sealed after a RESYNC behind that RESYNC (catchup.py), so a TURN numbered _answer_turn
## or later that arrives with no RESYNC before it says none was sent.
var _answer_pending := false
var _answer_pong := 0
var _answer_turn := -1
## PINGs sent and PONGs read on this link (each PONG answers the PINGs in order).
var _pings_out := 0
var _pongs_in := 0


func _init() -> void:
	_new_source()


func _new_source() -> void:
	source = RemoteSequencer.new()
	source.send = _send_command
	source.open = false
	source.closed_note = NOT_STARTED
	source.clock = _now


## After a match on a kept link: back to waiting for the next MATCH_CONFIG, with a fresh
## turn source and nothing of the last match (the session calls it on the way to the hub).
func rearm() -> void:
	if phase != Phase.ENDED or link == null or not link.is_open():
		return
	_new_source()
	sim = null
	config = {}
	match_id = 0
	mode = ""
	seat = 0
	seat_list = []
	names = []
	rtts = []
	link_flags = []
	load_states = []
	load_seconds = 0
	outcome = ""
	end_reason = ""
	final_tick = -1
	result_sent = false
	hashes_sent = 0
	sent_hashes = {}
	refusals = []
	loaded_sent = false
	_gap_asked = -1
	checkpoints = Checkpointing.new()
	_end_resilience()
	resyncs = []
	started_without = false
	said_visibility = SHOWN
	uploads = 0
	asks_unanswered = 0
	dump_path = ""
	phase = Phase.WAITING


## The hollow is built (defer_loaded): LOADING at 1000 and LOADED with the rules hash and
## the simulation's tick-0 hash, once per match.
## A game the match started without (START before its LOADED) sends it all the same, as
## it begins catching up: its LOADED brings the seat back once it is live (design 6.6).
func loaded() -> void:
	if sim == null or loaded_sent:
		return
	if phase != Phase.LOADING and not (started_without and phase in [Phase.STARTING, Phase.PLAYING]):
		return
	loaded_sent = true
	var tick0 := sim.state_hash() if sim.tick == 0 else _tick0_hash()
	_send("LOADING", {"per_mille": 1000})
	_send("LOADED", {"rules_hash": SimContent.rules_hash(), "tick0_hash": tick0})
	if started_without:
		_begin_catch_up()  # (from where it stands to the turns here now)


## Sends a hub message (PARTY, QUEUE, ACCEPT, LEAVE_MATCH) on the open link.
func send(type: String, fields := {}) -> void:
	_send(type, fields)


## Before join(): this game was started again and held wire seat `wire_seat` of `match_id`
## on that server (Identity.held_seat), so its first HELLO is a resume naming that seat;
## its earlier run numbered its commands below `seq_floor`.
func resume_seat(match_id_held: int, wire_seat: int, seq_floor := 0) -> void:
	if match_id_held <= 0 or wire_seat < 0 or wire_seat > 3:
		return
	held_match = match_id_held
	held_seat = wire_seat
	_seq_floor = maxi(0, seq_floor)
	boot_resume = true
	_resuming = true


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
	_reconnect_ms = NetProtocol.number("reconnect_ms")
	_silent_ms = NetProtocol.number("away_ms")
	_hello_sent = false
	_heard_at = _now()
	_pings_out = 0
	_pongs_in = 0
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
		if now - _last_frame_at > STALL_MS and _heard_at >= 0:
			_heard_at += now - _last_frame_at  # (this game stalled: not the server's silence)
	_last_frame_at = now
	_frozen = stalled_frames > 0
	if _frozen:
		stalled_frames -= 1
		return
	if link == null:
		return
	if reconnecting and not _resume_welcomed and now - _lost_at >= GIVE_UP_MS:
		# (30 s without the seat back, however the new link stands: closed, still connecting
		# (a SYN black-holed, which the system may wait minutes on) or open with no WELCOME)
		gave_up = true
		_fail(_lost_reason, true)
		return
	if reconnecting and link.is_closed():
		if now >= _reconnect_at:
			_open_again(now)
		return
	link.poll()
	if link.is_open() and not _hello_sent and (phase == Phase.CONNECTING or _resuming):
		_say_hello()
	for message: PackedByteArray in link.receive():
		_heard_at = now
		_handle(message, now)
	if _silent(now):
		# (no close came, and none may for minutes: dropped, and taken back as a lost link)
		link.abort(SILENT_LINK)
		if _may_rejoin():
			_lose_link(now)
		else:
			_fail(SILENT_LINK)
		return
	if _join_afresh:
		# (the seat it asked back is not held any more: a plain HELLO on a new link)
		_join_afresh = false
		var url := link.url
		if link.is_open():
			_send("BYE")
			link.close(1000, "Goodbye")
		connect_with(link_factory.call() if link_factory.is_valid() else NetLink.new(), url)
		return
	if link.is_closed() and phase not in [Phase.ENDED, Phase.FAILED, Phase.IDLE]:
		if _may_rejoin():
			_lose_link(now)
			return
		if phase == Phase.CONNECTING:
			_fail("No server answers at " + link.url)
		elif link.close_code == 1008:
			# (a refusal whose ERROR did not arrive: the server closes with 1008)
			_fail("The server refused a message from this game")
		else:
			_fail(link.close_reason if link.close_reason != "" else "The connection closed")
		return
	if not link.is_open() or (_resuming and not _resume_welcomed):
		return
	if _returning and not reconnecting:
		# (the tab is back: catching_up or shown is its first word, before the PING due
		# since the hide or a TURN_REQUEST, so neither is taken for the seat being back)
		_returning = false
		if _behind():
			_begin_catch_up()
		else:
			_say_visibility(SHOWN)
	if phase >= Phase.WAITING and phase <= Phase.PLAYING:
		if _last_ping_at < 0 or now - _last_ping_at >= _ping_every:
			_ping(now)
	if phase == Phase.PLAYING:
		_ask_for_gaps(now)
	_check_caught_up()
	if _returned and not hidden and not catching_up and not reconnecting and _resync.is_empty():
		if not _caretaken():
			_returned = false  # (the seat is its own again, or never stopped being)
			connection_changed.emit()


## Ticks the host should run this frame.
func ticks_this_frame() -> int:
	if phase != Phase.PLAYING or sim == null or sim.over or _frozen:
		return 0
	if started_without and not loaded_sent:
		return 0  # (its hollow is still building: it starts once LOADED went out)
	if not _resync.is_empty():
		return 0  # (the checkpoint's parts are on their way: what runs now goes)
	return playout.ticks_for_frame(source.ticks_available(sim))


## After each simulated tick: HASH every hash_every ticks, RESULT once the match is over.
func after_tick(tick: int) -> void:
	if sim == null or phase != Phase.PLAYING:
		return
	if tick % hash_every == 0:
		# (the state is serialized once: its digest is the hash, and at a checkpoint tick
		# the bytes are kept and the HASH flagged)
		var flags := checkpoints.at_hash_tick(sim, tick)
		var digest := checkpoints.last_hash
		if not _hash_hold:
			_send("HASH", {"tick": tick, "hash": digest, "flags": flags})
			sent_hashes[tick] = digest.hex_encode()
			hashes_sent += 1
	if sim.over and not _hash_hold:
		_send_result(tick)


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
	_release_seat()
	close()


## Says goodbye and closes the link (and gives up a reconnect).
func close() -> void:
	reconnecting = false
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
			if _resuming and not boot_resume:
				_on_resume_welcome(fields)
			else:
				_on_welcome(fields)
				_resume_welcomed = boot_resume
		"ERROR":
			error_code = int(fields["code"])
			var key := NetProtocol.enum_name("errors", error_code)
			error_text = str(fields["text"])
			_fail(str(ERROR_TEXT.get(key, error_text)))
		"NOTICE":
			notices.append([int(fields["code"]), int(fields["argument"])])
			hub_message.emit("NOTICE", fields)
			if _resuming and int(fields["code"]) == NetProtocol.enum_value("notices", "no_held_seat"):
				if boot_resume:
					_forget_boot_seat()
				else:
					_seat_gone()
		"PARTY_STATE", "QUEUE_STATE", "MATCH_FOUND":
			hub_message.emit(str(message["type"]), fields)
		"PONG":
			_on_pong(fields, now)
		"MATCH_CONFIG":
			if int(fields["flags"]) & NetProtocol.enum_value("config_flags", "rejoin"):
				_on_rejoin_config(fields)
			elif boot_resume:
				_on_loading_rejoin(fields)
			else:
				_on_config(fields)
		"LOAD_STATE":
			load_states = []
			for entry: Dictionary in fields["seats"]:
				load_states.append([int(entry["per_mille"]), int(entry["state"])])
			load_seconds = int(fields["seconds"])
			party_changed.emit()
		"START":
			if phase == Phase.LOADING:
				phase = Phase.STARTING
				source.open = true
				source.closed_note = ""
				if not loaded_sent:
					# (the match started without this game: it says so, and catches up)
					started_without = true
					_begin_catch_up()
				started.emit()
		"TURN":
			if phase == Phase.STARTING or phase == Phase.PLAYING:
				phase = Phase.PLAYING
				if not source.receive_turn(int(fields["turn"]), fields["commands"]):
					_fail("The server sent turn %d, out of reach" % int(fields["turn"]))
				elif _answer_pending and _answer_turn >= 0 and int(fields["turn"]) >= _answer_turn:
					# (no RESYNC came before it: none answers this game's catching_up)
					_answer_pending = false
					if not catching_up and not reconnecting and _resync.is_empty():
						_release_hold()
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
			_bye = true
			link.close(1000, "The server said goodbye")
		"CHECKPOINT_ASK":
			_on_checkpoint_ask(int(fields["tick"]))
		"RESYNC":
			_on_resync(fields)
		"CHECKPOINT_PART":
			_on_part(fields)


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
	welcomed.emit()


func _on_pong(fields: Dictionary, now: int) -> void:
	server_turn = int(fields["turn"])
	_pongs_in += 1
	if _answer_pending and _pongs_in == _answer_pong:
		_answer_turn = server_turn  # (the open turn as the server read our catching_up)
	var sent := int(fields["client_ms"])
	var rtt := (now - sent) & 0xFFFFFFFF
	if rtt > 60000:
		return  # not one of ours
	rtt_ms = rtt
	if not _ping_slow:
		playout.add_sample(rtt)


## MATCH_CONFIG: the match, built at tick 0. `rejoin`: a game started again takes its held
## seat back mid-match (boot_resume): it sends no LOADED, takes no orders, and waits for
## the RESYNC(rejoin) that follows.
func _on_config(fields: Dictionary, rejoin := false) -> void:
	if phase == Phase.ENDED and keep_link:
		rearm()  # (the next match on the session's link, before the hub called rearm)
	if phase != Phase.WAITING:
		return
	config = fields
	match_id = int(fields["match"])
	mode = NetProtocol.enum_name("modes", int(fields["mode"]))
	match_seed = int(fields["seed"])
	if not SimContent.RULES.has(mode):
		_fail("This game cannot play the server's mode (%d)" % int(fields["mode"]))
		return
	var mine := SimContent.rules_hash()
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
		# (a Builder whose views this build lacks is fielded as a Lamplighter, the same on
		# every client: Profile.fielded)
		var builder := Profile.fielded(NetProtocol.enum_name("builders", int(entry["builder"])))
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
	checkpoints.restart_at(sim, PackedByteArray())
	if not rejoin:
		_seq_floor = 0
	if remember_seat:
		Identity.hold_seat(link.url, match_id, seat - 1, _seq_floor)
	if rejoin:
		source.continue_from(_seq_floor)  # (above every number its earlier run may have sent)
		phase = Phase.STARTING
		loaded_sent = true
		source.closed_note = RECONNECTING_NOTE
		configured.emit()
		party_changed.emit()
		connection_changed.emit()
		return
	phase = Phase.LOADING
	loaded_sent = false
	configured.emit()
	if not defer_loaded:
		# The hollow is already built at boot: loading is done once the simulation stands.
		loaded()
	party_changed.emit()


func _on_end(fields: Dictionary) -> void:
	outcome = NetProtocol.enum_name("outcomes", int(fields["outcome"]))
	end_reason = NetProtocol.enum_name("end_reasons", int(fields["reason"]))
	final_tick = int(fields["final_tick"])
	phase = Phase.ENDED
	source.open = false
	source.closed_note = OVER
	_release_seat()
	_end_resilience()
	if outcome == "desynced" and sim != null:
		# (either way, two seats apart or this seat twice: a report to compare, design 6.7)
		dump_path = DesyncDump.write(self, checkpoints, final_tick)
	if not keep_link:
		close()
	ended.emit(outcome, end_reason)


# ── Resilience (M4) ──


## The tab was hidden (true) or shown again (false): VISIBILITY hidden now; on return
## catching_up when it is behind, else shown, once it has read what came meanwhile.
func set_hidden(now_hidden: bool) -> void:
	if now_hidden == hidden:
		return
	hidden = now_hidden
	_heard_at = _now()  # (a hidden tab's link may sleep: its silence counts from the return)
	if hidden:
		_returning = false
		_say_visibility(HIDDEN)
	else:
		_returning = true
		# (its own simulation learns of the AWAY only as it runs the turns it missed)
		_returned = phase == Phase.PLAYING
	connection_changed.emit()


## What the connection overlay shows: [ConnectionOverlay.State, bar per mille (-1 none),
## a second line].
func connection_state() -> Array:
	if phase == Phase.ENDED and outcome == "desynced":
		var more := ConnectionOverlay.REPORT_SAVED if dump_path != "" else ""
		return [ConnectionOverlay.State.DESYNCED, -1, more]
	if reconnecting or boot_resume or (not _resync.is_empty() and str(_resync["reason"]) == "rejoin"):
		var got: Array = checkpoints.download_progress()
		var bar := int(got[0]) * 1000 / int(got[1]) if int(got[1]) > 0 else -1
		return [ConnectionOverlay.State.RECONNECTING, bar, ""]
	if hidden:
		return [ConnectionOverlay.State.IN_ANOTHER_TAB, -1, ""]
	if catching_up or not _resync.is_empty():
		return [ConnectionOverlay.State.CATCHING_UP, catch_up_per_mille(), ""]
	if _returned and _caretaken():
		# (back from another tab or a dropped link and level again: the caretaker holds the
		# seat until the next build window opens, and the seat's own orders wait till then)
		return [ConnectionOverlay.State.BACK, -1, _hand_back_line()]
	return [ConnectionOverlay.State.NONE, -1, ""]


## When the caretaker hands my seat back: as the next build window opens, so after the
## wave that runs, or while a window is open after the wave that comes.
func _hand_back_line() -> String:
	var h := sim.hollows[sim.seat(seat).hollow]
	if h.phase == SimTypes.PHASE_PREP:
		return ConnectionOverlay.BACK_AFTER_NEXT_WAVE
	return ConnectionOverlay.BACK_AFTER_WAVE


## Whether the caretaker plays my seat now (away, returning, or for good).
func _caretaken() -> bool:
	return sim != null and seat > 0 and sim.seat(seat).state != SimTypes.SEAT_PRESENT


## How far the catch-up has come, per mille of the ticks it set out to run.
func catch_up_per_mille() -> int:
	if sim == null or catch_up_goal <= catch_up_from:
		return 0
	return clampi((sim.tick - catch_up_from) * 1000 / (catch_up_goal - catch_up_from), 0, 1000)


## The tick-0 hash LOADED carries: the simulation's own at tick 0, or one built again from
## MATCH_CONFIG when it has run past it.
func _tick0_hash() -> PackedByteArray:
	return SimMatch.new(SimContent.rules(mode), seat_list, match_seed).state_hash()


## Whether the open link has brought nothing for _silent_ms in a match, while this tab
## shows (a hidden tab reads nothing, and its link is the server's to keep or close).
func _silent(now: int) -> bool:
	if phase not in [Phase.STARTING, Phase.PLAYING] or hidden or not link.is_open() or _heard_at < 0:
		return false
	return now - _heard_at >= _silent_ms


## Whether a lost link may be taken back: in a match that started, with no ERROR and no
## goodbye from the server.
func _may_rejoin() -> bool:
	if phase not in [Phase.STARTING, Phase.PLAYING] or match_id == 0 or seat <= 0:
		return false
	if error_code != 0 or _bye or link.close_code == 1008:
		return false
	return true


func _lose_link(now: int) -> void:
	if not reconnecting:
		reconnecting = true
		_lost_at = now
		_lost_reason = link.close_reason if link.close_reason != "" else "The connection closed"
		held_match = match_id
		held_seat = seat - 1
		source.open = false
		source.closed_note = RECONNECTING_NOTE
		_resync = {}
		checkpoints.end_download()
		connection_changed.emit()
	# (what runs from the turns it holds is replaced by the RESYNC(rejoin): none of its
	# HASHes may follow the resume HELLO, below the checkpoint the server counts from)
	_hash_hold = true
	_answer_pending = false
	_resuming = false
	_resume_welcomed = false
	_reconnect_at = now + _reconnect_ms


## A new link to the same server for a resume HELLO.
func _open_again(now: int) -> void:
	_reconnect_at = now + _reconnect_ms
	reconnect_attempts += 1
	var url := link.url
	link = link_factory.call() if link_factory.is_valid() else NetLink.new()
	_resuming = true
	_resume_welcomed = false
	_hello_sent = false
	_last_ping_at = -1
	_heard_at = now
	_pings_out = 0
	_pongs_in = 0
	link.open(url)  # (closed at once when it cannot: the next attempt in reconnect_ms)


func _on_resume_welcome(fields: Dictionary) -> void:
	session = int(fields["session"])
	identity = fields["identity"]
	server_name = str(fields["server_name"])
	motd = str(fields["motd"])
	_resume_welcomed = true


## MATCH_CONFIG(rejoin): the match as it began; RESYNC(rejoin) follows. A game started
## again (boot_resume) builds the match from it, at tick 0, and catches up from the RESYNC.
func _on_rejoin_config(fields: Dictionary) -> void:
	if not (reconnecting or boot_resume) or int(fields["match"]) != held_match or int(fields["your_seat"]) != held_seat:
		_fail("The server rejoined this game to another seat")
		return
	if boot_resume:
		_on_config(fields, true)
		return
	config = fields


## A plain MATCH_CONFIG to a game started again (boot_resume): its match still loads, and
## the server took the seat back as at the start (shared/net/README.md, Rejoin: "loads
## like any seat"). The resume is over: the game loads and plays as any seat.
func _on_loading_rejoin(fields: Dictionary) -> void:
	if int(fields["match"]) != held_match or int(fields["your_seat"]) != held_seat:
		_fail("The server rejoined this game to another seat")
		return
	boot_resume = false
	_resuming = false
	_resume_welcomed = false
	_on_config(fields)


## NOTICE no_held_seat to a game started again: the seat it noted is not held (the match
## ended, the seat left): forgotten, and the game says HELLO again as a newcomer.
func _forget_boot_seat() -> void:
	if remember_seat:
		Identity.release_seat(link.url, held_match)
	boot_resume = false
	_resuming = false
	_resume_welcomed = false
	held_match = 0
	held_seat = 255
	_join_afresh = true


## The seat noted for a game started again is given up (the match is over for this game).
func _release_seat() -> void:
	if remember_seat and match_id > 0 and link != null:
		Identity.release_seat(link.url, match_id)


## NOTICE no_held_seat: the match ended, or the seat left, while this game was away.
func _seat_gone() -> void:
	_release_seat()
	_end_resilience()
	outcome = "aborted"
	end_reason = "no_held_seat"
	phase = Phase.ENDED
	source.open = false
	source.closed_note = OVER
	if not keep_link:
		close()
	ended.emit(outcome, end_reason)


## CHECKPOINT_ASK: the kept bytes in parts, or nothing when the tick is no longer kept.
func _on_checkpoint_ask(tick: int) -> void:
	var parts := checkpoints.upload(tick)
	if parts.is_empty():
		asks_unanswered += 1
		return
	uploads += 1
	for part: Dictionary in parts:
		_send("CHECKPOINT_PART", part)


func _on_resync(fields: Dictionary) -> void:
	if sim == null or phase not in [Phase.STARTING, Phase.PLAYING]:
		_fail("The server sent a RESYNC outside a match")
		return
	var tick := int(fields["checkpoint_tick"])
	var first := int(fields["first_turn"])
	var parts := int(fields["parts"])
	var reason := NetProtocol.enum_name("resync_reasons", int(fields["reason"]))
	if (
		tick % hash_every != 0
		or first * SimTypes.TURN_TICKS != tick
		or int(fields["open_turn"]) < first
		# (no further than a TURN may be: the turn log is rebased to `first` once loaded)
		or int(fields["open_turn"]) > source.complete_upto + 1 + RemoteSequencer.MAX_TURNS_AHEAD
		or parts > NetProtocol.number("max_checkpoint_parts")
		or (parts == 0) != (tick == 0)
		or reason == ""
		or (reason == "rejoin") != (reconnecting or boot_resume)
	):
		_fail("The server sent a RESYNC outside its limits")
		return
	_resync = fields.duplicate()
	_resync["reason"] = reason
	_answer_pending = false  # (this is the answer; its re-run hashes once it is loaded)
	checkpoints.begin_download(tick, parts, fields["checkpoint_hash"])
	connection_changed.emit()
	if parts == 0:
		_load_resync(PackedByteArray())


func _on_part(fields: Dictionary) -> void:
	if _resync.is_empty() or not checkpoints.add_part(fields):
		_fail("The server sent a checkpoint part out of order")
		return
	if not checkpoints.download_done():
		return
	var bytes := checkpoints.downloaded()
	if bytes.is_empty():
		_fail("The server's checkpoint does not match its hash")
		return
	_load_resync(bytes)


## Loads the RESYNC's checkpoint (tick 0: builds it again), drops what ran past it, and
## catches up from there to the open turn.
func _load_resync(bytes: PackedByteArray) -> void:
	var tick := int(_resync["checkpoint_tick"])
	var loaded: SimMatch
	if tick == 0:
		loaded = SimMatch.new(SimContent.rules(mode), seat_list, match_seed)
	else:
		loaded = SimMatch.deserialize(bytes, SimContent.rules(mode))
	var expected: PackedByteArray = _resync["checkpoint_hash"]
	if loaded == null or loaded.tick != tick or loaded.state_hash() != expected:
		_fail("The server's checkpoint does not load")
		return
	var reason := str(_resync["reason"])
	var open_turn := int(_resync["open_turn"])
	sim = loaded
	checkpoints.restart_at(sim, bytes)
	checkpoints.end_download()
	source.rebase(int(_resync["first_turn"]))
	for t: int in sent_hashes.keys():
		if t > tick:
			sent_hashes.erase(t)
	result_sent = false
	resyncs.append([reason, tick, open_turn])
	_resync = {}
	# (a tab back meanwhile needs no catch-up of its own: this one runs to the open turn,
	# its HASHes going out, and says shown at its end; a second would hold them and cut
	# its goal short of the turns still on their way)
	_returning = false
	if reason == "rejoin":
		reconnecting = false
		_resuming = false
		boot_resume = false
		rejoins += 1
		said_visibility = CATCHING_UP  # (a rejoin counts as catching up until it says shown)
		_returned = true  # (once level, the plate says when the caretaker hands back)
	phase = Phase.PLAYING
	_begin_catch_up(open_turn * SimTypes.TURN_TICKS, true)
	resynced.emit()


## More than Playout.CATCH_UP_TURNS behind: orders wait, VISIBILITY says so, and the turns
## run as fast as the playout lets them, up to `goal` (ticks; the turns here by default).
## `from_resync`: the re-run of a RESYNC's turns, whose HASHes go out; else they are held
## (_hash_hold) until a RESYNC comes or the catch-up ends.
func _begin_catch_up(goal := -1, from_resync := false) -> void:
	if sim == null:
		return
	_hash_hold = not from_resync
	_answer_pending = false
	catching_up = true
	catch_up_from = sim.tick
	catch_up_goal = goal if goal >= 0 else (source.highest + 1) * SimTypes.TURN_TICKS
	source.open = false
	source.closed_note = CATCHING_UP_NOTE
	_say_visibility(CATCHING_UP)
	if not from_resync and link != null and link.is_open() and not reconnecting:
		# (the PING whose PONG lets the TURNs tell whether a RESYNC answers it)
		_ping(_now())
		_answer_pending = true
		_answer_pong = _pings_out
		_answer_turn = -1
	connection_changed.emit()


func _behind() -> bool:
	if sim == null or phase != Phase.PLAYING:
		return false
	var ahead := (source.highest + 1) * SimTypes.TURN_TICKS - sim.tick
	return ahead > Playout.CATCH_UP_TURNS * SimTypes.TURN_TICKS


## The goal is reached and what is buffered is a playout's worth again: shown (which brings
## the seat BACK), and orders go out again.
func _check_caught_up() -> void:
	if not catching_up or sim == null or not _resync.is_empty() or reconnecting:
		return
	if started_without and not loaded_sent:
		return
	# (a simulation over is as far as it goes: its RESULT, held meanwhile, may go)
	if sim.tick < catch_up_goal and not sim.over:
		return
	if source.ticks_available(sim) > Playout.CATCH_UP_TURNS * SimTypes.TURN_TICKS and not sim.over:
		return
	catching_up = false
	if not _answer_pending:
		_release_hold()
	if not hidden:
		_say_visibility(SHOWN)
	if phase == Phase.PLAYING:
		source.open = true
		source.closed_note = ""
	connection_changed.emit()


func _say_visibility(state: int) -> void:
	if state == said_visibility:
		return
	said_visibility = state
	_send("VISIBILITY", {"state": state})


## The run is the match's again (no RESYNC replaces it): HASHes go out from the next hash
## tick, and a RESULT the hold kept back goes now.
func _release_hold() -> void:
	_hash_hold = false
	if sim != null and sim.over:
		_send_result(sim.tick)


func _send_result(tick: int) -> void:
	if result_sent or sim.aborted or phase != Phase.PLAYING:
		return
	result_sent = true
	_send("RESULT", {"tick": tick, "hash": sim.state_hash(), "outcomes": _outcomes()})


## The match is over or the link failed: no reconnect, catch-up or download goes on.
func _end_resilience() -> void:
	reconnecting = false
	catching_up = false
	_hash_hold = false
	_answer_pending = false
	_resuming = false
	_resume_welcomed = false
	boot_resume = false
	_join_afresh = false
	_returning = false
	_returned = false
	_resync = {}
	held_match = 0
	held_seat = 255
	checkpoints.end_download()


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
	if remember_seat and seq >= _seq_floor and match_id > 0 and link != null:
		# (noted before it goes: a game killed after this restarts above it)
		_seq_floor = seq + SEQ_BLOCK
		Identity.note_floor(link.url, match_id, seat - 1, _seq_floor)
	_send("CMD", {"seq": seq, "type": type, "a": a, "b": b, "c": c})


func _ping(now: int) -> void:
	_last_ping_at = now
	_ping_slow = false
	_pings_out += 1
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
	turn_requests += 1
	_send("TURN_REQUEST", {"first_missing": gap})


func _say_hello() -> void:
	var flags := 2 if web else 0
	if _resuming:
		flags |= NetProtocol.enum_value("hello_flags", "resume")
		resumes += 1
	_hello_sent = true
	_send(
		"HELLO",
		{
			"version": NetProtocol.number("version"),
			"build_seq": build_seq,
			"rules_hash": SimContent.rules_hash(),
			"token": token,
			"flags": flags,
			"name": player_name,
			"match": held_match,
			"seat": held_seat,
		}
	)
	if not _resuming or boot_resume:
		phase = Phase.HELLO


func _outcomes() -> Array:
	var list := []
	for team in sim.teams:
		# (a team's hollow DONE is a win, FALLEN a loss)
		var h := sim.hollows[team.hollows[0]]
		list.append({"outcome": 0 if h.phase == SimTypes.PHASE_DONE else 1})
	return list


## The link failed, or the server refused this game: nothing more goes on. `keep_seat`: a
## reconnect that gave up, whose seat the server holds to the match's end, so the game
## started again asks it back (remember_seat).
func _fail(text: String, keep_seat := false) -> void:
	if phase == Phase.FAILED:
		return
	if not keep_seat:
		_release_seat()
	_end_resilience()
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
