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


## {"mode": "classic", "seats": 1, "seed": 1, "clients": 1, "caretakers": [seat numbers]}
func start(cfg := {}) -> SimMatch:
	config = cfg
	var seat_count := int(cfg.get("seats", 1))
	var caretakers: Array = cfg.get("caretakers", [])
	seat_list = []
	for i in seat_count:
		seat_list.append(
			{"team": 0, "builder": "lamplighter", "caretaker": caretakers.has(i + 1)}
		)
	seq = LocalSequencer.new(seat_count)
	clients.clear()
	events.clear()
	hashes.clear()
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


## Works down the Lamplighter's plan for `seat` as commands, like tests/bot.gd does
## through the game: queues every step it can pay for now. Returns steps queued.
func plan_step(seat: int, cursor_name := "plan") -> int:
	var sim := clients[0]
	var s := sim.seat(seat)
	var steps: Array = sim.plans[s.builder]
	var key := "%s_%d" % [cursor_name, seat]
	var cursor := int(config.get(key, 0))
	var spent := 0
	var queued := 0
	while cursor < steps.size():
		var step: PackedInt32Array = steps[cursor]
		var here := sim.tower_at(0, step[2], step[3])
		if step[0] == 0:
			var kind := SimContent.kit_tower(s.builder, step[1])
			var cost := int(SimContent.TOWERS[kind]["cost"])
			if here != null:
				cursor += 1
				continue
			if s.gold - spent < cost:
				break
			cmd(seat, "BUILD", step[1], step[2], step[3])
			spent += cost
		else:
			if here == null:
				break  # its build has not landed yet
			var cost := int(SimContent.TOWERS[here.kind]["fork_cost"])
			if s.gold - spent < cost:
				break
			cmd(seat, "FORK", here.id, step[1])
			spent += cost
		cursor += 1
		queued += 1
	config[key] = cursor
	return queued


## For every buildable cell and every range in the content, compares the road stretches
## a tower would cover with the brute-force test d^2 <= r^2 at every whole millimetre
## near each stretch's ends and every 25 mm in between. Returns the mismatches found.
func check_ranges(limit := 10) -> Array:
	var road := SimRoad.parse(SimContent.map_text("hollow"))
	var ranges := []
	for kind: String in SimContent.TOWER_IDS:
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
	return SimMatch.new(
		SimContent.rules(str(config.get("mode", "classic"))),
		seat_list,
		int(config.get("seed", 1))
	)


func _join(sim: SimMatch) -> void:
	clients.append(sim)
	events.append([])
	hashes.append({sim.tick: sim.state_hash_hex()} if sim.tick % SimTypes.HASH_EVERY == 0 else {})


func _step(k: int) -> void:
	var sim := clients[k]
	if seq.advance(sim, 1) == 0:
		return
	events[k].append_array(sim.drain_events())
	if sim.tick % SimTypes.HASH_EVERY == 0:
		hashes[k][sim.tick] = sim.state_hash_hex()
