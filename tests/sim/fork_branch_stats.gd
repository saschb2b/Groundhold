## fork_branch_stats: every tower form of the Lamplighter's and the Lookout's kits, built
## and forked by command in a High Water match, stands with the numbers of design 3.4
## (as content.gd tunes them; the Lookout's reach includes Keen Sight's 0.4 tiles).
##   {"eval": "resource('res://tests/sim/fork_branch_stats.gd').problems(scene)", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

## Per form, the numbers the simulation resolves it to; a key not listed must be 0
## (or false, or the "first" aim).
const EXPECTED := {
	"arrow": {"dmg_c": 800, "cd_t": 30, "range_mm": 3200},
	"longbow_loft": {"dmg_c": 1600, "cd_t": 24, "range_mm": 3600},
	"skyward_loft": {"dmg_c": 1200, "cd_t": 27, "range_mm": 3600, "air": true},
	"cannon": {"dmg_c": 2000, "cd_t": 90, "range_mm": 3000, "splash_mm": 1100},
	"great_cannon": {"dmg_c": 4000, "cd_t": 78, "range_mm": 3300, "splash_mm": 1350},
	"iron_mortar": {"dmg_c": 4500, "cd_t": 84, "range_mm": 3300, "splash_mm": 600, "pierce_c": 400},
	"frost": {"dmg_c": 400, "cd_t": 54, "range_mm": 2800, "slow_pm": 450, "slow_t": 120, "team": 1},
	"deep_frost": {"dmg_c": 800, "cd_t": 54, "range_mm": 3200, "slow_pm": 600, "slow_t": 120, "team": 1},
	"rime_spire":
	{"dmg_c": 600, "cd_t": 54, "range_mm": 3200, "slow_pm": 400, "slow_t": 120, "team": 1, "air": true},
	"perch_ballista": {"dmg_c": 3200, "cd_t": 96, "range_mm": 4400, "air": true, "pierce_c": 300},
	"siege_perch": {"dmg_c": 6400, "cd_t": 90, "range_mm": 4400, "air": true, "pierce_c": 600},
	"pinning_ballista":
	{"dmg_c": 3600, "cd_t": 96, "range_mm": 4400, "air": true, "pierce_c": 300, "slow_pm": 500, "slow_t": 60},
	"hawk_roost": {"dmg_c": 1000, "cd_t": 42, "range_mm": 3800, "air": true, "aim": 1},
	"falcon_roost": {"dmg_c": 1800, "cd_t": 33, "range_mm": 3800, "air": true, "aim": 1},
	"kestrel_flock":
	{"dmg_c": 900, "cd_t": 42, "range_mm": 3800, "air": true, "aim": 1, "bounces": 2, "bounce_mm": 1200},
	"owls_eye":
	{"cd_t": 30, "range_mm": 4000, "air": true, "aim": 2, "team": 3, "mark_pm": 200, "marks": 1, "mark_t": 60},
	"owls_glare":
	{"cd_t": 30, "range_mm": 4000, "air": true, "aim": 2, "team": 3, "mark_pm": 350, "marks": 1, "mark_t": 60},
	"twin_gaze":
	{"cd_t": 30, "range_mm": 4000, "air": true, "aim": 2, "team": 3, "mark_pm": 200, "marks": 2, "mark_t": 60},
}
const KEYS := [
	"dmg_c", "cd_t", "range_mm", "air", "splash_mm", "pierce_c", "slow_pm", "slow_t", "aim",
	"bounces", "bounce_mm", "team", "mark_pm", "marks", "mark_t",
]
## Per seat, three cells per kit slot: one tower stays a base, one takes branch A, one B.
const CELLS := [
	[[[2, 3], [3, 3], [4, 3]], [[5, 3], [6, 3], [2, 4]], [[3, 4], [4, 4], [5, 4]]],
	[[[2, 7], [3, 7], [4, 7]], [[5, 7], [6, 7], [8, 7]], [[2, 9], [3, 9], [4, 9]]],
]


## Builds every form for a Lamplighter (seat 1) and a Lookout (seat 2) on `harness` and
## returns every number that differs from EXPECTED, and every form that is missing.
static func problems(harness: Node) -> Array:
	var out := []
	harness.call("start", {"mode": "high_water", "seats": 2, "builders": ["lamplighter", "lookout"]})
	var seen := {}
	for seat in [1, 2]:
		harness.call("debug", SimTypes.DBG_GOLD, seat, 5000)
	for seat in [1, 2]:
		var cells: Array = CELLS[seat - 1]
		for slot in 3:
			for cell: Array in cells[slot]:
				harness.call("cmd", seat, "BUILD", slot, int(cell[0]), int(cell[1]))
		harness.call("run_ticks", 6)
		for slot in 3:
			for branch in [0, 1]:
				var cell: Array = cells[slot][branch + 1]
				var t: SimRecords.SimTower = harness.call("tower_at", int(cell[0]), int(cell[1]))
				if t == null:
					out.append("seat %d has no tower at %s" % [seat, cell])
					continue
				harness.call("cmd", seat, "FORK", t.id, branch)
		harness.call("run_ticks", 6)
	var sim: SimMatch = harness.call("client", 1)
	for t in sim.towers:
		var form := SimContent.tower_form(t.kind, t.branch)
		seen[form] = true
		if not EXPECTED.has(form):
			out.append("%s is not in the expected table" % form)
			continue
		var want: Dictionary = EXPECTED[form]
		for key: String in KEYS:
			var have: Variant = t.get(key)
			var expected: Variant = want.get(key, false if key == "air" else 0)
			if have != expected:
				out.append("%s (seat %d) %s is %s, not %s" % [form, t.owner, key, have, expected])
	for form: String in EXPECTED:
		if not seen.has(form):
			out.append("no %s was built or forked" % form)
	return out
