## The match's Esc menu (design 5.1: "a small Esc menu"; 5.4: Try "with Esc pause and
## restart"). Esc opens it when nothing is being placed, signalled or selected, and closes
## it again. One small plate on the console's panel: Resume; Restart, for a match played
## offline (Play alone, a Try), which starts the same match over; and Leave to hub, which
## online tells the server (Session.to_hub sends LEAVE_MATCH, the caretaker takes the
## seat). Offline the match waits while the plate is up; online it plays on, and the
## plate says so.
##
## Restart and Leave to hub end the match being played, so each asks first (a playtest lost
## a whole match to one stray click on Leave to hub): the plate turns into the question,
## "Leave the match?" or "Restart the match?", with what it costs in one line, the answer
## that ends the match on the first row and Stay on the second. No answer stands where the
## asking button stood, so a second stray click there ends nothing. Stay, Esc, Enter and
## Space go back to the menu.
##
## Under the title the plate names the match played, the mode with its level where it is not
## Normal (M8, design 2.6): "High Water · Hard · Wickhollow".
class_name MatchMenu
extends CanvasLayer

## The question's title, its line (offline, online) and the answer that ends the match, by
## what is asked.
const ASKS := {
	"leave": {
		"title": "Leave the match?",
		"line": ["This match ends here", "The caretaker plays your seat to the end"],
		"answer": "Leave the match",
	},
	"restart": {
		"title": "Restart the match?",
		"line": ["It starts again from the first wave", "It starts again from the first wave"],
		"answer": "Restart the match",
	},
}
## The answer that ends the match, in the toll's red, apart from the menu's gold.
const ENDS := Color("#ff9a7a")
## The buttons in the plate's order, top to bottom (only some show at once).
const BUTTONS := ["MenuConfirm", "MenuResume", "MenuRestart", "MenuLeave", "MenuStay"]

var main: Node
var _root: Control
var _title: Label
var _match: Label
var _line: Label
var _restart: Button
var _confirm: Button
var _stay: Button
## What the plate asks now ("leave", "restart"), or "" while it offers the menu.
var _asking := ""


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
	# (its top stands still and it grows downward, so every state lays its rows at the same
	# heights: a question's answers sit where Resume and Restart stood, never over Restart or
	# Leave to hub)
	plate.offset_top = -171
	plate.offset_bottom = 60
	plate.grow_horizontal = Control.GROW_DIRECTION_BOTH
	plate.grow_vertical = Control.GROW_DIRECTION_END
	_root.add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	plate.add_child(box)
	_title = Shell.label("Paused", Shell.TITLE_FONT, 22, Shell.GOLD)
	_title.name = "MenuTitle"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_title)
	_match = Shell.label("", Shell.BOLD_FONT, 12, Shell.DIM)
	_match.name = "MenuMatch"
	_match.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_match.add_theme_constant_override("outline_size", 0)
	box.add_child(_match)
	box.add_child(Shell.gilt_rule(200))
	_line = Shell.label("", Shell.BODY_FONT, 13, Shell.DIM)
	_line.name = "MenuLine"
	_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_line.add_theme_constant_override("outline_size", 0)
	box.add_child(_line)
	_confirm = _button("MenuConfirm", "", _answer)
	for state: String in ["font_color", "font_hover_color", "font_pressed_color"]:
		_confirm.add_theme_color_override(state, ENDS.lightened(0.25) if state == "font_hover_color" else ENDS)
	box.add_child(_confirm)
	box.add_child(_button("MenuResume", "Resume", close))
	_restart = _button("MenuRestart", "Restart", ask.bind("restart"))
	box.add_child(_restart)
	box.add_child(_button("MenuLeave", "Leave to hub", ask.bind("leave")))
	_stay = _button("MenuStay", "Stay", stay)
	box.add_child(_stay)
	visible = false


func open() -> void:
	_asking = ""
	_show()
	visible = true


func close() -> void:
	_asking = ""
	visible = false


## Restart ("restart", offline only) or Leave to hub ("leave") was pressed: the plate asks
## before the match ends.
func ask(what: String) -> void:
	if not ASKS.has(what) or (what == "restart" and _online()):
		return
	_asking = what
	_show()


## Stay: no, back to the menu.
func stay() -> void:
	_asking = ""
	_show()


## The match played as the plate names it (M8): the mode, its level where it is not Normal,
## and the map: "High Water · Hard · Wickhollow"; "" before the match stands.
func match_line() -> String:
	var sim: SimMatch = main.get("sim") if main else null
	if sim == null:
		return ""
	var spec: Variant = main.get("_spec")
	var shown := str((spec as Dictionary).get("shown_mode", sim.mode)) if spec is Dictionary else sim.mode
	var words := Game.mode_words(Profile.mode_name(shown), MatchRules.level_played(sim.rules))
	var script := main.get_script() as Script
	var map := str(script.get_script_constant_map().get("MAP_NAME", "")) if script else ""
	return "%s · %s" % [words, map] if map != "" else words


## What the plate asks now, for tests: "leave", "restart", or "" while it offers the menu.
func asking() -> String:
	return _asking


## What the plate offers now, top to bottom, for tests: "Resume", "Restart", "Leave to
## hub"; while it asks, "Leave the match" (or "Restart the match") and "Stay".
func choices() -> Array[String]:
	var out: Array[String] = []
	for button_name: String in BUTTONS:
		var button := _root.find_child(button_name, true, false) as Button
		if button and button.visible:
			out.append(button.text)
	return out


func _input(event: InputEvent) -> void:
	if not visible:
		return
	var key := event as InputEventKey
	if key == null:
		return
	if key.pressed and not key.echo:
		var codes := [key.physical_keycode, key.keycode]
		if KEY_ESCAPE in codes:
			if _asking != "":
				stay()  # (Esc steps back one: from the question to the menu, then out)
			else:
				close()
		elif _asking != "" and (KEY_ENTER in codes or KEY_KP_ENTER in codes or KEY_SPACE in codes):
			stay()  # (Stay is the question's default)
	# (while the plate is up no key reaches the battlefield: no orders behind it)
	get_viewport().set_input_as_handled()


## The question answered yes: the match ends as asked.
func _answer() -> void:
	var what := _asking
	_asking = ""
	match what:
		"leave":
			main.leave_to_hub()
		"restart":
			main.restart()


func _online() -> bool:
	return main.get("client") != null


## The plate as it stands: the menu, or the question.
func _show() -> void:
	_match.text = match_line()
	var online := _online()
	var asked := _asking != ""
	if asked:
		var ask_now: Dictionary = ASKS[_asking]
		_title.text = str(ask_now["title"])
		_line.text = str(ask_now["line"][1 if online else 0])
		_confirm.text = str(ask_now["answer"])
	else:
		_title.text = "Menu" if online else "Paused"
		_line.text = "The match plays on" if online else "The match waits for you"
	_confirm.visible = asked
	_stay.visible = asked
	for button_name: String in ["MenuResume", "MenuLeave"]:
		(_root.find_child(button_name, true, false) as Control).visible = not asked
	_restart.visible = not asked and not online


func _button(button_name: String, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.name = button_name
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(0, 38)
	button.pressed.connect(action)
	return button
