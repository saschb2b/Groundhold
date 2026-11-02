## The party strip (design 5.7): top left, one slim plate per player while more than one
## seat plays. Each plate shows the seat's glyph in its colour, its Builder's face, the
## name, the gold, link bars from the round trips the server relays (LINKS), and a Ready
## mark during the build window (M8: during a wave of a mode that stacks too, where a mark is a
## call for the next wave, shown while one may be called or stands). "away", "back next window", "caretaker" and "left" replace the gold when the
## caretaker plays the seat ("in another tab" for an away seat whose browser tab is hidden, LINKS' hidden flag).
## My own plate is framed brighter.
##
## In a race (Tide Race, M6) it shows both teams, mine first: my team's plates, then under
## a small "Rival crew" caption the rival team's, a little dimmer (their Ready marks follow
## their own hollow's window). A duel (Undertow, M7) shows its two seats the same way, my
## plate, then my rival's under "Rival".
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
## How bright a rival's plate stands beside my team's.
const RIVAL_FADE := 0.82

var main: Node
var _bold: Font
var _body: Font
var _coin: Texture2D
var _plate_style: StyleBox
var _mine_style: StyleBox
var _status: PanelContainer
var _status_label: Label
## The plates in the order shown (my team first in a race), each with its seat.
var _rows: Array = []
var _shown_order := []
## Over the rival team's plates in a race.
var _rival_caption: Label


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
	var order := seat_order(sim) if shown else []
	# (the order and which plates are a rival's: a match of the same seats in other teams
	# lays the strip out again)
	if [order, _rivals(sim, order)] != _shown_order:
		_rebuild(order)
	for row: Dictionary in _rows:
		_fill(row, sim, client, int(row["seat"]))
	visible = status != "" or not order.is_empty()


## The seats as the strip lists them: in seat order, or in a race my team's first, then
## the rival team's, each in seat order (a duel too: two teams).
static func seat_order(sim: SimMatch) -> Array:
	var out := []
	if sim == null:
		return out
	var mine := Game.my_team() if sim.teams.size() > 1 else -1
	for s in sim.seats:
		if mine < 0 or s.team == mine:
			out.append(s.seat)
	for s in sim.seats:
		if mine >= 0 and s.team != mine:
			out.append(s.seat)
	return out


## Which of `order`'s seats are on the rival team in a race or a duel (none outside them).
static func _rivals(sim: SimMatch, order: Array) -> Array:
	var mine := Game.my_team() if sim and sim.teams.size() > 1 else -1
	return order.map(func(seat: int) -> bool: return mine >= 0 and sim.seat(seat).team != mine)


## The seat each plate shows, top to bottom, for tests.
func seats_shown() -> Array:
	return _rows.map(func(row: Dictionary) -> int: return int(row["seat"]))


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
			# (a session's match ends on the results plate, which says it in its own words)
			if client.keep_link:
				return ""
			return "Link lost · %s" % client.error_text
		MatchClient.Phase.ENDED:
			# (a session's match ends on the results plate, whose title says it)
			if client.outcome == "desynced" and not client.keep_link:
				return "The lands fell out of step"
	return ""


