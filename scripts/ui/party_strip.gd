## The party strip (design 5.7): top left, one slim plate per player while more than one
## seat plays. Each plate shows the seat's glyph in its colour, the name, the gold, link
## bars from the round trips the server relays (LINKS), and a Ready mark during the build
## window. "away", "back next window", "caretaker" and "left" replace the gold when the
## caretaker plays the seat. My own plate is framed brighter.
##
## Before a networked match starts, one plate says where the client stands: connecting,
## waiting for the others, loading; and why it stopped, when the link fails.
class_name PartyStrip
extends VBoxContainer

## Okabe-Ito seat colours and glyphs (design 5.9): seat 1 to 4.
const SEAT_COLORS := [Color("#E69F00"), Color("#56B4E9"), Color("#009E73"), Color("#CC79A7")]
const GLYPHS := ["diamond", "circle", "triangle", "square"]
const STATE_TEXT := {
	SimTypes.SEAT_AWAY: "away",
	SimTypes.SEAT_RETURNING: "back next window",
	SimTypes.SEAT_CARETAKER: "caretaker",
	SimTypes.SEAT_LEFT: "left",
}
const TEXT := Color("#ece2cc")
const DIM := Color("#a3957d")
const COIN := Color("#f6d06a")
## My own name: the gold the notices use.
const MINE := Color("#ffd36a")

var main: Node
var _bold: Font
var _body: Font
var _coin: Texture2D
var _plate_style: StyleBox
var _mine_style: StyleBox
var _status: PanelContainer
var _status_label: Label
var _rows: Array = []
var _shown_seats := -1


func setup(scene: Node, bold: Font, body: Font, coin: Texture2D, plate: StyleBox, mine: StyleBox) -> void:
	main = scene
	_bold = bold
	_body = body
	_coin = coin
	_plate_style = plate
	_mine_style = mine
	name = "PartyStrip"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_constant_override("separation", 3)
	position = Vector2(12, 10)
	_status = PanelContainer.new()
	_status.name = "NetStatus"
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status.add_theme_stylebox_override("panel", _plate_style)
	_status_label = _text("", _body, 14, TEXT)
	_status_label.name = "NetStatusText"
	_status.add_child(_status_label)
	add_child(_status)
	refresh()


func _process(_delta: float) -> void:
	refresh()


## Reads the match and the link and updates every plate.
func refresh() -> void:
	var sim: SimMatch = Game.sim
	var client: MatchClient = main.get("client") if main else null
	var status := _status_text(client)
	_status.visible = status != ""
	_status_label.text = status
	var count := sim.seats.size() if sim else 0
	var shown := count > 1 or (client != null and count > 0)
	if not shown:
		count = 0
	if count != _shown_seats:
		_rebuild(count)
	for i in count:
		_fill(_rows[i], sim, client, i + 1)
	visible = status != "" or count > 0


## The link bars each plate shows (-1 where none show), for tests.
func link_bars() -> Array[int]:
	var out: Array[int] = []
	for row: Dictionary in _rows:
		var bars: LinkBars = row["bars"]
		out.append(bars.bars if bars.visible else -1)
	return out


## How many plates show a Ready mark, for tests.
func ready_marks_shown() -> int:
	return _rows.filter(func(row: Dictionary) -> bool: return (row["ready"] as Control).visible).size()


## The plate texts as one line each, for tests: "Tamsin 120 ready", "Edda away".
func lines() -> Array[String]:
	var out: Array[String] = []
	for row: Dictionary in _rows:
		var parts := [(row["name"] as Label).text, (row["gold"] as Label).text]
		if (row["ready"] as Control).visible and (row["ready"] as ReadyMark).lit:
			parts.append("ready")
		out.append(" ".join(parts.filter(func(p: String) -> bool: return p != "")))
	return out


