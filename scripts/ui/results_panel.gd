## Results, the Ebb (design 5.8): an overlay on the finished hollow, on the end plate art
## widened. The title in the game's words, one line of the match (mode, waves, time, lives
## left), the lives along the waves, then one row per player: Builder, kills, damage,
## help, towers (and how many forked), and one positive line picked from a fixed list by
## the player's best stat relative to the team (ties go to the lower seat; no line
## repeats; no MVP). Every number comes from the simulation, so every client shows the
## same. Play again goes back to the hub with the party kept; Hub does the same.
## It never times out into the hub.
class_name ResultsPanel
extends CanvasLayer

const TITLES := {
	"won": "The Holdfast Holds",
	"lost": "The Holdfast Goes Under",
	"desynced": "The Lands Fell Out of Step",
	"aborted": "The Match Was Called Off",
	"draw": "The Tide Stands Still",
}
## The positive lines, in the list's order: [key, text]. "most_<creep>" keys are filled
## per creep kind; "held" names the wave.
const LINES := ["held", "help", "kills", "damage", "most_creep", "towers", "unsold"]
const FALLBACK := ["Kept watch", "Held the line", "Stood fast", "Saw it through"]

var results := {}
var _rows: VBoxContainer


## Builds the results from a finished match: the simulation's seats and teams, the names
## shown, the Builders chosen, the outcome, and `tally` (main.gd's count of the match's
## events: kills by seat and creep kind, kills by seat and wave, towers sold, lives after
## each wave).
static func compute(sim: SimMatch, names: Array, outcome: String, tally: Dictionary, shown_mode: String) -> Dictionary:
	var rows := []
	var team := sim.teams[0]
	for s in sim.seats:
		var i := s.seat - 1
		rows.append(
			{
				"seat": s.seat,
				"name": str(names[i]) if i < names.size() else "Seat %d" % s.seat,
				"builder": s.builder,
				"kills": s.kills,
				"damage_c": s.damage_c,
				"help_c": s.help_c,
				"towers": s.towers,
				"forks": s.forks,
				"left": s.state == SimTypes.SEAT_LEFT,
				"line": "",
			}
		)
	_pick_lines(rows, sim, tally)
	var lives := int(team.lives)
	var waves := sim.total_waves()
	var reached := sim.hollows[0].wave
	var minutes := sim.tick / 3600
	var seconds := (sim.tick / 60) % 60
	var detail := "%s · %d waves · %d:%02d · %d of %d lives left" % [
		Profile.mode_name(shown_mode), waves, minutes, seconds, lives, int(sim.rules["lives"])
	]
	if outcome == "lost":
		detail = "%s · fell in wave %d of %d · %d:%02d" % [Profile.mode_name(shown_mode), reached, waves, minutes, seconds]
	return {
		"outcome": outcome,
		"title": str(TITLES.get(outcome, "The Ebb")),
		"detail": detail,
		"rows": rows,
		"lives": tally.get("lives", []),
		"max_lives": int(sim.rules["lives"]),
		"waves": waves,
	}


