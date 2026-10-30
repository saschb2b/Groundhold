## The caretaker plays a seat nobody is at: an AWAY or LEFT player's, or a bot seat from
## tick 0 (the balance gates' bots are caretakers, design 4.4). It runs inside the
## simulation, so every client decides the same thing. It plays any Builder: it works down
## the Builder's plan (data/plans/<builder>.json, SimContent.plan_steps) with the seat's
## own gold, a step at a time as it can pay; it takes a step's alternative cells when
## another seat holds the first, skips steps nobody can do any more, takes a patching
## fork only while the team lacks the check it patches (else the deepening branch), and
## never sells. Its seat counts as Ready, so it never holds up a horn.
@warning_ignore_start("integer_division")
class_name Caretaker
extends RefCounted

## What decide() says about a step.
const SKIP := 0  # nothing to do here any more: move on
const WAIT := 1  # possible once the seat has the gold
const BUILD := 2  # [BUILD, slot, x, z]
const FORK := 3  # [FORK, tower id, branch]


## Called at the window's start and every 30 ticks for each caretaken seat.
static func think(m: SimMatch, s: SimRecords.SimSeat) -> void:
	var steps: Array = m.plans.get(s.builder, [])
	while s.plan_cursor < steps.size():
		var d := decide(m, s, steps[s.plan_cursor], s.gold)
		match d[0]:
			WAIT:
				return
			BUILD:
				m.execute_as(s.seat, SimTypes.CMD_BUILD, d[1], d[2], d[3])
			FORK:
				m.execute_as(s.seat, SimTypes.CMD_FORK, d[1], d[2])
		s.plan_cursor += 1


## What plan step `step` (a SimContent.plan_steps entry) asks of seat `s` now, given
## `gold` to spend and `claimed` cells (z * width + x) that orders still on their way
## will build on. Returns [SKIP], [WAIT], [BUILD, slot, x, z] or [FORK, tower, branch].
static func decide(
	m: SimMatch, s: SimRecords.SimSeat, step: PackedInt32Array, gold: int,
	claimed := PackedInt32Array()
) -> PackedInt32Array:
	var h := m.hollows[s.hollow]
	if step[0] == 0:
		var kind := SimContent.kit_tower(s.builder, step[1])
		if kind == "":
			return PackedInt32Array([SKIP])
		var cell := free_cell(m, h, step, claimed)
		if cell < 0:
			return PackedInt32Array([SKIP])
		if gold < int(SimContent.TOWERS[kind]["cost"]):
			return PackedInt32Array([WAIT])
		return PackedInt32Array([BUILD, step[1], cell % h.road.width, cell / h.road.width])
	var t := own_unforked(m, h, s, step)
	if t == null:
		return PackedInt32Array([SKIP])
	var branch := fork_branch(m, s, step)
	if not SimContent.has_branch(t.kind, branch):
		return PackedInt32Array([SKIP])
	if gold < int(SimContent.TOWERS[t.kind]["fork_cost"]):
		return PackedInt32Array([WAIT])
	return PackedInt32Array([FORK, t.id, branch])


## The step's cells in order of preference, as z * width + x: its cell, then its "alt"s.
static func cells(h: SimRecords.SimHollow, step: PackedInt32Array) -> PackedInt32Array:
	var out := PackedInt32Array()
	out.append(step[3] * h.road.width + step[2])
	var i := 5
	while i + 1 < step.size():
		out.append(step[i + 1] * h.road.width + step[i])
		i += 2
	return out


## The first of the step's cells a tower can go on now, or -1.
static func free_cell(
	m: SimMatch, h: SimRecords.SimHollow, step: PackedInt32Array, claimed: PackedInt32Array
) -> int:
	for cell in cells(h, step):
		var x := cell % h.road.width
		var z := cell / h.road.width
		if h.road.buildable(x, z) and h.occupied[cell] == 0 and not claimed.has(cell):
			return cell
	return -1


## The seat's unforked tower on the first of the step's cells that holds one, or null.
static func own_unforked(
	m: SimMatch, h: SimRecords.SimHollow, s: SimRecords.SimSeat, step: PackedInt32Array
) -> SimRecords.SimTower:
	for cell in cells(h, step):
		var t := m.tower(h.occupied[cell])
		if t != null and t.owner == s.seat and t.branch == -1:
			return t
	return null


## The branch a fork step takes for seat `s`: the step's own, unless it patches a check
## (step[4]) a Builder of the seat's team already covers; then the other one.
static func fork_branch(m: SimMatch, s: SimRecords.SimSeat, step: PackedInt32Array) -> int:
	var branch := step[1]
	if step.size() > 4 and step[4] >= 0 and team_covers(m, s.team, step[4]):
		return 1 - branch
	return branch


## Whether a Builder on team `team` is strong against check CHECK_IDS[check].
static func team_covers(m: SimMatch, team: int, check: int) -> bool:
	var builders := []
	for other in m.seats:
		if other.team == team:
			builders.append(other.builder)
	return SimContent.team_covers(builders).has(SimContent.CHECK_IDS[check])
