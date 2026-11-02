## The way through the game between matches (design 5.1): autoloaded as `Session`.
##
##   OFFLINE ---connect---> CONNECTING ---WELCOME---> HUB <---> COUNTDOWN (3-2-1)
##      |                                              |  ^
##      |                              QUEUE enter     v  | QUEUE_STATE idle (Cancel, a decline)
##      |                                            QUEUED <---> MATCH_FOUND (15 s, Accept)
##      | Play, Try (a party of one: in-process turns) | MATCH_CONFIG (a party's, the queue's)
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
##
## A link lost in a match is the MatchClient's to take back (M4): it reconnects with the
## same token and its held seat (`link_factory` makes the new link), the server's
## PARTY_STATE keeps the party here, and no WELCOME of a resume makes or joins a party.
## NOTICE no_held_seat ends that match for this game and shows the results' way back. A
## match that started without this game still takes its LOADED once the match scene
## stands (match_loaded). In the web build a ?join=CODE on the page joins that party at
## the first opening of the hub (WebBridge.query).
##
## The queue (M6, design 5.1, 5.2, 5.5, 5.9; shared/net/README.md The queue): the leader of
## a party with open seats (High Water: Find players) or of one race team (Find a rival)
## sends QUEUE enter; "Entering queue..." and "Leaving queue..." show until the server's
## QUEUE_STATE answers. Queued, the hub's pill counts from its elapsed_ms ("Finding players
## 0:42") and the leader's button cancels; after the offer it starts with caretakers (Race
## the caretaker). MATCH_FOUND opens the Match Found overlay (scripts/ui/match_found.gd) on
## the server's countdown; ACCEPT answers it. A player who came alone through the queue to
## a match of strangers is queued again by Play again. Only the leader may leave the queue,
## so a member's Try waits for it (try_refusal). Offline, a party of one in a race races the
## caretaker: a rival team of caretakers with the same Builders (offline_match).
##
## The level (M8, contract-m8.md §3; design 2.6, 5.2): the party's, which its leader picks as
## the mode (PARTY difficulty; a change clears every Ready), or the profile's in a party of one
## and offline. difficulty_id() is the level the hub shows, set_difficulty() the hub's click
## (the profile's always, the party's when the leader), offers_difficulty(mode) whether a mode
## takes one. A party this game makes starts at the profile's level (PARTY difficulty after the
## create), and every match the hub starts plays the level it shows where the mode takes one:
## Play, Try and Race the caretaker (offline_match's "difficulty"); Duel the caretaker plays
## Normal. A networked match plays MATCH_CONFIG's (match_spec "difficulty", the client's).
##
## Undertow (M7, contract-m7.md §4; design 1.4, 1.5): a duel is a two-team mode of one seat a
## side (is_duel). A party of one finds a rival through the queue (Find a rival), or, offline
## or after the queue's offer, duels the caretaker: a caretaker of the same Builder on team 1
## (offline_seats; the server's start_with_caretakers). A party of two is both sides, one on
## each team: it starts, and no row moves onto a side already taken (can_move; a race's rows
## move freely, as before). Play again queues a duellist who came alone again, as any player
## the queue found strangers for.
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
## Its "official" is the official server's wss:// URL (official_url).
const NET_FILE := "res://data/net.json"
## The link that opens the game in a friend's browser and joins the party.
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
## The hub's word after the link went on the results plate, the match already over: the
## party went with it.
const PARTY_LOST_NOTICE := "Your link was lost, and the party with it."
## ... and after a match whose link went: the server keeps the seat for the caretaker.
const LINK_LOST_NOTICE := PARTY_LOST_NOTICE + " The caretaker plays your seat to the end."
const NOTICE_TEXT := {
	"party_full": "That party is full",
	"no_such_party": "No party with that code",
	"removed": "You were removed from the party",
	"match_dissolved": "A player didn't accept. You keep your place.",
	# (the server tells the member who needs it: a newer build leads the party)
	"needs_reload": "A newer version is in the party: reload to play",
	"caretakers_offered": "Caretakers can fill the open seats",
	"tick0_mismatch": "A land did not match: the match was called off",
	"parties_full": "This server has no room for another party",
	"no_held_seat": "The match went on without you: back to the party",
}
## The queue's words (design 5.2): the pill and a member's button, by the mode's teams.
const FINDING_PLAYERS := "Finding players"
const FINDING_RIVAL := "Finding a rival"
## What a party of one plays against the caretaker in a two-team mode (design 1.5), and what
## the queue's offer of caretakers says there (caretaker_word, offer_text).
const RACE_CARETAKER := "Race the caretaker"
const DUEL_CARETAKER := "Duel the caretaker"
const OFFER_RACE := "Caretakers can race your team"
const OFFER_DUEL := "The caretaker can be your rival"
## A party larger than a duel's two sides (design 1.4: one against one).
const DUEL_TOO_MANY := "A duel is one against one"
## Why a member cannot Try while the party is queued (try_refusal).
const TRY_QUEUED := "The party is in the queue: only the leader can leave it"
const MATCH_FOUND_OVERLAY := "res://scripts/ui/match_found.gd"

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
## What Join's Online row and a bare code connect to: data/net.json's official URL.
var official_address := official_url()

