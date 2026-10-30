## The way through the game between matches (design 5.1): autoloaded as `Session`.
##
##   OFFLINE ---connect---> CONNECTING ---WELCOME---> HUB <---> COUNTDOWN (3-2-1)
##      |                                              |  (QUEUED, MATCH_FOUND: M6)
##      | Play, Try (a party of one: in-process turns) | MATCH_CONFIG
##      v                                              v
##   IN_MATCH <------------- START, turn 0 ------- LOADING (the sync barrier)
##      | won, lost, desynced, everyone left
##      v
##   RESULTS ---Play again / Hub---> HUB with the party kept (OFFLINE after an offline match)
##
## It keeps the player's Profile, this install's Identity, where the party lives (offline,
## LAN or online), the party as the server's last PARTY_STATE told it, and the one
## connection to a server: a MatchClient with `keep_link`, polled here between matches and
## by main.gd during one. The hub scene (scenes/hub.tscn, the main scene) draws the hub
## and the Builders screen from it; scenes/main.tscn plays the match `match_spec` names and
## hands back to results; the loading screen is this node's own layer, so it stays up
## while the match scene builds beneath it.
##
## Tests swap the network: `link_factory` makes the links (tests/net/loopback_hub.gd hands
## FakeLinks to the fake sequencer) and `clock` counts frames.
extends Node

## Anything the hub or the Builders screen shows changed.
signal changed
## A short notice for the player ("No party with that code").
signal noticed(text: String)

enum State { OFFLINE, CONNECTING, HUB, COUNTDOWN, QUEUED, MATCH_FOUND, LOADING, IN_MATCH, RESULTS }

const STATE_NAMES := [
	"OFFLINE", "CONNECTING", "HUB", "COUNTDOWN", "QUEUED", "MATCH_FOUND", "LOADING", "IN_MATCH", "RESULTS"
]
const HUB_SCENE := "res://scenes/hub.tscn"
const MATCH_SCENE := "res://scenes/main.tscn"
## The official server, and the link that opens the game in a friend's browser.
const OFFICIAL := "groundhold.saschb2b.com"
const JOIN_LINK := "https://saschb2b.github.io/Groundhold/play/?join=%s"
## Party codes: no vowels, no 0 O 1 I L (design 5.3).
const CODE_SYMBOLS := "23456789BCDFGHJKMNPQRSTVWXYZ"
const CODE_LENGTH := 5
## Seconds of loading after which the leader may start without the slow seats (§6.6).
const START_WITHOUT_AFTER := 30
## Boot flags that ask for a match at once (main.gd reads them): the hub steps aside.
const MATCH_FLAGS := ["join", "seed", "bot", "hash-log", "quit-after-match", "ticks-per-frame", "shot-at"]
## The scripted player a --flow-bot run hands the hub to (a test tool, not exported).
const FLOW_BOT := "res://tests/net/flow_bot.gd"
const NOTICE_TEXT := {
	"party_full": "That party is full",
	"no_such_party": "No party with that code",
	"removed": "You were removed from the party",
	"match_dissolved": "A player didn't accept. You keep your place.",
	"needs_reload": "Someone in the party needs to reload",
	"caretakers_offered": "Caretakers can fill the open seats",
	"tick0_mismatch": "A land did not match: the match was called off",
	"parties_full": "This server has no room for another party",
}

var state := State.OFFLINE
var profile: Profile
## Which hub screen the shell shows: "hub" or "builders".
var screen := "hub"
## Where the party lives: "offline", "lan" or "online"; and the server's host as shown.
var where := "offline"
var server_host := ""
## The connection to a server (a MatchClient that outlives its matches), or null.
var client: MatchClient
var beacon := BeaconListener.new()
## () -> NetLink for a new connection; NetLink.new() unless a test hands fakes.
var link_factory := Callable()
## Milliseconds of a monotonic clock; Time.get_ticks_msec unless a test counts frames.
var clock := Callable()
## What Join's Online row and a bare code connect to.
var official_address := OFFICIAL

## The party as the last PARTY_STATE told it: {"code", "mode", "flags", "leader", "phase",
## "countdown_ms", "at", "members": [{"member", "team", "main", "backup", "state", "rtt",
## "build_seq", "rules_hash", "name"}]}; {} without one.
var party := {}
## My member id in the party, -1 without one.
var me := -1
## A code to join once the server welcomes us.
var pending_code := ""
var last_notice := ""

