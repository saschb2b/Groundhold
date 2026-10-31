## The console, laid out like a classic strategy game's but pared down: one piece of
## dark bronze and stone along the bottom edge whose top rises into an arched crest
## around the live portrait and dips low between its parts so the hollow shows
## through. A minimap on the left wing, the portrait and the selection's numbers in the
## middle, the command card on the right wing. Resources hang from a slim strip at the
## top right. The pieces are painted by art_src/ui/console.py from
## art_src/ui/console.json at twice the layout's resolution and drawn at half size, so
## they stay crisp on large screens; layout.json gives the wells and windows.
##
## The command card (design 5.7) has six slots in fixed places with the same keys for
## every Builder, Game.CARD_KEYS: Q, W, E hold my Builder's three towers; on my own
## unforked tower they become its two branches (the hammer on their frames, the check a
## branch lifts in their corner) and E empties; on my forked tower the branch taken stays
## lit and the other greys. A signals, S sells (greyed on a teammate's tower: it is
## theirs), D is Ready. The strip shows the next wave's checks, each glyph with the
## portrait of the creep that brings it (during a wave, the current wave's), and
## hovering the wave lists every wave still to come.
class_name Hud
extends CanvasLayer

const GOLD := Color("#f0cf86")
const TEXT := Color("#ece2cc")
const DIM := Color("#a3957d")
const KEY := Color("#f3e6c4")
const COIN := Color("#f6d06a")
const SHORT := Color("#ff6a50")
const NOTICE := Color("#ffd36a")
const INK := Color(0.04, 0.03, 0.02, 0.85)
const TITLE_FONT := preload("res://fonts/NotoSerifDisplay-Bold.ttf")
const BOLD_FONT := preload("res://fonts/NotoSerif-Bold.ttf")
const BODY_FONT := preload("res://fonts/NotoSerif-Regular.ttf")
const GREY := preload("res://shaders/hud_grey.gdshader")
const ART := "res://ui/console/"
const ICONS := "res://ui/icons/"
## The card's slots in place order, by the names their buttons carry.
const SLOTS := ["q", "w", "e", "signal", "sell", "ready"]
const SLOT_NODES := ["CardQ", "CardW", "CardE", "Signal", "Sell", "Ready"]
## How light a greyed command stays: readable when only unaffordable, darker when it
## does not apply (nothing selected, a fork already taken, a wave running). An idle
## command keeps a fifth of its colour, so it still reads as a command and not a hole.
const POOR_VALUE := 0.72
const IDLE_VALUE := 0.6
const IDLE_GREY := 0.8
## How long a title stays up, and a notice such as "Not enough gold".
const BANNER_HOLD := 1.8
const NOTICE_HOLD := 0.9
## A teammate's seat changed hands: a longer line, and nobody pressed anything for it.
const TEAM_NOTICE_HOLD := 3.0
## Titles: how far below the top edge they stand, above the first row of towers.
const BANNER_TOP := 24
## The strip's check glyphs and creep portraits, and the wave list's.
const GLYPH_SIZE := 22.0
const FACE_SIZE := 24.0
const ROW_GLYPH := 18.0
const ROW_FACE := 20.0

var controller: BuildController

var _layout: Dictionary
## Texels of console art per layout pixel.
var _k := 1.0
var _gold: Label
var _lives: Label
var _wave: Label
var _countdown: Label
var _checks: HBoxContainer
var _wave_list: PanelContainer
var _wave_rows: VBoxContainer
var _ready_button: Button
var _banner: TitleBanner
var _notice: Label
var _notice_tween: Tween
var _portrait: Portrait
var _creep_shown := []
var _title: Label
var _title_glyph: TextureRect
var _subtitle: Label
var _stats: HBoxContainer
var _caps: FontVariation
var _card := {}
var _tooltip: PanelContainer
var _tooltip_title: Label
var _tooltip_key: Label
var _tooltip_cost: Label
var _tooltip_coin: TextureRect
var _tooltip_body: Label
var _tooltip_helps: HBoxContainer
var _tooltip_glyph: TextureRect
var _tooltip_helps_text: Label
var _hammer: Texture2D
var _hovered := ""
var _end_panel: Control
var _end_label: Label
var _end_detail: Label
## Whether my orders would go out (Game.order_refusal() == "": the match and the link take
## them, and my seat is mine, not the caretaker's) as the HUD last showed it.
var _live := true
## The session's results plate is up (results_shown): no notice or banner over it.
var _results_up := false


func setup(main: Node) -> void:
	controller = main.controller
	_layout = (load(ART + "layout.json") as JSON).data
	_k = float(_layout.get("scale", 1))
	_build(main)
	Game.gold_changed.connect(func(_g: int) -> void: _refresh())
	Game.lives_changed.connect(func(_l: int) -> void: _refresh())
	Game.wave_changed.connect(func(_w: int) -> void: _refresh())
	Game.state_changed.connect(_on_state)
	Game.announced.connect(show_banner)
	Game.noticed.connect(show_notice)
	Game.team_noticed.connect(func(text: String) -> void: show_notice(text, TEAM_NOTICE_HOLD))
	Game.ready_changed.connect(_refresh)
	Game.towers_changed.connect(_refresh)
	controller.selection_changed.connect(func(_t: Tower) -> void: _refresh())
	controller.creep_selected.connect(func(_c: Creep) -> void: _refresh())
	controller.mode_changed.connect(func(_k2: String) -> void: _refresh())
	_refresh()


func _process(_delta: float) -> void:
	var live := Game.accepts_commands()
	var orders := Game.order_refusal() == ""
	if orders != _live:
		_live = orders
		_refresh()  # (the match started, its link went, or the caretaker took or gave back my seat)
	var ready_cost := ""
	if Game.sim == null or not live:
		# (networked, before START or after the link went: the world stands still, and
		# the party strip says why)
		_countdown.text = ""
	elif Game.state == Game.State.PREP:
		var seconds := ceili(Game.countdown)
		if Game.wave == 0:
			_countdown.text = "First wave in %d s" % seconds
		else:
			_countdown.text = "· next in %d s" % seconds
		if Game.seat_count() > 1:
			# Ready pips: how many of the party are Ready for the horn.
			var count := Game.ready_count()
			# (my own Ready as my last press asked for it, as the horn and my bead show it,
			# before the turn that carries it runs)
			var mine := Game.sim.seat(Game.seat)
			if mine.state == SimTypes.SEAT_PRESENT and controller.wants_ready() != mine.ready:
				count[0] += 1 if controller.wants_ready() else -1
			_countdown.text += " · Ready %d/%d" % [count[0], count[1]]
		if Game.early_gold() > 0 and Game.wave < Game.total_waves() and orders:
			ready_cost = "+%d" % Game.early_gold()  # the gold an early horn pays
	elif Game.state == Game.State.WAVE:
		var left := Game.creeps_left()
		_countdown.text = "· %d %s left" % [left, "creep" if left == 1 else "creeps"]
	else:
		_countdown.text = ""
	_set_cost(_ready_button, ready_cost)
	var creep := controller.selected_creep
	if creep and is_instance_valid(creep) and not creep.dead:
		# Only when what it shows changes, not every frame.
		if _creep_shown != _creep_key(creep):
			_describe_creep(creep)
	elif creep:
		controller.select_creep(null)


