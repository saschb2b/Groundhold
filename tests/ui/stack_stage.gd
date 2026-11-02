## Stages stacked waves (M8) on the match scene for the view scenarios, through the logged
## scenario setters (Game.debug), so a replay reproduces them: creeps held at the Welling
## until a wave has set out in full, one creep or a whole road sent to the Holdfast.
extends RefCounted


## Stops every creep on `hollow`'s road where it stands (its speed 0); how many.
static func stop_all(hollow: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow and c.speed_um_t != 0:
			Game.debug(SimTypes.DBG_CREEP_SPEED, c.id, 0)
			n += 1
	return n


## Stops every creep of wave `wave` on `hollow`'s road where it stands, so that wave cannot
## clear while the others walk on; how many.
static func stop_wave(hollow: int, wave: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow and c.wave == wave and c.speed_um_t != 0:
			Game.debug(SimTypes.DBG_CREEP_SPEED, c.id, 0)
			n += 1
	return n


## The id of the creep of wave `wave` on `hollow`'s road that set out last; 0 for none.
static func newest_of_wave(hollow: int, wave: int) -> int:
	var id := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow and c.wave == wave:
			id = maxi(id, c.id)
	return id


## Sends creep `id` to the end of its road: it gets through on the next tick.
static func send_home(id: int) -> void:
	var c := Game.sim.creep(id)
	if c != null:
		Game.debug(SimTypes.DBG_CREEP_DIST, id, Game.sim.hollows[c.hollow].road.length_um)


## Sends every creep of wave `wave` on `hollow`'s road to its end, so they get through on one
## tick while the other waves walk on; how many.
static func leak_wave(hollow: int, wave: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow and c.wave == wave:
			Game.debug(SimTypes.DBG_CREEP_DIST, c.id, Game.sim.hollows[hollow].road.length_um)
			n += 1
	return n


## Sends every creep on `hollow`'s road to its end, so all get through on one tick.
static func leak_all(hollow: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow:
			Game.debug(SimTypes.DBG_CREEP_DIST, c.id, Game.sim.hollows[hollow].road.length_um)
			n += 1
	return n
