## The match's Esc menu (design 5.1: "a small Esc menu"; 5.4: Try "with Esc pause and
## restart"). Esc opens it when nothing is being placed, signalled or selected, and closes
## it again. One small plate on the console's panel: Resume; Restart, for a match played
## offline (Play alone, a Try), which starts the same match over; and Leave to hub, which
## online tells the server (Session.to_hub sends LEAVE_MATCH, the caretaker takes the
## seat). Offline the match waits while the plate is up; online it plays on, and the
## plate says so.
class_name MatchMenu
extends CanvasLayer

var main: Node
var _root: Control
var _title: Label
var _line: Label
var _restart: Button


func setup(scene: Node) -> void:
	main = scene
	name = "MatchMenu"
	layer = 40
	_root = Control.new()
	_root.name = "MenuRoot"
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.theme = Shell.theme()
	_root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.015, 0.01, 0.4)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(dim)
	var plate := PanelContainer.new()
	plate.name = "MenuPlate"
	plate.add_theme_stylebox_override("panel", Shell.panel_box())
	Shell.crown(plate)
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -150
	plate.offset_right = 150
	plate.offset_top = -150
	plate.offset_bottom = 60
	plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
	plate.grow_vertical = Control.GROW_DIRECTION_BOTH
	_root.add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	plate.add_child(box)
	_title = Shell.label("Paused", Shell.TITLE_FONT, 22, Shell.GOLD)
	_title.name = "MenuTitle"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_title)
	box.add_child(Shell.gilt_rule(200))
	_line = Shell.label("", Shell.BODY_FONT, 13, Shell.DIM)
	_line.name = "MenuLine"
	_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_line.add_theme_constant_override("outline_size", 0)
	box.add_child(_line)
	box.add_child(_button("MenuResume", "Resume", close))
	_restart = _button("MenuRestart", "Restart", func() -> void: main.restart())
	box.add_child(_restart)
	box.add_child(_button("MenuLeave", "Leave to hub", func() -> void: main.leave_to_hub()))
	visible = false


func open() -> void:
	var online: bool = main.get("client") != null
	_title.text = "Menu" if online else "Paused"
	_line.text = "The match plays on" if online else "The match waits for you"
	_restart.visible = not online
	visible = true


func close() -> void:
	visible = false


## What the plate offers now, for tests: "Resume", "Restart", "Leave to hub".
func choices() -> Array[String]:
	var out: Array[String] = []
	for name: String in ["MenuResume", "MenuRestart", "MenuLeave"]:
		var button := _root.find_child(name, true, false) as Button
		if button and button.visible:
			out.append(button.text)
	return out


func _input(event: InputEvent) -> void:
	if not visible:
		return
	var key := event as InputEventKey
	if key == null:
		return
	if key.pressed and not key.echo and KEY_ESCAPE in [key.physical_keycode, key.keycode]:
		close()
	# (while the plate is up no key reaches the battlefield: no orders behind it)
	get_viewport().set_input_as_handled()


func _button(button_name: String, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.name = button_name
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(0, 38)
	button.pressed.connect(action)
	return button