## The party as the last PARTY_STATE told it: {"code", "mode", "difficulty", "flags", "leader", "phase",
## "countdown_ms", "at", "members": [{"member", "team", "main", "backup", "state", "rtt",
## "build_seq", "rules_hash", "name"}]}; {} without one.
var party := {}
## My member id in the party, -1 without one.
var me := -1
## A code to join once the server welcomes us.
var pending_code := ""
## A join link's code waiting for the first launch's name (open_link): HELLO is the only
## message that carries a name, so the link connects once the prompt is answered.
var link_code := ""
var last_notice := ""
## A notice for the hub to show once it stands (Shell): why the party is gone after the
## link went in a match (LINK_LOST_NOTICE). "" for none.
var hub_notice := ""

## The match the next scenes/main.tscn plays: {"offline": true, "mode", "difficulty",
## "seats", "seed", ...} or {"networked": true, "difficulty"}; {} when the match scene was
## booted on its own. "difficulty" is the level the match plays (MatchRules.level_of).
var match_spec := {}
## The finished match as the results panel shows it (ResultsPanel.compute()).
var results := {}
## Where Play again and Hub lead: "hub", or "builders" after a Try.
var return_screen := "hub"
## The match scene while it plays the session's match.
var match_host: Node
var matches_played := 0

## The queue as the server's last QUEUE_STATE told it: {"state" ("idle" or "queued"),
## "elapsed" (ms queued then), "offer" (caretakers offered), "at" (the clock's ms it came)};
## {} before one.
var queue := {}
## The QUEUE op on its way, "enter" or "leave" ("" for none): the button says "Entering
## queue..." or "Leaving queue..." until the next QUEUE_STATE.
var queue_request := ""
## The match the queue found, as the last MATCH_FOUND said it: {"match", "mode", "seats",
## "accepted", "ms_left", "at", "answer" ("", "accept" or "decline")}; {} while none.
var found := {}
## The match this session plays is one of strangers the queue found for a party of one
## (through Match Found, not a start with caretakers): Play again queues it again (design 5.9).
var requeue_after := false
## The match came through Match Found (strangers): the leader cannot start it without a
## seat; the barrier's timers decide (design 6.6).
var strangers_match := false

var _loading: LoadingScreen
var _match_found: Node
var _builders_sent := []
var _booted := false
var _flags_played := false
var _announced := false


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
## makes a party (or joins --code's); --name, --main and --mode (one the hub offers) set
## this run's name, main and the party's mode without saving them; --flow-bot hands the
## hub to tests/net/flow_bot.gd, which goes through the loop by itself (tools/net/smoke.py
## --flow). Inside the session's matches
## the match flags still count (--bot, --hash-log), so a flow's seat can be played.
func boot() -> bool:
	if not _announced:
		_announced = true
		print(banner())  # (the first line a player's log or a release's boot check reads)
	var flags := boot_flags()
	if flags.has("server"):
		if not _booted:
			_booted = true
			_boot_hub(flags)
		return false
	if not _booted and WebBridge.is_web():
		_booted = true
		var code := clean_code(WebBridge.query("join"))
		if code_ok(code):
			open_link(code)  # (a friend's link: play/?join=K7Q4M, forwarded to the game)
			return false
	if _flags_played:
		return false  # (the flags' match was played; Leave to hub stays in the hub)
	for flag: String in MATCH_FLAGS:
		if flags.has(flag):
			_flags_played = true
			# (deferred: boot() runs in the hub's _ready, while the tree still adds it, and a
			# scene change then is refused with "Parent node is busy adding/removing children")
			_go.call_deferred(MATCH_SCENE)
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
	var mode := str(flags.get("mode", ""))
	if Profile.HUB_MODES.has(mode) and Profile.offers(mode):
		profile.mode = mode  # (the mode the party is made in, for this run: M7's --mode=undertow)
	var level := str(flags.get("difficulty", ""))
	if MatchRules.known(level):
		profile.difficulty = level  # (the level the party is made at, for this run: M8's --difficulty=hard)
	if flags.has("flow-bot") and ResourceLoader.exists(FLOW_BOT):
		var bot: Node = load(FLOW_BOT).new()
		bot.call("setup", flags)
		add_child(bot)  # (it connects, joins and plays the loop itself)
		return
	connect_to(str(flags["server"]), clean_code(str(flags.get("code", ""))))


# ── The one button, and playing ──


