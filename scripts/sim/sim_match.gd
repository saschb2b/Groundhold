## One match as a pure function of (rules, seats, seed, turns): integers only, records in
## Arrays ordered by id, its own random number generator, no scene tree, no clock and no
## shared state, so several run side by side in one process (design 6.4).
##
## The driver calls apply_turn(k, commands) at the start of tick 3k, then step() once per
## tick, and reads what happened from drain_events(). serialize() is the checkpoint and
## state_hash() its first 8 bytes of SHA-256.
##
## Tick order (design 6.4): the turn's commands; each hollow's wave clock and spawns; the
## caretaker; creeps move; towers fire or pulse; shots land; wave clears; the end check.
##
## A race (M6, Tide Race: the rules' "race" key) gives each team a hollow of its own from
## the same map text; nothing crosses between them, and each runs its own clock, so a
## mirror plays out the same on both. The simulation draws nothing random today; anything
## a hollow ever draws must come from a stream of its own, seeded from the match seed and
## the hollow id, for that to hold. The race is decided by design 1.3's win order as soon
## as the outcome is certain (_decide_race): outcomes(), race_time(), decided_by().
##
## A duel (M7, Undertow: the rules' "duel" key) plays the race's layout under one clock
## (the rules' "clock": "shared"), and is SimUndertow's: the Drift draws from the match's
## SimRng when a window opens for both, CORK, UNCORK and SEAWALL are its commands, and its
## own stage after the hollows' clocks fizzles bottles and spawns the uncorked packs on the
## rival's road. It is decided as soon as a Holdfast falls, or after the Surge
## (SimUndertow.decide), into the same record as a race: outcomes(), decided_by().
@warning_ignore_start("integer_division")
class_name SimMatch
extends RefCounted

var rules := {}
var mode := ""
var match_seed := 1
var tick := 0
var rng := SimRng.new(1)
var next_id := 1
## The last turn applied, so a driver never applies one twice.
var turn_applied := -1
var over := false
## True when the server's TIMEOUT ended the match.
var aborted := false
var teams: Array[SimRecords.SimTeam] = []
var hollows: Array[SimRecords.SimHollow] = []
## Index i holds seat i + 1.
var seats: Array[SimRecords.SimSeat] = []
var towers: Array[SimRecords.SimTower] = []
var creeps: Array[SimRecords.SimCreep] = []
var shots: Array[SimRecords.SimShot] = []
## Off in long headless runs that never read events.
var events_on := true
var map_text := ""
## The wave list for this mode (content), and each Builder's plan for the caretaker.
var waves: Array = []
var plans := {}
## (M6) A race (the rules' "race" key): two teams on hollows of their own, decided by the
## race's win order; life_t is what a lost life adds to a team's race time.
var race := false
var life_t := 0
## (M6) The race's decision once it is certain: its rule (an index into
## SimTypes.RACE_RULES, 0 while undecided) and one outcome per team (SimTypes.OUTCOME_*).
var race_rule := 0
var race_outcomes := PackedInt32Array()
## (M6) A switch for the balance gates, never state: a decided race plays on until every
## hollow is done or fallen (or the cap), so a gate can hold the early decision against
## the finish. The decision stands as it was taken.
var play_on := false
## (M7) A duel (the rules' "duel" key, SimUndertow) and one clock for every hollow (the
## rules' "clock": "shared"): set from the rules, never state of their own.
var duel := false
var shared_clock := false
## (M7) The duel's state (the codec's M7 block): every bottle corked, in id order; the
## Drift's latest window (the wave it precedes, 0 before the first), its packs (CHECK_IDS
## indexes) and the packs it left out (a bit per CHECK_IDS index); the tick of the latest
## shared horn, -1 before the first.
var bottle_list: Array[SimRecords.SimBottle] = []
var drift_window := 0
var drift_packs := PackedInt32Array()
var drift_left := 0
var horn_tick := -1

var _events: Array = []
var _tower_by_id := {}
var _creep_by_id := {}
## Stage 5's look along the road (by_distance()): the creeps, furthest first and ties to
## the lower id, as indexes into `creeps` with their road distances. Made at most once
## between open_look() and close_look(), on the first tower that asks: no creep moves,
## spawns or dies while stage 5 runs. Never part of the state, so the codec leaves it out
## and the sim harness's record_differences skips it. Read only.
var order_idx := PackedInt32Array()
var order_dist := PackedInt64Array()
var _order_built := false
var _looking := false
## How many times by_distance() sorted the creeps for stage 5 since this SimMatch was made
## or loaded: sim_bench holds with it that a real tick (step(), not a test that opens the
## look itself) looks along the road. Never state, like the order above.
var walks := 0
## The Chime Posts standing (towers with a crack aura), in id order, rebuilt whenever a
## tower is built, forked or sold, and whether a creep may still hold a crack from one:
## stage 5 refreshes the cracks only then. Never state.
var crack_posts: Array[SimRecords.SimTower] = []
var _cracks_out := true


## `seat_list` holds one Dictionary per seat: {"team", "builder", "caretaker"}; seat
## numbers follow the list order from 1. An empty `match_rules` makes a bare match for
## SimCodec to fill.
func _init(match_rules := {}, seat_list := [], start_seed := 1, text := "") -> void:
	if match_rules.is_empty():
		return
	setup(match_rules, start_seed, text)
	for i in seat_list.size():
		var cfg: Dictionary = seat_list[i]
		add_seat(
			int(cfg.get("team", 0)),
			str(cfg.get("builder", "lamplighter")),
			SimTypes.SEAT_CARETAKER if bool(cfg.get("caretaker", false)) else SimTypes.SEAT_PRESENT
		)
	for h in hollows:
		SimWaves.open_window(self, h, true)
	if duel:
		SimUndertow.window_opened(self, hollows[0])


## A match of `mode` with `seat_count` Lamplighter seats on one team.
static func create(match_mode := "classic", seat_count := 1, start_seed := 1) -> SimMatch:
	return SimMatch.new(SimContent.rules(match_mode), default_seats(seat_count), start_seed)


static func default_seats(seat_count: int) -> Array:
	var list := []
	for i in seat_count:
		list.append({"team": 0, "builder": "lamplighter"})
	return list


## Tables, map, teams and hollows; seats come after.
func setup(match_rules: Dictionary, start_seed: int, text: String) -> void:
	rules = match_rules
	mode = str(rules.get("mode", "classic"))
	match_seed = start_seed & SimRng.MASK
	rng = SimRng.new(match_seed)
	map_text = text if text != "" else SimContent.map_text(str(rules["map"]))
	waves = SimContent.WAVES[rules["waves"]]
	race = rules.get("race") is Dictionary
	life_t = int((rules.get("race", {}) as Dictionary).get("life_t", 0)) if race else 0
	duel = rules.get("duel") is Dictionary
	shared_clock = str(rules.get("clock", "hollow")) == "shared"
	for builder: String in SimContent.BUILDER_IDS:
		plans[builder] = SimContent.plan_steps(builder, mode)
	for t in int(rules["teams"]):
		var team := SimRecords.SimTeam.new()
		team.id = t
		team.lives = int(rules["lives"])
		team.hollows.append(t)
		teams.append(team)
		var hollow := SimRecords.SimHollow.new()
		hollow.id = t
		hollow.team = t
		hollow.road = SimRoad.parse(map_text)
		hollow.occupied.resize(hollow.road.width * hollow.road.depth)
		hollows.append(hollow)


