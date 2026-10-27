## Arrows and frost shards home in on their creep; cannon shells fly a fixed arc
## to where the creep is predicted to be and burst on landing.
class_name Projectile
extends Node3D

const MODELS := {
	"arrow": "res://models/projectiles/arrow.glb",
	"cannonball": "res://models/projectiles/cannonball.glb",
	"frost_shard": "res://models/projectiles/frost_shard.glb",
}
const ARC_HEIGHT := 1.1

var kind := ""
var damage := 0.0
var speed := 10.0
var splash := 0.0
var slow := 0.0
var slow_time := 0.0
var tower: Tower
var target: Creep
var target_pos := Vector3.ZERO

var _start := Vector3.ZERO
var _flight := 0.0
var _t := 0.0
var _done := false


func launch(from_tower: Tower, at: Creep, muzzle: Vector3) -> void:
	tower = from_tower
	target = at
	var s: Dictionary = from_tower.stats
	kind = str(s["projectile"])
	damage = float(s["damage"])
	speed = float(s["speed"])
	splash = float(s.get("splash", 0.0))
	slow = float(s.get("slow", 0.0))
	slow_time = float(s.get("slow_time", 0.0))
	position = muzzle
	_start = muzzle
	add_to_group("projectiles")
	add_child(Models.instance(MODELS[kind]))
	if kind == "cannonball":
		# Lead the target: fly time from the current distance, then aim where it will be.
		_flight = maxf(0.35, muzzle.distance_to(at.aim_point()) / speed)
		target_pos = at.predict(_flight)
	else:
		target_pos = at.aim_point()


func _physics_process(delta: float) -> void:
	if _done:
		return
	if kind == "cannonball":
		_t += delta
		var f := minf(_t / _flight, 1.0)
		var p := _start.lerp(target_pos, f) + Vector3.UP * ARC_HEIGHT * 4.0 * f * (1.0 - f)
		_face(p - position)
		position = p
		if f >= 1.0:
			_burst()
		return
	if is_instance_valid(target) and not target.dead:
		target_pos = target.aim_point()
	var to := target_pos - position
	var step := speed * delta
	if to.length() <= step + 0.05:
		position = target_pos
		_hit()
		return
	_face(to)
	position += to.normalized() * step


func _face(direction: Vector3) -> void:
	if direction.length_squared() > 1e-8:
		# Models point along +Z; Node3D.look_at points -Z, so look away from the target.
		look_at(
			position - direction,
			Vector3.UP if absf(direction.normalized().y) < 0.99 else Vector3.RIGHT
		)


func _hit() -> void:
	_done = true
	if is_instance_valid(target) and not target.dead:
		if slow > 0.0:
			target.apply_slow(slow, slow_time)
			Fx.burst(get_tree(), position, Color(0.6, 0.9, 1.0), 10, 1.6, 0.05, 0.45, -2.0)
		else:
			Fx.burst(get_tree(), position, Color(0.95, 0.85, 0.6), 5, 1.4, 0.04, 0.3)
		Sfx.play("hit", -10.0)
		if target.take_damage(damage):
			_credit_kill()
	queue_free()


func _burst() -> void:
	_done = true
	var ground := Vector3(position.x, 0.0, position.z)
	Fx.explosion(get_tree(), ground, splash)
	Sfx.play("explosion", -4.0)
	for node in get_tree().get_nodes_in_group("creeps"):
		var creep := node as Creep
		var d := (
			Vector2(creep.global_position.x - ground.x, creep.global_position.z - ground.z).length()
		)
		if d <= splash:
			# Full damage at the centre, half at the edge.
			if creep.take_damage(damage * lerpf(1.0, 0.5, d / splash)):
				_credit_kill()
	queue_free()


func _credit_kill() -> void:
	if is_instance_valid(tower):
		tower.kills += 1