## A title for a moment of the game: a wave arriving, a wave cleared, the end.
func show_banner(text: String) -> void:
	if _end_panel.visible or _results_up:
		return  # the end plate says it already
	_banner.show_title(text, BANNER_HOLD)


## A short line above the selection's name for a refused order, gone in about a second and
## a half (`hold` seconds before it fades: longer for a teammate's seat).
func show_notice(text: String, hold := NOTICE_HOLD) -> void:
	if _end_panel.visible or _results_up:
		return
	_notice.text = text
	_notice.visible = true
	_notice.modulate.a = 1.0
	if _notice_tween:
		_notice_tween.kill()
	_notice_tween = create_tween()
	_notice_tween.tween_interval(hold)
	_notice_tween.tween_property(_notice, "modulate:a", 0.0, 0.6)
	_notice_tween.tween_callback(func() -> void: _notice.visible = false)


## The session's results plate is up (main.gd): what the notice and the banner said goes,
## and nothing more shows under the plate (a teammate's word, a wave's title).
func results_shown() -> void:
	_results_up = true
	clear_messages()


## The notice and the banner go at once: the world jumped to a loaded checkpoint (a
## RESYNC), and what they said is from before it.
func clear_messages() -> void:
	if _notice_tween:
		_notice_tween.kill()
	_notice.visible = false
	_banner.hide_title()


## What each card slot shows now, in place order, for tests: {"what" (a tower or form
## id, "", "signal", "sell" or "ready"), "state" ("ok", "poor", "idle" or "lit"), "cost",
## "key", "icon" (its texture's path, "" when empty), "glyph" (the check it lifts, or ""),
## "hammer" (a fork), "active" (its ring lit)}.
func card() -> Array:
	var out := []
	for slot: String in SLOTS:
		var button: Button = _card[slot]
		var icon: TextureRect = button.get_node("Icon")
		var glyph: TextureRect = button.get_node("Glyph")
		out.append(
			{
				"what": str(button.get_meta("what", "")),
				"state": str(button.get_meta("state", "ok")),
				"cost": (button.get_node("Cost") as Label).text,
				"key": (button.get_node("KeyTab/Hotkey") as Label).text,
				"key_shown": (button.get_node("KeyTab") as Control).visible,
				"icon": icon.texture.resource_path if icon.visible and icon.texture else "",
				"glyph": str(glyph.get_meta("check", "")) if glyph.visible else "",
				"hammer": (button.get_node("Hammer") as Control).visible,
				"active": (button.get_node("Ring") as Control).visible,
			}
		)
	return out


## The strip's checks as shown, for tests: [[check, creep], ..., ["boss", creep]].
func checks_shown() -> Array:
	return _checks.get_meta("shown", []) if _checks.visible else []


# ── Layout ──


func _build(main: Node) -> void:
	_caps = FontVariation.new()
	_caps.base_font = BOLD_FONT
	_caps.spacing_glyph = 1
	_hammer = _tight(ICONS + "upgrade.png")
	var root := Control.new()
	root.name = "Root"
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _theme()
	# The art has twice the texels it is drawn with: mipmaps keep it clean at any size.
	root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(root)
	_build_console(root, main)
	_build_strip(root)
	_build_wave_list(root)
	_build_party(root, main)
	_build_banner(root)
	_build_notice(root)
	_build_tooltip(root)
	_build_end_panel(root)


func _build_console(root: Control, main: Node) -> void:
	var console := Control.new()
	console.name = "Console"
	console.set_anchors_preset(Control.PRESET_FULL_RECT)
	console.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(console)

	# The low band that joins the pieces, tiled across any width.
	var rail := _art("rail.png", true)
	rail.name = "Rail"
	rail.tile = true
	rail.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	rail.anchor_left = 0.0
	rail.anchor_right = 1.0
	rail.anchor_top = 1.0
	rail.anchor_bottom = 1.0
	rail.offset_left = 0
	rail.offset_right = 0
	rail.offset_top = -float(_layout["rail"])
	rail.offset_bottom = 0
	console.add_child(rail)

	# Centre: the arched crest round the portrait, the selection's numbers beside it.
	var centre_size := _vec("centre")
	var centre := _piece(console, "Centre", 0.5, -centre_size.x * 0.5, centre_size)
	var window := _rect("window")
	# The backdrop is shaped like the window and clips the portrait to the arch.
	var backdrop := _art("portrait_bg.png")
	backdrop.name = "Backdrop"
	_place(backdrop, _rect("backdrop"))
	backdrop.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	centre.add_child(backdrop)
	_portrait = Portrait.new()
	_portrait.name = "Portrait"
	_place(_portrait, Rect2(window.position - backdrop.position, window.size))
	backdrop.add_child(_portrait)
	var crest := _art("crest.png", true)
	crest.name = "Crest"
	crest.window = window
	centre.add_child(crest)
	centre.add_child(_build_info())

	# Left wing: the minimap.
	var wing := _vec("wing")
	var left := _piece(console, "WingLeft", 0.0, 0.0, wing)
	left.add_child(_art("wing_left.png", true))
	var minimap := Minimap.new()
	minimap.name = "Minimap"
	minimap.clip_contents = true
	_place(minimap, _rect("map_well"))
	minimap.setup(main.map, main.camera)
	left.add_child(minimap)
	var shade := _art("well_shade.png")
	_place(shade, _rect("map_well"))
	left.add_child(shade)

	# Right wing: the command card, six slots in fixed places with fixed keys.
	var right := _piece(console, "WingRight", 1.0, -wing.x, wing)
	right.add_child(_art("wing_right.png", true))
	var card_well := Control.new()
	card_well.name = "CommandCard"
	card_well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_place(card_well, _rect("card_well"))
	right.add_child(card_well)
	var socket := _vec("socket")
	var gap := _vec("gap")
	for i in SLOTS.size():
		var slot: String = SLOTS[i]
		var button := _card_button(SLOT_NODES[i], Game.CARD_KEYS[i])
		button.position = Vector2(i % 3, i / 3) * (socket + gap)
		button.pressed.connect(_press.bind(i))
		button.mouse_entered.connect(_hover.bind(slot))
		button.mouse_exited.connect(_hover.bind(""))
		card_well.add_child(button)
		_card[slot] = button
	_ready_button = _card["ready"]
	_set_icon(_card["signal"], Game.SIGNAL_ICON)
	_set_icon(_card["sell"], ICONS + "sell.png")
	# The war horn: Ready. When every seat is Ready the next wave comes at once.
	_set_icon(_ready_button, ICONS + "next_wave.png")


func _press(slot: int) -> void:
	match slot:
		0, 1, 2:
			controller.press_slot(slot)
		3:
			controller.arm_signal()
		4:
			controller.sell_selected()
		5:
			controller.toggle_ready()


