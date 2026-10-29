## The caretaker plays a seat nobody is at: an AWAY or LEFT player's, or a bot seat from
## tick 0. It runs inside the simulation, so every client decides the same thing. M1's
## caretaker works down its Builder's plan (data/plans/<builder>.json) with the seat's own
## gold, a step at a time as it can pay, skips steps another seat made impossible, and
## never sells. Its seat counts as Ready, so it never holds up a horn.
class_name Caretaker
extends RefCounted


## Called at the window's start and every 30 ticks for each caretaken seat.
static func think(m: SimMatch, s: SimRecords.SimSeat) -> void:
	var steps: Array = m.plans.get(s.builder, [])
	var h := m.hollows[s.hollow]
	while s.plan_cursor < steps.size():
		var step: PackedInt32Array = steps[s.plan_cursor]
		var x := step[2]
		var z := step[3]
		var here := m.tower_at(h.id, x, z)
		if step[0] == 0:
			var kind := SimContent.kit_tower(s.builder, step[1])
			if kind == "" or here != null or not h.road.buildable(x, z):
				s.plan_cursor += 1
				continue
			if s.gold < int(SimContent.TOWERS[kind]["cost"]):
				return
			m.execute_as(s.seat, SimTypes.CMD_BUILD, step[1], x, z)
		else:
			if here == null or here.owner != s.seat or here.branch != -1:
				s.plan_cursor += 1
				continue
			if not SimContent.has_branch(here.kind, step[1]):
				s.plan_cursor += 1
				continue
			if s.gold < int(SimContent.TOWERS[here.kind]["fork_cost"]):
				return
			m.execute_as(s.seat, SimTypes.CMD_FORK, here.id, step[1])
		s.plan_cursor += 1
