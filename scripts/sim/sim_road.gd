## A hollow's ground as the simulation sees it: which cells take a tower, and the road
## from the Welling to the Holdfast as integer corner points (millimetres, at tile
## centres) with cumulative lengths in micrometres. Parsed from the same map text as the
## view's HollowMap, without leaving ints.
##
## Range checks never take square roots per tick: intervals() turns a tower's circle
## into stretches of road distance once, when the tower is built or forked.
@warning_ignore_start("integer_division")
class_name SimRoad
extends RefCounted

const CELL_MM := 1000
const TILE_GRASS := 1
const TILE_ROAD := 2
const TILE_OTHER := 0

var width := 0
var depth := 0
## One byte per cell, row by row: TILE_GRASS (buildable), TILE_ROAD or TILE_OTHER.
var tiles := PackedByteArray()
var spawn_x := -1
var spawn_z := -1
var holdfast_x := -1
var holdfast_z := -1
## Cells from the Welling to the Holdfast in walking order, as x and z.
var path_x := PackedInt32Array()
var path_z := PackedInt32Array()
## Corners of the road (millimetres) and the road distance at each (micrometres).
var corner_x := PackedInt64Array()
var corner_z := PackedInt64Array()
var cum_um := PackedInt64Array()
var length_um := 0


static func parse(text: String) -> SimRoad:
	var road := SimRoad.new()
	road._parse(text)
	return road


func inside(x: int, z: int) -> bool:
	return x >= 0 and z >= 0 and x < width and z < depth


func tile(x: int, z: int) -> int:
	return tiles[z * width + x] if inside(x, z) else TILE_OTHER


func buildable(x: int, z: int) -> bool:
	return tile(x, z) == TILE_GRASS


## A cell's centre in millimetres.
static func centre_mm(cell: int) -> int:
	return cell * CELL_MM + CELL_MM / 2


## The segment a road distance lies on: the index of its far corner (1 to n - 1).
func segment_at(dist_um: int) -> int:
	var n := cum_um.size()
	if dist_um <= 0:
		return 1
	if dist_um >= length_um:
		return n - 1
	# Binary search for the first corner at or past the distance.
	var lo := 1
	var hi := n - 1
	while lo < hi:
		var mid := (lo + hi) / 2
		if cum_um[mid] >= dist_um:
			hi = mid
		else:
			lo = mid + 1
	return lo


## The x coordinate (millimetres) of the point at a road distance.
func x_at(dist_um: int) -> int:
	var i := segment_at(dist_um)
	return _along(corner_x[i - 1], corner_x[i], dist_um - cum_um[i - 1])


## The z coordinate (millimetres) of the point at a road distance.
func z_at(dist_um: int) -> int:
	var i := segment_at(dist_um)
	return _along(corner_z[i - 1], corner_z[i], dist_um - cum_um[i - 1])


## The stretches of road within r millimetres of (cx, cz), as sorted, merged pairs of
## road distances [from, to, from, to, ...] in micrometres, both ends inside. Segments
## are axis-aligned, so each stretch is the chord isqrt(r^2 - d^2) either side of the
## foot of the perpendicular; the floor keeps every point inside, losing under 1 mm.
func intervals(cx: int, cz: int, r: int) -> PackedInt64Array:
	var out := PackedInt64Array()
	for i in range(1, corner_x.size()):
		var ax := corner_x[i - 1]
		var az := corner_z[i - 1]
		var bx := corner_x[i]
		var bz := corner_z[i]
		var lo := 0
		var hi := 0
		if az == bz:
			var d := absi(az - cz)
			if d > r:
				continue
			var half := SimMath.isqrt(r * r - d * d)
			var x0 := maxi(mini(ax, bx), cx - half)
			var x1 := mini(maxi(ax, bx), cx + half)
			if x0 > x1:
				continue
			lo = cum_um[i - 1] + absi(x0 - ax) * 1000
			hi = cum_um[i - 1] + absi(x1 - ax) * 1000
		else:
			var d := absi(ax - cx)
			if d > r:
				continue
			var half := SimMath.isqrt(r * r - d * d)
			var z0 := maxi(mini(az, bz), cz - half)
			var z1 := mini(maxi(az, bz), cz + half)
			if z0 > z1:
				continue
			lo = cum_um[i - 1] + absi(z0 - az) * 1000
			hi = cum_um[i - 1] + absi(z1 - az) * 1000
		if lo > hi:
			var swap := lo
			lo = hi
			hi = swap
		# Segments run in walking order, so stretches arrive sorted; join touching ones.
		var n := out.size()
		if n > 0 and lo <= out[n - 1]:
			out[n - 1] = maxi(out[n - 1], hi)
		else:
			out.append(lo)
			out.append(hi)
	return out


