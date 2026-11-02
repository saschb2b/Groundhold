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
	## Tide Race (M6), counted only in a race (SimMatch.race): the wave its Holdfast went
	## under on (0 while it stands), how many of that wave's creeps it had killed by then,
	## and the kills of the wave it is on (from its horn); (M8) with waves stacked, the
	## oldest wave on its road, whichever horn its creeps came with.
	var fell_wave := 0
	var fell_kills := 0
	var wave_kills := 0
	## (M8) In a race, the kills of each younger wave on the road (the one after the oldest
	## first): a stacked horn opens one, the oldest wave's clear hands the first to
	## wave_kills. Empty while one wave or none is on the road.
	var stack_kills := PackedInt32Array()
	## Undertow (M7): lives this team's uncorked creeps took from the rival's Holdfast.
	var breach_dealt := 0
	## Undertow (the sends' pass): the creeps of each check (by CHECK_IDS index, the creep a
	## pack of that check sends on this map; a boss is none) that reached this team's
	## Holdfast so far, the wave's and the rival's uncorked alike: what its defence has shown
	## the rival, whose caretaker sends by it (SimUndertow.pick_pack). Empty until the first.
	var leaked := PackedInt32Array()


class SimHollow:
	extends RefCounted
	var id := 0
	var team := 0
	var road: SimRoad
	## Tower id per cell, row by row; 0 for an empty cell.
	var occupied := PackedInt32Array()
	var phase := SimTypes.PHASE_PREP
	## 1-based index of the current or last wave; 0 before the first. (M8) With waves
	## stacked, the newest called.
	var wave := 0
	## (M8) The waves cleared, in order: waves cleared + 1 to `wave` are on the road while the
	## phase is WAVE (one, or up to the rules' stack_max once waves stack); `wave` in a
	## window and once done.
	var cleared := 0
	## Ticks left in the build window.
	var countdown_t := 0
	## The current wave's spawns as pairs [creep kind index, ticks to wait before it]; (M8)
	## with waves stacked, the newest's.
	var queue := PackedInt32Array()
	## How many entries of the queue have spawned.
	var cursor := 0
	var spawn_wait_t := 0
	## (M8) The older waves' spawns still to come while a younger wave spawns too, as
	## triples [creep kind index, its wave, the tick it spawns on], oldest wave first and each
	## wave's in its own order: a stacked horn moves the rest of the newest wave's queue here,
	## on the ticks it would have spawned on, so both schedules run (SimWaves.stack_wave).
	## Empty while one wave spawns or none.
	var behind := PackedInt32Array()
	## Seats on this hollow, in seat order.
	var seats := PackedInt32Array()
	## The first tick of the current build window, for the caretaker.
	var window_tick := 0
	## Undertow (M7): uncorked creeps still to come on this road, as triples [creep kind
	## index, the seat that sent it, the tick it spawns on], in the order they were sent.
	var sends := PackedInt32Array()


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
	## Undertow (M7): the gold paid at each of its wave clears, grown by every uncorking
	## outside the Surge; its Seawall charges, the lives lost toward the next one, and the
	## tick the wall may rise again.
	var stipend := 0
	var seawall_charges := 0
	var seawall_lost := 0
	var seawall_ready := 0


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
	## A marking tower's (the Owl's Eye's) creeps, by id, as it last picked them; it keeps
	## their marks fresh while they stay in its reach (SimEffects.mark_stage).
	var marked := PackedInt32Array()
	## A bee cloud's (M6, the Clay Hive's) creep it last stung over, 0 for none: where the
	## view hangs the cloud.
	var cloud_creep := 0
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
	## Whom it picks: SimTargeting.AIM_FIRST, AIM_WINGED or AIM_MOST_HP.
	var aim := 0
	## Creeps each strike bounces on to, each within bounce_mm of the one before.
	var bounces := 0
	var bounce_mm := 0
	## Its team effect (SimTypes.EFFECT_*, 0 for none) and, for a mark, its numbers.
	var team := 0
	var mark_pm := 0
	var marks := 0
	var mark_t := 0
	## (M6) A pulse (the Toll Tower's): it strikes every creep in reach every cd_t, and
	## stuns a ground creep stun_t ticks, then leaves it immune stun_immune_t; a flier it
	## slows air_slow_pm for air_slow_t instead.
	var pulse := false
	var stun_t := 0
	var stun_immune_t := 0
	var air_slow_pm := 0
	var air_slow_t := 0
	## (M6) A bee cloud's radius around the creep it aims at (the Clay Hive), 0 for none.
	var cloud_mm := 0
	## (M6) A crack aura's armour off, hundredths (the Chime Post), and a haste aura's
	## share, per mille (the Hive Hum): what this tower gives, not what it receives
	## (haste_pm above).
	var crack_c := 0
	var hum_pm := 0
	## (M6) Extra damage against winged creeps, per mille (the Apiary).
	var air_bonus_pm := 0
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
	## Weaker slows that outlast the applying one, as [pm, until, seat] each, strongest
	## first, each ending later than the one before; the first still running takes hold
	## when the applying one lapses (SimEffects.lapse_slow).
	var slow_next := PackedInt32Array()
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
	## (M8) The wave it came with: its hollow's newest when it spawned (an uncorked creep's
	## is the wave it walks), the coming one for a creep a debug write put on the road in a
	## window. Waves clear in order of it (SimWaves.check_clear).
	var wave := 0
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
	## A bouncing strike (the Kestrel Flock's): its number in the chain (0 for the one
	## the tower loosed), the bounces still to come after it, how far each may reach, the
	## creep it leaves from (0: the tower) and the creeps the chain has struck so far.
	var bounce := 0
	var bounces := 0
	var bounce_mm := 0
	var from_creep := 0
	var struck := PackedInt32Array()
	## (M6) Extra damage against a winged creep, per mille (an Apiary's bolt).
	var air_bonus_pm := 0
	## (M6) A pulse's stun and its flier slow. Set only on the strikes pulses and clouds
	## deal in stage 5 (id 0), which land in the same tick and are never stored.
	var stun_t := 0
	var stun_immune_t := 0
	var air_slow_pm := 0
	var air_slow_t := 0


## Undertow (M7): a corked pack. The simulation knows its tier, its window and the
## commitment (two signed 32-bit halves), never its pack until a valid UNCORK names it.
class SimBottle:
	extends RefCounted
	var id := 0
	var seat := 1
	var tier := 0
	## The wave it was corked before, which it walks in.
	var window := 0
	var commit_hi := 0
	var commit_lo := 0
	var price := 0
	## Its CHECK_IDS index once uncorked, -1 before.
	var pack := -1
	var uncorked := false
	var fizzled := false
