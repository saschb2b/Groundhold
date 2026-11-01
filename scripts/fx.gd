## One-shot visual effects: particle bursts, blast rings, flashes and floating text; and
## the marks a team effect leaves on a creep while it lasts: the Owl's Eye's rune and a
## stunned creep's halo (design 3.7: "mark rune as Fx").
##
## M6's (design 3.7, contract-m6.md §5): the Toll Tower's bell ring (bell_ring, on its
## EV_PULSE), the Clapper Tower's clap (clap) and the Ringing Clapper's ring through a
## crowd (ring_burst), the Clay Hive's bee cloud over the creep it stings (bee_cloud,
## stirred by the tower's view), a cracked creep's chime shimmer (chime_shimmer) and the
## hum glow under a hastened tower (hum_glow). The lasting ones are made the first time a
## view needs one, so a match without M6's towers draws nothing more than before.
##
## Particles take fixed seeds from the effects' own random number generator, never the
## match's, so effects look the same on every run, captures stay comparable, and no
## effect can change what happens in the simulation.
class_name Fx
extends RefCounted

## The mark rune's gold: the Owl's lens.
const MARK_GOLD := Color(1.0, 0.84, 0.42, 0.92)
const STUN_PALE := Color(1.0, 0.95, 0.7, 0.95)
## The Bellfounder's bronze: the bell ring, the clap, the chime shimmer.
const BRONZE := Color(0.98, 0.74, 0.38, 0.9)
const BRONZE_LIGHT := Color(1.0, 0.9, 0.62, 0.95)
## The Beekeeper's honey: the hum glow; and her bees, dark bodies that catch the light.
const HONEY := Color(1.0, 0.76, 0.24, 0.55)
const BEE_BODY := Color(0.26, 0.17, 0.05)
const BEE_GOLD := Color(1.0, 0.78, 0.2)
## Bees in a cloud, and how high above and below the creep's middle they fly.
const CLOUD_BEES := 24
const CLOUD_RISE := 0.32

static var _particle_material: StandardMaterial3D
static var _ring_mesh: TorusMesh
static var _rune_mesh: ArrayMesh
static var _star_mesh: ArrayMesh
static var _bee_mesh: BoxMesh
static var _glint_mesh: ArrayMesh
## State of the particle seeds' xorshift; a plain int, so nothing outlives the scene.
static var _seed_state := 1


static func clear_cache() -> void:
	_particle_material = null
	_ring_mesh = null
	_rune_mesh = null
	_star_mesh = null
	_bee_mesh = null
	_glint_mesh = null


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
) -> MeshInstance3D:
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
	return ring_node


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


## A shell's blast: fire, smoke, a ring out to `radius` (in group "blasts" while it
## spreads, for tests) and a flash.
static func explosion(tree: SceneTree, at: Vector3, radius: float) -> void:
	burst(tree, at, Color(1.0, 0.75, 0.3), 18, 3.0, 0.09, 0.45, -3.0, Color(0.3, 0.25, 0.2, 0.0))
	burst(tree, at, Color(0.45, 0.42, 0.4, 0.9), 10, 1.2, 0.14, 0.8, 0.5)
	ring(tree, at, radius, Color(1.0, 0.7, 0.3, 0.8)).add_to_group("blasts")
	flash(tree, at, Color(1.0, 0.7, 0.35), 4.0, radius * 2.5)


static func _material() -> StandardMaterial3D:
	if _particle_material == null:
		_particle_material = StandardMaterial3D.new()
		_particle_material.vertex_color_use_as_albedo = true
		_particle_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_particle_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return _particle_material


# ── M6: the Bellfounder's bells and the Beekeeper's bees ──


## The Toll Tower rang (EV_PULSE): a bronze wave over the ground out to its reach, an echo
## inside it and glints at the bell. `at` is the tower's foot, `bell` the bell's height.
## In group "bell_rings" while it spreads (for tests).
static func bell_ring(tree: SceneTree, at: Vector3, radius: float, bell := 1.25) -> MeshInstance3D:
	var wave := ring(tree, at, radius, BRONZE, 0.6)
	wave.name = "BellRing"
	wave.add_to_group("bell_rings")
	ring(tree, at, radius * 0.55, Color(BRONZE_LIGHT, 0.7), 0.4)
	burst(tree, at + Vector3(0, bell, 0), BRONZE_LIGHT, 8, 1.2, 0.045, 0.4, 0.0)
	return wave


