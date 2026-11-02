## The fork bench (M8, contract-m8 §6, design 3.8): what each tower form does at the job
## its fork gives it, measured in bare simulations. High Water at Normal, one seat of the
## form's Builder with its perk (Keen Sight's reach and Bronze Hand's pierce count), the form
## built and forked on the bench cell (8, 11), between the two lower stretches of road; both
## branches of a pair stand on the same cell against the same creeps. What a form does is read
## from the HIT events as health removed: each hit's damage less the overkill of the hit that
## killed (a creep's hits summed and capped at its health), so a big hit on a small creep
## counts what it took, not what it rolled.
##
## The measures (design 3.8), each an int:
##   single:<creep>   health removed per second, in hundredths, from one creep at wave 12's
##                    health held still on the road where it runs nearest the bench cell (in
##                    every form's reach), a fresh one the tick after it dies, over 60 s; at
##                    one seat's Normal health, and as single:<creep>@<pm> at every other
##                    health the game plays (health_levels()): how many hits a kill takes, so
##                    what the killing hit wastes, moves with the health
##   crowd:<creep>    per mille of a line's health removed as 12 creeps of CROWD_HP_PM of wave
##                    7's health, one every 24 ticks (wave 7's interval), walk the road through
##                    the reach: at wave 7's own health a lone Great Cannon removed all of the
##                    line (1000 per mille) and every crowd form measured alike
##   control:<creep>  the hundredths of a second each creep of a line of 12 (as crowd's)
##                    spends in the form's reach beyond its unslowed time over the same road:
##                    the line has CONTROL_HP_PM of its health, so no creep dies and holding,
##                    not killing, is measured. A crowd and a control are taken on the bench
##                    cell, and as crowd:<creep>@<x>,<z> on every cell the base's Builder's plan
##                    builds it on (cells()): a bend reaches more road than a straight
##   lift:<lane>      per mille more health a fixed battery of a Lamplighter's (another seat's)
##                    towers removes on a lane because the form stands (the lane with it, less
##                    the lane without it, over the lane without it): "boss" a held Bristlesow
##                    at wave 12's health over 60 s and "line" 12 Thornbacks of CONTROL_HP_PM of
##                    wave 12's health, one every 60 ticks, before BATTERY (three Arrow Towers
##                    and a Cannon Tower around the bench cell); a hum's "tight" (three Arrow
##                    Towers within 2.2 of it) and "wide" (six, three of them between 2.2 and
##                    3.0), on 12 Gourdlings as tough, one every 24 ticks. A line nobody can
##                    kill measures the battery's extra damage; a line it could kill would
##                    measure nothing once it did
## Each job's measures are JOB_MEASURES', each with its variants (job_keys()): an armour job
## both single:thornback (armour 4) and single:bristlesow (6), the Sky Toll's (fliers, damage
## and slow) a flier's damage and its hold on a line of fliers (the Great Toll reaches none,
## so the pair is apart by rule 1 either way, and the slow is held to rule 3's ceiling). A
## pulse's damage to a flock (crowd:duskmoth) is not one of them: on its bends the Sky Toll's
## does what the Royal Apiary's does, the Bellfounder's one tower for the sky (design 3.8).
## Every bench match lays one seat's health over every seat count (hp_by_seats_pm 1000, so
## the lift lanes' second seat changes no creep) and LIVES lives (no line ends the match).
##
## A pair is apart (the fork_pairs_apart gate, design 3.8's acceptance) when
##   1. on each measure of its own job (JOBS, JOB_MEASURES), at every health and on every
##      cell, each branch does at least JOB_MARGIN_PM more than its sibling, or its sibling
##      cannot do it at all (0);
##   2. no branch does BOTH_JOBS_PM more than its sibling on every measure of both jobs;
##   3. a patch branch (BUILDERS "patches") does at most PATCH_CEILING_PM of the best form,
##      base or branch, of a Builder strong against the check it patches, on each measure
##      of its job at the same health or on the same cell.
## A FORK_BENCH line gives each measure at the bench's health and cell, the range of its
## variants, each branch's least lead at its own job and a patch's largest share.
##   {"eval": "resource('res://tests/sim/fork_bench.gd')", "as": "Bench"}
##   {"eval": "Bench.lines()", "as": "bench"}
##   {"eval": "Bench.problems()", "as": "found"}
##   {"assert": "found == []"}
@warning_ignore_start("integer_division")
extends RefCounted

