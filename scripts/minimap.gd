## The minimap: the tile map in small, creeps and towers as marks, and the camera's
## view as an outline. Click or drag on it to move the camera there.
class_name Minimap
extends Control

const COLORS := {
	".": Color("#4f7a2e"),
	",": Color("#6f8a34"),
	"T": Color("#2f5a2a"),
	"^": Color("#6b665f"),
	"~": Color("#2c5866"),
	"#": Color("#8a6a44"),
	"S": Color("#8a6a44"),
	"E": Color("#8a6a44"),
	"L": Color("#4f7a2e"),
}

var map: HollowMap
var camera: CameraRig
var _texture: ImageTexture
var _dragging := false


func setup(source: HollowMap, rig: CameraRig) -> void:
	map = source
	camera = rig
	var image := Image.create(map.width, map.depth, false, Image.FORMAT_RGBA8)
	for z in map.depth:
		for x in map.width:
			image.set_pixel(x, z, COLORS.get(map.tile(Vector2i(x, z)), Color.BLACK))
	_texture = ImageTexture.create_from_image(image)
	mouse_filter = Control.MOUSE_FILTER_STOP


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	if map == null:
		return
	var area := _map_rect()
	draw_texture_rect(_texture, area, false)
	var cell := area.size.x / map.width
	draw_rect(
		Rect2(_to_mini(map.center(map.spawn)) - Vector2(4, 4), Vector2(8, 8)), Color("#b070ff")
	)
	draw_rect(
		Rect2(_to_mini(map.center(map.hearth)) - Vector2(4, 4), Vector2(8, 8)), Color("#ffb040")
	)
	for tower in get_tree().get_nodes_in_group("towers"):
		var at := _to_mini((tower as Node3D).global_position)
		draw_rect(
			Rect2(at - Vector2(cell, cell) * 0.4, Vector2(cell, cell) * 0.8), Color("#5a8cff")
		)
	for creep in get_tree().get_nodes_in_group("creeps"):
		draw_circle(
			_to_mini((creep as Node3D).global_position), maxf(1.5, cell * 0.28), Color("#ff4a3a")
		)
	# What the camera sees, projected onto the ground.
	var view := get_viewport().get_visible_rect().size
	var corners := PackedVector2Array()
	for p: Vector2 in [
		Vector2(0, 0), Vector2(view.x, 0), Vector2(view.x, view.y), Vector2(0, view.y)
	]:
		var hit := _ground(p)
		if hit == Vector3.INF:
			return
		corners.append(_to_mini(hit))
	corners.append(corners[0])
	draw_polyline(corners, Color(1, 1, 1, 0.85), 1.0)


func _gui_input(event: InputEvent) -> void:
	if (
		event is InputEventMouseButton
		and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT
	):
		_dragging = (event as InputEventMouseButton).pressed
		if _dragging:
			_look((event as InputEventMouseButton).position)
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		_look((event as InputEventMouseMotion).position)
		accept_event()


func _look(local: Vector2) -> void:
	var area := _map_rect()
	var f := (local - area.position) / area.size
	camera.look_from(Vector3(f.x * map.width, 0, f.y * map.depth + 1.5), camera.distance)


func _map_rect() -> Rect2:
	var scale := minf(size.x / map.width, size.y / map.depth)
	var map_size := Vector2(map.width, map.depth) * scale
	return Rect2((size - map_size) * 0.5, map_size)


func _to_mini(world: Vector3) -> Vector2:
	var area := _map_rect()
	return area.position + Vector2(world.x / map.width, world.z / map.depth) * area.size


func _ground(screen: Vector2) -> Vector3:
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	if direction.y > -0.001:
		return Vector3.INF
	return origin + direction * (-origin.y / direction.y)