## The match the next scenes/main.tscn plays: {"offline": true, "mode", "seats", "seed"}
## or {"networked": true}; {} when the match scene was booted on its own.
var match_spec := {}
## The finished match as the results panel shows it (ResultsPanel.compute()).
var results := {}
## Where Play again and Hub lead: "hub", or "builders" after a Try.
var return_screen := "hub"
## The match scene while it plays the session's match.
var match_host: Node
var matches_played := 0

var _loading: LoadingScreen
var _builders_sent := []
var _booted := false
var _flags_played := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	profile = Profile.load_saved()
	profile.changed.connect(func() -> void: changed.emit())
	beacon.clock = _now
	beacon.changed.connect(func() -> void: changed.emit())


func _physics_process(_delta: float) -> void:
	# (during a networked match the match scene polls the connection, before it steps;
	# during an offline one, a Try or a Play from a party, the hub's connection is still
	# the session's: its PINGs keep the party's row, its PARTY_STATEs keep the party)
	if client and (match_host == null or not match_spec.has("networked")):
		client.poll()
	beacon.poll()
	if _loading and client and client.phase >= MatchClient.Phase.PLAYING:
		_hide_loading()
		if state == State.LOADING:
			_set_state(State.IN_MATCH)


func state_name() -> String:
	return STATE_NAMES[state]


## The hub scene asks first, each time it opens. With boot flags for a match (--join,
## --seed, --bot, ...) the match scene plays them as it always did, and the hub steps
## aside: true. With --server=ADDRESS the hub connects there at its first opening and
## makes a party (or joins --code's); --name and --main set this run's name and main
## without saving them; --flow-bot hands the hub to tests/net/flow_bot.gd, which goes
## through the loop by itself (tools/net/smoke.py --flow). Inside the session's matches
## the match flags still count (--bot, --hash-log), so a flow's seat can be played.
func boot() -> bool:
	var flags := boot_flags()
	if flags.has("server"):
		if not _booted:
			_booted = true
			_boot_hub(flags)
		return false
	if _flags_played:
		return false  # (the flags' match was played; Leave to hub stays in the hub)
	for flag: String in MATCH_FLAGS:
		if flags.has(flag):
			_flags_played = true
			_go(MATCH_SCENE)
			return true
	return false


## This run's flags after `--`: name -> value ("true" for a bare flag).
static func boot_flags() -> Dictionary:
	var out := {}
	for arg: String in OS.get_cmdline_user_args():
		if not arg.begins_with("--"):
			continue
		var cut := arg.find("=")
		if cut < 0:
			out[arg.substr(2)] = "true"
		else:
			out[arg.substr(2, cut - 2)] = arg.substr(cut + 1)
	return out


func _boot_hub(flags: Dictionary) -> void:
	if flags.has("name") and Profile.valid_name(str(flags["name"])):
		profile.player_name = str(flags["name"])
		profile.named = true  # (for this run: the saved profile stays as it was)
	var chosen := str(flags.get("main", ""))
	if SimContent.BUILDERS.has(chosen) and chosen != profile.main:
		if profile.backup == chosen:
			profile.backup = profile.main
		profile.main = chosen
	if flags.has("flow-bot") and ResourceLoader.exists(FLOW_BOT):
		var bot: Node = load(FLOW_BOT).new()
		bot.call("setup", flags)
		add_child(bot)  # (it connects, joins and plays the loop itself)
		return
	connect_to(str(flags["server"]), clean_code(str(flags.get("code", ""))))


# ── The one button, and playing ──


## What the hub's primary button says and does now (design 5.2): {"text" (the button's
## word, or the 3-2-1's digit), "line" (the sentence beside it: "Waiting for Ana", "Ana
## needs to reload"; "" for none), "enabled", "act"}, where "act" is "play", "start",
## "ready", "unready", "cancel" or "".
func primary() -> Dictionary:
	if state == State.CONNECTING:
		return _button("Play", "Connecting to %s ..." % server_host, false, "")
	if state == State.COUNTDOWN:
		var left := countdown_left()
		return _button(str(left), "Starting in %d · Enter cancels" % left, true, "cancel")
	var leads := is_leader()
	var word := "Start" if leads else ("Not ready" if my_ready() else "Ready")
	var reload := reload_names()
	if party_size() > 1 and not reload.is_empty():
		var who := "You need" if reload.has(my_name()) else "%s needs" % reload[0]
		return _button(word, who + " to reload", false, "")
	if party_size() <= 1:
		return _button("Play", "", true, "play")
	if leads:
		var waiting := not_ready_names()
		if waiting.is_empty():
			return _button("Start", "Everyone is Ready", true, "start")
		return _button("Start", "Waiting for " + waiting[0], false, "")
	if my_ready():
		return _button("Not ready", "Waiting for the leader to start", true, "unready")
	return _button("Ready", "", true, "ready")


