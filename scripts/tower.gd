## A tower's view on its cell, drawn as its form (the base, or the branch a fork laid
## over it; Game.TOWERS says how each looks). The simulation picks the target and fires;
## this turns the head (a cannon, a mortar, a ballista, the Owl's Eye's telescope)
## toward that target, spins a frost crystal and its shards, lets the pennant flutter,
## kicks the gun back and sends a projectile model on its way when a FIRE event says so:
## from the muzzle, or, for a Kestrel Flock's bounce, from the creep the strike leaves.
## Where a shot lands never depends on where the head points.
##
## The Owl's Eye fires nothing: its telescope follows the creep it marks, and a new mark
## sounds once (the rune on the creep is the creep's view's).
class_name Tower
extends Node3D

const PENNANT := "res://models/towers/pennant.glb"
const SHARD := "res://models/projectiles/frost_shard.glb"

var rec: SimRecords.SimTower
var id := 0
var kind := ""
var cell := Vector2i.ZERO
## The form standing now: the base's id, or its branch's after a fork.
var form := ""
## Display numbers for the HUD (damage, range, cooldown, ...) as this tower stands,
## its owner's Keen Sight included, with the form's display keys (Game.numbers).
var stats := {}
## What it last sent flying and from where, and how many strikes flew on from a creep
## (a Kestrel Flock's bounces), for tests.
var last_launch := ""
var last_start := Vector3.ZERO
var bounces_flown := 0
var last_bounce_start := Vector3.ZERO

## 1 unforked, 2 forked (either branch), as M1's levels counted.
var level: int:
	get:
		return 2 if rec.branch >= 0 else 1
## -1 unforked, 0 branch A, 1 branch B.
var branch: int:
	get:
		return rec.branch
var owner_seat: int:
	get:
		return rec.owner
## Gold put into this tower, for the sell refund.
var invested: int:
	get:
		return rec.invested
var kills: int:
	get:
		return rec.kills
	set(value):
		Game.debug(SimTypes.DBG_TOWER_KILLS, id, value)
var shots: int:
	get:
		return rec.shots
## The creep view this tower is firing at (an Owl's Eye: the first it marks), or null.
var target: Creep:
	get:
		var aim := rec.target
		if aim == 0 and not rec.marked.is_empty():
			aim = rec.marked[0]
		var view: Creep = _creeps.get(aim)
		return view if view and is_instance_valid(view) and not view.dead else null

var _creeps := {}
var _base: Node3D
var _head: Node3D
var _pennant: Node3D
var _shards: Array[Node3D] = []
var _recoil := 0.0
var _clock := 0.0
var _marked := PackedInt32Array()
## This tower's shots in flight by the creep each flies at (a bounce starts where the
## one before it struck).
var _flying := {}


## `creep_views` is the scene's id -> Creep table, read to find the target's model.
func setup(record: SimRecords.SimTower, world_pos: Vector3, creep_views: Dictionary) -> void:
	rec = record
	id = record.id
	kind = record.kind
	cell = Vector2i(record.x, record.z)
	_creeps = creep_views
	position = world_pos
	add_to_group("towers")
	BlobShadow.under(self, 0.62)
	_apply_form()
	# Rise out of the ground, the way a building completes.
	_base.scale = Vector3(1, 0.05, 1)
	(
		create_tween()
		. tween_property(_base, "scale", Vector3.ONE, 0.35)
		. set_trans(Tween.TRANS_BACK)
		. set_ease(Tween.EASE_OUT)
	)


## A form's whole model, its head seated and its pennant raised, standing still: for
## the placement ghost and the pending ghost.
static func model_of(form_id: String) -> Node3D:
	var data: Dictionary = Game.TOWERS[form_id]
	var root := Node3D.new()
	root.add_child(Models.instance(str(data["model"])))
	if data.has("head"):
		var head := Models.instance(str(data["head"]))
		head.position.y = float(data.get("head_height", 0.0))
		head.scale = Vector3.ONE * float(data.get("head_scale", 1.0))
		root.add_child(head)
	return root


