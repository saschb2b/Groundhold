## A scripted player for balance tests: works down a fixed build order, buying
## each step as soon as it can afford it. Use from a scenario:
##   {"eval": "resource('res://tests/bot.gd').new()", "as": "bot"}
##   {"repeat": 400, "steps": [{"eval": "bot.step(scene)"}, {"wait": 30}],
##    "until": "Game.state >= 2"}
extends RefCounted

const PLAN := [
	["build", "arrow", Vector2i(8, 3)],
	["build", "arrow", Vector2i(10, 8)],
	["build", "cannon", Vector2i(8, 11)],
	["build", "frost", Vector2i(13, 8)],
	["build", "arrow", Vector2i(12, 12)],
	["build", "cannon", Vector2i(5, 12)],
	["upgrade", "", Vector2i(10, 8)],
	["upgrade", "", Vector2i(8, 11)],
	["build", "arrow", Vector2i(14, 7)],
	["build", "cannon", Vector2i(11, 8)],
	["upgrade", "", Vector2i(8, 3)],
	["upgrade", "", Vector2i(12, 12)],
	["upgrade", "", Vector2i(5, 12)],
	["build", "arrow", Vector2i(4, 11)],
	["upgrade", "", Vector2i(11, 8)],
	["upgrade", "", Vector2i(13, 8)],
	["build", "cannon", Vector2i(15, 12)],
	["upgrade", "", Vector2i(14, 7)],
	["upgrade", "", Vector2i(15, 12)],
	["upgrade", "", Vector2i(4, 11)],
]

var done := 0
var log: Array[String] = []


## Takes the next step of the plan if affordable. Returns how many steps are done.
func step(main: Node) -> int:
	while done < PLAN.size():
		var entry: Array = PLAN[done]
		var cell: Vector2i = entry[2]
		if entry[0] == "build":
			if not Game.can_afford(int(Game.TOWERS[entry[1]]["cost"])):
				return done
			if not main.build(entry[1], cell):
				log.append("could not build %s at %s" % [entry[1], cell])
		else:
			var tower: Tower = main.tower_at(cell)
			if tower == null or tower.upgrade_cost() < 0:
				log.append("nothing to upgrade at %s" % cell)
			elif not Game.can_afford(tower.upgrade_cost()):
				return done
			else:
				main.controller.select(tower)
				main.controller.upgrade_selected()
				main.controller.select(null)
		log.append("wave %d: %s %s at %s" % [Game.wave, entry[0], entry[1], cell])
		done += 1
	return done
