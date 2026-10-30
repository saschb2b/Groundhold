## A creep's view: the model walking the road where the simulation says, its walk cycle
## at its walking speed, a health bar, the effects on it, and the hit, death and leak
## effects. A winged creep (the Duskmoth) hovers over the road at its "hover" height,
## bobbing, and its "walk" is its flap: it beats on, slower but never still, when slowed
## or stunned. Its glow is its model's emission; the view adds no light.
##
## Effects show while the simulation holds them: a slow tints the creep frost blue, a
## stun circles stars over its head, a mark floats the Owl's Eye's gold rune over it
## (Fx.mark_rune) and rings once when it takes hold.
##
## It reads its SimCreep record after every step and decides nothing. Between steps it
## is drawn between the last two ticks' positions. Keyed by the record's id.
class_name Creep
extends Node3D

const BAR_WIDTH := 0.5
const BAR_SHADER := preload("res://shaders/health_bar.gdshader")
## A flier's slowest flap, as a share of its authored cycle: slowed or stunned, it still
## beats its wings to stay up.
const MIN_FLAP := 0.6
## How far a flier bobs about its hover height, and how fast (radians per second).
const BOB := 0.06
const BOB_RATE := 2.4
## The mark rune's height over the head, and its turn (radians per second).
const RUNE_LIFT := 0.36
const RUNE_TURN := 1.1

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
## Metres per second it moves this tick: 0 while stunned.
var pace: float:
	get:
		return 0.0 if stunned else speed * slow_factor
var bounty: int:
	get:
		return rec.bounty
var lives_cost: int:
	get:
		return rec.toll
## Flat armour per hit, in the HUD's units.
var armor: float:
	get:
		return rec.armor_c / 100.0
var winged: bool:
	get:
		return rec.winged
var stunned: bool:
	get:
		return Game.sim != null and rec.stun_until > Game.sim.tick
## The extra share of every hit it takes while marked (0.2 for +20%), else 0.
var mark: float:
	get:
		var on := Game.sim != null and rec.mark_until > Game.sim.tick
		return rec.mark_pm / 1000.0 if on else 0.0
## How high it flies over the road (0 on the ground).
var hover := 0.0

var _points := PackedVector3Array()
var _lengths := PackedFloat32Array()
var _total := 0.0
var _body: Node3D
var _bar_root: Node3D
var _bar: MeshInstance3D
var _bar_material: ShaderMaterial
var _rune: MeshInstance3D
var _halo: Node3D
var _flash := 0.0
var _clock := 0.0
var _height := 0.4
var _model_scale := 1.0
var _shown_hp := -1
var _slowed := false
var _marked := false
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
	hover = float(data.get("hover", 0.0)) if rec.winged else 0.0
	_body.position.y = hover
	_start_walk()
	# (a flier's shadow lies smaller on the road below it)
	BlobShadow.under(self, 0.24 * _model_scale * (0.75 if hover > 0.0 else 1.0))
	_height = _model_height(_body) * _model_scale
	_build_bar()
	_rune = Fx.mark_rune()
	_rune.position.y = hover + _height + RUNE_LIFT
	add_child(_rune)
	_halo = Fx.stun_halo()
	_halo.position.y = hover + _height + 0.12
	add_child(_halo)
	_from = distance
	_to = _from
	_place(_to, true)


## After the simulation stepped `ticks` ticks: where it is now, how it walks or flies,
## its bar and the effects on it.
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
	_show_effects()
	var now := pace
	if _anim:
		# Feet keep pace with the ground: frost slows the cycle with the creep.
		# "stride" is the walking speed the authored cycle matches.
		var cycle := now / float(Game.CREEPS[kind].get("stride", 1.0))
		_anim.speed_scale = maxf(cycle, MIN_FLAP) if hover > 0.0 else cycle
		_anim.advance(seconds)
	else:
		# A waddle: lean side to side and bob, faster when walking faster.
		var step := _clock * now * 9.0
		_body.rotation.z = sin(step) * 0.12
		_body.position.y = hover + absf(sin(step)) * 0.035
	if hover > 0.0:
		# (by the simulation's clock and the creep's id, so captures repeat)
		_body.position.y = hover + sin(_clock * BOB_RATE + id * 0.9) * BOB
	if _flash > 0.0:
		_flash -= seconds
		_body.scale = Vector3.ONE * _model_scale * (1.0 + 0.12 * maxf(_flash, 0.0) / 0.12)
	_turn(ticks)


