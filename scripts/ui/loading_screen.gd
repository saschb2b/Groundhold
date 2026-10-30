## Loading, the sync barrier (design 5.6, 6.6). One job: reveal the line-up, then start
## every player on the same turn. A wide plate over the Causeway with the mode, the map and
## its waves; one card per player (seat glyph and name, Builder, and the seat's state as
## the server's LOAD_STATE gives it: Connecting, a bar with its percentage, Checking,
## Ready, Slow 0:18 from 15 s on); the team's coverage row; a line that walks out, and
## from 15 s names the seat everyone waits for; from 30 s the leader's Start without Ben
## (design 6.6); and leave. The session shows it from MATCH_CONFIG until turn 0 runs, over
## the match scene building beneath it.
class_name LoadingScreen
extends CanvasLayer

## Seconds after MATCH_CONFIG when a seat still loading reads as slow (Appendix A).
const SLOW_AFTER := 15
const CARD := Vector2(180, 176)
## A card's width less its frame's content margins, the seat glyph and the gap beside it:
## the room its name has.
const NAME_INSET := 28 + 12 + 6
## Maps by their protocol id's name, as titles show them.
const MAP_NAMES := {"hollow": "Wickhollow"}

var _root: Control
var _title: Label
var _cards: HBoxContainer
var _coverage: CoverageRow
var _line: Label
var _without: Button
var _shown := []
var _bars: Array = []


func _ready() -> void:
	name = "LoadingScreen"
	layer = 30
	_root = Control.new()
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.theme = Shell.theme()
	_root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(_root)
	var backdrop := CausewayView.new()
	_root.add_child(backdrop)
	var plate := Shell.WidePlate.new()
	plate.name = "LoadingPlate"
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -500
	plate.offset_right = 500
	plate.offset_top = -230
	plate.offset_bottom = 210
	_root.add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	Shell.place(box, Rect2(40, 62, 920, 350))
	plate.add_child(box)
	_title = Shell.label("", Shell.TITLE_FONT, 22, Shell.GOLD)
	_title.name = "LoadingTitle"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_title)
	box.add_child(Shell.gilt_rule(300))
	_cards = HBoxContainer.new()
	_cards.name = "Cards"
	_cards.alignment = BoxContainer.ALIGNMENT_CENTER
	_cards.add_theme_constant_override("separation", 18)
	box.add_child(_cards)
	var covers := HBoxContainer.new()
	covers.alignment = BoxContainer.ALIGNMENT_CENTER
	covers.add_theme_constant_override("separation", 10)
	box.add_child(covers)
	var caption := Shell.caps("Team covers", 10)
	caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	covers.add_child(caption)
	_coverage = CoverageRow.new()
	covers.add_child(_coverage)
	_line = Shell.label("Walking out", Shell.BOLD_FONT, 15, Shell.TEXT)
	_line.name = "LoadingLine"
	_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_line)
	_without = Button.new()
	_without.name = "StartWithout"
	_without.focus_mode = Control.FOCUS_NONE
	_without.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_without.custom_minimum_size = Vector2(220, 34)
	_without.visible = false
	_without.pressed.connect(func() -> void: Session.start_without())
	box.add_child(_without)
	var leave := Button.new()
	leave.name = "Leave"
	leave.text = "Leave"
	leave.focus_mode = Control.FOCUS_NONE
	leave.flat = true
	leave.add_theme_font_override("font", Shell.BODY_FONT)
	leave.add_theme_font_size_override("font_size", 13)
	leave.add_theme_color_override("font_color", Shell.DIM)
	for st: String in ["normal", "hover", "pressed", "hover_pressed"]:
		leave.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	leave.position = Vector2(880, 400)
	leave.pressed.connect(func() -> void: Session.to_hub())
	plate.add_child(leave)
	refresh()


func _process(delta: float) -> void:
	refresh()
	# (the bars ease toward the reported value: the web build reports in steps)
	for bar: LoadBar in _bars:
		bar.shown = move_toward(bar.shown, bar.target, delta * 1.5)
		bar.queue_redraw()


func refresh() -> void:
	var client := Session.client
	if client == null or client.seat_list.is_empty():
		return
	var shown_mode := Session.profile.mode if client.mode == Profile.played_mode(Session.profile.mode) else client.mode
	var waves := (SimContent.WAVES[SimContent.RULES[client.mode]["waves"]] as Array).size()
	var map := NetProtocol.enum_name("maps", int(client.config.get("map", 0)))
	_title.text = "%s  ·  %s  ·  %d waves" % [
		Profile.mode_name(shown_mode).to_upper(), str(MAP_NAMES.get(map, map)).to_upper(), waves
	]
	var seats := []
	for i in client.seat_list.size():
		seats.append([client.names[i] if i < client.names.size() else "Seat %d" % (i + 1), client.seat_list[i]["builder"]])
	if seats != _shown:
		_build_cards(seats)
	var builders := []
	for s: Array in seats:
		builders.append(s[1])
	_coverage.set_builders(builders)
	var waiting := ""
	for i in _cards.get_child_count():
		var state := card_state(i)
		var card := _cards.get_child(i)
		var text: Label = card.get_node("Box/State")
		var bar: LoadBar = _bars[i]
		text.text = state
		var tone := Shell.TEXT
		if state == "Ready":
			tone = Shell.GOOD
		elif state.begins_with("Slow"):
			tone = Shell.AMBER
		elif state in ["Connecting", "Caretaker"]:
			tone = Shell.DIM
		text.add_theme_color_override("font_color", tone)
		var load: Array = client.load_states[i] if i < client.load_states.size() else [0, 0]
		bar.target = int(load[0]) / 1000.0
		bar.visible = state.ends_with("%") or (state.begins_with("Slow") and int(load[0]) > 0)
		if waiting == "" and not state in ["Ready", "Checking", "Caretaker"]:
			waiting = str(seats[i][0])
	var without := Session.start_without_name()
	_without.visible = without != ""
	_without.text = "Start without " + without
	if client.phase >= MatchClient.Phase.STARTING:
		_line.text = "The tide turns ..."
	elif waiting != "" and client.load_seconds >= SLOW_AFTER:
		_line.text = "Waiting for " + waiting
	else:
		_line.text = "Walking out"