const CELL := [8, 11]
## Design 3.8's acceptance (core-loop §3.8, contract-m8 §6; tunable, the design's first).
const JOB_MARGIN_PM := 250
const BOTH_JOBS_PM := 100
const PATCH_CEILING_PM := 900
const SINGLE_T := 3600
const LINE := 12
const LINE_LIMIT_T := 9000
const CONTROL_HP_PM := 50000
const CROWD_HP_PM := 3000
const LIVES := 1000
## The battery of the lift lanes: a Lamplighter's (seat 2) [slot, x, z] around the bench cell.
const BATTERY := [[0, 7, 11], [0, 9, 11], [0, 7, 12], [1, 8, 12]]
## A hum's batteries: three Arrow Towers within 2.2 of the bench cell, and those and three
## more between 2.2 and 3.0 (2.24, 2.24 and 2.83 away).
const TIGHT := [[0, 7, 11], [0, 9, 11], [0, 8, 12]]
const WIDE := [[0, 7, 11], [0, 9, 11], [0, 8, 12], [0, 6, 12], [0, 10, 12], [0, 10, 9]]

## Each base's branches' jobs, A's then B's (design 3.8's table).
const JOBS := {
	"arrow": ["ground", "flier"],
	"cannon": ["crowd", "armour"],
	"frost": ["hold_ground", "hold_flier"],
	"perch_ballista": ["armour", "hold_ground"],
	"hawk_roost": ["flier", "crowd"],
	"owls_eye": ["lift_boss", "lift_pack"],
	"clapper_tower": ["armour", "crowd"],
	"toll_tower": ["hold_ground", "sky"],
	"chime_post": ["lift_boss", "lift_pack"],
	"clay_hive": ["crowd", "hold_ground"],
	"apiary": ["flier", "armour"],
	"hive_hum": ["lift_tight", "lift_wide"],
}
## What each job is measured by: a branch must hold its margin on every one.
const JOB_MEASURES := {
	"ground": ["single:gourdling"],
	"flier": ["single:duskmoth"],
	"armour": ["single:thornback", "single:bristlesow"],
	"crowd": ["crowd:gourdling"],
	"hold_ground": ["control:scuttler"],
	"hold_flier": ["control:duskmoth"],
	"sky": ["single:duskmoth", "control:duskmoth"],
	"lift_boss": ["lift:boss"],
	"lift_pack": ["lift:line"],
	"lift_tight": ["lift:tight"],
	"lift_wide": ["lift:wide"],
}
## How each measure reads in a FORK_BENCH line.
const UNITS := {"single": "/s", "crowd": " pm", "control": " s", "lift": " pm"}

static var _cache := {}


## A form's measure `what` ("single:thornback", "crowd:gourdling", "control:scuttler",
## "lift:boss", ...), worked out once a process.
static func measure(form: String, what: String) -> int:
	var key := form + "|" + what
	if not _cache.has(key):
		_cache[key] = _measure(form, what)
	return int(_cache[key])


## Forgets every measure (after the tables changed in a balance pass's process).
static func forget() -> void:
	_cache.clear()


## Every fork pair, in BUILDERS and kit order: {"builder", "base", "forms" [A, B], "jobs" [A's,
## B's], "on" {form: {measure: value}} (both forms on both jobs' measures), "gold" (a branch's
## price, base and fork), "patch" {form: check}, "problems" [...]}.
static func pairs() -> Array:
	var out := []
	for builder: String in SimContent.BUILDER_IDS:
		var kit: Array = SimContent.BUILDERS[builder]["towers"]
		for base: String in kit:
			out.append(_pair(builder, base))
	return out


## Every pair's FORK_BENCH line, printed.
static func lines() -> Array:
	var out := table()
	for line: String in out:
		print(line)
	return out


