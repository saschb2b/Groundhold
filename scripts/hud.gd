## The console, laid out like a classic strategy game's but pared down: one piece of
## dark bronze and stone along the bottom edge whose top rises into an arched crest
## around the live portrait and dips low between its parts so the hollow shows
## through. A minimap on the left wing, the portrait and the selection's numbers in the
## middle, the command card on the right wing. Resources hang from a slim strip at the
## top right. The pieces are painted by art_src/ui/console.py from
## art_src/ui/console.json at twice the layout's resolution and drawn at half size, so
## they stay crisp on large screens; layout.json gives the wells and windows.
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
## How light a greyed command stays: readable when only unaffordable, darker when it
## does not apply (nothing selected, fully upgraded, a wave running). An idle command
## keeps a fifth of its colour, so it still reads as a command and not a hole.
const POOR_VALUE := 0.72
const IDLE_VALUE := 0.6
const IDLE_GREY := 0.8
## How long a title stays up, and a notice such as "Not enough gold".
const BANNER_HOLD := 1.8
const NOTICE_HOLD := 0.9
## Titles: how far below the top edge they stand, above the first row of towers.
const BANNER_TOP := 24

var controller: BuildController

var _layout: Dictionary
## Texels of console art per layout pixel.
var _k := 1.0
var _gold: Label
var _lives: Label
var _wave: Label
var _countdown: Label
var _ready_button: Button
var _banner: TitleBanner
var _notice: Label
var _notice_tween: Tween
var _portrait: Portrait
var _creep_shown := []
var _title: Label
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
var _hovered := ""
var _end_panel: Control
var _end_label: Label
var _end_detail: Label
## Whether orders go out (Game.accepts_commands) as the HUD last showed it.
var _live := true


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
	Game.ready_changed.connect(_refresh)
	Game.towers_changed.connect(_refresh)
	controller.selection_changed.connect(func(_t: Tower) -> void: _refresh())
	controller.creep_selected.connect(func(_c: Creep) -> void: _refresh())
	controller.mode_changed.connect(func(_k2: String) -> void: _refresh())
	_refresh()


func _process(_delta: float) -> void:
	var live := Game.accepts_commands()
	if live != _live:
		_live = live
		_refresh()  # (the match started, or its link went)
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
		if Game.early_gold() > 0 and Game.wave < Game.total_waves():
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
		if _creep_shown != [ceili(creep.hp), creep.slow_factor < 1.0]:
			_describe_creep(creep)
	elif creep:
		controller.select_creep(null)


## A title for a moment of the game: a wave arriving, a wave cleared, the end.
func show_banner(text: String) -> void:
	if _end_panel.visible:
		return  # the end plate says it already
	_banner.show_title(text, BANNER_HOLD)


## A short line above the selection's name for a refused order, gone in about a second and a half.
func show_notice(text: String) -> void:
	if _end_panel.visible:
		return
	_notice.text = text
	_notice.visible = true
	_notice.modulate.a = 1.0
	if _notice_tween:
		_notice_tween.kill()
	_notice_tween = create_tween()
	_notice_tween.tween_interval(NOTICE_HOLD)
	_notice_tween.tween_property(_notice, "modulate:a", 0.0, 0.6)
	_notice_tween.tween_callback(func() -> void: _notice.visible = false)


# ── Layout ──


