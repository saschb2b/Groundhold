## The simulation's speed at a busy moment (design 6.8, M4's sim_bench): how many ticks a
## second one SimMatch steps natively at wave 11 of High Water with four seats, the load a
## catch-up after a drop or a hidden tab runs through. A checkpoint is taken at wave
## 11's horn of a match four caretakers play from tick 0 (two Lamplighters, two
## Lookouts), then loaded and stepped through the wave's first 1,800 ticks (the most a
## catch-up runs, design 6.8) with events on and drained every tick, as a client does.
##
##   {"eval": "resource('res://tests/sim/sim_bench.gd')", "as": "Bench"}
##   {"eval": "Bench.wave_load()", "as": "load"}
##   {"eval": "Bench.measure(load, 1800, 3)", "as": "bench"}
##   {"assert": "bench['ticks_per_second'] >= Bench.FLOOR"}
##   {"assert": "bench['walk_ticks'] * 1000 >= bench['ticks'] * Bench.WALK_FLOOR_PM"}
##   {"eval": "Bench.look(load, 1800)", "as": "look"}
##   {"assert": "look['speedup_pc'] >= Bench.LOOK_FLOOR_PC"}
##
## Timing is the test's own (Time); the simulation never reads a clock.
extends RefCounted

## The floor sim_bench holds the native rate to, in ticks a second, set from the first
## measurements (M4, best of three on the laptop that measured, beside other runs): about
## 4,300 to 5,200 with M3's scan of every creep for each tower's look, about 12,000 to
## 15,000 once the look walks the creeps sorted along the road. A CI runner steps at
## about half that and slower again with four scenarios at once, so the floor sits at
## 4,000, above design 6.8's 3,000 to start. The floor cannot tell a tick that lost the
## walk: on this load the scan alone steps about 4,100 to 4,300 (review M4 round 2),
## above it. A tick that lost the walk is caught by measure()'s `walk_ticks` instead,
## counted from SimMatch.walks: step() itself must sort the creeps on WALK_FLOOR_PM of the
## ticks, so a stage 5 that no longer opens the look, or a look that no longer asks for
## the order, fails on any machine. LOOK_FLOOR_PC holds the walk's speed against the scan
## (look() opens the look itself, so it times the walk outside a real tick). The web
## export's own target is 2,000 (design 6.8), measured by hand.
const FLOOR := 4000
## How many times faster (in hundredths) stage 5's walk along the road must be than the
## scan it replaced, at this load (look()): about 8.7 times measured, so 3 leaves room
## for noise and still fails on a look that scans again.
const LOOK_FLOOR_PC := 300
## Of the ticks measure() steps, how many (per mille) at the least must sort the creeps in
## stage 5 (SimMatch.walks grew): any tick with a shooting tower that has no target asks
## for the order, which on this load is nearly every tick.
const WALK_FLOOR_PM := 900

const BUILDERS := ["lamplighter", "lookout", "lamplighter", "lookout"]


## Plays the four-seat match to the horn of wave `wave` (or its end, or `limit` ticks)
## and returns {"bytes": its checkpoint, "tick", "wave", "lives", "towers", "seats"}.
static func wave_load(wave := 11, seed_value := 1, builders := BUILDERS, limit := 200000) -> Dictionary:
	var seats := []
	for b: String in builders:
		seats.append({"team": 0, "builder": b, "caretaker": true})
	var sim := SimMatch.new(SimContent.rules("high_water"), seats, seed_value)
	sim.events_on = false
	var seq := LocalSequencer.new(seats.size())
	while sim.hollows[0].wave < wave and not sim.over and sim.tick < limit:
		if seq.advance(sim, 1) == 0:
			break
	return {
		"bytes": sim.serialize(),
		"tick": sim.tick,
		"wave": sim.hollows[0].wave,
		"lives": sim.teams[0].lives,
		"towers": sim.towers.size(),
		"seats": seats.size(),
	}


