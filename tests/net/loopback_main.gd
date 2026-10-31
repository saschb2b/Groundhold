## The main scene as one window of a networked match, against the fake sequencer (test
## level 1, design 7.1): its own MatchClient (with the views, the HUD and the input) and a
## headless partner, both on FakeLinks, everything counted in frames, so a run is
## deterministic. A scenario adds it to the main scene and starts it:
##
##   {"eval": "scene.add_child(resource('res://tests/net/loopback_main.gd').new())"},
##   {"eval": "node('LoopbackMain').start({'partner_after': 120})"},
##   {"wait_until": "scene.client.phase_name() == 'WAITING'", "timeout": 30}
##
## start(config): {"seed": 1, "latency_turns": 1, "partner_after": frames (0: at once)}.
## The partner joins after `partner_after` frames, so this window waits for it first, as
## the first of two windows does. cut(frames) loses this window's link (the cable pulled)
## and refuses its new links for `frames` frames (-1, the default: for good), so it
## reconnects with a resume HELLO meanwhile (M4) and takes its seat back after; mute() lets
## nothing through its link, which never closes (the game's silence rule finds it); hide(frames)
## hides its tab as the browser would (WebBridge's handler, main.tab_hidden): its loop
## sleeps while its link fills; corrupt(field, value) writes into its simulation (its next
## hash parts from the partner's); sealed(type) counts this window's sealed commands;
## flood(n) sends n commands around the client's command bucket; stall_partner(frames)
## hangs the partner's game, hide_partner(frames) hides its tab.
@warning_ignore_start("integer_division")
extends Node

const FakeSequencer := preload("res://tests/net/fake_sequencer.gd")
const FakeLink := preload("res://tests/net/fake_link.gd")

var seq: FakeSequencer
var frame := 0
var main: Node
var mine: MatchClient
var partner: MatchClient
var links: Array = []

var _partner_at := -1
var _latency := 1
## This window's new links are refused while frame < it (-1: for good, 0: never).
var _refused_until := 0
## This window's tab is hidden while frame < it (-1: shown).
var _hidden_until := -1
## The partner's tab is shown again at this frame (-1: not hidden).
var _partner_shown_at := -1


func _init() -> void:
	name = "LoopbackMain"
	# (it runs on while the main scene sleeps as a hidden tab)
	process_mode = Node.PROCESS_MODE_ALWAYS
	# (the sequencer and the partner step before the main scene reads its link)
	process_physics_priority = -10


func start(cfg := {}) -> void:
	main = get_parent()
	seq = FakeSequencer.new(self, 2, "classic", int(cfg.get("seed", 1)))
	_latency = int(cfg.get("latency_turns", 1)) * SimTypes.TURN_TICKS
	mine = _client("Tamsin", 1)
	mine.link_factory = func() -> NetLink: return _new_link(1)
	main.play_through(mine)
	mine.connect_with(_new_link(1), "ws://loopback/causeway")
	_partner_at = int(cfg.get("partner_after", 0))


## This window's link is lost at once (what was on its way with it), and its new links are
## refused for `frames` frames (-1: for good).
func cut(frames := -1) -> void:
	_refused_until = -1 if frames < 0 else frame + frames
	if mine.link != null and mine.link.has_method("cut"):
		mine.link.cut()


## This window's link lets nothing through either way and never closes (`on`): a lost
## Wi-Fi, which only the game's own silence rule notices (M4 review round 2).
func mute(on := true) -> void:
	if mine.link != null and mine.link.has_method("mute"):
		mine.link.mute(on)


## This window's tab is hidden for `frames` frames: its loop sleeps (the main scene does not
## run) while what arrives fills its link's inbound buffer; then it is shown again.
func hide(frames: int) -> void:
	_hidden_until = frame + frames
	main.tab_hidden(true)
	main.process_mode = Node.PROCESS_MODE_DISABLED


## The partner's game hangs for `frames` frames (it neither reads nor steps nor says a
## word), so its seat goes AWAY after 5 s and comes BACK with its first word after.
func stall_partner(frames: int) -> void:
	partner.stalled_frames = frames


## The partner's tab is hidden for `frames` frames: VISIBILITY hidden, then its loop sleeps;
## shown again it catches up and says shown.
func hide_partner(frames: int) -> void:
	partner.set_hidden(true)  # (VISIBILITY hidden goes out at once, before the loop sleeps)
	partner.stalled_frames = frames
	_partner_shown_at = frame + frames


## Writes straight into this window's simulation, as a bug would.
func corrupt(field: String, value: int) -> void:
	match field:
		"gold":
			mine.sim.seat(mine.seat).gold = value
		"lives":
			mine.sim.teams[0].lives = value


## Whether the world refuses `link` now (FakeLink.open asks): this window's while cut.
func refuses(link: Variant) -> bool:
	if int(link.client_index) != 1:
		return false
	return _refused_until < 0 or frame < _refused_until


## How many commands of `type_name` ("READY") from this window the sequencer sealed.
func sealed(type_name: String) -> int:
	var type := SimTypes.command_type(type_name)
	var count := 0
	for entries: Array in seq.turns:
		for e: Array in entries:
			if int(e[0]) == mine.seat - 1 and int(e[2]) == type:
				count += 1
	return count


## Sends `n` READY commands at once around the client's own bucket, as a game without
## one would: the sequencer's bucket refuses the connection (ERROR 8).
func flood(n: int) -> void:
	for i in n:
		mine._send_command(1000 + i, SimTypes.CMD_READY, 0, 0, 0)


func _physics_process(_delta: float) -> void:
	if seq == null:
		return
	frame += 1
	if partner == null and _partner_at >= 0 and frame >= _partner_at:
		partner = _client("Edda", 2)
		partner.connect_with(_new_link(2), "ws://loopback/causeway")
	seq.step()
	if partner:
		if _partner_shown_at >= 0 and frame >= _partner_shown_at:
			_partner_shown_at = -1
			partner.set_hidden(false)
		partner.advance()
	if _hidden_until >= 0:
		if frame < _hidden_until:
			if mine.link != null and mine.link.has_method("buffer_hidden"):
				mine.link.buffer_hidden()
		else:
			_hidden_until = -1
			main.process_mode = Node.PROCESS_MODE_INHERIT
			main.tab_hidden(false)


func _client(player: String, number: int) -> MatchClient:
	var c := MatchClient.new()
	c.clock = _clock
	c.timed = false
	c.player_name = player
	c.token = PackedByteArray([number, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
	return c


func _new_link(index: int) -> NetLink:
	var link := FakeLink.new(self, _latency, 0, 1000 + links.size())
	link.client_index = index
	links.append(link)
	return link


func _exit_tree() -> void:
	for link: Variant in links:
		link.conn = null
	if seq:
		seq.conns.clear()


func _clock() -> int:
	return frame * 1000 / 60