## The name column's width: the widest name the game makes up (Profile.generated_name),
## at `font` and `size`.
static func name_room(font: Font, size: int) -> float:
	var widest := 0.0
	for word: String in Profile.NAME_WORDS:
		widest = maxf(widest, font.get_string_size(word + " 88", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
	return ceilf(widest) + 2.0


func _rebuild(order: Array) -> void:
	for row: Dictionary in _rows:
		(row["plate"] as Node).queue_free()
	_rows.clear()
	if _rival_caption:
		_rival_caption.queue_free()
		_rival_caption = null
	var sim: SimMatch = Game.sim
	var rivals := _rivals(sim, order)
	for i in order.size():
		var seat: int = order[i]
		var rival: bool = rivals[i]
		if rival and _rival_caption == null:
			# (a race: the rival team's plates under their own caption, after my team's)
			_rival_caption = _text("RIVAL" if Game.is_duel() else "RIVAL CREW", _bold, 11, DIM)
			_rival_caption.name = "RivalCaption"
			_rival_caption.add_theme_constant_override("outline_size", 3)
			_rival_caption.add_theme_color_override("font_outline_color", Color(0.04, 0.03, 0.02, 0.85))
			add_child(_rival_caption)
		var row := _make_row(seat)
		if rival:
			(row["plate"] as Control).modulate = Color(RIVAL_FADE, RIVAL_FADE, RIVAL_FADE, 1.0)
		_rows.append(row)
	_shown_order = [order.duplicate(), rivals]


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
	# (the seat's Builder, as the hub's party rows and the results show it: design 5.7)
	var builder := TextureRect.new()
	builder.name = "Builder"
	builder.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	builder.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	builder.custom_minimum_size = Vector2(20, 20)
	builder.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	builder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(builder)
	var who := _text("", _bold, 15, TEXT)
	who.name = "Name"
	# (room for every generated name whole; a longer one the player chose ends in an
	# ellipsis inside its column, never under the coin)
	who.custom_minimum_size.x = name_room(_bold, 15)
	who.clip_text = true
	who.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(who)
	var coin := TextureRect.new()
	coin.name = "Coin"
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
		"seat": seat,
		"plate": plate,
		"builder": builder,
		"builder_id": "",
		"name": who,
		"coin": coin,
		"gold": gold,
		"bars": bars,
		"ready": ready,
		"ready_room": room,
	}


func _fill(row: Dictionary, sim: SimMatch, client: MatchClient, seat: int) -> void:
	var s := sim.seat(seat)
	if row["builder_id"] != s.builder and Game.BUILDERS.has(s.builder):
		row["builder_id"] = s.builder
		var icon: TextureRect = row["builder"]
		icon.texture = Game.icon(str(Game.BUILDERS[s.builder]["glyph"]))
		icon.modulate = Game.glyph_tint(s.builder)
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
	# (online the server's names; offline the names the session gave the scene, else "Seat N")
	(row["name"] as Label).text = client.names[seat - 1] if listed else Game.seat_name(seat)
	var shown_state: String = STATE_TEXT.get(s.state, "")
	if s.state == SimTypes.SEAT_AWAY and client != null and seat - 1 < client.link_flags.size():
		if client.link_flags[seat - 1] & NetProtocol.enum_value("link_flags", "hidden"):
			shown_state = "in another tab"
	(row["gold"] as Label).text = shown_state if caretaken else str(s.gold - held)
	var bars: LinkBars = row["bars"]
	bars.visible = listed
	if listed and seat - 1 < client.rtts.size():
		# (with the link gone nobody's round trip is known: every plate's bars go dark)
		var linked := client.phase <= MatchClient.Phase.PLAYING and not client.reconnecting
		bars.set_bars(MatchClient.bars_for(client.rtts[seat - 1], client.link_flags[seat - 1]) if linked else 0)
	var ready: ReadyMark = row["ready"]
	var h := sim.hollows[s.hollow]
	var window := h.phase == SimTypes.PHASE_PREP
	# (M8: in a wave of a mode that stacks a mark is a call for the next wave, shown while
	# the hollow may take one or a call stands)
	if h.phase == SimTypes.PHASE_WAVE and sim.stack_max > 1:
		window = sim.can_stack(h.id) or _calls_on(sim, h)
	# (no Ready mark while no order goes out: before START, once the link is gone, and once
	# the match is decided, a race whose hollow was still in a window too; a rival still
	# racing after my hollow is done keeps its marks)
	var calls := Game.accepts_commands() and not sim.over and Game.outcome() == ""
	ready.visible = window and h.wave < sim.last_wave() and calls
	# (the bead's room is kept while it hides, so the plate does not jump as a wave starts)
	(row["ready_room"] as Control).visible = not ready.visible
	# (a seat the caretaker plays counts as Ready beside a present player, so its bead is
	# lit; on a hollow nobody is present at, a rival crew's in a race, the caretaker calls
	# only as its plan says, so its bead lights only once it has said Ready: M8, in a wave a
	# lit mark reads as a call for the next)
	var lit := s.ready or (s.state != SimTypes.SEAT_PRESENT and _anyone_present(sim, h))
	# My own bead lights from my press at once, as the horn button does, before the turn
	# that carries it runs (the simulation's Ready follows a round trip later).
	var controller: BuildController = main.get("controller") if main else null
	if mine and s.state == SimTypes.SEAT_PRESENT and controller != null:
		lit = controller.wants_ready()
	ready.set_lit(lit)


## Whether a seat of hollow `h` is present: the hollow's horn waits for its players, and a
## caretaken seat beside them counts as Ready (SimWaves._all_ready).
static func _anyone_present(sim: SimMatch, h: SimRecords.SimHollow) -> bool:
	for n in h.seats:
		if sim.seat(n).state == SimTypes.SEAT_PRESENT:
			return true
	return false


## (M8) Whether a present seat of hollow `h` has called the next wave during this one.
static func _calls_on(sim: SimMatch, h: SimRecords.SimHollow) -> bool:
	for n in h.seats:
		var s := sim.seat(n)
		if s.ready and s.state == SimTypes.SEAT_PRESENT:
			return true
	return false


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
