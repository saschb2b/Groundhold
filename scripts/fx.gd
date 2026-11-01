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
## M7's (contract-m7.md §3): the Seawall's surf round a Holdfast (seawall), an uncorked
## pack welling up at the rival's Welling (uncork), and the small bottle that glints over
## each creep it sent (sent_bottle, glint_bottle).
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
## (M7) The duel's sea: the wrack's sea-glass teal and its foam (world.md), how high a
## Seawall's surf stands, and the sent bottle's size over a creep.
const SEA_GLASS := Color(0.36, 0.8, 0.74, 0.9)
const FOAM := Color(0.93, 0.99, 0.97, 0.95)
## The Seawall's surf in palettes/hollow.gpl's water (the pond's and the seawall icon's):
## frost_dark for the body of the wave, frost where the light comes through it, snow for
## the foam on its crest.
const SURF_DEEP := Color(74 / 255.0, 160 / 255.0, 200 / 255.0)
const SURF_LIT := Color(143 / 255.0, 224 / 255.0, 240 / 255.0)
const SURF_FOAM := Color(238 / 255.0, 244 / 255.0, 248 / 255.0)
## The surf's crest at its highest, in metres, and how long the burst lasts in seconds: it
## runs out to the ring's radius in RUN_T, then sinks and fades, gone by SEAWALL_T.
const SEAWALL_HEIGHT := 1.0
const SEAWALL_RUN_T := 0.62
const SEAWALL_T := 1.05
## The surf ring's profile (a breaking wave in cross-section, travelling outward): radius
## (of the ring's own 1), height (of its crest's), how much light comes through the water
## there (frost_dark to frost), the opacity of its water and how much foam it carries (where
## the fixed froth runs high), from the trailing foot inside to the foot of its face outside.
## The water stays see-through (the ground shows through its back and its face); only the
## foam broken along the crest and the line of it at the foot are near white and solid.
const SURF_PROFILE := [
	[0.76, 0.0, 0.0, 0.0, 0.0],
	[0.84, 0.24, 0.1, 0.26, 0.0],
	[0.9, 0.56, 0.35, 0.36, 0.2],
	[0.945, 0.86, 0.75, 0.44, 0.75],
	[0.975, 1.0, 1.0, 0.5, 1.0],
	[1.02, 0.86, 0.85, 0.5, 0.9],
	[1.04, 0.45, 0.2, 0.46, 0.0],
	[1.05, 0.04, 0.5, 0.5, 0.7],
]
## How opaque the foam is where it lies thickest.
const SURF_FOAM_ALPHA := 0.92
## The swell that follows the crest in: the same wave, smaller, lower and fainter.
const SWELL := [0.7, 0.4, 0.4]
## Where the lace of foam the wave leaves behind lies (of the ring's radius), and how much
## of it there is: patches where a fixed ripple runs above LACE_CUT.
const LACE_FROM := 0.62
const LACE_TO := 0.74
const LACE_CUT := 0.35
const SURF_SEGMENTS := 96
## The surf's water: the mesh's vertex colours (the palette's, sRGB) and opacity, faded as a
## whole by `fade`, and kept on the hollow's floor: `shore` (shore_mask) is white where the
## surf may run and black on the high ground round the hollow, over `ground` (x0, z0, x1, z1
## in world metres; nothing draws outside it). Towards a cliff the wave lies down and thins
## out over the last tile and a half, as surf spends itself on a shore, along a line that
## wanders a little, so it never stands against the cliff cut off like a wall, nor hangs over
## the drop at the board's edge.
const SURF_SHADER := """shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, shadows_disabled, blend_mix;
uniform float fade = 1.0;
uniform vec4 ground = vec4(-1000.0, -1000.0, 1000.0, 1000.0);
uniform sampler2D shore : filter_linear, repeat_disable;
varying vec2 world;
float floor_at(vec2 p) {
	vec2 uv = (p - ground.xy) / (ground.zw - ground.xy);
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) {
		return 0.0;
	}
	return textureLod(shore, uv, 0.0).r;
}
void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
	VERTEX.y *= smoothstep(0.55, 1.0, floor_at(world));
}
void fragment() {
	vec3 c = COLOR.rgb;
	ALBEDO = mix(pow((c + vec3(0.055)) * (1.0 / 1.055), vec3(2.4)), c * (1.0 / 12.92), lessThan(c, vec3(0.04045)));
	float lap = 0.09 * sin(world.x * 2.7 + world.y * 1.9) * sin(world.x * 1.3 - world.y * 2.2);
	ALPHA = COLOR.a * fade * smoothstep(0.52, 0.95, floor_at(world) + lap);
}
"""
const SENT_BOTTLE_SCALE := 0.4
## Bees in a cloud, and how high above and below the creep's middle they fly.
const CLOUD_BEES := 24
const CLOUD_RISE := 0.32

