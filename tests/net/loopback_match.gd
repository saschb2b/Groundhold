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
## lose_turns(k, count), push_turn(k, number), push_resync(k, tick, open_turn, parts),
## hashes_agree(), tick(k), hash_hex(k).
##
## M4's faults (design 7.2): cut(k, frames) loses client k's link at once and refuses its
## new links for `frames` frames (-1: for good), so it reconnects with a resume HELLO;
## hide(k, frames, inbound_bytes) hides its tab: VISIBILITY hidden, then it neither reads
## nor steps while what arrives fills its inbound buffer (whole messages past
## `inbound_bytes` are dropped), then shown again; corrupt_uploads(k) flips a byte of its
## checkpoint uploads; delay(k, latency_turns, jitter_turns); mute(k) lets nothing through
## its link either way, which never closes. bots(on, which) lets the plan
## bot play clients' seats by commands (the caretaker's decisions, sent as orders, Ready
## once nothing more can be bought), so a match lasts; run_until(expr, frames) runs frames
## until an expression on the scene is true; system_sent(name, seat), refused(k, reason).
## kill_game(k) ends client k's game at once, as a kill or a crash would (its link drops
## with no goodbye, its MatchClient is gone), and boot_again(k) starts it again with the
## same token: its first HELLO names the seat user://net.cfg noted for it ("remember": the
## clients whose MatchClient notes its seat, as a --join game does) or the one it is given.
## start()'s config also takes "builders" (by seat),
## "caretakers" (every seat the caretaker's from tick 0), "late" (clients that send
## LOADED only on load(k): the sequencer starts without them once its loading minimum has
## passed), "resilience" (false:
## M1's sequencer) and "inbound_bytes".
@warning_ignore_start("integer_division")
extends Node

const FakeSequencer := preload("res://tests/net/fake_sequencer.gd")
const FakeLink := preload("res://tests/net/fake_link.gd")
## How often (frames) a bot takes its next step, as tests/bot.gd does in a window.
const BOT_EVERY := 15

var seq: FakeSequencer
var clients: Array[MatchClient] = []
var links: Array = []
var frame := 0
var config := {}
## Per client: the frame its tab shows again (hidden while frame < it), -1 shown.
var hidden_until: Array = []
## Per client: its new links are refused while frame < it (-1 for good, 0 never).
var refused_until: Array = []
## Clients whose new links stay connecting for good (black_hole).
var black_holed: Array = []
## Per client: whether the plan bot plays it, and the plan step it is on.
var bot_on: Array = []
var bot_step: Array = []
## Per client: every connection state it showed, in order, without repeats (for asserts
## on what the overlay went through): ["NONE", "RECONNECTING", "CATCHING_UP", ...].
var states_seen: Array = []
## Per client: every bar value (per mille) the overlay showed, without repeats.
var bars_seen: Array = []
## Per client: each build window as its simulation opened it: [wave, tick, ready count
## ([ready, seats]), every seat's state, every seat's towers], in order.
var windows: Array = []
## Per client: the largest gap (turns missing below the highest seen) it ever had.
var widest_gap: Array = []

var _latency: Array = []
var _jitter := 0