## Every pair's FORK_BENCH line, for the watches.
static func table() -> Array:
	var out := []
	for p: Dictionary in pairs():
		out.append("FORK_BENCH " + _line(p))
	return out


## Whatever keeps a pair from being apart (rules 1 to 3 above), [] when every pair is.
static func problems() -> Array:
	var out := []
	for p: Dictionary in pairs():
		out.append_array(p["problems"])
	return out


static func _pair(builder: String, base: String) -> Dictionary:
	var a := SimContent.tower_form(base, 0)
	var b := SimContent.tower_form(base, 1)
	var jobs: Array = JOBS[base]
	var on := {a: {}, b: {}}
	var keys := []
	for job: String in jobs:
		for key: String in job_keys(base, job):
			if not keys.has(key):
				keys.append(key)
	for form: String in [a, b]:
		for key: String in keys:
			on[form][key] = measure(form, key)
	var p := {
		"builder": builder,
		"base": base,
		"forms": [a, b],
		"jobs": jobs,
		"on": on,
		"gold": int(SimContent.TOWERS[base]["cost"]) + int(SimContent.TOWERS[base]["fork_cost"]),
		"patch": {},
		"problems": [],
	}
	var problems: Array = p["problems"]
	for i in 2:
		var mine: String = [a, b][i]
		var sib: String = [a, b][1 - i]
		var own_job: String = jobs[i]
		for key: String in job_keys(base, own_job):
			var v := int(on[mine][key])
			var w := int(on[sib][key])
			if v <= 0:
				problems.append("%s does nothing at its own job (%s %s)" % [mine, own_job, _named(key)])
			elif w > 0 and v * 1000 < w * (1000 + JOB_MARGIN_PM):
				problems.append(
					"%s is not %d%% ahead of %s at %s (%s): %s against %s"
					% [mine, JOB_MARGIN_PM / 10, sib, own_job, _named(key), _shown(key, v), _shown(key, w)]
				)
		var ahead := true
		for key: String in keys:
			if int(on[mine][key]) * 1000 < int(on[sib][key]) * (1000 + BOTH_JOBS_PM):
				ahead = false
		if ahead:
			problems.append("%s is %d%% ahead of %s on both jobs" % [mine, BOTH_JOBS_PM / 10, sib])
		var check := SimContent.branch_helps(builder, mine)
		if check != "":
			p["patch"][mine] = check
			for key: String in job_keys(base, own_job):
				var best := _best_strong(check, key)
				var v := int(on[mine][key])
				if v * 1000 > int(best[1]) * PATCH_CEILING_PM:
					problems.append(
						"%s patches %s past %d%% of %s (%s): %s against %s"
						% [
							mine, check, PATCH_CEILING_PM / 10, best[0], _named(key), _shown(key, v),
							_shown(key, int(best[1]))
						]
					)
	return p


## Every measure a pair of `base`'s branches is held to at `job`: each of JOB_MEASURES', a
## `single` at every health level (health_levels()) and a `crowd` or `control` on every cell of
## cells(base), as keys measure() takes ("single:thornback@1100", "crowd:gourdling@12,8";
## the bench's own health and cell bare).
static func job_keys(base: String, job: String) -> Array:
	var out := []
	for what: String in JOB_MEASURES[job]:
		out.append_array(variants(base, what))
	return out


## `what` and its variants for a pair of `base`'s branches (job_keys()).
static func variants(base: String, what: String) -> Array:
	var out := [what]
	var kind := what.get_slice(":", 0)
	if kind == "single":
		for pm: int in health_levels():
			if pm != 1000:
				out.append("%s@%d" % [what, pm])
	elif kind == "crowd" or kind == "control":
		for cell: Array in cells(base):
			if cell != CELL:
				out.append("%s@%d,%d" % [what, int(cell[0]), int(cell[1])])
	return out


