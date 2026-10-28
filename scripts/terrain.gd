## Builds the ground from the tile map: one smooth grid for the low ground, whose
## pond tiles sink into a rounded bowl with sloping banks, raised blocks with rock
## walls for high ground, the water surface, and the painted terrain material that
## blends road, grass, meadow, rock and shore.
class_name Terrain
extends Node3D

const TERRAIN_SHADER := preload("res://shaders/terrain.gdshader")
const WATER_SHADER := preload("res://shaders/water.gdshader")
const WATER_LEVEL := -0.1
## Deepest point of the pond bed below the grass.
const WATER_DEPTH := 0.55
## Height of the gentle rises and dips across the grass (the road stays level).
const HILL_HEIGHT := 0.09
## Grid points per tile edge on low ground: enough for banks to curve.
const SUB := 6
## Depth-map texels per tile edge, for the water shader's colour and foam.
const DEPTH_RES := 16
## How far cliff-top corners wander, so high ground is not a row of boxes.
const CLIFF_JITTER := 0.16

var map: HollowMap
var _material: ShaderMaterial
var _water_material: ShaderMaterial
## R: water depth below the surface (0 shore, 1 deepest); G: how much a point
## belongs to the pond. Shared by the water and terrain shaders.
var _shore: ImageTexture
var _clock := 0.0
var _noise := FastNoiseLite.new()
var _hills := FastNoiseLite.new()


func build(source: HollowMap) -> void:
	map = source
	_noise.seed = 7
	_noise.frequency = 0.55
	_noise.fractal_octaves = 3
	_hills.seed = 11
	_hills.frequency = 0.16
	_hills.fractal_octaves = 2
	_material = ShaderMaterial.new()
	_material.shader = TERRAIN_SHADER
	_material.set_shader_parameter("map_tex", _map_texture())
	_material.set_shader_parameter("map_size", Vector2(map.width, map.depth))
	_material.set_shader_parameter("water_level", WATER_LEVEL)
	for kind: String in ["grass", "meadow", "path", "sand", "mud", "rock"]:
		_material.set_shader_parameter(kind + "_tex", load("res://textures/%s.png" % kind))
	_shore = _shore_texture()
	_material.set_shader_parameter("shore_tex", _shore)

	var ground := MeshInstance3D.new()
	ground.name = "Ground"
	ground.mesh = _low_ground_mesh()
	ground.material_override = _material
	add_child(ground)
	var cliffs := MeshInstance3D.new()
	cliffs.name = "Cliffs"
	cliffs.mesh = _high_ground_mesh()
	cliffs.material_override = _material
	add_child(cliffs)
	_add_water()


## Ground height on low ground: gentle rolling grass, level road, and a bowl
## down to -WATER_DEPTH where the pond is.
func height_at(p: Vector2) -> float:
	var flat := 1.0 - smoothstep(0.15, 0.5, _field(p, _is_road))
	var ground := _hills.get_noise_2d(p.x, p.y) * HILL_HEIGHT * flat
	var w := _water_field(p)
	if w <= 0.0:
		return ground
	# Noise wobbles the shoreline so it does not follow the tile edges.
	var s := clampf((w - 0.34 + _noise.get_noise_2d(p.x, p.y) * 0.3) / 0.75, 0.0, 1.0)
	s = s * s * (3.0 - 2.0 * s)
	return lerpf(ground, 0.0, s) - WATER_DEPTH * s


## A point on the ground at a cell's centre, for placing towers and props.
func surface(cell: Vector2i) -> Vector3:
	var c := map.center(cell)
	if map.tile(cell) == HollowMap.HIGH:
		return c
	return Vector3(c.x, height_at(Vector2(c.x, c.z)), c.z)


## How much a point belongs to the pond: 1 at a water tile's centre, 0 well away,
## blended smoothly between tile centres so the pond's outline is rounded.
func _water_field(p: Vector2) -> float:
	return _field(p, _is_water)