func _status_text(client: MatchClient) -> String:
	if client == null:
		return ""
	match client.phase:
		MatchClient.Phase.CONNECTING, MatchClient.Phase.HELLO:
			return "Connecting to %s ..." % client.link.url if client.link else "Connecting ..."
		MatchClient.Phase.WAITING:
			return "On %s · waiting for the others" % client.server_name
		MatchClient.Phase.LOADING:
			return "Walking out · everyone's land checked against yours"
		MatchClient.Phase.STARTING:
			return "The tide turns ..."
		MatchClient.Phase.FAILED:
			return "Link lost · %s" % client.error_text
		MatchClient.Phase.ENDED:
			if client.outcome == "desynced":
				return "The lands fell out of step"
	return ""


func _rebuild(count: int) -> void:
	for row: Dictionary in _rows:
		(row["plate"] as Node).queue_free()
	_rows.clear()
	for i in count:
		_rows.append(_make_row(i + 1))
	_shown_seats = count


func _make_row(seat: int) -> Dictionary:
	var plate := PanelContainer.new()
	plate.name = "Seat%d" % seat
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.add_theme_stylebox_override("panel", _plate_style)
	add_child(plate)
	var row := HBoxContainer.new()
	row.name = "Row"
	row.add_theme_constant_override("separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plate.add_child(row)
	var glyph := SeatGlyph.new()
	glyph.shape = GLYPHS[(seat - 1) % GLYPHS.size()]
	glyph.color = SEAT_COLORS[(seat - 1) % SEAT_COLORS.size()]
	glyph.custom_minimum_size = Vector2(14, 14)
	glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(glyph)
	var who := _text("", _bold, 15, TEXT)
	who.name = "Name"
	who.custom_minimum_size.x = 92
	who.clip_text = true
	row.add_child(who)
	var coin := TextureRect.new()
	coin.texture = _coin
	coin.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	coin.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	coin.custom_minimum_size = Vector2(16, 16)
	coin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	coin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(coin)
	var gold := _text("", _bold, 15, COIN)
	gold.name = "Gold"
	gold.custom_minimum_size.x = 34
	row.add_child(gold)
	var bars := LinkBars.new()
	bars.custom_minimum_size = Vector2(16, 14)
	bars.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(bars)
	var ready := ReadyMark.new()
	ready.name = "Ready"
	ready.custom_minimum_size = Vector2(14, 14)
	ready.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(ready)
	var room := Control.new()
	room.name = "ReadyRoom"
	room.custom_minimum_size = ready.custom_minimum_size
	room.mouse_filter = Control.MOUSE_FILTER_IGNORE
	room.visible = false
	row.add_child(room)
	return {
		"plate": plate,
		"name": who,
		"coin": coin,
		"gold": gold,
		"bars": bars,
		"ready": ready,
		"ready_room": room,
	}


func _fill(row: Dictionary, sim: SimMatch, client: MatchClient, seat: int) -> void:
	var s := sim.seat(seat)
	var mine := seat == Game.seat
	var caretaken := STATE_TEXT.has(s.state)
	# (my own gold as the resource strip shows it: what my orders on their way will spend
	# is already gone, greyed until their turn runs)
	var held := Game.pending_gold if mine and not caretaken else 0
	# Overrides only when the plate's look changes: setting them re-themes the plate.
	var look := [mine, caretaken, held > 0]
	if row.get("look", []) != look:
		row["look"] = look
		(row["plate"] as PanelContainer).add_theme_stylebox_override(
			"panel", _mine_style if mine else _plate_style
		)
		(row["name"] as Label).add_theme_color_override("font_color", MINE if mine else TEXT)
		var tone := DIM if caretaken or held > 0 else COIN
		(row["gold"] as Label).add_theme_color_override("font_color", tone)
		(row["gold"] as Label).add_theme_font_override("font", _body if caretaken else _bold)
		(row["coin"] as TextureRect).visible = not caretaken
	var listed := client != null and seat - 1 < client.names.size()
	(row["name"] as Label).text = client.names[seat - 1] if listed else "Seat %d" % seat
	(row["gold"] as Label).text = STATE_TEXT[s.state] if caretaken else str(s.gold - held)
	var bars: LinkBars = row["bars"]
	bars.visible = listed
	if listed and seat - 1 < client.rtts.size():
		# (with the link gone nobody's round trip is known: every plate's bars go dark)
		var linked := client.phase <= MatchClient.Phase.PLAYING
		bars.set_bars(MatchClient.bars_for(client.rtts[seat - 1], client.link_flags[seat - 1]) if linked else 0)
	var ready: ReadyMark = row["ready"]
	var window := sim.hollows[s.hollow].phase == SimTypes.PHASE_PREP
	# (no Ready mark while no order goes out: before START, and once the link is gone)
	ready.visible = window and sim.hollows[s.hollow].wave < sim.total_waves() and Game.accepts_commands()
	# (the bead's room is kept while it hides, so the plate does not jump as a wave starts)
	(row["ready_room"] as Control).visible = not ready.visible
	var lit := s.ready or s.state != SimTypes.SEAT_PRESENT
	# My own bead lights from my press at once, as the horn button does, before the turn
	# that carries it runs (the simulation's Ready follows a round trip later).
	var controller: BuildController = main.get("controller") if main else null
	if mine and s.state == SimTypes.SEAT_PRESENT and controller != null:
		lit = controller.wants_ready()
	ready.set_lit(lit)


func _text(value: String, font: Font, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = value
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


## A seat's glyph: a diamond, circle, triangle or square in its colour, outlined dark,
## so colour-blind players tell the seats apart by shape.
class SeatGlyph:
	extends Control
	var shape := "diamond"
	var color := Color.WHITE

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.5
		var ink := Color(0.04, 0.03, 0.02, 0.9)
		match shape:
			"circle":
				draw_circle(c, r, ink)
				draw_circle(c, r - 1.5, color)
			"square":
				draw_rect(Rect2(c - Vector2(r, r) * 0.85, Vector2(r, r) * 1.7), ink)
				draw_rect(Rect2(c - Vector2(r, r) * 0.85 + Vector2(1.5, 1.5), Vector2(r, r) * 1.7 - Vector2(3, 3)), color)
			"triangle":
				var outer := PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, r * 0.8), c + Vector2(-r, r * 0.8)])
				draw_colored_polygon(outer, ink)
				var inner := PackedVector2Array(
					[c + Vector2(0, -r + 2.5), c + Vector2(r - 2.2, r * 0.8 - 1.2), c + Vector2(-r + 2.2, r * 0.8 - 1.2)]
				)
				draw_colored_polygon(inner, color)
			_:
				var outer := PackedVector2Array(
					[c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r), c + Vector2(-r, 0)]
				)
				draw_colored_polygon(outer, ink)
				var k := r - 2.0
				var inner := PackedVector2Array(
					[c + Vector2(0, -k), c + Vector2(k, 0), c + Vector2(0, k), c + Vector2(-k, 0)]
				)
				draw_colored_polygon(inner, color)


## Three rising bars, lit by the link's quality (3 under 120 ms, 2 under 250, else 1;
## none while the seat is silent).
class LinkBars:
	extends Control
	var bars := 3

	func set_bars(n: int) -> void:
		if n != bars:
			bars = n
			queue_redraw()

	func _draw() -> void:
		var w := size.x / 4.0
		for i in 3:
			var h := size.y * (0.4 + 0.3 * i)
			var rect := Rect2(Vector2(i * w * 1.4, size.y - h), Vector2(w, h))
			var on := i < bars
			draw_rect(rect, Color("#f0cf86") if on else Color(0.35, 0.3, 0.24, 0.8))


## Ready this window: a lit bead; not yet: a dim ring.
class ReadyMark:
	extends Control
	var lit := false

	func set_lit(on: bool) -> void:
		if on != lit:
			lit = on
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.5
		if lit:
			draw_circle(c, r, Color(1.0, 0.7, 0.3, 0.35))
			draw_circle(c, r * 0.62, Color("#ffd36a"))
		else:
			draw_arc(c, r * 0.55, 0.0, TAU, 20, Color(0.64, 0.58, 0.49, 0.8), 1.5, true)