## Whether a road distance lies in one of the stretches intervals() returned.
static func covers(stretches: PackedInt64Array, dist_um: int) -> bool:
	var i := 0
	var n := stretches.size()
	while i < n:
		if dist_um < stretches[i]:
			return false
		if dist_um <= stretches[i + 1]:
			return true
		i += 2
	return false


## One coordinate of a point a distance along an axis-aligned segment, in millimetres;
## the coordinate the segment does not run along stays put.
static func _along(from_mm: int, to_mm: int, offset_um: int) -> int:
	if to_mm > from_mm:
		return from_mm + offset_um / 1000
	if to_mm < from_mm:
		return from_mm - offset_um / 1000
	return from_mm


func _parse(text: String) -> void:
	var rows := PackedStringArray()
	for line in text.split("\n"):
		var row := line.strip_edges(false, true)
		if row.is_empty() or row.begins_with("#"):
			continue
		rows.append(row)
	depth = rows.size()
	width = rows[0].length() if depth > 0 else 0  # sim-lint: allow length() a String's length, an int
	tiles.resize(width * depth)
	for z in depth:
		var row := rows[z]
		for x in width:
			var ch := row[x] if x < row.length() else "^"  # sim-lint: allow length() a String's
			var kind := TILE_OTHER
			match ch:
				".":
					kind = TILE_GRASS
				"#":
					kind = TILE_ROAD
				"S":
					kind = TILE_ROAD
					spawn_x = x
					spawn_z = z
				"E":
					kind = TILE_ROAD
					holdfast_x = x
					holdfast_z = z
			tiles[z * width + x] = kind
	_trace()
	_corners()


## Walks the road from the Welling, always to the one unvisited road neighbour, trying
## right, down, left and up in that order (the view's HollowMap walks the same way).
func _trace() -> void:
	if spawn_x < 0:
		return
	var seen := PackedByteArray()
	seen.resize(width * depth)
	var x := spawn_x
	var z := spawn_z
	seen[z * width + x] = 1
	path_x.append(x)
	path_z.append(z)
	var dx := [1, 0, -1, 0]
	var dz := [0, 1, 0, -1]
	while not (x == holdfast_x and z == holdfast_z):
		var moved := false
		for k in 4:
			var nx: int = x + dx[k]
			var nz: int = z + dz[k]
			if tile(nx, nz) == TILE_ROAD and seen[nz * width + nx] == 0:
				x = nx
				z = nz
				moved = true
				break
		if not moved:
			push_error("road from the Welling ends at %d,%d before the Holdfast" % [x, z])
			return
		seen[z * width + x] = 1
		path_x.append(x)
		path_z.append(z)


func _corners() -> void:
	var n := path_x.size()
	var total := 0
	for i in n:
		var turn := (
			i == 0
			or i == n - 1
			or (path_x[i] - path_x[i - 1] != path_x[i + 1] - path_x[i])
			or (path_z[i] - path_z[i - 1] != path_z[i + 1] - path_z[i])
		)
		if not turn:
			continue
		var px := centre_mm(path_x[i])
		var pz := centre_mm(path_z[i])
		var k := corner_x.size()
		if k > 0:
			total += (absi(px - corner_x[k - 1]) + absi(pz - corner_z[k - 1])) * 1000
		corner_x.append(px)
		corner_z.append(pz)
		cum_um.append(total)
	length_um = total