## The creep health levels the game plays, per mille of one seat's at Normal: High Water's
## one to four seats (hp_by_seats_pm) at every level (DIFFICULTIES' hp_pm), in order:
## 1000, 1100, 1150, 2000, 2200, 2300, 2650, 2915, 3047, 3400, 3740 and 3910. A `single`
## is measured at each, since how many hits a kill takes, and so what the killing hit
## wastes, moves with the health: a pair is apart only where it is apart at every one.
static func health_levels() -> Array:
	var out := []
	for seats_pm: int in SimContent.RULES["high_water"]["hp_by_seats_pm"]:
		for level: String in SimContent.DIFFICULTY_IDS:
			var pm := seats_pm * int(SimContent.DIFFICULTIES[level].get("hp_pm", 1000)) / 1000
			if not out.has(pm):
				out.append(pm)
	out.sort()
	return out


## The cells a `crowd` or `control` measure of `base`'s branches is taken on: the bench
## cell, then every cell its Builder's plan builds it on (every mode's steps, main cells),
## in the plan's order.
static func cells(base: String) -> Array:
	var out := [CELL]
	var file := SimContent.plan_file(str(SimContent.TOWERS[base]["builder"]))
	var blocks := [file.get("steps", [])]
	for mode: String in SimContent.RULES:
		if file.get(mode) is Dictionary:
			blocks.append((file[mode] as Dictionary).get("steps", []))
	for steps: Array in blocks:
		for step: Dictionary in steps:
			if str(step.get("build", "")) != base:
				continue
			var cell := [int(step["cell"][0]), int(step["cell"][1])]
			if not out.has(cell):
				out.append(cell)
	return out


## The best form, base or branch, of every Builder strong against `check` at `key`:
## [form, value].
static func _best_strong(check: String, key: String) -> Array:
	var best := ["", 0]
	for builder: String in SimContent.BUILDER_IDS:
		if not SimContent.covers(builder, check):
			continue
		for base: String in SimContent.BUILDERS[builder]["towers"]:
			for branch in [-1, 0, 1]:
				var form := SimContent.tower_form(base, branch)
				var v := measure(form, key)
				if v > int(best[1]):
					best = [form, v]
	return best


## A FORK_BENCH line: per branch, each measure at the bench's health and cell, and where it
## has variants their range ("single:thornback 33.0/s (32.0/s to 33.6/s at 6 healths)").
static func _line(p: Dictionary) -> String:
	var parts := []
	for i in 2:
		var form: String = p["forms"][i]
		var bits := []
		for job: String in p["jobs"]:
			for what: String in JOB_MEASURES[job]:
				var keys := variants(str(p["base"]), what)
				var bit := "%s %s" % [what, _shown(what, int(p["on"][form][what]))]
				if keys.size() > 1:
					var lo := int(p["on"][form][what])
					var hi := lo
					for key: String in keys:
						lo = mini(lo, int(p["on"][form][key]))
						hi = maxi(hi, int(p["on"][form][key]))
					var over := "healths" if what.begins_with("single") else "cells"
					bit += " (%s to %s at %d %s)" % [_shown(what, lo), _shown(what, hi), keys.size(), over]
				bits.append(bit)
		var tag := " (patch %s)" % p["patch"][form] if p["patch"].has(form) else ""
		parts.append("%s [%s]%s: %s%s" % [form, p["jobs"][i], tag, ", ".join(bits), _margins(p, i)])
	var problems: Array = p["problems"]
	var verdict := "apart" if problems.is_empty() else "NOT APART: " + "; ".join(problems)
	return (
		"%s %s, %d gold a branch | %s | %s"
		% [p["builder"], p["base"], p["gold"], " | ".join(parts), verdict]
	)


