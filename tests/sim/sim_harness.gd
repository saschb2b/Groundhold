## A stage for the pure simulation (test level 0 in design 7.1): no views, no network.
## One LocalSequencer and N clients, each its own SimMatch fed the same turns, stepped
## thousands of ticks inside one call. Scenarios drive it with evals:
##   {"scene": "res://tests/sim/sim_harness.tscn", ...}
##   {"eval": "scene.start({'seats': 2, 'clients': 2})"}
##   {"eval": "scene.cmd(1, 'BUILD', 0, 8, 3)"}, {"eval": "scene.run_ticks(600)"}
##   {"assert": "scene.hashes_agree()"}
extends Node

var seq: LocalSequencer
var clients: Array[SimMatch] = []
var config := {}
var seat_list := []
## Per client: every event it emitted, oldest first.
var events: Array = []
## Per client: tick -> state hash (hex) at every HASH_EVERY tick.
var hashes: Array = []
## Client 1's leaks: one [wave, creep kind, toll] per creep that reached the Holdfast.
var leaks: Array = []
## Client 1's bosses by creep id: kind, wave, health, damage taken (whole points) and how
## it ended, for a balance pass to read.
var bosses := {}
## Client 1's waves: how many seconds each took from its horn to its clear.
var wave_seconds: Array = []


## {"mode": "classic", "seats": 1, "seed": 1, "clients": 1, "caretakers": [seat numbers],
##  "builders": [Builder id per seat, "lamplighter" where it runs out],
##  "plans": {Builder id: [plan entries as in data/plans]} to hand every client's
##  caretaker (and plan_step) other plans, "never_patch": {Builder id: [check ids]} for
##  its own plan with the forks that patch those checks turned to the other branch,
##  "events": false to keep no events (long balance runs; leaks are still counted)}
func start(cfg := {}) -> SimMatch:
	config = cfg
	var seat_count := int(cfg.get("seats", 1))
	var caretakers: Array = cfg.get("caretakers", [])
	var builders: Array = cfg.get("builders", [])
	seat_list = []
	for i in seat_count:
		var builder := str(builders[i]) if i < builders.size() else "lamplighter"
		seat_list.append({"team": 0, "builder": builder, "caretaker": caretakers.has(i + 1)})
	seq = LocalSequencer.new(seat_count)
	clients.clear()
	events.clear()
	hashes.clear()
	leaks.clear()
	bosses.clear()
	wave_seconds.clear()
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


## Steps every client `n` ticks, in lockstep. Returns the first client's tick.
func run_ticks(n: int) -> int:
	for i in n:
		for k in clients.size():
			_step(k)
	return clients[0].tick


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


## A debug write (SimTypes.DBG_*) on every client at once, logged like the game's
## scenario setters so a replay of record() reproduces it.
func debug(op: int, a: int, b := 0, c := 0) -> void:
	seq.record_debug(clients[0].tick, op, a, b, c)
	for sim in clients:
		sim.debug(op, a, b, c)


## Puts a creep of `kind` (a CREEP_IDS id) on the road of every client, `dist_um` along
## it, with this wave's health. Returns its id.
func spawn(kind: String, dist_um := 0) -> int:
	debug(SimTypes.DBG_SPAWN, 0, SimContent.CREEP_IDS.find(kind))
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
	for list_name: String in ["teams", "hollows", "seats", "towers", "creeps", "shots"]:
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


## Adds a client loaded from a checkpoint; it takes the following turns from the log.
func join_from(bytes: PackedByteArray) -> SimMatch:
	var sim := SimMatch.deserialize(bytes, SimContent.rules(str(config.get("mode", "classic"))))
	_join(sim)
	return sim


## The turn log so far, as LocalSequencer.replay takes it.
func record() -> Dictionary:
	return seq.log_for(clients[0], seat_list)


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
## steps queued.
func plan_step(seat: int, cursor_name := "plan") -> int:
	var sim := clients[0]
	var s := sim.seat(seat)
	var steps: Array = sim.plans[s.builder]
	var key := "%s_%d" % [cursor_name, seat]
	var cursor := int(config.get(key, 0))
	var spent := 0
	var queued := 0
	var claimed := PackedInt32Array()
	var width := sim.hollows[s.hollow].road.width
	while cursor < steps.size():
		var step: PackedInt32Array = steps[cursor]
		if step[0] == 1 and _claims_any(sim, step, claimed):
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


