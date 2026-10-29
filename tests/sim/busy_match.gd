## A busy three-seat match for the checkpoint codec's test (sim_checkpoint_roundtrip_busy;
## review M1 determinism 2): seats 1 and 3 work down the same plan by command, so they
## contest cells; seat 2 is caretaken from tick 0; seat 3 goes AWAY and comes BACK, seat 1
## is LEFT late; signals, Ready presses, a sale and orders the rules refuse. Every field of
## every record takes a value other than its default at some point, so a codec that drops
## one parts the hashes of a round-tripped simulation from the uninterrupted one.
##
##   {"eval": "resource('res://tests/sim/busy_match.gd')", "as": "B"}
##   {"eval": "B.busy_log(7)", "as": "rec"}
##   {"eval": "B.roundtrip_chain(rec, 7, 3)", "as": "trip"}, {"assert": "trip['first_bad'] == -1"}
extends RefCounted


## Plays the busy match from tick 0 to its end (or `limit`). Returns the turn log
## (LocalSequencer.log_for) with the hash at every tick ("per_tick") and a summary.
static func busy_log(seed_value := 7, limit := 60000) -> Dictionary:
	var seats := [
		{"team": 0, "builder": "lamplighter"},
		{"team": 0, "builder": "lamplighter", "caretaker": true},
		{"team": 0, "builder": "lamplighter"},
	]
	var sim := SimMatch.new(SimContent.rules("classic"), seats, seed_value)
	var seq := LocalSequencer.new(3)
	var cursors := {1: 0, 3: 0}
	var per_tick := {0: sim.state_hash_hex()}
	var sold := false
	var signals := 0
	var away_seen := false
	while not sim.over and sim.tick < limit:
		var t := sim.tick
		if t % 45 == 0:
			for s: int in [1, 3]:
				if sim.seat(s).state == SimTypes.SEAT_PRESENT:
					cursors[s] = _plan(sim, seq, s, int(cursors[s]))
		if t % 97 == 0:
			seq.submit_as(3, SimTypes.CMD_SIGNAL, 1000 + t, 2000, 0)
			signals += 1
		if t % 131 == 0:
			seq.submit_as(1, SimTypes.CMD_READY, 1)
		if t % 400 == 7:
			seq.submit_as(3, SimTypes.CMD_BUILD, 7, 1, 1)  # (no such slot)
			seq.submit_as(1, SimTypes.CMD_FORK, 99999, 0)  # (no such tower)
			if not sim.towers.is_empty():
				seq.submit_as(3, SimTypes.CMD_SELL, sim.towers[0].id)  # (not always seat 3's)
		if t == 1501:
			seq.system(SimTypes.SYS_AWAY, 3)
		if t == 4003:
			seq.system(SimTypes.SYS_BACK, 3)
		if t == 3500 and not sold and sim.towers.size() > 2:
			for tower in sim.towers:
				if tower.owner == 1:
					seq.submit_as(1, SimTypes.CMD_SELL, tower.id)
					sold = true
					break
		if t == 12001:
			seq.system(SimTypes.SYS_LEFT, 1)
		if seq.advance(sim, 1) == 0:
			break
		sim.drain_events()
		away_seen = away_seen or sim.seat(3).state == SimTypes.SEAT_AWAY
		per_tick[sim.tick] = sim.state_hash_hex()
	var record := seq.log_for(sim, seats)
	record["per_tick"] = per_tick
	record["final_tick"] = sim.tick
	record["over"] = sim.over
	record["wave"] = sim.hollows[0].wave
	record["towers"] = sim.towers.size()
	record["sold"] = sold
	record["signals"] = signals
	record["away_seen"] = away_seen
	record["left_seen"] = sim.seat(1).state == SimTypes.SEAT_LEFT
	record["seat_states"] = [sim.seat(1).state, sim.seat(2).state, sim.seat(3).state]
	record["plan_cursors"] = [sim.seat(1).plan_cursor, sim.seat(2).plan_cursor, sim.seat(3).plan_cursor]
	return record


## The next steps of `seat_no`'s plan it can pay for, sent as commands. Returns the cursor.
static func _plan(sim: SimMatch, seq: LocalSequencer, seat_no: int, cursor: int) -> int:
	var s := sim.seat(seat_no)
	var steps: Array = sim.plans[s.builder]
	var spent := 0
	while cursor < steps.size():
		var step: PackedInt32Array = steps[cursor]
		var here := sim.tower_at(0, step[2], step[3])
		if step[0] == 0:
			var cost := int(SimContent.TOWERS[SimContent.kit_tower(s.builder, step[1])]["cost"])
			if here != null:
				cursor += 1
				continue
			if s.gold - spent < cost:
				break
			seq.submit_as(seat_no, SimTypes.CMD_BUILD, step[1], step[2], step[3])
			spent += cost
		else:
			if here == null:
				break
			if here.owner != seat_no or here.branch != -1:
				cursor += 1
				continue
			var cost := int(SimContent.TOWERS[here.kind]["fork_cost"])
			if s.gold - spent < cost:
				break
			seq.submit_as(seat_no, SimTypes.CMD_FORK, here.id, step[1])
			spent += cost
		cursor += 1
	return cursor


## Replays `record`'s turns into a simulation that is replaced by
## deserialize(serialize()) every `every` ticks (at tick ≡ `offset`), comparing its hash
## with the uninterrupted run's at every tick. Returns {"first_bad": the first tick that
## differs or -1, "why", "trips": round trips made, "final": the last tick reached}.
static func roundtrip_chain(record: Dictionary, every := 7, offset := 0, events := false) -> Dictionary:
	var rules := SimContent.rules(str(record["mode"]))
	var seats: Array = record["seats"]
	var sim := SimMatch.new(rules, seats, int(record["seed"]))
	sim.events_on = events
	var source := LocalSequencer.replaying(record["turns"], record["debug"], seats.size())
	var reference: Dictionary = record["per_tick"]
	var trips := 0
	while sim.tick < int(record["final_tick"]):
		if sim.tick % every == offset % every:
			var bytes := sim.serialize()
			var back := SimMatch.deserialize(bytes, rules)
			back.events_on = events
			if back.serialize() != bytes:
				return {"first_bad": sim.tick, "why": "re-encoding differs", "trips": trips, "final": sim.tick}
			sim = back
			trips += 1
		if source.advance(sim, 1) == 0:
			return {"first_bad": sim.tick, "why": "the log ran out", "trips": trips, "final": sim.tick}
		sim.drain_events()
		if str(reference.get(sim.tick, "")) != sim.state_hash_hex():
			return {"first_bad": sim.tick, "why": "hash differs", "trips": trips, "final": sim.tick}
	return {"first_bad": -1, "why": "", "trips": trips, "final": sim.tick}