## What the hub's primary button says and does now (design 5.2): {"text" (the button's
## word, or the 3-2-1's digit), "line" (the sentence beside it: "Waiting for Ana", "Ana
## needs to reload", "Finding players 0:42"; "" for none), "enabled", "act", "second"}, where
## "act" is "play", "start", "ready", "unready", "cancel", "queue", "leave_queue",
## "caretakers" or "", and "second" is the other action beside it once the caretakers are
## offered ({"text": "Cancel · 1:02", "act": "leave_queue"}; {} otherwise).
func primary() -> Dictionary:
	if state == State.CONNECTING:
		return _button("Play", "Connecting to %s ..." % server_host, false, "")
	if state == State.COUNTDOWN:
		var left := countdown_left()
		return _button(str(left), "Starting in %d · Enter cancels" % left, true, "cancel")
	if queue_request == "enter":
		return _button("Entering queue...", "", false, "")
	if queue_request == "leave":
		return _button("Leaving queue...", "", false, "")
	var leads := is_leader()
	if state == State.MATCH_FOUND:
		return _button("Match found", "", false, "")
	if state == State.QUEUED:
		var finding := queue_text()
		if not leads:
			return _button(finding, "", false, "")
		var cancel := "Cancel · " + clock_text(queue_ms())
		if queue_offer():
			var word := caretaker_word(mode_id()) if is_race(mode_id()) else "Start with caretakers"
			var button := _button(word, finding, true, "caretakers")
			button["second"] = {"text": cancel, "act": "leave_queue"}
			return button
		return _button(cancel, finding, true, "leave_queue")
	var mode := mode_id()
	var race := is_race(mode)
	var word := "Start" if leads else ("Not ready" if my_ready() else "Ready")
	var reload := reload_names()
	if party_size() > 1 and not reload.is_empty():
		var who := "You need" if reload.has(my_name()) else "%s needs" % reload[0]
		return _button(word, who + " to reload", false, "")
	var partied := _connected() and not party.is_empty()
	if party_size() <= 1 and not partied and not Profile.offers(mode):
		# (offline, or on a server without a party, the match plays here, by this build's
		# rules; in a party the leader chose the mode where its build offers it, and a member
		# on another build needs to reload)
		return _button("Play", "%s comes with a later version" % Profile.mode_name(mode), false, "")
	if party_size() <= 1:
		if race:
			if partied:
				return _button("Find a rival", "", true, "queue")
			return _button(caretaker_word(mode), "", true, "play")  # (no party to queue: offline)
		if _connected() and open_seats():
			return _button("Find players", "", true, "queue")
		return _button("Play", "", true, "play")
	if party_size() > max_seats(mode):
		# (only a duel's two seats are fewer than a party may hold: the leader's Start waits
		# until the party is two again, and a member still says Ready or Not ready meanwhile)
		if leads:
			return _button("Start", DUEL_TOO_MANY, false, "")
		if my_ready():
			return _button("Not ready", DUEL_TOO_MANY, true, "unready")
		return _button("Ready", DUEL_TOO_MANY, true, "ready")
	if leads:
		var waiting := not_ready_names()
		var finds := ""
		if race and one_team() and party_size() * 2 <= max_seats(mode):
			finds = "Find a rival"
		elif race and not even_teams():
			return _button("Start", "Two teams of one size: click a row to move it", false, "")
		elif not race and open_seats() and party_size() < max_seats(mode):
			finds = "Find players"
		var act := "queue" if finds != "" else "start"
		var shown := finds if finds != "" else "Start"
		if waiting.is_empty():
			return _button(shown, "Everyone is Ready", true, act)
		return _button(shown, "Waiting for " + waiting[0], false, "")
	if my_ready():
		return _button("Not ready", "Waiting for the leader to start", true, "unready")
	return _button("Ready", "", true, "ready")


static func _button(text: String, line: String, enabled: bool, act: String) -> Dictionary:
	return {"text": text, "line": line, "enabled": enabled, "act": act, "second": {}}


## Presses the primary button (`second`: the action beside it, Cancel once caretakers are
## offered).
func play(second := false) -> void:
	var button := primary()
	var act := str(button["act"])
	if second:
		act = str((button["second"] as Dictionary).get("act", ""))
	match act:
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
		"queue":
			enter_queue()
		"leave_queue":
			leave_queue()
		"caretakers":
			start_with_caretakers()


## An offline match at once (a party of one): the chosen mode with `builder`, in-process
## turns. `company` adds caretaker seats (tests and practice) playing `company_builder`;
## `try` returns to the Builders screen afterwards.
func play_offline(builder: String, try := false, company := 0, company_builder := "lamplighter") -> void:
	if state == State.MATCH_FOUND:
		decline_match()  # (practising instead: the found match goes on without me)
	elif state == State.QUEUED and is_leader():
		leave_queue()  # (a member cannot: try_refusal keeps a member's Try for after the queue)
	if my_ready():
		set_ready(false)  # (the party cannot start a match while I practise)
	# (a Try is a solo High Water; Play in a race mode races the caretaker; Play plays the
	# mode the hub shows, the party's where I am in one)
	var mode := "high_water" if try else mode_id()
	matches_played += 1
	match_spec = offline_match(mode, builder, try, company, company_builder)
	return_screen = "builders" if try else "hub"
	results = {}
	_set_state(State.IN_MATCH)
	_go(MATCH_SCENE)