## {"mode": "classic", "clients": 2, "seed": 1, "latency_turns": 0 or [per client],
##  "jitter_turns": 0, "names": [...], "builders": [...], "caretakers": false,
##  "late": [client numbers], "resilience": true, "inbound_bytes": 1048576}
func start(cfg := {}) -> void:
	config = cfg
	var count := int(cfg.get("clients", 2))
	seq = FakeSequencer.new(self, count, str(cfg.get("mode", "classic")), int(cfg.get("seed", 1)))
	seq.resilience = bool(cfg.get("resilience", true))
	seq.seat_builders = cfg.get("builders", [])
	if bool(cfg.get("caretakers", false)):
		seq.seat_override = {"flags": NetProtocol.enum_value("seat_flags", "caretaker")}
	var late: Array = cfg.get("late", [])
	if not late.is_empty():
		# (the seats loaded start once the minimum has passed, not after a strangers' 45 s)
		seq.strangers_start_frames = seq.loading_min
	clients.clear()
	links.clear()
	hidden_until.clear()
	refused_until.clear()
	black_holed.clear()
	bot_on.clear()
	bot_step.clear()
	states_seen.clear()
	bars_seen.clear()
	windows.clear()
	widest_gap.clear()
	_latency.clear()
	var latency: Variant = cfg.get("latency_turns", 0)
	_jitter = int(cfg.get("jitter_turns", 0)) * SimTypes.TURN_TICKS
	var names: Array = cfg.get("names", [])
	for k in count:
		var delay: int = int(latency[k]) if latency is Array else int(latency)
		_latency.append(delay * SimTypes.TURN_TICKS)
		hidden_until.append(-1)
		refused_until.append(0)
		bot_on.append(false)
		bot_step.append(0)
		states_seen.append(["NONE"])
		bars_seen.append([])
		windows.append([])
		widest_gap.append(0)
		var client := MatchClient.new()
		client.clock = _clock
		client.timed = false
		client.player_name = str(names[k]) if k < names.size() else "Seat %d" % (k + 1)
		client.token = PackedByteArray([k + 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
		client.defer_loaded = late.has(k + 1)
		client.remember_seat = (cfg.get("remember", []) as Array).has(k + 1)
		var index := k + 1
		client.link_factory = func() -> NetLink: return _new_link(index)
		var link := _new_link(k + 1)
		client.connect_with(link, "ws://loopback/causeway")
		clients.append(client)


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


## Runs frames until `expr` (an expression on this scene: "client(2).rejoins == 1") is
## true, at most `frames`; returns whether it came true.
func run_until(expr: String, frames: int) -> bool:
	var test := Expression.new()
	if test.parse(expr) != OK:
		push_error("run_until: " + test.get_error_text())
		return false
	for i in frames:
		if _holds(test):
			return true
		_frame()
	return _holds(test)


# (an expression that fails to evaluate, as an index past an empty list, does not hold)
func _holds(test: Expression) -> bool:
	var value: Variant = test.execute([], self, false)
	return not test.has_execute_failed() and value is bool and value


## Whether the sequencer injected system command `name` ("AWAY") for wire seat `seat`.
func system_sent(name: String, seat: int) -> bool:
	for entry: Array in seq.system_log:
		if entry[1] == name and int(entry[2]) == seat:
			return true
	return false


## How many of client k's orders the simulation refused for `reason` ("CARETAKEN").
func refused(k: int, reason: String) -> int:
	var count := 0
	for r: Array in clients[k - 1].refusals:
		if SimTypes.refusal_name(int(r[2])) == reason:
			count += 1
	return count


## Client k neither reads its link nor steps for `turns` turns: a hung or busy process.
## Its link keeps filling meanwhile; afterwards it catches up.
func stall(k: int, turns: int) -> void:
	clients[k - 1].stalled_frames = turns * SimTypes.TURN_TICKS


## Client k's link is lost at once (what was on its way with it), and its new links are
## refused for `frames` frames (-1: for good): it reconnects every reconnect_ms meanwhile.
func cut(k: int, frames := 0) -> void:
	var link: Variant = clients[k - 1].link
	refused_until[k - 1] = -1 if frames < 0 else frame + frames
	if link != null:
		link.cut()


## Client k's link lets nothing through either way and never closes (`on`; false lets it
## through again): a stalled router or a lost Wi-Fi, which only the game's own silence
## rule notices.
func mute(k: int, on := true) -> void:
	var link: Variant = clients[k - 1].link
	if link != null:
		link.mute(on)


## Client k's game is killed: its link drops at once, with nothing on its way and no
## goodbye, and its MatchClient stops; the seat is held for it (AWAY after its silence).
func kill_game(k: int) -> void:
	var c := clients[k - 1]
	if c.link != null:
		c.link.cut()
	var stopped := MatchClient.new()  # (nothing of the killed game advances any more)
	stopped.token = c.token
	stopped.player_name = c.player_name
	stopped.remember_seat = c.remember_seat
	clients[k - 1] = stopped


## Client k's game starts again, as a player starts it after a kill: the same token, a
## new MatchClient and a new link. Its first HELLO is a resume naming `match_id`'s wire
## seat `wire_seat`, or (match_id -1) the seat user://net.cfg notes (Identity.held_seat).
func boot_again(k: int, match_id := -1, wire_seat := -1) -> MatchClient:
	var old := clients[k - 1]
	var client := MatchClient.new()
	client.clock = _clock
	client.timed = false
	client.player_name = old.player_name
	client.token = old.token
	client.remember_seat = old.remember_seat
	var url := "ws://loopback/causeway"
	if match_id < 0:
		var held := Identity.held_seat(url)
		if not held.is_empty():
			client.resume_seat(int(held[0]), int(held[1]), int(held[2]))
	else:
		client.resume_seat(match_id, wire_seat)
	var index := k
	client.link_factory = func() -> NetLink: return _new_link(index)
	client.connect_with(_new_link(k), url)
	clients[k - 1] = client
	return client


## Client k's tab is hidden for `frames` frames: VISIBILITY hidden, then its loop sleeps
## while its inbound buffer (`inbound_bytes`) fills and drops whole messages; then it is
## shown again and catches up.
func hide(k: int, frames: int, inbound_bytes := NetLink.INBOUND_BYTES) -> void:
	var c := clients[k - 1]
	c.set_hidden(true)
	if c.link != null and c.link.has_method("buffer_hidden"):
		c.link.inbound_bytes = inbound_bytes
	hidden_until[k - 1] = frame + frames


## Every checkpoint client k uploads from now on goes up with one byte flipped.
func corrupt_uploads(k: int, on := true) -> void:
	for link: Variant in links:
		if link.client_index == k:
			link.corrupt_parts = on


## Client k's link gets another latency and jitter, in turns.
func delay(k: int, latency_turns: int, jitter_turns := 0) -> void:
	_latency[k - 1] = latency_turns * SimTypes.TURN_TICKS
	var link: Variant = clients[k - 1].link
	if link != null:
		link.delay(latency_turns * SimTypes.TURN_TICKS, jitter_turns * SimTypes.TURN_TICKS)


## The plan bot plays the seats of `which` (client numbers; [] for all) by commands.
func bots(on := true, which := []) -> void:
	for k in clients.size():
		if which.is_empty() or which.has(k + 1):
			bot_on[k] = on


## A late client (start's "late") has built its hollow: LOADED now.
func load(k: int) -> void:
	clients[k - 1].loaded()


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
	var link = c.link
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


## The sequencer sends client k a RESYNC(desync) from `tick` to `open_turn` with `parts`
## parts and no parts after it, as a buggy or hostile server might.
func push_resync(k: int, tick: int, open_turn: int, parts := 1) -> void:
	var fields := {
		"checkpoint_tick": tick,
		"first_turn": tick / SimTypes.TURN_TICKS,
		"reason": NetProtocol.enum_value("resync_reasons", "desync"),
		"open_turn": open_turn,
		"checkpoint_hash": PackedByteArray([1, 2, 3, 4, 5, 6, 7, 8]),
		"parts": parts,
	}
	seq._send_bytes(seq.seat_conn(k - 1), NetProtocol.encode("RESYNC", fields))


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


## Client k's desync dump read back (DesyncDump.read), {} for none.
func dump(k: int) -> Dictionary:
	var path := clients[k - 1].dump_path
	return DesyncDump.read(path) if path != "" else {}


## A checkpoint's digest in hex (Checkpointing.digest).
func digest_hex(bytes: PackedByteArray) -> String:
	return Checkpointing.digest(bytes).hex_encode()


## The state hash a dump replays to at `tick` (DesyncDump.replay), "" when it cannot.
func replay_hash(d: Dictionary, tick: int) -> String:
	var sim := DesyncDump.replay(d, tick)
	return sim.state_hash_hex() if sim != null else ""


## Whether clients a and b sent the same hash at every tick both sent one.
func pair_agrees(a: int, b: int) -> bool:
	var ha: Dictionary = clients[a - 1].sent_hashes
	var hb: Dictionary = clients[b - 1].sent_hashes
	var shared := 0
	for t: int in ha:
		if hb.has(t):
			shared += 1
			if hb[t] != ha[t]:
				return false
	return shared > 0


## The hash ticks from `from` on that every client sent, and whether all agree there.
func sent_hashes_agree_from(from: int) -> bool:
	var ticks := common_hash_ticks().filter(func(t: int) -> bool: return t >= from)
	for t: int in ticks:
		for c in clients:
			if c.sent_hashes[t] != clients[0].sent_hashes[t]:
				return false
	return not ticks.is_empty()


## Whether every client's match ended with `outcome`, told the final tick `tick` and stopped
## there, all in the same state.
func all_ended(outcome: String, tick: int) -> bool:
	for c in clients:
		if c.phase_name() != "ENDED" or c.outcome != outcome or c.final_tick != tick or c.sim.tick != tick:
			return false
		if c.sim.state_hash_hex() != clients[0].sim.state_hash_hex():
			return false
	return true


## The wire seats whose checkpoint uploads the sequencer kept, each once, in order.
func uploaders() -> Array:
	var out := []
	for k: Array in seq.uploads_kept:
		if not out.has(int(k[1])):
			out.append(int(k[1]))
	out.sort()
	return out


## Whether every client keeps exactly its last two checkpoints and was never resynced.
func all_kept_two_unresynced() -> bool:
	for c in clients:
		if c.checkpoints.ticks.size() != Checkpointing.KEPT or not c.resyncs.is_empty():
			return false
	return true


## Whether a client's world (as the overlay shows it) went through `names`, in this order.
func went_through(k: int, names: Array) -> bool:
	var seen: Array = states_seen[k - 1]
	var at := 0
	for name: String in seen:
		if at < names.size() and name == names[at]:
			at += 1
	return at == names.size()


## The build windows client k's simulation opened while `seat` was the caretaker's: per
## window, whether the hollow's Ready count held it as Ready as the window opened (every
## seat's own Ready is cleared then, so only a caretaken seat counts).
func away_windows(k: int, seat: int) -> Array:
	var out := []
	for w: Array in windows[k - 1]:
		if int(w[3][seat - 1]) != SimTypes.SEAT_PRESENT:
			out.append(int(w[2][0]) >= 1)
	return out


## A cell client k's simulation would take a tower on now, scanning from the map's far
## corner (away from the plans' cells).
func free_cell(k: int) -> Vector2i:
	var h := clients[k - 1].sim.hollows[0]
	for z in range(h.road.depth - 1, -1, -1):
		for x in range(h.road.width - 1, -1, -1):
			if h.road.buildable(x, z) and h.occupied[z * h.road.width + x] == 0:
				return Vector2i(x, z)
	return Vector2i(-1, -1)


## Whether every upload the sequencer dropped was wire seat `seat`'s, for `why`.
func checkpoint_drops_are(seat: int, why: String) -> bool:
	for d: Array in seq.uploads_dropped:
		if int(d[1]) != seat or str(d[2]) != why:
			return false
	return not seq.uploads_dropped.is_empty()


## Whether every tick whose upload was dropped was then kept from another seat (or
## passed by a later checkpoint before it could be).
func retaken_by_others() -> bool:
	for d: Array in seq.uploads_dropped:
		var tick := int(d[0])
		var retaken := false
		for k: Array in seq.uploads_kept:
			if int(k[0]) == tick and int(k[1]) != int(d[1]):
				retaken = true
			elif int(k[0]) > tick:
				retaken = true
		if not retaken:
			return false
	return true


## Whether each checkpoint the sequencer keeps has the agreed hash as its digest.
func kept_digests_agree() -> bool:
	for tick: int in seq.checkpoint_ticks:
		if Checkpointing.digest(seq.checkpoints[tick]).hex_encode() != str(seq.agreed.get(tick, "")):
			return false
	return not seq.checkpoint_ticks.is_empty()


## Whether client k's kept checkpoints each have, as their digest, the hash it sent there.
func client_digests_match(k: int) -> bool:
	var c := clients[k - 1]
	for i in c.checkpoints.ticks.size():
		var tick := c.checkpoints.ticks[i]
		if Checkpointing.digest(c.checkpoints.kept[i]).hex_encode() != str(c.sent_hashes.get(tick, "")):
			return false
	return not c.checkpoints.ticks.is_empty()


## Whether the ticks the clients flagged as checkpoint ticks are exactly the contract's: a
## fresh simulation run through the sequencer's turn log, asked at every hash tick.
func flagged_ticks_ok() -> bool:
	var c := clients[0]
	var sim := SimMatch.new(SimContent.rules(c.mode), c.seat_list, c.match_seed)
	var last := 0
	for tick: int in seq.flagged:
		last = maxi(last, tick)
	var then := Checkpointing.waves_of(sim)
	var expected := {}
	while sim.tick < last:
		if sim.tick % SimTypes.TURN_TICKS == 0:
			var k := sim.tick / SimTypes.TURN_TICKS
			var commands := []
			for e: Array in seq.turns[k]:
				commands.append(RemoteSequencer.from_wire({"seat": e[0], "seq": e[1], "type": e[2], "a": e[3], "b": e[4], "c": e[5]}))
			sim.apply_turn(k, commands)
		sim.step()
		if sim.tick % SimTypes.HASH_EVERY == 0:
			var now := Checkpointing.waves_of(sim)
			if Checkpointing.is_checkpoint_tick(sim.tick, now, then):
				expected[sim.tick] = true
			then = now
	var flagged := seq.flagged.keys()
	flagged.sort()
	var want := expected.keys()
	want.sort()
	return flagged == want and not want.is_empty()


## Whether client k's new links connect for ever now, never opening nor failing (a SYN
## black-holed): black_hole(k) from now on.
func black_holes(link: Variant) -> bool:
	return black_holed.has(int(link.client_index))


## Client k's new links from now on go nowhere and stay connecting (FakeLink.open asks).
func black_hole(k: int) -> void:
	black_holed.append(k)


## Whether the world refuses client k's new link now (FakeLink.open asks).
func refuses(link: Variant) -> bool:
	var k := int(link.client_index)
	if k <= 0:
		return false
	var until_frame := int(refused_until[k - 1])
	return until_frame < 0 or frame < until_frame


func _new_link(k: int) -> NetLink:
	var link := FakeLink.new(self, _latency[k - 1], _jitter, 1000 * links.size() + k)
	link.client_index = k
	link.inbound_bytes = int(config.get("inbound_bytes", NetLink.INBOUND_BYTES))
	links.append(link)
	return link


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
	for i in clients.size():
		var c := clients[i]
		if int(hidden_until[i]) >= 0:
			if frame < int(hidden_until[i]):
				if c.link != null and c.link.has_method("buffer_hidden"):
					c.link.buffer_hidden()
				continue
			hidden_until[i] = -1
			c.set_hidden(false)
		c.advance()
		if bot_on[i] and frame % BOT_EVERY == 0:
			_bot(i)
		var now: Array = c.connection_state()
		var shown: String = ConnectionOverlay.State.keys()[int(now[0])]
		if (states_seen[i] as Array)[-1] != shown:
			(states_seen[i] as Array).append(shown)
		var bar := int(now[1])
		if bar >= 0 and ((bars_seen[i] as Array).is_empty() or (bars_seen[i] as Array)[-1] != bar):
			(bars_seen[i] as Array).append(bar)
		if c.source.first_gap() >= 0:
			widest_gap[i] = maxi(int(widest_gap[i]), c.source.highest - c.source.complete_upto)
		_note_window(i)


## Notes a build window client i + 1's simulation opened since the last frame.
func _note_window(i: int) -> void:
	var sim := clients[i].sim
	if sim == null or sim.hollows[0].phase != SimTypes.PHASE_PREP:
		return
	var log: Array = windows[i]
	var h := sim.hollows[0]
	if not log.is_empty() and int(log[-1][0]) == h.wave and int(log[-1][1]) == h.window_tick:
		return
	var states := []
	var towers := []
	for s in sim.seats:
		states.append(s.state)
		towers.append(s.towers)
	log.append([h.wave, h.window_tick, sim.ready_count(0), states, towers])


## The plan bot's next step for client i + 1: the caretaker's decision on its seat's plan,
## sent as an order once the last one came back in a turn; Ready when nothing more can be
## bought in a build window.
func _bot(i: int) -> void:
	var c := clients[i]
	var sim := c.sim
	if sim == null or sim.over or c.phase != MatchClient.Phase.PLAYING or not c.source.accepts_commands():
		return
	if c.source.own_pending():
		return
	var s := sim.seat(c.seat)
	if s.state != SimTypes.SEAT_PRESENT:
		bot_step[i] = maxi(int(bot_step[i]), s.plan_cursor)
		return
	var steps: Array = sim.plans.get(s.builder, [])
	while int(bot_step[i]) < steps.size():
		var d := Caretaker.decide(sim, s, steps[bot_step[i]], s.gold)
		if d[0] == Caretaker.SKIP:
			bot_step[i] = int(bot_step[i]) + 1
			continue
		if d[0] == Caretaker.BUILD:
			c.cmd(SimTypes.CMD_BUILD, d[1], d[2], d[3])
			return
		if d[0] == Caretaker.FORK:
			c.cmd(SimTypes.CMD_FORK, d[1], d[2])
			return
		break  # (WAIT: not enough gold yet)
	var h := sim.hollows[s.hollow]
	if h.phase == SimTypes.PHASE_PREP and not s.ready and h.wave < sim.total_waves():
		c.cmd(SimTypes.CMD_READY, 1)


func _clock() -> int:
	return frame * 1000 / 60