## One title (with the glyph of the check it brings or answers), one line under it and
## one row of numbers, clipped to the shoulder's text area.
func _build_info() -> Control:
	var info := VBoxContainer.new()
	info.name = "Info"
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.clip_contents = true
	info.add_theme_constant_override("separation", 0)
	_place(info, _rect("text"))
	var head := HBoxContainer.new()
	head.name = "Head"
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	head.add_theme_constant_override("separation", 6)
	info.add_child(head)
	# (no trimming: a trimmed label has no width of its own in a row; the text area clips)
	_title = _label("", TITLE_FONT, 21, GOLD)
	_title.name = "Title"
	_title.add_theme_constant_override("outline_size", 3)
	_title.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	head.add_child(_title)
	_title_glyph = _icon_rect(Vector2(20, 20))
	_title_glyph.name = "TitleGlyph"
	_title_glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_title_glyph.visible = false
	head.add_child(_title_glyph)
	_subtitle = _label("", BOLD_FONT, 13, DIM)
	_subtitle.name = "Subtitle"
	_subtitle.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_subtitle.add_theme_constant_override("outline_size", 0)
	info.add_child(_subtitle)
	_stats = HBoxContainer.new()
	_stats.name = "Stats"
	_stats.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stats.add_theme_constant_override("separation", 28)
	info.add_child(_stats)
	return info


## Gold, lives, the wave and its checks on a strip hanging from the top right. It is a
## nine-slice that grows leftwards, so big numbers widen it instead of spilling past its
## art. Hovering the wave lists every wave still to come.
func _build_strip(root: Control) -> void:
	var strip := ResourceStrip.new()
	strip.name = "TopBar"
	strip.setup(load(ART + "strip.tres"), _k, float(_layout["strip"]["cap"]))
	strip.anchor_left = 1.0
	strip.anchor_right = 1.0
	strip.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	strip.custom_minimum_size.y = float(_layout["strip"]["height"])
	root.add_child(strip)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 5)
	strip.add_child(row)
	_gold = _resource(row, "Gold", _tight(ICONS + "res_gold.png"), COIN, 26)
	_gap(row, 10)
	# The Holdfast, its head only and glowing (on Wickhollow the hearth's lamp): what the lives keep.
	_lives = _resource(row, "Lives", _tight(ICONS + "res_lives.png", 0.6), TEXT, 30, true)
	_gap(row, 12)
	# The wave, what comes next and when: hovered, it lists the waves to come.
	var area := HBoxContainer.new()
	area.name = "WaveArea"
	area.mouse_filter = Control.MOUSE_FILTER_PASS
	area.add_theme_constant_override("separation", 5)
	area.mouse_entered.connect(_show_wave_list.bind(true))
	area.mouse_exited.connect(_show_wave_list.bind(false))
	row.add_child(area)
	_wave = _label("", BOLD_FONT, 15, TEXT)
	_wave.name = "Wave"
	_wave.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	area.add_child(_wave)
	_countdown = _label("", BODY_FONT, 15, TEXT)
	_countdown.name = "Countdown"
	_countdown.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_countdown.custom_minimum_size.x = 98
	area.add_child(_countdown)
	_checks = HBoxContainer.new()
	_checks.name = "WaveChecks"
	_checks.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_checks.add_theme_constant_override("separation", 6)
	area.add_child(_checks)


## The waves still to come, one row each: its number, the glyphs of its checks and the
## portraits of its creeps with their counts. Under the strip, on the tooltip plate.
func _build_wave_list(root: Control) -> void:
	_wave_list = PanelContainer.new()
	_wave_list.name = "WaveList"
	_wave_list.add_theme_stylebox_override(
		"panel", HdStyleBox.new(load(ART + "tooltip.tres"), _k)
	)
	_wave_list.anchor_left = 1.0
	_wave_list.anchor_right = 1.0
	_wave_list.offset_right = -14
	_wave_list.offset_left = -14
	_wave_list.offset_top = float(_layout["strip"]["height"]) + 2
	_wave_list.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_wave_list.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wave_list.visible = false
	root.add_child(_wave_list)
	var box := VBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_theme_constant_override("separation", 4)
	_wave_list.add_child(box)
	box.add_child(_label("Waves to come", TITLE_FONT, 16, GOLD))
	_wave_rows = VBoxContainer.new()
	_wave_rows.name = "WaveRows"
	_wave_rows.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wave_rows.add_theme_constant_override("separation", 3)
	box.add_child(_wave_rows)


## The party strip, top left: a plate per player while more than one seat plays, and
## the link's state before a networked match starts (scripts/ui/party_strip.gd).
func _build_party(root: Control, main: Node) -> void:
	var source: StyleBoxTexture = load(ART + "tooltip.tres")
	var plate := HdStyleBox.new(source, _k)
	var bright := source.duplicate() as StyleBoxTexture
	bright.modulate_color = Color(1.7, 1.4, 0.95)
	var mine := HdStyleBox.new(bright, _k)
	for box: StyleBox in [plate, mine]:
		box.content_margin_left = 10
		box.content_margin_right = 12
		box.content_margin_top = 5
		box.content_margin_bottom = 6
	var party := PartyStrip.new()
	root.add_child(party)
	party.setup(main, BOLD_FONT, BODY_FONT, _tight(ICONS + "res_gold.png"), plate, mine)


## Titles stand high over the hollow, above the first row of towers.
func _build_banner(root: Control) -> void:
	_banner = TitleBanner.new()
	_banner.name = "Banner"
	_banner.anchor_left = 0.5
	_banner.anchor_right = 0.5
	_banner.offset_top = BANNER_TOP
	root.add_child(_banner)
	var title := _label("", TITLE_FONT, 24, GOLD)
	title.name = "BannerTitle"
	_banner.setup(_layout["banner"], ART, title)


## Notices sit just above the shoulder, over the column where the selection's name and
## cost are, small and quick: the eye is already there when an order is refused.
func _build_notice(root: Control) -> void:
	_notice = _label("", BOLD_FONT, 16, NOTICE)
	_notice.name = "Notice"
	_notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_notice.anchor_left = 0.5
	_notice.anchor_right = 0.5
	_notice.anchor_top = 1.0
	_notice.anchor_bottom = 1.0
	var column := -_vec("centre").x * 0.5 + _rect("text").get_center().x
	var above := float(_layout["shoulder"]) + 6
	_notice.offset_left = column - 240
	_notice.offset_right = column + 240
	_notice.offset_top = -above - 24
	_notice.offset_bottom = -above
	_notice.add_theme_constant_override("outline_size", 5)
	_notice.add_theme_color_override("font_outline_color", INK)
	_notice.visible = false
	root.add_child(_notice)


