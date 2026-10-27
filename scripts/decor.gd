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

var map: HollowMap
var _rng := RandomNumberGenerator.new()
## model name -> Array[Transform3D]
var _placements := {}
## model name -> Array[Vector2i]: which cell each instance belongs to
var _owners := {}
var _multimeshes := {}
var _cleared := {}


func build(source: HollowMap) -> void:
	map = source
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
			for i in _rng.randi_range(1, 2):
				_put(_pick(TREES_GREEN + TREES_AUTUMN + TREES_AUTUMN + PINES), cell, 0.3, 1.1, 1.5)
			_put(_pick(BUSHES), cell, 0.4, 0.8, 1.2)
			_scatter(TUFTS, cell, 2, 0.45)
		HollowMap.HIGH:
			if _rng.randf() < 0.55:
				_put(_pick(PINES + TREES_AUTUMN), cell, 0.3, 1.0, 1.45)
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
			for side: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				if map.tile(cell + side) != HollowMap.WATER and _rng.randf() < 0.5:
					var edge := Vector3(side.x, 0, side.y) * 0.45
					_put(_pick(TUFTS + ROCKS), cell, 0.1, 0.8, 1.2, edge + Vector3(0, -0.12, 0))
		HollowMap.LANTERN:
			_put_exact("lantern_post", cell, Vector3.ZERO, _face_road(cell), 1.8)
			_scatter(TUFTS, cell, 1, 0.4)


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
	var s := _rng.randf_range(min_scale, max_scale)
	var basis := Basis(Vector3.UP, _rng.randf_range(0, TAU)).scaled(Vector3(s, s, s))
	_add(name, cell, Transform3D(basis, pos))


func _put_exact(name: String, cell: Vector2i, offset: Vector3, yaw: float, scale := 1.0) -> void:
	_add(
		name,
		cell,
		Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * scale), map.center(cell) + offset)
	)


func _add(name: String, cell: Vector2i, transform: Transform3D) -> void:
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
