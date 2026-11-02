## The Drift tray (design 1.4 and 5.7, contract-m7.md §3): in a duel, a bronze-rimmed
## shelf standing on the console's left wing, over the minimap, in three parts.
##
## The Drift: the three packs the window offers, each its icon (the portrait of the creep
## it sends with a bottle on it), its key (1, 2, 3: off the card's Q row) and the tier's
## price, the same for every pack of a tier. A click or its key corks it in a build window.
## During a wave the next window's packs wait greyed.
##
## Yours: my bottles, each standing in its socket with the pack I put in it, from the moment
## its CORK goes out. During its wave the socket counts down to the uncorking the client
## does by itself (24 s after the horn); from 3 s after the horn the next one carries the
## Space key and lights, and a click or Space uncorks it sooner.
##
## The rival's: their bottles as corked shapes, each showing only its tier and, under it,
## its candidates (M8, contract-m8 §4): the packs its window offered at that tier, small and
## dim, never which one it holds.
##
## Hovering a pack or a bottle explains it in a small plate above the tray. The tray reads
## Game (the duel's records) and decides nothing; the build controller sends the orders.
class_name DriftTray
extends PanelContainer

const PACK_SIZE := Vector2(52, 52)
const BOTTLE_SIZE := Vector2(36, 50)
## (M8) A rival bottle's candidates: three small pack icons under it, dimmed, as wide as the
## socket together (the tray keeps left of the crest's arch at 1280 x 720).
const CANDIDATE_SIZE := 12.0
const CANDIDATE_TINT := Color(0.72, 0.68, 0.62, 0.8)
## Bottles shown per side: two corks a window from window 9 is the most a side can hold.
const BOTTLES := 2
## Where a bottle's pack face sits while the Space key's tab takes the socket's top.
const FACE_LIT_Y := 15.0
const KEYS := ["1", "2", "3"]
## How grey and how dark a pack that cannot be corked now draws.
const IDLE_GREY := 0.7
const IDLE_VALUE := 0.8
const GREY := preload("res://shaders/hud_grey.gdshader")

var controller: BuildController
var _bold: Font
var _body: Font
var _caps: Font
var _coin: Texture2D
var _socket: StyleBox
var _socket_lit: StyleBox
var _packs: Array[Button] = []
var _mine: Array[Button] = []
var _rivals: Array[Control] = []
var _tier: Label
var _price: Label
var _tip: PanelContainer
var _tip_title: Label
var _tip_body: Label
var _hovered := ""
## What each part shows now, for tests (packs_shown, mine_shown, rivals_shown).
var _shown_packs: Array = []
var _shown_mine: Array = []
var _shown_rivals: Array = []


func setup(
	build: BuildController, plate: StyleBox, socket: StyleBox, socket_lit: StyleBox, tip: StyleBox,
	fonts: Array, coin: Texture2D
) -> void:
	controller = build
	_bold = fonts[0]
	_body = fonts[1]
	_caps = fonts[2]
	_coin = coin
	_socket = socket
	_socket_lit = socket_lit
	name = "DriftTray"
	add_theme_stylebox_override("panel", plate)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var row := HBoxContainer.new()
	row.name = "Row"
	row.add_theme_constant_override("separation", 8)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(row)
	var drift := _section(row, "DriftSection", "THE DRIFT")
	var head := drift.get_child(0) as HBoxContainer
	_tier = _label("", _bold, 11, Hud.GOLD)
	_tier.name = "Tier"
	head.add_child(_tier)
	var coin_icon := TextureRect.new()
	coin_icon.name = "Coin"
	coin_icon.texture = _coin
	coin_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	coin_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	coin_icon.custom_minimum_size = Vector2(13, 13)
	coin_icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	coin_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	head.add_child(coin_icon)
	_price = _label("", _bold, 11, Hud.COIN)
	_price.name = "Price"
	head.add_child(_price)
	var packs := HBoxContainer.new()
	packs.name = "Packs"
	packs.add_theme_constant_override("separation", 5)
	packs.mouse_filter = Control.MOUSE_FILTER_IGNORE
	drift.add_child(packs)
	for i in KEYS.size():
		var button := _pack_button(i)
		packs.add_child(button)
		_packs.append(button)
	row.add_child(_rule())
	var mine := _section(row, "MineSection", "YOURS")
	var mine_row := HBoxContainer.new()
	mine_row.name = "Mine"
	mine_row.add_theme_constant_override("separation", 4)
	mine_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mine.add_child(mine_row)
	for i in BOTTLES:
		var bottle := _bottle_button(i)
		mine_row.add_child(bottle)
		_mine.append(bottle)
	row.add_child(_rule())
	var rival := _section(row, "RivalSection", "RIVAL'S")
	var rival_row := HBoxContainer.new()
	rival_row.name = "Rivals"
	rival_row.add_theme_constant_override("separation", 4)
	rival_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rival.add_child(rival_row)
	for i in BOTTLES:
		var shape := _rival_bottle(i)
		rival_row.add_child(shape)
		_rivals.append(shape)
	_build_tip(tip)
	visible = false