## Above the command card, like a strategy game's command tooltip: the name and its key,
## the cost on the same line, then what it does, and for a branch the check it lifts.
func _build_tooltip(root: Control) -> void:
	_tooltip = PanelContainer.new()
	_tooltip.name = "Tooltip"
	_tooltip.add_theme_stylebox_override("panel", HdStyleBox.new(load(ART + "tooltip.tres"), _k))
	_tooltip.anchor_left = 1.0
	_tooltip.anchor_right = 1.0
	_tooltip.anchor_top = 1.0
	_tooltip.anchor_bottom = 1.0
	_tooltip.offset_left = -300
	_tooltip.offset_right = -14
	_tooltip.offset_top = -_vec("wing").y + 2
	_tooltip.offset_bottom = _tooltip.offset_top
	_tooltip.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tooltip.visible = false
	root.add_child(_tooltip)
	var tip_box := VBoxContainer.new()
	tip_box.add_theme_constant_override("separation", 2)
	_tooltip.add_child(tip_box)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 6)
	tip_box.add_child(head)
	_tooltip_title = _label("", TITLE_FONT, 17, GOLD)
	head.add_child(_tooltip_title)
	_tooltip_key = _label("", BOLD_FONT, 13, KEY)
	_tooltip_key.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tooltip_key.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(_tooltip_key)
	_tooltip_coin = TextureRect.new()
	_tooltip_coin.texture = _tight(ICONS + "res_gold.png")
	_tooltip_coin.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_tooltip_coin.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_tooltip_coin.custom_minimum_size = Vector2(18, 18)
	_tooltip_coin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(_tooltip_coin)
	_tooltip_cost = _label("", BOLD_FONT, 15, COIN)
	_tooltip_cost.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(_tooltip_cost)
	_tooltip_body = _label("", BODY_FONT, 14, TEXT)
	_tooltip_body.name = "TooltipBody"
	_tooltip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tooltip_body.custom_minimum_size.x = 262
	_tooltip_body.add_theme_constant_override("outline_size", 0)
	tip_box.add_child(_tooltip_body)
	_tooltip_helps = HBoxContainer.new()
	_tooltip_helps.name = "TooltipHelps"
	_tooltip_helps.add_theme_constant_override("separation", 6)
	_tooltip_helps.visible = false
	tip_box.add_child(_tooltip_helps)
	_tooltip_glyph = _icon_rect(Vector2(ROW_GLYPH, ROW_GLYPH))
	_tooltip_glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_tooltip_helps.add_child(_tooltip_glyph)
	_tooltip_helps_text = _label("", BOLD_FONT, 13, GOLD)
	_tooltip_helps_text.add_theme_constant_override("outline_size", 0)
	_tooltip_helps.add_child(_tooltip_helps_text)


func _build_end_panel(root: Control) -> void:
	_end_panel = Control.new()
	_end_panel.name = "EndPanel"
	_end_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_end_panel.visible = false
	root.add_child(_end_panel)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.015, 0.01, 0.45)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_end_panel.add_child(dim)
	var size := Vector2(_layout["plate"]["size"][0], _layout["plate"]["size"][1])
	var plate := _art("plate.png")
	plate.set_anchors_preset(Control.PRESET_CENTER)
	plate.offset_left = -size.x * 0.5
	plate.offset_right = size.x * 0.5
	plate.offset_top = -size.y * 0.5 - 50
	plate.offset_bottom = size.y * 0.5 - 50
	_end_panel.add_child(plate)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 6)
	var text: Array = _layout["plate"]["text"]
	_place(box, Rect2(text[0], text[1], text[2], text[3]))
	plate.add_child(box)
	_end_label = _label("", TITLE_FONT, 28, GOLD)
	_end_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_end_label)
	_end_detail = _label("", BODY_FONT, 15, TEXT)
	_end_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_end_detail)
	_gap(box, 6)
	var again := Button.new()
	again.name = "PlayAgain"
	again.text = "Play Again"
	again.focus_mode = Control.FOCUS_NONE
	again.custom_minimum_size = Vector2(170, 40)
	again.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	again.pressed.connect(func() -> void: get_tree().reload_current_scene())
	box.add_child(again)


# ── Content ──


func _refresh() -> void:
	# Gold my orders still on their way will spend shows as already gone, greyed.
	_gold.text = str(Game.gold - Game.pending_gold)
	_gold.add_theme_color_override("font_color", DIM if Game.pending_gold > 0 else COIN)
	_lives.text = str(Game.lives)
	_lives.add_theme_color_override("font_color", _health_tone(Game.lives, Game.max_lives()))
	_wave.text = "Wave %d/%d" % [Game.wave, Game.total_waves()]
	_wave.visible = Game.wave > 0  # before the first, the countdown says it all
	_refresh_checks()
	_refresh_card()
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	var creep := controller.selected_creep
	var has_creep := creep != null and is_instance_valid(creep) and not creep.dead
	if has_creep:
		_describe_creep(creep)
	elif has_tower:
		_describe_tower(tower)
	elif controller.mode != "":
		_describe_build(controller.mode)
	else:
		_describe_holdfast()
	if _hovered != "":
		_show_tooltip(_hovered)
	if _wave_list.visible:
		_fill_wave_list()


## The six slots as the selection makes them (design 5.7's table).
func _refresh_card() -> void:
	var over := _over()
	# (networked, orders go nowhere before START or after the link went, nor while the
	# caretaker holds my seat (away, or back until the next build window): every command
	# greys, as it does once the match is over)
	var live := Game.order_refusal() == ""
	_live = live
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	# (only a tower's builder forks or sells it)
	var mine := has_tower and tower.owner_seat == Game.seat
	for i in 3:
		var button: Button = _card[SLOTS[i]]
		var use := controller.slot_use(i)
		if use == "build" and Game.kit_tower(i) == "":
			use = "idle"  # (a kit with no tower on this slot: an empty socket)
		_reset_slot(button)
		match use:
			"build":
				var kind := Game.kit_tower(i)
				button.set_meta("what", kind)
				_set_icon(button, str(Game.TOWERS[kind]["icon"]))
				var cost := Game.tower_cost(kind)
				_command(button, not over and live, Game.can_afford(cost), str(cost))
				_set_active(button, controller.mode == kind)
			"branch":
				var form := SimContent.tower_form(tower.kind, i)
				button.set_meta("what", form)
				_set_icon(button, str(Game.TOWERS[form]["icon"]))
				_set_glyph(button, SimContent.branch_helps(Game.builder(), form))
				(button.get_node("Hammer") as Control).visible = true
				var cost := tower.upgrade_cost()
				var waiting := controller.fork_pending(tower.cell)
				_command(button, not over and live and not waiting, Game.can_afford(cost), str(cost))
			"forked":
				var form := SimContent.tower_form(tower.kind, i)
				button.set_meta("what", form)
				_set_icon(button, str(Game.TOWERS[form]["icon"]))
				_set_glyph(button, SimContent.branch_helps(Game.builder(), form))
				if tower.branch == i:
					_lit(button)
				else:
					_command(button, false, true, "")
			_:
				# (E on my own tower: nothing to do there, an empty socket)
				button.set_meta("what", "")
				(button.get_node("Icon") as Control).visible = false
				(button.get_node("KeyTab") as Control).visible = false
				_command(button, false, true, "")
	_card["signal"].set_meta("what", "signal")
	_command(_card["signal"], not over and live, true, "")
	_set_active(_card["signal"], controller.signaling)
	_card["sell"].set_meta("what", "sell")
	_command(_card["sell"], mine and live, true, "+%d" % tower.sell_value() if mine else "")
	_ready_button.set_meta("what", "ready")
	var can_call := Game.state == Game.State.PREP and Game.wave < Game.total_waves() and live
	_command(_ready_button, can_call, true, (_ready_button.get_node("Cost") as Label).text)
	_set_active(_ready_button, can_call and controller.wants_ready())