## The rune while a mark holds (it rings once as the mark takes hold), the stars while
## a stun does; both turn by the simulation's clock.
func _show_effects() -> void:
	var marked := mark > 0.0
	if marked and not _marked:
		Fx.ring(get_tree(), global_position + Vector3(0, hover, 0), 0.5, Fx.MARK_GOLD, 0.45)
	_marked = marked
	_rune.visible = marked
	if marked:
		_rune.rotation.y = _clock * RUNE_TURN
		_rune.scale = Vector3.ONE * (1.0 + 0.06 * sin(_clock * 4.0))
	_halo.visible = stunned
	if _halo.visible:
		_halo.rotation.y = -_clock * 4.0


func _process(_delta: float) -> void:
	if dead:
		return
	_place(lerpf(_from, _to, Engine.get_physics_interpolation_fraction()))


## Where hits land: the body's middle, in the air for a flier.
func aim_point() -> Vector3:
	return global_position + Vector3(0, hover + _height * 0.55, 0)


## Whether the mark rune and the stun stars show, for tests: {"rune", "stars", "tint"}.
func effects_shown() -> Dictionary:
	return {"rune": _rune.visible, "stars": _halo.visible, "tint": _slowed}


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
	var at := global_position + Vector3(0, hover + _height * 0.5, 0)
	var color: Color = Game.CREEPS[kind]["color"]
	Fx.burst(get_tree(), at, color, 16, 2.6, 0.07, 0.6)
	Fx.floating_text(get_tree(), at, "+%d" % bounty, Color(1.0, 0.85, 0.3))
	Sfx.play("creep_death", -4.0)
	Sfx.play("coin", -8.0)
	var tween := create_tween()
	tween.tween_property(_body, "scale", Vector3(1.3, 0.1, 1.3) * _model_scale, 0.15)
	tween.tween_callback(queue_free)
	_bar_root.visible = false
	_rune.visible = false
	_halo.visible = false


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


## The health bar over the head: one quad facing the camera that draws its trough and the
## fill inside it (shaders/health_bar.gdshader), so the fill keeps to the trough however
## the creep turns. Shown once the creep is hurt.
func _build_bar() -> void:
	_bar_root = Node3D.new()
	_bar_root.position = Vector3(0, hover + _height + 0.18, 0)
	add_child(_bar_root)
	_bar = MeshInstance3D.new()
	_bar.name = "HealthBar"
	var quad := QuadMesh.new()
	quad.size = Vector2(BAR_WIDTH + 0.04, 0.09)
	_bar.mesh = quad
	_bar.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_bar_material = ShaderMaterial.new()
	_bar_material.shader = BAR_SHADER
	_bar_material.render_priority = 1
	_bar.material_override = _bar_material
	_bar_root.add_child(_bar)
	_bar_root.visible = false


func _update_bar() -> void:
	_shown_hp = rec.hp_c
	var ratio := clampf(hp / max_hp, 0.0, 1.0) if rec.max_hp_c > 0 else 0.0
	_bar_root.visible = ratio < 1.0
	_bar_material.set_shader_parameter("fill", ratio)
	_bar_material.set_shader_parameter(
		"fill_color", Color(0.9, 0.25, 0.2).lerp(Color(0.3, 0.9, 0.3), ratio)
	)


## The share of its trough the health bar fills now, for tests; -1 while it is hidden.
func bar_shown() -> float:
	if not _bar_root.visible:
		return -1.0
	return float(_bar_material.get_shader_parameter("fill"))


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
