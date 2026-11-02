## The duel bar (design 1.4 and 5.7, contract-m7.md §3): in a duel, a plate hung under the
## resource strip on the right, where a race's rival line hangs, with a row for each side,
## mine first: the lives its Holdfast keeps, the breach it has dealt (the lives its uncorked
## creeps took from the other side), the stipend it earns a wave from the packs it has
## uncorked, and its Seawall charges as gems, mine beside the F key that bursts one and,
## while the last still stands, the seconds until the next may. Hovering a side's Seawall (or
## its column's caption) explains it on a plate hung under the bar, from the rules' seawall
## block: what a burst does, how it charges, how long after one the next may come, and where
## it stands now. It reads Game (the duel's records) and decides nothing.
##
## (M8, contract-m8 §4) While the rival has a bottle corked for the coming or running wave,
## its row ends with the bottle's tier and its candidates by check, the glyphs of the checks
## a defender holds gold for: "corked II: Swarm, Armored or Winged". It stands at the end of
## the rival's Seawall cell but explains itself: hovering it, the plate speaks of the corked
## bottles (their tiers, waves and the packs each may hold, as the Drift tray's do), not of
## the Seawall.
class_name DuelBar
extends PanelContainer

const COLUMNS := ["", "LIVES", "BREACH", "STIPEND", "SEAWALL"]

var _bold: Font
var _body: Font
var _caps: Font
## Per side (0 mine, 1 the rival's): {"name", "lives", "breach", "stipend", "gems", "key", "wait"}.
var _rows: Array = []
var _shown: Array = []
## The explaining plate under the bar, and which side's Seawall it speaks of (-1: none).
var _tip: PanelContainer
var _tip_title: Label
var _tip_body: Label
var _hovered := -1
## (M8) Whether the pointer is on the rival's corked cell (inside its Seawall's): the plate
## then speaks of the corked bottles.
var _hover_corked := false


func setup(plate: StyleBox, fonts: Array, icons: Dictionary) -> void:
	_bold = fonts[0]
	_body = fonts[1]
	_caps = fonts[2]
	name = "DuelBar"
	add_theme_stylebox_override("panel", plate)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var grid := GridContainer.new()
	grid.name = "Grid"
	grid.columns = COLUMNS.size()
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 1)
	grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(grid)
	for caption: String in COLUMNS:
		var head := _label(caption, _caps, 10, Hud.DIM)
		head.add_theme_constant_override("outline_size", 0)
		grid.add_child(head)
		if caption == "SEAWALL":
			head.name = "SeawallHead"
			_hoverable(head, 0)
	for side in 2:
		var row := {}
		var who := _label("You" if side == 0 else "Rival", _bold, 14, PartyStrip.MINE if side == 0 else Hud.TEXT)
		who.name = "Side%d" % side
		who.custom_minimum_size.x = 44
		grid.add_child(who)
		row["name"] = who
		row["lives"] = _cell(grid, icons["lives"], "Lives%d" % side, Hud.TEXT)
		row["breach"] = _cell(grid, icons["breach"], "Breach%d" % side, Hud.TEXT)
		row["stipend"] = _cell(grid, icons["gold"], "Stipend%d" % side, Hud.COIN)
		var wall := HBoxContainer.new()
		wall.name = "Seawall%d" % side
		wall.add_theme_constant_override("separation", 3)
		grid.add_child(wall)
		_hoverable(wall, side)
		wall.add_child(_icon(icons["seawall"], Vector2(18, 18)))
		var gems := Gems.new()
		gems.name = "Gems"
		gems.mouse_filter = Control.MOUSE_FILTER_IGNORE  # (the Seawall cell explains itself)
		gems.custom_minimum_size = Vector2(24, 14)
		gems.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		wall.add_child(gems)
		row["gems"] = gems
		var key := _key_tab("F")
		key.visible = side == 0
		wall.add_child(key)
		row["key"] = key
		var wait := _label("", _body, 12, Hud.DIM)
		wait.name = "Wait"
		wait.add_theme_constant_override("outline_size", 0)
		wall.add_child(wait)
		row["wait"] = wait
		if side == 1:
			row["corked"] = _corked_cell(wall)
		_rows.append(row)
	_build_tip(plate)
	visible = false