func _over() -> bool:
	return Game.state == Game.State.WON or Game.state == Game.State.LOST


## The wave the strip speaks of: the next one in a build window, the current one while
## it runs (0-based), or -1 when none is left to show.
func _strip_wave() -> int:
	if Game.sim == null or _over():
		return -1
	if Game.state == Game.State.WAVE:
		return Game.wave - 1
	return Game.wave if Game.wave < Game.total_waves() else -1


## The glyph of each check the strip's wave brings with the portrait of the creep that
## brings it, then the portraits of its bosses. Rebuilt only when the wave changes.
func _refresh_checks() -> void:
	var index := _strip_wave()
	var shown := []
	if index >= 0:
		shown = Game.wave_checks(index)
		for boss: String in Game.wave_bosses(index):
			shown.append(["boss", boss])
	_checks.visible = not shown.is_empty()
	if _checks.get_meta("shown", []) == shown and _checks.get_child_count() == shown.size():
		return
	_checks.set_meta("shown", shown)
	for child in _checks.get_children():
		child.free()
	for pair: Array in shown:
		var group := HBoxContainer.new()
		group.mouse_filter = Control.MOUSE_FILTER_IGNORE
		group.add_theme_constant_override("separation", 1)
		if pair[0] != "boss":
			var glyph := _icon_rect(Vector2(GLYPH_SIZE, GLYPH_SIZE))
			glyph.name = "Glyph_%s" % pair[0]
			glyph.texture = Game.icon(str(Game.CHECKS[pair[0]]["icon"]))
			glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			group.add_child(glyph)
		var face := _icon_rect(Vector2(FACE_SIZE, FACE_SIZE))
		face.name = "Face_%s" % pair[1]
		face.texture = Game.icon(str(Game.CREEPS[pair[1]].get("icon", "")))
		face.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		group.add_child(face)
		_checks.add_child(group)


func _show_wave_list(on: bool) -> void:
	_wave_list.visible = on and Game.sim != null and Game.total_waves() > 0 and not _over()
	if _wave_list.visible:
		_fill_wave_list()


## Every wave from the strip's on: "5", its checks' glyphs, its creeps' portraits with
## their counts; the one running now is marked.
func _fill_wave_list() -> void:
	var first := _strip_wave()
	var key := [first, Game.state]
	if _wave_rows.get_meta("shown", []) == key:
		return
	_wave_rows.set_meta("shown", key)
	for child in _wave_rows.get_children():
		child.free()
	if first < 0:
		return
	for index in range(first, Game.total_waves()):
		var row := HBoxContainer.new()
		row.name = "WaveRow%d" % (index + 1)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_theme_constant_override("separation", 4)
		var now := Game.state == Game.State.WAVE and index == Game.wave - 1
		var number := _label(str(index + 1), BOLD_FONT, 14, GOLD if now else TEXT)
		number.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		number.custom_minimum_size.x = 20
		row.add_child(number)
		var glyphs := HBoxContainer.new()
		glyphs.mouse_filter = Control.MOUSE_FILTER_IGNORE
		glyphs.add_theme_constant_override("separation", 1)
		# (a column the width of the four glyphs, so the portraits line up)
		glyphs.custom_minimum_size.x = ROW_GLYPH * 4 + 3
		for pair: Array in Game.wave_checks(index):
			var glyph := _icon_rect(Vector2(ROW_GLYPH, ROW_GLYPH))
			glyph.texture = Game.icon(str(Game.CHECKS[pair[0]]["icon"]))
			glyph.tooltip_text = str(Game.CHECKS[pair[0]]["name"])
			glyphs.add_child(glyph)
		row.add_child(glyphs)
		for group: Dictionary in Game.wave_groups(index):
			var face := _icon_rect(Vector2(ROW_FACE, ROW_FACE))
			face.texture = Game.icon(str(Game.CREEPS[group["creep"]].get("icon", "")))
			face.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			row.add_child(face)
			var count := int(group["count"])
			var boss := bool(SimContent.CREEPS[group["creep"]].get("boss", false))
			var words := "boss" if boss else "×%d" % count
			var label := _label(words, BOLD_FONT if boss else BODY_FONT, 12, NOTICE if boss else DIM)
			label.add_theme_constant_override("outline_size", 0)
			row.add_child(label)
		if now:
			var mark := _label("now", BOLD_FONT, 12, GOLD)
			mark.add_theme_constant_override("outline_size", 0)
			row.add_child(mark)
		_wave_rows.add_child(row)


## Nothing selected: the Holdfast the player keeps, how it stands and what comes next.
func _describe_holdfast() -> void:
	_portrait.show_model("res://models/props/hearth.glb", "", 0.0, 1.0, true)
	var line := ""  # at the end the plate tells how it went
	if Game.state == Game.State.WAVE:
		line = "Wave %d of %d" % [Game.wave, Game.total_waves()]
	elif Game.state == Game.State.PREP and Game.wave < Game.total_waves():
		line = "Next: " + _wave_brings(Game.wave)
	_head("The Holdfast", line)
	_set_glyph_title("")
	_set_stats(
		[
			[
				"Lives",
				"%d/%d" % [Game.lives, Game.max_lives()],
				_health_tone(Game.lives, Game.max_lives())
			],
			["Kills", str(Game.kills)],
			["Towers", str(Game.tower_count())],
		]
	)


## What wave `index` (0-based) sends: "8 Gourdlings", "5 Thornbacks and The Hollowtide Crest".
func _wave_brings(index: int) -> String:
	var parts := PackedStringArray()
	for group: Dictionary in Game.wave_groups(index):
		var count := int(group["count"])
		var creep_name := str(Game.CREEPS[group["creep"]]["name"])
		if count == 1:
			parts.append(creep_name)
		else:
			parts.append("%d %ss" % [count, creep_name])
	return " and ".join(parts)


func _describe_build(kind: String) -> void:
	var data := Game.form_stats(kind, -1, Game.my_range_bonus())
	var cost := int(data["cost"])
	_show_tower_portrait(kind)
	var line := "%d gold" % cost
	if data["air"]:
		line += " · reaches the sky"
	_head(str(data["name"]), line, DIM if Game.can_afford(cost) else SHORT)
	_set_glyph_title("")
	_set_stats(_tower_stats(data))


## A tower: its form's name (the check a patch branch lifts beside it), whose it is when
## it is a teammate's ("Seat 2's"), whether it reaches the sky, its kills; its numbers.
func _describe_tower(tower: Tower) -> void:
	var data: Dictionary = Game.TOWERS[tower.form]
	_show_tower_portrait(tower.form)
	var parts := PackedStringArray()
	if tower.owner_seat != Game.seat:
		parts.append("%s's" % Game.seat_name(tower.owner_seat))
	if tower.stats.get("air", false):
		parts.append("reaches the sky")
	parts.append("%d %s" % [tower.kills, "kill" if tower.kills == 1 else "kills"])
	_head(str(data["name"]), " · ".join(parts))
	var owner: SimRecords.SimSeat = Game.sim.seat(tower.owner_seat) if Game.sim else null
	_set_glyph_title(SimContent.branch_helps(owner.builder, tower.form) if owner else "")
	_set_stats(_tower_stats(tower.stats))