## The packs as shown, for tests: [{"check", "name", "price", "key", "state" ("ok", "poor"
## or "idle"), "icon"}].
func packs_shown() -> Array:
	return _shown_packs.duplicate(true)


## My bottles as shown, for tests: [{"id", "pack", "text" (the countdown or what it waits
## for), "space" (it carries the Space key), "lit"}].
func mine_shown() -> Array:
	return _shown_mine.duplicate(true)


## The rival's bottles as shown, for tests: [{"tier" ("I", "II", "III"), "pack" (always ""),
## "candidates" (M8: the checks of the packs its window offered at its tier, as the icons
## under it show them)}].
func rivals_shown() -> Array:
	return _shown_rivals.duplicate(true)


## The explaining plate's title and body while something is hovered, else ["", ""].
func tip_shown() -> Array:
	return [_tip_title.text, _tip_body.text] if _tip.visible else ["", ""]


## Follows the duel's records: called every frame by the HUD while a duel plays.
func refresh() -> void:
	var window := Game.duel_window()
	var tier := Game.duel_tier(window)
	var offer := Game.drift_packs()
	var price := Game.cork_price(window)
	var corking := Game.state == Game.State.PREP and tier >= 0
	# (the window's tier and price; before the Drift opens, when it does; during a wave, whose
	# next window has not drawn its packs yet, that they come with it)
	var drawn := tier >= 0 and not offer.is_empty()
	if drawn:
		_tier.text = "TIER %s" % Game.TIER_NAMES[tier]
	elif tier >= 0:
		_tier.text = "NEXT WINDOW"
	else:
		_tier.text = "FROM WAVE %d" % int(Game.duel_rules()["drift_from"]) if Game.is_duel() else ""
	_price.text = str(price) if drawn else ""
	(_price.get_parent().get_node("Coin") as Control).visible = drawn
	_shown_packs = []
	for i in _packs.size():
		var button := _packs[i]
		var check := str(offer[i]) if i < offer.size() else ""
		button.set_meta("check", check)
		var icon: TextureRect = button.get_node("Icon")
		var cost: Label = button.get_node("Cost")
		if check == "":
			icon.visible = false
			cost.text = ""
			_style(button, "idle")
			continue
		var info := Game.pack_info(check, maxi(tier, 0))
		icon.visible = true
		var texture := Game.icon(str(info["icon"]))
		if icon.texture != texture:
			icon.texture = texture
		cost.text = str(price)
		var why := Game.cork_refusal(check)
		var state := "ok"
		if why != "":
			state = "poor" if corking and why == Game.NOTICES[SimTypes.REFUSE_NOT_ENOUGH_GOLD] else "idle"
		_style(button, state)
		cost.add_theme_color_override("font_color", Hud.SHORT if state == "poor" else (Hud.COIN if state == "ok" else Hud.DIM))
		_shown_packs.append(
			{"check": check, "name": info["name"], "price": price, "key": KEYS[i], "state": state, "icon": info["icon"]}
		)
	_refresh_mine()
	_refresh_rivals()
	if _hovered != "":
		_show_tip(_hovered)