static func _button(text: String, line: String, enabled: bool, act: String) -> Dictionary:
	return {"text": text, "line": line, "enabled": enabled, "act": act}


## Presses the primary button.
func play() -> void:
	match str(primary()["act"]):
		"play":
			play_offline(profile.main)
		"start":
			_party("start")
		"ready":
			set_ready(true)
		"unready":
			set_ready(false)
		"cancel":
			_party("cancel")


## An offline match at once (a party of one): the chosen mode with `builder`, in-process
## turns. `company` adds caretaker seats (tests and practice) playing `company_builder`;
## `try` returns to the Builders screen afterwards.
func play_offline(builder: String, try := false, company := 0, company_builder := "lamplighter") -> void:
	if my_ready():
		set_ready(false)  # (the party cannot start a match while I practise)
	var seats := [{"team": 0, "builder": Profile.fielded(builder)}]
	for i in company:
		seats.append({"team": 0, "builder": Profile.fielded(company_builder), "caretaker": true})
	matches_played += 1
	match_spec = {
		"offline": true,
		"mode": Profile.played_mode(profile.mode),
		"shown_mode": profile.mode,
		"seats": seats,
		"names": [profile.player_name] + _caretaker_names(company),
		"chosen": [builder] + _caretaker_builders(company, company_builder),
		"seed": matches_played,
		"try": try,
	}
	return_screen = "builders" if try else "hub"
	results = {}
	_set_state(State.IN_MATCH)
	_go(MATCH_SCENE)


## The match menu's Restart (design 5.4): the offline match the session plays, from its
## start again, as it was asked for (the same seats, seed and way back).
func restart_match() -> void:
	if not match_spec.has("offline"):
		return
	results = {}
	match_host = null
	_go(MATCH_SCENE)


## Try (design 5.4): a solo match with `builder`, offline, back to the Builders screen after.
func try_builder(builder: String) -> void:
	play_offline(builder, true)


## The match scene's first question: what to play. {} when it was booted on its own (its
## flags, or a test), and then it plays as it always did.
func enter_match(host: Node) -> Dictionary:
	if match_spec.is_empty():
		return {}
	match_host = host
	return match_spec


## The match scene built the hollow: a networked match says LOADED now.
func match_loaded() -> void:
	if client and match_spec.has("networked"):
		client.loaded()


## The match ended (the simulation over offline, MATCH_END online): results show.
func match_over(shown: Dictionary) -> void:
	results = shown
	_hide_loading()
	_set_state(State.RESULTS)


## Play again (design 5.9): back to the hub with the party, mode and Builders unchanged and
## Ready cleared; after a Try, back to the Builders screen.
func play_again() -> void:
	to_hub(return_screen)


## Leaves whatever plays or shows for the hub (or the Builders screen).
func to_hub(where_to := "hub") -> void:
	if client and client.phase in [MatchClient.Phase.LOADING, MatchClient.Phase.STARTING, MatchClient.Phase.PLAYING]:
		client.send("LEAVE_MATCH")
		client.phase = MatchClient.Phase.ENDED
	elif client and client.phase == MatchClient.Phase.ENDED and match_spec.has("networked"):
		# (after MATCH_END the server keeps my row on the results plate until LEAVE_MATCH:
		# Play again or Hub brings me back to the party, Ready cleared; shared/net/README.md)
		client.send("LEAVE_MATCH")
	if client and client.phase == MatchClient.Phase.FAILED:
		client = null  # (the link went during the match: back offline)
	if client:
		client.rearm()
	_hide_loading()
	match_host = null
	match_spec = {}
	screen = where_to
	_set_state(State.HUB if _connected() else State.OFFLINE)
	_go(HUB_SCENE)


func show_screen(which: String) -> void:
	screen = which
	changed.emit()


# ── Servers and parties ──


