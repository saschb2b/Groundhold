## The minimap: the map seen from straight above, towers (in their owners' seat colours
## when several seats play), creeps, the Welling and the Holdfast as marks, and the
## camera's view as an outline. Click or drag on it to move the camera there. The picture is the real terrain and woods, rendered once by an
## orthographic camera when the hollow is built (towers come later, so they are marks);
## a flat colour map of the tiles lies under it for runs that render nothing (headless).
class_name Minimap
extends Control

const COLORS := {
	".": Color("#4f7a2e"),
	",": Color("#64843a"),
	"T": Color("#2a4a26"),
	"^": Color("#3a352e"),
	"~": Color("#2c5866"),
	"#": Color("#8a6a44"),
	"S": Color("#8a6a44"),
	"E": Color("#8a6a44"),
	"L": Color("#4f7a2e"),
}
## Pixels per tile in the photograph: twice what the well shows, for a clean downscale.
const PIXELS_PER_TILE := 14
const INK := Color(0.04, 0.03, 0.03, 0.85)

var map: HollowMap
var camera: CameraRig
var _tiles: ImageTexture
var _photo: SubViewport
var _dragging := false


func setup(source: HollowMap, rig: CameraRig) -> void:
	map = source
	camera = rig
	var image := Image.create(map.width, map.depth, false, Image.FORMAT_RGBA8)
	for z in map.depth:
		for x in map.width:
			image.set_pixel(x, z, COLORS.get(map.tile(Vector2i(x, z)), Color.BLACK))
	_tiles = ImageTexture.create_from_image(image)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_photograph()


## One render from straight above, in the world's own light but without its haze and
## ambient occlusion (the camera is far up, both would only grey it).
func _photograph() -> void:
	_photo = SubViewport.new()
	_photo.size = Vector2i(map.width, map.depth) * PIXELS_PER_TILE
	_photo.world_3d = camera.get_world_3d()
	_photo.render_target_update_mode = SubViewport.UPDATE_ONCE
	_photo.msaa_3d = Viewport.MSAA_2X
	var eye := Camera3D.new()
	eye.projection = Camera3D.PROJECTION_ORTHOGONAL
	eye.keep_aspect = Camera3D.KEEP_HEIGHT
	eye.size = map.depth
	eye.near = 1.0
	eye.far = 80.0
	eye.position = Vector3(map.width * 0.5, 40.0, map.depth * 0.5)
	eye.rotation_degrees = Vector3(-90, 0, 0)
	var world_env := camera.get_world_3d().environment
	if world_env:
		var env := world_env.duplicate() as Environment
		env.fog_enabled = false
		env.volumetric_fog_enabled = false
		env.ssao_enabled = false
		eye.environment = env
	_photo.add_child(eye)
	add_child(_photo)


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	if map == null:
		return
	var area := _map_rect()
	draw_texture_rect(_tiles, area, false)
	draw_texture_rect(_photo.get_texture(), area, false)
	var cell := area.size.x / map.width
	_mark(_to_mini(map.center(map.spawn)), cell * 0.5, Color("#c58cff"))
	_mark(_to_mini(map.center(map.holdfast)), cell * 0.5, Color("#ffbf4a"))
	var seats := Game.seat_count()
	for node in get_tree().get_nodes_in_group("towers"):
		var tower := node as Tower
		_mark(_to_mini(tower.global_position), cell * 0.34, tower_color(tower.owner_seat, seats))
	for creep in get_tree().get_nodes_in_group("creeps"):
		_mark(_to_mini((creep as Node3D).global_position), maxf(1.6, cell * 0.24), Color("#ff5a40"))
	_draw_view(area)


## A tower's mark: its owner's seat colour while several seats play (design 5.7: owner
## colours), the quiet blue alone.
static func tower_color(owner: int, seats: int) -> Color:
	if seats <= 1:
		return Color("#9cc4ff")
	return PartyStrip.SEAT_COLORS[(owner - 1) % PartyStrip.SEAT_COLORS.size()]


## A dot with a dark rim, so marks read on grass and road alike.
func _mark(at: Vector2, radius: float, color: Color) -> void:
	draw_circle(at, radius + 1.2, INK, true, -1.0, true)
	draw_circle(at, radius, color, true, -1.0, true)


## What the camera sees, projected onto the ground and cut to the map's edge.
func _draw_view(area: Rect2) -> void:
	var view := get_viewport().get_visible_rect().size
	var corners := PackedVector2Array()
	for p: Vector2 in [Vector2(0, 0), Vector2(view.x, 0), view, Vector2(0, view.y)]:
		var hit := _ground(p)
		if hit == Vector3.INF:
			return
		corners.append(_to_mini(hit))
	var bounds := PackedVector2Array(
		[
			area.position,
			Vector2(area.end.x, area.position.y),
			area.end,
			Vector2(area.position.x, area.end.y)
		]
	)
	for shape: PackedVector2Array in Geometry2D.intersect_polygons(corners, bounds):
		var loop := shape.duplicate()
		loop.append(shape[0])
		draw_polyline(loop, Color(0, 0, 0, 0.4), 3.0, true)
		draw_polyline(loop, Color(1, 0.97, 0.9, 0.9), 1.2, true)


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
