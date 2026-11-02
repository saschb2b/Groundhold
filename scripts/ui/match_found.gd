## Match Found (design 5.5): the queue found strangers for the party, and everyone has the
## server's 15 s to accept. The plate names the map, the mode, the players and how long a
## match runs; a pip per seat lights as its player accepts ("2 of 4"); the bar and the
## seconds count the server's window down (MATCH_FOUND's ms_left, the client only draws
## it). Accept (Enter) and decline (Esc) answer with ACCEPT. A sound when it opens and a
## soft tick in the last 3 s; the desktop window asks for attention and the browser flashes
## the page title (WebBridge). The session shows it from MATCH_FOUND until the match forms
## (MATCH_CONFIG) or dissolves (QUEUE_STATE): everyone accepts, Loading; a decline or the
## time running out, back to the hub, or to the queue's front ("A player didn't accept. You
## keep your place."). A duel's plate says "1v1" for its two players (M7), with two pips.
## (M8) A level other than Normal follows the mode: "High Water · Hard · 4 players · ~13 min".
##
## The two sounds are track B's (sfx/match_found.wav, sfx/countdown_tick.wav): each loads
## only where it exists, so the overlay works without them.
extends CanvasLayer

const SOUND := "res://sfx/match_found.wav"
const TICK := "res://sfx/countdown_tick.wav"
## The last seconds that tick (design 5.5).
const TICK_FROM := 3
const MAP_NAME := "Wickhollow"
## About how long a match of each mode runs, for the plate's line (design 1.2, 1.3).
const MINUTES := {"high_water": 13, "tide_race": 13, "classic": 9, "undertow": 15}
const PLATE := Vector2(620, 268)
const FLASH := "Match found: Groundhold"

var _title: Label
var _line: Label
var _pips: Pips
var _count: Label
var _bar: Bar
var _seconds: Label
var _accept: Button
var _decline: Button
var _player: AudioStreamPlayer
var _tick: AudioStream
var _ticked := -1
var _bridge: WebBridge


func _ready() -> void:
	name = "MatchFound"
	layer = 25
	var root := Control.new()
	root.name = "MatchFoundRoot"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.theme = Shell.theme()
	root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(root)
	var scrim := ColorRect.new()
	scrim.name = "Scrim"
	scrim.color = Color(0.02, 0.02, 0.03, 0.55)
	scrim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scrim.mouse_filter = Control.MOUSE_FILTER_STOP  # (the hub beneath waits for the answer)
	root.add_child(scrim)
	var plate := Shell.WidePlate.new()
	plate.name = "MatchFoundPlate"
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -PLATE.x * 0.5
	plate.offset_right = PLATE.x * 0.5
	plate.offset_top = -PLATE.y * 0.5 - 40
	plate.offset_bottom = PLATE.y * 0.5 - 40
	root.add_child(plate)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 6)
	Shell.place(box, Rect2(40, 46, PLATE.x - 80, PLATE.y - 70))
	plate.add_child(box)
	_title = _centred(Shell.label("MATCH FOUND", Shell.TITLE_FONT, 24, Shell.GOLD))
	_title.name = "MatchFoundTitle"
	box.add_child(_title)
	var where := _centred(Shell.label("The tide turns at %s" % MAP_NAME, Shell.BODY_FONT, 14, Shell.TEXT))
	where.name = "MatchFoundWhere"
	box.add_child(where)
	_line = _centred(Shell.label("", Shell.BOLD_FONT, 14, Shell.DIM))
	_line.name = "MatchFoundLine"
	box.add_child(_line)
	var seats := HBoxContainer.new()
	seats.alignment = BoxContainer.ALIGNMENT_CENTER
	seats.add_theme_constant_override("separation", 10)
	box.add_child(seats)
	_pips = Pips.new()
	_pips.name = "MatchFoundPips"
	seats.add_child(_pips)
	_count = Shell.label("", Shell.BOLD_FONT, 13, Shell.TEXT)
	_count.name = "MatchFoundCount"
	seats.add_child(_count)
	var timer := HBoxContainer.new()
	timer.alignment = BoxContainer.ALIGNMENT_CENTER
	timer.add_theme_constant_override("separation", 10)
	box.add_child(timer)
	_bar = Bar.new()
	_bar.name = "MatchFoundBar"
	_bar.custom_minimum_size.x = 340
	timer.add_child(_bar)
	_seconds = Shell.label("", Shell.BOLD_FONT, 14, Shell.TEXT)
	_seconds.name = "MatchFoundSeconds"
	_seconds.custom_minimum_size.x = 36
	timer.add_child(_seconds)
	var answers := HBoxContainer.new()
	answers.alignment = BoxContainer.ALIGNMENT_CENTER
	answers.add_theme_constant_override("separation", 26)
	box.add_child(answers)
	_accept = Button.new()
	_accept.name = "MatchFoundAccept"
	_accept.text = "Accept"
	_accept.focus_mode = Control.FOCUS_NONE
	_accept.custom_minimum_size = Vector2(170, 36)
	_accept.tooltip_text = "Enter"
	_accept.pressed.connect(func() -> void: Session.accept_match())
	answers.add_child(_accept)
	_decline = Button.new()
	_decline.name = "MatchFoundDecline"
	_decline.text = "decline"
	_decline.flat = true
	_decline.focus_mode = Control.FOCUS_NONE
	_decline.tooltip_text = "Esc: back to the hub"
	_decline.add_theme_font_override("font", Shell.BODY_FONT)
	_decline.add_theme_font_size_override("font_size", 14)
	_decline.add_theme_color_override("font_color", Shell.DIM)
	_decline.add_theme_color_override("font_hover_color", Shell.TEXT)
	_decline.add_theme_constant_override("outline_size", 0)
	for st: String in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
		_decline.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	_decline.pressed.connect(func() -> void: Session.decline_match())
	answers.add_child(_decline)
	_player = AudioStreamPlayer.new()
	_player.name = "MatchFoundSound"
	add_child(_player)
	_tick = load(TICK) if ResourceLoader.exists(TICK) else null
	Session.changed.connect(refresh)
	refresh()
	_announce()


