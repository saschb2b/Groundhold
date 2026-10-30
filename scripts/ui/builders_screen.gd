## The Builders screen (design 5.4). One job: understand a Builder and choose your main and
## backup. The left well holds the roster as a 2 x 2 grid (main marked with a gold pip,
## backup with a pale one); the arch the selected Builder: name, epithet, role,
## difficulty, passive, the checks it is strong and weak against; the right well its three
## towers on Q W E (hovering one shows the command tooltip: cost, numbers, both branches)
## and Main, Backup, Try below. Above the console the kit plate lays out each tower and
## its two branches. Everything is unlocked (design 10, adopted). Esc goes back.
class_name BuildersScreen
extends Control

const SLOTS := 4

var shell: Shell
var selected := ""
var _cells: Array = []
var _title: Label
var _subtitle: Label
var _stars: Shell.Stars
var _passive: Label
var _strong: CoverageRow
var _weak: CoverageRow
var _weak_caption: Label
var _towers: Array[Button] = []
var _main: Button
var _backup: Button
var _try: Button
var _kit: GridContainer
var _kit_plate: PanelContainer
var _tooltip: PanelContainer
var _tip_title: Label
var _tip_key: Label
var _tip_cost: Label
var _tip_body: Label


func setup(owner: Shell) -> void:
	shell = owner
	name = "BuildersScreen"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_build_header()
	_build_roster()
	_build_arch()
	_build_card()
	_build_kit()
	_build_tooltip()


func refresh() -> void:
	if selected == "" or not SimContent.BUILDERS.has(selected):
		selected = Session.profile.main
	select(selected)


## Shows `builder` in the arch, the card and the kit plate.
func select(builder: String) -> void:
	selected = builder
	var info: Dictionary = SimContent.BUILDERS[builder]
	shell.show_builder(builder)
	for i in _cells.size():
		_fill_cell(_cells[i], SimContent.BUILDER_IDS[i] if i < SimContent.BUILDER_IDS.size() else "")
	_title.text = str(info["name"])
	_subtitle.text = "%s · %s" % [info["title"], Game.ROLES[info["role"]]["name"]]
	_stars.count = int(info["difficulty"])
	_stars.queue_redraw()
	var perk: Dictionary = Game.PERKS[info["perk"]["id"]]
	_passive.text = "%s: %s" % [perk["name"], perk["text"]]
	_passive.tooltip_text = _passive.text
	var strong: Array = info["covers"]
	_strong.set_builders([builder], strong)
	var weak := SimContent.CHECK_IDS.filter(func(c: String) -> bool: return not strong.has(c))
	_weak.set_builders([builder], weak)
	_weak_caption.visible = not weak.is_empty()
	for slot in 3:
		var tower := SimContent.kit_tower(builder, slot)
		var icon := _towers[slot].get_node("Icon") as TextureRect
		icon.texture = Game.icon(str(Game.TOWERS[tower]["icon"]))
	_main.disabled = builder == Session.profile.main
	_backup.disabled = builder == Session.profile.backup
	Shell.set_lit(_main, builder == Session.profile.main)
	Shell.set_lit(_backup, builder == Session.profile.backup)
	Shell.set_words(_main, "Main" if builder != Session.profile.main else "Your main")
	Shell.set_words(_backup, "Backup" if builder != Session.profile.backup else "Your backup")
	_fill_kit(builder)


## Esc back to the hub; Q W E show a tower's tooltip; 1 to 4 pick from the roster.
func key(code: int) -> void:
	match code:
		KEY_ESCAPE, KEY_BACKSPACE:
			_hover(-1)
			Session.show_screen("hub")
		KEY_Q, KEY_W, KEY_E:
			_hover([KEY_Q, KEY_W, KEY_E].find(code))
		KEY_1, KEY_2, KEY_3, KEY_4:
			var i := code - KEY_1
			if i < SimContent.BUILDER_IDS.size():
				select(SimContent.BUILDER_IDS[i])


