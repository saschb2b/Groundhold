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
## and then the decided race are in the state for the rest of the log. duel_log (M7) plays
## a busy Undertow duel for the codec's M7 block (sim_checkpoint_roundtrip_undertow), and
## roundtrip_chain compares a duel's own state (duel_state) across every trip too.
## (M8) busy_log plays at a `difficulty`, and with `stack` seat 1's Ready presses go out
## during waves too, so a preset that stacks calls waves while the last still sends its
## creeps (beside its caretaken partner, or while seat 3 is away): the M8 block's state
## (sim_checkpoint_roundtrip_m8), the older wave's spawns still to come among it. Without it, they go out only where they would have been
## taken before M8 (in a window that its countdown does not end before they land, or in a
## preset that never stacks), so the match plays as it did before M8's rules.
extends RefCounted


## Plays the busy match from tick 0 to its end (or `limit`). Returns the turn log
## (LocalSequencer.log_for) with the hash at every tick ("per_tick") and a summary.
static func busy_log(
	seed_value := 7, limit := 60000, mode := "classic",
	builders := ["lamplighter", "lamplighter", "lamplighter"], fall := [], difficulty := "normal",
	stack := false
) -> Dictionary:
	var two_teams := int(SimContent.rules(mode)["teams"]) == 2
	var seats := [
		{"team": 0, "builder": builders[0]},
		{"team": 0, "builder": builders[1], "caretaker": true},
		{"team": 1 if two_teams else 0, "builder": builders[2]},
	]
	var sim := SimMatch.new(SimContent.rules(mode, difficulty), seats, seed_value)
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
	# (M8) ticks on which a hollow had two waves on its road, a creep of the older walked, and
	# the older still had creeps to send while the newer sent its own
	var stacked_seen := {"two_waves": 0, "older_creeps": 0, "two_spawning": 0}
	while not sim.over and sim.tick < limit:
		for tower in sim.towers:
			most_marked = maxi(most_marked, tower.marked.size())
		_count_m6(sim, m6_seen)
		_count_m8(sim, stacked_seen)
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
		if t % 131 == 0 and (stack or _taken_before_m8(sim, t)):
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
	record["difficulty"] = difficulty
	record["per_tick"] = per_tick
	record["final_tick"] = sim.tick
	record["over"] = sim.over
	record["wave"] = sim.hollows[0].wave
	record["stacked_seen"] = stacked_seen
	record["m8_state"] = m8_state(sim)
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


