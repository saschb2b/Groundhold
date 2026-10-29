## A tower's view on its cell. The simulation picks the target and fires; this turns
## the cannon's barrel toward that target, spins the frost spire's shards, lets the
## pennant flutter, kicks the gun back and sends a projectile model on its way when a
## FIRE event says so. Where the shell lands never depends on where the barrel points.
class_name Tower
extends Node3D

const PENNANT := "res://models/towers/pennant.glb"
const SHARD := "res://models/projectiles/frost_shard.glb"

var rec: SimRecords.SimTower
var id := 0
var kind := ""
var cell := Vector2i.ZERO
## Display numbers for the HUD (damage, range, cooldown, ...) at this tower's level.
var stats := {}

var level: int:
	get:
		return 2 if rec.branch >= 0 else 1
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
## The creep view this tower is firing at, or null.
var target: Creep:
	get:
		var view: Creep = _creeps.get(rec.target)
		return view if view and is_instance_valid(view) and not view.dead else null

var _creeps := {}
var _base: Node3D
var _head: Node3D
var _pennant: Node3D
var _shards: Array[Node3D] = []
var _recoil := 0.0
var _clock := 0.0
var _shown_level := 0


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
	_apply_level()
	# Rise out of the ground, the way a building completes.
	_base.scale = Vector3(1, 0.05, 1)
	(
		create_tween()
		. tween_property(_base, "scale", Vector3.ONE, 0.35)
		. set_trans(Tween.TRANS_BACK)
		. set_ease(Tween.EASE_OUT)
	)


## After the simulation stepped `ticks` ticks: turn, spin and flutter by that much time.
func sync(ticks: int) -> void:
	var delta := ticks / float(SimTypes.TICKS_PER_SECOND)
	_clock += delta
	if _head:
		if kind == "frost":
			_head.rotation.y = _clock * 1.6
			_head.position.y = float(stats["head_height"]) + sin(_clock * 2.2) * 0.05
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
		if kind == "cannon":
			_recoil = maxf(0.0, _recoil - delta * 0.5)
			_head.position = Vector3(0, float(stats["head_height"]), 0) - _head.basis.z * _recoil
	if _pennant:
		# The pennant streams from the pole and flutters.
		_pennant.rotation = Vector3(
			0.0, 0.5 + sin(_clock * 2.3 + cell.x) * 0.35, sin(_clock * 5.1 + cell.y) * 0.12
		)


## The upgrade's cost, or -1 when there is nothing left to upgrade.
func upgrade_cost() -> int:
	return Game.fork_cost(kind) if level == 1 else -1


func sell_value() -> int:
	return SimMath.per_mille(invested, Game.sell_share())


func range_radius() -> float:
	return rec.range_mm / 1000.0


## The simulation fired: kick, flash, sound, and a projectile model over the shot's
## flight, from the muzzle to the target (homing) or to where the shell will burst.
func fire(event: Dictionary, road_point: Vector3) -> void:
	var projectile := Projectile.new()
	var muzzle: Vector3 = global_position + (stats["muzzle"] as Vector3)
	if _head and kind == "cannon":
		# The shell leaves the end of the barrel, and the gun kicks back. Only the
		# model's start point; the landing was fixed by the simulation.
		muzzle = _head.global_position + _head.global_basis * Vector3(0, 0.27, 0.36)
		_recoil = 0.07
	var aim: Creep = _creeps.get(int(event["target"]))
	projectile.launch(event, str(stats["projectile"]), muzzle, aim, road_point)
	Fx.layer(get_tree()).add_child(projectile)
	match kind:
		"arrow":
			Sfx.play("arrow", -6.0)
			Fx.muzzle_flash(get_tree(), muzzle, Color(1.0, 0.9, 0.6), 0.6)
		"cannon":
			Sfx.play("cannon", -3.0)
			Fx.muzzle_flash(get_tree(), muzzle, Color(1.0, 0.7, 0.3), 1.4)
			Fx.burst(get_tree(), muzzle, Color(0.8, 0.78, 0.72, 0.8), 8, 0.8, 0.08, 0.5, 0.6)
		"frost":
			Sfx.play("frost", -6.0)
			Fx.muzzle_flash(get_tree(), muzzle, Color(0.6, 0.9, 1.0), 0.8)


## The simulation forked this tower: the level-2 model and a flourish.
func forked() -> void:
	_apply_level()
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


func _apply_level() -> void:
	if _shown_level == level:
		return
	_shown_level = level
	stats = Game.tower_stats(kind, level)
	for node: Node3D in [_base, _head, _pennant]:
		if node:
			node.queue_free()
	_head = null
	_pennant = null
	_shards.clear()
	var data: Dictionary = Game.TOWERS[kind]
	var model_path: String = data.get("model_2", data["model"]) if level >= 2 else data["model"]
	_base = Models.instance(model_path)
	add_child(_base)
	if data.has("head"):
		_head = Models.instance(str(data["head"]))
		_head.position.y = float(data["head_height"])
		if level >= 2:
			_head.scale = Vector3.ONE * 1.12
		add_child(_head)
	if data.has("pennant"):
		_pennant = Models.instance(PENNANT)
		_pennant.position = data["pennant"]
		_base.add_child(_pennant)
	if kind == "frost":
		# Shards circle the floating crystal; more of them once upgraded.
		for i in 3 if level == 1 else 5:
			var shard := Models.instance(SHARD)
			shard.scale = Vector3.ONE * 0.8
			_head.add_child(shard)
			_shards.append(shard)
