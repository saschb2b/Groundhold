## The hub (design 5.2). One job: who am I playing with, as whom, in which mode; then one
## button. The left well lists the party (up to four rows: seat glyph in its colour, name,
## Builder, and a mark: the leader's crown, a Ready tick, "needs to reload"); the arch
## shows your Builder with the team's coverage row; the right well holds the modes on its
## top row and Builders (B), Join (J) and the one button (Enter) below; the strip says
## where the party lives and its code.
class_name HubPanel
extends Control

## Seat glyph shapes and colours, as the party strip and the pennants show them (5.9).
const GLYPHS := PartyStrip.GLYPHS
const SEAT_COLORS := PartyStrip.SEAT_COLORS
const STATE_TEXT := {
	"needs_reload": "needs to reload",
	"away": "reconnecting",
	"in_match": "in a match",
}
const SOON := "Comes with a later version"

var shell: Shell
var _rows: Array = []
var _count: Label
var _title: Label
var _subtitle: Label
var _stars: Shell.Stars
var _coverage: CoverageRow
var _mode_line: Label
var _modes := {}
var _builders: Button
var _join: Button
var _primary: Button
var _line: Label
var _place: Label
var _code_box: HBoxContainer
var _code: Label


func setup(owner: Shell) -> void:
	shell = owner
	name = "HubPanel"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_party()
	_build_arch()
	_build_card()
	_build_strip()


func _process(_delta: float) -> void:
	# (the countdown's seconds tick over the button)
	if visible and Session.state == Session.State.COUNTDOWN:
		_fill_primary()


func refresh() -> void:
	var members := Session.members()
	var size_now := Session.party_size()
	_count.text = "%d/%d" % [size_now, NetProtocol.number("max_seats")]
	for i in _rows.size():
		_fill_row(_rows[i], members[i] if i < members.size() else null, i, members.is_empty())
	var mine := Session.profile.main
	shell.show_builder(mine, true)
	(_builders.get_node("Icon") as TextureRect).texture = Game.icon(str(Game.BUILDERS[mine]["emblem"]))
	var info: Dictionary = SimContent.BUILDERS[mine]
	_title.text = str(info["name"])
	_subtitle.text = "%s · %s" % [info["title"], Game.ROLES[info["role"]]["name"]]
	_stars.count = int(info["difficulty"])
	_stars.queue_redraw()
	_coverage.set_builders(Session.party_builders())
	var played := Profile.played_mode(Session.profile.mode)
	var waves := (SimContent.WAVES[SimContent.RULES[played]["waves"]] as Array).size()
	var seats: Array = NetProtocol.spec()["modes"][Session.profile.mode]["seats"]
	_mode_line.text = "%s · %d–%d players · %d waves" % [Profile.mode_name(Session.profile.mode), seats[0], seats[1], waves]
	for id: String in _modes:
		var button: Button = _modes[id]
		button.disabled = not Profile.offers(id) or not Session.is_leader()
		Shell.set_lit(button, id == Session.profile.mode)
	_fill_primary()
	_place.text = Session.place_text()
	_code_box.visible = Session.party_code() != ""
	_code.text = Session.show_code(Session.party_code())


## The party rows as one line each, for tests: "diamond Sascha lamplighter leader",
## "circle Ana lookout ready", "triangle Ben lamplighter needs to reload", "+ invite".
func lines() -> Array[String]:
	var out: Array[String] = []
	for row: Dictionary in _rows:
		if (row["invite"] as Control).visible:
			out.append("+ invite")
			continue
		var parts: Array[String] = [str(row["shape"]), (row["name"] as Label).text, str(row["builder_id"])]
		if (row["crown"] as Control).visible:
			parts.append("leader")
		if (row["tick"] as Control).visible:
			parts.append("ready")
		if (row["state"] as Label).text != "":
			parts.append((row["state"] as Label).text)
		out.append(" ".join(parts))
	return out


func primary_text() -> String:
	return Shell.words_of(_primary)


## B opens the Builders, J the Join panel, Enter presses the one button.
func key(code: int) -> void:
	match code:
		KEY_B:
			Session.show_screen("builders")
		KEY_J:
			shell.join.toggle()
		KEY_ENTER, KEY_KP_ENTER:
			if not _primary.disabled:
				Session.play()


