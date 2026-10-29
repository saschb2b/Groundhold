## The resource strip: stops clicks only where its art is painted, not under the
## transparent curl of its cap.
class_name ResourceStrip
extends PanelContainer

var texel := 1.0
var cap := 0.0
var _image: Image


func setup(box: StyleBoxTexture, texels: float, cap_width: float) -> void:
	texel = texels
	cap = cap_width
	add_theme_stylebox_override("panel", HdStyleBox.new(box, texels))
	mouse_filter = Control.MOUSE_FILTER_STOP
	_image = box.texture.get_image()
	if _image and _image.is_compressed():
		_image.decompress()


func _has_point(point: Vector2) -> bool:
	if _image == null or not Rect2(Vector2.ZERO, size).has_point(point):
		return false
	# Past the cap the bar is the same in every column.
	var x := mini(int(minf(point.x, cap + 2.0) * texel), _image.get_width() - 1)
	var y := mini(int(point.y * texel), _image.get_height() - 1)
	return _image.get_pixel(x, y).a > 0.5


## A soft round light to lay behind an icon on the strip.
static func glow(color: Color) -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.set_color(0, Color(color, 0.6))
	gradient.set_color(1, Color(color, 0.0))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(0.5, 0.0)
	texture.width = 64
	texture.height = 64
	return texture