## After the simulation stepped `ticks` ticks: turn, spin and flutter by that much time.
func sync(ticks: int) -> void:
	var delta := ticks / float(SimTypes.TICKS_PER_SECOND)
	_clock += delta
	var data: Dictionary = Game.TOWERS[form]
	if _head:
		var height := float(data.get("head_height", 0.0))
		if data.get("head_motion", "turn") == "spin":
			_head.rotation.y = _clock * 1.6
			_head.position.y = height + sin(_clock * 2.2) * 0.05
			for i in _shards.size():
				var angle := -_clock * 3.2 + TAU * i / _shards.size()
				_shards[i].position = Vector3(
					cos(angle) * 0.3, 0.12 + sin(_clock * 3.0 + i) * 0.06, sin(angle) * 0.3
				)
				_shards[i].rotation = Vector3(0.0, -angle, 0.0)
		else:
			var aim := target
			if aim:
				var to := aim.global_position - global_position
				_head.rotation.y = lerp_angle(
					_head.rotation.y, atan2(to.x, to.z), minf(1.0, delta * 10.0)
				)
			_recoil = maxf(0.0, _recoil - delta * 0.5)
			_head.position = Vector3(0, height, 0) - _head.basis.z * _recoil
	if _pennant:
		# The pennant streams from the pole and flutters.
		_pennant.rotation = Vector3(
			0.0, 0.5 + sin(_clock * 2.3 + cell.x) * 0.35, sin(_clock * 5.1 + cell.y) * 0.12
		)
	if rec.team == SimTypes.EFFECT_MARK:
		_watch_marks(data)


## A fork's cost, or -1 once the tower is forked (a fork is final).
func upgrade_cost() -> int:
	return Game.fork_cost(kind) if rec.branch < 0 else -1


func sell_value() -> int:
	return SimMath.per_mille(invested, Game.sim.sell_pm(owner_seat) if Game.sim else Game.sell_share())


func range_radius() -> float:
	return rec.range_mm / 1000.0


## The simulation fired: kick, flash, sound, and a projectile model over the shot's
## flight, from the muzzle (a bounce: from the creep it leaves) to the target (homing)
## or to where the shell will burst.
func fire(event: Dictionary, road_point: Vector3) -> void:
	var data: Dictionary = Game.TOWERS[form]
	if not data.has("projectile"):
		return
	var from := int(event.get("from", 0))
	var bounce := from != 0
	var muzzle := muzzle_point()
	if bounce:
		muzzle = _strike_point(from, muzzle)
	elif _head and data.has("recoil"):
		_recoil = float(data["recoil"])
	var projectile := Projectile.new()
	var aim: Creep = _creeps.get(int(event["target"]))
	projectile.launch(event, str(data["projectile"]), muzzle, aim, road_point)
	projectile.scale = Vector3.ONE * float(data.get("projectile_scale", 1.0))
	Fx.layer(get_tree()).add_child(projectile)
	_flying[int(event["target"])] = projectile
	last_launch = projectile.kind
	last_start = muzzle
	if bounce:
		bounces_flown += 1
		last_bounce_start = muzzle
		return  # (the bird flies on from its last strike: no second launch)
	var sound: Array = data.get("sound", [])
	if not sound.is_empty():
		Sfx.play(str(sound[0]), float(sound[1]))
	if data.has("flash"):
		var flash: Array = data["flash"]
		Fx.muzzle_flash(get_tree(), muzzle, flash[0], float(flash[1]))
		if float(flash[1]) >= 1.4:
			Fx.burst(get_tree(), muzzle, Color(0.8, 0.78, 0.72, 0.8), 8, 0.8, 0.08, 0.5, 0.6)