## Whether the arch shows the selected Builder's passive whole, on its one line (the
## arch's text rect), with nothing cut: the only line that explains the perk.
func passive_fits() -> bool:
	var font := _passive.get_theme_font("font")
	var size := _passive.get_theme_font_size("font_size")
	return font.get_string_size(_passive.text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x <= _passive.size.x


## The roster as one line per cell, for tests: "lamplighter main", "lookout backup", "".
func roster_lines() -> Array[String]:
	var out: Array[String] = []
	for cell: Dictionary in _cells:
		var parts: Array[String] = [str(cell["id"])]
		if (cell["main"] as Control).visible:
			parts.append("main")
		if (cell["backup"] as Control).visible:
			parts.append("backup")
		out.append(" ".join(parts).strip_edges())
	return out


## The command tooltip for kit slot `slot` (0 to 2) of `builder`: name, key, cost, and
## the in-game card's own body (Game.kit_tip: what it does, its numbers with the Builder's
## perk in High Water, the hub's mode, and both branches), so the two never differ.
static func tower_tip(builder: String, slot: int) -> Dictionary:
	var tower := SimContent.kit_tower(builder, slot)
	var perks := bool(SimContent.RULES[Profile.played_mode(Session.profile.mode)].get("perks", false))
	var bonus := SimContent.perk_value(builder, "keen_sight", "range_mm", 0) if perks else 0
	return {
		"title": str(Game.TOWERS[tower]["name"]),
		"key": Game.CARD_KEYS[slot],
		"cost": int(SimContent.TOWERS[tower]["cost"]),
		"body": Game.kit_tip(builder, slot, bonus),
	}


# ── Building ──


func _build_header() -> void:
	var back := Button.new()
	back.name = "Back"
	back.text = "‹ Hub (Esc)"
	back.focus_mode = Control.FOCUS_NONE
	back.position = Vector2(14, 10)
	back.custom_minimum_size = Vector2(120, 34)
	back.add_theme_font_size_override("font_size", 14)
	back.pressed.connect(func() -> void: key(KEY_ESCAPE))
	add_child(back)
	var title := Shell.label("BUILDERS", Shell.TITLE_FONT, 24, Shell.GOLD)
	title.name = "ScreenTitle"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.anchor_left = 0.5
	title.anchor_right = 0.5
	title.offset_left = -200
	title.offset_right = 200
	title.offset_top = 10
	title.offset_bottom = 44
	add_child(title)


func _build_roster() -> void:
	var wing := Shell.piece(self, "RosterWing", 0.0, 0.0, Shell.vec("wing"))
	var grid := GridContainer.new()
	grid.name = "Roster"
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 4)
	grid.add_theme_constant_override("v_separation", 2)
	Shell.place(grid, Shell.rect("map_well").grow_individual(-4, -3, -4, -3))
	wing.add_child(grid)
	for i in SLOTS:
		_cells.append(_make_cell(grid, i))


func _make_cell(parent: Control, index: int) -> Dictionary:
	var cell := Button.new()
	cell.name = "Cell%d" % (index + 1)
	cell.focus_mode = Control.FOCUS_NONE
	cell.custom_minimum_size = Vector2(78, 51)
	var glow := HdStyleBox.new(load(Shell.ART + "card_glow.tres"), Shell.k())
	for st: String in ["normal", "disabled", "focus"]:
		cell.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	for st: String in ["hover", "pressed", "hover_pressed"]:
		cell.add_theme_stylebox_override(st, glow)
	parent.add_child(cell)
	var ring := Panel.new()
	ring.name = "Ring"
	ring.add_theme_stylebox_override("panel", glow)
	ring.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cell.add_child(ring)
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.position = Vector2(23, 2)
	icon.size = Vector2(32, 32)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cell.add_child(icon)
	var role := Shell.caps("", 9)
	role.name = "Role"
	role.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	role.position = Vector2(0, 35)
	role.size = Vector2(78, 14)
	cell.add_child(role)
	var main := Pip.new(Shell.GOLD)
	main.name = "MainPip"
	main.position = Vector2(4, 4)
	main.tooltip_text = "Your main"
	cell.add_child(main)
	var backup := Pip.new(Color("#c9c2b4"))
	backup.name = "BackupPip"
	backup.position = Vector2(4, 4)
	backup.tooltip_text = "Your backup"
	cell.add_child(backup)
	cell.pressed.connect(func() -> void:
		var id := str(_cells[index]["id"])
		if id != "":
			select(id))
	return {"button": cell, "ring": ring, "icon": icon, "role": role, "main": main, "backup": backup, "id": ""}