## The two rows as shown, mine first, for tests: "You · 18 lives · 3 breach · +10 a wave ·
## Seawall 2 (F)", the rival's without the key; " · ready in 12 s" while a Seawall stands;
## (M8) the rival's ending " · corked II: Swarm, Armored or Winged" while a bottle of theirs
## is corked.
func lines() -> Array[String]:
	var out: Array[String] = []
	for line: String in _shown:
		out.append(line)
	return out


## The explaining plate's title and body while a Seawall (or, M8, the rival's corked cell)
## is hovered, else ["", ""].
func tip_shown() -> Array:
	return [_tip_title.text, _tip_body.text] if _tip.visible else ["", ""]


## Follows the duel's records: called every frame by the HUD while a duel plays.
func refresh() -> void:
	var shown := []
	for side in 2:
		var team := Game.my_team() if side == 0 else 1 - Game.my_team()
		var d := Game.duel_side(team)
		var row: Dictionary = _rows[side]
		var lives := int(d["lives"])
		(row["lives"] as Label).text = str(lives)
		(row["lives"] as Label).add_theme_color_override("font_color", _health_tone(lives, Game.max_lives()))
		(row["breach"] as Label).text = str(int(d["breach"]))
		(row["stipend"] as Label).text = "+%d" % int(d["stipend"])
		var gems: Gems = row["gems"]
		var charges := int(d["charges"])
		var most := int(Game.duel_rules()["seawall"]["charges"])
		if gems.full != charges or gems.most != most:
			gems.full = charges
			gems.most = most
			gems.queue_redraw()
		var wait := ""
		var left := int(d["ready_tick"]) - Game.sim.tick
		if left > 0:
			wait = "%d s" % ceili(left / float(SimTypes.TICKS_PER_SECOND))
		(row["wait"] as Label).text = wait
		(row["key"] as Control).modulate = Color.WHITE if side == 0 and Game.seawall_refusal() == "" else Color(1, 1, 1, 0.5)
		var line := "%s · %d %s · %d breach · +%d a wave · Seawall %d" % [
			"You" if side == 0 else "Rival", lives, "life" if lives == 1 else "lives", int(d["breach"]),
			int(d["stipend"]), charges
		]
		if side == 0:
			line += " (F)"
		if wait != "":
			line += " · ready in " + wait
		if side == 1:
			var corked := _show_corked(row["corked"])
			if corked != "":
				line += " · " + corked
		shown.append(line)
	_shown = shown
	if _hovered >= 0 or _hover_corked:
		_update_tip()


# ── The explaining plate ──


## `control` explains side `side`'s Seawall while the pointer is on it.
func _hoverable(control: Control, side: int) -> void:
	control.mouse_filter = Control.MOUSE_FILTER_STOP
	control.mouse_entered.connect(func() -> void: _hover(side))
	control.mouse_exited.connect(func() -> void: _hover(-1))


func _build_tip(plate: StyleBox) -> void:
	_tip = PanelContainer.new()
	_tip.name = "SeawallTip"
	_tip.add_theme_stylebox_override("panel", plate)
	_tip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tip.top_level = true
	_tip.visible = false
	add_child(_tip)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 2)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tip.add_child(col)
	_tip_title = _label("", Hud.TITLE_FONT, 16, Hud.GOLD)
	col.add_child(_tip_title)
	_tip_body = _label("", _body, 13, Hud.TEXT)
	_tip_body.name = "SeawallTipBody"
	_tip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tip_body.custom_minimum_size.x = 320
	_tip_body.add_theme_constant_override("outline_size", 0)
	col.add_child(_tip_body)


func _hover(side: int) -> void:
	_hovered = side
	_update_tip()


## (M8) The pointer came onto (or left) the rival's corked cell.
func _hover_bottles(on: bool) -> void:
	_hover_corked = on
	_update_tip()