## Connects to a server at a typed address (the address rule, NetAddress) and makes a
## party there, or joins `code`'s. False when the address cannot be one.
func connect_to(address: String, code := "") -> bool:
	var url := NetAddress.url(address)
	if url == "":
		_notice("Not a server address: " + address.strip_edges())
		return false
	disconnect_server()
	var host := url.substr(url.find("://") + 3)
	host = host.substr(0, host.find("/"))
	if host.ends_with(":%d" % NetProtocol.number("port")):
		host = host.substr(0, host.length() - 5)
	server_host = host
	var name_end := host.rfind(":") if host.count(":") == 1 else host.length()
	where = "lan" if NetAddress.is_local(host.substr(0, name_end)) else "online"
	pending_code = code
	client = MatchClient.new()
	client.keep_link = true
	client.defer_loaded = true
	client.player_name = profile.player_name
	client.token = Identity.token_for(url)
	client.build_seq = build_seq()
	client.web = OS.has_feature("web")
	if clock.is_valid():
		client.clock = clock
		client.timed = false
	client.welcomed.connect(_on_welcomed)
	client.hub_message.connect(_on_hub_message)
	client.configured.connect(_on_configured)
	client.ended.connect(_on_ended)
	client.failed.connect(_on_failed)
	_set_state(State.CONNECTING)
	var link: NetLink = link_factory.call() if link_factory.is_valid() else NetLink.new()
	return client.connect_with(link, url)


## Joins a party by its code: lower case, spaces and hyphens are fine. On the server we
## are on, or the official one. False while the code is not five code symbols.
func join_code(typed: String) -> bool:
	var code := clean_code(typed)
	if not code_ok(code):
		return false
	if _connected():
		_party("join", {"code": code.to_ascii_buffer()})
		return true
	return connect_to(official_address, code)


## A party of my own on the server we are on (or the official one).
func create_party() -> void:
	if _connected():
		if not party.is_empty():
			_party("leave")
		_party("create", {"mode": Profile.wire_mode(profile.mode)})
	else:
		connect_to(official_address)


## Leaves the party and the server: back to offline, a party of one.
func leave_party() -> void:
	if _connected() and not party.is_empty():
		_party("leave")
	disconnect_server()
	_set_state(State.OFFLINE)


func disconnect_server() -> void:
	if client:
		for sig: Signal in [client.welcomed, client.hub_message, client.configured, client.ended, client.failed]:
			for c: Dictionary in sig.get_connections():
				sig.disconnect(c["callable"])
		client.close()
	client = null
	party = {}
	me = -1
	where = "offline"
	server_host = ""
	_builders_sent = []
	changed.emit()


func set_ready(on: bool) -> void:
	_party("ready", {"on": 1 if on else 0})


func set_mode(id: String) -> void:
	if not Profile.offers(id):
		return
	profile.set_mode(id)
	if is_leader() and party_size() > 0:
		_party("mode", {"mode": Profile.wire_mode(id)})


func set_main(builder: String) -> void:
	profile.set_main(builder)
	_send_builders()


func set_backup(builder: String) -> void:
	profile.set_backup(builder)
	_send_builders()


# ── Questions the screens ask ──


func party_size() -> int:
	return (party.get("members", []) as Array).size() if not party.is_empty() else 1


func members() -> Array:
	return party.get("members", []) if not party.is_empty() else []


func is_leader() -> bool:
	return party.is_empty() or int(party["leader"]) == me


func my_name() -> String:
	return profile.player_name


## Loading a party's match (design 6.6): from 30 s, with a seat loaded, the leader may
## start without the seats still loading; the name of the first of those, the one the
## button names ("Start without Ben"), or "" while the leader cannot.
func start_without_name() -> String:
	if client == null or party.is_empty() or not is_leader() or state != State.LOADING:
		return ""
	if client.phase >= MatchClient.Phase.STARTING or client.load_seconds < START_WITHOUT_AFTER:
		return ""
	var loaded := false
	var waiting := ""
	for i in client.load_states.size():
		var load_state := NetProtocol.enum_name("load_states", int(client.load_states[i][1]))
		if load_state in ["checking", "ready"]:
			loaded = true
		elif waiting == "" and load_state in ["connecting", "loading", "slow"] and i < client.names.size():
			waiting = str(client.names[i])
	return waiting if loaded else ""


## The leader's Start without: PARTY start while loading; the server starts the seats
## loaded, and the caretaker plays the rest until they come.
func start_without() -> void:
	if start_without_name() != "":
		_party("start")


func my_ready() -> bool:
	for m: Dictionary in members():
		if int(m["member"]) == me:
			return m["state"] == "ready"
	return false


