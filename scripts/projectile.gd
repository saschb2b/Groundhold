## A shot's model in flight. The simulation scheduled the shot and decides what it
## hits; this only flies the model over exactly the shot's flight ticks: arrows, bolts
## and frost shards home in on their creep, hawks and kestrels stoop on theirs in a low
## swoop, cannon and mortar shells fly an arc to where the simulation said they burst.
## It leaves when the shot has landed.
class_name Projectile
extends Node3D

const MODELS := {
	"arrow": "res://models/projectiles/arrow.glb",
	"cannonball": "res://models/projectiles/cannonball.glb",
	"frost_shard": "res://models/projectiles/frost_shard.glb",
	"ballista_bolt": "res://models/projectiles/ballista_bolt.glb",
	"pinning_bolt": "res://models/projectiles/pinning_bolt.glb",
	"hawk": "res://models/projectiles/hawk.glb",
	"kestrel": "res://models/projectiles/kestrel.glb",
	"mortar_shell": "res://models/projectiles/mortar_shell.glb",
}
## How high a bursting shell's arc rises, and a bird's swoop.
const ARC_HEIGHT := 1.1
const SWOOP := {"hawk": 0.45, "kestrel": 0.3}

var kind := ""
var shot := 0
var target: Creep
var target_pos := Vector3.ZERO

var _start := Vector3.ZERO
var _fire_tick := 0
var _flight := 1
var _arc := false
var _lift := 0.0


## `event` is the simulation's FIRE event; `burst_at` the road point a shell bursts on.
func launch(
	event: Dictionary, model: String, muzzle: Vector3, aim: Creep, burst_at: Vector3
) -> void:
	kind = model
	shot = int(event["shot"])
	_fire_tick = int(event["tick"])
	_flight = maxi(1, int(event["flight"]))
	_arc = int(event["land"]) >= 0
	_lift = ARC_HEIGHT if _arc else float(SWOOP.get(kind, 0.0))
	target = aim
	position = muzzle
	_start = muzzle
	add_to_group("projectiles")
	add_child(Models.instance(MODELS[kind]))
	if _arc:
		target_pos = burst_at + Vector3(0, 0.15, 0)
	elif aim:
		target_pos = aim.aim_point()
	_place(0.0)


func _physics_process(_delta: float) -> void:
	# The shot resolved during its landing tick; the simulation has moved past it.
	if Game.sim == null or Game.sim.tick > _fire_tick + _flight:
		queue_free()


func _process(_delta: float) -> void:
	if Game.sim == null:
		return
	var now := Game.sim.tick - 1 + Engine.get_physics_interpolation_fraction()
	_place(clampf((now - _fire_tick) / _flight, 0.0, 1.0))


func _place(f: float) -> void:
	if not _arc and is_instance_valid(target) and not target.dead:
		target_pos = target.aim_point()
	var p := _start.lerp(target_pos, f)
	p += Vector3.UP * _lift * 4.0 * f * (1.0 - f)
	_face(p - position)
	position = p


func _face(direction: Vector3) -> void:
	# (look_at refuses a target its own position equals within a tolerance that grows with
	# the distance from the origin, so a step under a centimetre keeps the last facing)
	if direction.length_squared() > 1e-4:
		# Models point along +Z; Node3D.look_at points -Z, so look away from the target.
		look_at(
			position - direction,
			Vector3.UP if absf(direction.normalized().y) < 0.99 else Vector3.RIGHT
		)