## The plate for what the pointer is on: the rival's corked bottles while on their cell and
## one is corked (M8), else the hovered side's Seawall, else nothing.
func _update_tip() -> void:
	if _hover_corked and Game.is_duel() and not Game.rival_bottles().is_empty():
		_show_bottles_tip()
	elif _hovered >= 0:
		_show_tip(_hovered)
	else:
		_tip.visible = false


## (M8) The rival's corked bottles in words, one paragraph each (Game.rival_bottle_text).
func _show_bottles_tip() -> void:
	var bottles := Game.rival_bottles()
	var paras := PackedStringArray()
	for b: Dictionary in bottles:
		paras.append(Game.rival_bottle_text(b, bottles))
	_tip_title.text = "Your rival's corked bottle" if bottles.size() == 1 else "Your rival's corked bottles"
	_tip_body.text = "\n".join(paras)
	_place_tip()


## Side `side`'s Seawall in words: mine, the rules (Game.seawall_rule_text) and where it
## stands, what the seconds beside F count down to; the rival's, its charges.
func _show_tip(side: int) -> void:
	if not Game.is_duel():
		_tip.visible = false
		return
	var team := Game.my_team() if side == 0 else 1 - Game.my_team()
	var d := Game.duel_side(team)
	var charges := int(d["charges"])
	var left := int(d["ready_tick"]) - Game.sim.tick
	var held := "No charge" if charges == 0 else "%d %s" % [charges, "charge" if charges == 1 else "charges"]
	var now := PackedStringArray()
	if left > 0:
		now.append("%s now. The seconds beside F count down to when the next may burst: %d s." % [
			held, ceili(left / float(SimTypes.TICKS_PER_SECOND))
		])
	else:
		now.append(("%s ready." % held) if charges > 0 else "No charge yet.")
	var more := int(d["to_charge"])
	if more > 0:
		now.append(
			"%d more %s %s." % [
				more, "life lost earns" if more == 1 else "lives lost earn", "one" if charges == 0 else "another"
			]
		)
	if side == 0:
		_tip_title.text = "Seawall (F)"
		_tip_body.text = Game.seawall_rule_text() + "\n" + " ".join(now)
	else:
		_tip_title.text = "Your rival's Seawall"
		_tip_body.text = "It bursts round your rival's Holdfast as yours does round yours. %s." % held
	_place_tip()


## Shows the plate hung under the bar, its right edge with the bar's.
func _place_tip() -> void:
	_tip.visible = true
	_tip.reset_size()
	var shown := _tip.get_combined_minimum_size()
	var rect := get_global_rect()
	_tip.global_position = Vector2(rect.end.x - shown.x, rect.end.y + 4)


## (M8) The rival's corked bottles at the row's end: their tiers ("II", "III ×2"), then the
## glyph of each check one of them may hold, dimmed, in CHECK_IDS order. Returns the words
## lines() says, "corked II: Swarm, Armored or Winged", or "" while none is corked.
func _show_corked(cell: Dictionary) -> String:
	var bottles := Game.rival_bottles()
	var box: HBoxContainer = cell["box"]
	box.visible = not bottles.is_empty()
	if bottles.is_empty():
		return ""
	var tiers := PackedStringArray()
	for b: Dictionary in bottles:
		var tier_name: String = Game.TIER_NAMES[clampi(int(b["tier"]), 0, 2)]
		if not tiers.has(tier_name):
			tiers.append(tier_name)
	var tier_words := ", ".join(tiers)
	if tiers.size() == 1 and bottles.size() > 1:
		tier_words += " ×%d" % bottles.size()
	(cell["tier"] as Label).text = tier_words
	var checks := []
	for check: String in SimContent.CHECK_IDS:
		for b: Dictionary in bottles:
			if (b.get("candidates", []) as Array).has(check) and not checks.has(check):
				checks.append(check)
	var glyphs: HBoxContainer = cell["glyphs"]
	for i in glyphs.get_child_count():
		var glyph := glyphs.get_child(i) as TextureRect
		glyph.visible = i < checks.size()
		if glyph.visible and str(glyph.get_meta("check", "")) != checks[i]:
			glyph.texture = Game.icon(str(Game.CHECKS[checks[i]]["icon"]))
			glyph.tooltip_text = str(Game.CHECKS[checks[i]]["name"])
			glyph.set_meta("check", checks[i])
	var words := Game.candidate_checks(bottles)
	return "corked %s: %s" % [tier_words, words] if words != "" else "corked %s" % tier_words