func add_seat(team: int, builder: String, state: int) -> SimRecords.SimSeat:
	var s := SimRecords.SimSeat.new()
	s.seat = seats.size() + 1
	s.team = team
	s.hollow = teams[team].hollows[0]
	s.builder = builder
	s.gold = int(rules["start_gold"])
	s.state = state
	seats.append(s)
	hollows[s.hollow].seats.append(s.seat)
	return s


# ── Driving ──


## Applies turn `turn`'s commands, in listed order, at the start of tick 3 * turn.
func apply_turn(turn: int, commands: Array) -> void:
	if tick != turn * SimTypes.TURN_TICKS:
		push_error("turn %d applied at tick %d" % [turn, tick])
	turn_applied = turn
	for cmd: Dictionary in commands:
		execute(cmd)


## One tick. Never reads a clock: the same turns give the same ticks everywhere.
func step() -> void:
	if shared_clock:
		SimUndertow.run_clock(self)
	for h in hollows:
		SimWaves.run_clock(self, h)
	if duel:
		SimUndertow.run_stage(self)
	_caretakers()
	_move_creeps()
	_fire_towers()
	_land_shots()
	for h in hollows:
		SimWaves.check_clear(self, h)
	_check_end()
	tick += 1


## Everything that happened since the last call, oldest first.
func drain_events() -> Array:
	var out := _events
	_events = []
	return out


func serialize() -> PackedByteArray:
	return SimCodec.encode(self)


static func deserialize(bytes: PackedByteArray, match_rules: Dictionary, text := "") -> SimMatch:
	return SimCodec.decode(bytes, match_rules, text)


## The first 8 bytes of SHA-256 over serialize().
func state_hash() -> PackedByteArray:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(serialize())
	return ctx.finish().slice(0, 8)


func state_hash_hex() -> String:
	return state_hash().hex_encode()


# ── Queries for views, tests and the caretaker ──


func seat(n: int) -> SimRecords.SimSeat:
	return seats[n - 1] if n >= 1 and n <= seats.size() else null


func tower(id: int) -> SimRecords.SimTower:
	return _tower_by_id.get(id)


func creep(id: int) -> SimRecords.SimCreep:
	return _creep_by_id.get(id)


func tower_at(hollow: int, x: int, z: int) -> SimRecords.SimTower:
	var h := hollows[hollow]
	if not h.road.inside(x, z):
		return null
	return tower(h.occupied[z * h.road.width + x])


func total_waves() -> int:
	return waves.size()


## (M7) The last wave the hollows play: total_waves(), and in a duel the Surge's after it.
func last_wave() -> int:
	return SimUndertow.last_wave(self)


## Spawns of the current wave still to come on a hollow.
func spawns_left(hollow: int) -> int:
	var h := hollows[hollow]
	if h.phase != SimTypes.PHASE_WAVE:
		return 0
	return h.queue.size() / 2 - h.cursor


func creeps_on(hollow: int) -> int:
	var n := 0
	for c in creeps:
		if c.hollow == hollow:
			n += 1
	return n


## How many seats of a hollow are Ready (caretaken seats count) and how many there are.
func ready_count(hollow: int) -> Array:
	var h := hollows[hollow]
	var ready := 0
	for n in h.seats:
		var s := seats[n - 1]
		if s.ready or s.state != SimTypes.SEAT_PRESENT:
			ready += 1
	return [ready, h.seats.size()]


## (M6) One MATCH_END outcome per team (SimTypes.OUTCOME_*), in team order; empty until
## the match is decided. A race gives its decision; otherwise a team that cleared its
## waves won and any other lost. A match the server's TIMEOUT aborted decided nothing.
func outcomes() -> Array:
	var out := []
	if race or duel:
		if race_rule != 0:
			for v in race_outcomes:
				out.append(v)
		return out
	if not over or aborted:
		return out
	for team in teams:
		var won := true
		for id in team.hollows:
			won = won and hollows[id].phase == SimTypes.PHASE_DONE
		out.append(SimTypes.OUTCOME_WON if won else SimTypes.OUTCOME_LOST)
	return out


## (M6) A team's race time in ticks: the tick it cleared its last wave plus life_t for
## every life it lost; -1 while it has not cleared them (or outside a race).
func race_time(team: int) -> int:
	if not race or team < 0 or team >= teams.size() or teams[team].clear_tick < 0:
		return -1
	return teams[team].clear_tick + race_penalty_t(team)


## (M6) What the lives a team lost so far add to its race time, in ticks: the "+20 s" of
## the rival line (0 outside a race).
func race_penalty_t(team: int) -> int:
	if not race or team < 0 or team >= teams.size():
		return 0
	return life_t * maxi(0, int(rules["lives"]) - teams[team].lives)


## (M6) What decided the race: "time", "fell", "cap" or "draw"; (M7) a duel's "fell",
## "lives", "breach" or "draw"; "" while it runs and in a match that is neither.
func decided_by() -> String:
	return str(SimTypes.RACE_RULES[race_rule]) if race_rule > 0 and race_rule < SimTypes.RACE_RULES.size() else ""


## (M6) How many waves a team has cleared: its hollow's wave in a build window or once done,
## the one before it during a wave, and the one before the wave it fell on.
func cleared_waves(team: int) -> int:
	var t := teams[team]
	var h := hollows[t.hollows[0]]
	match h.phase:
		SimTypes.PHASE_PREP, SimTypes.PHASE_DONE:
			return h.wave
		SimTypes.PHASE_FALLEN:
			return maxi(0, (t.fell_wave if t.fell_wave > 0 else h.wave) - 1)
	return maxi(0, h.wave - 1)


## (M7) The Drift's packs for the window that is open, or for the wave it precedes,
## as CHECK_IDS ids in CHECK_IDS order; [] outside a duel and before drift_from.
func drift_offer() -> Array:
	var out := []
	if not duel or drift_window == 0:
		return out
	var wave := hollows[0].wave
	if drift_window != wave and drift_window != wave + 1:
		return out
	for i in drift_packs:
		out.append(SimContent.CHECK_IDS[i])
	return out


## (M7) Lives team `team`'s uncorked creeps took from the rival's Holdfast.
func breach_dealt(team: int) -> int:
	return teams[team].breach_dealt if team >= 0 and team < teams.size() else 0


## (M7) The gold seat `seat_no` is paid at each of its wave clears.
func stipend(seat_no: int) -> int:
	var s := seat(seat_no)
	return s.stipend if s else 0


## (M7) Seat `seat_no`'s bottles, oldest first: {id, tier, window, price, uncorked,
## fizzled}, and "pack" (a CHECK_IDS id) only once uncorked, so a view never holds the
## pack of a rival's corked bottle.
func bottles(seat_no: int) -> Array:
	return SimUndertow.bottles_of(self, seat_no)