## Names of the members (not the leader) still not Ready.
func not_ready_names() -> Array:
	var out := []
	for m: Dictionary in members():
		if int(m["member"]) != int(party["leader"]) and m["state"] != "ready":
			out.append(m["name"])
	return out


## Names of the members on another rules version ("needs to reload").
func reload_names() -> Array:
	var out := []
	for m: Dictionary in members():
		if m["state"] == "needs_reload":
			out.append(str(m["name"]) if int(m["member"]) != me else my_name())
	return out


## The Builders the party has chosen as mains (just mine without one): the coverage row.
func party_builders() -> Array:
	if party.is_empty():
		return [profile.main]
	var out := []
	for m: Dictionary in members():
		out.append(str(m["main"]))
	return out


## Seconds left on the 3-2-1, counted from the server's countdown_ms.
func countdown_left() -> int:
	if party.is_empty():
		return 0
	var left := int(party["countdown_ms"]) - (_now() - int(party["at"]))
	return maxi(1, ceili(left / 1000.0))


## Where the party lives, as the strip says it: "Offline", "LAN · 192.168.1.20",
## "Online · groundhold.saschb2b.com".
func place_text() -> String:
	match where:
		"lan":
			return "LAN · " + server_host
		"online":
			return "Online · " + server_host
	return "Offline"


func party_code() -> String:
	return str(party.get("code", ""))


func join_link() -> String:
	return JOIN_LINK % party_code()


## A typed code without spaces or hyphens, in upper case.
static func clean_code(typed: String) -> String:
	return typed.to_upper().replace(" ", "").replace("-", "").replace("\t", "")


static func code_ok(code: String) -> bool:
	if code.length() != CODE_LENGTH:
		return false
	for c in code:
		if not CODE_SYMBOLS.contains(c):
			return false
	return true


## "K7Q4M" as it is shown and read aloud: "K7Q-4M".
static func show_code(code: String) -> String:
	return code.substr(0, 3) + "-" + code.substr(3) if code.length() == CODE_LENGTH else code


## The CI run number (data/build.json, written by the release build), else 0.
static func build_seq() -> int:
	if not FileAccess.file_exists("res://data/build.json"):
		return 0
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/build.json"))
	return int((parsed as Dictionary).get("build_seq", 0)) if parsed is Dictionary else 0


## A MatchClient for one match on the server at `address` at once (the --join boot
## flag): no party, no hub; the M1 path, now with this install's token for that server
## and the profile's name.
func direct_client(player_name: String, address: String) -> MatchClient:
	var joining := MatchClient.new()
	joining.player_name = player_name if player_name != "" else profile.player_name
	joining.token = Identity.token_for(NetAddress.url(address))
	joining.build_seq = build_seq()
	joining.web = OS.has_feature("web")
	return joining


# ── The server's side ──


func _on_welcomed() -> void:
	_set_state(State.HUB)
	if pending_code != "":
		_party("join", {"code": pending_code.to_ascii_buffer()})
		pending_code = ""
	else:
		_party("create", {"mode": Profile.wire_mode(profile.mode)})


func _on_hub_message(type: String, fields: Dictionary) -> void:
	match type:
		"PARTY_STATE":
			_on_party_state(fields)
		"NOTICE":
			var key := NetProtocol.enum_name("notices", int(fields["code"]))
			var argument := int(fields["argument"])
			if key == "no_such_party" and argument > 0:
				# (the lookups ran out: the argument is the seconds until the next one)
				_notice("Too many codes tried: wait %d s" % argument)
			else:
				_notice(str(NOTICE_TEXT.get(key, "The server says no")))
		"QUEUE_STATE":
			var queued := NetProtocol.enum_name("queue_states", int(fields["state"])) == "queued"
			if queued and state in [State.HUB, State.COUNTDOWN]:
				_set_state(State.QUEUED)
			elif not queued and state == State.QUEUED:
				_set_state(State.HUB)
		"MATCH_FOUND":
			if state in [State.HUB, State.QUEUED]:
				_set_state(State.MATCH_FOUND)