## The offline match play_offline plays ({"offline", "mode" (the rules played), "difficulty"
## (the level it plays: the hub's where the mode takes one, else Normal), "shown_mode",
## "seats", "names", "chosen", "seed", "try"}): `mode` with `builder` and `company` caretaker
## partners playing `company_builder` (as many as a team's seats hold: none in a duel); in a
## race the rival team mirrors them, its chosen Builders the same (racing the caretaker); in a
## duel the rival is one caretaker of my Builder (duelling the caretaker).
func offline_match(
	mode: String, builder: String, try := false, company := 0, company_builder := "lamplighter"
) -> Dictionary:
	company = clampi(company, 0, team_seats(mode) - 1)
	var seats := offline_seats(mode, builder, company, company_builder)
	var chosen := [builder] + _caretaker_builders(company, company_builder)
	if is_race(mode):
		chosen += chosen.duplicate()  # (the rival team: the same Builders, a mirror)
	return {
		"offline": true,
		"mode": Profile.played_mode(mode),
		"difficulty": try_level() if try else MatchRules.level_of(Profile.played_mode(mode), difficulty_id()),
		"shown_mode": mode,
		"seats": seats,
		"names": [profile.player_name] + _caretaker_names(seats.size() - 1),
		"chosen": chosen,
		"seed": matches_played,
		"try": try,
	}


## An offline match's seats ({"team", "builder", "caretaker"}): mine first, then `company`
## caretaker partners playing `company_builder`, as many as a team's seats hold; in a race
## (two teams) the rival team after them, caretakers with the same Builders, a mirror (racing
## the caretaker, design 1.3); in a duel, one a side, a caretaker of my Builder (design 1.5).
static func offline_seats(mode: String, builder: String, company := 0, company_builder := "lamplighter") -> Array:
	company = clampi(company, 0, team_seats(mode) - 1)
	var seats := [{"team": 0, "builder": Profile.fielded(builder)}]
	for i in company:
		seats.append({"team": 0, "builder": Profile.fielded(company_builder), "caretaker": true})
	if is_race(mode):
		for i in company + 1:
			seats.append({"team": 1, "builder": seats[i]["builder"], "caretaker": true})
	return seats


## The match menu's Restart (design 5.4): the offline match the session plays, from its
## start again, as it was asked for (the same seats, seed and way back).
func restart_match() -> void:
	if not match_spec.has("offline"):
		return
	results = {}
	match_host = null
	_go(MATCH_SCENE)


## Try (design 5.4): a solo match with `builder`, offline, back to the Builders screen after.
## Not while try_refusal() says why.
func try_builder(builder: String) -> void:
	var refusal := try_refusal()
	if refusal != "":
		_notice(refusal)
		return
	play_offline(builder, true)


## Why Try cannot start now ("" where it can): a member of a queued party. The leader's Try
## takes the party out of the queue, but only the leader may (a member's Ready and QUEUE
## leave are refused while queued), and a member gone into a Try would leave every Match
## Found the queue makes for the party to run out. In Match Found a Try is a decline.
func try_refusal() -> String:
	if state == State.QUEUED and not is_leader():
		return TRY_QUEUED
	return ""


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
## Ready cleared; after a Try, back to the Builders screen. A player who came alone through
## the queue to a match of strangers is queued again at once ("Entering queue..." until the
## server says queued); after a start with caretakers the party is forming, as after Start.
func play_again() -> void:
	var again := requeue_after and match_spec.has("networked")
	to_hub(return_screen)
	if again and _connected() and party_size() <= 1:
		enter_queue()


