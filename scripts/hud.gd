## The console, laid out the way strategy games do it: resources across the top
## right, and along the bottom a minimap, a live portrait of the selection, its
## stats, and a command card of framed icon buttons with hotkeys and tooltips.
## All frames are painted nine-slice StyleBoxes from ui/frames/.
class_name Hud
extends CanvasLayer

const GOLD := Color("#f2c94c")
const TEXT := Color("#efe3c4")
const DIM := Color("#b8a888")
const TITLE_FONT := preload("res://fonts/NotoSerifDisplay-Bold.ttf")
const BOLD_FONT := preload("res://fonts/NotoSerif-Bold.ttf")
const BODY_FONT := preload("res://fonts/NotoSerif-Regular.ttf")
const FRAMES := "res://ui/frames/"
const ICONS := "res://ui/icons/"
const CARD_SIZE := Vector2(54, 54)

var controller: BuildController
var waves: WaveDirector

var _gold: Label
var _lives: Label
var _wave: Label
var _countdown: Label
var _next_button: Button
var _banner: PanelContainer
var _banner_label: Label
var _banner_tween: Tween
var _portrait: Portrait
var _portrait_name: Label
var _title: Label
var _subtitle: Label
var _stats: GridContainer
var _body: Label
var _card := {}
var _tooltip: PanelContainer
var _tooltip_title: Label
var _tooltip_body: Label
var _hovered := ""
var _end_panel: PanelContainer
var _end_label: Label


func setup(main: Node) -> void:
	controller = main.controller
	waves = main.waves
	_build(main)
	Game.gold_changed.connect(func(_g: int) -> void: _refresh())
	Game.lives_changed.connect(func(_l: int) -> void: _refresh())
	Game.wave_changed.connect(func(_w: int) -> void: _refresh())
	Game.state_changed.connect(_on_state)
	Game.announced.connect(show_banner)
	controller.selection_changed.connect(func(_t: Tower) -> void: _refresh())
	controller.creep_selected.connect(func(_c: Creep) -> void: _refresh())
	controller.mode_changed.connect(func(_k: String) -> void: _refresh())
	_refresh()


func _process(_delta: float) -> void:
	if Game.state == Game.State.PREP:
		_countdown.text = "Next wave in %d" % ceili(Game.countdown)
	elif Game.state == Game.State.WAVE:
		_countdown.text = "Creeps left: %d" % waves.remaining()
	else:
		_countdown.text = ""
	var creep := controller.selected_creep
	if creep and is_instance_valid(creep) and not creep.dead:
		_describe_creep(creep)
	elif creep:
		controller.select_creep(null)


func show_banner(text: String) -> void:
	_banner_label.text = text
	_banner.visible = true
	_banner.modulate.a = 1.0
	if _banner_tween:
		_banner_tween.kill()
	_banner_tween = create_tween()
	_banner_tween.tween_interval(2.2)
	_banner_tween.tween_property(_banner, "modulate:a", 0.0, 0.6)
	_banner_tween.tween_callback(func() -> void: _banner.visible = false)


# ── Layout ──


