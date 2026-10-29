## Scatters vegetation and props over the map with MultiMeshes, seeded so the
## hollow looks the same every run. Fluff on buildable grass is removed when a
## tower takes the cell.
class_name Decor
extends Node3D

const V := "res://models/vegetation/"
const TREES_GREEN := ["tree_green_1", "tree_green_2", "tree_green_3"]
const TREES_AUTUMN := ["tree_amber_1", "tree_amber_2", "tree_amber_3", "tree_red_1", "tree_red_2"]
const PINES := ["tree_pine_1", "tree_pine_2", "tree_pine_3"]
const BUSHES := ["bush_1", "bush_2", "bush_3"]
const ROCKS := ["rock_1", "rock_2", "rock_3", "rock_4"]
const TUFTS := ["grass_tuft_1", "grass_tuft_2", "grass_tuft_3"]
const FLOWERS := [
	"flower_yellow_1",
	"flower_yellow_2",
	"flower_white_1",
	"flower_white_2",
	"flower_purple_1",
	"flower_purple_2"
]
const PUMPKINS := ["pumpkin_1", "pumpkin_2", "pumpkin_3"]
const SMALL := ["mushroom_1", "mushroom_2", "stump"]
const FERNS := ["fern_1", "fern_2"]
const REEDS := ["reeds_1", "reeds_2", "reeds_3"]
## Broadleaf crowns are wide; scaled down so the woods stay off the road.
const CROWN_SCALE := 0.8
const LILIES := ["lily_pad_1", "lily_pad_2", "lily_pad_3"]

var map: HollowMap
var terrain: Terrain
var _rng := RandomNumberGenerator.new()
## model name -> Array[Transform3D]
var _placements := {}
## model name -> Array[Vector2i]: which cell each instance belongs to
var _owners := {}
var _multimeshes := {}
var _cleared := {}
var _tree_shadows: Array[Transform3D] = []