## Loads the checkpoint `runs` times and steps each `ticks` ticks (fresh empty turns, as
## a match with nobody ordering), timing each run. Returns the best run's ticks a second,
## every run's, the most creeps and shots in flight seen, whether every run reached the
## same state hash (a catch-up repeats exactly), the checkpoint's size after the last tick
## and the largest at any hash tick on the way, and `walk_ticks`: of the ticks stepped,
## those whose stage 5 sorted the creeps along the road (SimMatch.walks grew in step()).
static func measure(load: Dictionary, ticks := 1800, runs := 3) -> Dictionary:
	var rates := []
	var hashes := []
	var most_creeps := 0
	var most_shots := 0
	var final_bytes := 0
	var walk_ticks := ticks
	for r in runs:
		var sim := SimMatch.deserialize(load["bytes"], SimContent.rules("high_water"))
		var source := LocalSequencer.new(int(load["seats"]))
		var ran := 0
		var walked := 0
		var started := Time.get_ticks_usec()
		while ran < ticks and not sim.over:
			var walks_before := sim.walks
			if source.advance(sim, 1) == 0:
				break
			if sim.walks > walks_before:
				walked += 1
			sim.drain_events()
			most_creeps = maxi(most_creeps, sim.creeps.size())
			most_shots = maxi(most_shots, sim.shots.size())
			ran += 1
		var spent := maxi(1, Time.get_ticks_usec() - started)
		rates.append(ran * 1000000 / spent)
		walk_ticks = mini(walk_ticks, walked)
		hashes.append(sim.state_hash_hex())
		final_bytes = sim.serialize().size()
	var best := 0
	for rate: int in rates:
		best = maxi(best, rate)
	var same := true
	for h: String in hashes:
		same = same and h == hashes[0]
	# (the largest checkpoint of the run, not only its last: the same ticks once more,
	# untimed, serialized at every hash tick, as a game does)
	var largest := 0
	var again := SimMatch.deserialize(load["bytes"], SimContent.rules("high_water"))
	var turns := LocalSequencer.new(int(load["seats"]))
	for t in ticks:
		if again.over or turns.advance(again, 1) == 0:
			break
		again.drain_events()
		if again.tick % SimTypes.HASH_EVERY == 0:
			largest = maxi(largest, again.serialize().size())
	return {
		"ticks_per_second": best,
		"runs": rates,
		"ticks": ticks,
		"most_creeps": most_creeps,
		"most_shots": most_shots,
		"checkpoint_bytes": final_bytes,
		"largest_checkpoint_bytes": largest,
		"same_hash": same,
		"floor": FLOOR,
		"walk_ticks": walk_ticks,
	}


## The towers' look at the same load both ways, on the same ticks: stage 5's walk along
## the road (SimMatch.by_distance, then SimTargeting.furthest for each tower that shoots)
## and the scan of every creep it replaced (the same call outside open_look), each
## before the tick is stepped. Returns the microseconds each way, how many times faster
## the walk is (in hundredths, `speedup_pc`) and how many looks picked differently
## (none: sim_targeting_walk_matches_scan holds that on every tick). Both ways run in
## one process on the same states, so the ratio holds on a slower or busier machine,
## where ticks_per_second moves with it.
static func look(load: Dictionary, ticks := 1800) -> Dictionary:
	var sim := SimMatch.deserialize(load["bytes"], SimContent.rules("high_water"))
	var source := LocalSequencer.new(int(load["seats"]))
	var walk_us := 0
	var scan_us := 0
	var looks := 0
	var differ := 0
	var picks := PackedInt32Array()
	var ran := 0
	while ran < ticks and not sim.over:
		picks.clear()
		var started := Time.get_ticks_usec()
		sim.open_look()
		for t: SimRecords.SimTower in sim.towers:
			if t.shot_um_t != 0:
				picks.append(SimTargeting.furthest(sim, t, false))
		sim.close_look()
		var walked := Time.get_ticks_usec()
		var i := 0
		for t: SimRecords.SimTower in sim.towers:
			if t.shot_um_t != 0:
				if SimTargeting.furthest(sim, t, false) != picks[i]:
					differ += 1
				i += 1
		var scanned := Time.get_ticks_usec()
		walk_us += walked - started
		scan_us += scanned - walked
		looks += picks.size()
		if source.advance(sim, 1) == 0:
			break
		sim.drain_events()
		ran += 1
	return {
		"walk_us": walk_us,
		"scan_us": scan_us,
		"speedup_pc": scan_us * 100 / maxi(1, walk_us),
		"looks": looks,
		"differ": differ,
		"ticks": ran,
	}