func _claims_any(sim: SimMatch, step: PackedInt32Array, claimed: PackedInt32Array) -> bool:
	for cell in Caretaker.cells(sim.hollows[0], step):
		if claimed.has(cell):
			return true
	return false


## Plays client 1's match to its end: the seats in `by_command` work down their plans
## through commands every `every` ticks (plan_step), caretaken seats play themselves,
## the rest stand idle. Returns the final tick.
func play_out(by_command := [], every := 30, limit := 120000) -> int:
	while not clients[0].over and clients[0].tick < limit:
		for seat: int in by_command:
			plan_step(int(seat))
		run_ticks(every)
	return clients[0].tick


## Lives client 1's team lost to leaks during waves `from` to `to`, both included.
func lives_lost(from := 1, to := 99) -> int:
	var total := 0
	for leak: Array in leaks:
		if int(leak[0]) >= from and int(leak[0]) <= to:
			total += int(leak[2])
	return total


## The leaks as a table a balance pass reads: "wave N" -> {creep kind: lives}.
func leak_table() -> Dictionary:
	var out := {}
	for leak: Array in leaks:
		var row: Dictionary = out.get_or_add("wave %d" % int(leak[0]), {})
		row[leak[1]] = int(row.get(leak[1], 0)) + int(leak[2])
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
	}


## One line per boss: kind, wave, damage taken of its health, and how it ended.
func boss_lines() -> Array:
	var out := []
	for id: int in bosses:
		var b: Dictionary = bosses[id]
		out.append("%s w%d %d/%d %s" % [b["kind"], b["wave"], b["dealt"], b["hp"], b["end"]])
	return out


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


func _new_match() -> SimMatch:
	var sim := SimMatch.new(
		SimContent.rules(str(config.get("mode", "classic"))),
		seat_list,
		int(config.get("seed", 1))
	)
	var plans: Dictionary = config.get("plans", {})
	var never: Dictionary = config.get("never_patch", {})
	for builder: String in SimContent.BUILDER_IDS:
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
	events.append([])
	hashes.append({sim.tick: sim.state_hash_hex()} if sim.tick % SimTypes.HASH_EVERY == 0 else {})


func _step(k: int) -> void:
	var sim := clients[k]
	if seq.advance(sim, 1) == 0:
		return
	var fresh := sim.drain_events()
	if k == 0:
		for e: Dictionary in fresh:
			match int(e["type"]):
				SimTypes.EV_LEAK:
					leaks.append([sim.hollows[0].wave, e["kind"], e["toll"]])
					if bosses.has(e["id"]):
						bosses[e["id"]]["end"] = "leaked at %d s" % ((sim.tick - int(bosses[e["id"]]["tick"])) / 60)
				SimTypes.EV_SPAWN:
					var rec := sim.creep(int(e["id"]))
					if rec and rec.boss:
						bosses[rec.id] = {"kind": rec.kind, "wave": sim.hollows[0].wave, "hp": rec.max_hp_c / 100, "dealt": 0, "tick": sim.tick, "end": ""}
				SimTypes.EV_HIT:
					if bosses.has(e["creep"]):
						bosses[e["creep"]]["dealt"] += int(e["dmg"]) / 100
				SimTypes.EV_DIE:
					if bosses.has(e["id"]):
						bosses[e["id"]]["end"] = "died at %d s" % ((sim.tick - int(bosses[e["id"]]["tick"])) / 60)
				SimTypes.EV_WAVE:
					if e.get("start", false):
						wave_seconds.append(-sim.tick)
					elif e.get("cleared", false) and not wave_seconds.is_empty():
						wave_seconds[-1] = (sim.tick + int(wave_seconds[-1])) / 60
	if bool(config.get("events", true)):
		events[k].append_array(fresh)
	if sim.tick % SimTypes.HASH_EVERY == 0:
		hashes[k][sim.tick] = sim.state_hash_hex()