static var _particle_material: StandardMaterial3D
static var _ring_mesh: TorusMesh
static var _rune_mesh: ArrayMesh
static var _star_mesh: ArrayMesh
static var _bee_mesh: BoxMesh
static var _glint_mesh: ArrayMesh
static var _surf_mesh: ArrayMesh
static var _surf_shader: Shader
static var _shore_image: Image
static var _shore_texture: ImageTexture
static var _open_shore: ImageTexture
## State of the particle seeds' xorshift; a plain int, so nothing outlives the scene.
static var _seed_state := 1


static func clear_cache() -> void:
	_particle_material = null
	_ring_mesh = null
	_rune_mesh = null
	_star_mesh = null
	_bee_mesh = null
	_glint_mesh = null
	_surf_mesh = null
	_surf_shader = null
	_shore_image = null
	_shore_texture = null
	_open_shore = null


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


# ── M7: the duel's surf and sea glass ──


## A Seawall burst (EV_SEAWALL, design 1.4): a ring of surf rises out of the ground round
## the Holdfast at `at` and runs out to the rules' `radius`, a breaking wave in the hollow's
## water with foam broken along its crest and a thin wash of water behind it, throws a little
## spray as it goes, then sinks and fades: gone in about a second, see-through all the while,
## so it never hides the board. It runs on the hollow's floor only: `shore` (shore_mask) over
## `ground` (the hollow's own tiles, in world metres) says where, so near the high ground round
## the hollow the wave lies down and thins out, and nothing of it shows past the board's edge.
## In group "seawalls" while it shows (for tests), its radius in the meta "radius".
static func seawall(
	tree: SceneTree, at: Vector3, radius: float, ground := Rect2(-1000, -1000, 2000, 2000), shore: Image = null
) -> Node3D:
	var root := Node3D.new()
	root.name = "Seawall"
	root.position = at
	root.set_meta("radius", radius)
	root.add_to_group("seawalls")
	if _surf_mesh == null:
		_surf_mesh = _build_surf()
	var surf := MeshInstance3D.new()
	surf.name = "Surf"
	surf.mesh = _surf_mesh
	if _surf_shader == null:
		_surf_shader = Shader.new()
		_surf_shader.code = SURF_SHADER
	var water := ShaderMaterial.new()
	water.shader = _surf_shader
	water.render_priority = 1
	water.set_shader_parameter("ground", Vector4(ground.position.x, ground.position.y, ground.end.x, ground.end.y))
	water.set_shader_parameter("shore", _shore_of(shore))
	surf.material_override = water
	surf.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(surf)
	layer(tree).add_child(root)
	# (k runs 0 to 1 over the burst: out to the radius with the crest high, then down and away)
	var shape := func(k: float) -> void:
		var run := clampf(k * SEAWALL_T / SEAWALL_RUN_T, 0.0, 1.0)
		var out := 1.0 - pow(1.0 - run, 3.0)
		var reach := radius * (0.18 + 0.82 * out)
		var rise := smoothstep(0.0, 0.28, k) * (1.0 - 0.75 * smoothstep(0.45, 1.0, k))
		surf.scale = Vector3(reach, maxf(SEAWALL_HEIGHT * rise, 0.01), reach)
		water.set_shader_parameter("fade", 1.0 - smoothstep(0.5, 1.0, k))
	shape.call(0.0)
	var tween := root.create_tween()
	tween.tween_method(shape, 0.0, 1.0, SEAWALL_T)
	tween.tween_callback(root.queue_free)
	# (spray off the crest as it nears the ring's edge: a few drops at a time, round the ring,
	# where the surf still stands)
	var spray := root.create_tween()
	spray.tween_interval(SEAWALL_RUN_T * 0.55)
	spray.tween_callback(func() -> void:
		for i in 9:
			var angle := TAU * (i + 0.35) / 9.0
			var where := at + Vector3(cos(angle), 0.0, sin(angle)) * radius * 0.86 + Vector3(0, SEAWALL_HEIGHT * 0.8, 0)
			if shore_at(shore, ground, Vector2(where.x, where.z)) < 0.95:
				continue
			burst(tree, where, Color(SURF_FOAM, 0.95), 4, 1.9, 0.07, 0.5, -7.0, Color(SURF_LIT, 0.0))
	)
	return root