## A tile property blended smoothly between tile centres (1 inside, 0 outside).
func _field(p: Vector2, has: Callable) -> float:
	var fx := p.x - 0.5
	var fz := p.y - 0.5
	var x0 := floori(fx)
	var z0 := floori(fz)
	var tx := smoothstep(0.0, 1.0, fx - x0)
	var tz := smoothstep(0.0, 1.0, fz - z0)
	var top := lerpf(has.call(x0, z0), has.call(x0 + 1, z0), tx)
	var bottom := lerpf(has.call(x0, z0 + 1), has.call(x0 + 1, z0 + 1), tx)
	return lerpf(top, bottom, tz)


func _is_water(x: int, z: int) -> float:
	return 1.0 if map.tile(Vector2i(x, z)) == HollowMap.WATER else 0.0


func _is_road(x: int, z: int) -> float:
	return 1.0 if map.is_road(Vector2i(x, z)) else 0.0


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


## Low ground as one indexed grid, so normals are shared and the banks shade smoothly.
func _low_ground_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var columns := map.width * SUB + 1
	var index := {}
	for gz in map.depth * SUB + 1:
		for gx in columns:
			var p := Vector2(float(gx) / SUB, float(gz) / SUB)
			st.set_uv(p)
			st.add_vertex(Vector3(p.x, height_at(p), p.y))
			index[Vector2i(gx, gz)] = gz * columns + gx
	for z in map.depth:
		for x in map.width:
			if map.tile(Vector2i(x, z)) == HollowMap.HIGH:
				continue
			for j in SUB:
				for i in SUB:
					var gx := x * SUB + i
					var gz := z * SUB + j
					var a: int = index[Vector2i(gx, gz)]
					var b: int = index[Vector2i(gx + 1, gz)]
					var c: int = index[Vector2i(gx + 1, gz + 1)]
					var d: int = index[Vector2i(gx, gz + 1)]
					for k: int in [a, b, c, a, c, d]:
						st.add_index(k)
	st.generate_normals()
	return st.commit()


## High ground: a raised top per tile and rock walls down to lower neighbours.
func _high_ground_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z in map.depth:
		for x in map.width:
			var cell := Vector2i(x, z)
			if map.tile(cell) != HollowMap.HIGH:
				continue
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
				var foot_p := Vector3(top_p.x, low - 0.2, top_p.z)
				var foot_q := Vector3(top_q.x, low - 0.2, top_q.z)
				_quad(st, top_p, top_q, foot_q, foot_p)
	st.generate_normals()
	return st.commit()


## Two triangles, wound so the face is seen from above or outside.
func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	for v: Vector3 in [a, b, c, a, c, d]:
		st.set_uv(Vector2(v.x, v.z))
		st.add_vertex(v)


## The pond surface: a flat sheet at water level over the pond and a margin; the
## ground rises through it along the shore, so the waterline follows the banks.
## A depth map lets the shader colour shallows, deeps and foam.
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
	lo -= Vector2.ONE
	hi += Vector2.ONE
	var plane := PlaneMesh.new()
	plane.size = hi - lo
	_water_material = ShaderMaterial.new()
	_water_material.shader = WATER_SHADER
	_water_material.set_shader_parameter("depth_tex", _shore)
	_water_material.set_shader_parameter("map_size", Vector2(map.width, map.depth))
	var water := MeshInstance3D.new()
	water.name = "Water"
	water.mesh = plane
	water.material_override = _water_material
	water.position = Vector3((lo.x + hi.x) * 0.5, WATER_LEVEL, (lo.y + hi.y) * 0.5)
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(water)


## Water depth (R) and the pond field (G), 8-bit so every renderer (WebGL 2
## included) can filter them.
func _shore_texture() -> ImageTexture:
	var image := Image.create(map.width * DEPTH_RES, map.depth * DEPTH_RES, false, Image.FORMAT_RG8)
	var deepest := WATER_DEPTH + WATER_LEVEL
	for z in image.get_height():
		for x in image.get_width():
			var p := (Vector2(x, z) + Vector2(0.5, 0.5)) / DEPTH_RES
			var depth := clampf((WATER_LEVEL - height_at(p)) / deepest, 0.0, 1.0)
			image.set_pixel(x, z, Color(depth, _water_field(p), 0))
	return ImageTexture.create_from_image(image)