## Seat i's card as the server's LOAD_STATE says it: "Connecting", "45%", "Checking",
## "Ready", "Slow 0:18", "Caretaker".
func card_state(i: int) -> String:
	var client := Session.client
	if client == null or i >= client.load_states.size():
		return "Connecting"
	var load: Array = client.load_states[i]
	var per_mille := int(load[0])
	var name := NetProtocol.enum_name("load_states", int(load[1]))
	var seconds := client.load_seconds
	var waiting := name in ["connecting", "loading", "slow"]
	if waiting and (name == "slow" or seconds >= SLOW_AFTER):
		return "Slow %d:%02d" % [seconds / 60, seconds % 60]
	match name:
		"loading":
			return "%d%%" % (per_mille / 10)
		"checking":
			return "Checking"
		"ready":
			return "Ready"
		"gone":
			return "Caretaker"
	return "Connecting"


## The cards as one line each, for tests: "Sascha Lamplighter Checking".
func card_lines() -> Array[String]:
	var out: Array[String] = []
	for i in _cards.get_child_count():
		var card := _cards.get_child(i)
		out.append(
			"%s %s %s" % [
				(card.get_node("Box/Who/Name") as Label).text,
				(card.get_node("Box/Builder") as Label).text,
				(card.get_node("Box/State") as Label).text,
			]
		)
	return out


func line_text() -> String:
	return _line.text


func _build_cards(seats: Array) -> void:
	_shown = seats.duplicate(true)
	for child in _cards.get_children():
		child.free()
	_bars.clear()
	for i in seats.size():
		var builder := str(seats[i][1])
		var card := PanelContainer.new()
		card.name = "Card%d" % (i + 1)
		var mine := i + 1 == Session.client.seat
		card.add_theme_stylebox_override("panel", Shell.card_box(mine))
		card.custom_minimum_size = CARD
		card.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		_cards.add_child(card)
		var box := VBoxContainer.new()
		box.name = "Box"
		box.add_theme_constant_override("separation", 4)
		card.add_child(box)
		var picture := TextureRect.new()
		picture.texture = Game.icon(str(Game.BUILDERS[builder]["glyph"]))
		picture.modulate = Game.glyph_tint(builder)
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		picture.custom_minimum_size = Vector2(0, 70)
		box.add_child(picture)
		var who := HBoxContainer.new()
		who.name = "Who"
		who.alignment = BoxContainer.ALIGNMENT_CENTER
		who.add_theme_constant_override("separation", 6)
		box.add_child(who)
		var glyph := PartyStrip.SeatGlyph.new()
		glyph.shape = PartyStrip.GLYPHS[i % 4]
		glyph.color = PartyStrip.SEAT_COLORS[i % 4]
		glyph.custom_minimum_size = Vector2(12, 12)
		glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		who.add_child(glyph)
		var name_label := Shell.label(str(seats[i][0]), Shell.BOLD_FONT, 15, PartyStrip.MINE if mine else Shell.TEXT)
		name_label.name = "Name"
		# (every card the same width: a long name ends in an ellipsis inside it)
		var room := CARD.x - NAME_INSET
		var wide := Shell.BOLD_FONT.get_string_size(name_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		name_label.custom_minimum_size.x = minf(ceilf(wide) + 1.0, room)
		name_label.clip_text = true
		name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		who.add_child(name_label)
		var title := str(SimContent.BUILDERS[builder]["title"]).trim_prefix("the ")
		var builder_label := Shell.label(title, Shell.BODY_FONT, 13, Shell.DIM)
		builder_label.name = "Builder"
		builder_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		builder_label.add_theme_constant_override("outline_size", 0)
		box.add_child(builder_label)
		var bar := LoadBar.new()
		bar.name = "Bar"
		box.add_child(bar)
		_bars.append(bar)
		var state := Shell.label("", Shell.BOLD_FONT, 14, Shell.TEXT)
		state.name = "State"
		state.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box.add_child(state)


## The console's progress bar: the painted trough (bar_trough) and, inset in it, the gold
## fill (bar_fill) as wide as the share loaded (layout.json's bar).
class LoadBar:
	extends Control
	var target := 0.0
	var shown := 0.0
	var trough: StyleBox
	var fill: StyleBox

	func _init() -> void:
		var spec: Dictionary = Shell.layout()["bar"]
		custom_minimum_size = Vector2(0, float(spec["height"]))
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		trough = Shell.piece_box("bar_trough.tres")
		fill = Shell.piece_box("bar_fill.tres")

	func _draw() -> void:
		var spec: Dictionary = Shell.layout()["bar"]
		var inset := Vector2(spec["inset"][0], spec["inset"][1])
		var r := Rect2(Vector2(4, 0), Vector2(size.x - 8, size.y))
		draw_style_box(trough, r)
		var room := r.size.x - inset.x * 2.0
		var wide := room * clampf(shown, 0.0, 1.0)
		if wide >= 2.0:
			draw_style_box(fill, Rect2(r.position + inset, Vector2(wide, float(spec["fill_height"]))))