## The Clapper Tower struck: a short bronze crack of a ring at the creep and sparks off it.
## In group "claps" while it shows.
static func clap(tree: SceneTree, ground: Vector3, body: Vector3) -> MeshInstance3D:
	var crack := ring(tree, ground, 0.55, BRONZE_LIGHT, 0.22)
	crack.name = "Clap"
	crack.add_to_group("claps")
	burst(tree, body, BRONZE_LIGHT, 9, 2.4, 0.045, 0.25, -2.0)
	return crack


## A Ringing Clapper's strike rings through the crowd: its splash as bronze rings, not fire.
static func ring_burst(tree: SceneTree, at: Vector3, radius: float) -> void:
	var wave := ring(tree, at, radius, BRONZE, 0.4)
	wave.add_to_group("ring_bursts")
	ring(tree, at, radius * 0.6, Color(BRONZE_LIGHT, 0.8), 0.28)
	burst(tree, at + Vector3(0, 0.4, 0), BRONZE_LIGHT, 10, 2.0, 0.04, 0.35, -1.0)


## A Clay Hive's bee cloud: bees circling inside `reach` metres of the creep they sting and
## a faint honey ring on the ground marking that reach. The tower's view moves it with its
## creep and stirs it by the simulation's clock (stir_cloud), so captures repeat.
static func bee_cloud(reach: float) -> Node3D:
	if _bee_mesh == null:
		_bee_mesh = BoxMesh.new()
		_bee_mesh.size = Vector3(0.075, 0.06, 0.1)
		var body := StandardMaterial3D.new()
		body.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		body.vertex_color_use_as_albedo = true
		_bee_mesh.material = body
	var cloud := Node3D.new()
	cloud.name = "BeeCloud"
	cloud.set_meta("reach", reach)
	var bees := MultiMeshInstance3D.new()
	bees.name = "Bees"
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _bee_mesh
	mm.instance_count = CLOUD_BEES
	for i in CLOUD_BEES:
		# (gold and dark bees, so the swarm flickers as it turns)
		mm.set_instance_color(i, BEE_GOLD if i % 3 == 0 else BEE_BODY)
	bees.multimesh = mm
	bees.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cloud.add_child(bees)
	var edge := MeshInstance3D.new()
	edge.name = "Reach"
	var torus := TorusMesh.new()
	torus.inner_radius = 0.95
	torus.outer_radius = 1.0
	torus.rings = 32
	torus.ring_segments = 4
	edge.mesh = torus
	edge.material_override = _glow_material(Color(HONEY, 0.26))
	edge.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	edge.scale = Vector3(reach, 0.25, reach)
	cloud.add_child(edge)
	cloud.visible = false
	return cloud


## Where every bee of the cloud flies at `clock` seconds, the cloud's centre `lift` metres
## above the ground it stands on (a flier's cloud flies with it).
static func stir_cloud(cloud: Node3D, clock: float, lift: float) -> void:
	var reach := float(cloud.get_meta("reach", 0.9))
	var mm := (cloud.get_node("Bees") as MultiMeshInstance3D).multimesh
	for i in CLOUD_BEES:
		# Each bee its own orbit: radius, height, speed and phase from its number alone.
		var r := reach * (0.3 + 0.65 * fposmod(i * 0.618, 1.0))
		var w := 2.6 + 2.2 * fposmod(i * 0.37, 1.0)
		var a := clock * w * (1.0 if i % 2 == 0 else -1.0) + i * 2.4
		var y := lift + CLOUD_RISE * (2.0 * fposmod(i * 0.29, 1.0) - 1.0) + 0.06 * sin(clock * 7.0 + i)
		var at := Vector3(cos(a) * r, maxf(0.08, y), sin(a) * r)
		var heading := Basis(Vector3.UP, -a + (PI * 0.5 if i % 2 == 0 else -PI * 0.5))
		mm.set_instance_transform(i, Transform3D(heading, at))
	(cloud.get_node("Reach") as Node3D).position.y = 0.04