## Where the Seawall's surf may run on `map` (a hollow's tiles): one pixel a tile, the share
## of its 3 x 3 neighbourhood that is the hollow's floor (high ground and the board's outside
## count as not), so sampled smoothly it is 1 a tile and a half from a cliff and a half at the
## cliff's foot. main.gd makes it once for its map.
static func shore_mask(map: HollowMap) -> Image:
	var image := Image.create(maxi(1, map.width), maxi(1, map.depth), false, Image.FORMAT_L8)
	for z in map.depth:
		for x in map.width:
			var low := 0
			for dz: int in [-1, 0, 1]:
				for dx: int in [-1, 0, 1]:
					if map.tile(Vector2i(x + dx, z + dz)) != HollowMap.HIGH:
						low += 1
			var v := low / 9.0
			image.set_pixel(x, z, Color(v, v, v))
	return image


## The shore mask's value at world point `p` (x, z) over `ground`, as the surf's shader reads
## it (the tile's own, 1 without a mask, 0 off the board).
static func shore_at(shore: Image, ground: Rect2, p: Vector2) -> float:
	if not ground.has_point(p):
		return 0.0
	if shore == null:
		return 1.0
	var x := clampi(floori((p.x - ground.position.x) / ground.size.x * shore.get_width()), 0, shore.get_width() - 1)
	var z := clampi(floori((p.y - ground.position.y) / ground.size.y * shore.get_height()), 0, shore.get_height() - 1)
	return shore.get_pixel(x, z).r


## The surf's shore as a texture: the mask's, made once for the image it was made from, or
## open water everywhere without one.
static func _shore_of(shore: Image) -> Texture2D:
	if shore == null:
		if _open_shore == null:
			var open := Image.create(1, 1, false, Image.FORMAT_L8)
			open.fill(Color.WHITE)
			_open_shore = ImageTexture.create_from_image(open)
		return _open_shore
	if shore != _shore_image or _shore_texture == null:
		_shore_image = shore
		_shore_texture = ImageTexture.create_from_image(shore)
	return _shore_texture


## The Seawall's surf as one ring mesh of radius 1 and height 1: SURF_PROFILE swept round,
## the crest's height and foam broken by a fixed ripple so it reads as surf, not a hoop, and
## a thin wash of water on the ground inside it. Vertex colours carry the water and its
## opacity; the material fades it as a whole.
static func _build_surf() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_sweep(st, 1.0, 1.0, 1.0, 0.0)
	_sweep(st, float(SWELL[0]), float(SWELL[1]), float(SWELL[2]), 2.4)
	# (the wash: water spread thin on the ground behind the crest, clear at its inner edge, and
	# a broken lace of foam on it)
	var inner := 0.42
	var outer := float(SURF_PROFILE[0][0]) + 0.01
	for i in SURF_SEGMENTS:
		var a0 := TAU * i / SURF_SEGMENTS
		var a1 := TAU * (i + 1) / SURF_SEGMENTS
		_flat_quad(st, a0, a1, inner, outer, Color(SURF_DEEP, 0.0), Color(SURF_LIT, 0.14), 0.015)
		var lace := 0.5 + 0.5 * sin((a0 + a1) * 0.5 * 13.0 + 2.1) * cos((a0 + a1) * 0.5 * 5.0)
		if lace > LACE_CUT:
			var foam := Color(SURF_FOAM, 0.75 * (lace - LACE_CUT) / (1.0 - LACE_CUT))
			_flat_quad(st, a0, a1, LACE_FROM, LACE_TO, foam, Color(foam, foam.a * 0.4), 0.02)
	return st.commit()


## SURF_PROFILE swept round at `scale` of the ring's radius, `height` of its crest's and
## `fade` of its opacity: the crest's height, its reach and its foam broken by fixed ripples
## (turned by `phase`), so the ring reads as surf, not a hoop.
static func _sweep(st: SurfaceTool, scale: float, height: float, fade: float, phase: float) -> void:
	var rings := []
	for i in SURF_SEGMENTS + 1:
		var a := TAU * i / SURF_SEGMENTS
		var ripple := 0.8 + 0.2 * sin(a * 7.0 + 1.3 + phase) * cos(a * 3.0 - 0.4)
		var reach := scale * (1.0 + 0.025 * sin(a * 6.0 + 0.7 + phase))
		# (the foam: a thin broken line along the crest, gathered in streaks with clear water
		# between them, not an even pale band)
		var raw := 0.5 + 0.35 * sin(a * 7.0 + 0.6 + phase) + 0.25 * sin(a * 17.0 + 1.9 + phase)
		var froth := 0.15 + 0.85 * smoothstep(0.4, 0.75, raw)
		var ring := []
		for p: Array in SURF_PROFILE:
			var r := float(p[0]) * reach
			var y := float(p[1]) * ripple * height
			var colour := SURF_DEEP.lerp(SURF_LIT, float(p[2]))
			var alpha := float(p[3])
			var foam := float(p[4]) * froth
			colour = colour.lerp(SURF_FOAM, foam)
			alpha = lerpf(alpha, SURF_FOAM_ALPHA, foam)
			colour.a = alpha * fade
			ring.append([Vector3(cos(a) * r, y, sin(a) * r), colour])
		rings.append(ring)
	for i in SURF_SEGMENTS:
		for j in SURF_PROFILE.size() - 1:
			var quad: Array = [rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]]
			for k: int in [0, 1, 2, 0, 2, 3]:
				st.set_color(quad[k][1])
				st.add_vertex(quad[k][0])