func build(source: HollowMap, ground: Terrain) -> void:
	map = source
	terrain = ground
	_rng.seed = 20261027
	for z in map.depth:
		for x in map.width:
			_dress(Vector2i(x, z))
	for name: String in _placements:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		var path := V + name + ".glb"
		if not ResourceLoader.exists(path):
			path = "res://models/props/%s.glb" % name
		mm.mesh = Models.mesh(path)
		var transforms: Array = _placements[name]
		mm.instance_count = transforms.size()
		for i in transforms.size():
			mm.set_instance_transform(i, transforms[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = name
		mmi.multimesh = mm
		add_child(mmi)
		_multimeshes[name] = mm
	_add_tree_shadows()


func _add_tree_shadows() -> void:
	var plane := PlaneMesh.new()
	plane.size = Vector2.ONE
	var material := ShaderMaterial.new()
	material.shader = BlobShadow.SHADER
	material.set_shader_parameter("strength", 0.6)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = plane
	mm.instance_count = _tree_shadows.size()
	for i in _tree_shadows.size():
		mm.set_instance_transform(i, _tree_shadows[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "TreeShadows"
	mmi.multimesh = mm
	mmi.material_override = material
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)


## Hides the fluff standing on a cell (a tower is being built there).
func clear_cell(cell: Vector2i) -> void:
	_cleared[cell] = true
	for name: String in _owners:
		var cells: Array = _owners[name]
		for i in cells.size():
			if cells[i] == cell:
				(_multimeshes[name] as MultiMesh).set_instance_transform(
					i, Transform3D(Basis.from_scale(Vector3.ZERO), Vector3.ZERO)
				)


## Pieces of decor still standing on a cell. Tracked here rather than read back
## from the MultiMesh, which keeps no data without a renderer (headless runs).
func count_on(cell: Vector2i) -> int:
	if _cleared.has(cell):
		return 0
	var total := 0
	for name: String in _owners:
		total += (_owners[name] as Array).count(cell)
	return total


func _dress(cell: Vector2i) -> void:
	var t := map.tile(cell)
	match t:
		HollowMap.WOODS:
			# Dense woods: two or three big trees a tile, a bush, and now and then a stump.
			for i in _rng.randi_range(2, 3):
				_put(_pick(TREES_GREEN + TREES_AUTUMN + PINES + PINES), cell, 0.34, 0.85, 1.15)
			_put(_pick(BUSHES), cell, 0.4, 0.8, 1.2)
			if _rng.randf() < 0.3:
				_put("stump", cell, 0.42, 0.9, 1.3)
			if _rng.randf() < 0.6:
				_put(_pick(FERNS), cell, 0.42, 0.9, 1.3)
			_scatter(TUFTS, cell, 2, 0.45)
		HollowMap.HIGH:
			if _rng.randf() < 0.7:
				_put(_pick(PINES + PINES + TREES_AUTUMN), cell, 0.3, 0.8, 1.1)
			elif _rng.randf() < 0.5:
				_put(_pick(ROCKS), cell, 0.3, 1.2, 2.0)
			if _rng.randf() < 0.5:
				_put(_pick(BUSHES + TUFTS), cell, 0.4, 0.8, 1.2)
		HollowMap.MEADOW:
			_scatter(FLOWERS, cell, _rng.randi_range(3, 5), 0.45)
			_scatter(TUFTS, cell, 2, 0.45)
			if _rng.randf() < 0.4:
				_put(_pick(PUMPKINS), cell, 0.3, 1.2, 1.6)
		HollowMap.GRASS:
			if _rng.randf() < 0.35:
				_scatter(TUFTS, cell, _rng.randi_range(1, 2), 0.42)
			if _rng.randf() < 0.08:
				_put(_pick(FLOWERS), cell, 0.4, 1.0, 1.3)
			if _rng.randf() < 0.04:
				_put(_pick(PUMPKINS + SMALL), cell, 0.35, 1.0, 1.4)
		HollowMap.WATER:
			_dress_shore(cell)
		HollowMap.LANTERN:
			_put_exact("lantern_post", cell, Vector3.ZERO, _face_road(cell), 1.8)
			_scatter(TUFTS, cell, 1, 0.4)


## Reeds where the bank meets the water, lily pads out on the deep, stones on the
## sand: placed by the ground's real height, so they follow the curved shoreline.
func _dress_shore(cell: Vector2i) -> void:
	for i in 18:
		var p := (
			Vector2(cell.x - 0.5, cell.y - 0.5) + Vector2(_rng.randf() * 2.0, _rng.randf() * 2.0)
		)
		var h := terrain.height_at(p)
		var roll := _rng.randf()
		var at := Vector3(p.x, h, p.y)
		var owner := map.cell_at(at)
		if h > -0.2 and h < -0.04 and roll < 0.55:
			_put_at(_pick(REEDS), owner, at, _rng.randf_range(0.9, 1.35))
		elif h < -0.38 and roll < 0.05:
			_put_at(
				_pick(LILIES),
				owner,
				Vector3(p.x, Terrain.WATER_LEVEL + 0.003, p.y),
				_rng.randf_range(0.9, 1.4)
			)
		elif h > -0.04 and h < -0.002 and roll < 0.3:
			_put_at(_pick(ROCKS), owner, at, _rng.randf_range(0.5, 0.9))


func _put_at(name: String, owner: Vector2i, at: Vector3, s: float) -> void:
	var basis := Basis(Vector3.UP, _rng.randf_range(0, TAU)).scaled(Vector3(s, s, s))
	_add(name, owner, Transform3D(basis, at))


func _pick(names: Array) -> String:
	return names[_rng.randi() % names.size()]


func _scatter(names: Array, cell: Vector2i, count: int, spread: float) -> void:
	for i in count:
		_put(_pick(names), cell, spread, 0.9, 1.3)


func _put(
	name: String,
	cell: Vector2i,
	spread: float,
	min_scale: float,
	max_scale: float,
	offset := Vector3.ZERO
) -> void:
	var c := map.center(cell)
	if map.tile(cell) == HollowMap.HIGH:
		c.y = HollowMap.HIGH_HEIGHT - 0.02
	var pos := (
		c
		+ offset
		+ Vector3(_rng.randf_range(-spread, spread), 0, _rng.randf_range(-spread, spread))
	)
	if map.tile(cell) != HollowMap.HIGH:
		pos.y = terrain.height_at(Vector2(pos.x, pos.z)) + offset.y
	var s := _rng.randf_range(min_scale, max_scale)
	if name in TREES_GREEN or name in TREES_AUTUMN:
		s *= CROWN_SCALE
	var basis := Basis(Vector3.UP, _rng.randf_range(0, TAU)).scaled(Vector3(s, s, s))
	_add(name, cell, Transform3D(basis, pos))


func _put_exact(name: String, cell: Vector2i, offset: Vector3, yaw: float, scale := 1.0) -> void:
	_add(
		name,
		cell,
		Transform3D(
			Basis(Vector3.UP, yaw).scaled(Vector3.ONE * scale), terrain.surface(cell) + offset
		)
	)


func _add(name: String, cell: Vector2i, transform: Transform3D) -> void:
	if name.begins_with("tree_"):
		# A soft contact shadow under every tree, sized to it.
		var r := 0.62 * transform.basis.get_scale().x
		_tree_shadows.append(
			Transform3D(
				Basis.from_scale(Vector3(r * 2.0, 1.0, r * 2.0)),
				transform.origin + Vector3(0, 0.03, 0)
			)
		)
	if not _placements.has(name):
		_placements[name] = []
		_owners[name] = []
	_placements[name].append(transform)
	_owners[name].append(cell)


## Yaw that points a lantern post's arm (+X) over the nearest road cell.
func _face_road(cell: Vector2i) -> float:
	for side: Vector2i in [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.DOWN, Vector2i.UP]:
		if map.is_road(cell + side):
			return atan2(-float(side.y), float(side.x))
	return 0.0
