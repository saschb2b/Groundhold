## A stage for the pure simulation (test level 0 in design 7.1): no views, no network.
## One LocalSequencer and N clients, each its own SimMatch fed the same turns, stepped
## thousands of ticks inside one call. Scenarios drive it with evals:
##   {"scene": "res://tests/sim/sim_harness.tscn", ...}
##   {"eval": "scene.start({'seats': 2, 'clients': 2})"}
##   {"eval": "scene.cmd(1, 'BUILD', 0, 8, 3)"}, {"eval": "scene.run_ticks(600)"}
##   {"assert": "scene.hashes_agree()"}
extends Node

## SimMatch's working memory for stage 5 (SimMatch.by_distance, the Chime Posts it lists),
## rebuilt every tick or with the towers and never state: record_differences leaves it out.
const MATCH_CACHES := [
	"order_idx", "order_dist", "_order_built", "_looking", "walks", "crack_posts", "_cracks_out"
]
## (M7) The duel styles that cork on the caretaker's budget (duel_out), and like the
## caretaker hold their plan while their window waits on the rival's wave.
const CARETAKER_BUDGET_STYLES := ["balanced", "counter_cork", "random"]

var seq: LocalSequencer
var clients: Array[SimMatch] = []
var config := {}
var seat_list := []
## Per client: every event it emitted, oldest first.
var events: Array = []
## Per client: tick -> state hash (hex) at every HASH_EVERY tick.
var hashes: Array = []
## Client 1's leaks: one [wave, creep kind, toll, hollow] per creep that reached a Holdfast.
var leaks: Array = []
## Client 1's bosses by creep id: kind, wave, health, damage taken (whole points) and how
## it ended, for a balance pass to read.
var bosses := {}
## Client 1's waves: how many seconds each took from its horn to its clear.
var wave_seconds: Array = []
## Per client: lockstep ticks it still sits out (stall()).
var stalled := PackedInt32Array()
## Per client number: the tick its race was decided at (EV_RACE "decided").
var _decided_at := {}
## Client 1's creeps' health as they spawned, by id (creep_report).
var spawned_hp := {}
## (M7) Client 1's duel by seat: how many corks, uncorks, fizzles, breaches and Seawalls
## each made, counted with events off too (duel_summary).
var duel_counts := {}
## (M7) The packs each seat uncorked on client 1, in order: {seat: [CHECK_IDS id, ...]}.
var duel_picks := {}
## (M8, the sends' pass) Client 1's uncorked packs, in order, each {"seat", "tier",
## "window", "pack" (a CHECK_IDS id), "creeps", "leaked" (its creeps that reached the
## rival's Holdfast), "lives" (their tolls)}, counted with events off too (sends_table);
## the bottles' tiers and windows by id from their EV_CORK, each sent creep's row by id, and
## each seat's rows whose creeps are still to come.
var sends: Array = []
var _send_bottles := {}
var _send_creeps := {}
var _send_waiting := {}
## (M8) Client 1's stacked horns, in order: [hollow, the wave called, tick, each seat's pay,
## the stake (lives on the road)] each (EV_WAVE stacked).
var stack_calls: Array = []
## (M8) Client 1's creeps' waves by id, from their spawns, so a leak counts for its own
## wave once waves stack; and each wave's slot in wave_seconds by [hollow 0's] wave.
var _creep_waves := {}
var _wave_slots := {}
## (M7) The salts the duel's play styles corked with, per seat: [window, pack, salt_hi,
## salt_lo, commit_hi, commit_lo] each, until its UNCORK goes out; and their own random
## streams (the random corker's picks and every salt), seeded by the match seed and seat.
var _salts := {}
var _style_rngs := {}


## {"mode": "classic", "seats": 1, "seed": 1, "clients": 1, "caretakers": [seat numbers],
##  "builders": [Builder id per seat, "lamplighter" where it runs out],
##  "teams": [team per seat, 0 where it runs out] (a race: seats of team t on hollow t;
##  "tide_race" with no "teams" puts the first half of the seats on team 0, the rest on 1),
##  "plans": {Builder id: [plan entries as in data/plans]} to hand every client's
##  caretaker (and plan_step) other plans, "never_patch": {Builder id: [check ids]} for
##  its own plan with the forks that patch those checks turned to the other branch,
##  "events": false to keep no events (long balance runs; leaks are still counted),
##  "play_on": true to let a decided race play on until both hollows are done or fallen
##  (SimMatch.play_on), (M8) "difficulty": the level asked for ("normal", "hard",
##  "very_hard"; SimContent.rules(mode, difficulty), so a mode without levels plays Normal),
##  "stacks": {Builder id: [waves]} to hand every client other stack lists than the plans',
##  "rules": {key: value} laid over the rules (rules())}
func start(cfg := {}) -> SimMatch:
	config = cfg
	var seat_count := int(cfg.get("seats", 1))
	var caretakers: Array = cfg.get("caretakers", [])
	var builders: Array = cfg.get("builders", [])
	var teams: Array = cfg.get("teams", [])
	var two_teams := int(SimContent.rules(str(cfg.get("mode", "classic")))["teams"]) == 2
	seat_list = []
	for i in seat_count:
		var builder := str(builders[i]) if i < builders.size() else "lamplighter"
		var team := 0
		if i < teams.size():
			team = int(teams[i])
		elif two_teams:
			team = 0 if i * 2 < seat_count else 1
		seat_list.append({"team": team, "builder": builder, "caretaker": caretakers.has(i + 1)})
	seq = LocalSequencer.new(seat_count)
	clients.clear()
	events.clear()
	hashes.clear()
	leaks.clear()
	bosses.clear()
	wave_seconds.clear()
	stalled.clear()
	_decided_at.clear()
	spawned_hp.clear()
	duel_counts.clear()
	duel_picks.clear()
	sends.clear()
	_send_bottles.clear()
	_send_creeps.clear()
	_send_waiting.clear()
	_salts.clear()
	_style_rngs.clear()
	stack_calls.clear()
	_creep_waves.clear()
	_wave_slots.clear()
	for k in int(cfg.get("clients", 1)):
		_join(_new_match())
	return clients[0]


func client(k := 1) -> SimMatch:
	return clients[k - 1]


## Queues a command as `seat` for the next turn, by name ("BUILD", "SELL", ...).
func cmd(seat: int, name: String, a := 0, b := 0, c := 0) -> int:
	return seq.submit_as(seat, SimTypes.command_type(name), a, b, c)


## Queues a system command ("AWAY", "BACK", "LEFT", "TIMEOUT").
func system(name: String, a := 0) -> void:
	seq.system(SimTypes.command_type(name), a)


## Steps every client `n` ticks, in lockstep (a stalled client sits them out). Returns
## the first client's tick.
func run_ticks(n: int) -> int:
	for i in n:
		for k in clients.size():
			if stalled[k] > 0:
				stalled[k] -= 1
				continue
			_step(k)
	return clients[0].tick


## Client k (2 or more; client 1 keeps the clock) sits out the next `ticks` lockstep
## ticks, as a game whose loop stopped (a hidden tab, a long hitch): the turns it misses
## wait in the log, as they wait in a socket's buffer. catch_up(k) brings it back.
func stall(k: int, ticks: int) -> void:
	stalled[k - 1] = maxi(0, ticks)


## How many ticks client k is behind client 1.
func behind(k: int) -> int:
	return clients[0].tick - clients[k - 1].tick


## Runs client k alone, `per_call` ticks at a time (Playout catches up 8 ticks a frame;
## at least 1), until it stands at client 1's tick. Returns how many calls that took, or
## -1 with an error when a call ran no tick (its turn is not in the log): a wait that
## cannot end stops at once instead of spinning until the run's timeout.
func catch_up(k: int, per_call := 8) -> int:
	stalled[k - 1] = 0
	var calls := 0
	while clients[k - 1].tick < clients[0].tick:
		var was := clients[k - 1].tick
		var n := mini(maxi(1, per_call), clients[0].tick - was)
		for i in n:
			_step(k - 1)
		calls += 1
		if clients[k - 1].tick == was:
			push_error("catch_up: client %d has no turn for tick %d" % [k, was])
			return -1
	return calls


## Seat `seat`'s state on client k by name: "present", "away", "returning", "caretaker"
## or "left".
func seat_state(seat: int, k := 1) -> String:
	return SimTypes.seat_state_name(clients[k - 1].seat(seat).state)