## A flat band of the ring on the ground between radii `r0` and `r1` and angles `a0`, `a1`,
## coloured `c0` at its inner edge and `c1` at its outer.
static func _flat_quad(
	st: SurfaceTool, a0: float, a1: float, r0: float, r1: float, c0: Color, c1: Color, y: float
) -> void:
	var pts := [
		[Vector3(cos(a0) * r0, y, sin(a0) * r0), c0],
		[Vector3(cos(a1) * r0, y, sin(a1) * r0), c0],
		[Vector3(cos(a1) * r1, y, sin(a1) * r1), c1],
		[Vector3(cos(a0) * r1, y, sin(a0) * r1), c1],
	]
	for k: int in [0, 1, 2, 0, 2, 3]:
		st.set_color(pts[k][1])
		st.add_vertex(pts[k][0])


## An uncorked pack wells up (EV_UNCORK) at the Welling it sets out from: a pop of foam and
## sea glass, and a ring in the colour of the seat that sent it. In group "uncorks" while
## its ring spreads.
static func uncork(tree: SceneTree, at: Vector3, color: Color) -> void:
	burst(tree, at + Vector3(0, 0.5, 0), FOAM, 14, 2.8, 0.06, 0.6, -5.0)
	burst(tree, at + Vector3(0, 0.6, 0), SEA_GLASS, 10, 2.0, 0.05, 0.7, -3.0)
	ring(tree, at, 1.2, Color(color, 0.9), 0.6).add_to_group("uncorks")


## The bottle that glints over a creep an uncorked pack sent (design 1.4, contract-m7.md
## §3): the corked bottle's model small and leaning, in the sending seat's colour at its
## foot, and a star that catches the light now and then (glint_bottle turns and lights it
## by the simulation's clock).
static func sent_bottle(color: Color) -> Node3D:
	var holder := Node3D.new()
	holder.name = "SentBottle"
	var bottle := Models.instance(Game.BOTTLE_MODEL)
	bottle.name = "Bottle"
	bottle.scale = Vector3.ONE * SENT_BOTTLE_SCALE
	bottle.rotation.z = deg_to_rad(-18.0)
	holder.add_child(bottle)
	if _star_mesh == null:
		_star_mesh = _build_star()
	var star := MeshInstance3D.new()
	star.name = "Glint"
	star.mesh = _star_mesh
	star.material_override = _glow_material(Color(1.0, 1.0, 0.94, 0.95))
	star.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	star.position = Vector3(0.03, 0.2, 0.05)
	star.scale = Vector3.ONE * 1.3
	holder.add_child(star)
	var mark := MeshInstance3D.new()
	mark.name = "SeatMark"
	var torus := TorusMesh.new()
	torus.inner_radius = 0.07
	torus.outer_radius = 0.1
	torus.rings = 16
	torus.ring_segments = 4
	mark.mesh = torus
	mark.material_override = _glow_material(Color(color, 0.95))
	mark.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mark.scale = Vector3(1.0, 0.4, 1.0)
	holder.add_child(mark)
	return holder


## Turns the sent bottle and lets its star catch the light for a moment every 1.6 s, by
## `clock` (the creep's simulated seconds) and the creep's id, so captures repeat.
static func glint_bottle(holder: Node3D, clock: float, id: int) -> void:
	holder.rotation.y = clock * 1.4 + id
	var phase := fmod(clock + id * 0.37, 1.6) / 1.6
	var star := holder.get_node_or_null("Glint") as Node3D
	if star:
		var k := clampf(1.0 - absf(phase - 0.15) / 0.15, 0.0, 1.0)
		star.visible = k > 0.0
		star.scale = Vector3.ONE * (0.6 + 1.4 * k)
