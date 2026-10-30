## A StyleBoxTexture painted with `texel` texels per layout pixel, drawn at layout size:
## its nine-slice margins are in texels, so it is drawn scaled.
##
## A band whose centre tiles across (the resource strip: a cap on the left, then a bar that
## repeats) is drawn one quad per tile. Godot tiles a nine-patch's centre inside one quad by
## wrapping its texture coordinates, and where they wrap the jump picks the texture's
## smallest mip for that column: with the console's mipmapped art that drew a dark hairline
## down the strip every tile (review round 2). Quads of their own never wrap.
class_name HdStyleBox
extends StyleBox

var inner: StyleBoxTexture
var texel := 1.0


func _init(source: StyleBoxTexture = null, texels := 1.0) -> void:
	inner = source if source else StyleBoxTexture.new()
	texel = texels
	for side: int in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		set_content_margin(side, inner.get_content_margin(side) / texels)


func _draw(item: RID, rect: Rect2) -> void:
	RenderingServer.canvas_item_add_set_transform(
		item, Transform2D(0.0, Vector2.ONE / texel, 0.0, Vector2.ZERO)
	)
	var area := Rect2(rect.position * texel, rect.size * texel)
	if tiles_across(area.size.x):
		_draw_tiles(item, area)
	else:
		inner.draw(item, area)
	RenderingServer.canvas_item_add_set_transform(item, Transform2D.IDENTITY)


func _get_draw_rect(rect: Rect2) -> Rect2:
	return rect.grow_individual(
		inner.expand_margin_left / texel,
		inner.expand_margin_top / texel,
		inner.expand_margin_right / texel,
		inner.expand_margin_bottom / texel
	)


## Whether a box `width` texels wide is drawn tile by tile: a horizontal band (no top or
## bottom slice) whose centre tiles and is wider than one tile.
func tiles_across(width: float) -> bool:
	if inner.texture == null or inner.axis_stretch_horizontal != StyleBoxTexture.AXIS_STRETCH_MODE_TILE:
		return false
	if inner.texture_margin_top != 0.0 or inner.texture_margin_bottom != 0.0:
		return false
	var tile := _tile()
	return tile > 0.0 and width - inner.texture_margin_left - inner.texture_margin_right > tile


func _source() -> Rect2:
	if inner.region_rect.has_area():
		return inner.region_rect
	return Rect2(Vector2.ZERO, inner.texture.get_size())


func _tile() -> float:
	return _source().size.x - inner.texture_margin_left - inner.texture_margin_right


func _draw_tiles(item: RID, area: Rect2) -> void:
	area = area.grow_individual(
		inner.expand_margin_left, inner.expand_margin_top, inner.expand_margin_right, inner.expand_margin_bottom
	)
	var source := _source()
	var left := inner.texture_margin_left
	var right := inner.texture_margin_right
	var tile := _tile()
	_quad(item, area.position.x, area, source.position.x, left)
	if inner.draw_center:
		var x := left
		var end := area.size.x - right
		while x < end:
			var width := minf(tile, end - x)
			_quad(item, area.position.x + x, area, source.position.x + left, width)
			x += width
	_quad(item, area.end.x - right, area, source.end.x - right, right)


## One quad `width` texels wide at `x` across `area`'s height, from the texture's columns
## from `from`, its whole height.
func _quad(item: RID, x: float, area: Rect2, from: float, width: float) -> void:
	if width <= 0.0:
		return
	var source := _source()
	RenderingServer.canvas_item_add_texture_rect_region(
		item,
		Rect2(x, area.position.y, width, area.size.y),
		inner.texture.get_rid(),
		Rect2(from, source.position.y, width, source.size.y),
		inner.modulate_color
	)
