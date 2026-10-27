## Builds the ground from the tile map: a top face per cell at its height, rock
## walls wherever a neighbour is lower, a pond surface, and the painted terrain
## material that blends road, grass, meadow and rock.
class_name Terrain
extends Node3D

const TERRAIN_SHADER := preload("res://shaders/terrain.gdshader")
const WATER_SHADER := preload("res://shaders/water.gdshader")
const WATER_LEVEL := -0.12
## How far cliff-top corners wander, so high ground is not a row of boxes.
const CLIFF_JITTER := 0.16

var map: HollowMap
var _material: ShaderMaterial
var _water_material: ShaderMaterial
var _clock := 0.0


func build(source: HollowMap) -> void:
	map = source
	_material = ShaderMaterial.new()
	_material.shader = TERRAIN_SHADER
	_material.set_shader_parameter("map_tex", _map_texture())
	_material.set_shader_parameter("map_size", Vector2(map.width, map.depth))

	var ground := MeshInstance3D.new()
	ground.name = "Ground"
	ground.mesh = _ground_mesh()
	ground.material_override = _material
	add_child(ground)
	_add_water()


func _physics_process(delta: float) -> void:
	if _water_material:
		_clock += delta
		_water_material.set_shader_parameter("t", _clock)


func show_grid(on: bool) -> void:
	_material.set_shader_parameter("show_grid", 1.0 if on else 0.0)


## Highlights a cell green (can build) or red; a negative cell clears it.
func set_hover(cell: Vector2i, ok: bool) -> void:
	_material.set_shader_parameter("hover_cell", Vector2(cell))
	_material.set_shader_parameter(
		"hover_color", Color(0.45, 1.0, 0.4) if ok else Color(1.0, 0.3, 0.25)
	)


func _map_texture() -> ImageTexture:
	var image := Image.create(map.width, map.depth, false, Image.FORMAT_RGBA8)
	for z in map.depth:
		for x in map.width:
			var cell := Vector2i(x, z)
			var t := map.tile(cell)
			image.set_pixel(
				x,
				z,
				Color(
					1.0 if map.is_road(cell) else 0.0,
					1.0 if t == HollowMap.MEADOW else 0.0,
					1.0 if t == HollowMap.HIGH else 0.0,
					1.0 if map.buildable(cell) else 0.0
				)
			)
	return ImageTexture.create_from_image(image)


## A world-space corner, nudged on high ground; the same corner always moves the
## same way, so neighbouring faces and walls stay joined.
func _corner(x: int, z: int, y: float) -> Vector3:
	if y < HollowMap.HIGH_HEIGHT - 0.01:
		return Vector3(x, y, z)
	var h := hash(Vector2i(x, z))
	var dx := ((h & 0xff) / 255.0 - 0.5) * 2.0 * CLIFF_JITTER
	var dz := (((h >> 8) & 0xff) / 255.0 - 0.5) * 2.0 * CLIFF_JITTER
	var dy := (((h >> 16) & 0xff) / 255.0 - 0.5) * 0.18
	# The map border stays put so the world has straight outer edges.
	if x == 0 or x == map.width:
		dx = 0.0
	if z == 0 or z == map.depth:
		dz = 0.0
	return Vector3(x + dx, y + dy, z + dz)


func _ground_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z in map.depth:
		for x in map.width:
			var cell := Vector2i(x, z)
			var h := map.height(cell)
			var a := _corner(x, z, h)
			var b := _corner(x + 1, z, h)
			var c := _corner(x + 1, z + 1, h)
			var d := _corner(x, z + 1, h)
			_quad(st, a, b, c, d)
			# Walls down to each lower neighbour (or below the world at the border).
			var sides := [
				[Vector2i(0, -1), Vector2i(x, z), Vector2i(x + 1, z)],
				[Vector2i(1, 0), Vector2i(x + 1, z), Vector2i(x + 1, z + 1)],
				[Vector2i(0, 1), Vector2i(x + 1, z + 1), Vector2i(x, z + 1)],
				[Vector2i(-1, 0), Vector2i(x, z + 1), Vector2i(x, z)],
			]
			for side: Array in sides:
				var neighbour: Vector2i = cell + side[0]
				var low := map.height(neighbour) if map.inside(neighbour) else -1.0
				if low >= h - 0.001:
					continue
				var p: Vector2i = side[1]
				var q: Vector2i = side[2]
				var top_p := _corner(p.x, p.y, h)
				var top_q := _corner(q.x, q.y, h)
				# Sink the foot a little so no seam shows against the lower ground.
				var foot_p := Vector3(top_p.x, low - 0.05, top_p.z)
				var foot_q := Vector3(top_q.x, low - 0.05, top_q.z)
				_quad(st, top_p, top_q, foot_q, foot_p)
	st.generate_normals()
	return st.commit()


## Two triangles, wound so the face is seen from above or outside.
func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	for v: Vector3 in [a, b, c, a, c, d]:
		st.set_uv(Vector2(v.x, v.z))
		st.add_vertex(v)


func _add_water() -> void:
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for z in map.depth:
		for x in map.width:
			if map.tile(Vector2i(x, z)) == HollowMap.WATER:
				lo = lo.min(Vector2(x, z))
				hi = hi.max(Vector2(x + 1, z + 1))
	if lo.x == INF:
		return
	var plane := PlaneMesh.new()
	plane.size = hi - lo
	_water_material = ShaderMaterial.new()
	_water_material.shader = WATER_SHADER
	var water := MeshInstance3D.new()
	water.name = "Water"
	water.mesh = plane
	water.material_override = _water_material
	water.position = Vector3((lo.x + hi.x) * 0.5, WATER_LEVEL, (lo.y + hi.y) * 0.5)
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(water)
