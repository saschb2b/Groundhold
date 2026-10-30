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
## It prints one line per step for the tool reading its output:
##   FLOW party <code> members <n> me <row> leader|member
##   FLOW state <the session's state>
##   FLOW match <mode> seat <k> of <n> builders <b1,b2,...>
##   FLOW results <outcome> <the results' title>
##   FLOW back <code> members <n> phase <phase>
##   FLOW notice <text>   FLOW failed <why>
## Flags: --code-out=FILE writes the party's code to FILE once made; --ready-calls says
## Ready in every build window, so the waves come at once (a short match); --matches=N
## plays N matches before it is done (default 1); --quit-after-flow quits when done (exit
## 0) or on a failure (exit 1).
extends Node

## Frames on the results before Play again (the plate is read, as a player would).
const RESULTS_FRAMES := 90
## Frames between two asks of the same thing (Ready, Start) while the answer is on its way.
const ASK_FRAMES := 30

var flags := {}
var party_size := 2
var matches := 1
var played := 0
var done := false

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
	party_size = maxi(1, int(boot.get("party", "2")))
	matches = maxi(1, int(boot.get("matches", "1")))


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
	if flags.has("ready-calls") and Game.state == Game.State.PREP and Game.accepts_commands():
		var controller: BuildController = main.get("controller")
		if controller and not controller.wants_ready() and _frame - _asked_at >= ASK_FRAMES:
			_asked_at = _frame
			controller.toggle_ready()


func _on_results() -> void:
	if _results_at < 0:
		_results_at = _frame
		_in_match = false
		var shown: Dictionary = Session.results
		print("FLOW results %s %s" % [str(shown.get("outcome", "?")), str(shown.get("title", ""))])
	if _frame - _results_at >= RESULTS_FRAMES:
		_results_at = -1
		played += 1
		_asked_at = _frame
		Session.play_again()


func _fail(why: String) -> void:
	print("FLOW failed %s" % why)
	_done(1)


func _done(code: int) -> void:
	done = true
	if flags.has("quit-after-flow"):
		get_tree().quit(code)
