## What one tower of a patch branch holds alone on Wickhollow, for the words its glyph says
## (Game.lifts_line, Game.LIFTS; patch_lift_words_measured). Each run is a bare High Water
## match of the form's Builder alone in the sim harness, lives and gold out of the way: the
## tower built and forked on a cell, the hollow's wave set before the wave measured, and the
## horn sounded; it counts the creeps of the check that got through (bosses aside, whose
## leaks are every Builder's, P4 of the playtest) against those that came.
extends RefCounted

const LEVELS := ["normal", "hard", "very_hard"]


## Every patch branch: [builder, form, check], in BUILDERS' and CHECK_IDS' order.
static func patches() -> Array:
	var out := []
	for builder: String in SimContent.BUILDER_IDS:
		var lifts: Dictionary = SimContent.BUILDERS[builder]["patches"]
		for check: String in SimContent.CHECK_IDS:
			for form: String in lifts.get(check, []):
				out.append([builder, form, check])
	return out


## [base kind, branch index, the first cell the Builder's plan forks `form` on].
static func plan_cell(builder: String, form: String) -> Array:
	var built := {}
	for step: Dictionary in SimContent.plan_file(builder)["steps"]:
		var cell := Vector2i(int(step["cell"][0]), int(step["cell"][1]))
		if step.has("build"):
			built[cell] = str(step["build"])
			continue
		var base := str(built.get(cell, ""))
		var branch := 0 if str(step["fork"]) == "a" else 1
		if base != "" and SimContent.tower_form(base, branch) == form:
			return [base, branch, cell]
	return ["", -1, Vector2i(-1, -1)]


## The waves of hollow12 that teach `check` before the first boss's (design 2.3: waves 1 to
## 5 each teach one check), the "early" waves LIFTS names.
static func early_waves(check: String) -> Array:
	var first_boss := 0
	var waves: Array = SimContent.WAVES["hollow12"]
	for i in waves.size():
		for group: Dictionary in waves[i]:
			if first_boss == 0 and SimContent.CREEPS[str(group["creep"])].get("boss", false):
				first_boss = i + 1
	return waves_of(check).filter(func(w: int) -> bool: return w < first_boss)


## The waves of hollow12 whose creeps bring `check` (Game.CREEPS' "check"; Swarm only in a
## group of Game.SWARM_PACK or more, as the wave list counts it; bosses aside).
static func waves_of(check: String) -> Array:
	var out := []
	var waves: Array = SimContent.WAVES["hollow12"]
	for i in waves.size():
		for group: Dictionary in waves[i]:
			var kind := str(group["creep"])
			if str(Game.CREEPS[kind]["check"]) != check or SimContent.CREEPS[kind].get("boss", false):
				continue
			if check == "swarm" and int(group["count"]) < Game.SWARM_PACK:
				continue
			if not out.has(i + 1):
				out.append(i + 1)
	return out


## [through, came]: wave `wave`'s creeps of `check` (bosses aside) that got through one
## `form` of `builder`'s alone on `cell` at `level`, and how many came.
static func through(scene: Node, builder: String, form: String, cell: Vector2i, level: String, wave: int, check: String) -> Array:
	var spec := plan_cell(builder, form)
	scene.start({"mode": "high_water", "seats": 1, "builders": [builder], "difficulty": level})
	scene.debug(SimTypes.DBG_GOLD, 1, 20000)
	scene.debug(SimTypes.DBG_LIVES, 0, 999)
	scene.cmd(1, "BUILD", SimContent.BUILDERS[builder]["towers"].find(spec[0]), cell.x, cell.y)
	scene.run_ticks(6)
	var t: SimRecords.SimTower = scene.tower_at(cell.x, cell.y)
	if t == null:
		return [-1, -1]
	scene.cmd(1, "FORK", t.id, int(spec[1]))
	scene.run_ticks(6)
	scene.debug(SimTypes.DBG_WAVE, 0, wave - 1)
	scene.debug(SimTypes.DBG_COUNTDOWN, 0, 1)
	var sim: SimMatch = scene.client(1)
	var limit: int = sim.tick + 30000
	scene.run_ticks(60)
	while sim.tick < limit and not (sim.hollows[0].phase == SimTypes.PHASE_PREP and sim.hollows[0].wave >= wave):
		scene.run_ticks(30)
	var came := 0
	for e: Dictionary in scene.events_of("SPAWN"):
		if _counts(str(e["kind"]), check):
			came += 1
	var got := 0
	for leak: Array in scene.leaks:
		if _counts(str(leak[1]), check):
			got += 1
	return [got, came]


