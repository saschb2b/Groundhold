## The hub, its party and the loading barrier against the fake sequencer in lobby mode
## (test level 1, design 7.1): the session's own connection runs on a FakeLink, the other
## members are scripted (no client), and everything counts frames, so a run is
## deterministic. It lives under the Session autoload, so it outlives the scene changes
## from the hub to the match and back:
##
##   {"eval": "Session.add_child(resource('res://tests/net/loopback_hub.gd').new())"},
##   {"eval": "Session.get_node('LoopbackHub').start({})"},
##   {"eval": "Session.get_node('LoopbackHub').host('Ana', 'lookout')"},
##   {"eval": "Session.join_code('k7q-4m')"},
##   {"wait_until": "Session.party_size() == 2", "timeout": 60}
##
## start(config): {"seed": 1, "latency_turns": 1, "mode": "high_water"}. host(name, main) makes a scripted member
## who hosts the party (code K7Q4M) before anyone joins; member(name, main) adds one to it;
## set_member(name, key, value) sets "ready", "reload" or "main"; load_member(name,
## per_mille, loaded) scripts its loading; finish(outcome) ends the match. `seq` is the
## fake sequencer.
@warning_ignore_start("integer_division")
extends Node

const FakeSequencer := preload("res://tests/net/fake_sequencer.gd")
const FakeLink := preload("res://tests/net/fake_link.gd")

var seq: FakeSequencer
var frame := 0
var links: Array = []
var _latency := 3


func _init() -> void:
	name = "LoopbackHub"
	# (the sequencer steps before the session and the match scene read their link)
	process_physics_priority = -10


func start(cfg := {}) -> void:
	seq = FakeSequencer.new(self, 4, str(cfg.get("mode", "high_water")), int(cfg.get("seed", 1)))
	seq.lobby = true
	_latency = int(cfg.get("latency_turns", 1)) * SimTypes.TURN_TICKS
	Session.link_factory = _new_link
	Session.clock = _clock
	Session.beacon.clock = _clock
	Session.official_address = "play.loopback.test"


func host(who: String, main := "lamplighter") -> void:
	seq.add_member(who, main)


func member(who: String, main := "lamplighter") -> void:
	seq.add_member(who, main)


func set_member(who: String, key: String, value: Variant) -> void:
	seq.set_member(who, key, value)


func load_member(who: String, per_mille: int, loaded := false) -> void:
	seq.script_load(who, per_mille, loaded)


func finish(outcome := "won") -> void:
	seq.finish(outcome)


func _physics_process(_delta: float) -> void:
	if seq == null:
		return
	frame += 1
	seq.step()


func _new_link() -> NetLink:
	var link := FakeLink.new(self, _latency, 0, 1000 + links.size())
	links.append(link)
	return link


func _exit_tree() -> void:
	for link: Variant in links:
		link.conn = null
	if seq:
		for conn: Dictionary in seq.conns:
			(conn["link"] as Object).set("conn", null)
		seq.conns.clear()


func _clock() -> int:
	return frame * 1000 / 60
