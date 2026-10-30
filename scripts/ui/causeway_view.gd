## The Causeway at low water (design 5.1, 5.2; world.md: the hub's place, which belongs to
## no map), behind every screen outside a match: a raised stone road runs out across the
## bared Flats under an open sky, with tide poles along it, waymark cairns and wrack left
## by the tide, from art_src/blender/causeway/causeway.py (models/causeway/), in a world of
## its own. A low sun, haze on the horizon, pools that catch the sky (flats.gdshader). The
## camera drifts slowly along the road; road, props and flats repeat every PERIOD units,
## so the drift never ends. It counts physics frames, never the clock, so captures repeat.
## It renders at the screen's own resolution, as the portraits do.
class_name CausewayView
extends Control

const PERIOD := 24.0
const ROAD := "res://models/causeway/road.glb"
const POLE := "res://models/causeway/pole.glb"
const CAIRN := "res://models/causeway/cairn.glb"
const WRACK := "res://models/causeway/wrack.glb"
## Units a second the camera drifts along the road, toward the far end.
const DRIFT := 0.25
## The road pieces (2 units long, chained along +Z) from here back to the haze.
const ROAD_FROM := 14.0
const ROAD_TO := -140.0
## Tiles of props, each PERIOD long, from the camera back to the haze.
const TILES := [-1, 0, 1, 2, 3, 4, 5]
## One tile's props: [model, x, z (0 to -PERIOD), yaw, lean, scale].
const PROPS := [
	[POLE, 1.05, -2.0, 20.0, 4.0, 1.0],
	[POLE, -1.1, -6.0, 160.0, -3.0, 0.95],
	[POLE, 1.05, -10.0, 70.0, -5.0, 1.05],
	[POLE, -1.1, -14.0, 230.0, 3.0, 1.0],
	[POLE, 1.05, -18.0, 300.0, 2.0, 0.9],
	[POLE, -1.1, -22.0, 110.0, -4.0, 1.0],
	[CAIRN, -2.5, -8.5, 30.0, 0.0, 1.0],
	[CAIRN, 3.4, -19.0, 200.0, 0.0, 0.85],
	[WRACK, 2.1, -4.2, 0.0, 0.0, 1.0],
	[WRACK, -3.0, -12.5, 80.0, 0.0, 1.2],
	[WRACK, 4.6, -15.0, 150.0, 0.0, 0.9],
	[WRACK, -1.9, -20.8, 260.0, 0.0, 1.0],
	[WRACK, 6.2, -7.0, 40.0, 0.0, 1.3],
	[WRACK, -5.6, -2.5, 300.0, 0.0, 1.1],
]
## Where the camera stands (beside the road, a little above it) and what it looks toward.
const EYE := Vector3(3.4, 2.4, 6.0)
const LOOK := Vector3(-2.0, 0.0, -30.0)

var drift := 0.0
var _viewport: SubViewport
var _camera: Camera3D
var _world: Node3D


func _init() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _ready() -> void:
	_viewport = SubViewport.new()
	_viewport.name = "CausewayWorld"
	_viewport.own_world_3d = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)
	_build()
	_place_camera()
	_fit_resolution()
	resized.connect(_fit_resolution)
	get_viewport().size_changed.connect(_fit_resolution)


func _physics_process(_delta: float) -> void:
	drift += 1.0 / 60.0
	_place_camera()


func _draw() -> void:
	draw_texture_rect(_viewport.get_texture(), Rect2(Vector2.ZERO, size), false)


## How many of each prop stand in the world, by model path (for tests).
func props() -> Dictionary:
	var out := {}
	for node: Node in _world.get_children():
		var path := node.scene_file_path
		if path != "":
			out[path] = int(out.get(path, 0)) + 1
	return out


## Where the camera is along the road (for tests).
func camera_z() -> float:
	return _camera.position.z


func _place_camera() -> void:
	var along := -fposmod(drift * DRIFT, PERIOD)
	_camera.position = EYE + Vector3(0, 0, along)
	_camera.look_at(LOOK + Vector3(0, 0, along), Vector3.UP)


## One rendered pixel per screen pixel: the layout size times the window's stretch.
func _fit_resolution() -> void:
	if _viewport == null:
		return
	var stretch := get_viewport().get_stretch_transform().get_scale()
	var pixels := Vector2i((size * maxf(1.0, stretch.y)).round())
	_viewport.size = Vector2i(maxi(pixels.x, 2), maxi(pixels.y, 2))
	queue_redraw()


func _build() -> void:
	var sky := ProceduralSkyMaterial.new()
	sky.sky_top_color = Color("#1c2b3f")
	sky.sky_horizon_color = Color("#cdbf9f")
	sky.sky_curve = 0.09
	sky.ground_horizon_color = Color("#8a8a80")
	sky.ground_bottom_color = Color("#34332d")
	sky.sun_angle_max = 5.0
	sky.sun_curve = 0.2
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.45
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.95
	env.fog_enabled = true
	env.fog_light_color = Color("#b9ae94")
	env.fog_density = 0.022
	env.fog_sky_affect = 0.0
	env.fog_aerial_perspective = 0.25
	# (the browser's Compatibility renderer lights the same scene brighter: the flats came
	# out bleached there, so it gets less light and exposure for the same look)
	var browser := RenderingServer.get_current_rendering_method() == "gl_compatibility"
	if browser:
		env.tonemap_exposure = 0.72
		env.ambient_light_energy = 0.32
	var environment := WorldEnvironment.new()
	environment.environment = env
	_viewport.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.name = "LowSun"
	# (low over the far left, so the road's near side is in shade and the pools glint)
	sun.rotation_degrees = Vector3(-9.0, 210.0, 0.0)
	sun.light_color = Color("#ffcf98")
	sun.light_energy = 0.95 if browser else 1.3
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 60.0
	_viewport.add_child(sun)
	_world = Node3D.new()
	_world.name = "Causeway"
	_viewport.add_child(_world)
	var flats := MeshInstance3D.new()
	flats.name = "Flats"
	var plane := PlaneMesh.new()
	plane.size = Vector2(300, 300)
	flats.mesh = plane
	flats.position = Vector3(0, -0.01, -70)
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/flats.gdshader")
	material.set_shader_parameter("period", PERIOD)
	flats.material_override = material
	_viewport.add_child(flats)
	var z := ROAD_FROM - 1.0
	while z > ROAD_TO:
		_stand(ROAD, Vector3(0, 0, z), 0.0, 0.0, 1.0)
		z -= 2.0
	for tile: int in TILES:
		for prop: Array in PROPS:
			var at := Vector3(prop[1], 0, float(prop[2]) - tile * PERIOD)
			_stand(str(prop[0]), at, float(prop[3]), float(prop[4]), float(prop[5]))
	_camera = Camera3D.new()
	_camera.name = "DriftCamera"
	_camera.fov = 48.0
	_camera.far = 400.0
	_camera.current = true
	_viewport.add_child(_camera)


func _stand(path: String, at: Vector3, yaw: float, lean: float, scale_by: float) -> void:
	var prop := Models.instance(path)
	prop.position = at
	prop.rotation_degrees = Vector3(0, yaw, lean)
	prop.scale = Vector3.ONE * scale_by
	_world.add_child(prop)
