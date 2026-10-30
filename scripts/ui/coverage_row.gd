## The team coverage row (design 3.3, 5.2): the four checks' glyphs in CHECK_IDS order,
## each lit when any of the party's Builders is strong against it
## (SimContent.team_covers), dim otherwise, with a tooltip that says who covers it or that
## nobody here does. The hub's arch, the Builders screen and the loading screen show it.
class_name CoverageRow
extends HBoxContainer

const LIT := Color(1, 1, 1, 1)
const UNLIT := Color(0.55, 0.5, 0.44, 0.45)

## The Builders counted (SimContent ids; duplicates count once).
var builders: Array = []
## Which checks to show (all four unless a screen shows strong and weak apart).
var only: Array = []
var icon_size := 20.0
var with_names := true
var _cells := {}


func _init(icon_px := 20.0, names := true) -> void:
	icon_size = icon_px
	with_names = names
	name = "CoverageRow"
	mouse_filter = Control.MOUSE_FILTER_PASS
	add_theme_constant_override("separation", 10 if names else 6)


func set_builders(list: Array, shown: Array = []) -> void:
	builders = list.duplicate()
	only = shown.duplicate()
	if _cells.is_empty():
		_build()
	var covered := SimContent.team_covers(builders)
	for check: String in SimContent.CHECK_IDS:
		var cell: Dictionary = _cells[check]
		var on := covered.has(check)
		(cell["box"] as Control).visible = only.is_empty() or only.has(check)
		(cell["icon"] as TextureRect).modulate = LIT if on else UNLIT
		if cell.has("name"):
			(cell["name"] as Label).add_theme_color_override("font_color", Shell.GOLD if on else Color("#6f6455"))
		(cell["box"] as Control).tooltip_text = tip(check)


## The checks lit, in CHECK_IDS order (for tests and the loading screen).
func lit() -> Array:
	return SimContent.team_covers(builders)


## The checks shown dim.
func dim() -> Array:
	var covered := lit()
	return SimContent.CHECK_IDS.filter(func(c: String) -> bool: return not covered.has(c))


## What hovering a check says.
func tip(check: String) -> String:
	var shown: Dictionary = Game.CHECKS[check]
	var who := []
	for b: Variant in builders:
		var id := str(b)
		if SimContent.BUILDERS.has(id) and SimContent.covers(id, check):
			var title := str(SimContent.BUILDERS[id]["title"])
			var short := title.trim_prefix("the ").capitalize()
			if not who.has(short):
				who.append(short)
	var head := "%s · %s" % [shown["name"], shown["glyph"]]
	if who.is_empty():
		return "%s\nNobody here is strong against %s" % [head, shown["name"]]
	return "%s\nStrong: %s" % [head, ", ".join(who)]


func _build() -> void:
	for check: String in SimContent.CHECK_IDS:
		var shown: Dictionary = Game.CHECKS[check]
		var box := HBoxContainer.new()
		box.name = "Check_" + check
		box.mouse_filter = Control.MOUSE_FILTER_STOP
		box.add_theme_constant_override("separation", 3)
		add_child(box)
		var icon := TextureRect.new()
		icon.name = "Icon"
		icon.texture = Game.icon(str(shown["icon"]))
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.custom_minimum_size = Vector2(icon_size, icon_size)
		icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.add_child(icon)
		var cell := {"box": box, "icon": icon}
		if with_names:
			var caption := Shell.caps(str(shown["name"]), 10)
			caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			box.add_child(caption)
			cell["name"] = caption
		_cells[check] = cell