## (M7) A busy duel for the codec's M7 block (sim_checkpoint_roundtrip_undertow): seat 1,
## a Lamplighter by command, works down its plan, corks the window's cheapest tier
## whenever it can pay (a salt of its own stream each time) and reveals every other bottle,
## so the rest fizzle, raises its Seawall whenever the caretaker would, and is AWAY from
## tick 9001 to 13001 (its caretaker cannot reveal its salted bottles); seat 2 is the
## caretaker from tick 0 (corks with salt 0, uncorks, raises its Seawall). With
## `fall_team`, that team's lives go to 0 (a logged scenario setter) 600 ticks into the
## Surge's second wave, so the duel is decided by the fall there and plays on to the other
## hollow's end (SimMatch.play_on), its decision in the state for every tick after; seat 1
## gives no more orders once its hollow has fallen. Returns the turn log as busy_log does,
## with "seen": how many ticks each piece of the duel's state was set.
static func duel_log(seed_value := 3, limit := 30000, fall_team := -1) -> Dictionary:
	var seats := [
		{"team": 0, "builder": "lamplighter"},
		{"team": 1, "builder": "lamplighter", "caretaker": true},
	]
	var sim := SimMatch.new(SimContent.rules("undertow"), seats, seed_value)
	sim.play_on = fall_team >= 0
	var seq := LocalSequencer.new(2)
	var cursor := 0
	var fell := false
	var decided_tick := -1
	var salts := []
	var rng := SimRng.new(seed_value * 31 + 1)
	var reveal := true
	var per_tick := {0: sim.state_hash_hex()}
	var seen := {
		"corked": 0, "uncorked": 0, "fizzled": 0, "sends": 0, "walls": 0, "stipend": 0,
		"breach": 0, "charges": 0, "surge": 0, "decided": 0,
	}
	while not sim.over and sim.tick < limit:
		var t := sim.tick
		var s := sim.seat(1)
		if t == 0:
			# (200 lives each, a logged scenario setter, so the duel lasts into the Surge)
			for team in 2:
				seq.record_debug(t, SimTypes.DBG_LIVES, team, 200, 0)
				sim.debug(SimTypes.DBG_LIVES, team, 200)
		if (
			fall_team >= 0 and not fell and sim.horn_tick >= 0 and t == sim.horn_tick + 600
			and SimUndertow.surge_of(sim, sim.hollows[0].wave) == 2
		):
			seq.record_debug(t, SimTypes.DBG_LIVES, fall_team, 0, 0)
			sim.debug(SimTypes.DBG_LIVES, fall_team, 0)
			fell = true
		if t % 45 == 0 and s.state == SimTypes.SEAT_PRESENT and sim.hollows[0].phase != SimTypes.PHASE_FALLEN:
			var window := sim.hollows[0].wave + 1
			if SimUndertow.window_open(sim) and sim.drift_window == window and SimUndertow.corks_of(sim, 1, window) == 0:
				var tier := SimUndertow.cheapest_tier(sim, window, s.gold)
				if tier >= 0:
					var pack := SimUndertow.weakest_pack(sim, 1)
					var hi := SimUndertow.signed32(rng.next_u32())
					var lo := SimUndertow.signed32(rng.next_u32())
					var c := SimUndertow.commit(sim.match_seed, 1, window, pack, hi, lo)
					seq.submit_as(1, SimTypes.CMD_CORK, tier, int(c[0]), int(c[1]))
					salts.append([window, pack, hi, lo, int(c[0]), int(c[1])])
			cursor = _plan(sim, seq, 1, cursor)
			if sim.uncork_tick() >= 0 and t >= sim.uncork_tick():
				for b in SimUndertow.pending(sim, 1):
					for i in salts.size():
						var e: Array = salts[i]
						if int(e[0]) == b.window and int(e[4]) == b.commit_hi and int(e[5]) == b.commit_lo:
							if reveal:
								seq.submit_as(1, SimTypes.CMD_UNCORK, int(e[1]), int(e[2]), int(e[3]))
							reveal = not reveal
							salts.remove_at(i)
							break
			if Caretaker.wants_seawall(sim, s):
				seq.submit_as(1, SimTypes.CMD_SEAWALL)
		if t == 9001:
			seq.system(SimTypes.SYS_AWAY, 1)
		if t == 13001:
			seq.system(SimTypes.SYS_BACK, 1)
		if seq.advance(sim, 1) == 0:
			break
		if decided_tick < 0 and sim.decided_by() != "":
			decided_tick = sim.tick
		sim.drain_events()
		_count_duel(sim, seen)
		per_tick[sim.tick] = sim.state_hash_hex()
	var record := seq.log_for(sim, seats)
	record["per_tick"] = per_tick
	record["final_tick"] = sim.tick
	record["over"] = sim.over
	record["wave"] = sim.hollows[0].wave
	record["seen"] = seen
	record["duel_state"] = duel_state(sim)
	record["decided_tick"] = decided_tick
	record["play_on"] = sim.play_on
	return record


static func _count_duel(sim: SimMatch, seen: Dictionary) -> void:
	var now := {
		"corked": false, "uncorked": false, "fizzled": false,
		"sends": not sim.hollows[0].sends.is_empty() or not sim.hollows[1].sends.is_empty(),
		"walls": false, "stipend": false, "charges": false,
		"breach": sim.teams[0].breach_dealt > 0 or sim.teams[1].breach_dealt > 0,
		"surge": SimUndertow.surge_of(sim, sim.hollows[0].wave) > 0,
		"decided": sim.decided_by() != "",
	}
	for b in sim.bottle_list:
		now["corked"] = now["corked"] or (not b.uncorked and not b.fizzled)
		now["uncorked"] = now["uncorked"] or b.uncorked
		now["fizzled"] = now["fizzled"] or b.fizzled
	for s in sim.seats:
		now["walls"] = now["walls"] or s.seawall_ready > sim.tick
		now["stipend"] = now["stipend"] or s.stipend > 0
		now["charges"] = now["charges"] or s.seawall_charges > 0 or s.seawall_lost > 0
	for key: String in now:
		if now[key]:
			seen[key] = int(seen[key]) + 1


## (M7) A duel's own state as the codec's M7 block holds it: the decision, the Drift, the
## horn, per seat [stipend, Seawall charges, lives toward the next, ready tick], per team its
## breach dealt and its creeps through by check, per hollow its sends, and every bottle's
## fields; [] outside a duel.
static func duel_state(sim: SimMatch) -> Array:
	if not sim.duel:
		return []
	var seats := []
	for s in sim.seats:
		seats.append([s.stipend, s.seawall_charges, s.seawall_lost, s.seawall_ready])
	var bottles := []
	for b in sim.bottle_list:
		bottles.append([b.id, b.seat, b.tier, b.window, b.commit_hi, b.commit_lo, b.price, b.pack, b.uncorked, b.fizzled])
	return [
		sim.decided_by(), sim.outcomes(), sim.drift_window, sim.drift_left, Array(sim.drift_packs),
		sim.horn_tick, seats, [sim.teams[0].breach_dealt, sim.teams[1].breach_dealt],
		[Array(sim.teams[0].leaked), Array(sim.teams[1].leaked)],
		[Array(sim.hollows[0].sends), Array(sim.hollows[1].sends)], bottles,
	]