## Where a bounce leaves from: the creep the last strike hit, or, when that strike killed
## it (its view is gone from the table in the same frame), where that strike's bird was
## flying to.
func _strike_point(creep_id: int, otherwise: Vector3) -> Vector3:
	var view: Creep = _creeps.get(creep_id)
	if view and is_instance_valid(view) and not view.dead:
		return view.aim_point()
	var last: Variant = _flying.get(creep_id)
	if is_instance_valid(last):
		return (last as Projectile).target_pos
	return otherwise


## Where a shot leaves this tower now: the head's bore (it turns with the head), or the
## fixed muzzle over the cell.
func muzzle_point() -> Vector3:
	var data: Dictionary = Game.TOWERS[form]
	if _head and data.has("bore"):
		return _head.global_transform * (data["bore"] as Vector3)
	return global_position + (data.get("muzzle", Vector3(0, 1.0, 0)) as Vector3)


## The simulation forked this tower: the branch's model and a flourish.
func forked() -> void:
	_apply_form()
	Fx.burst(
		get_tree(), global_position + Vector3(0, 0.8, 0), Color(1.0, 0.85, 0.35), 20, 2.5, 0.06, 0.7
	)
	Fx.ring(get_tree(), global_position, 0.8, Color(1.0, 0.85, 0.35, 0.9), 0.5)
	Sfx.play("upgrade")


## The simulation sold this tower: coins, dust, gone.
func sold(refund: int) -> void:
	Fx.floating_text(
		get_tree(), global_position + Vector3(0, 0.8, 0), "+%d" % refund, Color(1.0, 0.85, 0.3)
	)
	Fx.burst(
		get_tree(), global_position + Vector3(0, 0.3, 0), Color(0.6, 0.5, 0.35, 0.9), 16, 1.5, 0.08, 0.6
	)
	Sfx.play("sell")
	remove_from_group("towers")
	queue_free()


## A marking tower took a creep it did not hold before: its sound, once.
func _watch_marks(data: Dictionary) -> void:
	if rec.marked == _marked:
		return
	for creep_id in rec.marked:
		if not _marked.has(creep_id):
			var sound: Array = data.get("sound", [])
			if not sound.is_empty():
				Sfx.play(str(sound[0]), float(sound[1]))
			break
	_marked = rec.marked.duplicate()


## Builds the standing form's model, head, pennant and shards; a fork swaps them.
func _apply_form() -> void:
	var now := SimContent.tower_form(kind, rec.branch)
	if now == form:
		return
	form = now
	stats = Game.numbers(_numbers(), 0)
	stats.merge(Game.TOWERS[form])
	for node: Node3D in [_base, _head]:
		if node:
			node.queue_free()
	_head = null
	_pennant = null
	_shards.clear()
	var data: Dictionary = Game.TOWERS[form]
	_base = Models.instance(str(data["model"]))
	add_child(_base)
	if data.has("head"):
		_head = Models.instance(str(data["head"]))
		_head.position.y = float(data.get("head_height", 0.0))
		_head.scale = Vector3.ONE * float(data.get("head_scale", 1.0))
		add_child(_head)
	if data.has("pennant"):
		_pennant = Models.instance(PENNANT)
		_pennant.position = data["pennant"]
		_base.add_child(_pennant)
	if _head and data.has("shards"):
		# Shards circle the floating crystal; more of them once deepened.
		for i in int(data["shards"]):
			var shard := Models.instance(SHARD)
			shard.scale = Vector3.ONE * 0.8
			_head.add_child(shard)
			_shards.append(shard)


## The record's resolved numbers under SimContent's keys (its owner's reach included).
func _numbers() -> Dictionary:
	return {
		"dmg_c": rec.dmg_c,
		"cd_t": rec.cd_t,
		"range_mm": rec.range_mm,
		"air": rec.air,
		"splash_mm": rec.splash_mm,
		"slow_pm": rec.slow_pm,
		"slow_t": rec.slow_t,
		"pierce_c": rec.pierce_c,
		"mark_pm": rec.mark_pm,
		"marks": rec.marks,
		"bounces": rec.bounces,
		"bounce_mm": rec.bounce_mm,
	}