func _exit_tree() -> void:
	if _bridge:
		_bridge.stop_flash()


func _process(_delta: float) -> void:
	refresh()


## Draws the found match as the session has it now.
func refresh() -> void:
	var found := Session.found
	if found.is_empty():
		return
	var mode := str(found["mode"])
	var seats := int(found["seats"])
	# (a duel is one against one: "Undertow · 1v1 · ~15 min"; the others count their players)
	var players := "1v1" if Session.is_duel(mode) else "%d players" % seats
	# (M8: the queue finds only parties of one level, so the party's own is the match's,
	# named where it is not Normal: "High Water · Hard · 4 players · ~13 min")
	var level := MatchRules.level_of(mode, Session.difficulty_id())
	_line.text = "%s · %s · ~%d min" % [Game.mode_words(Profile.mode_name(mode), level), players, int(MINUTES.get(mode, 13))]
	_pips.seats = seats
	_pips.lit = int(found["accepted"])
	_pips.queue_redraw()
	_count.text = "%d of %d" % [int(found["accepted"]), seats]
	_bar.share = Session.found_share()
	_bar.queue_redraw()
	var left := Session.found_seconds()
	_seconds.text = "%d s" % left
	var answer := str(found["answer"])
	_accept.disabled = answer != ""
	_decline.disabled = answer != ""
	_accept.text = "Accepted" if answer == "accept" else "Accept"
	if left <= TICK_FROM and left > 0 and left != _ticked:
		_ticked = left
		_play(_tick, -10.0)


## What the plate says, one line each, for tests.
func lines() -> Array[String]:
	return [_title.text, _line.text, _count.text, _seconds.text, _accept.text]


## Whether the opening sound played (a stream loaded and started).
func sounded() -> bool:
	return _player.stream != null


func _unhandled_key_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo:
		return
	match key.keycode:
		KEY_ENTER, KEY_KP_ENTER:
			Session.accept_match()
			get_viewport().set_input_as_handled()
		KEY_ESCAPE:
			Session.decline_match()
			get_viewport().set_input_as_handled()


## The opening: a sound, the window's attention, the browser's title.
func _announce() -> void:
	if ResourceLoader.exists(SOUND):
		_play(load(SOUND), 0.0)
	if WebBridge.is_web():
		_bridge = WebBridge.new()
		_bridge.flash_title(FLASH)
	elif DisplayServer.get_name() != "headless":
		DisplayServer.window_request_attention()


func _play(stream: AudioStream, volume_db: float) -> void:
	if stream == null:
		return
	_player.stream = stream
	_player.volume_db = volume_db
	_player.play()


static func _centred(label: Label) -> Label:
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_constant_override("outline_size", 3)
	return label


## A pip per seat: lit gold for each player who accepted.
class Pips:
	extends Control
	var seats := 4
	var lit := 0

	func _init() -> void:
		custom_minimum_size = Vector2(4 * 22, 18)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var step := 22.0
		var start := (size.x - step * seats) * 0.5 + step * 0.5
		for i in seats:
			var c := Vector2(start + i * step, size.y * 0.5)
			draw_circle(c, 7.5, Color(0.05, 0.04, 0.03, 0.9))
			draw_circle(c, 6.0, Shell.GOLD if i < lit else Color(0.32, 0.28, 0.22))


## The window's time left: the console's painted trough and its gold fill (layout.json's bar).
class Bar:
	extends Control
	var share := 1.0
	var trough: StyleBox
	var fill: StyleBox

	func _init() -> void:
		var spec: Dictionary = Shell.layout()["bar"]
		custom_minimum_size = Vector2(0, float(spec["height"]))
		size_flags_vertical = Control.SIZE_SHRINK_CENTER
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		trough = Shell.piece_box("bar_trough.tres")
		fill = Shell.piece_box("bar_fill.tres")

	func _draw() -> void:
		var spec: Dictionary = Shell.layout()["bar"]
		var inset := Vector2(spec["inset"][0], spec["inset"][1])
		draw_style_box(trough, Rect2(Vector2.ZERO, size))
		var wide := (size.x - inset.x * 2.0) * clampf(share, 0.0, 1.0)
		if wide >= 2.0:
			draw_style_box(fill, Rect2(inset, Vector2(wide, float(spec["fill_height"]))))
