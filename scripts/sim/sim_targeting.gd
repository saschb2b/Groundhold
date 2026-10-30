## Whom a tower picks (design 3.2, "Targeting"): ties always go to the lower creep id,
## which walking the match's creeps in id order with strict comparisons gives. A tower
## without `air` never sees a winged creep (SimMatch.in_range).
##   first    the creep furthest along the road; it keeps it until it dies or leaves
##            range (every tower but those below)
##   winged   winged creeps first, furthest along; then as "first" (the Hawk Roost); a
##            ground target is dropped as soon as a winged one comes into reach
##   most_hp  the highest current health (the Owl's Eye; SimEffects marks with it)
## Bounces go to the nearest creep to the one struck, by squared millimetres.
@warning_ignore_start("integer_division")
class_name SimTargeting
extends RefCounted

const AIM_FIRST := 0
const AIM_WINGED := 1
const AIM_MOST_HP := 2
const AIM_NAMES := ["first", "winged", "most_hp"]


## The AIM_* code for a TOWERS "aim" value; "first" for none or an unknown one.
static func aim_code(name: String) -> int:
	return maxi(0, AIM_NAMES.find(name))


## Stage 5's choice for a firing tower: the target it keeps or a new one, 0 for none.
static func target_for(m: SimMatch, t: SimRecords.SimTower) -> int:
	if t.target != 0:
		var held := m.creep(t.target)
		if held == null or not m.in_range(t, held):
			t.target = 0
		elif t.aim == AIM_WINGED and not held.winged:
			var flier := furthest(m, t, true)
			if flier != 0:
				return flier
	if t.target != 0:
		return t.target
	return pick(m, t)


## A fresh pick by the tower's aim.
static func pick(m: SimMatch, t: SimRecords.SimTower) -> int:
	match t.aim:
		AIM_WINGED:
			var flier := furthest(m, t, true)
			return flier if flier != 0 else furthest(m, t, false)
		AIM_MOST_HP:
			var best := strongest(m, t, 1, PackedInt32Array())
			return best[0] if not best.is_empty() else 0
	return furthest(m, t, false)


## The creep furthest along the road in the tower's reach (winged ones only, when
## `winged_only`), or 0.
static func furthest(m: SimMatch, t: SimRecords.SimTower, winged_only: bool) -> int:
	var best: SimRecords.SimCreep = null
	for c in m.creeps:
		if winged_only and not c.winged:
			continue
		if m.in_range(t, c) and (best == null or c.dist_um > best.dist_um):
			best = c
	return best.id if best else 0


## Up to `count` creeps in the tower's reach with the highest current health, highest
## first, ties to the lower id; none of `skip`.
static func strongest(
	m: SimMatch, t: SimRecords.SimTower, count: int, skip: PackedInt32Array
) -> PackedInt32Array:
	var out := PackedInt32Array()
	var taken := skip.duplicate()
	for k in count:
		var best: SimRecords.SimCreep = null
		for c in m.creeps:
			if taken.has(c.id) or not m.in_range(t, c):
				continue
			if best == null or c.hp_c > best.hp_c:
				best = c
		if best == null:
			break
		out.append(best.id)
		taken.append(best.id)
	return out


## Where a bounce goes from creep `from`: the nearest live creep on its hollow within
## `reach_mm` that the chain has not struck yet (ground or winged, as `air` allows), or 0.
static func bounce_target(
	m: SimMatch, from: SimRecords.SimCreep, reach_mm: int, air: bool, struck: PackedInt32Array
) -> int:
	var road := m.hollows[from.hollow].road
	var fx := road.x_at(from.dist_um)
	var fz := road.z_at(from.dist_um)
	var best := 0
	var best_d2 := reach_mm * reach_mm + 1
	for c in m.creeps:
		if c.hollow != from.hollow or c.id == from.id or struck.has(c.id):
			continue
		if c.winged and not air:
			continue
		var dx := road.x_at(c.dist_um) - fx
		var dz := road.z_at(c.dist_um) - fz
		var d2 := dx * dx + dz * dz
		if d2 < best_d2:
			best_d2 = d2
			best = c.id
	return best
