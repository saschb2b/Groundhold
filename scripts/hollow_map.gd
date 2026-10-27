## The tile map: parses data/hollow.txt and answers questions about cells.
##
## Cell (x, z) covers world [x, x+1] x [z, z+1]; its centre is (x + 0.5, h, z + 0.5).
class_name HollowMap
extends RefCounted

const GRASS := "."
const ROAD := "#"
const SPAWN := "S"
const HEARTH := "E"
const HIGH := "^"
const WOODS := "T"
const WATER := "~"
const MEADOW := ","
const LANTERN := "L"

const HIGH_HEIGHT := 0.9
const ROAD_HEIGHT := 0.0
const WATER_BED := -0.4

var width := 0
var depth := 0
var rows: PackedStringArray = []
var spawn := Vector2i(-1, -1)
var hearth := Vector2i(-1, -1)
## Cells from spawn to hearth, in walking order.
var path_cells: Array[Vector2i] = []


static func load_file(file_path: String) -> HollowMap:
	var map := HollowMap.new()
	map.parse(FileAccess.get_file_as_string(file_path))
	return map


func parse(text: String) -> void:
	rows.clear()
	for line in text.split("\n"):
		var row := line.strip_edges(false, true)
		if row.is_empty() or row.begins_with("#"):
			continue
		rows.append(row)
	depth = rows.size()
	width = rows[0].length() if depth > 0 else 0
	for z in depth:
		for x in width:
			match tile(Vector2i(x, z)):
				SPAWN:
					spawn = Vector2i(x, z)
				HEARTH:
					hearth = Vector2i(x, z)
	path_cells = _trace_road()


func inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < width and cell.y < depth


func tile(cell: Vector2i) -> String:
	if not inside(cell):
		return HIGH
	var row := rows[cell.y]
	return row[cell.x] if cell.x < row.length() else HIGH


func is_road(cell: Vector2i) -> bool:
	return tile(cell) in [ROAD, SPAWN, HEARTH]


func buildable(cell: Vector2i) -> bool:
	return tile(cell) == GRASS


func height(cell: Vector2i) -> float:
	match tile(cell):
		HIGH:
			return HIGH_HEIGHT
		WATER:
			return WATER_BED
		ROAD, SPAWN, HEARTH:
			return ROAD_HEIGHT
	return 0.0


func center(cell: Vector2i) -> Vector3:
	return Vector3(cell.x + 0.5, maxf(height(cell), 0.0), cell.y + 0.5)


func cell_at(world: Vector3) -> Vector2i:
	return Vector2i(floori(world.x), floori(world.z))


## The road as world points at walking height, corners only.
func path_points() -> PackedVector3Array:
	var points := PackedVector3Array()
	for i in path_cells.size():
		var is_turn := (
			i == 0
			or i == path_cells.size() - 1
			or path_cells[i] - path_cells[i - 1] != path_cells[i + 1] - path_cells[i]
		)
		if is_turn:
			var p := center(path_cells[i])
			points.append(Vector3(p.x, 0.0, p.z))
	return points


## Walks the road from the spawn, always to the one unvisited road neighbour.
func _trace_road() -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	if spawn.x < 0:
		return result
	var seen := {spawn: true}
	var current := spawn
	result.append(current)
	while current != hearth:
		var next := Vector2i(-1, -1)
		for step: Vector2i in [Vector2i.RIGHT, Vector2i.DOWN, Vector2i.LEFT, Vector2i.UP]:
			var candidate := current + step
			if is_road(candidate) and not seen.has(candidate):
				next = candidate
				break
		if next.x < 0:
			push_error("road from %s ends at %s before reaching the hearth" % [spawn, current])
			break
		seen[next] = true
		result.append(next)
		current = next
	return result