static func _counts(kind: String, check: String) -> bool:
	return str(Game.CREEPS[kind]["check"]) == check and not SimContent.CREEPS[kind].get("boss", false)


## One row a patch branch: what one of it does alone on the cell its plan forks it on.
## "early" [wave, level, through, came] of its check's early waves at every level, "later"
## [wave, through, came] of each later wave at Normal (its easiest: Hard and Very Hard only
## add health); "measured" the LIFTS word that fits: "one" when it holds every early wave
## at every level and lets some of every later one through, "slow" when every wave of its
## check lets some through at Normal, "" when neither; and "said", Game.TOWERS' word.
static func rows(scene: Node) -> Array:
	var out := []
	for p: Array in patches():
		var builder: String = p[0]
		var form: String = p[1]
		var check: String = p[2]
		var cell: Vector2i = plan_cell(builder, form)[2]
		var early := []
		var holds_early := true
		var leaks_early := true
		for wave: int in early_waves(check):
			for level: String in LEVELS:
				var r := through(scene, builder, form, cell, level, wave, check)
				early.append([wave, level, r[0], r[1]])
				holds_early = holds_early and r[0] == 0 and r[1] > 0
				if level == "normal":
					leaks_early = leaks_early and r[0] > 0
		var later := []
		var leaks_later := true
		for wave: int in waves_of(check):
			if early_waves(check).has(wave):
				continue
			var r := through(scene, builder, form, cell, "normal", wave, check)
			later.append([wave, r[0], r[1]])
			leaks_later = leaks_later and r[0] > 0
		var measured := ""
		if holds_early and leaks_later:
			measured = "one"
		elif leaks_early and leaks_later:
			measured = "slow"
		var said := str(Game.TOWERS[form].get("lift", "one"))
		out.append(
			{
				"builder": builder, "form": form, "check": check, "cell": [cell.x, cell.y],
				"early": early, "later": later, "measured": measured, "said": said,
			}
		)
	return out


## The forms of `table` measured as `word`, in its order.
static func measured_as(table: Array, word: String) -> Array:
	var out := []
	for row: Dictionary in table:
		if str(row["measured"]) == word:
			out.append(row["form"])
	return out


## The rows whose word is not the one measured ("bend" is "one" measured on its plan's
## cell, held to its bend by bend_holds).
static func mismatches(table: Array) -> Array:
	var out := []
	for row: Dictionary in table:
		var said := str(row["said"])
		if said == "bend":
			said = "one"
		if said != str(row["measured"]):
			out.append("%s says %s, measured %s: %s" % [row["form"], row["said"], row["measured"], row])
	return out


## The Sky Toll's "only inside a bend": on (14, 8), inside the bend where the road comes
## along row 6, turns down and goes back along row 10, one takes all of wave 5's Duskmoths
## at every level; on (16, 8), outside it, with the road on one side only, it takes none.
## [[through, came] inside at each level, the same outside], and the road in each one's
## reach in millimetres.
static func bend_holds(scene: Node) -> Dictionary:
	var inside := []
	var outside := []
	for level: String in LEVELS:
		inside.append(through(scene, "bellfounder", "sky_toll", Vector2i(14, 8), level, 5, "winged"))
		outside.append(through(scene, "bellfounder", "sky_toll", Vector2i(16, 8), level, 5, "winged"))
	return {
		"inside": inside, "outside": outside,
		"road_inside_mm": road_in_reach(Vector2i(14, 8), "sky_toll"),
		"road_outside_mm": road_in_reach(Vector2i(16, 8), "sky_toll"),
	}


## How much road (millimetres) lies within the Bellfounder's `form` on `cell`'s reach.
static func road_in_reach(cell: Vector2i, form: String) -> int:
	var road := SimRoad.parse(SimContent.map_text("hollow"))
	var spec := plan_cell("bellfounder", form)
	var base: Dictionary = SimContent.TOWERS[spec[0]]
	var branch: Dictionary = base["a" if int(spec[1]) == 0 else "b"]
	var r := int(branch.get("range_mm", base["range_mm"]))
	var s := road.intervals(SimRoad.centre_mm(cell.x), SimRoad.centre_mm(cell.y), r)
	var total := 0
	for i in range(0, s.size(), 2):
		total += int((s[i + 1] - s[i]) / 1000)
	return total