## Fills each row's "line": candidates are the lines a seat truly leads the team in (ties
## to the lower seat), taken strongest share first; a seat that leads nothing gets a
## plain line of its own.
static func _pick_lines(rows: Array, sim: SimMatch, tally: Dictionary) -> void:
	var stats := {}  # line text -> Array of per-seat values
	var order := []  # line texts in the fixed list's order
	var per_wave: Dictionary = tally.get("wave_kills", {})
	var best_wave := []
	for r: Dictionary in rows:
		var top := [0, 0]  # [kills, wave]
		var waves: Dictionary = per_wave.get(int(r["seat"]), {})
		for w: int in waves:
			if int(waves[w]) > top[0] or (int(waves[w]) == top[0] and w < top[1]):
				top = [int(waves[w]), w]
		best_wave.append(top)
	for key: String in LINES:
		match key:
			"held":
				for r_i in rows.size():
					var text := "Held wave %d" % int(best_wave[r_i][1])
					var values := []
					for k in rows.size():
						values.append(int(best_wave[k][0]) if k == r_i else 0)
					if int(best_wave[r_i][0]) > 0:
						# (the seat's best wave, against the others' kills in that same wave)
						var w := int(best_wave[r_i][1])
						for k in rows.size():
							if k != r_i:
								var theirs: Dictionary = per_wave.get(int(rows[k]["seat"]), {})
								values[k] = int(theirs.get(w, 0))
						stats[text] = values
						order.append(text)
			"help", "kills", "damage", "towers":
				var field: String = {"help": "help_c", "kills": "kills", "damage": "damage_c", "towers": "towers"}[key]
				var values := []
				for r: Dictionary in rows:
					values.append(int(r[field]))
				var text := "Most " + key
				stats[text] = values
				order.append(text)
			"most_creep":
				var by_kind: Dictionary = tally.get("kind_kills", {})
				for kind: String in ["duskmoth", "thornback", "scuttler", "gourdling"]:
					if not Game.CREEPS.has(kind):
						continue
					var values := []
					for r: Dictionary in rows:
						var mine: Dictionary = by_kind.get(int(r["seat"]), {})
						values.append(int(mine.get(kind, 0)))
					var text := "Most %ss" % Game.CREEPS[kind]["name"]
					stats[text] = values
					order.append(text)
			"unsold":
				var sold: Dictionary = tally.get("sold", {})
				var values := []
				for r: Dictionary in rows:
					var clean := int(r["towers"]) > 0 and int(sold.get(int(r["seat"]), 0)) == 0
					values.append(1 if clean else 0)
				stats["No towers sold"] = values
				order.append("No towers sold")
	var candidates := []  # [share per mille, line index, seat index, text]
	for li in order.size():
		var text: String = order[li]
		var values: Array = stats[text]
		var total := 0
		var best := -1
		for k in values.size():
			total += int(values[k])
			if int(values[k]) > 0 and (best < 0 or int(values[k]) > int(values[best])):
				best = k
		if best < 0 or bool(rows[best]["left"]):
			continue
		candidates.append([int(values[best]) * 1000 / maxi(1, total), li, best, text])
	candidates.sort_custom(
		func(a: Array, b: Array) -> bool:
			if a[0] != b[0]:
				return a[0] > b[0]
			if a[1] != b[1]:
				return a[1] < b[1]
			return a[2] < b[2]
	)
	var used := {}
	for c: Array in candidates:
		var row: Dictionary = rows[int(c[2])]
		if row["line"] == "" and not used.has(c[3]):
			row["line"] = c[3]
			used[c[3]] = true
	var plain := 0
	for row: Dictionary in rows:
		if row["line"] == "" and not bool(row["left"]):
			row["line"] = FALLBACK[plain % FALLBACK.size()]
			plain += 1


func show_results(shown: Dictionary) -> void:
	results = shown
	name = "ResultsPanel"
	layer = 10
	var root := Control.new()
	root.name = "Root"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.theme = Shell.theme()
	root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(root)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.015, 0.01, 0.5)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var plate := Shell.WidePlate.new()
	plate.name = "ResultsPlate"
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -470
	plate.offset_right = 470
	plate.offset_top = -250
	plate.offset_bottom = 200
	root.add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	Shell.place(box, Rect2(46, 64, 848, 360))
	plate.add_child(box)
	var title := Shell.label(str(shown["title"]).to_upper(), Shell.TITLE_FONT, 26, Shell.GOLD)
	title.name = "ResultsTitle"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	var detail := Shell.label(str(shown["detail"]), Shell.BODY_FONT, 15, Shell.TEXT)
	detail.name = "ResultsDetail"
	detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(detail)
	var lives := LivesLine.new()
	lives.values = shown.get("lives", [])
	lives.top = int(shown.get("max_lives", 20))
	lives.waves = int(shown.get("waves", 1))
	box.add_child(lives)
	_rows = VBoxContainer.new()
	_rows.name = "Rows"
	_rows.add_theme_constant_override("separation", 3)
	box.add_child(_rows)
	_rows.add_child(_row(["Player", "Builder", "Kills", "Damage", "Help", "Towers", ""], true, -1))
	for r: Dictionary in shown["rows"]:
		var cells := []
		var builder_title := str(SimContent.BUILDERS[r["builder"]]["title"]).trim_prefix("the ")
		if bool(r["left"]):
			cells = [r["name"], builder_title, "", "", "", "", "left the match; the caretaker finished"]
		else:
			cells = [
				r["name"], builder_title, str(r["kills"]), _short(int(r["damage_c"]) / 100),
				_short(int(r["help_c"]) / 100), "%d (%d forked)" % [r["towers"], r["forks"]], r["line"]
			]
		_rows.add_child(_row(cells, false, int(r["seat"]) - 1, str(r["builder"])))
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(spacer)
	var foot := HBoxContainer.new()
	foot.alignment = BoxContainer.ALIGNMENT_CENTER
	foot.add_theme_constant_override("separation", 28)
	box.add_child(foot)
	var again := Button.new()
	again.name = "ResultsPlayAgain"
	again.text = "Play again"
	again.focus_mode = Control.FOCUS_NONE
	again.custom_minimum_size = Vector2(190, 42)
	again.add_theme_font_override("font", Shell.TITLE_FONT)
	again.add_theme_font_size_override("font_size", 17)
	again.pressed.connect(Session.play_again)
	foot.add_child(again)
	var hub := Button.new()
	hub.name = "ResultsHub"
	hub.text = "Hub"
	hub.focus_mode = Control.FOCUS_NONE
	hub.flat = true
	hub.add_theme_color_override("font_color", Shell.DIM)
	for st: String in ["normal", "hover", "pressed", "hover_pressed"]:
		hub.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	hub.pressed.connect(func() -> void: Session.to_hub())
	foot.add_child(hub)


