## A live 3D portrait: the selected tower or creep turning slowly on its own stage,
## the way strategy-game consoles show the unit you have selected.
class_name Portrait
extends SubViewportContainer

var _viewport: SubViewport
var _holder: Node3D
var _camera: Camera3D
var _shown := ""


func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_viewport = SubViewport.new()
	_viewport.own_world_3d = true
	# Transparent, over a backdrop drawn by the HUD: a 3D background colour comes out
	# differently under Forward+ and the web build's Compatibility renderer.
	_viewport.transparent_bg = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)
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


func _process(delta: float) -> void:
	_holder.rotation.y += delta * 0.6


## Shows a model (plus an optional head placed at head_height); same paths keep the turn going.
func show_model(path: String, head := "", head_height := 0.0, model_scale := 1.0) -> void:
	var key := "%s|%s|%s" % [path, head, model_scale]
	if key == _shown:
		return
	_shown = key
	for child in _holder.get_children():
		child.queue_free()
	if path.is_empty():
		return
	var model := Models.instance(path)
	model.scale = Vector3.ONE * model_scale
	_holder.add_child(model)
	if head != "":
		var top := Models.instance(head)
		top.position.y = head_height * model_scale
		top.scale = Vector3.ONE * model_scale
		_holder.add_child(top)
	_frame(_bounds(_holder))


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


## Head-and-shoulders framing: the top two thirds of the model fill the frame.
func _frame(box: AABB) -> void:
	var focus := box.get_center() + Vector3(0, box.size.y * 0.12, 0)
	var radius := maxf(box.size.length() * 0.42, 0.2)
	var distance := radius / sin(deg_to_rad(_camera.fov * 0.5))
	var direction := Vector3(0, 0.35, 1).normalized()
	_camera.position = focus + direction * distance
	_camera.look_at(focus, Vector3.UP)
