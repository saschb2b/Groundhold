## N networked clients and the fake sequencer in one SceneTree (test level 1, design 7.1
## and 7.2): each client is a real MatchClient with its own SimMatch, joined to the
## fake sequencer by a FakeLink with its own latency and jitter. Everything counts
## frames, so a run is deterministic and --determinism passes. The clients are headless
## (no views); the main scene shows a networked client against the real server.
##
##   {"scene": "res://tests/net/loopback_match.tscn"}
##   {"eval": "scene.start({'clients': 2, 'latency_turns': [2, 4], 'jitter_turns': 1})"}
##   {"wait_until": "scene.phase() == 'IN_MATCH'", "timeout": 600}
##   {"eval": "scene.client(1).cmd('BUILD', 0, 8, 3)"}
##   {"eval": "scene.run_turns(600)"}, {"assert": "scene.hashes_agree()"}
##
## Helpers: start(config), seq (the fake sequencer), client(k) (a MatchClient: .sim,
## .cmd(type, a, b, c), .last_refusal(), .phase_name()), phase(), run_turns(n),
## run_frames(n), stall(k, turns), corrupt(k, field, value), claim_result(k, outcome),
## lose_turns(k, count), push_turn(k, number), hashes_agree(), tick(k), hash_hex(k).
@warning_ignore_start("integer_division")
extends Node

const FakeSequencer := preload("res://tests/net/fake_sequencer.gd")
const FakeLink := preload("res://tests/net/fake_link.gd")

var seq: FakeSequencer
var clients: Array[MatchClient] = []
var links: Array = []
var frame := 0
var config := {}


## {"mode": "classic", "clients": 2, "seed": 1, "latency_turns": 0 or [per client],
##  "jitter_turns": 0, "names": [...]}
func start(cfg := {}) -> void:
	config = cfg
	var count := int(cfg.get("clients", 2))
	seq = FakeSequencer.new(self, count, str(cfg.get("mode", "classic")), int(cfg.get("seed", 1)))
	clients.clear()
	links.clear()
	var latency: Variant = cfg.get("latency_turns", 0)
	var jitter := int(cfg.get("jitter_turns", 0)) * SimTypes.TURN_TICKS
	var names: Array = cfg.get("names", [])
	for k in count:
		var delay: int = int(latency[k]) if latency is Array else int(latency)
		var link := FakeLink.new(self, delay * SimTypes.TURN_TICKS, jitter, 1000 + k)
		var client := MatchClient.new()
		client.clock = _clock
		client.timed = false
		client.player_name = str(names[k]) if k < names.size() else "Seat %d" % (k + 1)
		client.token = PackedByteArray([k + 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
		client.connect_with(link, "ws://loopback/causeway")
		clients.append(client)
		links.append(link)


func client(k := 1) -> MatchClient:
	return clients[k - 1]


## The least advanced client's phase ("IN_MATCH" once every client has a turn).
func phase() -> String:
	if clients.is_empty():
		return "IDLE"
	var least := clients[0].phase
	for c in clients:
		least = mini(least, c.phase)
	return MatchClient.PHASE_NAMES[least]


func tick(k := 1) -> int:
	var sim := clients[k - 1].sim
	return sim.tick if sim else 0


func hash_hex(k := 1) -> String:
	var sim := clients[k - 1].sim if k <= clients.size() else null
	return sim.state_hash_hex() if sim else ""


## Runs the whole loopback `n` turns (3n frames) inside one call.
func run_turns(n: int) -> int:
	return run_frames(n * SimTypes.TURN_TICKS)


func run_frames(n: int) -> int:
	for i in n:
		_frame()
	return frame


## Client k neither reads its link nor steps for `turns` turns: a hung or busy process.
## Its link keeps filling meanwhile; afterwards it catches up.
func stall(k: int, turns: int) -> void:
	clients[k - 1].stalled_frames = turns * SimTypes.TURN_TICKS


## Writes straight into client k's simulation, as a bug would: its hashes go apart.
func corrupt(k: int, field: String, value: int) -> void:
	var c := clients[k - 1]
	match field:
		"gold":
			c.sim.seat(c.seat).gold = value
		"lives":
			c.sim.teams[0].lives = value


## Client k claims the match now, as a modified game would: RESULT at its current tick
## with its hash there and `outcome` (0 won, 1 lost), while its simulation plays on. Its
## own RESULT at the real end is never sent.
func claim_result(k: int, outcome := 0) -> int:
	var c := clients[k - 1]
	var at := c.sim.tick
	c._send("RESULT", {"tick": at, "hash": c.sim.state_hash(), "outcomes": [{"outcome": outcome}]})
	c.result_sent = true
	return at


## Client k's link loses `count` TURNs still on their way to it, from the first one
## numbered past its complete turns + 4, as a full browser buffer drops whole messages.
## Returns how many it lost.
func lose_turns(k: int, count: int) -> int:
	var c := clients[k - 1]
	var link = links[k - 1]
	var first := c.source.complete_upto + 5
	var kept := []
	var lost := 0
	for entry: Array in link._down:
		var message := NetProtocol.decode(entry[1])
		if str(message.get("type", "")) == "TURN":
			var number := int(message["fields"]["turn"])
			if number >= first and number < first + count:
				lost += 1
				continue
		kept.append(entry)
	link._down = kept
	return lost


## The sequencer sends client k an empty TURN numbered `number`, as a buggy or hostile
## server might.
func push_turn(k: int, number: int) -> void:
	seq._send_bytes(seq.seat_conn(k - 1), seq._turn_bytes(number, []))


func hashes_agree() -> bool:
	return seq != null and seq.hashes_agree()


## Ticks every client sent a HASH for, and whether each client's hash there is the same.
func common_hash_ticks() -> Array:
	var ticks := []
	for t: int in clients[0].sent_hashes:
		if clients.all(func(c: MatchClient) -> bool: return c.sent_hashes.has(t)):
			ticks.append(t)
	return ticks


func sent_hashes_agree() -> bool:
	var ticks := common_hash_ticks()
	for t: int in ticks:
		for c in clients:
			if c.sent_hashes[t] != clients[0].sent_hashes[t]:
				return false
	return not ticks.is_empty()


func _exit_tree() -> void:
	# (a link and the sequencer's record of it point at each other)
	for link: Variant in links:
		link.conn = null
	if seq:
		seq.conns.clear()


func _physics_process(_delta: float) -> void:
	if seq:
		_frame()


func _frame() -> void:
	frame += 1
	seq.step()
	for c in clients:
		c.advance()


func _clock() -> int:
	return frame * 1000 / 60