func _build(main: Node) -> void:
	_caps = FontVariation.new()
	_caps.base_font = BOLD_FONT
	_caps.spacing_glyph = 1
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

	# Right wing: the command card, every slot a command, each in a fixed place.
	var right := _piece(console, "WingRight", 1.0, -wing.x, wing)
	right.add_child(_art("wing_right.png", true))
	var card := Control.new()
	card.name = "CommandCard"
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_place(card, _rect("card_well"))
	right.add_child(card)
	var commands := []
	for kind: String in ["arrow", "cannon", "frost"]:
		var data: Dictionary = Game.TOWERS[kind]
		var button := _card_button(
			"Build%s" % kind.capitalize(), str(data["hotkey"]), str(data["icon"])
		)
		button.pressed.connect(controller.set_mode.bind(kind))
		commands.append([button, kind])
	var upgrade := _card_button("Upgrade", "U", ICONS + "upgrade.png")
	upgrade.pressed.connect(controller.upgrade_selected)
	commands.append([upgrade, "upgrade"])
	var sell := _card_button("Sell", "S", ICONS + "sell.png")
	sell.pressed.connect(controller.sell_selected)
	commands.append([sell, "sell"])
	# The war horn: Ready. When every seat is Ready the next wave comes at once.
	_ready_button = _card_button("Ready", "N", ICONS + "next_wave.png")
	_ready_button.pressed.connect(func() -> void: controller.toggle_ready())
	commands.append([_ready_button, "ready"])
	var socket := _vec("socket")
	var gap := _vec("gap")
	for i in commands.size():
		var button: Button = commands[i][0]
		var what: String = commands[i][1]
		button.position = Vector2(i % 3, i / 3) * (socket + gap)
		button.mouse_entered.connect(_hover.bind(what))
		button.mouse_exited.connect(_hover.bind(""))
		card.add_child(button)
		_card[what] = button


## One title, one line under it and one row of numbers, clipped to the shoulder's text area.
func _build_info() -> Control:
	var info := VBoxContainer.new()
	info.name = "Info"
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.clip_contents = true
	info.add_theme_constant_override("separation", 0)
	_place(info, _rect("text"))
	_title = _label("", TITLE_FONT, 21, GOLD)
	_title.name = "Title"
	_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_title.add_theme_constant_override("outline_size", 3)
	info.add_child(_title)
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


## Gold, lives and the wave on a strip hanging from the top right. It is a nine-slice
## that grows leftwards, so big numbers widen it instead of spilling past its art.
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
	_wave = _label("", BOLD_FONT, 15, TEXT)
	_wave.name = "Wave"
	_wave.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(_wave)
	_countdown = _label("", BODY_FONT, 15, TEXT)
	_countdown.name = "Countdown"
	_countdown.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_countdown.custom_minimum_size.x = 98
	row.add_child(_countdown)


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
## the cost on the same line, then what it does.
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
	_tooltip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tooltip_body.custom_minimum_size.x = 262
	_tooltip_body.add_theme_constant_override("outline_size", 0)
	tip_box.add_child(_tooltip_body)


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
	var over := _over()
	# (networked, orders go nowhere before START or after the link went: every command
	# greys, as it does once the match is over)
	var live := Game.accepts_commands()
	_live = live
	for kind: String in ["arrow", "cannon", "frost"]:
		var cost := Game.tower_cost(kind)
		_command(_card[kind], not over and live, Game.can_afford(cost), str(cost))
		_set_active(_card[kind], controller.mode == kind)
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	# (only a tower's builder upgrades or sells it)
	var mine := has_tower and tower.owner_seat == Game.seat
	var upgrade_cost := tower.upgrade_cost() if has_tower else -1
	if has_tower and upgrade_cost < 0:
		_command(_card["upgrade"], false, true, "Max")
	else:
		_command(
			_card["upgrade"],
			upgrade_cost > 0 and mine and live,
			Game.can_afford(upgrade_cost),
			str(upgrade_cost) if upgrade_cost > 0 else ""
		)
	_command(
		_card["sell"], mine and live, true, "+%d" % tower.sell_value() if has_tower else ""
	)
	var can_call := Game.state == Game.State.PREP and Game.wave < Game.total_waves() and live
	_command(_ready_button, can_call, true, (_ready_button.get_node("Cost") as Label).text)
	_set_active(_ready_button, can_call and controller.wants_ready())
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


func _over() -> bool:
	return Game.state == Game.State.WON or Game.state == Game.State.LOST