## A creep: its name with the glyph of the check it brings, what holds it (winged,
## slowed, stunned, marked) and its numbers.
func _describe_creep(creep: Creep) -> void:
	_creep_shown = _creep_key(creep)
	var data: Dictionary = Game.CREEPS[creep.kind]
	_portrait.show_model(str(data["model"]))
	var parts := PackedStringArray(["Wave %d" % Game.wave])
	if creep.winged:
		parts.append("winged")
	if creep.stunned:
		parts.append("stunned")
	elif creep.slow_factor < 1.0:
		parts.append("slowed")
	if creep.mark > 0.0:
		parts.append("marked +%d%%" % roundi(creep.mark * 100.0))
	_head(str(data["name"]), " · ".join(parts))
	_set_glyph_title(str(data.get("check", "")))
	var fraction := creep.hp / creep.max_hp
	var cells := [
		["Health", "%d/%d" % [ceili(creep.hp), ceili(creep.max_hp)], _health_tone(fraction, 1.0)],
		["Speed", "%.1f" % creep.pace],
	]
	if creep.armor > 0.0:
		cells.append(["Armour", _num(creep.armor)])
	cells.append(["Bounty", str(creep.bounty)])
	# What it takes from the Holdfast if it gets there.
	cells.append(["Toll", "–%d" % creep.lives_cost, Color("#ff9a7a")])
	_set_stats(cells)


func _creep_key(creep: Creep) -> Array:
	return [ceili(creep.hp), creep.slow_factor < 1.0, creep.stunned, creep.mark]


func _head(title: String, line: String, tone := DIM) -> void:
	_title.text = title
	_subtitle.text = line
	# Without a line the numbers move up under the title instead of leaving a gap.
	_subtitle.visible = line != ""
	_subtitle.add_theme_color_override("font_color", tone)


## The check glyph beside the title, or none.
func _set_glyph_title(check: String) -> void:
	_title_glyph.visible = Game.CHECKS.has(check)
	if _title_glyph.visible:
		_title_glyph.texture = Game.icon(str(Game.CHECKS[check]["icon"]))
		_title_glyph.set_meta("check", check)


func _show_tower_portrait(form: String) -> void:
	var data: Dictionary = Game.TOWERS[form]
	_portrait.show_model(
		str(data["model"]), str(data.get("head", "")), float(data.get("head_height", 0.0))
	)


## The numbers a tower shows: damage (or, for a tower that marks, the mark), range,
## cooldown (or how many it marks), then what it adds: splash, slow, pierce, bounces.
func _tower_stats(s: Dictionary) -> Array:
	var stats := []
	var marks := s.has("mark") and float(s["damage"]) <= 0.0
	if marks:
		stats.append(["Mark", "+%d%%" % roundi(float(s["mark"]) * 100.0)])
	else:
		stats.append(["Damage", str(s["damage"])])
	stats.append(["Range", str(s["range"])])
	if marks:
		stats.append(["Marks", str(s.get("marks", 1))])
	else:
		stats.append(["Cooldown", "%ss" % s["cooldown"]])
	if s.has("splash"):
		stats.append(["Splash", str(s["splash"])])
	if s.has("slow"):
		stats.append(["Slow", "%d%%" % roundi(float(s["slow"]) * 100.0)])
	if s.has("pierce"):
		stats.append(["Pierce", _num(float(s["pierce"]))])
	if s.has("bounces"):
		stats.append(["Bounces", str(s["bounces"])])
	return stats


## One row of numbers, each a bold value over its name in small capitals. Rebuilt only
## when the values change; five cells sit closer than four.
func _set_stats(cells: Array) -> void:
	if _stats.get_meta("cells", []) == cells:
		return
	_stats.set_meta("cells", cells)
	_stats.add_theme_constant_override("separation", 28 if cells.size() <= 4 else 16)
	for child in _stats.get_children():
		child.free()
	for cell: Array in cells:
		var box := VBoxContainer.new()
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.add_theme_constant_override("separation", -3)
		var value_color: Color = cell[2] if cell.size() > 2 else TEXT
		var value := _label(str(cell[1]), BOLD_FONT, 16, value_color)
		value.add_theme_constant_override("outline_size", 2)
		box.add_child(value)
		# On the dark plate the captions need no outline; one would clog their counters.
		var caption := _label(str(cell[0]).to_upper(), _caps, 11, DIM)
		caption.add_theme_constant_override("outline_size", 0)
		box.add_child(caption)
		_stats.add_child(box)


## Green while most is left, yellow below 60 %, red below 30 %.
func _health_tone(value: float, full: float) -> Color:
	var share := value / full
	if share > 0.6:
		return Color("#9be06a")
	return Color("#ffd166") if share > 0.3 else Color("#ff7a5a")


func _hover(what: String) -> void:
	_hovered = what
	if what == "":
		_tooltip.visible = false
		_refresh()
		return
	_show_tooltip(what)
	var slot := SLOTS.find(what)
	var use := controller.slot_use(slot) if slot >= 0 and slot < 3 else ""
	if use == "build" and controller.selected == null and Game.kit_tower(slot) != "":
		_describe_build(Game.kit_tower(slot))


