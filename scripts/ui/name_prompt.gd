## The first launch's one question (design 5.1): the name the others see, one field,
## prefilled with a generated name ("Curlew 42") the player may keep or change. Enter
## takes it. The rule is the server's: 1 to 16 letters, digits, spaces, _ or -.
class_name NamePrompt
extends Control

var shell: Shell
var field: LineEdit
var _hint: Label


func setup(owner: Shell) -> void:
	shell = owner
	name = "NamePrompt"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.015, 0.01, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var plate := PanelContainer.new()
	plate.name = "Plate"
	plate.add_theme_stylebox_override("panel", Shell.panel_box())
	Shell.crown(plate)
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -210
	plate.offset_right = 210
	plate.offset_top = -150
	plate.offset_bottom = -20
	plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
	plate.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	plate.add_child(box)
	var title := Shell.label("Your name on the Causeway", Shell.TITLE_FONT, 20, Shell.GOLD)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	var rule := Shell.gilt_rule(220)
	box.add_child(rule)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	box.add_child(row)
	field = LineEdit.new()
	field.name = "NameField"
	field.max_length = NetProtocol.number("name_bytes")
	field.custom_minimum_size = Vector2(0, 34)
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.text_submitted.connect(func(_t: String) -> void: accept())
	field.text_changed.connect(func(_t: String) -> void: _check())
	row.add_child(field)
	var done := Button.new()
	done.name = "Done"
	done.text = "Done"
	done.focus_mode = Control.FOCUS_NONE
	done.custom_minimum_size = Vector2(90, 34)
	done.pressed.connect(accept)
	row.add_child(done)
	_hint = Shell.label("Others see it in your party and on your plate in a match.", Shell.BODY_FONT, 12, Shell.DIM)
	_hint.name = "NameHint"
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.add_theme_constant_override("outline_size", 0)
	box.add_child(_hint)


func open() -> void:
	field.text = Session.profile.player_name
	visible = true
	field.grab_focus()
	field.caret_column = field.text.length()
	_check()


## Takes the typed name; stays open while it breaks the rule.
func accept() -> void:
	if Session.profile.set_name(field.text):
		visible = false
		field.release_focus()
	else:
		_check()


func _check() -> void:
	var ok := Profile.valid_name(field.text.strip_edges())
	_hint.text = (
		"Others see it in your party and on your plate in a match."
		if ok
		else "Use 1-16 letters, digits, spaces, _ or -"
	)
	_hint.add_theme_color_override("font_color", Shell.DIM if ok else Shell.AMBER)