## Branch i's margins at its own job, for the line: its least lead over its sibling on any
## of the job's measures ("; lead +32% at worst, 33.9/s against 25.6/s, single:thornback at
## 1100 per mille health"; none where the sibling cannot do the job at all) and, for a
## patch, its largest share of a strong Builder's best ("; 70% of a strong Builder's best at
## most, ... against great_clapper's ...").
static func _margins(p: Dictionary, i: int) -> String:
	var mine: String = p["forms"][i]
	var sib: String = p["forms"][1 - i]
	var keys := job_keys(str(p["base"]), str(p["jobs"][i]))
	var out := ""
	var worst := -1
	var worst_key := ""
	for key: String in keys:
		var v := int(p["on"][mine][key])
		var w := int(p["on"][sib][key])
		if w > 0 and v > 0:
			var lead := v * 1000 / w - 1000
			if worst_key == "" or lead < worst:
				worst = lead
				worst_key = key
	if worst_key != "":
		out += (
			"; lead %+d%% at worst, %s against %s, %s"
			% [
				worst / 10, _shown(worst_key, int(p["on"][mine][worst_key])),
				_shown(worst_key, int(p["on"][sib][worst_key])), _named(worst_key)
			]
		)
	if p["patch"].has(mine):
		var most := -1
		var most_key := ""
		for key: String in keys:
			var best := _best_strong(str(p["patch"][mine]), key)
			if int(best[1]) > 0:
				var share := int(p["on"][mine][key]) * 1000 / int(best[1])
				if share > most:
					most = share
					most_key = key
		if most_key != "":
			var best := _best_strong(str(p["patch"][mine]), most_key)
			out += (
				"; %d%% of a strong Builder's best at most, %s against %s's %s, %s"
				% [
					most / 10, _shown(most_key, int(p["on"][mine][most_key])), best[0],
					_shown(most_key, int(best[1])), _named(most_key)
				]
			)
	return out


## A measure key as a problem names it: "single:thornback at 1100 per mille health",
## "crowd:gourdling on (12, 8)".
static func _named(key: String) -> String:
	if not key.contains("@"):
		return key
	var what := key.get_slice("@", 0)
	var at := key.get_slice("@", 1)
	if at.contains(","):
		return "%s on (%s)" % [what, at.replace(",", ", ")]
	return "%s at %s per mille health" % [what, at]


static func _shown(what: String, v: int) -> String:
	var kind := what.get_slice(":", 0)
	if kind == "single":
		return "%.1f%s" % [v / 100.0, UNITS[kind]]
	if kind == "control":
		return "%.2f%s" % [v / 100.0, UNITS[kind]]
	return "%d%s" % [v, UNITS[kind]]


# ── The simulations ──


static func _measure(form: String, key: String) -> int:
	var what := key.get_slice("@", 0)
	var at := key.get_slice("@", 1) if key.contains("@") else ""
	var kind := what.get_slice(":", 0)
	var arg := what.get_slice(":", 1)
	var stats := _stats(form)
	if stats.is_empty():
		return 0
	var winged := bool(SimContent.CREEPS.get(arg, {}).get("winged", false))
	var hits := int(stats.get("dmg_c", 0)) > 0
	match kind:
		"single":
			if not hits or (winged and not bool(stats.get("air", false))):
				return 0
			return _single(form, arg, 1000 if at == "" else int(at))
		"crowd":
			if not hits or (winged and not bool(stats.get("air", false))):
				return 0
			return _crowd(form, arg, _cell_of(at))
		"control":
			var slows := int(stats.get("slow_pm", 0)) > 0
			var holds := slows or int(stats.get("stun_t", 0)) > 0
			if winged:
				holds = bool(stats.get("air", false)) and (slows or int(stats.get("air_slow_pm", 0)) > 0)
			if not holds:
				return 0
			return _control(form, arg, _cell_of(at))
		"lift":
			if str(stats.get("team", "")) == "" or str(stats.get("team", "")) == "slow":
				return 0
			return _lift(form, arg)
	push_error("fork_bench: no measure %s" % key)
	return 0


## The cell a variant names ("12,8"), the bench cell for none.
static func _cell_of(at: String) -> Array:
	return CELL if at == "" else [int(at.get_slice(",", 0)), int(at.get_slice(",", 1))]


## The table of a form: its base's numbers with its branch's laid over them, {} for no form.
static func _stats(form: String) -> Dictionary:
	var at := _where(form)
	return {} if at.is_empty() else SimContent.tower_stats(str(at[0]), int(at[1]))


## [base, branch, builder] of a form (branch -1 for a base), [] for none.
static func _where(form: String) -> Array:
	for base: String in SimContent.TOWERS:
		for branch in [-1, 0, 1]:
			if SimContent.tower_form(base, branch) == form:
				return [base, branch, str(SimContent.TOWERS[base]["builder"])]
	return []


