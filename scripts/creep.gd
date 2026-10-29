## A creep walking the road from the rift gate to the hearth.
##
## Movement is distance along a polyline, advanced in _physics_process, so a
## creep's position at a given frame is exact and repeatable.
class_name Creep
extends Node3D

signal died(creep: Creep)
signal leaked(creep: Creep)

const BAR_WIDTH := 0.5

## Creeps spawned so far, to start each walk cycle at its own phase.
static var _spawned := 0

var kind := ""
var max_hp := 1.0
var hp := 1.0
var speed := 1.0
var bounty := 0
var lives_cost := 1
## Metres walked along the road; towers target the creep furthest along.
var distance := 0.0
var slow_factor := 1.0
var slow_left := 0.0
var dead := false

var _points := PackedVector3Array()
var _lengths := PackedFloat32Array()
var _total := 0.0
var _body: Node3D
var _bar_root: Node3D
var _bar_fill: MeshInstance3D
var _bar_material: StandardMaterial3D
var _flash := 0.0
var _clock := 0.0
var _height := 0.4
var _model_scale := 1.0
## The model's own walk cycle, when it has one; otherwise the creep waddles.
var _anim: AnimationPlayer


func setup(creep_kind: String, points: PackedVector3Array, hp_multiplier: float) -> void:
	kind = creep_kind
	var data: Dictionary = Game.CREEPS[kind]
	max_hp = float(data["hp"]) * hp_multiplier
	hp = max_hp
	speed = float(data["speed"])
	bounty = int(data["bounty"])
	lives_cost = int(data["lives"])
	_points = points
	_lengths.resize(points.size())
	_total = 0.0
	for i in points.size():
		if i > 0:
			_total += points[i].distance_to(points[i - 1])
		_lengths[i] = _total
	add_to_group("creeps")
	_body = Models.instance(str(data["model"]))
	_model_scale = float(data.get("scale", 1.0))
	_body.scale = Vector3.ONE * _model_scale
	add_child(_body)
	_start_walk()
	BlobShadow.under(self, 0.24 * _model_scale)
	_height = _model_height(_body) * _model_scale
	_build_bar()
	_place(0.0)


func _physics_process(delta: float) -> void:
	if dead:
		return
	_clock += delta
	if slow_left > 0.0:
		slow_left -= delta
		if slow_left <= 0.0:
			slow_factor = 1.0
			_tint(Color.WHITE)
	distance += speed * slow_factor * delta
	if distance >= _total:
		_leak()
		return
	_place(distance)
	if _anim:
		# Feet keep pace with the ground: frost slows the cycle with the creep.
		# "stride" is the walking speed the authored cycle matches.
		_anim.speed_scale = speed * slow_factor / float(Game.CREEPS[kind].get("stride", 1.0))
		_anim.advance(delta)
	else:
		# A waddle: lean side to side and bob, faster when walking faster.
		var step := _clock * speed * slow_factor * 9.0
		_body.rotation.z = sin(step) * 0.12
		_body.position.y = absf(sin(step)) * 0.035
	if _flash > 0.0:
		_flash -= delta
		_body.scale = Vector3.ONE * _model_scale * (1.0 + 0.12 * maxf(_flash, 0.0) / 0.12)


## Point on the road where hits land.
func aim_point() -> Vector3:
	return global_position + Vector3(0, _height * 0.55, 0)


## Where this creep will be after `seconds`, assuming it keeps walking.
func predict(seconds: float) -> Vector3:
	return (
		_point_at(minf(distance + speed * slow_factor * seconds, _total))
		+ Vector3(0, _height * 0.4, 0)
	)


## Returns true when this hit killed the creep.
func take_damage(amount: float) -> bool:
	if dead:
		return false
	hp -= amount
	_flash = 0.12
	_update_bar()
	if hp <= 0.0:
		_die()
		return true
	return false


func apply_slow(factor: float, seconds: float) -> void:
	if dead:
		return
	slow_factor = minf(slow_factor, 1.0 - factor)
	slow_left = maxf(slow_left, seconds)
	_tint(Color(0.6, 0.85, 1.0))