func _refresh_mine() -> void:
	var bottles := Game.my_bottles()
	var next := Game.next_to_uncork()
	var can_now := next >= 0 and Game.uncork_refusal(next) == ""
	_shown_mine = []
	for i in _mine.size():
		var button := _mine[i]
		var b: Dictionary = bottles[i] if i < bottles.size() else {}
		button.set_meta("bottle", int(b.get("id", -1)) if not b.is_empty() else -2)
		var glass: TextureRect = button.get_node("Glass")
		var face: TextureRect = button.get_node("Face")
		var text: Label = button.get_node("Count")
		var tab: Control = button.get_node("KeyTab")
		glass.visible = not b.is_empty()
		face.visible = not b.is_empty() and str(b["pack"]) != ""
		tab.visible = false
		var lit := false
		if b.is_empty():
			text.text = ""
			button.disabled = true
			_set_socket(button, false)
			continue
		if face.visible:
			var texture := Game.icon(str(Game.pack_info(str(b["pack"]), 0)["icon"]))
			if face.texture != texture:
				face.texture = texture
		var words := ""
		if bool(b["waiting"]):
			words = "…"
		elif int(b["uncork"]) >= 0:
			words = "open"
		elif not bool(b["known"]) and not bool(b["caretaker"]):
			# (its salt is not on this machine: nothing can open it, and it fizzles at 25 s)
			words = "lost"
		elif int(b["auto"]) >= 0:
			# (to the client's own uncorking at 24 s; a caretaker's bottle to its at 3 s)
			words = "%d s" % ceili(maxi(0, int(b["auto"]) - Game.sim.tick) / float(SimTypes.TICKS_PER_SECOND))
			if int(b["id"]) == next and can_now:
				lit = true
				tab.visible = true
		elif int(b["window"]) == Game.duel_window():
			words = "wave %d" % int(b["window"])
		text.text = words
		# (the Space key's tab takes the socket's top: the pack's face steps down beside the glass,
		# so a lit bottle still shows what it holds)
		face.position.y = FACE_LIT_Y if tab.visible else 1.0
		# (a bottle corked for the duel's wave answers a click as Space does, while that wave runs
		# on either hollow: mine may stand in its window while the rival's road waits for the
		# pack; one still corking or opening does not)
		button.disabled = int(b["id"]) < 0 or not bool(b["due"]) or int(b["uncork"]) >= 0
		_set_socket(button, lit)
		_shown_mine.append({"id": int(b["id"]), "pack": str(b["pack"]), "text": words, "space": tab.visible, "lit": lit})


func _refresh_rivals() -> void:
	var bottles := Game.rival_bottles()
	_shown_rivals = []
	for i in _rivals.size():
		var shape := _rivals[i]
		var has := i < bottles.size()
		(shape.get_node("Glass") as Control).visible = has
		var tier: Label = shape.get_node("Tier")
		tier.text = Game.TIER_NAMES[clampi(int(bottles[i]["tier"]), 0, 2)] if has else ""
		shape.set_meta("tier", tier.text)
		var shown := _show_candidates(shape, bottles[i]["candidates"] if has else [], int(bottles[i]["tier"]) if has else 0)
		if has:
			_shown_rivals.append({"tier": tier.text, "pack": "", "candidates": shown})


## (M8) The pack icons of a rival bottle's candidates under it, in CHECK_IDS order; the
## checks shown.
func _show_candidates(shape: Control, candidates: Array, tier: int) -> Array:
	var row: HBoxContainer = shape.get_node("Candidates")
	var shown := []
	for i in row.get_child_count():
		var icon := row.get_child(i) as TextureRect
		var has := i < candidates.size()
		icon.visible = has
		if has:
			var check := str(candidates[i])
			if str(icon.get_meta("check", "")) != check:
				icon.texture = Game.icon(str(Game.pack_info(check, tier)["icon"]))
				icon.set_meta("check", check)
			shown.append(check)
	return shown