func _build(main: Node) -> void:
	var root := Control.new()
	root.name = "Root"
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _theme()
	add_child(root)

	# Resources, top right.
	var top := _panel("topbar")
	top.name = "TopBar"
	top.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	top.offset_left = -600
	top.offset_right = -6
	top.offset_top = 6
	top.offset_bottom = 50
	root.add_child(top)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	top.add_child(row)
	_gold = _resource(row, "Gold", ICONS + "sell.png", GOLD)
	_lives = _resource(row, "Lives", ICONS + "hearth.png", Color("#ffb070"))
	_wave = _resource(row, "Wave", ICONS + "gourdling.png", Color("#d8c8ff"))
	_countdown = _label("", BODY_FONT, 15, DIM)
	_countdown.custom_minimum_size.x = 140
	_countdown.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(_countdown)

	_next_button = Button.new()
	_next_button.name = "NextWave"
	_next_button.text = "Next Wave  (N)"
	_next_button.focus_mode = Control.FOCUS_NONE
	_next_button.position = Vector2(8, 8)
	_next_button.custom_minimum_size = Vector2(170, 40)
	_next_button.pressed.connect(func() -> void: waves.start_next_wave())
	root.add_child(_next_button)

	# Announcement plate.
	_banner = _panel("banner")
	_banner.name = "Banner"
	_banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_banner.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_banner.offset_top = 62
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_banner.visible = false
	root.add_child(_banner)
	_banner_label = _label("", TITLE_FONT, 24, GOLD)
	_banner_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner.add_child(_banner_label)

	# Console.
	var console := _panel("console")
	console.name = "Console"
	console.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	console.offset_top = -208
	root.add_child(console)
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 10)
	console.add_child(columns)

	var mini_frame := _panel("frame")
	mini_frame.custom_minimum_size = Vector2(176, 164)
	columns.add_child(mini_frame)
	var minimap := Minimap.new()
	minimap.name = "Minimap"
	minimap.clip_contents = true
	minimap.setup(main.map, main.camera)
	mini_frame.add_child(minimap)

	var portrait_box := VBoxContainer.new()
	portrait_box.add_theme_constant_override("separation", 2)
	columns.add_child(portrait_box)
	var portrait_frame := _panel("frame")
	portrait_frame.custom_minimum_size = Vector2(140, 136)
	portrait_box.add_child(portrait_frame)
	var backdrop := TextureRect.new()
	backdrop.texture = _backdrop()
	backdrop.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	backdrop.stretch_mode = TextureRect.STRETCH_SCALE
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	portrait_frame.add_child(backdrop)
	_portrait = Portrait.new()
	_portrait.name = "Portrait"
	portrait_frame.add_child(_portrait)
	_portrait_name = _label("", BOLD_FONT, 13, GOLD)
	_portrait_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_portrait_name.custom_minimum_size.x = 140
	portrait_box.add_child(_portrait_name)

	var info := _panel("inset")
	info.name = "Info"
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	columns.add_child(info)
	var info_box := VBoxContainer.new()
	info_box.add_theme_constant_override("separation", 3)
	info.add_child(info_box)
	_title = _label("", TITLE_FONT, 22, GOLD)
	_title.name = "Title"
	info_box.add_child(_title)
	_subtitle = _label("", BOLD_FONT, 14, DIM)
	info_box.add_child(_subtitle)
	_stats = GridContainer.new()
	_stats.columns = 4
	_stats.add_theme_constant_override("h_separation", 18)
	info_box.add_child(_stats)
	_body = _label("", BODY_FONT, 14, TEXT)
	_body.name = "Body"
	_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.custom_minimum_size.x = 300
	info_box.add_child(_body)

	var card := GridContainer.new()
	card.name = "CommandCard"
	card.columns = 4
	card.add_theme_constant_override("h_separation", 4)
	card.add_theme_constant_override("v_separation", 4)
	columns.add_child(card)
	for kind: String in ["arrow", "cannon", "frost"]:
		var data: Dictionary = Game.TOWERS[kind]
		var button := _card_button(
			"Build%s" % kind.capitalize(), str(data["hotkey"]), str(data["icon"]), int(data["cost"])
		)
		button.pressed.connect(controller.set_mode.bind(kind))
		button.mouse_entered.connect(_hover.bind(kind))
		button.mouse_exited.connect(_hover.bind(""))
		card.add_child(button)
		_card[kind] = button
	card.add_child(_slot())
	var upgrade := _card_button("Upgrade", "U", ICONS + "upgrade.png", 0)
	upgrade.pressed.connect(controller.upgrade_selected)
	upgrade.mouse_entered.connect(_hover.bind("upgrade"))
	upgrade.mouse_exited.connect(_hover.bind(""))
	card.add_child(upgrade)
	_card["upgrade"] = upgrade
	var sell := _card_button("Sell", "S", ICONS + "sell.png", 0)
	sell.pressed.connect(controller.sell_selected)
	sell.mouse_entered.connect(_hover.bind("sell"))
	sell.mouse_exited.connect(_hover.bind(""))
	card.add_child(sell)
	_card["sell"] = sell
	for i in 6:
		card.add_child(_slot())

	# Tooltip above the command card.
	_tooltip = _panel("tooltip")
	_tooltip.name = "Tooltip"
	_tooltip.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_tooltip.offset_left = -340
	_tooltip.offset_right = -14
	_tooltip.offset_top = -342
	_tooltip.offset_bottom = -216
	_tooltip.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tooltip.visible = false
	root.add_child(_tooltip)
	var tip_box := VBoxContainer.new()
	_tooltip.add_child(tip_box)
	_tooltip_title = _label("", TITLE_FONT, 18, GOLD)
	tip_box.add_child(_tooltip_title)
	_tooltip_body = _label("", BODY_FONT, 14, TEXT)
	_tooltip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tooltip_body.custom_minimum_size.x = 290
	tip_box.add_child(_tooltip_body)

	# End of game.
	_end_panel = _panel("console")
	_end_panel.name = "EndPanel"
	_end_panel.set_anchors_preset(Control.PRESET_CENTER)
	_end_panel.custom_minimum_size = Vector2(440, 170)
	_end_panel.offset_left = -220
	_end_panel.offset_top = -150
	_end_panel.visible = false
	root.add_child(_end_panel)
	var end_box := VBoxContainer.new()
	end_box.alignment = BoxContainer.ALIGNMENT_CENTER
	end_box.add_theme_constant_override("separation", 14)
	_end_panel.add_child(end_box)
	_end_label = _label("", TITLE_FONT, 30, GOLD)
	_end_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	end_box.add_child(_end_label)
	var again := Button.new()
	again.name = "PlayAgain"
	again.text = "Play Again"
	again.focus_mode = Control.FOCUS_NONE
	again.custom_minimum_size = Vector2(170, 40)
	again.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	again.pressed.connect(func() -> void: get_tree().reload_current_scene())
	end_box.add_child(again)


