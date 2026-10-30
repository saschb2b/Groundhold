## A scripted player for balance tests and the --bot flag. In the classic match it works
## down the Lamplighter's classic plan (data/plans/lamplighter.json, the same plan the
## caretaker follows) and sends each step through the game's own input route, the build
## controller, as soon as it can pay. In any other mode it plays whatever Builder its seat
## has, the way the caretaker would (Caretaker.decide on the match's own plan for that
## Builder: alternative cells, the patching forks the team lacks), still through the build
## controller, so a Lookout's seat or a Lamplighter's High Water seat plays from the hub
## (tools/net/smoke.py --flow --bot). Use from a scenario:
##   {"eval": "resource('res://tests/bot.gd').new()", "as": "bot"}
##   {"repeat": 400, "steps": [{"eval": "bot.step(scene)"}, {"wait": 15}],
##    "until": "Game.state >= 2"}
extends RefCounted

const BUILDER := "lamplighter"
## A second seat's plan, on other cells (a party of bots holds one road together).
const SEAT_PLANS := "res://tests/plans/lamplighter_seat%d.json"

var plan: Array = SimContent.plan(BUILDER)
var done := 0
var log: Array[String] = []
var _seat := 1


## Takes the next steps of the plan it can afford. Returns how many steps are done.
## A step waits while an earlier order of its own is still on its way.
func step(main: Node) -> int:
	var sim: SimMatch = main.get("sim")
	if sim != null and sim.mode != "classic":
		return _step_as_caretaker(main, sim)
	if Game.seat != _seat:
		_seat = Game.seat
		plan = plan_for(_seat)
	while done < plan.size():
		var entry: Dictionary = plan[done]
		var at: Array = entry["cell"]
		var cell := Vector2i(int(at[0]), int(at[1]))
		var what := "build %s" % entry["build"] if entry.has("build") else "upgrade"
		if entry.has("build"):
			var kind := str(entry["build"])
			if not Game.can_afford(Game.tower_cost(kind)):
				return done
			if main.tower_at(cell) != null or not main.build(kind, cell):
				log.append("could not build %s at %s" % [kind, cell])
		else:
			var tower: Tower = main.tower_at(cell)
			if tower == null and not main.settled():
				return done  # its build has not landed yet
			if tower == null or tower.upgrade_cost() < 0 or tower.owner_seat != Game.seat:
				log.append("nothing to upgrade at %s" % cell)
			elif not Game.can_afford(tower.upgrade_cost()):
				return done
			elif not main.fork(cell):
				log.append("could not upgrade at %s" % cell)
		log.append("wave %d: %s at %s" % [Game.wave, what, cell])
		done += 1
	return done


## Any Builder, any mode but classic: the seat's plan as the caretaker reads it, one step
## at a time; a step waits while an order of mine is still on its way, so a fork never
## races the build it forks and gold is never counted twice.
func _step_as_caretaker(main: Node, sim: SimMatch) -> int:
	var s := sim.seat(Game.seat)
	var steps: Array = sim.plans.get(s.builder, [])
	while done < steps.size():
		if not main.settled():
			return done
		var d := Caretaker.decide(sim, s, steps[done], s.gold)
		if d[0] == Caretaker.WAIT:
			return done
		if d[0] == Caretaker.BUILD:
			var kind := SimContent.kit_tower(s.builder, d[1])
			var cell := Vector2i(d[2], d[3])
			if not main.build(kind, cell):
				log.append("could not build %s at %s" % [kind, cell])
			else:
				log.append("wave %d: build %s at %s" % [Game.wave, kind, cell])
		elif d[0] == Caretaker.FORK:
			var tower := sim.tower(d[1])
			var cell := Vector2i(tower.x, tower.z)
			if not main.fork(cell, d[2]):
				log.append("could not fork %s at %s" % [tower.kind, cell])
			else:
				log.append("wave %d: fork %s at %s to %s" % [Game.wave, tower.kind, cell, "AB"[d[2]]])
		done += 1
	return done


## Seat 1 plays the Builder's own plan; seat k > 1 its own plan from tests/plans/ if one
## is there.
static func plan_for(seat: int) -> Array:
	var path := SEAT_PLANS % seat
	if seat > 1 and FileAccess.file_exists(path):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if parsed is Dictionary:
			return (parsed as Dictionary).get("steps", [])
	return SimContent.plan(BUILDER)