func _fill_cell(cell: Dictionary, id: String) -> void:
	cell["id"] = id
	var button: Button = cell["button"]
	button.disabled = id == ""
	(cell["ring"] as Control).visible = id != "" and id == selected
	(cell["main"] as Control).visible = id != "" and id == Session.profile.main
	(cell["backup"] as Control).visible = id != "" and id == Session.profile.backup
	var icon: TextureRect = cell["icon"]
	var role: Label = cell["role"]
	if id == "":
		# (a seat in the roster for the Builders still to come: an empty socket)
		icon.texture = Game.placeholder_icon()
		icon.modulate = Color(1, 1, 1, 0.25)
		role.text = ""
		button.tooltip_text = ""
		return
	var info: Dictionary = SimContent.BUILDERS[id]
	icon.texture = Game.icon(str(Game.BUILDERS[id]["glyph"]))
	icon.modulate = Game.glyph_tint(id)
	role.text = str(Game.ROLES[info["role"]]["name"]).to_upper()
	button.tooltip_text = "%s, %s" % [info["name"], info["title"]]


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
	line.add_theme_constant_override("separation", 8)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_child(line)
	_subtitle = Shell.label("", Shell.BOLD_FONT, 13, Shell.DIM)
	_subtitle.add_theme_constant_override("outline_size", 0)
	line.add_child(_subtitle)
	_stars = Shell.Stars.new()
	_stars.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(_stars)
	_passive = Shell.label("", Shell.BODY_FONT, 12, Shell.TEXT)
	_passive.name = "Passive"
	_passive.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_passive.mouse_filter = Control.MOUSE_FILTER_PASS
	_passive.add_theme_constant_override("outline_size", 0)
	info.add_child(_passive)
	var checks := HBoxContainer.new()
	checks.mouse_filter = Control.MOUSE_FILTER_IGNORE
	checks.add_theme_constant_override("separation", 6)
	info.add_child(checks)
	checks.add_child(_aligned(Shell.caps("Strong", 10, Shell.GOLD)))
	_strong = CoverageRow.new(18.0, false)
	_strong.name = "Strong"
	checks.add_child(_strong)
	var spacer := Control.new()
	spacer.custom_minimum_size.x = 8
	checks.add_child(spacer)
	_weak_caption = _aligned(Shell.caps("Weak", 10))
	checks.add_child(_weak_caption)
	_weak = CoverageRow.new(18.0, false)
	_weak.name = "Weak"
	checks.add_child(_weak)


func _aligned(l: Label) -> Label:
	l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return l


func _build_card() -> void:
	var wing := Shell.vec("wing")
	var right := Shell.piece(self, "KitWing", 1.0, -wing.x, wing)
	var card := Control.new()
	card.name = "KitCard"
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	Shell.place(card, Shell.rect("card_well"))
	right.add_child(card)
	var buttons := []
	for slot in 3:
		var button := Shell.icon_socket("Tower%d" % (slot + 1), Game.placeholder_icon(), Game.CARD_KEYS[slot])
		button.mouse_entered.connect(_hover.bind(slot))
		button.mouse_exited.connect(_hover.bind(-1))
		_towers.append(button)
		buttons.append(button)
	_main = Shell.socket("SetMain", "Main")
	_main.tooltip_text = "Play this Builder"
	_main.pressed.connect(func() -> void:
		Session.set_main(selected)
		select(selected))
	_backup = Shell.socket("SetBackup", "Backup")
	_backup.tooltip_text = "Your second choice, when a party already has your main"
	_backup.pressed.connect(func() -> void:
		Session.set_backup(selected)
		select(selected))
	_try = Shell.socket("Try", "Try")
	_try.tooltip_text = "A solo practice match with this Builder, offline"
	_try.pressed.connect(func() -> void: Session.try_builder(selected))
	buttons.append_array([_main, _backup, _try])
	Shell.lay_card(card, buttons)


## The kit plate: each tower with its cost, and its two branches with their cost, what
## they change and the check they help, under the screen's title.
func _build_kit() -> void:
	_kit_plate = PanelContainer.new()
	_kit_plate.name = "KitPlate"
	_kit_plate.add_theme_stylebox_override("panel", Shell.panel_box())
	Shell.crown(_kit_plate)
	_kit_plate.anchor_left = 0.5
	_kit_plate.anchor_right = 0.5
	_kit_plate.offset_left = -330
	_kit_plate.offset_right = 330
	# (low enough that its jewel clears the screen's title)
	_kit_plate.offset_top = 56 + float(Shell.layout()["panel_jewel"]["seat"][1])
	_kit_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_kit_plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	_kit_plate.add_child(box)
	box.add_child(Shell.caps("Kit", 12, Shell.GOLD))
	_kit = GridContainer.new()
	_kit.name = "Kit"
	_kit.columns = 5
	_kit.add_theme_constant_override("h_separation", 12)
	_kit.add_theme_constant_override("v_separation", 3)
	box.add_child(_kit)


