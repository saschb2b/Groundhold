## A scripted player for the hub, against a real server (tools/net/smoke.py --flow and the
## tests/net/live/ party scenarios). The game booted with --server=ADDRESS --flow-bot hands
## the hub to it (Session.boot), and it goes through the loop by itself:
##
##   connect and make a party (or join the one --code names, or whose code --code-in's file
##   holds once it appears, and again whenever the file changes while the code it tried
##   found no party: a file left from an earlier run) -> a member says Ready; the leader
##   says Start once --party=N
##   members are there and Ready -> the 3-2-1, the loading barrier and the match run as the
##   session runs them (--bot lets the plan bot play the seat) -> on the results it waits
##   a moment and presses Play again -> back in the party, every member here again.
##
## With --queue (smoke.py --flow --queue) it plays the queue instead, a party of one of its
## own: open seats on, Find players, Accept on Match Found, the match of strangers, and on
## the results Play again, which queues it again: done once it is queued again (before the
## next Match Found, which the server may send in the same breath as QUEUE_STATE: so it
## reads the session's queue, not only its state, which may skip QUEUED within a frame).
## With --mode=undertow (or tide_race; the hub makes the party in it, Session's boot flag)
## the party is one side of a two-team mode: no open seats, Find a rival (M7); a party in
## another mode than the one asked for (a build without the mode's rules) is a failure.
##
## It prints one line per step for the tool reading its output:
##   FLOW party <code> members <n> me <row> leader|member
##   FLOW state <the session's state>
##   FLOW queued <code>                          (--queue: the server's QUEUE_STATE queued)
##   FLOW found <match> seats <n>                (--queue: Match Found, accepted)
##   FLOW match <mode> seat <k> of <n> builders <b1,b2,...>   (as this build fields them)
##   FLOW config builders <b1,b2,...>            (MATCH_CONFIG's, as the server chose them)
##   FLOW results <outcome> <the results' title>
##   FLOW back <code> members <n> phase <phase>
##   FLOW notice <text>   FLOW failed <why>
## Flags: --code-out=FILE writes the party's code to FILE once made; --ready-calls says
## Ready in every build window, so the waves come at once (a short match; in a duel with --bot
## once the plan bot has corked and built in the window both hollows share); --matches=N
## plays N matches before it is done (default 1); --quit-after-flow quits when done (exit
## 0) or on a failure (exit 1); --linger=S stays S seconds on the results before Play again
## (the server closes a connection silent for 15 s: the plate must keep it).
extends Node

## Frames on the results before Play again (the plate is read, as a player would).
const RESULTS_FRAMES := 90
## Frames between two asks of the same thing (Ready, Start) while the answer is on its way.
const ASK_FRAMES := 30
## --queue: frames in the hub after Play again before it counts as not queued again.
const REQUEUE_FRAMES := 600

var flags := {}
## Frames on the results before Play again (--linger, else RESULTS_FRAMES).
var results_frames := RESULTS_FRAMES
var party_size := 2
var matches := 1
var played := 0
var done := false
## --queue: the queue instead of a party by code.
var queue := false
var _said_queued := false

var _frame := 0
var _joined := false
var _code_tried := ""
var _code_written := false
var _last_state := ""
var _last_party := ""
var _asked_at := -1000
var _results_at := -1
var _in_match := false


func _init() -> void:
	name = "FlowBot"
	process_mode = Node.PROCESS_MODE_ALWAYS


func setup(boot: Dictionary) -> void:
	flags = boot
	queue = boot.has("queue")
	party_size = 1 if queue else maxi(1, int(boot.get("party", "2")))
	matches = maxi(1, int(boot.get("matches", "1")))
	if boot.has("linger"):
		results_frames = maxi(RESULTS_FRAMES, int(float(str(boot["linger"])) * Engine.physics_ticks_per_second))


func _ready() -> void:
	Session.noticed.connect(func(text: String) -> void: print("FLOW notice %s" % text))
	var code := Session.clean_code(str(flags.get("code", "")))
	if code == "" and flags.has("code-in"):
		return  # (waits for the file the host writes)
	_connect(code)


func _connect(code: String) -> void:
	_joined = true
	_code_tried = code
	if not Session.connect_to(str(flags["server"]), code):
		_fail("not a server address: %s" % flags["server"])


## A joiner whose code found no party (a file left from an earlier run, read before the
## host wrote its own) tries again once the file holds another code.
func _join_again() -> void:
	if not flags.has("code-in") or not Session.party.is_empty() or _frame % ASK_FRAMES != 0:
		return
	var path := str(flags["code-in"])
	if not FileAccess.file_exists(path):
		return
	var code := Session.clean_code(FileAccess.get_file_as_string(path).strip_edges())
	if Session.code_ok(code) and code != _code_tried:
		_code_tried = code
		Session.join_code(code)


func _physics_process(_delta: float) -> void:
	_frame += 1
	if done:
		return
	if not _joined:
		_wait_for_code()
		return
	var state := Session.state_name()
	if state != _last_state:
		_last_state = state
		print("FLOW state %s" % state)
		if state == "OFFLINE":
			_fail(Session.last_notice if Session.last_notice != "" else "the connection went")
			return
	_say_party()
	match state:
		"HUB":
			_join_again()
			_in_hub()
		"QUEUED", "MATCH_FOUND":
			_in_queue()
		"IN_MATCH":
			_play()
		"RESULTS":
			_on_results()


func _wait_for_code() -> void:
	var path := str(flags["code-in"])
	if not FileAccess.file_exists(path):
		return
	var code := Session.clean_code(FileAccess.get_file_as_string(path).strip_edges())
	if Session.code_ok(code):
		_connect(code)