## A race's own state as the codec's trailing block holds it: the decision's rule and
## outcomes, then per team [fell_wave, fell_kills, wave_kills, clear_tick, lives, (M8) the
## kills of the younger waves on its road].
static func race_state(sim: SimMatch) -> Array:
	var per_team := []
	for t in sim.teams:
		per_team.append([t.fell_wave, t.fell_kills, t.wave_kills, t.clear_tick, t.lives, Array(t.stack_kills)])
	return [sim.decided_by(), sim.outcomes(), per_team]


## (M8) Whether seat 1's READY sent at tick `t` lands where the rules before M8 took it: in
## its hollow's window, before the countdown ends (it lands on the next turn's tick), or in
## any phase of a preset that never stacks, which refuses one in a wave as before. Elsewhere
## a preset that stacks would take it as a call for the next wave.
static func _taken_before_m8(sim: SimMatch, t: int) -> bool:
	if sim.stack_max < 2:
		return true
	var h := sim.hollows[sim.seat(1).hollow]
	if h.phase == SimTypes.PHASE_WAVE:
		return false
	var lands := posmod(-t, SimTypes.TURN_TICKS)
	return h.phase != SimTypes.PHASE_PREP or h.countdown_t > lands


## (M8) What the codec's M8 block holds, read from the records: the level, each hollow's
## waves cleared, the waves on its road and the older waves' spawns still to come, and every
## creep's [id, wave].
static func m8_state(sim: SimMatch) -> Array:
	var per_hollow := []
	for h in sim.hollows:
		per_hollow.append([h.cleared, Array(sim.waves_on_road(h.id)), Array(h.behind)])
	var per_creep := []
	for c in sim.creeps:
		per_creep.append([c.id, c.wave])
	return [sim.level, per_hollow, per_creep]


static func _count_m8(sim: SimMatch, seen: Dictionary) -> void:
	var two := false
	var spawning := false
	for h in sim.hollows:
		two = two or sim.waves_on_road(h.id).size() >= 2
		spawning = spawning or (not h.behind.is_empty() and h.cursor * 2 < h.queue.size())
	var older := false
	for c in sim.creeps:
		older = older or c.wave < sim.hollows[c.hollow].wave
	if two:
		seen["two_waves"] = int(seen["two_waves"]) + 1
	if older:
		seen["older_creeps"] = int(seen["older_creeps"]) + 1
	if spawning:
		seen["two_spawning"] = int(seen["two_spawning"]) + 1


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
## trips made while the race stood decided, (M8) "stacked_trips": trips made while a hollow
## had two waves on its road, "spawning_trips": those made while an older wave still had
## creeps to send beside the newest's (SimHollow.behind)}. A record with a "difficulty" plays
## that level.
static func roundtrip_chain(record: Dictionary, every := 7, offset := 0, events := false) -> Dictionary:
	var rules := SimContent.rules(str(record["mode"]), str(record.get("difficulty", "normal")))
	var seats: Array = record["seats"]
	var sim := SimMatch.new(rules, seats, int(record["seed"]))
	sim.events_on = events
	sim.play_on = bool(record.get("play_on", false))
	var source := LocalSequencer.replaying(record["turns"], record["debug"], seats.size())
	var reference: Dictionary = record["per_tick"]
	var trips := 0
	var decided_trips := 0
	var stacked_trips := 0
	var spawning_trips := 0
	var why := ""
	while sim.tick < int(record["final_tick"]):
		if sim.tick % every == offset % every:
			var bytes := sim.serialize()
			var back := SimMatch.deserialize(bytes, rules)
			if back == null:
				why = "the bytes did not decode"
				break
			back.events_on = events
			back.play_on = sim.play_on
			if back.serialize() != bytes:
				why = "re-encoding differs"
				break
			if race_state(back) != race_state(sim):
				why = "the race's state differs"
				break
			if duel_state(back) != duel_state(sim):
				why = "the duel's state differs"
				break
			if m8_state(back) != m8_state(sim):
				why = "the stacked waves' state differs"
				break
			if sim.decided_by() != "":
				decided_trips += 1
			for h in sim.hollows:
				if sim.waves_on_road(h.id).size() >= 2:
					stacked_trips += 1
					break
			for h in sim.hollows:
				if not h.behind.is_empty():
					spawning_trips += 1
					break
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
		"stacked_trips": stacked_trips, "spawning_trips": spawning_trips,
	}