## A bench match: seat 1 the form's Builder (and seat 2 a Lamplighter with `battery` built
## for a lift lane), the form standing on the bench cell unless `without`, the hollow's wave
## at `wave` in a window that never runs out. `over` lays keys over the rules.
static func _bench(
	form: String, wave: int, battery := [], without := false, over := {}, cell := CELL
) -> SimMatch:
	var at := _where(form)
	var rules := SimContent.rules("high_water")
	rules["hp_by_seats_pm"] = [1000, 1000, 1000, 1000]
	rules["lives"] = LIVES
	rules.merge(over, true)
	var seats := [{"team": 0, "builder": str(at[2]), "caretaker": false}]
	if not battery.is_empty():
		seats.append({"team": 0, "builder": "lamplighter", "caretaker": false})
	var sim := SimMatch.new(rules, seats, 1)
	for s in sim.seats:
		sim.debug(SimTypes.DBG_GOLD, s.seat, 100000)
	if not without:
		var base := str(at[0])
		var slot := (SimContent.BUILDERS[str(at[2])]["towers"] as Array).find(base)
		sim.execute_as(1, SimTypes.CMD_BUILD, slot, int(cell[0]), int(cell[1]))
		var t := sim.tower_at(0, int(cell[0]), int(cell[1]))
		if t == null:
			push_error("fork_bench: %s did not stand on %s" % [form, str(cell)])
		elif int(at[1]) >= 0:
			sim.execute_as(1, SimTypes.CMD_FORK, t.id, int(at[1]))
	for spot: Array in battery:
		sim.execute_as(2, SimTypes.CMD_BUILD, int(spot[0]), int(spot[1]), int(spot[2]))
	sim.debug(SimTypes.DBG_WAVE, 0, wave)
	sim.debug(SimTypes.DBG_COUNTDOWN, 0, 100000000)
	sim.drain_events()
	return sim


## Where the road runs nearest the bench cell, as a road distance: a held creep stands there.
static func _held_at(sim: SimMatch) -> int:
	var road := sim.hollows[0].road
	var cx := SimRoad.centre_mm(int(CELL[0]))
	var cz := SimRoad.centre_mm(int(CELL[1]))
	var best := 0
	var best_d := -1
	for dist in range(0, road.length_um + 1, 10000):
		var dx := road.x_at(dist) - cx
		var dz := road.z_at(dist) - cz
		if best_d < 0 or dx * dx + dz * dz < best_d:
			best_d = dx * dx + dz * dz
			best = dist
	return best


## Where a line sets out: two tiles before the first stretch of road any tower on the board
## reaches (the creeps walk the rest of the road from there, as from the Welling).
static func _line_from(sim: SimMatch) -> int:
	var first := sim.hollows[0].road.length_um
	for t in sim.towers:
		if t.intervals.size() > 0:
			first = mini(first, int(t.intervals[0]))
	return maxi(0, first - 2000000)


static func _spawn(sim: SimMatch, creep: String, dist: int, held: bool) -> SimRecords.SimCreep:
	sim.debug(SimTypes.DBG_SPAWN, 0, SimContent.CREEP_IDS.find(creep))
	var c := sim.creep(sim.next_id - 1)
	c.dist_um = dist
	if held:
		c.speed_um_t = 0
	return c


## Adds the damage `seat`'s hits in `events` dealt to `dealt` (hundredths, per creep id).
static func _count(events: Array, seat: int, dealt: Dictionary) -> void:
	for e: Dictionary in events:
		if int(e["type"]) == SimTypes.EV_HIT and int(e["seat"]) == seat:
			dealt[int(e["creep"])] = int(dealt.get(int(e["creep"]), 0)) + int(e["dmg"])


## Health removed (hundredths): each creep's damage dealt, capped at its health `hp` (per
## creep id), so the killing hit's overkill does not count.
static func _removed(dealt: Dictionary, hp: Dictionary) -> int:
	var total := 0
	for id: int in hp:
		total += mini(int(dealt.get(id, 0)), int(hp[id]))
	return total