## Prints the party whenever its code, size or my row changes; writes --code-out once.
func _say_party() -> void:
	if Session.party.is_empty() or Session.me < 0:
		return
	var line := "FLOW party %s members %d me %d %s" % [
		Session.party_code(), Session.party_size(), Session.me, "leader" if Session.is_leader() else "member"
	]
	if line != _last_party:
		_last_party = line
		print(line)
	if flags.has("code-out") and not _code_written:
		_code_written = true
		var file := FileAccess.open(str(flags["code-out"]), FileAccess.WRITE)
		if file:
			file.store_line(Session.party_code())
			file.close()


func _in_hub() -> void:
	if Session.party.is_empty() or Session.me < 0:
		return
	if queue:
		_queue_from_hub()
		return
	if played > 0 and _back_together():
		print("FLOW back %s members %d phase %s" % [Session.party_code(), Session.party_size(), Session.party["phase"]])
		if played >= matches:
			_done(0)
			return
	if str(Session.party["phase"]) != "forming" or Session.party_size() < party_size:
		return
	if _frame - _asked_at < ASK_FRAMES:
		return
	var button := Session.primary()
	if Session.is_leader():
		if button["act"] == "start" and button["enabled"]:
			_asked_at = _frame
			Session.play()
	elif not Session.my_ready():
		_asked_at = _frame
		Session.set_ready(true)


## --queue in the hub: open seats on, then Find players; after a match Play again queues by
## itself, and a hub that stays forming is a failure.
func _queue_from_hub() -> void:
	if played > 0:
		if Session.queue_request == "" and _frame - _asked_at > REQUEUE_FRAMES:
			_fail("Play again left the party forming, not queued again")
		return
	if str(Session.party["phase"]) != "forming" or _frame - _asked_at < ASK_FRAMES:
		return
	_asked_at = _frame
	var wanted := str(flags.get("mode", ""))
	if wanted != "" and Session.mode_id() != wanted:
		_fail("the party plays %s, not %s: this build does not offer %s" % [Session.mode_id(), wanted, wanted])
		return
	if not Session.is_race(Session.mode_id()) and not Session.open_seats():
		Session.set_open(true)
		return
	var button := Session.primary()
	if button["act"] == "queue" and button["enabled"]:
		Session.play()


## --queue, queued or in Match Found: the first time Match Found's Accept; after a match,
## queued again by Play again, and done.
func _in_queue() -> void:
	if not queue or Session.party.is_empty():
		return
	if not _said_queued and str(Session.queue.get("state", "")) == "queued":
		_said_queued = true
		print("FLOW queued %s" % Session.party_code())
	if played > 0:
		if _said_queued:
			print("FLOW back %s members %d phase %s" % [Session.party_code(), Session.party_size(), Session.party["phase"]])
			_done(0)
		return
	if Session.state == Session.State.MATCH_FOUND:
		_on_found()


## Match Found: Accept, once.
func _on_found() -> void:
	if Session.found.is_empty() or str(Session.found["answer"]) != "":
		return
	print("FLOW found %d seats %d" % [int(Session.found["match"]), int(Session.found["seats"])])
	Session.accept_match()


## Every member of the party is here again after the match (none on the results plate).
func _back_together() -> bool:
	if str(Session.party["phase"]) != "forming" or Session.party_size() < party_size:
		return false
	for m: Dictionary in Session.members():
		if m["state"] == "in_match":
			return false
	return true


func _play() -> void:
	var main := Session.match_host
	if main == null or not is_instance_valid(main) or main.get("sim") == null:
		return
	if not _in_match:
		_in_match = true
		var client: MatchClient = Session.client
		var builders := []
		for entry: Dictionary in client.seat_list:
			builders.append(str(entry["builder"]))
		print("FLOW match %s seat %d of %d builders %s" % [
			client.mode, client.seat, client.seat_list.size(), ",".join(builders)
		])
		var chosen := []
		for entry: Dictionary in client.config.get("seats", []):
			chosen.append(NetProtocol.enum_name("builders", int(entry["builder"])))
		print("FLOW config builders %s" % ",".join(chosen))
	if flags.has("ready-calls") and Game.state == Game.State.PREP and Game.accepts_commands():
		var controller: BuildController = main.get("controller")
		if controller and not controller.wants_ready() and _frame - _asked_at >= ASK_FRAMES and _window_played(main):
			_asked_at = _frame
			controller.toggle_ready()


## Whether this window's Ready may go: at once, but in a duel the plan bot's (--bot) only once
## it has played the window both hollows share (tests/bot.gd played_window: corked and built),
## as the caretaker's Ready waits for its window, for a Ready on both sides sounds the horn.
func _window_played(main: Node) -> bool:
	var bot: Variant = main.get("_bot")
	if not Game.is_duel() or not bot is RefCounted:
		return true
	return int((bot as RefCounted).get("played_window")) == Game.wave + 1


func _on_results() -> void:
	if _results_at < 0:
		_results_at = _frame
		_in_match = false
		var shown: Dictionary = Session.results
		print("FLOW results %s %s" % [str(shown.get("outcome", "?")), str(shown.get("title", ""))])
	if _frame - _results_at >= results_frames:
		_results_at = -1
		played += 1
		_asked_at = _frame
		_said_queued = false
		Session.play_again()


func _fail(why: String) -> void:
	print("FLOW failed %s" % why)
	_done(1)


func _done(code: int) -> void:
	done = true
	if flags.has("quit-after-flow"):
		get_tree().quit(code)
