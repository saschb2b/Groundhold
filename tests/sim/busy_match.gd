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
##
## busy_log(seed, limit, "high_water", ["lookout", "lookout", "lookout"]) plays the same
## match in High Water with three Lookouts, so marks, the Owl's Eye's picks, the Pinning
## Ballista's slows, Help and the Kestrel Flock's bounces are in the state too
## (sim_checkpoint_roundtrip_high_water); with the Bellfounder and the Beekeeper, M6's
## stuns, cracks, hastes, bee clouds and Apiary bolts, and in "tide_race" (seat 3 then on
## the second team, its own hollow) the race's state as well (sim_checkpoint_roundtrip_m6).
## A race given `fall` = [team, tick] sets that team's lives to 0 at that tick (a scenario
## setter, logged), so its Holdfast falls with the kills of the wave it is on counted, and
## the race is decided by the fall once the other team has cleared that wave; it plays on
## past the decision (SimMatch.play_on, which roundtrip_chain carries over), so the fall
## and then the decided race are in the state for the rest of the log.
extends RefCounted


## Plays the busy match from tick 0 to its end (or `limit`). Returns the turn log
## (LocalSequencer.log_for) with the hash at every tick ("per_tick") and a summary.
static func busy_log(
	seed_value := 7, limit := 60000, mode := "classic",
	builders := ["lamplighter", "lamplighter", "lamplighter"], fall := []
) -> Dictionary:
	var two_teams := int(SimContent.rules(mode)["teams"]) == 2
	var seats := [
		{"team": 0, "builder": builders[0]},
		{"team": 0, "builder": builders[1], "caretaker": true},
		{"team": 1 if two_teams else 0, "builder": builders[2]},
	]
	var sim := SimMatch.new(SimContent.rules(mode), seats, seed_value)
	sim.play_on = sim.race and fall.size() == 2
	var seq := LocalSequencer.new(3)
	var cursors := {1: 0, 3: 0}
	var decided_tick := -1
	var per_tick := {0: sim.state_hash_hex()}
	var sold := false
	var signals := 0
	var away_seen := false
	var most_marked := 0
	var bounces_seen := 0
	# (M6) ticks on which a creep stood stunned or cracked, a tower hastened or under a
	# cloud, an Apiary bolt flew
	var m6_seen := {"stunned": 0, "cracked": 0, "hastened": 0, "clouds": 0, "bolts": 0}
	while not sim.over and sim.tick < limit:
		for tower in sim.towers:
			most_marked = maxi(most_marked, tower.marked.size())
		_count_m6(sim, m6_seen)
		for shot in sim.shots:
			if shot.bounce > 0:
				bounces_seen += 1
		var t := sim.tick
		if t == 0 and builders[0] == "bellfounder":
			# (a Chime Post first, so a crack is in the state long before her plan's own)
			seq.submit_as(1, SimTypes.CMD_BUILD, 2, 6, 4)
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
		if sim.play_on and t == int(fall[1]):
			seq.record_debug(t, SimTypes.DBG_LIVES, int(fall[0]), 0, 0)
			sim.debug(SimTypes.DBG_LIVES, int(fall[0]), 0)
		if seq.advance(sim, 1) == 0:
			break
		if decided_tick < 0 and sim.decided_by() != "":
			decided_tick = sim.tick
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
	var forms := []
	for tower in sim.towers:
		forms.append("%d:%s" % [tower.owner, SimContent.tower_form(tower.kind, tower.branch)])
	record["forms"] = forms
	record["most_marked"] = most_marked
	record["bounces_seen"] = bounces_seen
	record["help"] = [sim.seat(1).help_c, sim.seat(2).help_c, sim.seat(3).help_c]
	record["m6_seen"] = m6_seen
	record["race"] = [sim.decided_by(), sim.outcomes(), sim.hollows.size()]
	record["race_state"] = race_state(sim)
	record["decided_tick"] = decided_tick
	record["play_on"] = sim.play_on
	return record


## A race's own state as the codec's trailing block holds it: the decision's rule and
## outcomes, then per team [fell_wave, fell_kills, wave_kills, clear_tick, lives].
static func race_state(sim: SimMatch) -> Array:
	var per_team := []
	for t in sim.teams:
		per_team.append([t.fell_wave, t.fell_kills, t.wave_kills, t.clear_tick, t.lives])
	return [sim.decided_by(), sim.outcomes(), per_team]


static func _count_m6(sim: SimMatch, seen: Dictionary) -> void:
	var stunned := false
	var cracked := false
	for c in sim.creeps:
		stunned = stunned or c.stun_until > sim.tick
		cracked = cracked or c.crack_c > 0
	var hastened := false
	var clouds := false
	for t in sim.towers:
		hastened = hastened or t.haste_pm > 0
		clouds = clouds or t.cloud_creep != 0
	var bolts := false
	for shot in sim.shots:
		bolts = bolts or shot.air_bonus_pm > 0
	var now := {"stunned": stunned, "cracked": cracked, "hastened": hastened, "clouds": clouds, "bolts": bolts}
	for key: String in now:
		if now[key]:
			seen[key] = int(seen[key]) + 1


## The next steps of `seat_no`'s plan it can pay for, sent as commands. Returns the cursor.
static func _plan(sim: SimMatch, seq: LocalSequencer, seat_no: int, cursor: int) -> int:
	var s := sim.seat(seat_no)
	var steps: Array = sim.plans[s.builder]
	var spent := 0
	while cursor < steps.size():
		var step: PackedInt32Array = steps[cursor]
		var here := sim.tower_at(s.hollow, step[2], step[3])
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
## with the uninterrupted run's at every tick, and a race's own state (race_state: the
## decision and each team's fall) before and after each trip, which a field the codec
## neither wrote nor read would part without moving a hash. A record that plays on past
## its race's decision (`play_on`, a switch and no state) gives it to every copy.
## Returns {"first_bad": the first tick that differs or -1, "why", "trips": round trips
## made, "final": the last tick reached, "race": race_state at the end, "decided_trips":
## trips made while the race stood decided}.
static func roundtrip_chain(record: Dictionary, every := 7, offset := 0, events := false) -> Dictionary:
	var rules := SimContent.rules(str(record["mode"]))
	var seats: Array = record["seats"]
	var sim := SimMatch.new(rules, seats, int(record["seed"]))
	sim.events_on = events
	sim.play_on = bool(record.get("play_on", false))
	var source := LocalSequencer.replaying(record["turns"], record["debug"], seats.size())
	var reference: Dictionary = record["per_tick"]
	var trips := 0
	var decided_trips := 0
	var why := ""
	while sim.tick < int(record["final_tick"]):
		if sim.tick % every == offset % every:
			var bytes := sim.serialize()
			var back := SimMatch.deserialize(bytes, rules)
			back.events_on = events
			back.play_on = sim.play_on
			if back.serialize() != bytes:
				why = "re-encoding differs"
				break
			if race_state(back) != race_state(sim):
				why = "the race's state differs"
				break
			if sim.decided_by() != "":
				decided_trips += 1
			sim = back
			trips += 1
		if source.advance(sim, 1) == 0:
			why = "the log ran out"
			break
		sim.drain_events()
		if str(reference.get(sim.tick, "")) != sim.state_hash_hex():
			why = "hash differs"
			break
	return {
		"first_bad": sim.tick if why != "" else -1, "why": why, "trips": trips,
		"final": sim.tick, "race": race_state(sim), "decided_trips": decided_trips,
	}