## Nothing selected: the Holdfast the player keeps, how it stands and what comes next.
func _describe_holdfast() -> void:
	_portrait.show_model("res://models/props/hearth.glb", "", 0.0, 1.0, true)
	var line := ""  # at the end the plate tells how it went
	if Game.state == Game.State.WAVE:
		line = "Wave %d of %d" % [Game.wave, Game.total_waves()]
	elif Game.state == Game.State.PREP and Game.wave < Game.total_waves():
		line = "Next: " + _wave_brings(Game.wave)
	_head("The Holdfast", line)
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
	var data: Dictionary = Game.tower_stats(kind, 1)
	var cost := int(data["cost"])
	_show_tower_portrait(kind, 1)
	_head(str(data["name"]), "%d gold" % cost, DIM if Game.can_afford(cost) else SHORT)
	_set_stats(_tower_stats(data))


func _describe_tower(tower: Tower) -> void:
	var data: Dictionary = Game.TOWERS[tower.kind]
	_show_tower_portrait(tower.kind, tower.level)
	var kills := "%d %s" % [tower.kills, "kill" if tower.kills == 1 else "kills"]
	_head(str(data["name"]), "Level %d · %s" % [tower.level, kills])
	_set_stats(_tower_stats(tower.stats))


func _describe_creep(creep: Creep) -> void:
	_creep_shown = [ceili(creep.hp), creep.slow_factor < 1.0]
	var data: Dictionary = Game.CREEPS[creep.kind]
	_portrait.show_model(str(data["model"]))
	_head(
		str(data["name"]), "Wave %d%s" % [Game.wave, " · slowed" if creep.slow_factor < 1.0 else ""]
	)
	var fraction := creep.hp / creep.max_hp
	_set_stats(
		[
			[
				"Health",
				"%d/%d" % [ceili(creep.hp), ceili(creep.max_hp)],
				_health_tone(fraction, 1.0)
			],
			["Speed", "%.1f" % (creep.speed * creep.slow_factor)],
			["Bounty", str(creep.bounty)],
			# What it takes from the Holdfast if it gets there.
			["Toll", "–%d" % creep.lives_cost, Color("#ff9a7a")],
		]
	)


func _head(title: String, line: String, tone := DIM) -> void:
	_title.text = title
	_subtitle.text = line
	# Without a line the numbers move up under the title instead of leaving a gap.
	_subtitle.visible = line != ""
	_subtitle.add_theme_color_override("font_color", tone)


func _show_tower_portrait(kind: String, level: int) -> void:
	var data: Dictionary = Game.TOWERS[kind]
	var model: String = data.get("model_2", data["model"]) if level >= 2 else data["model"]
	_portrait.show_model(model, str(data.get("head", "")), float(data.get("head_height", 0.0)))


func _tower_stats(s: Dictionary) -> Array:
	var stats := [
		["Damage", str(s["damage"])],
		["Range", str(s["range"])],
		["Cooldown", "%ss" % s["cooldown"]]
	]
	if s.has("splash"):
		stats.append(["Splash", str(s["splash"])])
	elif s.has("slow"):
		stats.append(["Slow", "%d%%" % int(float(s["slow"]) * 100)])
	return stats


## One row of numbers, each a bold value over its name in small capitals. Rebuilt only
## when the values change.
func _set_stats(cells: Array) -> void:
	if _stats.get_meta("cells", []) == cells:
		return
	_stats.set_meta("cells", cells)
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
	if what in Game.TOWERS and controller.selected == null:
		_describe_build(what)


