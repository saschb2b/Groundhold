## The connection overlay (design 5.7; docs/design/contract-m4.md): a small plate over the
## portrait, never a modal, saying why this player's world is not live. The match plays on
## underneath (towers keep firing; the caretaker holds the seat), so it takes no input.
##
##   .------------------------------------------.   .------------------------------------------.
##   |  Reconnecting...  your towers keep firing |   |  Catching up   [########------]  62%     |
##   '------------------------------------------'   '------------------------------------------'
##
## States, set by the match scene from the MatchClient (MatchClient.connection_state()):
##   RECONNECTING    the link dropped; the client says resume HELLOs every reconnect_ms; the
##                   bar shows the checkpoint's parts once RESYNC(rejoin) names them
##   CATCHING_UP     running the turns it missed (after a rejoin, a RESYNC, a hidden tab,
##                   a late load); the bar is ticks run of ticks to run
##   IN_ANOTHER_TAB  the tab is hidden: the caretaker keeps the seat
##   DESYNCED        the match ended "desynced" for this seat; the detail says a report was
##                   saved (the results plate, which follows in a session's match, offers it)
##   BACK            back from another tab or a dropped link and level again, while the
##                   caretaker still holds the seat: the detail says when it hands back
##                   (after this wave, or after the coming one while a window is open);
##                   the seat's own orders are refused until then
## The words are TEXTS; the plate is the console's own pieces: the bronze tooltip plate
## (Shell.plate_box), the bar's trough and gold fill (LoadingScreen.LoadBar, as the loading
## screen's cards), the title in the console's bold serif and the rest in its dim body
## face. A TEXTS line splits at its first double space or colon into a title and a quieter
## second line. It fades in and out over a quarter second.
@warning_ignore_start("integer_division")
class_name ConnectionOverlay
extends Control

enum State { NONE, RECONNECTING, CATCHING_UP, IN_ANOTHER_TAB, DESYNCED, BACK }

const TEXTS := {
	State.NONE: "",
	State.RECONNECTING: "Reconnecting...  your towers keep firing",
	State.CATCHING_UP: "Catching up",
	State.IN_ANOTHER_TAB: "In another tab: the caretaker kept your seat",
	State.DESYNCED: "The lands fell out of step",
	State.BACK: "Welcome back",
}
## The detail line under DESYNCED once the game wrote its dump.
const REPORT_SAVED := "A report was saved"
## The detail line under BACK: while a wave runs, and while a build window is open (the
## caretaker hands the seat back as the next window opens, after the coming wave).
const BACK_AFTER_WAVE := "The caretaker hands back after this wave"
const BACK_AFTER_NEXT_WAVE := "The caretaker hands back after the coming wave"
## The plate's width, and how far its foot stands above the screen's bottom edge: just
## over the console's crest, round the portrait (layout.json's centre is 198 high).
const WIDTH := 400.0
const ABOVE := 214.0
const FADE := 0.25

var state := State.NONE
## The bar, per mille; -1 for none.
var progress_pm := -1
## A second line (DESYNCED: that a report was saved; BACK: when the seat is handed back).
var detail := ""

var _plate: PanelContainer
var _title: Label
var _line: Label
var _bar: LoadingScreen.LoadBar
var _percent: Label
var _bar_row: HBoxContainer
var _tween: Tween


func _init() -> void:
	name = "ConnectionOverlay"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Shows `new_state` with a bar at `progress` per mille (-1: none) and a `more` line.
func show_state(new_state: State, progress := -1, more := "") -> void:
	var was := state
	state = new_state
	progress_pm = clampi(progress, -1, 1000)
	detail = more
	if is_inside_tree():
		_refresh(was)


## What the plate says now, one line: "Catching up 62%", "" for NONE.
func text() -> String:
	var line: String = TEXTS[state]
	if progress_pm >= 0 and state != State.NONE:
		line += " %d%%" % (progress_pm / 10)
	if detail != "":
		line += " · " + detail
	return line