# ── Building ──


func _build_party() -> void:
	var wing := Shell.piece(self, "PartyWing", 0.0, 0.0, Shell.vec("wing"))
	var well := VBoxContainer.new()
	well.name = "Party"
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_theme_constant_override("separation", 1)
	well.clip_contents = true
	Shell.place(well, Shell.rect("map_well").grow_individual(-6, -4, -6, -2))
	wing.add_child(well)
	var head := HBoxContainer.new()
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_child(head)
	var title := Shell.caps("Party", 11, Shell.GOLD)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(title)
	_count = Shell.caps("1/4", 11)
	_count.name = "PartyCount"
	head.add_child(_count)
	for i in NetProtocol.number("max_seats"):
		_rows.append(_make_row(well, i))


func _make_row(parent: Control, index: int) -> Dictionary:
	var row := HBoxContainer.new()
	row.name = "Member%d" % (index + 1)
	row.custom_minimum_size.y = 22
	row.mouse_filter = Control.MOUSE_FILTER_PASS
	row.add_theme_constant_override("separation", 4)
	parent.add_child(row)
	var glyph := PartyStrip.SeatGlyph.new()
	glyph.shape = GLYPHS[index]
	glyph.color = SEAT_COLORS[index]
	glyph.custom_minimum_size = Vector2(11, 11)
	glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(glyph)
	var who := Shell.label("", Shell.BOLD_FONT, 13, Shell.TEXT)
	who.name = "Name"
	who.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	who.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	who.add_theme_constant_override("outline_size", 3)
	row.add_child(who)
	var state := Shell.label("", Shell.BODY_FONT, 10, Shell.AMBER)
	state.name = "State"
	state.add_theme_constant_override("outline_size", 2)
	row.add_child(state)
	var builder := TextureRect.new()
	builder.name = "Builder"
	builder.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	builder.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	builder.custom_minimum_size = Vector2(17, 17)
	builder.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	builder.mouse_filter = Control.MOUSE_FILTER_STOP
	row.add_child(builder)
	var crown := Crown.new()
	crown.name = "Leader"
	crown.tooltip_text = "Leads the party: picks the mode and starts"
	row.add_child(crown)
	var tick := Tick.new()
	tick.name = "Ready"
	tick.tooltip_text = "Ready"
	row.add_child(tick)
	var invite := Button.new()
	invite.name = "Invite"
	invite.text = "+ invite"
	invite.flat = true
	invite.focus_mode = Control.FOCUS_NONE
	invite.alignment = HORIZONTAL_ALIGNMENT_LEFT
	invite.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	invite.add_theme_font_override("font", Shell.BODY_FONT)
	invite.add_theme_font_size_override("font_size", 12)
	invite.add_theme_color_override("font_color", Color("#7d705c"))
	invite.add_theme_color_override("font_hover_color", Shell.TEXT)
	invite.add_theme_constant_override("outline_size", 0)
	for st: String in ["normal", "hover", "pressed", "hover_pressed", "focus"]:
		invite.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	invite.pressed.connect(_invite)
	row.add_child(invite)
	return {
		"row": row, "glyph": glyph, "name": who, "state": state, "builder": builder,
		"crown": crown, "tick": tick, "invite": invite, "shape": GLYPHS[index], "builder_id": "",
	}


func _fill_row(row: Dictionary, member: Variant, index: int, solo: bool) -> void:
	var filled := member != null or (solo and index == 0)
	for key: String in ["glyph", "name", "state", "builder", "crown", "tick"]:
		(row[key] as Control).visible = filled
	(row["invite"] as Control).visible = not filled
	if not filled:
		row["builder_id"] = ""
		return
	var who: String
	var main: String
	var mark := ""
	var leader := solo
	var ready := false
	var mine := solo
	if member == null:
		who = Session.my_name()
		main = Session.profile.main
	else:
		var m: Dictionary = member
		who = str(m["name"])
		main = str(m["main"]) if SimContent.BUILDERS.has(str(m["main"])) else "lamplighter"
		mark = str(STATE_TEXT.get(str(m["state"]), ""))
		leader = int(m["member"]) == int(Session.party["leader"])
		ready = m["state"] == "ready"
		mine = int(m["member"]) == Session.me
	row["builder_id"] = main
	(row["name"] as Label).text = who
	(row["name"] as Label).add_theme_color_override("font_color", PartyStrip.MINE if mine else Shell.TEXT)
	(row["state"] as Label).text = mark
	var icon: TextureRect = row["builder"]
	icon.texture = Game.icon(str(Game.BUILDERS[main]["glyph"]))
	icon.modulate = Game.glyph_tint(main)
	icon.tooltip_text = "%s, %s" % [SimContent.BUILDERS[main]["name"], SimContent.BUILDERS[main]["title"]]
	(row["crown"] as Control).visible = leader and not solo
	(row["tick"] as Control).visible = ready