# ── Pieces ──


func _section(row: HBoxContainer, node_name: String, caption: String) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.name = node_name
	box.add_theme_constant_override("separation", 3)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(box)
	var head := HBoxContainer.new()
	head.name = "Head"
	head.add_theme_constant_override("separation", 6)
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(head)
	var label := _label(caption, _caps, 11, Hud.DIM)
	label.name = "Caption"
	head.add_child(label)
	return box


## A thin bronze rule between the tray's parts.
func _rule() -> Control:
	var rule := ColorRect.new()
	rule.color = Color("#5c4b33")
	rule.custom_minimum_size = Vector2(1, 0)
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rule


func _pack_button(i: int) -> Button:
	var button := Button.new()
	button.name = "Pack%d" % (i + 1)
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = PACK_SIZE
	for state: String in ["normal", "hover", "pressed", "hover_pressed", "disabled", "focus"]:
		button.add_theme_stylebox_override(state, StyleBoxEmpty.new())
	var well := Panel.new()
	well.name = "Well"
	well.add_theme_stylebox_override("panel", _socket)
	well.set_anchors_preset(Control.PRESET_FULL_RECT)
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(well)
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.position = Vector2(3, 3)
	icon.size = PACK_SIZE - Vector2(6, 6)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material := ShaderMaterial.new()
	material.shader = GREY
	icon.material = material
	button.add_child(icon)
	button.add_child(_key_tab(KEYS[i], Vector2(2, 2), Vector2(14, 14)))
	var cost := _label("", _bold, 12, Hud.COIN)
	cost.name = "Cost"
	cost.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	cost.position = Vector2(2, PACK_SIZE.y - 17)
	cost.size = Vector2(PACK_SIZE.x - 6, 16)
	cost.add_theme_constant_override("outline_size", 3)
	button.add_child(cost)
	button.pressed.connect(func() -> void: controller.cork_slot(i))
	button.mouse_entered.connect(func() -> void: _hover("pack%d" % i))
	button.mouse_exited.connect(func() -> void: _hover(""))
	return button


func _bottle_button(i: int) -> Button:
	var button := Button.new()
	button.name = "Mine%d" % (i + 1)
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = BOTTLE_SIZE
	for state: String in ["normal", "hover", "pressed", "hover_pressed", "disabled", "focus"]:
		button.add_theme_stylebox_override(state, StyleBoxEmpty.new())
	var well := Panel.new()
	well.name = "Well"
	well.add_theme_stylebox_override("panel", _socket)
	well.set_anchors_preset(Control.PRESET_FULL_RECT)
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(well)
	button.add_child(_glass(Vector2(BOTTLE_SIZE.x, BOTTLE_SIZE.y - 12)))
	var face := TextureRect.new()
	face.name = "Face"
	face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	face.position = Vector2(BOTTLE_SIZE.x - 19, 1)
	face.size = Vector2(18, 18)
	face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(face)
	var count := _label("", _bold, 11, Hud.TEXT)
	count.name = "Count"
	count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	count.position = Vector2(-6, BOTTLE_SIZE.y - 15)
	count.size = Vector2(BOTTLE_SIZE.x + 12, 14)
	count.add_theme_constant_override("outline_size", 3)
	button.add_child(count)
	var tab := _key_tab("Space", Vector2(1, 1), Vector2(30, 13))
	tab.visible = false
	button.add_child(tab)
	button.pressed.connect(func() -> void: controller.uncork(int(button.get_meta("bottle", -1))))
	button.mouse_entered.connect(func() -> void: _hover("mine%d" % i))
	button.mouse_exited.connect(func() -> void: _hover(""))
	return button