func _show_tooltip(what: String) -> void:
	if _over():
		return
	_tooltip.visible = true
	_tooltip_helps.visible = false
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	var slot := SLOTS.find(what)
	_tooltip_key.text = "(%s)" % Game.CARD_KEYS[slot]
	var cost := 0
	_tooltip_cost.text = ""
	var use := controller.slot_use(slot) if slot < 3 else what
	if use == "build" and Game.kit_tower(slot) == "":
		use = "idle"
	match use:
		"build":
			var kind := Game.kit_tower(slot)
			var data: Dictionary = Game.TOWERS[kind]
			_tooltip_title.text = str(data["name"])
			cost = Game.tower_cost(kind)
			# (the Builders screen shows this very body: Game.kit_tip)
			_tooltip_body.text = Game.kit_tip(Game.builder(), slot, Game.my_range_bonus())
		"branch", "forked":
			var form := SimContent.tower_form(tower.kind, slot)
			_tooltip_title.text = str(Game.TOWERS[form]["name"])
			if use == "branch":
				cost = tower.upgrade_cost()
				_tooltip_body.text = _fork_gains(tower, slot)
			elif tower.branch == slot:
				_tooltip_body.text = "This tower stands as the %s." % Game.TOWERS[form]["name"]
			else:
				_tooltip_body.text = (
					"A fork is final: this tower stands as the %s." % Game.TOWERS[tower.form]["name"]
				)
			var helps := SimContent.branch_helps(Game.builder(), form)
			if helps != "":
				_tooltip_helps.visible = true
				_tooltip_glyph.texture = Game.icon(str(Game.CHECKS[helps]["icon"]))
				_tooltip_helps_text.text = "Lifts %s to passable" % Game.CHECKS[helps]["name"]
		"idle":
			_tooltip.visible = false
			return
		"signal":
			_tooltip_title.text = "Signal"
			_tooltip_body.text = (
				"Then click the ground, a creep or a tower: a ring there shows everyone where to look. Alt+click signals at once."
			)
		"sell":
			_tooltip_title.text = "Sell"
			_tooltip_cost.text = "+%d" % tower.sell_value() if has_tower else ""
			_tooltip_body.text = (
				"Returns most of what the tower cost." if has_tower else "Select a tower to sell it."
			)
			if has_tower and tower.owner_seat != Game.seat:
				_tooltip_cost.text = ""
				_tooltip_body.text = (
					"That tower is %s's: only its builder sells it." % Game.seat_name(tower.owner_seat)
				)
		_:
			_tooltip_title.text = "Ready"
			var bonus := Game.early_gold()
			_tooltip_cost.text = "+%d" % bonus if bonus > 0 and not _ready_button.disabled else ""
			var everyone := "you are" if Game.seat_count() == 1 else "everyone is"
			_tooltip_body.text = (
				(
					"Sounds the horn when %s Ready: the next wave comes at once, and each second left on the countdown pays one gold. N and Space too."
					% everyone
				)
				if not _ready_button.disabled
				else (
					"The horn waits until this wave is cleared."
					if Game.order_refusal() == ""
					else Game.order_refusal() + "."
				)
			)
	if cost > 0:
		_tooltip_cost.text = str(cost)
	_tooltip_cost.add_theme_color_override(
		"font_color", SHORT if cost > 0 and not Game.can_afford(cost) else COIN
	)
	_tooltip_cost.visible = _tooltip_cost.text != ""
	_tooltip_coin.visible = _tooltip_cost.visible


## What a fork to `branch` changes, in numbers: "Damage 8.0 to 16.0 · range 3.2 to 3.6",
## and "reaches the sky" when it starts to.
func _fork_gains(tower: Tower, branch: int) -> String:
	var after := Game.form_stats(tower.kind, branch, Game.sim.range_bonus(tower.owner_seat))
	var was: Dictionary = tower.stats
	var parts := PackedStringArray()
	for key: String in ["damage", "range", "cooldown", "splash", "slow", "pierce", "bounces", "mark", "marks"]:
		if not after.has(key) and not was.has(key):
			continue
		var before := float(was.get(key, 0.0))
		var now := float(after.get(key, 0.0))
		if is_equal_approx(before, now):
			continue
		match key:
			"slow", "mark":
				parts.append("%s %d%% to %d%%" % [key, roundi(before * 100), roundi(now * 100)])
			"cooldown":
				parts.append("cooldown %ss to %ss" % [was[key], after[key]])
			"pierce", "bounces", "marks":
				parts.append("%s %s to %s" % [key, _num(before), _num(now)])
			_:
				parts.append("%s %s to %s" % [key, was.get(key, 0.0), after.get(key, 0.0)])
	if bool(after["air"]) and not bool(was.get("air", false)):
		parts.append("reaches the sky")
	if parts.is_empty():
		return ""
	var text := " · ".join(parts)
	return text[0].to_upper() + text.substr(1)


## A whole number without its ".0", any other with one decimal.
func _num(value: float) -> String:
	return str(roundi(value)) if is_equal_approx(value, roundf(value)) else "%.1f" % value


func _on_state(state: int) -> void:
	_refresh()
	if state == Game.State.WON or state == Game.State.LOST:
		controller.set_mode("")
		_hovered = ""
		_tooltip.visible = false
		_wave_list.visible = false
		_end_panel.visible = true
		_banner.hide_title()
		_notice.visible = false
		var won := state == Game.State.WON
		_end_label.text = "Victory!" if won else "The Holdfast has gone under"
		_end_detail.text = "Fell in wave %d of %d" % [Game.wave, Game.total_waves()]
		if won:
			_end_detail.text = "All %d waves held back" % Game.total_waves()
		elif Game.wave == 0:
			_end_detail.text = "Fell before the first wave"


# ── Widgets ──


func _theme() -> Theme:
	var theme := Theme.new()
	theme.default_font = BODY_FONT
	theme.default_font_size = 15
	theme.set_color("font_color", "Label", TEXT)
	theme.set_constant("outline_size", "Label", 4)
	theme.set_color("font_outline_color", "Label", INK)
	for state: String in ["normal", "hover", "pressed", "disabled"]:
		theme.set_stylebox(
			state, "Button", HdStyleBox.new(load(ART + "button_%s.tres" % state), _k)
		)
	theme.set_stylebox(
		"hover_pressed", "Button", HdStyleBox.new(load(ART + "button_pressed.tres"), _k)
	)
	theme.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	theme.set_font("font", "Button", BOLD_FONT)
	theme.set_font_size("font_size", "Button", 15)
	theme.set_color("font_color", "Button", GOLD)
	theme.set_color("font_hover_color", "Button", Color("#fff1c8"))
	theme.set_color("font_pressed_color", "Button", GOLD)
	theme.set_color("font_disabled_color", "Button", Color("#76695a"))
	theme.set_constant("outline_size", "Button", 4)
	theme.set_color("font_outline_color", "Button", Color(0.04, 0.03, 0.02))
	return theme


## A piece of the console anchored to the bottom edge at anchor_x (0 left, 0.5 centre, 1 right).
func _piece(parent: Control, name: String, anchor_x: float, left: float, size: Vector2) -> Control:
	var piece := Control.new()
	piece.name = name
	piece.mouse_filter = Control.MOUSE_FILTER_IGNORE
	piece.anchor_left = anchor_x
	piece.anchor_right = anchor_x
	piece.anchor_top = 1.0
	piece.anchor_bottom = 1.0
	piece.offset_left = left
	piece.offset_right = left + size.x
	piece.offset_top = -size.y
	piece.offset_bottom = 0
	parent.add_child(piece)
	return piece


func _rect(key: String) -> Rect2:
	var r: Array = _layout[key]
	return Rect2(r[0], r[1], r[2], r[3])


func _vec(key: String) -> Vector2:
	var v: Array = _layout[key]
	return Vector2(v[0], v[1])


func _place(control: Control, rect: Rect2) -> void:
	control.position = rect.position
	control.size = rect.size


func _gap(parent: Control, width: float) -> void:
	var gap := Control.new()
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gap.custom_minimum_size = Vector2(width, width)
	parent.add_child(gap)


func _art(file: String, hit := false) -> ConsoleArt:
	return ConsoleArt.new(load(ART + file), _k, hit)


## An icon cropped to what is drawn in it, so a small icon shows its subject large;
## `top` keeps only that share of it from the top (the lives icon without its plinth).
func _tight(path: String, top := 1.0) -> Texture2D:
	var texture: Texture2D = load(path)
	var image := texture.get_image()
	if image == null:
		return texture
	if image.is_compressed():
		image.decompress()
	var used := image.get_used_rect()
	used.size.y = roundi(used.size.y * top)
	var atlas := AtlasTexture.new()
	atlas.atlas = texture
	atlas.region = used
	return atlas