## Leaves whatever plays or shows for the hub (or the Builders screen).
func to_hub(where_to := "hub") -> void:
	if client and client.phase == MatchClient.Phase.ENDED and (client.link == null or not client.link.is_open()):
		# (the link closed on the results plate before a poll saw it: the party went with it)
		client.phase = MatchClient.Phase.FAILED
	if client and client.reconnecting:
		# (leaving while the link is gone: the server's held seat goes to the caretaker)
		client.close()
		client.phase = MatchClient.Phase.FAILED
	elif client and client.phase in [MatchClient.Phase.LOADING, MatchClient.Phase.STARTING, MatchClient.Phase.PLAYING]:
		client.send("LEAVE_MATCH")
		client.phase = MatchClient.Phase.ENDED
	elif client and client.phase == MatchClient.Phase.ENDED and match_spec.has("networked"):
		# (after MATCH_END the server keeps my row on the results plate until LEAVE_MATCH:
		# Play again or Hub brings me back to the party, Ready cleared; shared/net/README.md)
		client.send("LEAVE_MATCH")
	if client and client.phase == MatchClient.Phase.FAILED:
		# (the link went during the match, or on its results plate: back offline, a party of
		# one; after MATCH_END the word has no caretaker in it)
		var after_end := client.outcome != ""
		client = null
		party = {}
		me = -1
		where = "offline"
		server_host = ""
		_builders_sent = []
		if match_spec.has("networked"):
			hub_notice = PARTY_LOST_NOTICE if after_end else LINK_LOST_NOTICE
			last_notice = hub_notice
	if client:
		client.rearm()
	_hide_loading()
	_hide_match_found()
	match_host = null
	match_spec = {}
	requeue_after = false
	found = {}
	screen = where_to
	var queued := _connected() and str(queue.get("state", "")) == "queued"
	_set_state(State.QUEUED if queued else (State.HUB if _connected() else State.OFFLINE))
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
	var host := host_of(url)
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
	if link_factory.is_valid():
		client.link_factory = link_factory  # (a reconnect's link is the test's too)
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


## A party's link opened (play/?join=K7Q4M): joins it at once, or, on a first launch, once
## the player has named themselves (name_confirmed), so the party sees the name they chose
## and not the generated one. False while the code is not five code symbols.
func open_link(typed: String) -> bool:
	var code := clean_code(typed)
	if not code_ok(code):
		return false
	if profile.named:
		return join_code(code)
	link_code = code
	return true


## The first launch's name is in (NamePrompt): a join link waiting for it connects now.
func name_confirmed() -> void:
	if link_code == "":
		return
	var code := link_code
	link_code = ""
	join_code(code)


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


## A party of my own on the server we are on (or the official one), at my level.
func create_party() -> void:
	if _connected():
		if not party.is_empty():
			_party("leave")
		_create()
	else:
		connect_to(official_address)


## PARTY create in my mode, then (M8) PARTY difficulty when my level is not Normal: a new
## party starts at its creator's level. The server takes them in order, so the creator leads
## when the second comes.
func _create() -> void:
	_party("create", {"mode": Profile.wire_mode(profile.mode)})
	if profile.difficulty != MatchRules.NORMAL:
		_party("difficulty", {"difficulty": MatchRules.level_id(profile.difficulty)})


## Leaves the party and the server: back to offline, a party of one.
func leave_party() -> void:
	if _connected() and not party.is_empty():
		_party("leave")
	disconnect_server()
	_set_state(State.OFFLINE)


func disconnect_server() -> void:
	_forget_queue()
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


## The level (M8; design 2.6, 5.2): the profile's always, and the party's too when I lead it
## (PARTY difficulty: every Ready cleared). A member's click changes only the profile; the
## hub shows the party's. Not an unknown level. While the party is out of forming (queued,
## loading, in a match) the server answers the pick with the party's level, so the profile
## keeps its own too: the level shown and the level played stay one.
func set_difficulty(id: String) -> void:
	if not MatchRules.known(id):
		return
	if party.is_empty() or str(party.get("phase", "forming")) == "forming":
		profile.set_difficulty(id)
	if is_leader() and not party.is_empty() and str(party.get("difficulty", "")) != id:
		_party("difficulty", {"difficulty": MatchRules.level_id(id)})


## Whether my click on the hub's level words picks a level now: the mode takes one, and I
## play alone or lead a party still forming (the server keeps a queued, loading or playing
## party's level, as it does its open seats while it loads).
func picks_difficulty() -> bool:
	if not offers_difficulty(mode_id()) or not is_leader():
		return false
	return party.is_empty() or str(party.get("phase", "forming")) == "forming"


## The level a Try plays (a solo High Water): the hub's where the hub's mode takes one, so a
## Try plays the level the hub lights; Normal where the hub lights none (a duel), as every
## match the hub starts plays the level it shows (design 2.6).
func try_level() -> String:
	if not offers_difficulty(mode_id()):
		return MatchRules.NORMAL
	return MatchRules.level_of("high_water", difficulty_id())


## The level the hub shows and its matches play where the mode takes one: the party's in a
## party, else the profile's (contract-m8 §3).
func difficulty_id() -> String:
	if not party.is_empty() and MatchRules.known(str(party.get("difficulty", ""))):
		return str(party["difficulty"])
	return profile.difficulty


## Whether `mode` takes a level (protocol.json's `levels`: High Water and Tide Race; a duel and
## classic play Normal).
static func offers_difficulty(mode: String) -> bool:
	return MatchRules.takes_level(mode)


