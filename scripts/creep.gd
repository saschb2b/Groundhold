## A creep's view: the model walking the road where the simulation says, its walk cycle
## at its walking speed, a health bar, frost's tint, and the hit, death and leak effects.
##
## It reads its SimCreep record after every step and decides nothing. Between steps it
## is drawn between the last two ticks' positions. Keyed by the record's id.
class_name Creep
extends Node3D

const BAR_WIDTH := 0.5

var rec: SimRecords.SimCreep
var id := 0
var kind := ""
var dead := false

## Health in the HUD's units (the simulation counts hundredths).
var hp: float:
	get:
		return rec.hp_c / 100.0
var max_hp: float:
	get:
		return rec.max_hp_c / 100.0
## Walking speed in metres per second, before frost. Setting it is a scenario setter.
var speed: float:
	get:
		return rec.speed_um_t * SimTypes.TICKS_PER_SECOND / 1000000.0
	set(value):
		Game.debug(SimTypes.DBG_CREEP_SPEED, id, roundi(value * 1000000.0 / SimTypes.TICKS_PER_SECOND))
## Metres walked along the road. Setting it is a scenario setter.
var distance: float:
	get:
		return rec.dist_um / 1000000.0
	set(value):
		Game.debug(SimTypes.DBG_CREEP_DIST, id, roundi(value * 1000000.0))
## 1 when walking freely, 0.55 under a 45% slow.
var slow_factor: float:
	get:
		return 1.0 - _slow_pm() / 1000.0
var bounty: int:
	get:
		return rec.bounty
var lives_cost: int:
	get:
		return rec.toll

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
var _shown_hp := -1
var _slowed := false
## Road distance (metres) at the previous and the latest tick, drawn between.
var _from := 0.0
var _to := 0.0
## The model's own walk cycle, when it has one; otherwise the creep waddles.
var _anim: AnimationPlayer


func setup(record: SimRecords.SimCreep, points: PackedVector3Array) -> void:
	rec = record
	id = record.id
	kind = record.kind
	var data: Dictionary = Game.CREEPS[kind]
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
	_from = distance
	_to = _from
	_place(_to, true)


## After the simulation stepped `ticks` ticks: where it is now, how it walks, its bar.
func sync(ticks: int) -> void:
	if dead:
		return
	_from = _to
	_to = distance
	var seconds := ticks / float(SimTypes.TICKS_PER_SECOND)
	_clock += seconds
	var slowed := _slow_pm() > 0
	if slowed != _slowed:
		_slowed = slowed
		_tint(Color(0.6, 0.85, 1.0) if slowed else Color.WHITE)
	if rec.hp_c != _shown_hp:
		_update_bar()
	var pace := speed * slow_factor
	if _anim:
		# Feet keep pace with the ground: frost slows the cycle with the creep.
		# "stride" is the walking speed the authored cycle matches.
		_anim.speed_scale = pace / float(Game.CREEPS[kind].get("stride", 1.0))
		_anim.advance(seconds)
	else:
		# A waddle: lean side to side and bob, faster when walking faster.
		var step := _clock * pace * 9.0
		_body.rotation.z = sin(step) * 0.12
		_body.position.y = absf(sin(step)) * 0.035
	if _flash > 0.0:
		_flash -= seconds
		_body.scale = Vector3.ONE * _model_scale * (1.0 + 0.12 * maxf(_flash, 0.0) / 0.12)
	_turn(ticks)


func _process(_delta: float) -> void:
	if dead:
		return
	_place(lerpf(_from, _to, Engine.get_physics_interpolation_fraction()))


## Point on the road where hits land.
func aim_point() -> Vector3:
	return global_position + Vector3(0, _height * 0.55, 0)


## A hit landed: the model flinches and the bar shows what is left.
func hit() -> void:
	if dead:
		return
	_flash = 0.12
	_update_bar()


## Frost on this creep (a scenario setter): `factor` 0.45 slows it by 45%.
func apply_slow(factor: float, seconds: float) -> void:
	Game.debug(
		SimTypes.DBG_SLOW,
		id,
		roundi(factor * 1000.0),
		roundi(seconds * SimTypes.TICKS_PER_SECOND)
	)


func die() -> void:
	if dead:
		return
	dead = true
	remove_from_group("creeps")
	var at := global_position + Vector3(0, _height * 0.5, 0)
	var color: Color = Game.CREEPS[kind]["color"]
	Fx.burst(get_tree(), at, color, 16, 2.6, 0.07, 0.6)
	Fx.floating_text(get_tree(), at, "+%d" % bounty, Color(1.0, 0.85, 0.3))
	Sfx.play("creep_death", -4.0)
	Sfx.play("coin", -8.0)
	var tween := create_tween()
	tween.tween_property(_body, "scale", Vector3(1.3, 0.1, 1.3) * _model_scale, 0.15)
	tween.tween_callback(queue_free)
	_bar_root.visible = false


func leak() -> void:
	if dead:
		return
	dead = true
	remove_from_group("creeps")
	_place(_total, false)
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
	queue_free()


## The slow that holds for the coming tick, per mille.
func _slow_pm() -> int:
	return rec.slow_pm if Game.sim and rec.slow_until > Game.sim.tick else 0


## Faces along the road, easing round the bends.
func _turn(ticks: int) -> void:
	var ahead := _point_at(minf(_to + 0.25, _total))
	var dir := ahead - _point_at(_to)
	if dir.length_squared() > 1e-6:
		var weight := 1.0 - pow(0.75, ticks)
		rotation.y = lerp_angle(rotation.y, atan2(dir.x, dir.z), weight)


func _place(at: float, face := false) -> void:
	position = _point_at(at)
	if face:
		var dir := _point_at(minf(at + 0.25, _total)) - position
		if dir.length_squared() > 1e-6:
			rotation.y = atan2(dir.x, dir.z)


func _point_at(at: float) -> Vector3:
	for i in range(1, _points.size()):
		if at <= _lengths[i]:
			var span := _lengths[i] - _lengths[i - 1]
			var f := (at - _lengths[i - 1]) / span if span > 0.0 else 0.0
			return _points[i - 1].lerp(_points[i], f)
	return _points[_points.size() - 1]


## Loops the model's "walk" action. It is advanced by hand from sync() so the pose at a
## given tick is exact and repeatable.
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
	# Creeps of a wave spawn in step; start each one somewhere else in its cycle,
	# chosen by its id so the same creep always walks the same way.
	_anim.seek(fmod(id * 0.37, _anim.current_animation_length), true)


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
	_shown_hp = rec.hp_c
	var ratio := clampf(hp / max_hp, 0.0, 1.0) if rec.max_hp_c > 0 else 0.0
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