func _on_party_state(fields: Dictionary) -> void:
	if (fields["members"] as Array).is_empty():
		# (the no-party state: a code of zero bytes, leader 255, nobody; a party of one again)
		party = {}
		me = -1
		_builders_sent = []
		if state in [State.COUNTDOWN, State.QUEUED, State.CONNECTING]:
			_set_state(State.HUB)
		changed.emit()
		return
	var listed := []
	for m: Dictionary in fields["members"]:
		listed.append(
			{
				"member": int(m["member"]),
				"team": int(m["team"]),
				"main": NetProtocol.enum_name("builders", int(m["main"])),
				"backup": NetProtocol.enum_name("builders", int(m["backup"])),
				"state": NetProtocol.enum_name("member_states", int(m["state"])),
				"rtt": int(m["rtt_ms"]),
				"build_seq": int(m["build_seq"]),
				"rules_hash": (m["rules_hash"] as PackedByteArray).hex_encode(),
				"name": str(m["name"]),
			}
		)
	party = {
		"code": (fields["code"] as PackedByteArray).get_string_from_ascii(),
		"mode": NetProtocol.enum_name("modes", int(fields["mode"])),
		"flags": int(fields["flags"]),
		"leader": int(fields["leader"]),
		"phase": NetProtocol.enum_name("party_phases", int(fields["phase"])),
		"countdown_ms": int(fields["countdown_ms"]),
		"at": _now(),
		"members": listed,
	}
	# My row: the server tells each member its own number (`you`).
	me = -1
	for m: Dictionary in listed:
		if int(m["member"]) == int(fields["you"]):
			me = int(m["member"])
	if me >= 0 and _builders_sent != [profile.main, profile.backup]:
		_send_builders()
	if state in [State.HUB, State.COUNTDOWN, State.QUEUED, State.CONNECTING]:
		match str(party["phase"]):
			"countdown":
				_set_state(State.COUNTDOWN)
			"queued":
				_set_state(State.QUEUED)
			"forming", "results":
				_set_state(State.HUB)
	changed.emit()


func _on_configured() -> void:
	match_spec = {"networked": true}
	matches_played += 1
	return_screen = "hub"
	results = {}
	_set_state(State.LOADING)
	_show_loading()
	_go(MATCH_SCENE)


func _on_ended(_outcome: String, _reason: String) -> void:
	if match_host == null and state == State.LOADING:
		# (called off before the match scene stood: straight back to the party)
		to_hub()


func _on_failed(text: String) -> void:
	_notice(text)
	var in_match := match_host != null
	if client:
		for c: Dictionary in client.failed.get_connections():
			client.failed.disconnect(c["callable"])
	party = {}
	me = -1
	where = "offline"
	server_host = ""
	if not in_match:
		client = null
		_hide_loading()
		if state != State.OFFLINE:
			_set_state(State.OFFLINE)
		if get_tree().current_scene and get_tree().current_scene.scene_file_path == MATCH_SCENE:
			_go(HUB_SCENE)
	changed.emit()


# ── Helpers ──


func _party(op: String, fields := {}) -> void:
	if not _connected():
		return
	var message := {"op": op}  # (the codec takes a switch case by its name)
	message.merge(fields)
	client.send("PARTY", message)


func _send_builders() -> void:
	if not _connected() or party.is_empty():
		return
	_builders_sent = [profile.main, profile.backup]
	_party(
		"builders",
		{
			"main": NetProtocol.enum_value("builders", profile.main),
			"backup": NetProtocol.enum_value("builders", profile.backup),
		}
	)


func _connected() -> bool:
	return client != null and client.link != null and client.link.is_open() and client.phase >= MatchClient.Phase.WAITING and client.phase != MatchClient.Phase.FAILED


func _set_state(next: State) -> void:
	if next == state:
		return
	state = next
	changed.emit()


func _notice(text: String) -> void:
	last_notice = text
	noticed.emit(text)


func _go(path: String) -> void:
	var tree := get_tree()
	if tree.current_scene and tree.current_scene.scene_file_path == path and path == HUB_SCENE:
		changed.emit()
		return
	tree.change_scene_to_file(path)


func _show_loading() -> void:
	if _loading == null:
		_loading = LoadingScreen.new()
		add_child(_loading)


func _hide_loading() -> void:
	if _loading:
		_loading.queue_free()
		_loading = null


func _now() -> int:
	return int(clock.call()) if clock.is_valid() else Time.get_ticks_msec()


static func _caretaker_names(count: int) -> Array:
	var out := []
	for i in count:
		out.append("Caretaker %d" % (i + 1))
	return out


static func _caretaker_builders(count: int, builder := "lamplighter") -> Array:
	var out := []
	for i in count:
		out.append(builder)
	return out