func _build_arch() -> void:
	var centre_size := Shell.vec("centre")
	var centre := Shell.piece(self, "Arch", 0.5, -centre_size.x * 0.5, centre_size)
	var info := VBoxContainer.new()
	info.name = "Info"
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_theme_constant_override("separation", 0)
	Shell.place(info, Shell.rect("text").grow_individual(0, 4, 0, 0))
	centre.add_child(info)
	_title = Shell.label("", Shell.TITLE_FONT, 21, Shell.GOLD)
	_title.name = "Title"
	_title.add_theme_constant_override("outline_size", 3)
	info.add_child(_title)
	var line := HBoxContainer.new()
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.add_theme_constant_override("separation", 8)
	info.add_child(line)
	_subtitle = Shell.label("", Shell.BOLD_FONT, 13, Shell.DIM)
	_subtitle.name = "Subtitle"
	_subtitle.add_theme_constant_override("outline_size", 0)
	line.add_child(_subtitle)
	_stars = Shell.Stars.new()
	_stars.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(_stars)
	var gap := Control.new()
	gap.custom_minimum_size.y = 3
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_child(gap)
	_coverage = CoverageRow.new()
	info.add_child(_coverage)
	_mode_line = Shell.label("", Shell.BODY_FONT, 12, Shell.DIM)
	_mode_line.name = "ModeLine"
	_mode_line.add_theme_constant_override("outline_size", 0)
	info.add_child(_mode_line)


func _build_card() -> void:
	var wing := Shell.vec("wing")
	var right := Shell.piece(self, "CardWing", 1.0, -wing.x, wing)
	var card := Control.new()
	card.name = "HubCard"
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	Shell.place(card, Shell.rect("card_well"))
	right.add_child(card)
	var buttons := []
	for id: String in Profile.HUB_MODES:
		var button := Shell.socket("Mode_" + id, Profile.mode_name(id))
		button.tooltip_text = (
			"Play with up to four on one shared road" if id == "high_water" else SOON
		)
		button.pressed.connect(Session.set_mode.bind(id))
		_modes[id] = button
		buttons.append(button)
	# (your main's emblem, its signature prop, as a command button: Builders on B)
	_builders = Shell.icon_socket("Builders", Game.placeholder_icon(), "B")
	_builders.tooltip_text = "Builders (B): browse them; choose your main and backup"
	_builders.pressed.connect(Session.show_screen.bind("builders"))
	buttons.append(_builders)
	_join = Shell.socket("Join", "Join", "J")
	_join.tooltip_text = "Join a party by its code, or find a server nearby"
	_join.pressed.connect(func() -> void: shell.join.toggle())
	buttons.append(_join)
	_primary = Shell.socket("Primary", "Play", "Enter")
	_primary.pressed.connect(Session.play)
	buttons.append(_primary)
	Shell.lay_card(card, buttons)
	# The one button's sentence, just above the card: who it waits for, the 3-2-1.
	_line = Shell.label("", Shell.BOLD_FONT, 14, Shell.TEXT)
	_line.name = "PrimaryLine"
	_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_line.add_theme_constant_override("outline_size", 5)
	_line.add_theme_color_override("font_outline_color", Shell.INK)
	_line.position = Vector2(-150, -24)
	_line.size = Vector2(wing.x + 136, 22)
	right.add_child(_line)