## Open seats (design 5.2), the leader's: the queue fills them with strangers.
func set_open(on: bool) -> void:
	if is_leader() and not party.is_empty():
		_party("open", {"on": 1 if on else 0})


## The leader moves `member` to the other team (a race party, design 5.2), where can_move.
func move_team(member: int) -> void:
	if not can_move(member):
		return
	for m: Dictionary in members():
		if int(m["member"]) == member:
			_party("team", {"member": member, "team": 1 - int(m["team"])})


## Whether the leader may move `member` to the other team now: a forming two-team party. In a
## race any row moves, as in 0.7.0: a full race of four at 2-2 regroups through 3-1, one move
## at a time. In a duel no row moves onto the side already taken, so a duel of two stays one a
## side (two on one side may part).
func can_move(member: int) -> bool:
	if not is_leader() or party.is_empty() or not is_race(mode_id()) or str(party["phase"]) != "forming":
		return false
	var sizes := [0, 0]
	var team := -1
	for m: Dictionary in members():
		sizes[clampi(int(m["team"]), 0, 1)] += 1
		if int(m["member"]) == member:
			team = clampi(int(m["team"]), 0, 1)
	if team < 0:
		return false
	return not is_duel(mode_id()) or sizes[1 - team] < team_seats(mode_id())


## Find players or Find a rival: QUEUE enter ("Entering queue..." until the server answers).
func enter_queue() -> void:
	if not _connected() or party.is_empty() or queue_request != "":
		return
	queue_request = "enter"
	client.send("QUEUE", {"op": NetProtocol.enum_value("queue_ops", "enter")})
	changed.emit()


## Cancel: QUEUE leave ("Leaving queue..." until the server answers).
func leave_queue() -> void:
	if not _connected() or queue_request != "" or state != State.QUEUED or not is_leader():
		return
	queue_request = "leave"
	client.send("QUEUE", {"op": NetProtocol.enum_value("queue_ops", "leave")})
	changed.emit()


## After the offer: the party's match at once, caretakers in the free seats (a race: a
## caretaker rival team).
func start_with_caretakers() -> void:
	if not _connected() or not queue_offer() or not is_leader():
		return
	client.send("QUEUE", {"op": NetProtocol.enum_value("queue_ops", "start_with_caretakers")})


## Match Found's Accept (design 5.5).
func accept_match() -> void:
	_answer_found(true)


## Match Found's decline: the match dissolves, this party back to forming.
func decline_match() -> void:
	_answer_found(false)


func _answer_found(yes: bool) -> void:
	if found.is_empty() or str(found["answer"]) != "" or not _connected():
		return
	found["answer"] = "accept" if yes else "decline"
	client.send("ACCEPT", {"match": int(found["match"]), "yes": 1 if yes else 0})
	changed.emit()


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
	if strangers_match:
		return ""  # (strangers never start without a seat: their barrier's timers decide)
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


## The mode the hub plays: the party's (its leader's choice), else mine.
func mode_id() -> String:
	if not party.is_empty() and str(party.get("mode", "")) != "":
		return str(party["mode"])
	return profile.mode


## Whether `mode` sets two teams against each other (Tide Race, Undertow).
static func is_race(mode: String) -> bool:
	var modes: Dictionary = NetProtocol.spec()["modes"]
	return modes.has(mode) and int(modes[mode]["teams"]) > 1


static func max_seats(mode: String) -> int:
	var modes: Dictionary = NetProtocol.spec()["modes"]
	return int(modes[mode]["seats"][1]) if modes.has(mode) else NetProtocol.number("max_seats")


## Whether `mode` is a duel: two teams of one seat each (Undertow, design 1.4).
static func is_duel(mode: String) -> bool:
	return is_race(mode) and team_seats(mode) == 1


## The most seats a team of `mode` holds: all of them in a one-team mode, half in a race.
@warning_ignore("integer_division")
static func team_seats(mode: String) -> int:
	var modes: Dictionary = NetProtocol.spec()["modes"]
	var teams := int(modes[mode]["teams"]) if modes.has(mode) else 1
	return maxi(1, max_seats(mode) / maxi(1, teams))


## What a party of one in a two-team mode plays against the caretaker: "Race the caretaker"
## (Tide Race) or "Duel the caretaker" (Undertow).
static func caretaker_word(mode: String) -> String:
	return DUEL_CARETAKER if is_duel(mode) else RACE_CARETAKER


## NOTICE caretakers_offered in the words of the party's mode: a one-team mode's open seats,
## a race's rival team, a duel's rival.
func offer_text() -> String:
	if is_duel(mode_id()):
		return OFFER_DUEL
	if is_race(mode_id()):
		return OFFER_RACE
	return str(NOTICE_TEXT["caretakers_offered"])


## Whether the party has open seats on (PARTY_STATE flags): a one-team mode's, so never in
## a race, whose queue finds a rival team (the server turns them off with the mode).
func open_seats() -> bool:
	if party.is_empty() or is_race(mode_id()):
		return false
	return (int(party["flags"]) & NetProtocol.enum_value("party_flags", "open")) != 0