# ── Content ──


func _refresh() -> void:
	_gold.text = str(Game.gold)
	_lives.text = str(Game.lives)
	_wave.text = "%d / %d" % [Game.wave, Game.total_waves()]
	_next_button.disabled = Game.state != Game.State.PREP or Game.wave >= Game.total_waves()
	for kind: String in ["arrow", "cannon", "frost"]:
		var button: Button = _card[kind]
		button.disabled = not Game.can_afford(int(Game.TOWERS[kind]["cost"]))
		button.modulate = Color(1.25, 1.2, 0.95) if controller.mode == kind else Color.WHITE
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	(_card["upgrade"] as Button).disabled = (
		not has_tower or tower.upgrade_cost() < 0 or not Game.can_afford(tower.upgrade_cost())
	)
	(_card["sell"] as Button).disabled = not has_tower
	if has_tower:
		_describe_tower(tower)
	elif controller.selected_creep and is_instance_valid(controller.selected_creep):
		_describe_creep(controller.selected_creep)
	elif controller.mode != "":
		_describe_build(controller.mode)
	else:
		_portrait.show_model("res://models/props/hearth.glb")
		_portrait_name.text = "The Hearth"
		_title.text = "Lantern Hollow"
		_subtitle.text = "Keep the lantern lit"
		_set_stats([])
		_body.text = (
			"Build with A, C and F, then click a grass tile. Click a tower to upgrade (U) or sell (S). "
			+ "N calls the next wave early for bonus gold. Arrows, wheel or the minimap move the view."
		)
	if _hovered != "":
		_show_tooltip(_hovered)


func _describe_build(kind: String) -> void:
	var data: Dictionary = Game.TOWERS[kind]
	_show_tower_portrait(kind, 1)
	_portrait_name.text = str(data["name"])
	_title.text = str(data["name"])
	_subtitle.text = "Costs %d gold · click a grass tile" % int(data["cost"])
	_set_stats(_tower_stats(data))
	_body.text = str(data["description"])


func _describe_tower(tower: Tower) -> void:
	var data: Dictionary = Game.TOWERS[tower.kind]
	_show_tower_portrait(tower.kind, tower.level)
	_portrait_name.text = str(data["name"])
	_title.text = str(data["name"])
	_subtitle.text = "Level %d · %d kills" % [tower.level, tower.kills]
	_set_stats(_tower_stats(tower.stats))
	var next := (
		"Upgrade (U) for %d gold." % tower.upgrade_cost()
		if tower.upgrade_cost() > 0
		else "Fully upgraded."
	)
	_body.text = "%s  Sell (S) for %d gold." % [next, tower.sell_value()]


func _describe_creep(creep: Creep) -> void:
	var data: Dictionary = Game.CREEPS[creep.kind]
	_portrait.show_model(str(data["model"]))
	_portrait_name.text = str(data["name"])
	_title.text = str(data["name"])
	_subtitle.text = "Wave %d" % Game.wave
	_set_stats(
		[
			["Health", "%d / %d" % [ceili(creep.hp), ceili(creep.max_hp)]],
			["Speed", "%.1f" % (creep.speed * creep.slow_factor)],
			["Bounty", "%d gold" % creep.bounty],
			["Lives", str(creep.lives_cost)],
		]
	)
	_body.text = "Slowed by frost." if creep.slow_factor < 1.0 else ""


func _show_tower_portrait(kind: String, level: int) -> void:
	var data: Dictionary = Game.TOWERS[kind]
	var model: String = data.get("model_2", data["model"]) if level >= 2 else data["model"]
	_portrait.show_model(model, str(data.get("head", "")), float(data.get("head_height", 0.0)))


func _tower_stats(s: Dictionary) -> Array:
	var stats := [
		["Damage", str(s["damage"])], ["Range", str(s["range"])], ["Every", "%ss" % s["cooldown"]]
	]
	if s.has("splash"):
		stats.append(["Splash", str(s["splash"])])
	elif s.has("slow"):
		stats.append(["Slow", "%d%%" % int(float(s["slow"]) * 100)])
	return stats


