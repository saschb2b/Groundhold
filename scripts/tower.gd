## A tower on one cell: finds the creep furthest along the road within range and
## fires projectiles at it. Cannons turn their barrel; frost spires spin a shard.
class_name Tower
extends Node3D

var kind := ""
var level := 1
var cell := Vector2i.ZERO
var stats := {}
## Gold put into this tower, for the sell refund.
var invested := 0
var kills := 0
var shots := 0
var target: Creep

const PENNANT := "res://models/towers/pennant.glb"
const SHARD := "res://models/projectiles/frost_shard.glb"

var _cooldown := 0.0
var _base: Node3D
var _head: Node3D
var _pennant: Node3D
var _shards: Array[Node3D] = []
var _recoil := 0.0
var _clock := 0.0


func setup(tower_kind: String, at_cell: Vector2i, world_pos: Vector3) -> void:
	kind = tower_kind
	cell = at_cell
	position = world_pos
	invested = int(Game.TOWERS[kind]["cost"])
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


func _physics_process(delta: float) -> void:
	_clock += delta
	_cooldown -= delta
	if target == null or not is_instance_valid(target) or target.dead or not _in_range(target):
		target = _find_target()
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
		elif target:
			var to := target.global_position - global_position
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
	if target and _cooldown <= 0.0:
		_fire(target)
		_cooldown = float(stats["cooldown"])


func upgrade_cost() -> int:
	return int(Game.TOWERS[kind]["upgrade"]["cost"]) if level == 1 else -1


func sell_value() -> int:
	return int(round(invested * Game.SELL_REFUND))


## Applies the level-2 stats and model. The caller pays.
func upgrade() -> void:
	invested += upgrade_cost()
	level = 2
	_apply_level()
	Fx.burst(
		get_tree(), global_position + Vector3(0, 0.8, 0), Color(1.0, 0.85, 0.35), 20, 2.5, 0.06, 0.7
	)
	Fx.ring(get_tree(), global_position, 0.8, Color(1.0, 0.85, 0.35, 0.9), 0.5)


func range_radius() -> float:
	return float(stats["range"])


func _apply_level() -> void:
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


func _in_range(creep: Creep) -> bool:
	var d := Vector2(
		creep.global_position.x - global_position.x, creep.global_position.z - global_position.z
	)
	return d.length() <= range_radius()


func _find_target() -> Creep:
	var best: Creep = null
	for node in get_tree().get_nodes_in_group("creeps"):
		var creep := node as Creep
		if creep.dead or not _in_range(creep):
			continue
		if best == null or creep.distance > best.distance:
			best = creep
	return best


func _fire(at: Creep) -> void:
	shots += 1
	var projectile := Projectile.new()
	var muzzle: Vector3 = global_position + (stats["muzzle"] as Vector3)
	if _head and kind == "cannon":
		# The shell leaves the end of the barrel, and the gun kicks back.
		muzzle = _head.global_position + _head.global_basis * Vector3(0, 0.27, 0.36)
		_recoil = 0.07
	projectile.launch(self, at, muzzle)
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