func _rival_bottle(i: int) -> Control:
	var shape := Control.new()
	shape.name = "Rival%d" % (i + 1)
	# (the socket, and under it a row for the candidates, M8: three small packs side by side)
	var width := maxf(BOTTLE_SIZE.x, CANDIDATE_SIZE * 3)
	var left := (width - BOTTLE_SIZE.x) * 0.5
	shape.custom_minimum_size = Vector2(width, BOTTLE_SIZE.y + CANDIDATE_SIZE + 2)
	shape.mouse_filter = Control.MOUSE_FILTER_PASS
	var well := Panel.new()
	well.name = "Well"
	well.add_theme_stylebox_override("panel", _socket)
	well.position = Vector2(left, 0)
	well.size = BOTTLE_SIZE
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shape.add_child(well)
	# (the rival's glass is dark: corked, it shows nothing of what is inside)
	var glass := _glass(Vector2(BOTTLE_SIZE.x, BOTTLE_SIZE.y - 12))
	glass.position.x += left
	glass.modulate = Color(0.55, 0.62, 0.66)
	shape.add_child(glass)
	var tier := _label("", Hud.TITLE_FONT, 15, Hud.GOLD)
	tier.name = "Tier"
	tier.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tier.position = Vector2(left, BOTTLE_SIZE.y - 18)
	tier.size = Vector2(BOTTLE_SIZE.x, 16)
	tier.add_theme_constant_override("outline_size", 4)
	shape.add_child(tier)
	var candidates := HBoxContainer.new()
	candidates.name = "Candidates"
	candidates.alignment = BoxContainer.ALIGNMENT_CENTER
	candidates.add_theme_constant_override("separation", 0)
	candidates.mouse_filter = Control.MOUSE_FILTER_IGNORE
	candidates.position = Vector2(0, BOTTLE_SIZE.y + 2)
	candidates.size = Vector2(width, CANDIDATE_SIZE)
	for k in 3:
		var icon := TextureRect.new()
		icon.name = "Candidate%d" % (k + 1)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.custom_minimum_size = Vector2(CANDIDATE_SIZE, CANDIDATE_SIZE)
		icon.modulate = CANDIDATE_TINT
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon.visible = false
		candidates.add_child(icon)
	shape.add_child(candidates)
	shape.mouse_entered.connect(func() -> void: _hover("rival%d" % i))
	shape.mouse_exited.connect(func() -> void: _hover(""))
	return shape


func _glass(size: Vector2) -> TextureRect:
	var glass := TextureRect.new()
	glass.name = "Glass"
	glass.texture = Game.icon(Game.BOTTLE_ICON)
	glass.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glass.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	glass.position = Vector2(0, 1)
	glass.size = size
	glass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	glass.visible = false
	return glass


func _key_tab(key: String, at: Vector2, size: Vector2) -> Panel:
	var tab := Panel.new()
	tab.name = "KeyTab"
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0, 0, 0, 0.7)
	box.set_corner_radius_all(3)
	tab.add_theme_stylebox_override("panel", box)
	tab.position = at
	tab.size = size
	tab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var label := _label(key, _bold, 10, Hud.KEY)
	label.name = "Hotkey"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_constant_override("outline_size", 0)
	label.set_anchors_preset(Control.PRESET_FULL_RECT)
	tab.add_child(label)
	return tab


## A pack's look: in full colour when it may be corked, grey when short of gold, darker
## when it cannot be now.
func _style(button: Button, state: String) -> void:
	button.disabled = state != "ok"
	button.set_meta("state", state)
	var material := (button.get_node("Icon") as TextureRect).material as ShaderMaterial
	# (an idle pack stays readable: the tray shows what the next window will offer)
	material.set_shader_parameter("grey", 0.0 if state == "ok" else (1.0 if state == "poor" else IDLE_GREY))
	material.set_shader_parameter("value", Hud.POOR_VALUE if state == "poor" else IDLE_VALUE)
	(button.get_node("KeyTab") as Control).visible = (button.get_node("Icon") as Control).visible


func _set_socket(button: Button, lit: bool) -> void:
	(button.get_node("Well") as Panel).add_theme_stylebox_override("panel", _socket_lit if lit else _socket)


# ── The explaining plate ──


func _build_tip(box: StyleBox) -> void:
	_tip = PanelContainer.new()
	_tip.name = "DriftTip"
	_tip.add_theme_stylebox_override("panel", box)
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
	_tip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tip_body.custom_minimum_size.x = 300
	_tip_body.add_theme_constant_override("outline_size", 0)
	col.add_child(_tip_body)