func _show_tooltip(what: String) -> void:
	if _over():
		return
	_tooltip.visible = true
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	var cost := 0
	_tooltip_cost.text = ""
	if what in Game.TOWERS:
		var data: Dictionary = Game.TOWERS[what]
		_tooltip_title.text = str(data["name"])
		_tooltip_key.text = "(%s)" % data["hotkey"]
		cost = Game.tower_cost(what)
		_tooltip_body.text = str(data["description"])
	elif what == "upgrade":
		_tooltip_title.text = "Upgrade"
		_tooltip_key.text = "(U)"
		var can := has_tower and tower.upgrade_cost() > 0
		cost = tower.upgrade_cost() if can else 0
		_tooltip_body.text = (
			_upgrade_gains(tower)
			if can
			else ("Fully upgraded." if has_tower else "Select a tower to upgrade it.")
		)
		if can and tower.owner_seat != Game.seat:
			_tooltip_body.text = "Only the one who built it can upgrade it."
	elif what == "sell":
		_tooltip_title.text = "Sell"
		_tooltip_key.text = "(S)"
		_tooltip_cost.text = "+%d" % tower.sell_value() if has_tower else ""
		_tooltip_body.text = (
			"Returns most of what the tower cost." if has_tower else "Select a tower to sell it."
		)
		if has_tower and tower.owner_seat != Game.seat:
			_tooltip_body.text = "Only the one who built it can sell it."
	else:
		_tooltip_title.text = "Ready"
		_tooltip_key.text = "(N)"
		var bonus := Game.early_gold()
		_tooltip_cost.text = "+%d" % bonus if bonus > 0 and not _ready_button.disabled else ""
		var everyone := "you are" if Game.seat_count() == 1 else "everyone is"
		_tooltip_body.text = (
			(
				"Sounds the horn when %s Ready: the next wave comes at once, and each second left on the countdown pays one gold."
				% everyone
			)
			if not _ready_button.disabled
			else (
				"The horn waits until this wave is cleared."
				if Game.accepts_commands()
				else Game.command_refusal() + "."
			)
		)
	if cost > 0:
		_tooltip_cost.text = str(cost)
	_tooltip_cost.add_theme_color_override(
		"font_color", SHORT if cost > 0 and not Game.can_afford(cost) else COIN
	)
	_tooltip_cost.visible = _tooltip_cost.text != ""
	_tooltip_coin.visible = _tooltip_cost.visible


## What the next level changes, in numbers: "Damage 8.0 to 16.0 · range 3.2 to 3.6".
func _upgrade_gains(tower: Tower) -> String:
	var after := Game.tower_stats(tower.kind, tower.level + 1)
	var parts := PackedStringArray()
	for key: String in ["damage", "range", "cooldown", "splash", "slow"]:
		if not tower.stats.has(key) or is_equal_approx(tower.stats[key], after[key]):
			continue
		var was: float = tower.stats[key]
		var now: float = after[key]
		if key == "slow":
			parts.append("slow %d%% to %d%%" % [roundi(was * 100), roundi(now * 100)])
		elif key == "cooldown":
			parts.append("cooldown %ss to %ss" % [was, now])
		else:
			parts.append("%s %s to %s" % [key, was, now])
	if parts.is_empty():
		return ""
	var text := " · ".join(parts)
	return text[0].to_upper() + text.substr(1)


func _on_state(state: int) -> void:
	_refresh()
	if state == Game.State.WON or state == Game.State.LOST:
		controller.set_mode("")
		_hovered = ""
		_tooltip.visible = false
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
## corner and the cost on the icon's shaded foot, so neither is painted over the subject.
func _card_button(name: String, hotkey: String, icon_path: String) -> Button:
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
	icon.texture = load(icon_path)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_SCALE
	icon.size = button.size
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material := ShaderMaterial.new()
	material.shader = GREY
	icon.material = material
	button.add_child(icon)
	button.draw.connect(_style_command.bind(button, icon, material))
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


func _style_command(button: Button, icon: TextureRect, material: ShaderMaterial) -> void:
	var mode := button.get_draw_mode()
	var pressed := mode == BaseButton.DRAW_PRESSED or mode == BaseButton.DRAW_HOVER_PRESSED
	icon.position = Vector2(0, 1) if pressed else Vector2.ZERO
	var state: String = button.get_meta("state", "ok")
	material.set_shader_parameter(
		"grey", 0.0 if state == "ok" else (1.0 if state == "poor" else IDLE_GREY)
	)
	material.set_shader_parameter("value", POOR_VALUE if state == "poor" else IDLE_VALUE)
	if state != "ok":
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