## A held creep, a fresh one the tick after each dies, for SINGLE_T ticks: what `seat`'s
## hits removed, in hundredths.
static func _held_run(sim: SimMatch, creep: String, seat: int) -> int:
	var at := _held_at(sim)
	var dealt := {}
	var hp := {}
	var c := _spawn(sim, creep, at, true)
	hp[c.id] = c.max_hp_c
	for i in SINGLE_T:
		sim.step()
		_count(sim.drain_events(), seat, dealt)
		if not c.alive:
			c = _spawn(sim, creep, at, true)
			hp[c.id] = c.max_hp_c
	return _removed(dealt, hp)


## A line of LINE creeps of `creep`, one every `every` ticks from _line_from, walked until none
## is left: [what `seat`'s hits removed, the line's health], in hundredths. With `reach`
## (a tower's road stretches), `held` gets each creep's ticks in that reach beyond its
## unslowed time over the same road, summed.
static func _line_run(
	sim: SimMatch, creep: String, every: int, seat: int, reach := PackedInt64Array(), held := [0]
) -> Array:
	var from := _line_from(sim)
	var dealt := {}
	var hp := {}
	var walking: Array[SimRecords.SimCreep] = []
	var extra_um := {}
	var sent := 0
	var t := 0
	while t < LINE_LIMIT_T:
		if sent < LINE and t == sent * every:
			var c := _spawn(sim, creep, from, false)
			hp[c.id] = c.max_hp_c
			walking.append(c)
			extra_um[c.id] = 0
			sent += 1
		var before := {}
		for c in walking:
			before[c.id] = c.dist_um
		sim.step()
		_count(sim.drain_events(), seat, dealt)
		for c in walking:
			var was := int(before[c.id])
			if not reach.is_empty() and SimRoad.covers(reach, was):
				extra_um[c.id] = int(extra_um[c.id]) + c.speed_um_t - (c.dist_um - was)
		var left: Array[SimRecords.SimCreep] = []
		for c in walking:
			if c.alive and sim.creep(c.id) != null:
				left.append(c)
		walking = left
		t += 1
		if sent >= LINE and walking.is_empty():
			break
	if not reach.is_empty():
		var total_t := 0
		for id: int in extra_um:
			var speed := int(SimContent.CREEPS[creep]["speed_um_t"])
			total_t += int(extra_um[id]) / speed
		held[0] = total_t
	var health := 0
	for id: int in hp:
		health += int(hp[id])
	return [_removed(dealt, hp), health]


## Rules keys that give every creep `pm` per mille of one seat's health.
static func _health(pm: int) -> Dictionary:
	return {"hp_by_seats_pm": [pm, pm, pm, pm]}


static func _single(form: String, creep: String, health_pm: int) -> int:
	var sim := _bench(form, 12, [], false, _health(health_pm))
	return _held_run(sim, creep, 1) * 60 / SINGLE_T


static func _crowd(form: String, creep: String, cell: Array) -> int:
	var sim := _bench(form, 7, [], false, _health(CROWD_HP_PM), cell)
	var run := _line_run(sim, creep, 24, 1)
	return int(run[0]) * 1000 / maxi(1, int(run[1]))


static func _control(form: String, creep: String, cell: Array) -> int:
	var sim := _bench(form, 7, [], false, _health(CONTROL_HP_PM), cell)
	var t := sim.tower_at(0, int(cell[0]), int(cell[1]))
	var held := [0]
	_line_run(sim, creep, 24, 1, t.intervals, held)
	return int(held[0]) * 100 / 60 / LINE


static func _lift(form: String, lane: String) -> int:
	var battery: Array = TIGHT if lane == "tight" else (WIDE if lane == "wide" else BATTERY)
	var runs := []
	for without in [false, true]:
		var sim := _bench(form, 12, battery, without, {} if lane == "boss" else _health(CONTROL_HP_PM))
		match lane:
			"boss":
				runs.append(_held_run(sim, "bristlesow", 2))
			"line":
				runs.append(int(_line_run(sim, "thornback", 60, 2)[0]))
			_:
				runs.append(int(_line_run(sim, "gourdling", 24, 2)[0]))
	return (int(runs[0]) - int(runs[1])) * 1000 / maxi(1, int(runs[1]))