## The player rows as one line each, for tests: "Sascha Lamplighter 12 Most kills".
func lines() -> Array[String]:
	var out: Array[String] = []
	for r: Dictionary in results.get("rows", []):
		var title := str(SimContent.BUILDERS[r["builder"]]["title"]).trim_prefix("the ")
		out.append("%s %s %d %s" % [r["name"], title, int(r["kills"]), r["line"]])
	return out


func _row(cells: Array, header: bool, seat: int, builder := "") -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "Header" if header else "Seat%d" % (seat + 1)
	row.add_theme_constant_override("separation", 18)
	var widths := [160, 140, 54, 70, 60, 124, 0]
	for i in cells.size():
		var cell: Control
		if header:
			cell = Shell.caps(str(cells[i]), 10)
		else:
			var color := Shell.TEXT
			if i == 0 and seat + 1 == Game.seat:
				color = PartyStrip.MINE
			elif i == cells.size() - 1:
				color = Shell.GOLD
			cell = Shell.label(str(cells[i]), Shell.BOLD_FONT if i in [0, 6] else Shell.BODY_FONT, 14, color)
			cell.add_theme_constant_override("outline_size", 0)
		if i >= 2 and i <= 4:
			(cell as Label).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		if i == 0 and not header:
			var lead := HBoxContainer.new()
			lead.add_theme_constant_override("separation", 6)
			lead.custom_minimum_size.x = widths[0]
			var glyph := PartyStrip.SeatGlyph.new()
			glyph.shape = PartyStrip.GLYPHS[seat % 4]
			glyph.color = PartyStrip.SEAT_COLORS[seat % 4]
			glyph.custom_minimum_size = Vector2(12, 12)
			glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			lead.add_child(glyph)
			lead.add_child(cell)
			row.add_child(lead)
			continue
		if i == 1 and not header and Game.BUILDERS.has(builder):
			# (the Builder's face beside its title, as the party rows and the strip show it)
			var who := HBoxContainer.new()
			who.add_theme_constant_override("separation", 6)
			who.custom_minimum_size.x = widths[1]
			var face := TextureRect.new()
			face.name = "Face"
			face.texture = Game.icon(str(Game.BUILDERS[builder]["glyph"]))
			face.modulate = Game.glyph_tint(builder)
			face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			face.custom_minimum_size = Vector2(22, 22)
			face.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			who.add_child(face)
			who.add_child(cell)
			row.add_child(who)
			continue
		cell.custom_minimum_size.x = widths[i]
		if widths[i] == 0:
			cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(cell)
	return row


static func _short(value: int) -> String:
	return "%.1fk" % (value / 1000.0) if value >= 1000 else str(value)


## The lives the team kept after each wave, as one gilt line from wave 1 to the last.
class LivesLine:
	extends Control
	var values: Array = []
	var top := 20
	var waves := 8

	func _init() -> void:
		custom_minimum_size = Vector2(0, 34)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var left := size.x * 0.2
		var width := size.x * 0.6
		draw_line(Vector2(left, size.y - 2), Vector2(left + width, size.y - 2), Color("#5c4b33"), 1.0)
		if values.is_empty():
			return
		var points := PackedVector2Array([Vector2(left, 2)])
		for i in values.size():
			var x := left + width * (i + 1) / float(maxi(1, waves))
			var y := 2 + (size.y - 6) * (1.0 - clampf(float(values[i]) / maxf(1, top), 0.0, 1.0))
			points.append(Vector2(x, y))
		draw_polyline(points, Shell.GOLD, 2.0, true)
		for p in points:
			draw_circle(p, 2.2, Shell.GOLD)