func _die() -> void:
	dead = true
	remove_from_group("creeps")
	var at := global_position + Vector3(0, _height * 0.5, 0)
	var color: Color = Game.CREEPS[kind]["color"]
	Fx.burst(get_tree(), at, color, 16, 2.6, 0.07, 0.6)
	Fx.floating_text(get_tree(), at, "+%d" % bounty, Color(1.0, 0.85, 0.3))
	Sfx.play("creep_death", -4.0)
	died.emit(self)
	var tween := create_tween()
	tween.tween_property(_body, "scale", Vector3(1.3, 0.1, 1.3) * _model_scale, 0.15)
	tween.tween_callback(queue_free)
	_bar_root.visible = false


func _leak() -> void:
	dead = true
	remove_from_group("creeps")
	Fx.burst(
		get_tree(),
		global_position + Vector3(0, 0.6, 0),
		Color(0.7, 0.4, 1.0),
		14,
		1.5,
		0.06,
		0.6,
		1.0
	)
	Sfx.play("leak")
	leaked.emit(self)
	queue_free()


func _place(at: float) -> void:
	var p := _point_at(at)
	var ahead := _point_at(minf(at + 0.25, _total))
	position = p
	var dir := ahead - p
	if dir.length_squared() > 1e-6:
		var target_yaw := atan2(dir.x, dir.z)
		rotation.y = lerp_angle(rotation.y, target_yaw, 0.25) if at > 0.0 else target_yaw


func _point_at(at: float) -> Vector3:
	for i in range(1, _points.size()):
		if at <= _lengths[i]:
			var span := _lengths[i] - _lengths[i - 1]
			var f := (at - _lengths[i - 1]) / span if span > 0.0 else 0.0
			return _points[i - 1].lerp(_points[i], f)
	return _points[_points.size() - 1]


## Loops the model's "walk" action. The player is advanced by hand from
## _physics_process so the pose at a given frame is exact and repeatable.
func _start_walk() -> void:
	var players := _body.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		return
	var player := players[0] as AnimationPlayer
	if not player.has_animation("walk"):
		return
	_anim = player
	_anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	_anim.get_animation("walk").loop_mode = Animation.LOOP_LINEAR
	_anim.play("walk")
	# Creeps of a wave spawn in step; start each one somewhere else in its cycle.
	_spawned += 1
	_anim.seek(fmod(_spawned * 0.37, _anim.current_animation_length), true)


func _model_height(node: Node3D) -> float:
	var top := 0.3
	for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		top = maxf(top, mi.get_aabb().end.y)
	return top


func _build_bar() -> void:
	_bar_root = Node3D.new()
	_bar_root.position = Vector3(0, _height + 0.18, 0)
	add_child(_bar_root)
	var back := MeshInstance3D.new()
	back.mesh = _bar_mesh(BAR_WIDTH + 0.04, 0.09)
	back.material_override = _bar_mat(Color(0.05, 0.04, 0.03, 0.85), 0)
	_bar_root.add_child(back)
	_bar_fill = MeshInstance3D.new()
	_bar_fill.mesh = _bar_mesh(BAR_WIDTH, 0.055)
	_bar_material = _bar_mat(Color(0.3, 0.9, 0.3), 1)
	_bar_fill.material_override = _bar_material
	_bar_root.add_child(_bar_fill)
	_bar_root.visible = false


func _bar_mesh(width: float, height: float) -> QuadMesh:
	var quad := QuadMesh.new()
	quad.size = Vector2(width, height)
	return quad


func _bar_mat(color: Color, priority: int) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	mat.no_depth_test = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = color
	mat.render_priority = priority
	return mat


func _update_bar() -> void:
	var ratio := clampf(hp / max_hp, 0.0, 1.0)
	_bar_root.visible = ratio < 1.0
	# The quad is centred, so shrink it and slide it left to keep its left edge fixed.
	_bar_fill.scale.x = maxf(ratio, 0.001)
	_bar_fill.position.x = -BAR_WIDTH * (1.0 - ratio) * 0.5
	_bar_material.albedo_color = Color(0.9, 0.25, 0.2).lerp(Color(0.3, 0.9, 0.3), ratio)


## A translucent overlay on the model; white removes it. Frost uses a cool blue.
func _tint(color: Color) -> void:
	for mi: MeshInstance3D in _body.find_children("*", "MeshInstance3D", true, false):
		if color == Color.WHITE:
			mi.material_overlay = null
		else:
			var overlay := StandardMaterial3D.new()
			overlay.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			overlay.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			overlay.albedo_color = Color(color, 0.35)
			mi.material_overlay = overlay
