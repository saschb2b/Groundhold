## Reads a drawn piece of the console back from the screen, for view scenarios that need
## pixels. A headless run has none: every probe here answers as if the pixels were right.
extends RefCounted


static func _image(node: Node) -> Image:
	if DisplayServer.get_name() == "headless":
		return null
	var image := node.get_viewport().get_texture().get_image()
	return null if image == null or image.is_empty() else image


## The columns (screen x) where a strip shows a seam: in its shadow band, `rows` layout
## pixels down from its top (the shadow below the gilt edge, over the backdrop), a column
## at least `threshold` darker than the columns two pixels to either side. [] where
## nothing stands out, and in a headless run.
static func dark_columns(strip: Control, rows: Array, threshold := 0.08) -> Array:
	var image := _image(strip)
	if image == null:
		return []
	var rect := strip.get_global_rect()
	var out := []
	for row: int in rows:
		var y := int(rect.position.y) + row
		for x in range(int(rect.position.x) + 2, int(rect.end.x) - 2):
			var here := image.get_pixel(x, y).get_luminance()
			var left := image.get_pixel(x - 2, y).get_luminance()
			var right := image.get_pixel(x + 2, y).get_luminance()
			if here < minf(left, right) - threshold and not out.has(x):
				out.append(x)
	return out


var _without: Image


## The screen as it is now, to measure a piece drawn over it next (bar_fill).
func snapshot(node: Node) -> bool:
	_without = _image(node)
	return true


## A creep's health bar as drawn: the share of the bar's inner width (BAR_WIDTH across the
## screen, centred on the bar's node) that its lit fill covers, on the row where the most
## of it shows within the bar's height either side. A fill pixel is one the bar changed
## since snapshot() (taken with the bar hidden) to a saturated green to red; the trough
## is near black. -1 in a headless run.
func bar_fill(creep: Creep) -> float:
	var image := _image(creep)
	if image == null or _without == null:
		return -1.0
	var camera := creep.get_viewport().get_camera_3d()
	var centre: Vector3 = creep._bar_root.global_position
	var right := camera.global_transform.basis.x * (Creep.BAR_WIDTH * 0.5)
	var up := camera.global_transform.basis.y * 0.09
	var left_end := camera.unproject_position(centre - right)
	var right_end := camera.unproject_position(centre + right)
	var width := right_end.x - left_end.x
	var top := mini(int(camera.unproject_position(centre + up).y), int(camera.unproject_position(centre - up).y))
	var bottom := maxi(int(camera.unproject_position(centre + up).y), int(camera.unproject_position(centre - up).y))
	var best := 0
	for y in range(top, bottom + 1):
		var lit := 0
		for x in range(int(left_end.x - width * 0.3), int(right_end.x + width * 0.3) + 1):
			var c := image.get_pixel(x, y)
			var was := _without.get_pixel(x, y)
			var changed := absf(c.r - was.r) + absf(c.g - was.g) + absf(c.b - was.b) > 0.15
			if changed and maxf(c.r, c.g) - minf(c.r, minf(c.g, c.b)) > 0.3 and maxf(c.r, c.g) > 0.45:
				lit += 1
		best = maxi(best, lit)
	return best / width