## (M7) The Seawall charges seat `seat_no` holds.
func seawall_charges(seat_no: int) -> int:
	var s := seat(seat_no)
	return s.seawall_charges if s else 0


## (M7) The tick seat `seat_no`'s Seawall may rise again (0 before its first).
func seawall_ready_tick(seat_no: int) -> int:
	var s := seat(seat_no)
	return s.seawall_ready if s else 0


## (M7) Whether hollow `hollow_id`'s wave is held by the duel alone: nothing left to spawn
## and its road empty, yet a rival's bottle for it is still corked or its uncorked creeps
## are still to come (SimUndertow.holds), so it clears only at the pack's last creep or the
## bottle's fizzle, up to fizzle_t after the horn, and the next window for both waits.
func wave_held(hollow_id: int) -> bool:
	if not duel or hollow_id < 0 or hollow_id >= hollows.size():
		return false
	var h := hollows[hollow_id]
	if h.phase != SimTypes.PHASE_WAVE or h.cursor < h.queue.size() / 2 or creeps_on(h.id) > 0:
		return false
	return SimUndertow.holds(self, h)


## Gold each seat would get if the horn sounded now: one per whole second left.
func early_gold(hollow: int) -> int:
	var h := hollows[hollow]
	if h.phase != SimTypes.PHASE_PREP or not bool(rules.get("ready_pays", true)):
		return 0
	return h.countdown_t / SimTypes.TICKS_PER_SECOND


## The share of what was put into a tower its owner gets back for selling it, per mille:
## the rules' sell_pm, or the Thrifty perk's where perks are on (design 4.1).
func sell_pm(seat_no: int) -> int:
	var base := int(rules["sell_pm"])
	var s := seat(seat_no)
	if s == null or not bool(rules.get("perks", true)):
		return base
	return SimContent.perk_value(s.builder, "thrifty", "sell_pm", base)


## What selling tower `t` would pay its owner now.
func refund(t: SimRecords.SimTower) -> int:
	return SimMath.per_mille(t.invested, sell_pm(t.owner))


## Extra reach every tower of seat `seat_no` gets: the Keen Sight perk's, where perks are on.
func range_bonus(seat_no: int) -> int:
	var s := seat(seat_no)
	if s == null or not bool(rules.get("perks", true)):
		return 0
	return SimContent.perk_value(s.builder, "keen_sight", "range_mm", 0)


## (M6) Armour every hit of seat `seat_no`'s towers ignores besides their own pierce: the
## Bronze Hand perk's, where perks are on.
func pierce_bonus(seat_no: int) -> int:
	var s := seat(seat_no)
	if s == null or not bool(rules.get("perks", true)):
		return 0
	return SimContent.perk_value(s.builder, "bronze_hand", "pierce_c", 0)


## Effective speed this tick: stunned creeps stand, slowed ones walk slower.
func speed_now(c: SimRecords.SimCreep) -> int:
	if c.stun_until > tick:
		return 0
	if c.slow_until > tick and c.slow_pm > 0:
		return c.speed_um_t * (1000 - c.slow_pm) / 1000
	return c.speed_um_t


func in_range(t: SimRecords.SimTower, c: SimRecords.SimCreep) -> bool:
	if c.hollow != t.hollow or (c.winged and not t.air):
		return false
	return SimRoad.covers(t.intervals, c.dist_um)


## Stage 5 brackets the towers' look with these (and a test that compares the look with a
## scan does too): between them the creeps stand still, so by_distance() may sort them
## once; any other time it says no.
func open_look() -> void:
	_looking = true
	_order_built = false


func close_look() -> void:
	_looking = false


## While the towers look (open_look), makes order_idx and order_dist hold the creeps
## furthest first (ties to the lower id): indexes into `creeps` and their road distances;
## false at any other time, when positions may still change. Each tower's look then
## reads two packed arrays from the first creep within its farthest reach and stops at
## the first in reach, instead of testing every creep (sim_bench: the towers' look was
## nine tenths of a busy tick).
func by_distance() -> bool:
	if not _looking:
		return false
	if not _order_built:
		_order_built = true
		walks += 1
		# One integer key per creep, distance first and then the index reversed, so an
		# ascending sort read backwards gives distance descending and ties by index
		# (= by id: `creeps` is in id order) ascending. Creeps on the road number far under
		# 2^16 (a wave brings about 40; the codec writes the count as a u16, unchecked) and
		# road distances stay far under 2^40, so the key fits.
		var keys := PackedInt64Array()
		keys.resize(creeps.size())
		for i in creeps.size():
			keys[i] = creeps[i].dist_um * 65536 + (65535 - i)
		keys.sort()  # sim-lint: allow sort() integers in a total order, never objects
		var n := keys.size()
		order_idx.resize(n)
		order_dist.resize(n)
		for k in n:
			var key := keys[n - 1 - k]
			order_idx[k] = 65535 - (key & 65535)
			order_dist[k] = key >> 16
	return true


# ── Commands ──


## Runs one command as the sequencer listed it. Invalid ones change nothing and leave a
## REJECTED event for the sender's interface.
func execute(cmd: Dictionary, from_caretaker := false) -> void:
	var seat_no: int = cmd["seat"]
	var type: int = cmd["type"]
	if seat_no == SimTypes.SYSTEM_SEAT:
		_system(type, int(cmd["a"]))
		return
	var s := seat(seat_no)
	if s == null:
		return
	if over:
		_reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	if s.state != SimTypes.SEAT_PRESENT and not from_caretaker:
		_reject(s, cmd, SimTypes.REFUSE_CARETAKEN)
		return
	match type:
		SimTypes.CMD_BUILD:
			_build(s, cmd)
		SimTypes.CMD_FORK:
			_fork(s, cmd)
		SimTypes.CMD_SELL:
			_sell(s, cmd)
		SimTypes.CMD_READY:
			_set_ready(s, cmd)
		SimTypes.CMD_SIGNAL:
			_signal(s, cmd)
		SimTypes.CMD_CORK when duel:
			SimUndertow.cork(self, s, cmd)
		SimTypes.CMD_UNCORK when duel:
			SimUndertow.uncork(self, s, cmd)
		SimTypes.CMD_SEAWALL when duel:
			SimUndertow.seawall(self, s, cmd)
		_:
			_reject(s, cmd, SimTypes.REFUSE_BAD_COMMAND)


## A command the caretaker decided for a seat, applied as if it had been received.
func execute_as(seat_no: int, type: int, a := 0, b := 0, c := 0) -> void:
	execute(SimTypes.command(seat_no, 0, type, a, b, c), true)