## The plate's two lines as drawn: [title, second line].
func lines() -> Array:
	if _title == null:
		return ["", ""]
	return [_title.text, _line.text if _line.visible else ""]


func _ready() -> void:
	# (the offsets too: set_anchors_preset alone keeps the zero rect it had, and the plate,
	# anchored to its middle, stood above the window's top left corner)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()
	_refresh(State.NONE)


func _process(delta: float) -> void:
	if _bar and _bar.visible and not is_equal_approx(_bar.shown, _bar.target):
		# (the fill eases toward the share, as the loading screen's does)
		_bar.shown = move_toward(_bar.shown, _bar.target, delta * 2.0)
		_bar.queue_redraw()


func _build() -> void:
	_plate = PanelContainer.new()
	_plate.name = "Plate"
	_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_plate.add_theme_stylebox_override("panel", Shell.plate_box(Vector4(22, 12, 22, 14)))
	_plate.anchor_left = 0.5
	_plate.anchor_right = 0.5
	_plate.anchor_top = 1.0
	_plate.anchor_bottom = 1.0
	_plate.offset_left = -WIDTH * 0.5
	_plate.offset_right = WIDTH * 0.5
	_plate.offset_bottom = -ABOVE
	_plate.grow_vertical = Control.GROW_DIRECTION_BEGIN
	add_child(_plate)
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", 4)
	_plate.add_child(column)
	_title = Shell.label("", Shell.BOLD_FONT, 17, Shell.TEXT)
	_title.name = "Title"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.add_theme_constant_override("outline_size", 4)
	_title.add_theme_color_override("font_outline_color", Shell.INK)
	column.add_child(_title)
	_line = Shell.label("", Shell.BODY_FONT, 13, Shell.DIM)
	_line.name = "Line"
	_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_line)
	_bar_row = HBoxContainer.new()
	_bar_row.name = "BarRow"
	_bar_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar_row.add_theme_constant_override("separation", 8)
	column.add_child(_bar_row)
	_bar = LoadingScreen.LoadBar.new()
	_bar.name = "Bar"
	_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_bar_row.add_child(_bar)
	_percent = Shell.label("", Shell.BOLD_FONT, 13, Shell.GOLD)
	_percent.name = "Percent"
	_percent.custom_minimum_size = Vector2(40, 0)
	_percent.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_bar_row.add_child(_percent)


func _refresh(was: State) -> void:
	if _plate == null:
		return
	var words: String = TEXTS[state]
	var cut := words.find("  ")
	var title := words
	var second := ""
	if cut >= 0:
		title = words.substr(0, cut)
		second = words.substr(cut + 2).strip_edges()
	elif words.contains(": "):
		cut = words.find(": ")
		title = words.substr(0, cut)
		second = words.substr(cut + 2)
		second = second.substr(0, 1).to_upper() + second.substr(1)
	if detail != "":
		second = detail if second == "" else second + "\n" + detail
	_title.text = title
	_title.add_theme_color_override("font_color", Shell.NOTICE if state == State.DESYNCED else Shell.TEXT)
	_line.text = second
	_line.visible = second != ""
	_bar_row.visible = progress_pm >= 0
	if progress_pm >= 0:
		if was != state:
			_bar.shown = progress_pm / 1000.0
		_bar.target = progress_pm / 1000.0
		_bar.queue_redraw()
		_percent.text = "%d%%" % (progress_pm / 10)
	var show := state != State.NONE
	if show == visible and (was != State.NONE or not show):
		return
	if _tween:
		_tween.kill()
	_tween = create_tween()
	if show:
		visible = true
		modulate.a = 0.0 if was == State.NONE else modulate.a
		_tween.tween_property(self, "modulate:a", 1.0, FADE)
	else:
		_tween.tween_property(self, "modulate:a", 0.0, FADE)
		_tween.tween_callback(func() -> void: visible = false)
