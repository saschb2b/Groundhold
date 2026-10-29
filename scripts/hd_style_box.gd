## A StyleBoxTexture painted with `texel` texels per layout pixel, drawn at layout size:
## its nine-slice margins are in texels, so it is drawn scaled.
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
	inner.draw(item, Rect2(rect.position * texel, rect.size * texel))
	RenderingServer.canvas_item_add_set_transform(item, Transform2D.IDENTITY)


func _get_draw_rect(rect: Rect2) -> Rect2:
	return rect.grow_individual(
		inner.expand_margin_left / texel,
		inner.expand_margin_top / texel,
		inner.expand_margin_right / texel,
		inner.expand_margin_bottom / texel
	)