## A cracked creep's chime shimmer: two bronze bands crossing round its middle, like a
## struck bell's rings, and four glints that circle it, the armour ringing loose. The
## creep's view turns it by the simulation's clock (ring_shimmer).
static func chime_shimmer() -> Node3D:
	if _glint_mesh == null:
		_glint_mesh = _build_star()
	var shimmer := Node3D.new()
	shimmer.name = "ChimeShimmer"
	var torus := TorusMesh.new()
	torus.inner_radius = 0.86
	torus.outer_radius = 1.0
	torus.rings = 28
	torus.ring_segments = 4
	var band_material := _glow_material(Color(BRONZE, 0.7))
	for i in 2:
		var band := MeshInstance3D.new()
		band.name = "Band%d" % i
		band.mesh = torus
		band.material_override = band_material
		band.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		shimmer.add_child(band)
	var glint := _glow_material(BRONZE_LIGHT)
	for i in 4:
		var spark := MeshInstance3D.new()
		spark.name = "Glint%d" % i
		spark.mesh = _glint_mesh
		spark.material_override = glint
		spark.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		spark.scale = Vector3.ONE * 1.8
		shimmer.add_child(spark)
	shimmer.visible = false
	return shimmer


## Turns the shimmer at `clock` seconds: the bands breathe and tilt about the creep, the
## glints circle and bob. `girth` is how far round its middle they ring.
static func ring_shimmer(shimmer: Node3D, clock: float, girth: float) -> void:
	var s := girth * (1.0 + 0.1 * sin(clock * 6.0))
	for i in 2:
		var band := shimmer.get_node("Band%d" % i) as Node3D
		band.scale = Vector3(s, 0.6, s)
		var tilt := 0.5 if i == 0 else -0.5
		band.rotation = Vector3(tilt, clock * 1.7 + i * PI * 0.5, 0.0)
	for k in 4:
		var a := clock * 2.8 + TAU * k / 4.0
		(shimmer.get_node("Glint%d" % k) as Node3D).position = Vector3(
			cos(a) * girth * 1.15, 0.14 * sin(clock * 5.0 + k), sin(a) * girth * 1.15
		)


## The hum glow under a tower a Hive Hum hastens: a honey ring round its foot and a soft
## pool inside it, breathing (hum_breathe). Its own material, so each breathes in its time.
static func hum_glow() -> Node3D:
	var glow := Node3D.new()
	glow.name = "HumGlow"
	var material := _glow_material(HONEY)
	var edge := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.88
	torus.outer_radius = 1.0
	torus.rings = 28
	torus.ring_segments = 4
	edge.mesh = torus
	edge.material_override = material
	edge.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	edge.scale = Vector3(0.5, 0.2, 0.5)
	edge.position.y = 0.06
	glow.add_child(edge)
	var pool := MeshInstance3D.new()
	var disc := CylinderMesh.new()
	disc.top_radius = 0.42
	disc.bottom_radius = 0.42
	disc.height = 0.01
	disc.radial_segments = 24
	disc.rings = 1
	pool.mesh = disc
	var soft := _glow_material(Color(HONEY, 0.18))
	pool.material_override = soft
	pool.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	pool.position.y = 0.04
	glow.add_child(pool)
	glow.set_meta("materials", [material, soft])
	glow.visible = false
	return glow


static func hum_breathe(glow: Node3D, clock: float) -> void:
	var materials: Array = glow.get_meta("materials", [])
	var k := 0.5 + 0.5 * sin(clock * 3.2)
	if materials.size() == 2:
		(materials[0] as StandardMaterial3D).albedo_color.a = 0.22 + 0.26 * k
		(materials[1] as StandardMaterial3D).albedo_color.a = 0.05 + 0.08 * k
