## A piece of console art, painted with `texel` texels per layout pixel and drawn at its
## layout size (tiled along its width for the rail). With `hit` it stops clicks only
## where it is painted (and over its window), so the hollow stays clickable round its
## curves.
class_name ConsoleArt
extends Control

var texture: Texture2D
var texel := 1.0
var tile := false
var window := Rect2()
var _image: Image


func _init(art: Texture2D = null, texels := 1.0, hit := false) -> void:
	texture = art
	texel = texels
	mouse_filter = Control.MOUSE_FILTER_STOP if hit else Control.MOUSE_FILTER_IGNORE
	if art == null:
		return
	size = art.get_size() / texels
	if hit:
		_image = art.get_image()
		if _image and _image.is_compressed():
			_image.decompress()


func _draw() -> void:
	if texture == null:
		return
	if tile:
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE / texel)
		draw_texture_rect(texture, Rect2(Vector2.ZERO, size * texel), true)
		draw_set_transform(Vector2.ZERO)
	else:
		draw_texture_rect(texture, Rect2(Vector2.ZERO, size), false)


func _has_point(point: Vector2) -> bool:
	if window.has_point(point):
		return true
	if _image == null:
		return Rect2(Vector2.ZERO, size).has_point(point)
	var x := int(point.x * texel)
	if tile:
		x = posmod(x, _image.get_width())
	var y := int(point.y * texel)
	if x < 0 or y < 0 or x >= _image.get_width() or y >= _image.get_height():
		return false
	return _image.get_pixel(x, y).a > 0.7