## (M8) The rival's corked cell, at the end of its Seawall's: a dim "corked" caption, the
## tiers in gold and up to four check glyphs.
func _corked_cell(wall: HBoxContainer) -> Dictionary:
	var box := HBoxContainer.new()
	box.name = "Corked"
	box.add_theme_constant_override("separation", 3)
	# (it explains the bottles, not the Seawall whose cell it ends: the pointer on it is
	# still on the wall, which hears no exit while it stays within its children)
	box.mouse_filter = Control.MOUSE_FILTER_STOP
	box.mouse_entered.connect(_hover_bottles.bind(true))
	box.mouse_exited.connect(_hover_bottles.bind(false))
	box.visible = false
	wall.add_child(box)
	var gap := Control.new()
	gap.custom_minimum_size.x = 6
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(gap)
	var caption := _label("corked", _body, 12, Hud.DIM)
	caption.add_theme_constant_override("outline_size", 0)
	box.add_child(caption)
	var tier := _label("", Hud.TITLE_FONT, 14, Hud.GOLD)
	tier.name = "CorkedTier"
	box.add_child(tier)
	var glyphs := HBoxContainer.new()
	glyphs.name = "CorkedChecks"
	glyphs.add_theme_constant_override("separation", 1)
	glyphs.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(glyphs)
	for i in SimContent.CHECK_IDS.size():
		var glyph := _icon(null, Vector2(16, 16))
		glyph.modulate = Color(1, 1, 1, 0.85)
		glyph.visible = false
		glyphs.add_child(glyph)
	return {"box": box, "tier": tier, "glyphs": glyphs}


func _cell(grid: GridContainer, texture: Texture2D, node_name: String, color: Color) -> Label:
	var cell := HBoxContainer.new()
	cell.add_theme_constant_override("separation", 3)
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
	grid.add_child(cell)
	cell.add_child(_icon(texture, Vector2(16, 16)))
	var value := _label("", _bold, 14, color)
	value.name = node_name
	value.custom_minimum_size.x = 22
	cell.add_child(value)
	return value


func _icon(texture: Texture2D, size: Vector2) -> TextureRect:
	var rect := TextureRect.new()
	rect.texture = texture
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	rect.custom_minimum_size = size
	rect.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect


func _key_tab(key: String) -> Panel:
	var tab := Panel.new()
	tab.name = "KeyTab"
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0, 0, 0, 0.7)
	box.set_corner_radius_all(3)
	tab.add_theme_stylebox_override("panel", box)
	tab.custom_minimum_size = Vector2(14, 14)
	tab.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	tab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var label := _label(key, _bold, 10, Hud.KEY)
	label.name = "Hotkey"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_constant_override("outline_size", 0)
	label.set_anchors_preset(Control.PRESET_FULL_RECT)
	tab.add_child(label)
	return tab


static func _health_tone(value: float, full: float) -> Color:
	var share := value / maxf(1.0, full)
	if share > 0.6:
		return Color("#9be06a")
	return Color("#ffd166") if share > 0.3 else Color("#ff7a5a")


func _label(text: String, font: Font, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


## The Seawall's charges: `most` small sea-glass gems, the first `full` of them lit.
class Gems:
	extends Control
	var full := 0
	var most := 2

	func _draw() -> void:
		var r := minf(size.y * 0.42, 6.0)
		for i in most:
			var c := Vector2(r + 1.0 + i * (2.0 * r + 4.0), size.y * 0.5)
			var points := PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r), c + Vector2(-r, 0)])
			draw_colored_polygon(points, Fx.SEA_GLASS if i < full else Color(0.12, 0.1, 0.08, 0.9))
			points.append(points[0])
			draw_polyline(points, Color("#e9d39a") if i < full else Color("#5c4b33"), 1.2, true)