func _fill_kit(builder: String) -> void:
	for child in _kit.get_children():
		child.free()
	for slot in 3:
		var tower := SimContent.kit_tower(builder, slot)
		var stats: Dictionary = SimContent.TOWERS[tower]
		for b in 2:
			var branch_id := str(SimContent.BUILDERS[builder]["branches"][slot][b])
			if b == 0:
				var head := HBoxContainer.new()
				head.add_theme_constant_override("separation", 6)
				var icon := TextureRect.new()
				icon.texture = Game.icon(str(Game.TOWERS[tower]["icon"]))
				icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				icon.custom_minimum_size = Vector2(22, 22)
				head.add_child(icon)
				head.add_child(Shell.label(str(Game.TOWERS[tower]["name"]), Shell.BOLD_FONT, 14, Shell.TEXT))
				head.add_child(Shell.label(str(stats["cost"]), Shell.BOLD_FONT, 13, Color("#f6d06a")))
				_kit.add_child(head)
			else:
				_kit.add_child(Control.new())
			_kit.add_child(Shell.label(Game.FORK_MARK, Shell.BOLD_FONT, 14, Shell.DIM))
			_kit.add_child(Shell.label(str(Game.TOWERS[branch_id]["name"]), Shell.BOLD_FONT, 13, Shell.GOLD))
			_kit.add_child(Shell.label("+%d  %s" % [int(stats["fork_cost"]), Game.TOWERS[branch_id]["gain"]], Shell.BODY_FONT, 13, Shell.TEXT))
			var helps := SimContent.branch_helps(builder, branch_id)
			var glyph := TextureRect.new()
			glyph.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			glyph.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			glyph.custom_minimum_size = Vector2(18, 18)
			glyph.mouse_filter = Control.MOUSE_FILTER_STOP
			if helps != "":
				glyph.texture = Game.icon(str(Game.CHECKS[helps]["icon"]))
				glyph.tooltip_text = "Lifts %s to passable" % Game.CHECKS[helps]["name"]
			_kit.add_child(glyph)
	for child in _kit.get_children():
		if child is Label:
			(child as Label).add_theme_constant_override("outline_size", 0)
		(child as Control).mouse_filter = (
			Control.MOUSE_FILTER_STOP if child is TextureRect and (child as TextureRect).texture else Control.MOUSE_FILTER_IGNORE
		)


func _build_tooltip() -> void:
	_tooltip = PanelContainer.new()
	_tooltip.name = "TowerTip"
	_tooltip.add_theme_stylebox_override("panel", Shell.plate_box(Vector4(14, 9, 14, 11)))
	_tooltip.anchor_left = 1.0
	_tooltip.anchor_right = 1.0
	_tooltip.anchor_top = 1.0
	_tooltip.anchor_bottom = 1.0
	_tooltip.offset_left = -330
	_tooltip.offset_right = -14
	_tooltip.offset_top = -Shell.vec("wing").y + 2
	_tooltip.offset_bottom = _tooltip.offset_top
	_tooltip.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tooltip.visible = false
	add_child(_tooltip)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	_tooltip.add_child(box)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 6)
	box.add_child(head)
	_tip_title = Shell.label("", Shell.TITLE_FONT, 17, Shell.GOLD)
	head.add_child(_tip_title)
	_tip_key = Shell.label("", Shell.BOLD_FONT, 13, Shell.KEY)
	_tip_key.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tip_key.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(_tip_key)
	_tip_cost = Shell.label("", Shell.BOLD_FONT, 15, Color("#f6d06a"))
	head.add_child(_tip_cost)
	_tip_body = Shell.label("", Shell.BODY_FONT, 13, Shell.TEXT)
	_tip_body.name = "TowerTipBody"
	_tip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tip_body.custom_minimum_size.x = 290
	_tip_body.add_theme_constant_override("outline_size", 0)
	box.add_child(_tip_body)


func _hover(slot: int) -> void:
	if slot < 0:
		_tooltip.visible = false
		return
	var tip := tower_tip(selected, slot)
	_tip_title.text = str(tip["title"])
	_tip_key.text = "(%s)" % tip["key"]
	_tip_cost.text = str(tip["cost"])
	_tip_body.text = str(tip["body"])
	_tooltip.visible = true


## The main's and the backup's mark on a roster cell.
class Pip:
	extends Control
	var color := Color.WHITE

	func _init(tint: Color) -> void:
		color = tint
		size = Vector2(10, 10)
		custom_minimum_size = size
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _draw() -> void:
		var c := size * 0.5
		draw_circle(c, 5.0, Color(0.04, 0.03, 0.02, 0.9))
		draw_circle(c, 3.6, color)