## A race party all on one team (Find a rival).
func one_team() -> bool:
	var teams := {}
	for m: Dictionary in members():
		teams[int(m["team"])] = true
	return teams.size() <= 1


## A race party on two teams of one size (Start).
func even_teams() -> bool:
	var sizes := [0, 0]
	for m: Dictionary in members():
		sizes[clampi(int(m["team"]), 0, 1)] += 1
	return sizes[0] > 0 and sizes[0] == sizes[1]


## Milliseconds queued, counted on from the server's elapsed_ms.
func queue_ms() -> int:
	if str(queue.get("state", "")) != "queued":
		return 0
	return int(queue["elapsed"]) + maxi(0, _now() - int(queue["at"]))


func queue_offer() -> bool:
	return str(queue.get("state", "")) == "queued" and bool(queue.get("offer", false))


## The pill's words: "Finding players 0:42", "Finding a rival 1:05".
func queue_text() -> String:
	var finding := FINDING_RIVAL if is_race(mode_id()) else FINDING_PLAYERS
	return "%s %s" % [finding, clock_text(queue_ms())]


## Seconds left to answer Match Found, from the server's ms_left (0 when none).
func found_seconds() -> int:
	if found.is_empty():
		return 0
	var left := int(found["ms_left"]) - maxi(0, _now() - int(found["at"]))
	return maxi(0, ceili(left / 1000.0))


## The share of Match Found's window left, 1 at its start.
func found_share() -> float:
	if found.is_empty():
		return 0.0
	var left := int(found["ms_left"]) - maxi(0, _now() - int(found["at"]))
	return clampf(float(left) / float(NetProtocol.number("accept_ms")), 0.0, 1.0)


## "0:42", "12:05".
static func clock_text(ms: int) -> String:
	var seconds := maxi(0, ms) / 1000
	return "%d:%02d" % [seconds / 60, seconds % 60]


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


## The party's link, play/?join=CODE. The link always opens the official server, so it
## leads to this party only while the party lives there: "" anywhere else (a LAN or a
## server of your own), where the code is what to pass on.
func join_link() -> String:
	return JOIN_LINK % party_code() if on_official() and party_code() != "" else ""


## Whether the server we are on is the official one (data/net.json's).
func on_official() -> bool:
	if server_host == "" or official_address == "":
		return false
	return server_host == host_of(NetAddress.url(official_address))


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


## The official server's URL as data/net.json names it (through the address rule, so a
## bare host name would do too); "" when the file is missing or says none, and then Join
## has no Official server and a bare code nowhere to go.
static func official_url() -> String:
	var parsed: Variant = null
	if FileAccess.file_exists(NET_FILE):
		parsed = JSON.parse_string(FileAccess.get_file_as_string(NET_FILE))
	var url := NetAddress.url(str((parsed as Dictionary).get("official", ""))) if parsed is Dictionary else ""
	if url == "":
		push_warning("%s names no official server" % NET_FILE)
	return url


## The host a server URL names, as the hub shows it: "groundhold.saschb2b.com",
## "192.168.1.20" (the protocol's own port left out), "host:9000".
static func host_of(url: String) -> String:
	var host := url.substr(url.find("://") + 3) if url.contains("://") else url
	if host.contains("/"):
		host = host.substr(0, host.find("/"))
	if host.ends_with(":%d" % NetProtocol.number("port")):
		host = host.substr(0, host.length() - str(NetProtocol.number("port")).length() - 1)
	return host


## The line the game prints as the hub first opens: "Groundhold 0.6.0 (build 42), official
## server wss://groundhold.saschb2b.com/causeway". The version is project.godot's
## config/version, the build data/build.json's.
func banner() -> String:
	return "%s %s (build %d), official server %s" % [
		ProjectSettings.get_setting("application/config/name", "Groundhold"),
		ProjectSettings.get_setting("application/config/version", "?"), build_seq(),
		official_address if official_address != "" else "none"]


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
	var url := NetAddress.url(address)
	joining.player_name = player_name if player_name != "" else profile.player_name
	joining.token = Identity.token_for(url)
	joining.build_seq = build_seq()
	joining.web = OS.has_feature("web")
	# (a game killed or closed mid-match asks its seat back when it starts again, M4)
	joining.remember_seat = true
	var held := Identity.held_seat(url)
	if not held.is_empty():
		joining.resume_seat(int(held[0]), int(held[1]), int(held[2]))
	return joining


# ── The server's side ──


func _on_welcomed() -> void:
	_set_state(State.HUB)
	if pending_code != "":
		_party("join", {"code": pending_code.to_ascii_buffer()})
		pending_code = ""
	else:
		_create()


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
			elif key == "caretakers_offered":
				_notice(offer_text())
			else:
				_notice(str(NOTICE_TEXT.get(key, "The server says no")))
		"QUEUE_STATE":
			_on_queue_state(fields)
		"MATCH_FOUND":
			_on_match_found(fields)