func _build(s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var h := hollows[s.hollow]
	if h.phase == SimTypes.PHASE_DONE or h.phase == SimTypes.PHASE_FALLEN:
		_reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	var kind := SimContent.kit_tower(s.builder, int(cmd["a"]))
	if kind == "":
		_reject(s, cmd, SimTypes.REFUSE_BAD_COMMAND)
		return
	var x: int = cmd["b"]
	var z: int = cmd["c"]
	if not h.road.buildable(x, z) or h.occupied[z * h.road.width + x] != 0:
		_reject(s, cmd, SimTypes.REFUSE_CANNOT_BUILD_THERE)
		return
	var cost := int(SimContent.TOWERS[kind]["cost"])
	if s.gold < cost:
		_reject(s, cmd, SimTypes.REFUSE_NOT_ENOUGH_GOLD)
		return
	var t := SimRecords.SimTower.new()
	t.id = _new_id()
	t.owner = s.seat
	t.hollow = h.id
	t.x = x
	t.z = z
	t.kind = kind
	t.invested = cost
	t.cooldown_until = tick
	resolve_tower(t)
	towers.append(t)
	_tower_by_id[t.id] = t
	h.occupied[z * h.road.width + x] = t.id
	s.towers += 1
	_towers_changed(h.id)
	_emit(
		{
			"type": SimTypes.EV_BUILT,
			"id": t.id,
			"seat": s.seat,
			"seq": cmd["seq"],
			"kind": kind,
			"hollow": h.id,
			"x": x,
			"z": z
		}
	)
	add_gold(s, -cost, "build")


func _fork(s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var t := tower(int(cmd["a"]))
	var branch: int = cmd["b"]
	if t == null:
		_reject(s, cmd, SimTypes.REFUSE_NO_SUCH_TOWER)
		return
	if t.owner != s.seat:
		_reject(s, cmd, SimTypes.REFUSE_NOT_YOURS)
		return
	if t.branch != -1:
		_reject(s, cmd, SimTypes.REFUSE_ALREADY_FORKED)
		return
	if not SimContent.has_branch(t.kind, branch):
		_reject(s, cmd, SimTypes.REFUSE_BAD_COMMAND)
		return
	var cost := int(SimContent.TOWERS[t.kind]["fork_cost"])
	if s.gold < cost:
		_reject(s, cmd, SimTypes.REFUSE_NOT_ENOUGH_GOLD)
		return
	t.branch = branch
	t.invested += cost
	resolve_tower(t)
	s.forks += 1
	_towers_changed(t.hollow)
	_emit(
		{
			"type": SimTypes.EV_FORKED,
			"id": t.id,
			"seat": s.seat,
			"seq": cmd["seq"],
			"branch": branch,
			"form": SimContent.tower_form(t.kind, branch)
		}
	)
	add_gold(s, -cost, "fork")


func _sell(s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var t := tower(int(cmd["a"]))
	if t == null:
		_reject(s, cmd, SimTypes.REFUSE_NO_SUCH_TOWER)
		return
	if t.owner != s.seat:
		_reject(s, cmd, SimTypes.REFUSE_NOT_YOURS)
		return
	var refund := SimMath.per_mille(t.invested, sell_pm(s.seat))
	var h := hollows[t.hollow]
	h.occupied[t.z * h.road.width + t.x] = 0
	towers.erase(t)
	_tower_by_id.erase(t.id)
	s.towers -= 1
	_towers_changed(h.id)
	_emit(
		{
			"type": SimTypes.EV_SOLD,
			"id": t.id,
			"seat": s.seat,
			"seq": cmd["seq"],
			"refund": refund,
			"hollow": h.id,
			"x": t.x,
			"z": t.z
		}
	)
	add_gold(s, refund, "sell")


func _set_ready(s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	if hollows[s.hollow].phase != SimTypes.PHASE_PREP:
		_reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	s.ready = int(cmd["a"]) != 0
	_emit({"type": SimTypes.EV_READY, "seat": s.seat, "seq": cmd["seq"], "on": s.ready})


func _signal(s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var limit: Array = rules.get("signals", [3, 300])
	var most := int(limit[0])
	var window := int(limit[1])
	if s.signal_ticks.size() >= most and tick - s.signal_ticks[0] < window:
		_reject(s, cmd, SimTypes.REFUSE_RATE_LIMITED)
		return
	s.signal_ticks.append(tick)
	if s.signal_ticks.size() > most:
		s.signal_ticks.remove_at(0)
	_emit(
		{
			"type": SimTypes.EV_SIGNAL,
			"seat": s.seat,
			"x": cmd["a"],
			"z": cmd["b"],
			"target": cmd["c"]
		}
	)


func _system(type: int, seat_no: int) -> void:
	if type == SimTypes.SYS_TIMEOUT:
		over = true
		aborted = true
		return
	var s := seat(seat_no)
	if s == null:
		return
	var was := s.state
	match type:
		SimTypes.SYS_AWAY:
			if s.state == SimTypes.SEAT_PRESENT or s.state == SimTypes.SEAT_RETURNING:
				s.state = SimTypes.SEAT_AWAY
		SimTypes.SYS_BACK:
			if s.state == SimTypes.SEAT_AWAY:
				s.state = SimTypes.SEAT_RETURNING
		SimTypes.SYS_LEFT:
			s.state = SimTypes.SEAT_LEFT
	# (a seat state moves only as design 6.7 says: AWAY takes a present or returning
	# seat, BACK an away one, LEFT any, and only SimWaves.open_window makes a returning
	# seat present; EV_SEAT says when it moved, never for a command that left it be)
	if s.state != was:
		_emit({"type": SimTypes.EV_SEAT, "seat": s.seat, "state": s.state})


## A command refused for `reason` (REJECTED), as SimUndertow's commands refuse theirs.
func reject(s: SimRecords.SimSeat, cmd: Dictionary, reason: int) -> void:
	_reject(s, cmd, reason)


func _reject(s: SimRecords.SimSeat, cmd: Dictionary, reason: int) -> void:
	_emit(
		{
			"type": SimTypes.EV_REJECTED,
			"seat": s.seat,
			"seq": cmd["seq"],
			"cmd": cmd["type"],
			"reason": reason
		}
	)


# ── Debug writes (offline only; logged by the turn source with their tick) ──


## Applies a scenario setter to the state at once. The facade logs it so a replay of the
## turn log reproduces it; a networked match refuses these before they get here.
func debug(op: int, a: int, b := 0, c := 0) -> void:
	match op:
		SimTypes.DBG_GOLD:
			var s := seat(a)
			if s:
				add_gold(s, b - s.gold, "debug")
		SimTypes.DBG_LIVES:
			if a >= 0 and a < teams.size():
				set_lives(teams[a], maxi(0, b))
		SimTypes.DBG_WAVE:
			var h := hollows[a]
			h.wave = clampi(b, 0, last_wave())  # (a duel's Surge too, M7)
			_emit(
				{
					"type": SimTypes.EV_WAVE,
					"hollow": h.id,
					"wave": h.wave,
					"phase": h.phase
				}
			)
		SimTypes.DBG_COUNTDOWN:
			hollows[a].countdown_t = maxi(0, b)
		SimTypes.DBG_CREEP_DIST:
			var cr := creep(a)
			if cr:
				cr.dist_um = clampi(b, 0, hollows[cr.hollow].road.length_um)
		SimTypes.DBG_CREEP_SPEED:
			var cr := creep(a)
			if cr:
				cr.speed_um_t = maxi(0, b)
		SimTypes.DBG_SPAWN:
			SimWaves.spawn(self, hollows[a], b)
		SimTypes.DBG_SLOW:
			var cr := creep(a)
			if cr:
				apply_slow(cr, b, c, 0)
		SimTypes.DBG_TOWER_KILLS:
			var t := tower(a)
			if t:
				t.kills = b
		SimTypes.DBG_KILLS:
			if a >= 0 and a < teams.size():
				teams[a].kills = b


# ── Rules shared with SimWaves ──


func add_gold(s: SimRecords.SimSeat, change: int, why: String) -> void:
	s.gold += change
	_emit(
		{"type": SimTypes.EV_GOLD, "seat": s.seat, "gold": s.gold, "change": change, "why": why}
	)


func set_lives(team: SimRecords.SimTeam, lives: int) -> void:
	var change := lives - team.lives
	team.lives = lives
	_emit({"type": SimTypes.EV_LIVES, "team": team.id, "lives": lives, "change": change})
	if duel and change < 0:
		SimUndertow.lives_lost(self, team, -change)
	if lives == 0:
		_fall(team)


## Seats a hollow's bounty and bonuses go to: every seat on its team.
func team_seats(team: int) -> Array[SimRecords.SimSeat]:
	var out: Array[SimRecords.SimSeat] = []
	for s in seats:
		if s.team == team:
			out.append(s)
	return out


func push_event(event: Dictionary) -> void:
	_emit(event)


func new_id() -> int:
	return _new_id()


func add_creep(c: SimRecords.SimCreep) -> void:
	creeps.append(c)
	_creep_by_id[c.id] = c


## Sets a tower's numbers from its kind, its branch and its owner's perk, and its road
## stretches in range.
func resolve_tower(t: SimRecords.SimTower) -> void:
	var stats := SimContent.tower_stats(t.kind, t.branch)
	t.dmg_c = int(stats["dmg_c"])
	t.cd_t = maxi(1, int(stats["cd_t"]))
	t.range_mm = int(stats["range_mm"]) + range_bonus(t.owner)
	t.air = bool(stats.get("air", false))
	t.shot_um_t = maxi(0, int(stats["shot_um_t"]))  # 0: no shot (content.gd)
	t.min_flight_t = maxi(1, int(stats.get("min_flight_t", 1)))
	t.splash_mm = int(stats.get("splash_mm", 0))
	t.slow_pm = int(stats.get("slow_pm", 0))
	t.slow_t = int(stats.get("slow_t", 0))
	t.pierce_c = int(stats.get("pierce_c", 0))
	t.aim = SimTargeting.aim_code(str(stats.get("aim", "first")))
	t.bounces = maxi(0, int(stats.get("bounces", 0)))
	t.bounce_mm = maxi(0, int(stats.get("bounce_mm", 0)))
	t.team = SimTypes.effect(str(stats.get("team", "")))
	t.mark_pm = int(stats.get("mark_pm", 0))
	t.marks = int(stats.get("marks", 0))
	t.mark_t = int(stats.get("mark_t", 0))
	t.pierce_c += pierce_bonus(t.owner)
	t.pulse = bool(stats.get("pulse", false))
	t.stun_t = maxi(0, int(stats.get("stun_t", 0)))
	t.stun_immune_t = maxi(0, int(stats.get("stun_immune_t", 0)))
	t.air_slow_pm = int(stats.get("air_slow_pm", 0))
	t.air_slow_t = int(stats.get("air_slow_t", 0))
	t.cloud_mm = maxi(0, int(stats.get("cloud_mm", 0)))
	t.crack_c = maxi(0, int(stats.get("crack_c", 0)))
	t.hum_pm = maxi(0, int(stats.get("haste_pm", 0)))
	t.air_bonus_pm = maxi(0, int(stats.get("air_bonus_pm", 0)))
	var road := hollows[t.hollow].road
	t.intervals = road.intervals(SimRoad.centre_mm(t.x), SimRoad.centre_mm(t.z), t.range_mm)


## The strongest slow applies, for its own time; a weaker one waits under it (design 3.2;
## SimEffects).
func apply_slow(c: SimRecords.SimCreep, pm: int, ticks: int, from_seat: int, from_tower := 0) -> void:
	SimEffects.apply_slow(self, c, pm, ticks, from_seat, from_tower)


## After a tower on hollow `hollow` was built, forked or sold: the hums' haste there is
## worked out again (SimEffects.recompute_haste) and the Chime Posts listed again.
func _towers_changed(hollow: int) -> void:
	SimEffects.recompute_haste(self, hollow)
	_list_posts()


func _list_posts() -> void:
	crack_posts.clear()
	for t in towers:
		if t.crack_c > 0:
			crack_posts.append(t)


# ── The tick's stages ──


func _caretakers() -> void:
	if over:
		return
	# (M7) in a duel also on the first tick of the window both hollows share, so it corks
	# and says Ready before the horn (SimUndertow._all_ready), and when it may uncork
	var duel_tick := duel and (tick == uncork_tick() or tick == SimUndertow.shared_window_tick(self))
	for s in seats:
		if s.state == SimTypes.SEAT_PRESENT:
			continue
		var h := hollows[s.hollow]
		if tick % 30 == 0 or tick == h.window_tick or duel_tick:
			Caretaker.think(self, s)


## (M7) The first tick of the current wave a bottle may be uncorked on (-1 before the
## first horn): when the caretaker uncorks its own.
func uncork_tick() -> int:
	if horn_tick < 0:
		return -1
	return horn_tick + int(SimUndertow.rules_of(self)["uncork_after_t"])


func _move_creeps() -> void:
	var ends := PackedInt64Array()
	for h in hollows:
		ends.append(h.road.length_um)
	var i := 0
	while i < creeps.size():
		var c := creeps[i]
		# (the calls change nothing unless a slow ran out with one set or waiting, or a
		# mark ran out: asked here first, since every creep passes every tick)
		if c.slow_until <= tick and (c.slow_pm != 0 or not c.slow_next.is_empty()):
			SimEffects.lapse_slow(self, c)
		if c.mark_pm != 0 and c.mark_until <= tick:
			SimEffects.expire(self, c)
		var end := ends[c.hollow]
		c.dist_um += speed_now(c)
		if c.dist_um >= end:
			c.dist_um = end
			creeps.remove_at(i)
			_leak(c)
		else:
			i += 1


func _leak(c: SimRecords.SimCreep) -> void:
	c.alive = false
	_creep_by_id.erase(c.id)
	var h := hollows[c.hollow]
	var team := teams[h.team]
	_emit(
		{
			"type": SimTypes.EV_LEAK,
			"id": c.id,
			"kind": c.kind,
			"hollow": h.id,
			"team": team.id,
			"toll": c.toll
		}
	)
	if team.lives > 0:
		var taken := mini(team.lives, c.toll)
		set_lives(team, team.lives - taken)
		if duel and c.sent_by != 0:
			SimUndertow.breach(self, c, team, taken)


func _fall(team: SimRecords.SimTeam) -> void:
	for id in team.hollows:
		var h := hollows[id]
		if h.phase == SimTypes.PHASE_DONE or h.phase == SimTypes.PHASE_FALLEN:
			continue
		if race and team.fell_wave == 0:
			# (in a window it falls facing the next wave, of which it has killed nothing)
			team.fell_wave = h.wave + 1 if h.phase == SimTypes.PHASE_PREP else maxi(1, h.wave)
			team.fell_kills = team.wave_kills if h.phase == SimTypes.PHASE_WAVE else 0
			race_event("fell", team.id, team.fell_wave)
		h.phase = SimTypes.PHASE_FALLEN
		h.cursor = h.queue.size() / 2
		_emit(
			{
				"type": SimTypes.EV_WAVE,
				"hollow": h.id,
				"wave": h.wave,
				"phase": h.phase
			}
		)


## Stage 5, in id order. The Chime Posts' cracks come first (SimEffects.refresh_cracks),
## so every hit this tick meets the armour the creep has where it stands. A pulse (the
## Toll Tower) strikes every creep in its reach, a bee cloud (the Clay Hive) every creep
## near the one it aims at; a tower that fires no shot otherwise works by its team effect
## alone (SimEffects.team_tower: the Owl's Eye's marks; the auras need no turn); the
## others keep or pick a target by their aim (SimTargeting) and fire when cooled down.
## The strikes of pulses and clouds land once every tower has looked (_strike_all), so
## no creep dies while the towers look along the road (by_distance).
func _fire_towers() -> void:
	if not crack_posts.is_empty() or _cracks_out:
		SimEffects.refresh_cracks(self, crack_posts)
		_cracks_out = not crack_posts.is_empty()
	var strikes := PackedInt32Array()
	open_look()
	for t in towers:
		if t.pulse:
			_pulse(t, strikes)
			continue
		if t.cloud_mm > 0:
			_cloud(t, strikes)
			continue
		if t.shot_um_t == 0:
			SimEffects.team_tower(self, t)
			continue
		t.target = SimTargeting.target_for(self, t)
		if t.target != 0 and tick >= t.cooldown_until:
			_fire(t, creep(t.target))
			t.cooldown_until = tick + cooldown_of(t)
	close_look()
	if not strikes.is_empty():
		_strike_all(strikes)


## A tower's ticks until it may act again: its cd_t, divided by 1 + its haste (M6).
func cooldown_of(t: SimRecords.SimTower) -> int:
	if t.haste_pm > 0:
		return maxi(1, t.cd_t * 1000 / (1000 + t.haste_pm))
	return t.cd_t


## (M6) A pulse, once cooled down and with a creep in reach: every creep in its reach
## (fliers only where it has `air`) is struck at once (as [tower, creep] pairs into
## `strikes`), and EV_PULSE says where it rang. A pulse that has cooled down waits for
## a creep every tick, so it asks the walk along the road first whether one is in reach
## (SimTargeting.furthest, the same test as in_range), and scans every creep, in id
## order, only on the tick it rings (sim_bench's M6 board: the scan of a waiting Toll
## Tower was a third of a busy tick).
func _pulse(t: SimRecords.SimTower, strikes: PackedInt32Array) -> void:
	if tick < t.cooldown_until:
		return
	if SimTargeting.furthest(self, t, false) == 0:
		return
	var struck := false
	for c in creeps:
		if in_range(t, c):
			strikes.append(t.id)
			strikes.append(c.id)
			struck = true
	if not struck:
		return
	t.shots += 1
	t.cooldown_until = tick + cooldown_of(t)
	_emit(
		{
			"type": SimTypes.EV_PULSE,
			"tower": t.id,
			"form": SimContent.tower_form(t.kind, t.branch),
			"hollow": t.hollow,
			"x": SimRoad.centre_mm(t.x),
			"z": SimRoad.centre_mm(t.z),
			"r": t.range_mm
		}
	)


## (M6) A bee cloud: it aims as a tower does (fliers too where it has `air`) and, once
## cooled down, stings every creep on its hollow, ground or air, within cloud_mm of the one
## it aims at. cloud_creep says where the cloud hangs: the creep it last stung over while
## that one lives, 0 once it has none to aim at.
func _cloud(t: SimRecords.SimTower, strikes: PackedInt32Array) -> void:
	t.target = SimTargeting.target_for(self, t)
	if t.target == 0 or (t.cloud_creep != 0 and creep(t.cloud_creep) == null):
		t.cloud_creep = 0
	if t.target == 0:
		return
	if tick < t.cooldown_until:
		return
	var over_creep := creep(t.target)
	var road := hollows[t.hollow].road
	var x := road.x_at(over_creep.dist_um)
	var z := road.z_at(over_creep.dist_um)
	var r := t.cloud_mm
	for c in creeps:
		if c.hollow != t.hollow:
			continue
		var dx := road.x_at(c.dist_um) - x
		var dz := road.z_at(c.dist_um) - z
		if dx * dx + dz * dz <= r * r:
			strikes.append(t.id)
			strikes.append(c.id)
	t.cloud_creep = over_creep.id
	t.shots += 1
	t.cooldown_until = tick + cooldown_of(t)


## The strikes stage 5's pulses and clouds dealt, in the order they were struck: each a
## hit of its tower's damage through the armour rule, with its slow, its stun or its
## flier slow, on a creep still alive. No shot flies, so none is stored (id 0).
func _strike_all(strikes: PackedInt32Array) -> void:
	var t: SimRecords.SimTower = null
	var strike: SimRecords.SimShot = null
	var k := 0
	while k < strikes.size():
		if t == null or t.id != strikes[k]:
			t = tower(strikes[k])
			strike = _strike_of(t)
		var c := creep(strikes[k + 1])
		k += 2
		if c != null and c.alive:
			_hurt(c, strike, strike.dmg_c, false)


## A pulse's or cloud's strike as a shot that has already landed: never stored.
func _strike_of(t: SimRecords.SimTower) -> SimRecords.SimShot:
	var strike := SimRecords.SimShot.new()
	strike.tower = t.id
	strike.seat = t.owner
	strike.hollow = t.hollow
	strike.kind = t.kind
	strike.fire_tick = tick
	strike.land_tick = tick
	strike.dmg_c = t.dmg_c
	strike.slow_pm = t.slow_pm
	strike.slow_t = t.slow_t
	strike.pierce_c = t.pierce_c
	strike.air_bonus_pm = t.air_bonus_pm
	if t.pulse:
		strike.stun_t = t.stun_t
		strike.stun_immune_t = t.stun_immune_t
		strike.air_slow_pm = t.air_slow_pm
		strike.air_slow_t = t.air_slow_t
	return strike


## Schedules a shot from the tower's cell centre. Its flight time comes from the
## distance on the ground, never from where a view's barrel points; a shell lands where
## its target will be by then, clamped to the road.
func _fire(t: SimRecords.SimTower, c: SimRecords.SimCreep) -> void:
	t.shots += 1
	var road := hollows[t.hollow].road
	var dx := road.x_at(c.dist_um) - SimRoad.centre_mm(t.x)
	var dz := road.z_at(c.dist_um) - SimRoad.centre_mm(t.z)
	var d := SimMath.isqrt(dx * dx + dz * dz)
	var flight := maxi(t.min_flight_t, maxi(1, SimMath.ceil_div(d * 1000, t.shot_um_t)))
	var shot := SimRecords.SimShot.new()
	shot.id = _new_id()
	shot.tower = t.id
	shot.seat = t.owner
	shot.hollow = t.hollow
	shot.kind = t.kind
	shot.target = c.id
	shot.fire_tick = tick
	shot.land_tick = tick + flight
	shot.dmg_c = t.dmg_c
	shot.splash_mm = t.splash_mm
	shot.slow_pm = t.slow_pm
	shot.slow_t = t.slow_t
	shot.pierce_c = t.pierce_c
	shot.air_bonus_pm = t.air_bonus_pm
	shot.bounces = t.bounces
	shot.bounce_mm = t.bounce_mm if t.bounces > 0 else 0
	if t.splash_mm > 0:
		shot.land_dist_um = mini(c.dist_um + speed_now(c) * flight, road.length_um)
	shots.append(shot)
	_emit(
		{
			"type": SimTypes.EV_FIRE,
			"tower": t.id,
			"shot": shot.id,
			"target": c.id,
			"kind": t.kind,
			"flight": flight,
			"land": shot.land_dist_um,
			"from": 0,
			"form": SimContent.tower_form(t.kind, t.branch)
		}
	)


## A bouncing strike that struck `c` flies on to the nearest creep within its reach the
## chain has not struck, from where `c` stands (design 3.4, the Kestrel Flock).
func _bounce(shot: SimRecords.SimShot, c: SimRecords.SimCreep) -> void:
	if shot.bounces <= 0:
		return
	var t := tower(shot.tower)
	var base: Dictionary = SimContent.TOWERS[shot.kind]
	var air := t.air if t else bool(base.get("air", false))
	var speed := t.shot_um_t if t else int(base["shot_um_t"])
	var struck := shot.struck.duplicate()
	struck.append(c.id)
	var next := creep(SimTargeting.bounce_target(self, c, shot.bounce_mm, air, struck))
	if next == null or speed <= 0:
		return
	var road := hollows[c.hollow].road
	var dx := road.x_at(next.dist_um) - road.x_at(c.dist_um)
	var dz := road.z_at(next.dist_um) - road.z_at(c.dist_um)
	var flight := maxi(1, SimMath.ceil_div(SimMath.isqrt(dx * dx + dz * dz) * 1000, speed))
	var hop := SimRecords.SimShot.new()
	hop.id = _new_id()
	hop.tower = shot.tower
	hop.seat = shot.seat
	hop.hollow = shot.hollow
	hop.kind = shot.kind
	hop.target = next.id
	hop.fire_tick = tick
	hop.land_tick = tick + flight
	hop.dmg_c = shot.dmg_c
	hop.slow_pm = shot.slow_pm
	hop.slow_t = shot.slow_t
	hop.pierce_c = shot.pierce_c
	hop.air_bonus_pm = shot.air_bonus_pm
	hop.bounce = shot.bounce + 1
	hop.bounces = shot.bounces - 1
	hop.bounce_mm = shot.bounce_mm
	hop.from_creep = c.id
	hop.struck = struck
	shots.append(hop)
	_emit(
		{
			"type": SimTypes.EV_FIRE,
			"tower": hop.tower,
			"shot": hop.id,
			"target": next.id,
			"kind": hop.kind,
			"flight": flight,
			"land": -1,
			"from": c.id,
			"form": SimContent.tower_form(hop.kind, t.branch if t else -1)
		}
	)


func _land_shots() -> void:
	var i := 0
	while i < shots.size():
		var shot := shots[i]
		if shot.land_tick > tick:
			i += 1
			continue
		shots.remove_at(i)
		if shot.land_dist_um >= 0:
			_burst(shot)
		else:
			_strike(shot)


## A homing shot hits its target if it still lives, then bounces if it can; otherwise it
## is spent.
func _strike(shot: SimRecords.SimShot) -> void:
	var c := creep(shot.target)
	if c == null:
		return
	_hurt(c, shot, shot.dmg_c, false)
	_bounce(shot, c)


## A shell bursts on the road: every ground creep within the splash radius takes the
## damage, falling off to half at the edge.
func _burst(shot: SimRecords.SimShot) -> void:
	var road := hollows[shot.hollow].road
	var x := road.x_at(shot.land_dist_um)
	var z := road.z_at(shot.land_dist_um)
	var r := shot.splash_mm
	_emit(
		{
			"type": SimTypes.EV_EFFECT,
			"what": "splash",
			"shot": shot.id,
			"tower": shot.tower,
			"hollow": shot.hollow,
			"x": x,
			"z": z,
			"r": r
		}
	)
	var hit: Array[SimRecords.SimCreep] = []
	var dist2 := PackedInt64Array()
	for c in creeps:
		if c.hollow != shot.hollow or c.winged:
			continue
		var dx := road.x_at(c.dist_um) - x
		var dz := road.z_at(c.dist_um) - z
		var d2 := dx * dx + dz * dz
		if d2 <= r * r:
			hit.append(c)
			dist2.append(d2)
	for k in hit.size():
		var d := SimMath.isqrt(dist2[k])
		_hurt(hit[k], shot, shot.dmg_c * (2 * r - d) / (2 * r), true)


## Damage by the armour rule (design 3.2), in hundredths: a flier takes the shot's air
## bonus (M6, the Apiary's), then the mark amplifies the hit,
## `raw = hit × (1000 + mark) / 1000`; armour less pierce (Bronze Hand's included) and
## crack takes off a flat amount, but never more than three quarters,
## `dealt = max(raw − armour_left, raw / 4)`. Then the shot's effect (a slow; a pulse's
## stun, or its slow on a flier), Help for the seats whose effects were on the creep or
## whose hum hastens the tower, and a death pays.
func _hurt(c: SimRecords.SimCreep, shot: SimRecords.SimShot, raw_c: int, splash: bool) -> void:
	if not c.alive:
		return
	var helped := SimEffects.helpers(self, c, shot.seat, tower(shot.tower))
	var mark := c.mark_pm if c.mark_until > tick else 0
	var hit := raw_c
	if c.winged and shot.air_bonus_pm > 0:
		hit = hit * (1000 + shot.air_bonus_pm) / 1000
	var raw := hit * (1000 + mark) / 1000
	var crack := c.crack_c
	var armor_left := maxi(0, c.armor_c - shot.pierce_c - crack)
	var dealt := maxi(raw - armor_left, raw / 4)
	if shot.slow_pm > 0:
		apply_slow(c, shot.slow_pm, shot.slow_t, shot.seat, shot.tower)
	if c.winged:
		if shot.air_slow_pm > 0:
			apply_slow(c, shot.air_slow_pm, shot.air_slow_t, shot.seat, shot.tower)
	elif shot.stun_t > 0:
		SimEffects.apply_stun(self, c, shot.stun_t, shot.stun_immune_t, shot.seat, shot.tower)
	c.hp_c -= dealt
	var s := seat(shot.seat)
	if s:
		s.damage_c += dealt
	_emit(
		{
			"type": SimTypes.EV_HIT,
			"creep": c.id,
			"shot": shot.id,
			"tower": shot.tower,
			"seat": shot.seat,
			"kind": shot.kind,
			"dmg": dealt,
			"splash": splash,
			"raw": raw,
			"armor": raw - dealt,
			"bounce": shot.bounce
		}
	)
	SimEffects.credit(self, c, shot.seat, helped, dealt)
	if c.hp_c <= 0:
		_die(c, shot)


## (M7) A creep the Seawall of seat `seat_no` killed: it dies as to a shot of no tower.
func kill(c: SimRecords.SimCreep, seat_no: int) -> void:
	var strike := SimRecords.SimShot.new()
	strike.seat = seat_no
	strike.hollow = c.hollow
	strike.fire_tick = tick
	strike.land_tick = tick
	_die(c, strike)


## A death pays the full bounty to every seat on the team (design 4.1).
func _die(c: SimRecords.SimCreep, shot: SimRecords.SimShot) -> void:
	c.alive = false
	creeps.erase(c)
	_creep_by_id.erase(c.id)
	var h := hollows[c.hollow]
	teams[h.team].kills += 1
	if race:
		teams[h.team].wave_kills += 1
	var t := tower(shot.tower)
	if t:
		t.kills += 1
	var s := seat(shot.seat)
	if s:
		s.kills += 1
	_emit(
		{
			"type": SimTypes.EV_DIE,
			"id": c.id,
			"kind": c.kind,
			"hollow": h.id,
			"tower": shot.tower,
			"seat": shot.seat,
			"bounty": c.bounty
		}
	)
	for payee in team_seats(h.team):
		add_gold(payee, c.bounty, "bounty")


## Stage 8. A race ends as soon as its outcome is certain (_decide_race); any match ends
## at the rules' cap (cap_t ticks of match time, 0 for none), and once every hollow is
## done or fallen.
func _check_end() -> void:
	if over:
		return
	if (race or duel) and race_rule == 0:
		if race:
			_decide_race()
		else:
			SimUndertow.decide(self)
		if race_rule != 0 and not play_on:
			over = true
			return
	var cap := int(rules.get("cap_t", 0))
	if cap > 0 and tick + 1 >= cap:
		over = true
		return
	for h in hollows:
		if h.phase != SimTypes.PHASE_DONE and h.phase != SimTypes.PHASE_FALLEN:
			return
	over = true


## The race's win order (design 1.3), at the end of a tick, for two teams:
##   both cleared: the lower race time wins, equal ticks are a draw; one cleared: it wins
##     once no time the other could still make beats or equals its own (the other clears
##     on a later tick, and its lost lives only add);
##   a Holdfast fell on wave W: the other team wins once it has cleared W; both fell: the
##     later wave, then more of that wave's creeps killed, then a draw;
##   at the cap (the tick the match reaches cap_t): more waves cleared, then more lives,
##     then the lower race time where both have one, else a draw.
## Decides at most once: race_rule and race_outcomes, and EV_RACE "decided".
func _decide_race() -> void:
	if teams.size() != 2:
		return
	var a := teams[0]
	var b := teams[1]
	var fell_a := hollows[a.hollows[0]].phase == SimTypes.PHASE_FALLEN
	var fell_b := hollows[b.hollows[0]].phase == SimTypes.PHASE_FALLEN
	var done_a := hollows[a.hollows[0]].phase == SimTypes.PHASE_DONE
	var done_b := hollows[b.hollows[0]].phase == SimTypes.PHASE_DONE
	var winner := -2  # -2 open, -1 a draw, else the winning team
	var rule := ""
	if fell_a and fell_b:
		rule = "fell"
		winner = _better(a.fell_wave, b.fell_wave)
		if winner == -1:
			winner = _better(a.fell_kills, b.fell_kills)
	elif fell_a or fell_b:
		var fallen := 0 if fell_a else 1
		if cleared_waves(1 - fallen) >= teams[fallen].fell_wave:
			winner = 1 - fallen
			rule = "fell"
	elif done_a and done_b:
		rule = "time"
		winner = _better(race_time(1), race_time(0))
	elif done_a or done_b:
		var first := 0 if done_a else 1
		if race_time(first) < tick + 1 + race_penalty_t(1 - first):
			winner = first
			rule = "time"
	var cap := int(rules.get("cap_t", 0))
	if winner == -2 and cap > 0 and tick + 1 >= cap:
		rule = "cap"
		winner = _better(cleared_waves(0), cleared_waves(1))
		if winner == -1:
			winner = _better(a.lives, b.lives)
		if winner == -1 and race_time(0) >= 0 and race_time(1) >= 0:
			winner = _better(race_time(1), race_time(0))
	if winner == -2:
		return
	if winner == -1:
		rule = "draw"
	race_rule = SimTypes.RACE_RULES.find(rule)
	race_outcomes = PackedInt32Array()
	for t in teams:
		if winner == -1:
			race_outcomes.append(SimTypes.OUTCOME_DRAW)
		else:
			race_outcomes.append(SimTypes.OUTCOME_WON if t.id == winner else SimTypes.OUTCOME_LOST)
	var shown := maxi(winner, 0)
	race_event("decided", winner, cleared_waves(shown), {"outcomes": Array(race_outcomes), "rule": rule})


## 0 when team 0's number is the larger, 1 when team 1's is, -1 when they are equal.
static func _better(n0: int, n1: int) -> int:
	if n0 == n1:
		return -1
	return 0 if n0 > n1 else 1


## (M6) An EV_RACE: "cleared", "fell" or "decided" for `team` (-1: a draw), the wave, the
## team's race time (-1 while it has none) and any `more` fields.
func race_event(what: String, team: int, wave: int, more := {}) -> void:
	var event := {
		"type": SimTypes.EV_RACE, "what": what, "team": team, "wave": wave,
		"race_t": race_time(team)
	}
	event.merge(more)
	_emit(event)


func _new_id() -> int:
	var id := next_id
	next_id += 1
	return id


func _emit(event: Dictionary) -> void:
	if not events_on:
		return
	event["tick"] = tick
	_events.append(event)


## Rebuilds the id lookups and each hollow's occupied cells after SimCodec filled the records.
func reindex() -> void:
	_tower_by_id.clear()
	_creep_by_id.clear()
	for h in hollows:
		h.occupied.fill(0)
	for t in towers:
		_tower_by_id[t.id] = t
		resolve_tower(t)
		var h := hollows[t.hollow]
		h.occupied[t.z * h.road.width + t.x] = t.id
	for c in creeps:
		_creep_by_id[c.id] = c
	_list_posts()
	_cracks_out = true