## Rebuilt only when the values change, so labels are not recreated every frame.
func _set_stats(pairs: Array) -> void:
	if _stats.get_meta("pairs", []) == pairs:
		return
	_stats.set_meta("pairs", pairs)
	for child in _stats.get_children():
		child.free()
	for pair: Array in pairs:
		var cell := HBoxContainer.new()
		cell.add_theme_constant_override("separation", 6)
		cell.add_child(_label(str(pair[0]), BOLD_FONT, 13, DIM))
		cell.add_child(_label(str(pair[1]), BOLD_FONT, 14, TEXT))
		_stats.add_child(cell)


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
	_tooltip.visible = true
	var tower := controller.selected
	var has_tower := tower != null and is_instance_valid(tower)
	if what in Game.TOWERS:
		var data: Dictionary = Game.TOWERS[what]
		_tooltip_title.text = "%s  [%s]" % [data["name"], data["hotkey"]]
		_tooltip_body.text = "Costs %d gold.\n%s" % [int(data["cost"]), data["description"]]
	elif what == "upgrade":
		_tooltip_title.text = "Upgrade  [U]"
		_tooltip_body.text = (
			"Raises damage and range for %d gold." % tower.upgrade_cost()
			if has_tower and tower.upgrade_cost() > 0
			else "Select a tower to upgrade it."
		)
	else:
		_tooltip_title.text = "Sell  [S]"
		_tooltip_body.text = (
			"Returns %d gold." % tower.sell_value() if has_tower else "Select a tower to sell it."
		)


func _on_state(state: int) -> void:
	_refresh()
	if state == Game.State.WON or state == Game.State.LOST:
		controller.set_mode("")
		_end_panel.visible = true
		_end_label.text = "Victory!" if state == Game.State.WON else "The hearth has gone dark"


# ── Widgets ──


func _theme() -> Theme:
	var theme := Theme.new()
	theme.default_font = BODY_FONT
	theme.default_font_size = 15
	theme.set_color("font_color", "Label", TEXT)
	theme.set_constant("outline_size", "Label", 4)
	theme.set_color("font_outline_color", "Label", Color(0.05, 0.03, 0.02, 0.9))
	for state: String in ["normal", "hover", "pressed", "disabled"]:
		theme.set_stylebox(state, "Button", load(FRAMES + "wide_button_%s.tres" % state))
	theme.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	theme.set_font("font", "Button", BOLD_FONT)
	theme.set_font_size("font_size", "Button", 15)
	theme.set_color("font_color", "Button", GOLD)
	theme.set_color("font_hover_color", "Button", Color("#fff1c0"))
	theme.set_color("font_disabled_color", "Button", Color("#7a6d58"))
	theme.set_constant("outline_size", "Button", 4)
	theme.set_color("font_outline_color", "Button", Color(0.05, 0.03, 0.02))
	return theme


func _panel(frame: String) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", load(FRAMES + frame + ".tres"))
	return panel


func _label(text: String, font: Font, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


func _resource(parent: Node, name: String, icon_path: String, color: Color) -> Label:
	var icon := TextureRect.new()
	icon.texture = load(icon_path)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.custom_minimum_size = Vector2(28, 28)
	parent.add_child(icon)
	var value := _label("", TITLE_FONT, 19, color)
	value.name = name
	value.custom_minimum_size.x = 64
	parent.add_child(value)
	return value


func _card_button(name: String, hotkey: String, icon_path: String, cost: int) -> Button:
	var button := Button.new()
	button.name = name
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = CARD_SIZE
	for state: String in ["normal", "hover", "pressed", "disabled"]:
		button.add_theme_stylebox_override(state, load(FRAMES + "button_%s.tres" % state))
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.texture = load(icon_path)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_SCALE
	icon.set_anchors_preset(Control.PRESET_FULL_RECT)
	icon.offset_left = 4
	icon.offset_top = 4
	icon.offset_right = -4
	icon.offset_bottom = -4
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(icon)
	# Disabled buttons grey their icon out, like an unaffordable command.
	button.draw.connect(
		func() -> void: icon.modulate = Color(0.4, 0.4, 0.42) if button.disabled else Color.WHITE
	)
	var key := _label(hotkey, BOLD_FONT, 13, Color("#ffe08a"))
	key.position = Vector2(6, 2)
	key.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(key)
	if cost > 0:
		var price := _label(str(cost), BOLD_FONT, 12, GOLD)
		price.position = Vector2(27, 34)
		price.mouse_filter = Control.MOUSE_FILTER_IGNORE
		button.add_child(price)
	return button


## A dusk-blue radial backdrop for the portrait, brighter behind the model.
func _backdrop() -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.set_color(0, Color("#2c3f63"))
	gradient.set_color(1, Color("#0c111c"))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.42)
	texture.fill_to = Vector2(1.0, 1.0)
	return texture


func _slot() -> Control:
	var slot := Panel.new()
	slot.custom_minimum_size = CARD_SIZE
	slot.add_theme_stylebox_override("panel", load(FRAMES + "slot.tres"))
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return slot
