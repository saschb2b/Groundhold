## One-shot visual effects: particle bursts, blast rings, flashes and floating text.
##
## Particles use fixed seeds from Game.rng, so effects look the same on every run
## and captures stay comparable.
class_name Fx
extends RefCounted

static var _particle_material: StandardMaterial3D
static var _ring_mesh: TorusMesh


static func clear_cache() -> void:
	_particle_material = null
	_ring_mesh = null


static func layer(tree: SceneTree) -> Node3D:
	var scene := tree.current_scene
	var effects := scene.get_node_or_null("Effects") if scene else null
	return effects if effects else scene


static func burst(
	tree: SceneTree,
	at: Vector3,
	color: Color,
	amount := 12,
	speed := 2.0,
	size := 0.06,
	lifetime := 0.5,
	gravity := -6.0,
	color_end := Color(0, 0, 0, 0)
) -> void:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 0.95
	p.amount = amount
	p.lifetime = lifetime
	p.use_fixed_seed = true
	p.seed = Game.rng.randi()
	p.direction = Vector3.UP
	p.spread = 80.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, gravity, 0)
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.2
	var mesh := BoxMesh.new()
	mesh.size = Vector3.ONE * size
	mesh.material = _material()
	p.mesh = mesh
	var ramp := Gradient.new()
	ramp.set_color(0, color)
	ramp.set_color(1, color_end if color_end.a > 0.0 else Color(color, 0.0))
	p.color_ramp = ramp
	p.position = at
	layer(tree).add_child(p)
	p.emitting = true
	p.finished.connect(p.queue_free)


## A flat ring that expands and fades: blast radius, frost nova, build footprint.
static func ring(
	tree: SceneTree, at: Vector3, radius: float, color: Color, duration := 0.35
) -> void:
	if _ring_mesh == null:
		_ring_mesh = TorusMesh.new()
		_ring_mesh.inner_radius = 0.9
		_ring_mesh.outer_radius = 1.0
		_ring_mesh.rings = 24
		_ring_mesh.ring_segments = 4
	var ring_node := MeshInstance3D.new()
	ring_node.mesh = _ring_mesh
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = color
	ring_node.material_override = mat
	ring_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring_node.position = at + Vector3(0, 0.05, 0)
	ring_node.scale = Vector3(0.2, 0.3, 0.2) * radius
	layer(tree).add_child(ring_node)
	var tween := ring_node.create_tween().set_parallel()
	tween.tween_property(ring_node, "scale", Vector3(radius, 0.3, radius), duration)
	tween.tween_property(mat, "albedo_color:a", 0.0, duration).set_ease(Tween.EASE_IN)
	tween.chain().tween_callback(ring_node.queue_free)


static func flash(
	tree: SceneTree, at: Vector3, color: Color, energy := 3.0, radius := 2.5, duration := 0.25
) -> void:
	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = energy
	light.omni_range = radius
	light.position = at + Vector3(0, 0.4, 0)
	layer(tree).add_child(light)
	var tween := light.create_tween()
	tween.tween_property(light, "light_energy", 0.0, duration)
	tween.tween_callback(light.queue_free)


static func floating_text(tree: SceneTree, at: Vector3, text: String, color: Color) -> void:
	var label := Label3D.new()
	label.text = text
	label.modulate = color
	label.outline_modulate = Color(0.1, 0.06, 0.02)
	label.outline_size = 10
	label.font_size = 40
	label.pixel_size = 0.006
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.position = at + Vector3(0, 0.5, 0)
	layer(tree).add_child(label)
	var tween := label.create_tween().set_parallel()
	tween.tween_property(label, "position:y", label.position.y + 0.7, 0.9)
	tween.tween_property(label, "modulate:a", 0.0, 0.9).set_delay(0.3)
	tween.chain().tween_callback(label.queue_free)


## A short bright pop at a muzzle: light flash plus a few fast sparks. `size` scales both.
static func muzzle_flash(tree: SceneTree, at: Vector3, color: Color, size := 1.0) -> void:
	burst(tree, at, color, int(6 * size) + 2, 2.5 * size, 0.05 * size, 0.18, 0.0)
	flash(tree, at - Vector3(0, 0.4, 0), color, 2.5 * size, 1.5 * size, 0.1)


static func explosion(tree: SceneTree, at: Vector3, radius: float) -> void:
	burst(tree, at, Color(1.0, 0.75, 0.3), 18, 3.0, 0.09, 0.45, -3.0, Color(0.3, 0.25, 0.2, 0.0))
	burst(tree, at, Color(0.45, 0.42, 0.4, 0.9), 10, 1.2, 0.14, 0.8, 0.5)
	ring(tree, at, radius, Color(1.0, 0.7, 0.3, 0.8))
	flash(tree, at, Color(1.0, 0.7, 0.35), 4.0, radius * 2.5)


static func _material() -> StandardMaterial3D:
	if _particle_material == null:
		_particle_material = StandardMaterial3D.new()
		_particle_material.vertex_color_use_as_albedo = true
		_particle_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_particle_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return _particle_material