func _label(text: String, font: Font, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


## A small icon that keeps its aspect inside `size`.
func _icon_rect(size: Vector2) -> TextureRect:
	var rect := TextureRect.new()
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	rect.custom_minimum_size = size
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect


## An icon and its number; `glow` lays a warm light behind the icon.
func _resource(
	parent: Node, name: String, icon: Texture2D, color: Color, tall: float, glow := false
) -> Label:
	var holder := Control.new()
	holder.name = name + "Icon"
	holder.custom_minimum_size = Vector2(tall, tall)
	holder.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(holder)
	if glow:
		var light := TextureRect.new()
		light.texture = ResourceStrip.glow(Color("#ffb347"))
		light.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		light.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_place(light, Rect2(Vector2(-tall * 0.35, -tall * 0.4), Vector2(tall, tall) * 1.7))
		holder.add_child(light)
	var picture := TextureRect.new()
	picture.texture = icon
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.set_anchors_preset(Control.PRESET_FULL_RECT)
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(picture)
	var value := _label("", BOLD_FONT, 17, color)
	value.name = name
	value.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	parent.add_child(value)
	return value


## A command: the bevelled icon is the button. It brightens and leaks warm light on
## hover, sinks when pressed, glows while active, greys with a red cost when the gold is
## short, and greys darker when it does not apply. The hotkey sits on a dark tab in the
## top left corner and the cost on the icon's shaded foot, so neither is painted over the
## subject; a fork carries the hammer in its lower left corner and, when it lifts a check,
## that check's glyph in its upper right.
func _card_button(name: String, hotkey: String) -> Button:
	var button := Button.new()
	button.name = name
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = _vec("socket")
	button.size = _vec("socket")
	var glow := HdStyleBox.new(load(ART + "card_glow.tres"), _k)
	var empty := StyleBoxEmpty.new()
	for state: String in ["normal", "disabled", "focus"]:
		button.add_theme_stylebox_override(state, empty)
	for state: String in ["hover", "pressed", "hover_pressed"]:
		button.add_theme_stylebox_override(state, glow)
	var ring := Panel.new()
	ring.name = "Ring"
	ring.add_theme_stylebox_override("panel", glow)
	ring.set_anchors_preset(Control.PRESET_FULL_RECT)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ring.visible = false
	button.add_child(ring)
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_SCALE
	icon.size = button.size
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material := ShaderMaterial.new()
	material.shader = GREY
	icon.material = material
	button.add_child(icon)
	button.draw.connect(_style_command.bind(button, icon, material))
	var hammer := TextureRect.new()
	hammer.name = "Hammer"
	hammer.texture = _hammer
	hammer.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	hammer.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	hammer.position = Vector2(2, button.size.y - 19)
	hammer.size = Vector2(17, 17)
	hammer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hammer.visible = false
	button.add_child(hammer)
	var glyph := TextureRect.new()
	glyph.name = "Glyph"
	glyph.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glyph.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	glyph.position = Vector2(button.size.x - 20, 2)
	glyph.size = Vector2(18, 18)
	glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
	glyph.visible = false
	button.add_child(glyph)
	var tab := Panel.new()
	tab.name = "KeyTab"
	var tab_box := StyleBoxFlat.new()
	tab_box.bg_color = Color(0, 0, 0, 0.7)
	tab_box.set_corner_radius_all(3)
	tab.add_theme_stylebox_override("panel", tab_box)
	tab.position = Vector2(2, 2)
	tab.size = Vector2(14, 14)
	tab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(tab)
	var key := _label(hotkey, BOLD_FONT, 10, KEY)
	key.name = "Hotkey"
	key.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	key.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	key.add_theme_constant_override("outline_size", 0)
	key.set_anchors_preset(Control.PRESET_FULL_RECT)
	tab.add_child(key)
	var cost := _label("", BOLD_FONT, 12, COIN)
	cost.name = "Cost"
	cost.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	cost.position = Vector2(3, button.size.y - 18)
	cost.size = Vector2(button.size.x - 7, 16)
	cost.add_theme_constant_override("outline_size", 3)
	button.add_child(cost)
	return button


## Back to a plain slot before the selection dresses it: its icon and key shown, no
## hammer, no glyph, no ring.
func _reset_slot(button: Button) -> void:
	(button.get_node("Icon") as Control).visible = true
	(button.get_node("KeyTab") as Control).visible = true
	(button.get_node("Hammer") as Control).visible = false
	(button.get_node("Glyph") as Control).visible = false
	_set_active(button, false)


func _set_icon(button: Button, path: String) -> void:
	var icon: TextureRect = button.get_node("Icon")
	var texture := Game.icon(path)
	if icon.texture != texture:
		icon.texture = texture


## The glyph of the check a branch lifts, in the slot's corner; "" hides it.
func _set_glyph(button: Button, check: String) -> void:
	var glyph: TextureRect = button.get_node("Glyph")
	glyph.visible = Game.CHECKS.has(check)
	if glyph.visible:
		glyph.texture = Game.icon(str(Game.CHECKS[check]["icon"]))
		glyph.set_meta("check", check)


## Sets a command's state: usable, short of gold (grey, red cost) or not applicable
## (darker grey, the cost line shows only a note such as "Max").
func _command(button: Button, applies: bool, affordable: bool, cost_text: String) -> void:
	button.disabled = not applies or not affordable
	var state := "ok" if button.disabled == false else ("poor" if applies else "idle")
	button.set_meta("state", state)
	var cost: Label = button.get_node("Cost")
	cost.text = cost_text
	var color := COIN
	if state == "poor":
		color = SHORT
	elif state == "idle":
		color = DIM
	cost.add_theme_color_override("font_color", color)
	button.queue_redraw()


## The branch a forked tower took: in full colour with its ring, but nothing to press.
func _lit(button: Button) -> void:
	button.disabled = true
	button.set_meta("state", "lit")
	(button.get_node("Cost") as Label).text = ""
	_set_active(button, true)
	button.queue_redraw()


func _style_command(button: Button, icon: TextureRect, material: ShaderMaterial) -> void:
	var mode := button.get_draw_mode()
	var pressed := mode == BaseButton.DRAW_PRESSED or mode == BaseButton.DRAW_HOVER_PRESSED
	icon.position = Vector2(0, 1) if pressed else Vector2.ZERO
	var state: String = button.get_meta("state", "ok")
	var bright := state == "ok" or state == "lit"
	material.set_shader_parameter("grey", 0.0 if bright else (1.0 if state == "poor" else IDLE_GREY))
	material.set_shader_parameter("value", POOR_VALUE if state == "poor" else IDLE_VALUE)
	if not bright or state == "lit":
		icon.modulate = Color.WHITE
	elif pressed:
		icon.modulate = Color(0.8, 0.76, 0.7)
	elif mode == BaseButton.DRAW_HOVER:
		icon.modulate = Color(1.2, 1.15, 1.05)
	else:
		icon.modulate = Color.WHITE


func _set_cost(button: Button, text: String) -> void:
	(button.get_node("Cost") as Label).text = text


func _set_active(button: Button, active: bool) -> void:
	(button.get_node("Ring") as Control).visible = active
