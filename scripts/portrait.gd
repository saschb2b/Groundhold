## A live 3D portrait: the selected tower or creep turning slowly on its own stage,
## the way strategy-game consoles show the unit you have selected. It renders at the
## screen's own resolution (the window may be larger than the 1280x720 layout), so the
## model stays as crisp as the text beside it.
class_name Portrait
extends Control

var _viewport: SubViewport
var _holder: Node3D
var _camera: Camera3D
var _shown := ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_viewport = SubViewport.new()
	_viewport.own_world_3d = true
	# Transparent, over a backdrop drawn by the HUD: a 3D background colour comes out
	# differently under Forward+ and the web build's Compatibility renderer.
	_viewport.transparent_bg = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)
	# The browser's Compatibility renderer hands a transparent viewport over in linear
	# colour, so the model came out dark there; encode it the way Forward+ does.
	if RenderingServer.get_current_rendering_method() == "gl_compatibility":
		material = ShaderMaterial.new()
		(material as ShaderMaterial).shader = preload("res://shaders/portrait_srgb.gdshader")
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.75, 0.75, 0.9)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.glow_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	_viewport.add_child(world)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-35, -40, 0)
	key.light_color = Color(1.0, 0.9, 0.75)
	_viewport.add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-20, 150, 0)
	rim.light_color = Color(0.5, 0.65, 1.0)
	rim.light_energy = 0.8
	_viewport.add_child(rim)
	_holder = Node3D.new()
	_viewport.add_child(_holder)
	_camera = Camera3D.new()
	_camera.fov = 30.0
	_viewport.add_child(_camera)
	_fit_resolution()
	resized.connect(_fit_resolution)
	get_viewport().size_changed.connect(_fit_resolution)


## One rendered pixel per screen pixel: the layout size times the window's stretch.
func _fit_resolution() -> void:
	if _viewport == null:
		return
	var stretch := get_viewport().get_stretch_transform().get_scale()
	var pixels := Vector2i((size * maxf(1.0, stretch.y)).round())
	_viewport.size = Vector2i(maxi(pixels.x, 2), maxi(pixels.y, 2))
	queue_redraw()


func _draw() -> void:
	draw_texture_rect(_viewport.get_texture(), Rect2(Vector2.ZERO, size), false)


func _process(delta: float) -> void:
	_holder.rotation.y += delta * 0.6


## Shows a model (plus an optional head placed at head_height); same paths keep the turn
## going. `whole` frames all of it instead of head and shoulders (a building on a plinth).
func show_model(
	path: String, head := "", head_height := 0.0, model_scale := 1.0, whole := false
) -> void:
	var key := "%s|%s|%s|%s" % [path, head, model_scale, whole]
	if key == _shown:
		return
	_shown = key
	# (a new subject turns from its front, whatever the last one's turn had reached)
	_holder.rotation.y = 0.0
	# Out of the holder now, not at the end of the frame: the framing below measures it.
	for child in _holder.get_children():
		_holder.remove_child(child)
		child.queue_free()
	if path.is_empty():
		return
	var model := Models.instance(path)
	# a Builder's bust wears the toon material, levelled for this renderer
	BuilderFigure.dress_for_portrait(model)
	model.scale = Vector3.ONE * model_scale
	_holder.add_child(model)
	if head != "":
		var top := Models.instance(head)
		top.position.y = head_height * model_scale
		top.scale = Vector3.ONE * model_scale
		_holder.add_child(top)
	_animate(model)
	_frame(_bounds(_holder), whole)


## Rigged creeps stand in their idle (or walk) cycle: the skin is only posed once an
## animation runs, so without one the body would be drawn in its bind pose.
func _animate(model: Node) -> void:
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		return
	var player := players[0] as AnimationPlayer
	for clip: String in ["idle", "walk"]:
		if player.has_animation(clip):
			player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
			player.play(clip)
			player.speed_scale = 1.0 if clip == "idle" else 0.7
			return


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var local := mi.transform
		var parent := mi.get_parent() as Node3D
		while parent and parent != node:
			local = parent.transform * local
			parent = parent.get_parent() as Node3D
		var part := local * mi.get_aabb()
		box = part if first else box.merge(part)
		first = false
	return box


## Head-and-shoulders framing: the top two thirds of the model fill the frame. Whole
## framing fits all of it with a margin, its foot clear of the window's lower edge.
func _frame(box: AABB, whole := false) -> void:
	var focus := box.get_center() + Vector3(0, box.size.y * 0.12, 0)
	var radius := maxf(box.size.length() * 0.42, 0.2)
	if whole:
		focus = box.get_center() + Vector3(0, box.size.y * 0.04, 0)
		radius = maxf(box.size.length() * 0.56, 0.2)
	var distance := radius / sin(deg_to_rad(_camera.fov * 0.5))
	var direction := Vector3(0, 0.35, 1).normalized()
	_camera.position = focus + direction * distance
	_camera.look_at(focus, Vector3.UP)