func _hover(what: String) -> void:
	_hovered = what
	if what == "":
		_tip.visible = false
		return
	_show_tip(what)


func _show_tip(what: String) -> void:
	var title := ""
	var body := ""
	var window := Game.duel_window()
	var tier := maxi(0, Game.duel_tier(window))
	if what.begins_with("pack"):
		var i := int(what.trim_prefix("pack"))
		var check := str(_packs[i].get_meta("check", ""))
		if check == "":
			if Game.duel_tier(window) < 0:
				# (how many it offers is the rules', as the numbers say it)
				body = "The Drift opens before wave %d: then each window brings %s of %s packs, the same to both sides." % [
					int(Game.duel_rules()["drift_from"]), Game.waves_word(int(Game.duel_rules()["offered"])).to_lower(),
					Game.waves_word(SimContent.CHECK_IDS.size()).to_lower()
				]
			else:
				body = "The next window's %s packs show here when it opens, once both waves are over." % Game.waves_word(int(Game.duel_rules()["offered"])).to_lower()
			title = "The Drift"
		else:
			var info := Game.pack_info(check, tier)
			title = "%s (%s)" % [info["name"], KEYS[i]]
			var creep := str(Game.CREEPS.get(str(info["creep"]), {}).get("name", info["creep"]))
			var gain := "then +%d gold a wave for the rest of the match" % Game.stipend_gain(window)
			if Game.surge() > 0:
				gain = "in the Surge stipends no longer grow"
			# (the premium on a sent creep's health is its pack's in the rules, as the numbers
			# say it)
			var stronger := Game.send_premium_words(check)
			body = "%d %s%s walk your rival's road · %s%s. Corked now for %d gold, uncorked in the next wave; %s. Your rival sees only a tier %s bottle." % [
				int(info["count"]), creep, "s" if int(info["count"]) > 1 else "",
				str(Game.CHECKS[check]["name"]), ", " + stronger if stronger != "" else "",
				Game.cork_price(window), gain, Game.TIER_NAMES[tier]
			]
			var why := Game.cork_refusal(check)
			if why != "":
				body += "\n" + why + "."
	elif what.begins_with("mine"):
		var i := int(what.trim_prefix("mine"))
		var bottles := Game.my_bottles()
		title = "Your bottle"
		if i < bottles.size():
			var b: Dictionary = bottles[i]
			if str(b["pack"]) != "":
				title = "%s, corked" % Game.pack_info(str(b["pack"]), 0)["name"]
			# (the timings are the duel's rules', as the numbers say them)
			var auto := Game.duel_seconds("auto_uncork_t")
			var after := Game.duel_seconds("uncork_after_t")
			body = "It uncorks by itself %s after the horn of wave %d. From %s after it, Space or a click uncorks it sooner." % [auto, int(b["window"]), after]
			if bool(b["caretaker"]):
				body = "The caretaker corked it while you were away, its pack in plain sight: it uncorks it %s after the horn of wave %d." % [after, int(b["window"])]
			elif not bool(b["known"]):
				body = "Its salt is not on this machine any more, so nothing can uncork it: %s after the horn of wave %d it fizzles, its gold spent." % [Game.duel_seconds("fizzle_t"), int(b["window"])]
		else:
			body = "A pack you cork waits here for the next wave."
	elif what.begins_with("rival"):
		var i := int(what.trim_prefix("rival"))
		var bottles := Game.rival_bottles()
		title = "Your rival's bottle"
		if i < bottles.size():
			body = Game.rival_bottle_text(bottles[i], bottles)
		else:
			body = "Your rival's corked bottles stand here, each with its tier and the packs it may hold."
	_tip_title.text = title
	_tip_body.text = body
	_tip.visible = body != "" or title != ""
	_tip.reset_size()
	_tip.global_position = global_position + Vector2(0, -_tip.get_combined_minimum_size().y - 6)


func _label(text: String, font: Font, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_override("font", font)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label
