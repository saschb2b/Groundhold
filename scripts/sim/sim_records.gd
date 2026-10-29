## The records a SimMatch holds (design 6.4). Plain RefCounted data in integer units;
## the match keeps each kind in an Array ordered by id and never iterates a Dictionary.
## Views hold references to these records and read them; they never write them.
class_name SimRecords
extends RefCounted


class SimTeam:
	extends RefCounted
	var id := 0
	var lives := 0
	var kills := 0
	## Hollows this team defends (one in High Water and in each Tide Race team).
	var hollows := PackedInt32Array()
	## Tide Race (M6): the tick the team cleared its last wave, -1 until then.
	var clear_tick := -1


class SimHollow:
	extends RefCounted
	var id := 0
	var team := 0
	var road: SimRoad
	## Tower id per cell, row by row; 0 for an empty cell.
	var occupied := PackedInt32Array()
	var phase := SimTypes.PHASE_PREP
	## 1-based index of the current or last wave; 0 before the first.
	var wave := 0
	## Ticks left in the build window.
	var countdown_t := 0
	## The current wave's spawns as pairs [creep kind index, ticks to wait before it].
	var queue := PackedInt32Array()
	## How many entries of the queue have spawned.
	var cursor := 0
	var spawn_wait_t := 0
	## Seats on this hollow, in seat order.
	var seats := PackedInt32Array()
	## The first tick of the current build window, for the caretaker.
	var window_tick := 0


class SimSeat:
	extends RefCounted
	var seat := 1
	var team := 0
	var hollow := 0
	var builder := "lamplighter"
	var gold := 0
	var ready := false
	var state := SimTypes.SEAT_PRESENT
	var kills := 0
	var damage_c := 0
	var help_c := 0
	var towers := 0
	var forks := 0
	## The caretaker's place in the Builder's plan.
	var plan_cursor := 0
	## Ticks of this seat's recent signals, for the rate limit.
	var signal_ticks := PackedInt32Array()


class SimTower:
	extends RefCounted
	var id := 0
	var owner := 1
	var hollow := 0
	var x := 0
	var z := 0
	var kind := ""
	## -1 unforked, 0 branch A, 1 branch B.
	var branch := -1
	## Gold put into this tower, for the sell refund.
	var invested := 0
	var cooldown_until := 0
	## Creep id being fired at, 0 for none.
	var target := 0
	var kills := 0
	var shots := 0
	## Team haste (M6): per mille and the seat whose hive gives it.
	var haste_pm := 0
	var haste_seat := 0
	# Resolved from the content tables at build and fork; not part of the checkpoint.
	var dmg_c := 0
	var cd_t := 1
	var range_mm := 0
	var air := false
	var shot_um_t := 1
	var min_flight_t := 1
	var splash_mm := 0
	var slow_pm := 0
	var slow_t := 0
	var pierce_c := 0
	## Road stretches in range: pairs of micrometre distances (SimRoad.intervals).
	var intervals := PackedInt64Array()


class SimCreep:
	extends RefCounted
	var id := 0
	var hollow := 0
	var kind := ""
	var dist_um := 0
	var hp_c := 0
	var max_hp_c := 0
	var armor_c := 0
	var speed_um_t := 0
	var bounty := 0
	var toll := 0
	var winged := false
	var boss := false
	var control_resist_pm := 0
	var slow_pm := 0
	var slow_until := 0
	var slow_seat := 0
	var stun_until := 0
	var stun_immune_until := 0
	var stun_seat := 0
	var mark_pm := 0
	var mark_until := 0
	var mark_seat := 0
	var crack_c := 0
	var crack_seat := 0
	## Undertow (M7): the seat that uncorked this creep, 0 for the wave's own.
	var sent_by := 0
	## False once it died or leaked; views keep the record after the match drops it.
	var alive := true


class SimShot:
	extends RefCounted
	var id := 0
	var tower := 0
	var seat := 0
	var hollow := 0
	var kind := ""
	var target := 0
	var fire_tick := 0
	var land_tick := 0
	## Where a shell bursts on the road (micrometres); -1 for a homing shot.
	var land_dist_um := -1
	var dmg_c := 0
	var splash_mm := 0
	var slow_pm := 0
	var slow_t := 0
	var pierce_c := 0
