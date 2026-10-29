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
## the first of two windows does. cut() drops this window's link from the server's end;
## sealed(type) counts this window's sealed commands; flood(n) sends n commands around
## the client's command bucket.
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


func _init() -> void:
	name = "LoopbackMain"
	# (the sequencer and the partner step before the main scene reads its link)
	process_physics_priority = -10


func start(cfg := {}) -> void:
	main = get_parent()
	seq = FakeSequencer.new(self, 2, "classic", int(cfg.get("seed", 1)))
	_latency = int(cfg.get("latency_turns", 1)) * SimTypes.TURN_TICKS
	mine = _client("Tamsin", 1)
	main.play_through(mine)
	_open(mine)
	_partner_at = int(cfg.get("partner_after", 0))


## This window's link, dropped by the server (its connection gone, as a lost link).
func cut() -> void:
	links[0].drop("The connection closed", 1006)


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
		_open(partner)
	seq.step()
	if partner:
		partner.advance()


func _client(player: String, number: int) -> MatchClient:
	var c := MatchClient.new()
	c.clock = _clock
	c.timed = false
	c.player_name = player
	c.token = PackedByteArray([number, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
	return c


func _open(c: MatchClient) -> void:
	var link := FakeLink.new(self, _latency, 0, 1000 + links.size())
	links.append(link)
	c.connect_with(link, "ws://loopback/causeway")


func _exit_tree() -> void:
	for link: Variant in links:
		link.conn = null
	if seq:
		seq.conns.clear()


func _clock() -> int:
	return frame * 1000 / 60