func _on_party_state(fields: Dictionary) -> void:
	if (fields["members"] as Array).is_empty():
		# (the no-party state: a code of zero bytes, leader 255, nobody; a party of one again)
		party = {}
		me = -1
		_builders_sent = []
		if state in [State.COUNTDOWN, State.QUEUED, State.MATCH_FOUND, State.CONNECTING]:
			# (out of the party, out of its queue and its Match Found too)
			_forget_queue()
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
		"difficulty": MatchRules.level_name(int(fields["difficulty"])),
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
	if state in [State.HUB, State.COUNTDOWN, State.QUEUED, State.CONNECTING, State.MATCH_FOUND]:
		match str(party["phase"]):
			"countdown":
				_set_state(State.COUNTDOWN)
			"queued":
				if state != State.MATCH_FOUND:
					_set_state(State.QUEUED)
			"forming", "results":
				found = {}
				_hide_match_found()
				_set_state(State.HUB)
	changed.emit()


## QUEUE_STATE: the queue as the server has it now; the request on its way is answered.
func _on_queue_state(fields: Dictionary) -> void:
	var queued := NetProtocol.enum_name("queue_states", int(fields["state"])) == "queued"
	var offer := int(fields["caretaker_offer"]) != 0
	# (the server answers each QUEUE with one QUEUE_STATE, but also says the offer unasked at
	# 60 s: one that comes while a Cancel is on its way answers nothing, and the Cancel's own
	# answer follows it. Every other QUEUE_STATE answers the request on its way.)
	if not (queue_request == "leave" and queued and offer and not queue_offer()):
		queue_request = ""
	queue = {
		"state": "queued" if queued else "idle",
		"elapsed": int(fields["elapsed_ms"]),
		"offer": offer,
		"at": _now(),
	}
	if queued and state in [State.HUB, State.COUNTDOWN, State.QUEUED, State.MATCH_FOUND]:
		# (back in the queue after a match dissolved, too: the overlay goes)
		found = {}
		_hide_match_found()
		_set_state(State.QUEUED)
	elif not queued and state in [State.QUEUED, State.MATCH_FOUND]:
		found = {}
		_hide_match_found()
		_set_state(State.HUB)
	changed.emit()


## MATCH_FOUND: strangers found (design 5.5): the overlay, on the server's countdown.
func _on_match_found(fields: Dictionary) -> void:
	if not state in [State.HUB, State.QUEUED, State.MATCH_FOUND]:
		return
	var same := not found.is_empty() and int(found["match"]) == int(fields["match"])
	found = {
		"match": int(fields["match"]),
		"mode": NetProtocol.enum_name("modes", int(fields["mode"])),
		"seats": int(fields["seats"]),
		"accepted": int(fields["accepted"]),
		"ms_left": int(fields["ms_left"]),
		"at": _now(),
		"answer": str(found["answer"]) if same else "",
	}
	_set_state(State.MATCH_FOUND)
	_show_match_found()
	changed.emit()


func _on_configured() -> void:
	# (a match of strangers the queue found for a party of one: Play again queues again,
	# design 5.9; strangers always come through Match Found. Starting with caretakers left
	# the queue for the party's own match, which Play again leaves forming, as any start)
	requeue_after = state == State.MATCH_FOUND and party_size() <= 1
	strangers_match = state == State.MATCH_FOUND
	found = {}
	queue = {}
	queue_request = ""
	_hide_match_found()
	match_spec = {"networked": true, "difficulty": client.difficulty}
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
	var in_match := match_host != null
	# (a link that closed under a party, with no refusal from the server: in the hub the party
	# went with it, and that is what to say, not the link's own reason)
	var refused := client != null and (client.error_code != 0 or (client.link != null and client.link.close_code == 1008))
	_notice(PARTY_LOST_NOTICE if not in_match and not party.is_empty() and not refused else text)
	if client:
		for c: Dictionary in client.failed.get_connections():
			client.failed.disconnect(c["callable"])
	party = {}
	me = -1
	where = "offline"
	server_host = ""
	_forget_queue()
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


## Whether the session is on a server with its link open (outside a failed one).
func online() -> bool:
	return _connected()


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


func _forget_queue() -> void:
	queue = {}
	queue_request = ""
	found = {}
	_hide_match_found()


func _show_match_found() -> void:
	if _match_found == null and ResourceLoader.exists(MATCH_FOUND_OVERLAY):
		_match_found = load(MATCH_FOUND_OVERLAY).new()
		add_child(_match_found)


func _hide_match_found() -> void:
	if _match_found:
		_match_found.queue_free()
		_match_found = null


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