func _fill_primary() -> void:
	var p := Session.primary()
	var counting := str(p["act"]) == "cancel"
	# (the countdown's digit in the display face; the words in the bold face every socket
	# uses, a size up: at 13 px the display face lost the tail of its 'y' to the outline)
	if counting:
		Shell.set_words(_primary, str(p["text"]), Shell.TITLE_FONT, 24)
	else:
		Shell.set_words(_primary, str(p["text"]), Shell.BOLD_FONT, 14)
	_primary.disabled = not bool(p["enabled"])
	_primary.tooltip_text = str(p["line"]) if str(p["line"]) != "" else ("An offline match at once" if str(p["act"]) == "play" else "")
	_line.text = str(p["line"])
	_line.add_theme_color_override("font_color", Shell.AMBER if str(p["line"]).ends_with("reload") else Shell.TEXT)
	Shell.set_lit(_primary, bool(p["enabled"]) and str(p["act"]) in ["play", "start"])


func _build_strip() -> void:
	var strip := ResourceStrip.new()
	strip.name = "PlaceStrip"
	strip.setup(load(Shell.ART + "strip.tres"), Shell.k(), float(Shell.layout()["strip"]["cap"]))
	strip.anchor_left = 1.0
	strip.anchor_right = 1.0
	strip.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	strip.custom_minimum_size.y = float(Shell.layout()["strip"]["height"])
	add_child(strip)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 8)
	strip.add_child(row)
	_place = Shell.label("Offline", Shell.BOLD_FONT, 14, Shell.TEXT)
	_place.name = "Place"
	_place.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(_place)
	_code_box = HBoxContainer.new()
	_code_box.name = "CodeBox"
	_code_box.add_theme_constant_override("separation", 6)
	row.add_child(_code_box)
	var party := Shell.caps("Party", 11)
	party.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_code_box.add_child(party)
	_code = Shell.label("", Shell.BOLD_FONT, 15, Shell.GOLD)
	_code.name = "Code"
	_code.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_code_box.add_child(_code)
	for what: String in ["code", "link"]:
		var copy := Button.new()
		copy.name = "Copy" + what.capitalize()
		copy.text = "copy " + what
		copy.focus_mode = Control.FOCUS_NONE
		copy.flat = true
		copy.add_theme_font_override("font", Shell.BODY_FONT)
		copy.add_theme_font_size_override("font_size", 11)
		copy.add_theme_color_override("font_color", Shell.DIM)
		copy.add_theme_color_override("font_hover_color", Shell.GOLD)
		copy.add_theme_constant_override("outline_size", 0)
		for st: String in ["normal", "hover", "pressed", "hover_pressed"]:
			copy.add_theme_stylebox_override(st, StyleBoxEmpty.new())
		copy.pressed.connect(_copy.bind(what))
		_code_box.add_child(copy)


func _copy(what: String) -> void:
	var text := Session.show_code(Session.party_code()) if what == "code" else Session.join_link()
	DisplayServer.clipboard_set(text)
	shell.show_notice("Copied " + text)


func _invite() -> void:
	if Session.party_code() != "":
		_copy("link")
	else:
		shell.join.open()


## The leader's crown: three gold points on a band.
class Crown:
	extends Control

	func _init() -> void:
		custom_minimum_size = Vector2(13, 12)
		size_flags_vertical = Control.SIZE_SHRINK_CENTER
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var points := PackedVector2Array([
			Vector2(1, h - 2), Vector2(1, h * 0.35), Vector2(w * 0.3, h * 0.6), Vector2(w * 0.5, 1),
			Vector2(w * 0.7, h * 0.6), Vector2(w - 1, h * 0.35), Vector2(w - 1, h - 2),
		])
		draw_colored_polygon(points, Shell.GOLD)
		draw_polyline(points + PackedVector2Array([points[0]]), Color(0.1, 0.07, 0.03, 0.9), 1.0, true)


## A Ready tick, bright on the dark well.
class Tick:
	extends Control

	func _init() -> void:
		custom_minimum_size = Vector2(13, 12)
		size_flags_vertical = Control.SIZE_SHRINK_CENTER
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _draw() -> void:
		var h := size.y
		var points := PackedVector2Array([Vector2(1.5, h * 0.55), Vector2(size.x * 0.4, h - 2), Vector2(size.x - 1.5, 2)])
		draw_polyline(points, Color(0.04, 0.03, 0.02, 0.9), 4.0, true)
		draw_polyline(points, Shell.GOOD, 2.2, true)
