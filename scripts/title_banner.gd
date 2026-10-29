## A title over the hollow: a soft dark band fitted to the title and, under it, a gilt
## rule with a small diamond in its middle. The console painter paints the band, the
## rule's left half (mirrored for the right) and the diamond; `art` is the "banner"
## entry of its layout.json. Anchor it at the top centre; it sizes itself to each title.
class_name TitleBanner
extends Control

## How far the rule runs past the title on each side, the band's soft margin past the
## rule, and the band's widest, which keeps it clear of the resource strip.
const RULE_PAST := 48.0
const BAND_PAST := 40.0
const BAND_MAX := 520.0

var title: Label
var _art: Dictionary
var _band: TextureRect
var _rule: Array[TextureRect] = []
var _gem: TextureRect
var _tween: Tween


func setup(art: Dictionary, folder: String, label: Label) -> void:
	_art = art
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_band = _stretched(folder + "banner.png")
	add_child(_band)
	for flip: bool in [false, true]:
		var rule := _stretched(folder + "banner_rule.png")
		rule.flip_h = flip
		add_child(rule)
		_rule.append(rule)
	_gem = _stretched(folder + "banner_gem.png")
	add_child(_gem)
	title = label
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	add_child(title)


## Shows `text` for `hold` seconds, then fades it out.
func show_title(text: String, hold: float) -> void:
	title.text = text
	_fit(text)
	visible = true
	modulate.a = 1.0
	if _tween:
		_tween.kill()
	_tween = create_tween()
	_tween.tween_interval(hold)
	_tween.tween_property(self, "modulate:a", 0.0, 0.6)
	_tween.tween_callback(func() -> void: visible = false)


func hide_title() -> void:
	if _tween:
		_tween.kill()
	visible = false


## Sizes the band to the title and lays the rule 4 px under its baseline, running
## RULE_PAST beyond the title on each side.
func _fit(text: String) -> void:
	var font := title.get_theme_font("font")
	var font_size := title.get_theme_font_size("font_size")
	var band_h := float(_art["band"][1])
	var title_w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var width := minf(title_w + 2 * (RULE_PAST + BAND_PAST), BAND_MAX)
	var half := minf(title_w * 0.5 + RULE_PAST, width * 0.5 - BAND_PAST * 0.5)
	offset_left = -width * 0.5
	offset_right = width * 0.5
	offset_bottom = offset_top + band_h
	_place(_band, Rect2(0, 0, width, band_h))
	_place(title, Rect2(0, 0, width, band_h))
	var ascent := font.get_ascent(font_size)
	var baseline := (band_h - ascent - font.get_descent(font_size)) * 0.5 + ascent
	# The rule's art carries its gilt line one pixel below its top edge.
	var rule_h := float(_art["rule"][1])
	var gem := Vector2(_art["gem"][0], _art["gem"][1])
	var mid := width * 0.5
	var y := baseline + 3.0
	_place(_rule[0], Rect2(mid - half, y, half - gem.x * 0.4, rule_h))
	_place(_rule[1], Rect2(mid + gem.x * 0.4, y, half - gem.x * 0.4, rule_h))
	_place(_gem, Rect2(Vector2(mid, y + 1.75) - gem * 0.5, gem))


static func _place(control: Control, rect: Rect2) -> void:
	control.position = rect.position
	control.size = rect.size


static func _stretched(path: String) -> TextureRect:
	var rect := TextureRect.new()
	rect.texture = load(path)
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_SCALE
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect
