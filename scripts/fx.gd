## One-shot visual effects: particle bursts, blast rings, flashes and floating text; and
## the marks a team effect leaves on a creep while it lasts: the Owl's Eye's rune and a
## stunned creep's halo (design 3.7: "mark rune as Fx").
##
## Particles take fixed seeds from the effects' own random number generator, never the
## match's, so effects look the same on every run, captures stay comparable, and no
## effect can change what happens in the simulation.
class_name Fx
extends RefCounted

## The mark rune's gold: the Owl's lens.
const MARK_GOLD := Color(1.0, 0.84, 0.42, 0.92)
const STUN_PALE := Color(1.0, 0.95, 0.7, 0.95)

static var _particle_material: StandardMaterial3D
static var _ring_mesh: TorusMesh
static var _rune_mesh: ArrayMesh
static var _star_mesh: ArrayMesh
## State of the particle seeds' xorshift; a plain int, so nothing outlives the scene.
static var _seed_state := 1


static func clear_cache() -> void:
	_particle_material = null
	_ring_mesh = null
	_rune_mesh = null
	_star_mesh = null


## The Owl's Eye's mark: a flat gold rune, a broken ring round an open eye, that floats
## over a marked creep. The creep's view shows it while the mark holds and turns it by
## the simulation's ticks (Creep.sync), so it never depends on wall-clock time.
static func mark_rune() -> MeshInstance3D:
	if _rune_mesh == null:
		_rune_mesh = _build_rune()
	var rune := MeshInstance3D.new()
	rune.name = "MarkRune"
	rune.mesh = _rune_mesh
	rune.material_override = _glow_material(MARK_GOLD)
	rune.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	rune.visible = false
	return rune


## A stunned creep's halo: three small pale stars circling over its head.
static func stun_halo() -> Node3D:
	if _star_mesh == null:
		_star_mesh = _build_star()
	var halo := Node3D.new()
	halo.name = "StunHalo"
	var material := _glow_material(STUN_PALE)
	for i in 3:
		var star := MeshInstance3D.new()
		star.mesh = _star_mesh
		star.material_override = material
		star.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var angle := TAU * i / 3.0
		star.position = Vector3(cos(angle), 0.0, sin(angle)) * 0.2
		halo.add_child(star)
	halo.visible = false
	return halo


## Unshaded, so the marks read the same in shade, at night and in the browser's
## Compatibility renderer, and lit by nothing (no extra lights).
static func _glow_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = color
	material.render_priority = 2
	return material


## The rune in the ground plane, 0.62 across: four arcs of a ring with a diamond in
## each gap, an eye drawn as two arcs, and its pupil.
static func _build_rune() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for quarter in 4:
		var start := TAU * quarter / 4.0 + deg_to_rad(12.0)
		_arc(st, Vector2.ZERO, 0.27, 0.31, start, start + deg_to_rad(66.0), 10)
		var gap := TAU * quarter / 4.0
		_diamond(st, Vector2(cos(gap), sin(gap)) * 0.29, 0.035)
	# The eye: two arcs meeting at its corners, 0.4 wide and 0.2 high.
	var bulge := 0.1
	var half := 0.2
	var radius := (half * half + bulge * bulge) / (2.0 * bulge)
	var sweep := asin(half / radius)
	for side: float in [1.0, -1.0]:
		var centre := Vector2(0.0, -side * (radius - bulge))
		var mid := PI * 0.5 if side > 0.0 else -PI * 0.5
		_arc(st, centre, radius - 0.022, radius + 0.008, mid - sweep, mid + sweep, 10)
	_arc(st, Vector2.ZERO, 0.0, 0.055, 0.0, TAU, 12)
	return st.commit()


static func _build_star() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var tips := [Vector3(0.045, 0, 0), Vector3(0, 0, 0.045), Vector3(-0.045, 0, 0), Vector3(0, 0, -0.045)]
	for up: float in [0.06, -0.06]:
		for i in 4:
			st.add_vertex(Vector3(0, up, 0))
			st.add_vertex(tips[i])
			st.add_vertex(tips[(i + 1) % 4])
	return st.commit()


## A band between two radii from angle a0 to a1 in the ground plane (x, z).
static func _arc(
	st: SurfaceTool, centre: Vector2, inner: float, outer: float, a0: float, a1: float, steps: int
) -> void:
	for i in steps:
		var t0 := lerpf(a0, a1, float(i) / steps)
		var t1 := lerpf(a0, a1, float(i + 1) / steps)
		var p := [
			centre + Vector2(cos(t0), sin(t0)) * inner,
			centre + Vector2(cos(t0), sin(t0)) * outer,
			centre + Vector2(cos(t1), sin(t1)) * outer,
			centre + Vector2(cos(t1), sin(t1)) * inner,
		]
		for k: int in [0, 1, 2, 0, 2, 3]:
			st.add_vertex(Vector3(p[k].x, 0.0, p[k].y))


static func _diamond(st: SurfaceTool, at: Vector2, r: float) -> void:
	var p := [at + Vector2(r, 0), at + Vector2(0, r), at + Vector2(-r, 0), at + Vector2(0, -r)]
	for k: int in [0, 1, 2, 0, 2, 3]:
		st.add_vertex(Vector3(p[k].x, 0.0, p[k].y))


## Starts the particle seeds over; the scene calls it when a match begins.
static func reset(seed_value := 1) -> void:
	_seed_state = maxi(1, seed_value & 0xFFFFFFFF)


static func _next_seed() -> int:
	var x := _seed_state
	x ^= (x << 13) & 0xFFFFFFFF
	x ^= x >> 17
	x ^= (x << 5) & 0xFFFFFFFF
	_seed_state = x
	return x


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
	p.seed = _next_seed()
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