## Every move of seat `seat`'s state on client k (its SEAT events) as [tick, state name].
func seat_moves(seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_where("SEAT", {"seat": seat}, k):
		out.append([int(e["tick"]), SimTypes.seat_state_name(int(e["state"]))])
	return out


## The entries of a list from tick `tick` on: events (events_of, events_where) or
## [tick, ...] rows (refusal_ticks, seat_moves).
func since(list: Array, tick: int) -> Array:
	var out := []
	for e: Variant in list:
		var at := int((e as Dictionary)["tick"]) if e is Dictionary else int((e as Array)[0])
		if at >= tick:
			out.append(e)
	return out


## The refusals seat `seat` received on client k as [tick, reason name], oldest first.
func refusal_ticks(seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_where("REJECTED", {"seat": seat}, k):
		out.append([int(e["tick"]), SimTypes.refusal_name(int(e["reason"]))])
	return out


## Shots fired so far by the towers seat `seat` has standing on client k.
func shots_by(seat: int, k := 1) -> int:
	var total := 0
	for t: SimRecords.SimTower in clients[k - 1].towers:
		if t.owner == seat:
			total += t.shots
	return total


## The seat whose tower stands on cell (x, z) of client k, 0 for none (an Expression
## evaluates both sides of `or`, so a scenario cannot write tower_at(x, z).owner safely).
func owner_at(x: int, z: int, k := 1) -> int:
	var t := tower_at(x, z, k)
	return t.owner if t else 0


## How many creeps on client k's road are marked and how many slowed right now.
func effects_on_road(k := 1) -> Array:
	var sim := clients[k - 1]
	var marked := 0
	var slowed := 0
	for c: SimRecords.SimCreep in sim.creeps:
		if c.mark_pm > 0 and c.mark_until > sim.tick:
			marked += 1
		if c.slow_pm > 0 and c.slow_until > sim.tick:
			slowed += 1
	return [marked, slowed]


## Seat `seat`'s towers on client k as "x,z form", in id order.
func towers_of(seat: int, k := 1) -> Array:
	var out := []
	for t: SimRecords.SimTower in clients[k - 1].towers:
		if t.owner == seat:
			out.append("%d,%d %s" % [t.x, t.z, SimContent.tower_form(t.kind, t.branch)])
	return out


## A cell no tower can stand on (the road's first cell, at the Welling), for orders that
## must be refused whoever reads them: CARETAKEN while the caretaker holds the seat,
## CANNOT_BUILD_THERE once it is the player's.
func road_cell(k := 1) -> Array:
	var road := clients[k - 1].hollows[0].road
	return [road.path_x[0], road.path_z[0]]


## For every tower on client k as the state stands now, the creep stage 5's walk along
## the road picks (SimTargeting.furthest with SimMatch.by_distance) against a scan of
## every creep, winged only and not; returns where they differ. Adds the count of
## comparisons to config["walk_checks"].
func targeting_mismatches(k := 1) -> Array:
	var sim := clients[k - 1]
	var out := []
	var walked := []
	sim.open_look()  # as stage 5 does: the walk along the road
	for t: SimRecords.SimTower in sim.towers:
		walked.append([SimTargeting.furthest(sim, t, false), SimTargeting.furthest(sim, t, true)])
	sim.close_look()  # any other time: the scan of every creep
	for i in sim.towers.size():
		var t := sim.towers[i]
		for w in 2:
			var scanned := SimTargeting.furthest(sim, t, w == 1)
			config["walk_checks"] = int(config.get("walk_checks", 0)) + 1
			if walked[i][w] != scanned:
				out.append("tick %d tower %d (%s) winged_only %s: walk %d, scan %d" % [sim.tick, t.id, t.kind, w == 1, walked[i][w], scanned])
	return out


## Steps every client `n` ticks, checking targeting_mismatches on client k before each.
## Returns the first mismatches found, or [].
func run_checking_targets(n: int, k := 1) -> Array:
	for i in n:
		var bad := targeting_mismatches(k)
		if not bad.is_empty():
			return bad
		run_ticks(1)
	return []


func run_turns(n: int) -> int:
	return run_ticks(n * SimTypes.TURN_TICKS)


func run_to(tick: int) -> int:
	return run_ticks(maxi(0, tick - clients[0].tick))


## Steps until the first client's match is over or `limit` ticks have run.
func run_until_over(limit := 100000) -> int:
	var ran := 0
	while not clients[0].over and ran < limit:
		run_ticks(1)
		ran += 1
	return clients[0].tick


## Every client reported the same hash at every hash tick they share.
func hashes_agree() -> bool:
	for k in range(1, hashes.size()):
		for tick: int in hashes[k]:
			if hashes[0].has(tick) and hashes[0][tick] != hashes[k][tick]:
				return false
	return true


func hash_at(tick: int, k := 1) -> String:
	return str(hashes[k - 1].get(tick, ""))


## Events of client k with the given type name ("REJECTED", "DIE", ...).
func events_of(type_name: String, k := 1) -> Array:
	var type := SimTypes.event_type(type_name)
	return events[k - 1].filter(func(e: Dictionary) -> bool: return e["type"] == type)


## The gold paid to every seat together for `why` ("ready", "bounty", "clear", ...) on
## client k.
func gold_paid(why: String, k := 1) -> int:
	var total := 0
	for e: Dictionary in events_of("GOLD", k):
		if str(e.get("why", "")) == why:
			total += int(e["change"])
	return total


## The ticks at which `seat`'s events of `type_name` ("BUILT", "FORKED") came on client k.
func ticks_of(type_name: String, seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_of(type_name, k):
		if int(e.get("seat", 0)) == seat:
			out.append(int(e["tick"]))
	return out


## Names of the refusals a seat received on client k, oldest first.
func refusals(seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_of("REJECTED", k):
		if e["seat"] == seat:
			out.append(SimTypes.refusal_name(e["reason"]))
	return out


func last_refusal(seat: int, k := 1) -> String:
	var all := refusals(seat, k)
	return str(all[-1]) if not all.is_empty() else ""


func gold(seat: int, k := 1) -> int:
	return clients[k - 1].seat(seat).gold


func tower_at(x: int, z: int, k := 1) -> SimRecords.SimTower:
	return clients[k - 1].tower_at(0, x, z)


## The tower on cell (x, z) of hollow `hollow` on client k (a race's second hollow), or null.
func tower_on(hollow: int, x: int, z: int, k := 1) -> SimRecords.SimTower:
	return clients[k - 1].tower_at(hollow, x, z)


## A debug write (SimTypes.DBG_*) on every client at once, logged like the game's
## scenario setters so a replay of record() reproduces it. Every client must stand at
## the same tick (none stalled behind), or the write would land at different ticks.
func debug(op: int, a: int, b := 0, c := 0) -> void:
	for k in range(1, clients.size()):
		if clients[k].tick != clients[0].tick:
			push_error("debug write while client %d is %d ticks behind" % [k + 1, behind(k + 1)])
	seq.record_debug(clients[0].tick, op, a, b, c)
	for sim in clients:
		sim.debug(op, a, b, c)


## Puts a creep of `kind` (a CREEP_IDS id) on the road of every client, `dist_um` along
## it, with this wave's health, on hollow `hollow` (a race's second: 1). Returns its id.
func spawn(kind: String, dist_um := 0, hollow := 0) -> int:
	debug(SimTypes.DBG_SPAWN, hollow, SimContent.CREEP_IDS.find(kind))
	var id := clients[0].next_id - 1
	if dist_um > 0:
		debug(SimTypes.DBG_CREEP_DIST, id, dist_um)
	return id


## Holds a creep where it is (speed 0) on every client, or sets another speed.
func hold(id: int, speed_um_t := 0) -> void:
	debug(SimTypes.DBG_CREEP_SPEED, id, speed_um_t)


func creep(id: int, k := 1) -> SimRecords.SimCreep:
	return clients[k - 1].creep(id)


## The kind of every creep client k has spawned, by id (from its SPAWN events).
func creep_kinds_by_id(k := 1) -> Dictionary:
	var out := {}
	for e: Dictionary in events_of("SPAWN", k):
		out[int(e["id"])] = str(e["kind"])
	return out


## Client k's HIT events from towers of base `tower_kind` ("" for any) on creeps of
## `creep_kind` ("" for any).
func hits(tower_kind := "", creep_kind := "", k := 1) -> Array:
	var kinds := creep_kinds_by_id(k)
	var out := []
	for e: Dictionary in events_of("HIT", k):
		if tower_kind != "" and str(e["kind"]) != tower_kind:
			continue
		if creep_kind != "" and str(kinds.get(int(e["creep"]), "")) != creep_kind:
			continue
		out.append(e)
	return out


## Those hits as rows [tick, creep, tower kind, dealt, tower], oldest first.
func hit_rows(tower_kind := "", creep_kind := "", k := 1) -> Array:
	var out := []
	for e: Dictionary in hits(tower_kind, creep_kind, k):
		out.append([int(e["tick"]), int(e["creep"]), str(e["kind"]), int(e["dmg"]), int(e["tower"])])
	return out


## For a balance pass: per creep of `creep_kind` client k spawned, "id: dealt/health by
## tower kind (hits), died or leaked", from its events.
func creep_report(creep_kind: String, k := 1) -> Array:
	var health := {}
	for e: Dictionary in events_where("SPAWN", {"kind": creep_kind}, k):
		health[int(e["id"])] = int(spawned_hp.get(int(e["id"]), 0))
	var by := {}
	for e: Dictionary in hits("", creep_kind, k):
		var row: Dictionary = by.get_or_add(int(e["creep"]), {})
		var key := str(e["kind"])
		var cell: Array = row.get_or_add(key, [0, 0])
		cell[0] += int(e["dmg"])
		cell[1] += 1
	var ended := {}
	for e: Dictionary in events_of("DIE", k):
		ended[int(e["id"])] = "died"
	for e: Dictionary in events_of("LEAK", k):
		ended[int(e["id"])] = "leaked"
	var out := []
	for id: int in health:
		var parts := []
		var row: Dictionary = by.get(id, {})
		for key: String in row:
			parts.append("%s %d (%d)" % [key, int(row[key][0]) / 100, int(row[key][1])])
		out.append("%d: %d hp, %s, %s" % [id, int(health[id]) / 100, ", ".join(parts), ended.get(id, "-")])
	return out


## The distinct [dealt, raw, armour] of those hits, in the order they first came.
func hit_values(tower_kind := "", creep_kind := "", k := 1) -> Array:
	var out := []
	for e: Dictionary in hits(tower_kind, creep_kind, k):
		var v := [int(e["dmg"]), int(e.get("raw", -1)), int(e.get("armor", -1))]
		if not out.has(v):
			out.append(v)
	return out


## Client k's events of `type_name` whose fields include every pair of `fields`.
func events_where(type_name: String, fields: Dictionary, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_of(type_name, k):
		var ok := true
		for key: String in fields:
			if not e.has(key) or e[key] != fields[key]:
				ok = false
				break
		if ok:
			out.append(e)
	return out


## Client k's events of `type_name` whose fields include `where`, each as a row of the
## `fields` listed (a missing one reads as null), oldest first.
func rows(type_name: String, fields: Array, where := {}, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_where(type_name, where, k):
		var row := []
		for f: Variant in fields:
			row.append(e.get(f))
		out.append(row)
	return out


## The refunds `seat`'s sales paid on client k, oldest first.
func refunds(seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_where("SOLD", {"seat": seat}, k):
		out.append(int(e["refund"]))
	return out


## The distinct strengths an effect (SimTypes.EFFECT_*) took on creep `id` (EV_STATUS).
func status_amounts(id: int, effect: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_where("STATUS", {"creep": id, "effect": effect}, k):
		if not out.has(int(e["amount"])):
			out.append(int(e["amount"]))
	return out


## Steps every client `n` ticks, one at a time, and returns how much creep `id` on client
## k was slowed on each, in per mille, read from how far it walked against its speed:
## give it a speed of 1000 micrometres a tick first (hold(id, 1000)). -1 once it is gone.
func slowed_by_tick(id: int, n: int, k := 1) -> Array:
	var out := []
	for i in n:
		var c := creep(id, k)
		var before := c.dist_um if c and c.alive else -1
		run_ticks(1)
		if before < 0 or not c.alive:
			out.append(-1)
		else:
			out.append(c.speed_um_t - (c.dist_um - before) * 1000 / maxi(1, c.speed_um_t))
	return out


## For the `n` ticks from `from_tick`, the slow creep `id` is owed on each by the slowing
## hits on it (client k's HIT events): the strongest whose time has not run out. A hit
## lands after the creep moved, so it slows from the next tick for its tower's slow_t,
## shrunk by a boss's control resistance as the rules say.
func slow_owed(id: int, from_tick: int, n: int, k := 1) -> Array:
	var m := clients[k - 1]
	var c := creep(id, k)
	var out := []
	out.resize(n)
	out.fill(0)
	for e: Dictionary in events_where("HIT", {"creep": id}, k):
		var t := m.tower(int(e["tower"]))
		if t == null or t.slow_pm <= 0:
			continue
		var strength := SimEffects.resisted(m, c, t.slow_pm)
		for tick in range(int(e["tick"]) + 1, int(e["tick"]) + t.slow_t):
			var i := tick - from_tick
			if i >= 0 and i < n:
				out[i] = maxi(int(out[i]), strength)
	return out


## The Help credited to `seat` by its EV_HELP events on client k.
func help_total(seat: int, k := 1) -> int:
	var total := 0
	for e: Dictionary in events_where("HELP", {"seat": seat}, k):
		total += int(e["dmg"])
	return total


## How many of `seat`'s hits on client k landed harder than their tower's damage: hits
## on a marked creep (towers still standing).
func amplified_hits(seat: int, k := 1) -> int:
	var count := 0
	for e: Dictionary in events_where("HIT", {"seat": seat}, k):
		var t := clients[k - 1].tower(int(e["tower"]))
		if t and int(e["raw"]) > t.dmg_c:
			count += 1
	return count


## A wave list as people read it: per wave, "creep x count" per group.
func wave_summary(k := 1) -> Array:
	var out := []
	for wave: Array in clients[k - 1].waves:
		var groups := []
		for g: Dictionary in wave:
			groups.append("%s x%d" % [g["creep"], g["count"]])
		out.append(", ".join(groups))
	return out


## A road distance (micrometres) tower `t` reaches that a tower on its cell with range
## `smaller_mm` would not, or -1: where Keen Sight makes the difference.
func reach_beyond(t: SimRecords.SimTower, smaller_mm: int, k := 1) -> int:
	var road := clients[k - 1].hollows[t.hollow].road
	var small := road.intervals(SimRoad.centre_mm(t.x), SimRoad.centre_mm(t.z), smaller_mm)
	for dist in range(0, road.length_um, 10000):
		if SimRoad.covers(t.intervals, dist) and not SimRoad.covers(small, dist):
			return dist
	return -1


## The forms (SimContent.tower_form) of the towers standing on client k, in id order;
## only `seat`'s when it is above 0.
func forms(seat := 0, k := 1) -> Array:
	var out := []
	for t: SimRecords.SimTower in clients[k - 1].towers:
		if seat == 0 or t.owner == seat:
			out.append(SimContent.tower_form(t.kind, t.branch))
	return out


## The kinds of the creeps on client k's road, each once, in CREEP_IDS order.
func creep_kinds(k := 1) -> Array:
	var out := []
	for kind: String in SimContent.CREEP_IDS:
		for c: SimRecords.SimCreep in clients[k - 1].creeps:
			if c.kind == kind:
				out.append(kind)
				break
	return out


## Bounces in the air on client k: strikes flying on from a creep they struck.
func bouncing(k := 1) -> int:
	var count := 0
	for shot: SimRecords.SimShot in clients[k - 1].shots:
		if shot.bounce > 0:
			count += 1
	return count


## Cannon shells in the air on client k: shots bursting at a road distance.
func shells_in_flight(k := 1) -> int:
	var count := 0
	for shot: SimRecords.SimShot in clients[k - 1].shots:
		if shot.land_dist_um >= 0:
			count += 1
	return count


## Every field in which client b's match differs from client a's: the match's own numbers
## and every script variable of every team, hollow, seat, tower, creep and shot, one by
## one. Comparing serialize() bytes cannot show a field the codec leaves out on both sides;
## this does. Objects (the road, the RNG) are compared by their own fields where they
## have them, never by reference.
func record_differences(a := 1, b := 2) -> Array:
	var out := []
	var x := clients[a - 1]
	var y := clients[b - 1]
	_compare_fields("match", x, y, out)
	_compare_fields("rng", x.rng, y.rng, out)
	for list_name: String in ["teams", "hollows", "seats", "towers", "creeps", "shots", "bottle_list"]:
		var xs: Array = x.get(list_name)
		var ys: Array = y.get(list_name)
		if xs.size() != ys.size():
			out.append("%s: %d against %d" % [list_name, xs.size(), ys.size()])
			continue
		for i in xs.size():
			_compare_fields("%s[%d]" % [list_name, i], xs[i], ys[i], out)
	return out


func _compare_fields(where: String, x: Object, y: Object, out: Array) -> void:
	for p: Dictionary in x.get_property_list():
		if not (int(p["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE):
			continue
		var name: String = p["name"]
		if x is SimMatch and MATCH_CACHES.has(name):
			continue  # stage 5's working memory, rebuilt each tick; not state
		var vx: Variant = x.get(name)
		var vy: Variant = y.get(name)
		# (records in lists are compared one by one above; objects and maps of them
		# are links between records, not state of their own)
		if vx is Object or vx is Dictionary or (vx is Array and not (vx as Array).is_empty() and (vx as Array)[0] is Object):
			continue
		if vx != vy:
			out.append("%s.%s: %s against %s" % [where, name, str(vx).left(40), str(vy).left(40)])


## Client k's checkpoint now.
func checkpoint(k := 1) -> PackedByteArray:
	return clients[k - 1].serialize()


## Adds a client loaded from a checkpoint; it takes the following turns from the log. It
## plays the rules every client plays (rules()) with cfg's switches and plans (_configured).
func join_from(bytes: PackedByteArray) -> SimMatch:
	var sim := SimMatch.deserialize(bytes, rules())
	if sim == null:
		push_error("join_from: the checkpoint does not load under these rules")
		return null
	_join(_configured(sim))
	return sim


## (M8) The rules every client plays: the mode's at the level asked for, with cfg "rules"
## ({key: value}, a balance pass's switch: a level's or a preset's numbers tried before they
## are written into content.gd) laid over them.
func rules() -> Dictionary:
	var out := SimContent.rules(str(config.get("mode", "classic")), str(config.get("difficulty", "normal")))
	out.merge(config.get("rules", {}), true)
	return out


## The turn log so far, as LocalSequencer.replay takes it, with (M8) the level asked for.
## A replay builds the mode's rules from the record (LocalSequencer.replay, track C's: at
## the record's "difficulty" once C's §3 change reads it, Normal until then), so
## replay_matches holds only for a match cfg played at Normal without "rules", "stacks",
## "plans" or "never_patch", which are the harness's alone and no record carries.
func record() -> Dictionary:
	var out := seq.log_for(clients[0], seat_list)
	out["difficulty"] = str(config.get("difficulty", "normal"))
	return out


## Replays the log into a fresh match to `to_tick`; true when every hash it passes
## equals the one client 1 recorded.
func replay_matches(to_tick: int) -> bool:
	var replayed := {}
	LocalSequencer.replay(record(), to_tick, replayed)
	if replayed.is_empty():
		return false
	for tick: int in replayed:
		if hashes[0].get(tick, "") != replayed[tick]:
			return false
	return true


## Works down the seat's Builder's plan for `seat` as commands, like tests/bot.gd does
## through the game, deciding each step as the caretaker would (Caretaker.decide: the
## alternative cells, the patching forks the team lacks): queues every step it can pay
## for now. A fork whose tower is still on its way waits for the next call. Returns the
## steps queued. `reserved` is gold already promised this turn (a duel's corks).
func plan_step(seat: int, cursor_name := "plan", reserved := 0) -> int:
	var sim := clients[0]
	var s := sim.seat(seat)
	var steps: Array = sim.plans[s.builder]
	var key := "%s_%d" % [cursor_name, seat]
	var cursor := int(config.get(key, 0))
	var spent := reserved
	var queued := 0
	var claimed := PackedInt32Array()
	var width := sim.hollows[s.hollow].road.width
	config["held_%d" % seat] = false
	while cursor < steps.size():
		var step: PackedInt32Array = steps[cursor]
		if step[0] == 1 and _claims_any(sim, step, claimed):
			config["held_%d" % seat] = true  # (M8: a stacking seat waits for it too)
			break  # its build has not landed yet
		var d := Caretaker.decide(sim, s, step, s.gold - spent, claimed)
		if d[0] == Caretaker.WAIT:
			break
		if d[0] == Caretaker.BUILD:
			cmd(seat, "BUILD", d[1], d[2], d[3])
			claimed.append(d[3] * width + d[2])
			spent += int(SimContent.TOWERS[SimContent.kit_tower(s.builder, d[1])]["cost"])
			queued += 1
		elif d[0] == Caretaker.FORK:
			cmd(seat, "FORK", d[1], d[2])
			spent += int(SimContent.TOWERS[sim.tower(d[1]).kind]["fork_cost"])
			queued += 1
		cursor += 1
	config[key] = cursor
	return queued


## (M8) Seat `seat`, played by command, calls the next wave during this one when `how`
## says so ("plan": Caretaker.wants_stack over its plan cursor, unless a fork waits for its
## build to land; "all": whenever the hollow can take another wave): queues READY 1.
## Returns whether it did.
func stack_call(seat: int, how: String) -> bool:
	var sim := clients[0]
	var s := sim.seat(seat)
	if s == null or s.ready or s.state != SimTypes.SEAT_PRESENT:
		return false
	var h := sim.hollows[s.hollow]
	if h.phase != SimTypes.PHASE_WAVE or not sim.can_stack(h.id):
		return false
	if how == "plan":
		if bool(config.get("held_%d" % seat, false)):
			return false
		var steps: Array = sim.plans[s.builder]
		if not Caretaker.wants_stack(sim, s, steps, int(config.get("plan_%d" % seat, 0))):
			return false
	elif how != "all":
		return false
	cmd(seat, "READY", 1)
	return true


func _claims_any(sim: SimMatch, step: PackedInt32Array, claimed: PackedInt32Array) -> bool:
	for cell in Caretaker.cells(sim.hollows[0], step):
		if claimed.has(cell):
			return true
	return false


## Plays client 1's match to its end: the seats in `by_command` work down their plans
## through commands every `every` ticks (plan_step), caretaken seats play themselves,
## the rest stand idle; the seats in `ready_at_once` (by command too) press Ready in every
## build window as soon as their orders are out. (M8) The seats in `stacking` ({seat:
## how}, by command too) press Ready during a wave as well: "plan" as the caretaker would
## (Caretaker.wants_stack: its plan's stack list, at Normal, once the steps it can pay for
## are out and none waits for a build to land), "all" in every wave the hollow can take
## another (SimMatch.can_stack), at any level. Returns the final tick. Stops at `limit`,
## and with an error when a round ran no tick (the sequencer paused): the wait would
## never end.
func play_out(
	by_command := [], every := 30, limit := 120000, ready_at_once := [], stacking := {}
) -> int:
	while not clients[0].over and clients[0].tick < limit:
		var was := clients[0].tick
		for seat: int in by_command:
			plan_step(int(seat))
		for seat: int in ready_at_once:
			var s := clients[0].seat(int(seat))
			if clients[0].hollows[s.hollow].phase == SimTypes.PHASE_PREP and not s.ready:
				cmd(int(seat), "READY", 1)
		for seat: Variant in stacking:
			stack_call(int(seat), str(stacking[seat]))
		run_ticks(maxi(1, every))
		if clients[0].tick == was:
			push_error("play_out: no turn for tick %d (the sequencer is paused)" % was)
			break
	return clients[0].tick


## (M7) Plays client 1's duel to its end with the seats in `styles` ({seat: style}) played
## by command, every `every` ticks, in a play style of the duel's balance gates:
##   "turtle"        works down its plan and never corks
##   "balanced"      the caretaker's policy (Caretaker._duel): in the window both hollows
##                   share, while it has corks left, the cheapest tier it can pay for while
##                   its corks stay within CORK_SHARE_PM of its worth (Caretaker.cork_tier),
##                   the pack the rival's defence has shown it should send
##                   (SimUndertow.pick_pack)
##   "counter_cork"  the same: the caretaker's pick of the rival's weakest check, named
##                   for it in the gate against "random"
##   "reckless"      corks the most it can every window, before it builds, the same pack
##   "random"        the caretaker's budget, an offered pack drawn at random
## The three on the caretaker's budget (CARETAKER_BUDGET_STYLES) hold their plan while their
## hollow stands in a window the rival's wave keeps shut, as the caretaker does
## (Caretaker.holds_plan), so their corks come before their builds; the reckless one builds
## meanwhile and corks what is left when the window opens (holding too, it out-corks the
## turtle's defence: duel_turtle_beats_reckless and duel_seawall_saves 2 of 5). Each corks
## with a salt of its own stream, uncorks every bottle from uncork_after_t after
## the horn and raises its Seawall as the caretaker would (Caretaker.wants_seawall), unless
## its seat is in options "no_seawall"; options "packs" ({seat: CHECK_IDS id}) has a seat
## cork that pack wherever its window offers it (_duel_cork). Nobody presses Ready: the
## windows run out. Other
## seats play themselves if caretaken. Returns the final tick; stops at `limit`, and with an
## error when a round ran no tick.
func duel_out(styles: Dictionary, options := {}, every := 30, limit := 150000) -> int:
	while not clients[0].over and clients[0].tick < limit:
		var was := clients[0].tick
		for seat: int in styles:
			_duel_play(int(seat), str(styles[seat]), options)
		run_ticks(maxi(1, every))
		if clients[0].tick == was:
			push_error("duel_out: no turn for tick %d (the sequencer is paused)" % was)
			break
	return clients[0].tick


## (M7) The duel of `cfg` (start()'s, with mode undertow) played by duel_out(styles,
## options) once for each of `seeds`, with cfg "builders_by_seed" (one Builder list per
## seed, in step with `seeds`) in place of its "builders" where it is given: {"wins": [team
## 0's, team 1's], "draws": n, "mirrors": matches whose two seats ended the same,
## "distinct": how many of the matches differ (by their final state hash: the match's
## SimRng feeds only the Drift, so two seeds may play one match), "leading_picks": {seat:
## how many different packs led its uncorkings across the matches (the pack it uncorked
## most in each, ties to the earlier check)}, "matches": [duel_summary() of each, with its
## seed, Builders, hash and every seat's picks], "lines": [duel_line() of each]}.
func duel_series(cfg: Dictionary, styles: Dictionary, seeds: Array, options := {}) -> Dictionary:
	var wins := [0, 0]
	var draws := 0
	var matches := []
	var lines := []
	var mirrors := 0
	var finals := []
	var leading := {}
	var by_seed: Array = cfg.get("builders_by_seed", [])
	for i in seeds.size():
		var s: Variant = seeds[i]
		var one := cfg.duplicate(true)
		one["seed"] = int(s)
		if i < by_seed.size():
			one["builders"] = by_seed[i]
		start(one)
		duel_out(styles, options)
		var out := clients[0].outcomes()
		if out.size() == 2 and int(out[0]) == SimTypes.OUTCOME_WON:
			wins[0] += 1
		elif out.size() == 2 and int(out[1]) == SimTypes.OUTCOME_WON:
			wins[1] += 1
		else:
			draws += 1
		var row := duel_summary()
		row["seed"] = int(s)
		row["builders"] = one.get("builders", [])
		row["hash"] = clients[0].state_hash_hex()
		row["picks"] = duel_picks.duplicate(true)
		matches.append(row)
		lines.append("seed %d %s: %s" % [int(s), "/".join(PackedStringArray(row["builders"])), duel_line()])
		if _mirrored():
			mirrors += 1
		if not finals.has(row["hash"]):
			finals.append(row["hash"])
		for seat: int in duel_picks:
			var top := _leading_pick(duel_picks[seat])
			var kinds: Array = leading.get_or_add(seat, [])
			if top != "" and not kinds.has(top):
				kinds.append(top)
	var leading_count := {}
	for seat: int in leading:
		leading_count[seat] = (leading[seat] as Array).size()
	return {
		"wins": wins, "draws": draws, "mirrors": mirrors, "distinct": finals.size(),
		"leading_picks": leading_count, "matches": matches, "lines": lines,
	}


## (M8, the sends' pass) How often an uncorked pack breaches, one of its creeps taking a
## life, in mirrors of Builders: for each style of `styles` ("caretaker": both seats
## caretaken from tick 0; else both played by command in that duel_out style, the seats'
## options in `options`) and each Builder of `builders`, a duel of that Builder on both
## seats (cfg's keys laid over the undertow start) under each of `seeds`. Counts are
## [packs uncorked, packs that breached] and shares per mille of the packs: {"total",
## "total_pm", "tiers" and "tiers_pm" (I, II, III), "styles" {style: ...}, "mirrors" and
## "mirrors_pm" {"<style> <builder>": ...}, "cells" {"<style> <builder> tier N": [packs,
## breached, creeps, creeps leaked, lives]}, "picks" {"<builder> <pack>": ...}, "windows"
## {window: ...} and "lines" (duel_line() of each duel)}.
func sends_table(styles: Array, builders: Array, seeds: Array, cfg := {}, options := {}) -> Dictionary:
	var total := [0, 0]
	var tiers := [[0, 0], [0, 0], [0, 0]]
	var by_style := {}
	var mirrors := {}
	var cells := {}
	var picks := {}
	var windows := {}
	var lines := []
	for style: String in styles:
		for builder: String in builders:
			for s: Variant in seeds:
				var one := {"mode": "undertow", "seats": 2, "seed": int(s), "builders": [builder, builder], "events": false}
				one.merge(cfg, true)
				if style == "caretaker":
					one["caretakers"] = [1, 2]
				start(one)
				duel_out({} if style == "caretaker" else {1: style, 2: style}, options)
				lines.append("%s %s seed %d: %s" % [style, builder, int(s), duel_line()])
				for row: Dictionary in sends:
					var hit := 1 if int(row["leaked"]) > 0 else 0
					var tier := clampi(int(row["tier"]), 0, 2)
					var pairs: Array = [
						total, tiers[tier], by_style.get_or_add(style, [0, 0]),
						mirrors.get_or_add("%s %s" % [style, builder], [0, 0]),
						picks.get_or_add("%s %s" % [builder, row["pack"]], [0, 0]),
						windows.get_or_add(int(row["window"]), [0, 0]),
					]
					for pair: Array in pairs:
						pair[0] += 1
						pair[1] += hit
					var cell: Array = cells.get_or_add("%s %s tier %d" % [style, builder, tier + 1], [0, 0, 0, 0, 0])
					cell[0] += 1
					cell[1] += hit
					cell[2] += int(row["creeps"])
					cell[3] += int(row["leaked"])
					cell[4] += int(row["lives"])
	var mirrors_pm := {}
	for key: String in mirrors:
		mirrors_pm[key] = share_pm(mirrors[key])
	return {
		"total": total, "total_pm": share_pm(total), "tiers": tiers,
		"tiers_pm": tiers.map(func(pair: Array) -> int: return share_pm(pair)),
		"styles": by_style, "mirrors": mirrors, "mirrors_pm": mirrors_pm, "cells": cells,
		"picks": picks, "windows": windows, "lines": lines,
	}


## (M8, the packs' matrix) What each pack does to each Builder that defends against it: for
## each defending style of `defenders` ("caretaker": seat 2 caretaken from tick 0; else
## seat 2 played by command in that duel_out style), each Builder of `builders` (on both
## seats, a mirror), each pack of `packs` (CHECK_IDS ids, all four by default) and each of
## `seeds`, a duel in which seat 1 plays the balanced style corking that pack wherever its
## window offers it (duel_out's options "packs"; elsewhere it corks the caretaker's pick,
## which is not counted). Only seat 1's uncorkings of the pack count, against seat 2's
## defence. Each count is [packs uncorked, packs that breached, creeps, creeps leaked,
## lives]: {"cells" {"<builder> <pack> tier N": ...}, "packs" {"<builder> <pack>": ...}
## (every tier), "styles" {"<style> <builder> <pack>": ...}, "weak" and "covered" {pack:
## ...} (over the Builders whose BUILDERS covers leave its check out, and those that cover
## it), "weak_pm" and "covered_pm" {pack: per mille breached}, "cells_pm" and "packs_pm"
## alike, and "lines" (duel_line() of each duel)}.
func pack_matrix(defenders: Array, builders: Array, seeds: Array, packs := [], cfg := {}, options := {}) -> Dictionary:
	var sent: Array = SimContent.CHECK_IDS if packs.is_empty() else packs
	var cells := {}
	var by_pack := {}
	var by_style := {}
	var weak := {}
	var covered := {}
	var lines := []
	for style: String in defenders:
		for builder: String in builders:
			var covers: Array = SimContent.BUILDERS[builder]["covers"]
			for pack: String in sent:
				for s: Variant in seeds:
					var one := {"mode": "undertow", "seats": 2, "seed": int(s), "builders": [builder, builder], "events": false}
					one.merge(cfg, true)
					var styles := {1: "balanced"}
					if style == "caretaker":
						one["caretakers"] = [2]
					else:
						styles[2] = style
					start(one)
					var opts := options.duplicate(true)
					opts["packs"] = {1: pack}
					duel_out(styles, opts)
					lines.append("%s %s %s seed %d: %s" % [style, builder, pack, int(s), duel_line()])
					for row: Dictionary in sends:
						if int(row["seat"]) != 1 or str(row["pack"]) != pack:
							continue
						var tier := clampi(int(row["tier"]), 0, 2)
						var counts: Array = [
							cells.get_or_add("%s %s tier %d" % [builder, pack, tier + 1], [0, 0, 0, 0, 0]),
							by_pack.get_or_add("%s %s" % [builder, pack], [0, 0, 0, 0, 0]),
							by_style.get_or_add("%s %s %s" % [style, builder, pack], [0, 0, 0, 0, 0]),
							(covered if covers.has(pack) else weak).get_or_add(pack, [0, 0, 0, 0, 0]),
						]
						for c: Array in counts:
							c[0] += 1
							c[1] += 1 if int(row["leaked"]) > 0 else 0
							c[2] += int(row["creeps"])
							c[3] += int(row["leaked"])
							c[4] += int(row["lives"])
	var shares := func(table: Dictionary) -> Dictionary:
		var out := {}
		for key: String in table:
			out[key] = share_pm(table[key])
		return out
	return {
		"cells": cells, "cells_pm": shares.call(cells), "packs": by_pack, "packs_pm": shares.call(by_pack),
		"styles": by_style, "weak": weak, "weak_pm": shares.call(weak), "covered": covered,
		"covered_pm": shares.call(covered), "lines": lines,
	}


## [count, of which] as per mille of the count (0 of none).
static func share_pm(pair: Array) -> int:
	return int(pair[1]) * 1000 / maxi(1, int(pair[0]))


## The pack in `picks` (CHECK_IDS ids) that comes most often, ties to the earlier check;
## "" for none.
static func _leading_pick(picks: Array) -> String:
	var best := ""
	var most := 0
	for id: String in SimContent.CHECK_IDS:
		var n := picks.count(id)
		if n > most:
			best = id
			most = n
	return best


## Whether client 1's two seats ended the same: lives, breach dealt, stipend, gold, towers
## and duel counts (a mirror match).
func _mirrored() -> bool:
	var sim := clients[0]
	if sim.seats.size() != 2 or sim.teams.size() != 2:
		return false
	var a := sim.seats[0]
	var b := sim.seats[1]
	return (
		sim.teams[0].lives == sim.teams[1].lives
		and sim.teams[0].breach_dealt == sim.teams[1].breach_dealt
		and a.stipend == b.stipend and a.gold == b.gold and a.towers == b.towers
		and duel_counts.get(1, {}) == duel_counts.get(2, {})
	)


## (M7) Client 1's duel in one line for a balance pass: outcomes, rule, wave, minutes, then
## per seat its lives, breach dealt, stipend, towers and corks / uncorks / fizzles /
## breaches / Seawalls.
func duel_line() -> String:
	var sim := clients[0]
	var parts := []
	for t: SimRecords.SimTeam in sim.teams:
		for s: SimRecords.SimSeat in sim.seats:
			if s.team == t.id:
				parts.append(
					"s%d %d lives, breach %d, stipend %d, %d towers, %d/%d/%d/%d/%d"
					% [
						s.seat, t.lives, t.breach_dealt, s.stipend, s.towers,
						duel_count(s.seat, "cork"), duel_count(s.seat, "uncork"),
						duel_count(s.seat, "fizzle"), duel_count(s.seat, "breach"),
						duel_count(s.seat, "seawall")
					]
				)
	return "%s %s wave %d %.1f min; %s" % [
		str(sim.outcomes()), sim.decided_by(), sim.hollows[0].wave, sim.tick / 3600.0, "; ".join(parts)
	]


func _duel_play(seat: int, style: String, options: Dictionary) -> void:
	var sim := clients[0]
	var reserved := 0
	if style != "turtle":
		reserved = _duel_cork(seat, style, options)
	if not CARETAKER_BUDGET_STYLES.has(style) or not Caretaker.holds_plan(sim, sim.seat(seat)):
		plan_step(seat, "plan", reserved)
	_duel_uncork(seat)
	var no_wall: Array = options.get("no_seawall", [])
	if not no_wall.has(seat) and Caretaker.wants_seawall(sim, sim.seat(seat)):
		cmd(seat, "SEAWALL")


## Queues this round's corks for `seat` in its style; returns the gold they will take.
## config "share_pm" ({seat: per mille}) gives a seat another budget than the caretaker's
## CORK_SHARE_PM (a balance pass's sweep), and options "packs" ({seat: CHECK_IDS id}) the
## pack it corks wherever the window offers it (what each pack does against a Builder).
func _duel_cork(seat: int, style: String, options := {}) -> int:
	var sim := clients[0]
	var s := sim.seat(seat)
	var window := sim.hollows[s.hollow].wave + 1
	if not SimUndertow.window_open(sim) or sim.drift_window != window:
		return 0
	var key := "corked_%d_%d" % [seat, window]
	var queued := maxi(int(config.get(key, 0)), SimUndertow.corks_of(sim, seat, window))
	var share := int((config.get("share_pm", {}) as Dictionary).get(seat, Caretaker.CORK_SHARE_PM))
	var reserved := 0
	var rng := _style_rng(seat)
	while queued < SimUndertow.corks_allowed(sim, window):
		var tier := -1
		if style == "reckless":
			tier = SimUndertow.cheapest_tier(sim, window, s.gold - reserved)
		else:
			tier = Caretaker.cork_tier(sim, s, reserved, share)
		if tier < 0:
			break
		var pack := SimUndertow.pick_pack(sim, seat)
		if style == "random":
			pack = sim.drift_packs[rng.below(sim.drift_packs.size())]
		var only := SimContent.CHECK_IDS.find(str((options.get("packs", {}) as Dictionary).get(seat, "")))
		if only >= 0 and sim.drift_packs.has(only):
			pack = only
		var salt_hi := SimUndertow.signed32(rng.next_u32())
		var salt_lo := SimUndertow.signed32(rng.next_u32())
		var c := SimUndertow.commit(sim.match_seed, seat, window, pack, salt_hi, salt_lo)
		cmd(seat, "CORK", tier, int(c[0]), int(c[1]))
		(_salts.get_or_add(seat, []) as Array).append([window, pack, salt_hi, salt_lo, int(c[0]), int(c[1])])
		reserved += SimUndertow.cork_price(sim, tier, window)
		queued += 1
	config[key] = queued
	return reserved


## Sends UNCORK for every bottle of `seat`'s still corked, from uncork_after_t after the
## horn, with the salt it was corked with.
func _duel_uncork(seat: int) -> void:
	var sim := clients[0]
	var from := sim.uncork_tick()
	if from < 0 or sim.tick < from:
		return
	var kept: Array = _salts.get(seat, [])
	for b: SimRecords.SimBottle in SimUndertow.pending(sim, seat):
		for i in kept.size():
			var e: Array = kept[i]
			if int(e[0]) == b.window and int(e[4]) == b.commit_hi and int(e[5]) == b.commit_lo:
				cmd(seat, "UNCORK", int(e[1]), int(e[2]), int(e[3]))
				kept.remove_at(i)
				break


func _style_rng(seat: int) -> SimRng:
	if not _style_rngs.has(seat):
		_style_rngs[seat] = SimRng.new(int(config.get("seed", 1)) * 7919 + seat)
	return _style_rngs[seat]


## (M7) Plays client 1's duel until the window before wave `window` is open for both:
## every seat present works down its plan by command and presses Ready in every earlier
## window (a caretaken seat plays itself). Returns the tick; stops at `limit` with an
## error.
func duel_to_window(window: int, limit := 80000) -> int:
	while clients[0].tick < limit:
		var sim := clients[0]
		var open := SimUndertow.window_open(sim)
		if open and sim.hollows[0].wave + 1 >= window:
			return sim.tick
		for s: SimRecords.SimSeat in sim.seats:
			if s.state != SimTypes.SEAT_PRESENT:
				continue
			plan_step(s.seat)
			if open and not s.ready:
				cmd(s.seat, "READY", 1)
		run_ticks(30)
	push_error("duel_to_window: window %d not open by tick %d" % [window, limit])
	return clients[0].tick


## (M7) Steps client 1 until the shared horn sounds (a wave runs on a hollow); returns the
## horn's tick, or -1 with an error after `limit` ticks.
func run_to_horn(limit := 5000) -> int:
	var ran := 0
	while not SimUndertow.wave_running(clients[0]) and ran < limit:
		run_ticks(1)
		ran += 1
	if not SimUndertow.wave_running(clients[0]):
		push_error("run_to_horn: no horn in %d ticks" % limit)
		return -1
	return clients[0].horn_tick


## (M7) Steps client 1 until the window is open for both again; returns the tick, or -1
## with an error after `limit` ticks.
func run_to_window(limit := 20000) -> int:
	var ran := 0
	while not SimUndertow.window_open(clients[0]) and not clients[0].over and ran < limit:
		run_ticks(1)
		ran += 1
	if not SimUndertow.window_open(clients[0]):
		push_error("run_to_window: no window in %d ticks" % ran)
		return -1
	return clients[0].tick


## (M7) Queues CORK for `seat` in the open window: pack CHECK_IDS[pack] with the salt's
## halves (signed 32-bit), at `tier` (-1: the window's cheapest). Returns the commitment.
func cork(seat: int, pack: int, salt_hi := 0, salt_lo := 0, tier := -1) -> Array:
	var sim := clients[0]
	var window := sim.hollows[sim.seat(seat).hollow].wave + 1
	if tier < 0:
		tier = SimUndertow.cheapest_tier(sim, window, 1 << 30)
	var c := SimUndertow.commit(sim.match_seed, seat, window, pack, salt_hi, salt_lo)
	cmd(seat, "CORK", tier, int(c[0]), int(c[1]))
	return c


## (M7) Queues UNCORK for `seat`: pack CHECK_IDS[pack] and the salt's halves.
func uncork(seat: int, pack: int, salt_hi := 0, salt_lo := 0) -> int:
	return cmd(seat, "UNCORK", pack, salt_hi, salt_lo)


## (M7) The lives pack CHECK_IDS[pack] at `tier` takes if every creep of it leaks, and the
## gold its creeps pay a defender who kills them all.
func pack_toll(pack: int, tier := 0) -> int:
	var spec: Dictionary = SimContent.PACKS["hollow"][SimContent.CHECK_IDS[pack]]
	return int(spec["counts"][tier]) * int(SimContent.CREEPS[str(spec["creep"])]["toll"])


func pack_bounty(pack: int, tier := 0) -> int:
	var spec: Dictionary = SimContent.PACKS["hollow"][SimContent.CHECK_IDS[pack]]
	return int(spec["counts"][tier]) * int(SimContent.CREEPS[str(spec["creep"])]["bounty"])


## (M7) The left-out pack of `n` Drifts drawn in a row from a fresh duel's SimRng at `seed`
## (SimUndertow.draw_drift), each as its CHECK_IDS id, and every offer's size and order
## checked: a row of "bad offer ..." where one is not `offered` packs in CHECK_IDS order.
func drift_draws(seed_value: int, n: int) -> Array:
	var sim := SimMatch.new(SimContent.rules("undertow"), [{"team": 0}, {"team": 1}], seed_value)
	var out := []
	for i in n:
		SimUndertow.draw_drift(sim, 2 + i)
		var sorted := sim.drift_packs.duplicate()
		sorted.sort()
		if sorted != sim.drift_packs or sim.drift_packs.size() != int(sim.rules["duel"]["offered"]):
			out.append("bad offer %s" % sim.drift_packs)
		for k in SimContent.CHECK_IDS.size():
			if not sim.drift_packs.has(k):
				out.append(SimContent.CHECK_IDS[k])
	return out


## (M7) Every EV_BREACH on client k whose pay is not `times` its creep's bounty, as rows
## [creep, kind, pay]; [] when they all are.
func breaches_not_paying(times: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in events_of("BREACH", k):
		if int(e["pay"]) != times * int(SimContent.CREEPS[str(e["kind"])]["bounty"]):
			out.append([e["creep"], e["kind"], e["pay"]])
	return out


## (M7) How many entries of `list` equal the one before.
static func repeats(list: Array) -> int:
	var n := 0
	for i in range(1, list.size()):
		if list[i] == list[i - 1]:
			n += 1
	return n


## (M7) What became of every creep seat `seat` sent on client k, by id order: "died to
## seat N for B" (the DIE event's seat and bounty), "leaked" or "walking".
func sent_fates(seat: int, k := 1) -> Array:
	var out := []
	for e: Dictionary in sent_by(seat, k):
		var id := int(e["id"])
		var fate := "walking"
		for d: Dictionary in events_where("DIE", {"id": id}, k):
			fate = "died to seat %d for %d" % [int(d["seat"]), int(d["bounty"])]
		for d: Dictionary in events_where("LEAK", {"id": id}, k):
			fate = "leaked"
		out.append(fate)
	return out


## (M7) The bounties of every creep that died on hollow `hollow` of client k (DIE events).
func bounty_on(hollow: int, k := 1) -> int:
	var total := 0
	for e: Dictionary in events_where("DIE", {"hollow": hollow}, k):
		total += int(e["bounty"])
	return total


## (M7) The gold paid to seat `seat` for `why` on client k.
func gold_to(seat: int, why: String, k := 1) -> int:
	var total := 0
	for e: Dictionary in events_where("GOLD", {"seat": seat, "why": why}, k):
		total += int(e["change"])
	return total


## (M7) The health the first creep of `kind` spawned on hollow `hollow` from tick `from`
## on had on client 1 (spawned_hp), or -1.
func first_spawn_hp(kind: String, from: int, hollow := 0) -> int:
	for e: Dictionary in since(events_where("SPAWN", {"kind": kind, "hollow": hollow}), from):
		return int(spawned_hp.get(int(e["id"]), -1))
	return -1


## (M7) The ids of the creeps on hollow `hollow` of client k inside the Seawall's ring.
func ring_ids(hollow: int, k := 1) -> Array:
	var out := []
	for c: SimRecords.SimCreep in SimUndertow.in_ring(clients[k - 1], clients[k - 1].hollows[hollow]):
		out.append(c.id)
	return out


## (M7) How many bytes two checkpoints of one size differ in, or -1 when their sizes differ.
static func differing_bytes(a: PackedByteArray, b: PackedByteArray) -> int:
	if a.size() != b.size():
		return -1
	var n := 0
	for i in a.size():
		if a[i] != b[i]:
			n += 1
	return n


## (M7) A duel on client k as a balance pass reads it: per team its lives, breach dealt,
## waves cleared and its seat's stipend, Seawall charges, towers and duel counts (corks,
## uncorks, fizzles, breaches, Seawalls); then the outcomes, what decided them and when.
func duel_summary(k := 1) -> Dictionary:
	var sim := clients[k - 1]
	var per_team := []
	for t: SimRecords.SimTeam in sim.teams:
		var row := {
			"lives": t.lives,
			"breach": t.breach_dealt,
			"cleared": sim.cleared_waves(t.id),
			"phase": sim.hollows[t.hollows[0]].phase,
		}
		for s: SimRecords.SimSeat in sim.seats:
			if s.team == t.id:
				row["seat"] = s.seat
				row["stipend"] = s.stipend
				row["gold"] = s.gold
				row["towers"] = s.towers
				row["charges"] = s.seawall_charges
				row["counts"] = duel_counts.get(s.seat, {})
		per_team.append(row)
	return {
		"teams": per_team,
		"outcomes": sim.outcomes(),
		"decided_by": sim.decided_by(),
		"tick": sim.tick,
		"minutes": snappedf(sim.tick / 3600.0, 0.01),
		"wave": sim.hollows[0].wave,
	}


## (M7) How many `what` ("cork", "uncork", "fizzle", "breach", "seawall") seat `seat` made
## on client 1 (a breach counts for its sender).
func duel_count(seat: int, what: String) -> int:
	return int((duel_counts.get(seat, {}) as Dictionary).get(what, 0))


## (M7) The ticks of the horns on seat `seat`'s hollow that sounded in a window where the
## seat had not said Ready before them (since the horn before): [] when it had its say in
## every window (a caretaker playing its window before a player's Ready calls the horn).
func horns_before_ready(seat: int, k := 1) -> Array:
	var sim := clients[k - 1]
	var hollow := sim.seat(seat).hollow
	var readies := []
	for e: Dictionary in events_where("READY", {"seat": seat, "on": true}, k):
		readies.append(int(e["tick"]))
	var out := []
	var since := -1
	for e: Dictionary in events_where("WAVE", {"hollow": hollow, "start": true}, k):
		var horn := int(e["tick"])
		var said := false
		for t: int in readies:
			said = said or (t > since and t < horn)
		if not said:
			out.append(horn)
		since = horn
	return out


## (M7) The ticks seat `seat` built or forked on while its hollow stood in its window and the
## rival's still played that wave (from the tick after its clear up to the rival's clear, on
## which the window opens for both: Caretaker.holds_plan), oldest first, on client k.
func builds_while_held(seat: int, k := 1) -> Array:
	var sim := clients[k - 1]
	var mine := sim.seat(seat).hollow
	var cleared := {}  # (hollow -> {wave: the tick it cleared on})
	for e: Dictionary in events_where("WAVE", {"cleared": true}, k):
		(cleared.get_or_add(int(e["hollow"]), {}) as Dictionary)[int(e["wave"])] = int(e["tick"])
	var held := []  # ([from, to] ticks, both included)
	var own: Dictionary = cleared.get(mine, {})
	for w: int in own:
		var to := -1
		for h: int in cleared:
			if h != mine and (cleared[h] as Dictionary).has(w):
				to = maxi(to, int(cleared[h][w]))
		if to > int(own[w]):
			held.append([int(own[w]) + 1, to])
	var out := []
	for type_name: String in ["BUILT", "FORKED"]:
		for e: Dictionary in events_where(type_name, {"seat": seat}, k):
			var t := int(e["tick"])
			for span: Array in held:
				if t >= int(span[0]) and t <= int(span[1]):
					out.append(t)
	out.sort()
	return out


## (M7) The SPAWN events of the creeps seat `seat` sent on client k.
func sent_by(seat: int, k := 1) -> Array:
	return events_where("SPAWN", {"sent_by": seat}, k)


## Lives client 1's team on hollow `hollow` lost to leaks during waves `from` to `to`,
## both included.
func lives_lost(from := 1, to := 99, hollow := 0) -> int:
	var total := 0
	for leak: Array in leaks:
		if int(leak[3]) == hollow and int(leak[0]) >= from and int(leak[0]) <= to:
			total += int(leak[2])
	return total


## The leaks as a table a balance pass reads: "wave N" -> {creep kind: lives}, on a race's
## second hollow "hollow 1 wave N".
func leak_table() -> Dictionary:
	var out := {}
	for leak: Array in leaks:
		var key := "wave %d" % int(leak[0])
		if int(leak[3]) != 0:
			key = "hollow %d %s" % [int(leak[3]), key]
		var row: Dictionary = out.get_or_add(key, {})
		row[leak[1]] = int(row.get(leak[1], 0)) + int(leak[2])
	return out


## A race on client k as a balance pass reads it: per team its lives, waves cleared, clear
## tick and race time; then the outcomes and what decided them (SimMatch.outcomes(),
## decided_by()).
func race_summary(k := 1) -> Dictionary:
	var sim := clients[k - 1]
	var per_team := []
	for t: SimRecords.SimTeam in sim.teams:
		per_team.append(
			{
				"lives": t.lives,
				"cleared": sim.cleared_waves(t.id),
				"clear_tick": t.clear_tick,
				"race_t": sim.race_time(t.id),
				"fell_wave": t.fell_wave,
			}
		)
	return {
		"teams": per_team,
		"outcomes": sim.outcomes(),
		"decided_by": sim.decided_by(),
		"tick": sim.tick,
		"decided_tick": int(_decided_at.get(k, -1)),
	}


## (M8) The wave creep `id` came with on client 1 (from its spawn), -1 for one it never saw.
func creep_wave(id: int) -> int:
	return int(_creep_waves.get(id, -1))


## (M8) How many of wave `wave`'s creeps on hollow `hollow` client 1 killed so far (its DIE
## events, each creep's wave from its spawn).
func kills_of_wave(hollow: int, wave: int) -> int:
	var n := 0
	for e: Dictionary in events_where("DIE", {"hollow": hollow}):
		if creep_wave(int(e["id"])) == wave:
			n += 1
	return n


## (M8) What level `difficulty` lays over a preset (SimContent.DIFFICULTIES), and a mode's
## rules at a level (SimContent.rules), for scenarios to read the numbers from.
func level_keys(difficulty: String) -> Dictionary:
	return SimContent.DIFFICULTIES.get(difficulty, {})


func preset(mode: String, difficulty := "normal") -> Dictionary:
	return SimContent.rules(mode, difficulty)


## (M8) Whether checkpoint `bytes` loads under `mode`'s rules at `difficulty` (the codec
## refuses a level other than the rules').
func decodes(bytes: PackedByteArray, mode: String, difficulty := "normal") -> bool:
	return SimMatch.deserialize(bytes, SimContent.rules(mode, difficulty)) != null


## (M8) Seat `seat`'s bottles on client k by SimUndertow.candidates, each as CHECK_IDS ids.
func candidates_of(seat: int, k := 1) -> Array:
	var sim := clients[k - 1]
	var out := []
	for b: SimRecords.SimBottle in sim.bottle_list:
		if b.seat != seat:
			continue
		var ids := []
		for i in SimUndertow.candidates(sim, b):
			ids.append(SimContent.CHECK_IDS[i])
		out.append(ids)
	return out


## (M8) Client 1's stacked horns as a balance pass reads them: each [hollow, the wave
## called, tick, each seat's pay, the stake in lives], on `hollow` alone when it is 0 or
## more; how many, what they paid each seat together and the level played.
func stack_summary(hollow := -1) -> Dictionary:
	var calls := []
	var paid := 0
	for call: Array in stack_calls:
		if hollow < 0 or int(call[0]) == hollow:
			calls.append(call)
			paid += int(call[3])
	return {
		"calls": calls,
		"count": calls.size(),
		"paid": paid,
		"level": str(clients[0].rules.get("difficulty", "normal")),
	}


## (M8) The waves client 1's stacked horns called on hollow `hollow`, in order.
func stacked_waves(hollow := 0) -> Array:
	var out := []
	for call: Array in stack_calls:
		if int(call[0]) == hollow:
			out.append(int(call[1]))
	return out


## (M8) Client 1's match as one row the level and stacking gates compare across runs: won,
## fallen, lives, the newest wave, the waves cleared, team 0's clear tick (-1 until it
## cleared its last wave), minutes, `standing` (the lives kept once the Holdfast stands;
## after a fall the wave it fell on less 100, so a fall reads below any lives and an earlier
## fall below a later), hollow 0's stacked horns: how many and what they paid each seat
## together, its bosses (boss_lines) and what its Crest kept (boss_left_pm).
func report() -> Dictionary:
	var sim := clients[0]
	var h := sim.hollows[0]
	var fallen := h.phase == SimTypes.PHASE_FALLEN
	var stacked := stack_summary(0)
	return {
		"won": h.phase == SimTypes.PHASE_DONE,
		"fallen": fallen,
		"lives": sim.teams[0].lives,
		"wave": h.wave,
		"cleared": h.cleared,
		"clear_tick": sim.teams[0].clear_tick,
		"minutes": snappedf(sim.tick / 3600.0, 0.01),
		"standing": h.cleared + 1 - 100 if fallen else sim.teams[0].lives,
		"stacked": stacked["count"],
		"stack_paid": stacked["paid"],
		"level": stacked["level"],
		"bosses": boss_lines(),
		"crest_left_pm": boss_left_pm("hollowtide_crest"),
	}


## (M8) A series of Tide Races, one a crew in `crews` (each a list of Builders, the same crew
## on both hollows: a mirror of Builders, as the duel gates' DUEL_ROSTER), every seat played
## by command and Ready at once in every window, team 0's seats stacking as `stacking[0]`
## says and team 1's as `stacking[1]` ("plan", "all", or "" for never; play_out's), played on
## past the decision (play_on) from `cfg` (its "mode" tide_race). The match's SimRng feeds
## only a duel's Drift, so a race plays the same under every seed: the crews are what
## varies. Returns each team's wins, the draws, one row a race (the crew, both race times,
## lives, the wave each fell on, 0 standing, and the stacked horns each called), how many
## races team 0 called more stacked horns in than team 1 while team 1 called some
## (`stacked_more`), and a line a race for the watches.
func race_series(cfg: Dictionary, stacking: Array, crews: Array) -> Dictionary:
	var wins := [0, 0]
	var draws := 0
	var rows := []
	var lines := []
	var stacked_more := 0
	for crew: Array in crews:
		var one := cfg.duplicate(true)
		var n := crew.size()
		one["seats"] = 2 * n
		one["builders"] = crew + crew
		var teams := []
		for i in 2 * n:
			teams.append(0 if i < n else 1)
		one["teams"] = teams
		one["play_on"] = true
		start(one)
		var seats := []
		var how := {}
		for seat in range(1, 2 * n + 1):
			seats.append(seat)
			var style := str(stacking[0 if seat <= n else 1])
			if style != "":
				how[seat] = style
		play_out(seats, 30, 120000, seats, how)
		var sim := clients[0]
		var out := sim.outcomes()
		if out.size() == 2 and int(out[0]) == SimTypes.OUTCOME_WON:
			wins[0] += 1
		elif out.size() == 2 and int(out[1]) == SimTypes.OUTCOME_WON:
			wins[1] += 1
		else:
			draws += 1
		var row := {
			"crew": crew,
			"times": [sim.race_time(0), sim.race_time(1)],
			"lives": [sim.teams[0].lives, sim.teams[1].lives],
			"fell": [sim.teams[0].fell_wave, sim.teams[1].fell_wave],
			"stacked": [stack_summary(0)["count"], stack_summary(1)["count"]],
			"outcomes": out,
			"rule": sim.decided_by(),
		}
		rows.append(row)
		if int(row["stacked"][0]) > int(row["stacked"][1]) and int(row["stacked"][1]) > 0:
			stacked_more += 1
		lines.append(
			"%s: %s, race times %d / %d, lives %d / %d, fell %d / %d, stacked %d / %d"
			% [
				"+".join(PackedStringArray(crew)), row["rule"], row["times"][0], row["times"][1],
				row["lives"][0], row["lives"][1], row["fell"][0], row["fell"][1],
				row["stacked"][0], row["stacked"][1],
			]
		)
	return {"wins": wins, "draws": draws, "rows": rows, "lines": lines, "stacked_more": stacked_more}


## The tick client k's race was decided at (its EV_RACE "decided"), -1 while it runs.
func decided_tick(k := 1) -> int:
	return int(_decided_at.get(k, -1))


## The spawns of wave `wave` on hollow `hollow` of client k as [ticks after that wave's
## horn, creep kind], in order: what a race's two hollows must share. (M8) On client 1 a
## spawn from that horn on counts for its creep's own wave (creep_wave), so two stacked
## waves setting out together part (a debug spawn in the window before, which comes with the
## coming wave, is no spawn of its horn); on another client, every spawn from that wave's
## horn to the next's.
func wave_spawns(hollow: int, wave: int, k := 1) -> Array:
	var horn := -1
	var ends := -1
	for e: Dictionary in events_where("WAVE", {"hollow": hollow, "start": true}, k):
		if int(e["wave"]) == wave:
			horn = int(e["tick"])
		elif int(e["wave"]) == wave + 1:
			ends = int(e["tick"])
	var out := []
	if horn < 0:
		return out
	for e: Dictionary in events_where("SPAWN", {"hollow": hollow}, k):
		var at := int(e["tick"])
		var its := creep_wave(int(e["id"])) if k == 1 else -1
		if at >= horn and (its == wave or (its < 0 and (ends < 0 or at < ends))):
			out.append([at - horn, str(e["kind"])])
	return out


## Client k's EV_PULSE events from tower `tower` (0: any).
func pulses(tower := 0, k := 1) -> Array:
	if tower == 0:
		return events_of("PULSE", k)
	return events_where("PULSE", {"tower": tower}, k)


## How far creep `id` walked on client k over each of the next `n` ticks, stepping every
## client one tick at a time (-1 once it is gone): 0 while it stands stunned.
func walked_by_tick(id: int, n: int, k := 1) -> Array:
	var out := []
	for i in n:
		var c := creep(id, k)
		var before := c.dist_um if c and c.alive else -1
		run_ticks(1)
		out.append(-1 if before < 0 or not c.alive else c.dist_um - before)
	return out


## A short line for a balance gate's watches: outcome, lives, wave, minutes, towers.
func summary() -> Dictionary:
	var sim := clients[0]
	var h := sim.hollows[0]
	var forms := []
	for t in sim.towers:
		forms.append("%d:%s" % [t.owner, SimContent.tower_form(t.kind, t.branch)])
	return {
		"won": h.phase == SimTypes.PHASE_DONE,
		"lives": sim.teams[0].lives,
		"wave": h.wave,
		"minutes": snappedf(sim.tick / 3600.0, 0.01),
		"towers": forms,
		"gold": sim.seats.map(func(s: SimRecords.SimSeat) -> int: return s.gold),
		"help": sim.seats.map(func(s: SimRecords.SimSeat) -> int: return s.help_c),
		"bosses": boss_lines(),
		"wave_seconds": wave_seconds.filter(func(s: int) -> bool: return s >= 0),
		"race": race_summary() if sim.race else {},
		"duel": duel_summary() if sim.duel else {},
	}


## One line per boss: kind, wave, damage taken of its health, and how it ended (on a
## race's second hollow, "h1 " first).
func boss_lines() -> Array:
	var out := []
	for id: int in bosses:
		var b: Dictionary = bosses[id]
		var line := "%s w%d %d/%d %s" % [b["kind"], b["wave"], b["dealt"], b["hp"], b["end"]]
		out.append(("h%d " % int(b["hollow"])) + line if int(b["hollow"]) != 0 else line)
	return out


## (M8) How much of its health client 1's boss of `kind` on `hollow` kept, per mille of its
## maximum: 0 once it died, what it carried into the Holdfast if it leaked, and what it
## still has if it walks on when the match ends (a Holdfast the creeps around it took
## first); -1 when none spawned, and the most of any when several did. Counted in
## hundredths from the HIT events, so a Very Hard gate can tell a Crest that leaked with a
## sliver left from one that walked in whole (bot_reaches_crest_very_hard_*).
func boss_left_pm(kind: String, hollow := 0) -> int:
	var most := -1
	for id: int in bosses:
		var b: Dictionary = bosses[id]
		if str(b["kind"]) != kind or int(b["hollow"]) != hollow:
			continue
		var left := 0 if str(b["end"]).begins_with("died") else maxi(0, int(b["hp_c"]) - int(b["dealt_c"]))
		most = maxi(most, left * 1000 / maxi(1, int(b["hp_c"])))
	return most


## For every buildable cell and every range in the content, compares the road stretches
## a tower would cover with the brute-force test d^2 <= r^2 at every whole millimetre
## near each stretch's ends and every 25 mm in between. Returns the mismatches found.
func check_ranges(limit := 10) -> Array:
	var road := SimRoad.parse(SimContent.map_text("hollow"))
	var ranges := []
	for kind: String in SimContent.TOWER_IDS:
		if not SimContent.TOWERS.has(kind):
			continue  # a branch id: its range is checked with its base
		for branch in [-1, 0, 1]:
			if branch == -1 or SimContent.has_branch(kind, branch):
				var r := int(SimContent.tower_stats(kind, branch)["range_mm"])
				if not ranges.has(r):
					ranges.append(r)
	var bad := []
	var checked := 0
	for z in road.depth:
		for x in road.width:
			if not road.buildable(x, z):
				continue
			var cx := SimRoad.centre_mm(x)
			var cz := SimRoad.centre_mm(z)
			for r: int in ranges:
				var stretches := road.intervals(cx, cz, r)
				var probes := {}
				for i in stretches.size():
					for d in range(-2, 3):
						probes[stretches[i] + d * 1000] = true
				for dist in range(0, road.length_um + 1, 25000):
					probes[dist] = true
				for dist: int in probes:
					if dist < 0 or dist > road.length_um:
						continue
					checked += 1
					var dx := road.x_at(dist) - cx
					var dz := road.z_at(dist) - cz
					var brute := dx * dx + dz * dz <= r * r
					if brute != SimRoad.covers(stretches, dist):
						bad.append("cell %d,%d r %d at %d um: brute %s" % [x, z, r, dist, brute])
						if bad.size() >= limit:
							return bad
	config["range_points_checked"] = checked
	return bad


## (M8, the sends' pass) An uncorking on client 1: its pack's row in `sends`.
func _send_uncorked(e: Dictionary) -> void:
	var seat := int(e["seat"])
	var bottle: Array = _send_bottles.get(int(e["bottle"]), [-1, -1])
	sends.append(
		{
			"seat": seat, "tier": int(bottle[0]), "window": int(bottle[1]), "pack": str(e["pack"]),
			"creeps": int(e["creeps"]), "spawned": 0, "leaked": 0, "lives": 0,
		}
	)
	(_send_waiting.get_or_add(seat, []) as Array).append(sends.size() - 1)


## (M8, the sends' pass) A creep `seat` sent set out: it belongs to the oldest of the seat's
## uncorked packs with creeps still to come (each pack's come out in the order sent).
func _send_spawned(seat: int, id: int) -> void:
	var waiting: Array = _send_waiting.get(seat, [])
	while not waiting.is_empty():
		var row: Dictionary = sends[int(waiting[0])]
		if int(row["spawned"]) < int(row["creeps"]):
			row["spawned"] += 1
			_send_creeps[id] = int(waiting[0])
			if int(row["spawned"]) == int(row["creeps"]):
				waiting.pop_front()
			return
		waiting.pop_front()


func _count_duel(seat: int, what: String) -> void:
	var row: Dictionary = duel_counts.get_or_add(seat, {})
	row[what] = int(row.get(what, 0)) + 1


func _new_match() -> SimMatch:
	return _configured(SimMatch.new(rules(), seat_list, int(config.get("seed", 1))))


## What cfg sets on every client and no checkpoint holds (none of it is state): "play_on"
## and the plans and stack lists its caretakers play ("plans", "never_patch", "stacks"). A
## client made at start and one joined from a checkpoint (join_from) get the same, so a
## joined client's caretakers decide as the others' do.
func _configured(sim: SimMatch) -> SimMatch:
	sim.play_on = bool(config.get("play_on", false))
	var plans: Dictionary = config.get("plans", {})
	var never: Dictionary = config.get("never_patch", {})
	var stack_lists: Dictionary = config.get("stacks", {})
	for builder: String in SimContent.BUILDER_IDS:
		if stack_lists.has(builder):
			var list := PackedInt32Array()
			for wave: Variant in stack_lists[builder]:
				list.append(int(wave))
			sim.stacks[builder] = list
		if plans.has(builder):
			sim.plans[builder] = SimContent.plan_steps_of(builder, plans[builder])
		elif never.has(builder):
			sim.plans[builder] = SimContent.plan_steps_of(
				builder, without_patches(SimContent.plan(builder, sim.mode), never[builder])
			)
	return sim


## A plan whose forks that patch one of `checks` take the other branch instead, as a
## Builder would that never forks for them (coverage_matters_winged).
static func without_patches(entries: Array, checks: Array) -> Array:
	var out := []
	for step: Dictionary in entries:
		var entry := step.duplicate(true)
		if entry.has("fork") and checks.has(entry.get("patch", "")):
			entry["fork"] = "a" if str(entry["fork"]) == "b" else "b"
			entry.erase("patch")
		out.append(entry)
	return out


func _join(sim: SimMatch) -> void:
	clients.append(sim)
	stalled.append(0)
	events.append([])
	hashes.append({sim.tick: sim.state_hash_hex()} if sim.tick % SimTypes.HASH_EVERY == 0 else {})


func _step(k: int) -> void:
	var sim := clients[k]
	if seq.advance(sim, 1) == 0:
		return
	var fresh := sim.drain_events()
	for e: Dictionary in fresh:
		if int(e["type"]) == SimTypes.EV_RACE and str(e["what"]) == "decided":
			_decided_at[k + 1] = int(e["tick"])
	if k == 0:
		for e: Dictionary in fresh:
			match int(e["type"]):
				SimTypes.EV_LEAK:
					var on := int(e["hollow"])
					# (M8: the leak counts for its creep's own wave, the older of two
					# stacked ones too; with one wave on the road, the hollow's)
					var wave := int(_creep_waves.get(int(e["id"]), sim.hollows[on].wave))
					leaks.append([wave, e["kind"], e["toll"], on])
					if bosses.has(e["id"]):
						bosses[e["id"]]["end"] = "leaked at %d s" % ((sim.tick - int(bosses[e["id"]]["tick"])) / 60)
				SimTypes.EV_SPAWN:
					if int(e.get("sent_by", 0)) != 0:
						_send_spawned(int(e["sent_by"]), int(e["id"]))
					var rec := sim.creep(int(e["id"]))
					if rec:
						spawned_hp[rec.id] = rec.max_hp_c
						_creep_waves[rec.id] = rec.wave
					if rec and rec.boss:
						bosses[rec.id] = {"kind": rec.kind, "wave": sim.hollows[rec.hollow].wave, "hp": rec.max_hp_c / 100, "hp_c": rec.max_hp_c, "dealt": 0, "dealt_c": 0, "tick": sim.tick, "end": "", "hollow": rec.hollow}
				SimTypes.EV_HIT:
					if bosses.has(e["creep"]):
						bosses[e["creep"]]["dealt"] += int(e["dmg"]) / 100
						bosses[e["creep"]]["dealt_c"] += int(e["dmg"])
				SimTypes.EV_CORK, SimTypes.EV_UNCORK, SimTypes.EV_FIZZLE, SimTypes.EV_SEAWALL:
					_count_duel(int(e["seat"]), str(SimTypes.EVENT_TYPES.find_key(int(e["type"]))).to_lower())
					if int(e["type"]) == SimTypes.EV_CORK:
						_send_bottles[int(e["bottle"])] = [int(e["tier"]), int(e["window"])]
					if int(e["type"]) == SimTypes.EV_UNCORK:
						(duel_picks.get_or_add(int(e["seat"]), []) as Array).append(str(e["pack"]))
						_send_uncorked(e)
				SimTypes.EV_BREACH:
					_count_duel(int(e["by"]), "breach")
					var row: Variant = _send_creeps.get(int(e["creep"]))
					if row != null:
						sends[int(row)]["leaked"] += 1
						sends[int(row)]["lives"] += int(e["toll"])
				SimTypes.EV_DIE:
					if bosses.has(e["id"]):
						bosses[e["id"]]["end"] = "died at %d s" % ((sim.tick - int(bosses[e["id"]]["tick"])) / 60)
				SimTypes.EV_WAVE:
					if e.get("stacked", false):
						stack_calls.append([int(e["hollow"]), int(e["wave"]), int(e["tick"]), int(e["early"]), int(e["stake"])])
					if int(e["hollow"]) != 0:
						pass  # (hollow 0's waves only)
					elif e.get("start", false):
						_wave_slots[int(e["wave"])] = wave_seconds.size()
						wave_seconds.append(-sim.tick)
					elif e.get("cleared", false) and _wave_slots.has(int(e["wave"])):
						# (M8: each wave's own horn, the older of two stacked ones too)
						var slot := int(_wave_slots[int(e["wave"])])
						wave_seconds[slot] = (sim.tick + int(wave_seconds[slot])) / 60
	if bool(config.get("events", true)):
		events[k].append_array(fresh)
	if sim.tick % SimTypes.HASH_EVERY == 0:
		hashes[k][sim.tick] = sim.state_hash_hex()
