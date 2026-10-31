## The hub's frame (design 5.1): the Causeway at low water behind everything (CausewayView,
## its props in a world of their own), and the game's own bronze console in front, the
## same pieces the HUD draws (ui/console/, placed by layout.json), whose wells hold what
## each screen needs. The hub (HubPanel) puts the
## party in the left well, your Builder in the arch and the modes and the one button in
## the right well; the Builders screen (BuildersScreen) the roster, the selected Builder
## and its kit. Overlays: the Join panel, the name prompt on first launch, notices.
##
## The statics are the console kit every screen shares: fonts, colours, the theme, the
## painted pieces, plates and command sockets.
class_name Shell
extends CanvasLayer

const GOLD := Color("#f0cf86")
const TEXT := Color("#ece2cc")
const DIM := Color("#a3957d")
const KEY := Color("#f3e6c4")
const AMBER := Color("#ffb347")
const NOTICE := Color("#ffd36a")
const GOOD := Color("#9be06a")
const INK := Color(0.04, 0.03, 0.02, 0.85)
const TITLE_FONT := preload("res://fonts/NotoSerifDisplay-Bold.ttf")
const BOLD_FONT := preload("res://fonts/NotoSerif-Bold.ttf")
const BODY_FONT := preload("res://fonts/NotoSerif-Regular.ttf")
const ART := "res://ui/console/"
const ICONS := "res://ui/icons/"

## How long the hub's word after a lost link stays (Session.hub_notice), in seconds.
const HUB_NOTICE_HOLD := 7.0

static var _layout := {}
static var _caps: FontVariation

var portrait: Portrait
var hub: HubPanel
var builders: BuildersScreen
var join: JoinPanel
var prompt: NamePrompt
var _root: Control
var _glyph: TextureRect
var _notice: Label
var _notice_tween: Tween
var _shown_builder := ""


func _ready() -> void:
	name = "Shell"
	if Session.boot():
		return  # (boot flags asked for a match: the match scene plays them)
	_root = Control.new()
	_root.name = "Root"
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.theme = theme()
	_root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(_root)
	var backdrop := CausewayView.new()
	backdrop.name = "Causeway"
	_root.add_child(backdrop)
	_build_console()
	hub = HubPanel.new()
	_root.add_child(hub)
	hub.setup(self)
	builders = BuildersScreen.new()
	_root.add_child(builders)
	builders.setup(self)
	join = JoinPanel.new()
	_root.add_child(join)
	join.setup(self)
	_build_notice()
	prompt = NamePrompt.new()
	_root.add_child(prompt)
	prompt.setup(self)
	Session.changed.connect(refresh)
	Session.noticed.connect(show_notice)
	refresh()
	if Session.hub_notice != "":
		# (why the party is gone: said once the hub stands, and held long enough to read)
		show_notice(Session.hub_notice, HUB_NOTICE_HOLD)
		Session.hub_notice = ""
	if not Session.profile.named:
		prompt.open()


func _exit_tree() -> void:
	Session.beacon.stop()


## Shows the screen the session names and fills it.
func refresh() -> void:
	if _root == null:
		return
	var on_builders := Session.screen == "builders"
	hub.visible = not on_builders
	builders.visible = on_builders
	if on_builders:
		join.close()
		builders.refresh()
	else:
		hub.refresh()
	join.refresh()


## The arch shows a Builder: its posed model once built (models/builders/), its bust when
## `close` (the hub's arch: a face, as a portrait window frames one) and the whole figure
## otherwise (the Builders screen); until it is built, its glyph in its own tint.
func show_builder(builder: String, close := false) -> void:
	var key := "%s|%s" % [builder, close]
	if key == _shown_builder:
		return
	_shown_builder = key
	var model := str(Game.BUILDERS[builder]["portrait"])
	if close and Game.has_art(str(Game.BUILDERS[builder].get("bust", ""))):
		model = str(Game.BUILDERS[builder]["bust"])
	if Game.has_art(model):
		portrait.show_model(model)
		_glyph.visible = false
	else:
		portrait.show_model("")
		_glyph.texture = Game.icon(str(Game.BUILDERS[builder]["glyph"]))
		_glyph.modulate = Game.glyph_tint(builder)
		_glyph.visible = true


## A short line over the arch for a moment: a refused code, a lost server.
func show_notice(text: String, hold := 2.2) -> void:
	_notice.text = text
	_notice.visible = true
	_notice.modulate.a = 1.0
	if _notice_tween:
		_notice_tween.kill()
	_notice_tween = create_tween()
	_notice_tween.tween_interval(hold)
	_notice_tween.tween_property(_notice, "modulate:a", 0.0, 0.6)
	_notice_tween.tween_callback(func() -> void: _notice.visible = false)


func _unhandled_key_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo or prompt.visible:
		return
	if Session.screen == "builders":
		builders.key(key.keycode)
	elif join.visible and key.keycode == KEY_ESCAPE:
		join.close()
	else:
		hub.key(key.keycode)


func _build_console() -> void:
	var console := Control.new()
	console.name = "Console"
	console.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	console.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(console)
	var rail := art("rail.png", true)
	rail.name = "Rail"
	rail.tile = true
	rail.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	rail.anchor_right = 1.0
	rail.anchor_top = 1.0
	rail.anchor_bottom = 1.0
	rail.offset_top = -float(layout()["rail"])
	console.add_child(rail)
	var centre_size := vec("centre")
	var centre := piece(console, "Centre", 0.5, -centre_size.x * 0.5, centre_size)
	var window := rect("window")
	var backdrop := art("portrait_bg.png")
	backdrop.name = "Backdrop"
	place(backdrop, rect("backdrop"))
	backdrop.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	centre.add_child(backdrop)
	portrait = Portrait.new()
	portrait.name = "Portrait"
	place(portrait, Rect2(window.position - backdrop.position, window.size))
	backdrop.add_child(portrait)
	_glyph = TextureRect.new()
	_glyph.name = "BuilderGlyph"
	_glyph.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_glyph.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
	place(_glyph, Rect2(window.position - backdrop.position + Vector2(14, 20), window.size - Vector2(28, 36)))
	backdrop.add_child(_glyph)
	var crest := art("crest.png", true)
	crest.name = "Crest"
	crest.window = window
	centre.add_child(crest)
	var wing := vec("wing")
	var left := piece(console, "WingLeft", 0.0, 0.0, wing)
	left.add_child(art("wing_left.png", true))
	var right := piece(console, "WingRight", 1.0, -wing.x, wing)
	right.add_child(art("wing_right.png", true))


func _build_notice() -> void:
	_notice = label("", BOLD_FONT, 16, NOTICE)
	_notice.name = "Notice"
	_notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_notice.anchor_left = 0.5
	_notice.anchor_right = 0.5
	_notice.anchor_top = 1.0
	_notice.anchor_bottom = 1.0
	var above := float(layout()["shoulder"]) + 6
	_notice.offset_left = -440
	_notice.offset_right = 440
	# (above the arch's crest, which rises past the shoulder: a long notice clears it)
	_notice.offset_top = -above - 94
	_notice.offset_bottom = -above - 70
	_notice.add_theme_constant_override("outline_size", 5)
	_notice.add_theme_color_override("font_outline_color", INK)
	_notice.visible = false
	_root.add_child(_notice)


# ── The console kit ──


static func layout() -> Dictionary:
	if _layout.is_empty():
		_layout = (load(ART + "layout.json") as JSON).data
	return _layout


## Texels of console art per layout pixel.
static func k() -> float:
	return float(layout().get("scale", 1))


static func rect(key: String) -> Rect2:
	var r: Array = layout()[key]
	return Rect2(r[0], r[1], r[2], r[3])


static func vec(key: String) -> Vector2:
	var v: Array = layout()[key]
	return Vector2(v[0], v[1])


static func place(control: Control, where: Rect2) -> void:
	control.position = where.position
	control.size = where.size


static func art(file: String, hit := false) -> ConsoleArt:
	return ConsoleArt.new(load(ART + file), k(), hit)


## A piece anchored to the bottom edge at anchor_x (0 left, 0.5 centre, 1 right), sized
## as the console piece it lies over.
static func piece(parent: Control, piece_name: String, anchor_x: float, left: float, size: Vector2) -> Control:
	var p := Control.new()
	p.name = piece_name
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.anchor_left = anchor_x
	p.anchor_right = anchor_x
	p.anchor_top = 1.0
	p.anchor_bottom = 1.0
	p.offset_left = left
	p.offset_right = left + size.x
	p.offset_top = -size.y
	p.offset_bottom = 0
	parent.add_child(p)
	return p


static func label(text: String, font: Font, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


## Small capitals for captions and headers ("PARTY", "KIT").
static func caps(text: String, size := 11, color := DIM) -> Label:
	if _caps == null:
		_caps = FontVariation.new()
		_caps.base_font = BOLD_FONT
		_caps.spacing_glyph = 1
	var l := label(text.to_upper(), _caps, size, color)
	l.add_theme_constant_override("outline_size", 0)
	return l


## The tooltip's bronze nine-slice: the plate every small panel stands on.
static func plate_box(margin := Vector4(12, 8, 12, 9), bright := false) -> StyleBox:
	var source: StyleBoxTexture = load(ART + "tooltip.tres")
	if bright:
		source = source.duplicate() as StyleBoxTexture
		source.modulate_color = Color(1.7, 1.4, 0.95)
	var box := HdStyleBox.new(source, k())
	box.content_margin_left = margin.x
	box.content_margin_top = margin.y
	box.content_margin_right = margin.z
	box.content_margin_bottom = margin.w
	return box


## A painted console piece's nine-slice (ui/console/<file>), drawn at the layout's scale.
static func piece_box(file: String) -> HdStyleBox:
	return HdStyleBox.new(load(ART + file), k())


## The screens' large panel (design 3.7): the bronze rim round stone that tile-fits, its
## shadow outside the control, layout.json's content margins. crown() seats its jewel.
static func panel_box() -> StyleBox:
	var box := piece_box("panel.tres")
	var m: Array = layout()["panel"]["content"]
	box.content_margin_left = m[0]
	box.content_margin_top = m[1]
	box.content_margin_right = m[2]
	box.content_margin_bottom = m[3]
	return box


## A card's frame (a loading card, a party member's), lit for my own.
static func card_box(lit := false) -> StyleBox:
	var box := piece_box("card_frame_lit.tres" if lit else "card_frame.tres")
	var m: Array = layout()["card_frame"]["content"]
	box.content_margin_left = m[0]
	box.content_margin_top = m[1]
	box.content_margin_right = m[2]
	box.content_margin_bottom = m[3]
	return box


## Seats the panel's jewel (panel_jewel.png) on the middle of `panel`'s top edge, as
## layout.json's panel_jewel says: drawn by the panel itself, over its rim, so a container
## never lays it out.
static func crown(panel: Control) -> void:
	var jewel: Texture2D = load(ART + "panel_jewel.png")
	var spec: Dictionary = layout()["panel_jewel"]
	var size := Vector2(spec["size"][0], spec["size"][1])
	var seat := Vector2(spec["seat"][0], spec["seat"][1])
	panel.set_meta(&"crown", jewel)
	panel.draw.connect(func() -> void:
		panel.draw_texture_rect(jewel, Rect2(Vector2(panel.size.x * 0.5, 0.0) - seat, size), false))


## The HUD's theme: bronze buttons, gold captions, dark outlines.
static func theme() -> Theme:
	var t := Theme.new()
	t.default_font = BODY_FONT
	t.default_font_size = 15
	t.set_color("font_color", "Label", TEXT)
	t.set_constant("outline_size", "Label", 4)
	t.set_color("font_outline_color", "Label", INK)
	for st: String in ["normal", "hover", "pressed", "disabled"]:
		t.set_stylebox(st, "Button", HdStyleBox.new(load(ART + "button_%s.tres" % st), k()))
	t.set_stylebox("hover_pressed", "Button", HdStyleBox.new(load(ART + "button_pressed.tres"), k()))
	t.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	t.set_font("font", "Button", BOLD_FONT)
	t.set_font_size("font_size", "Button", 15)
	t.set_color("font_color", "Button", GOLD)
	t.set_color("font_hover_color", "Button", Color("#fff1c8"))
	t.set_color("font_pressed_color", "Button", GOLD)
	t.set_color("font_disabled_color", "Button", Color("#76695a"))
	t.set_constant("outline_size", "Button", 4)
	t.set_color("font_outline_color", "Button", Color(0.04, 0.03, 0.02))
	# (the console's painted field, its focus lit; the divider for rules: layout.json)
	t.set_stylebox("normal", "LineEdit", piece_box("field.tres"))
	t.set_stylebox("read_only", "LineEdit", piece_box("field.tres"))
	t.set_stylebox("focus", "LineEdit", piece_box("field_focus.tres"))
	t.set_font("font", "LineEdit", BOLD_FONT)
	t.set_font_size("font_size", "LineEdit", 15)
	t.set_color("font_color", "LineEdit", TEXT)
	t.set_color("font_placeholder_color", "LineEdit", Color("#6f6455"))
	t.set_color("caret_color", "LineEdit", GOLD)
	var rule := piece_box("divider.tres")
	var half := float(layout()["divider"]["height"]) * 0.5
	rule.content_margin_top = half
	rule.content_margin_bottom = half
	t.set_stylebox("separator", "HSeparator", rule)
	t.set_constant("separation", "HSeparator", int(layout()["divider"]["height"]) + 4)
	t.set_stylebox("panel", "TooltipPanel", plate_box(Vector4(10, 6, 10, 7)))
	t.set_color("font_color", "TooltipLabel", TEXT)
	t.set_font("font", "TooltipLabel", BODY_FONT)
	t.set_font_size("font_size", "TooltipLabel", 13)
	return t


## A command socket of the card well holding words instead of an icon: the screens' modes
## and actions. The hotkey sits on the dark tab in its corner, as on the command card.
static func socket(socket_name: String, text: String, hotkey := "") -> Button:
	var button := Button.new()
	button.name = socket_name
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = vec("socket")
	button.size = vec("socket")
	for st: String in ["normal", "hover", "pressed", "disabled", "hover_pressed"]:
		var source: StyleBoxTexture = load(ART + "button_%s.tres" % ("pressed" if st == "hover_pressed" else st))
		button.add_theme_stylebox_override(st, HdStyleBox.new(source, k()))
	var ring := Panel.new()
	ring.name = "Ring"
	ring.add_theme_stylebox_override("panel", HdStyleBox.new(load(ART + "card_glow.tres"), k()))
	ring.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ring.visible = false
	button.add_child(ring)
	# The words sit in their own label below the key tab, a word to a line, as large as
	# the socket allows.
	var words := label("", BOLD_FONT, 12, GOLD)
	words.name = "Words"
	words.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	words.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	words.add_theme_constant_override("outline_size", 3)
	words.add_theme_constant_override("line_spacing", -3)
	words.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	words.offset_top = 13 if hotkey != "" else 3
	words.offset_bottom = -3
	button.add_child(words)
	button.draw.connect(_tint_words.bind(button, words))
	if hotkey != "":
		_key_tab(button, hotkey)
	set_words(button, text)
	return button


## A word socket's words: one word to a line, shrunk until the longest fits.
static func set_words(button: Button, text: String, font: Font = BOLD_FONT, largest := 13) -> void:
	var words := button.get_node("Words") as Label
	var lines := text.replace(" ", "\n")
	if words.text == lines and words.get_theme_font("font") == font and int(words.get_meta("largest", 0)) == largest:
		return
	words.text = lines
	words.add_theme_font_override("font", font)
	words.set_meta("largest", largest)
	var room := vec("socket").x - 6
	var size := largest
	while size > 9:
		var widest := 0.0
		for line in lines.split("\n"):
			widest = maxf(widest, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
		if widest <= room:
			break
		size -= 1
	words.add_theme_font_size_override("font_size", size)


## A word socket's words as one line ("High Water").
static func words_of(button: Button) -> String:
	return (button.get_node("Words") as Label).text.replace("\n", " ")


static func _tint_words(button: Button, words: Label) -> void:
	var mode := button.get_draw_mode()
	var color := GOLD
	if button.disabled:
		color = Color("#76695a")
	elif mode == BaseButton.DRAW_HOVER:
		color = Color("#fff1c8")
	words.add_theme_color_override("font_color", color)


## A socket holding an icon (a tower of the kit).
static func icon_socket(socket_name: String, texture: Texture2D, hotkey := "") -> Button:
	var button := Button.new()
	button.name = socket_name
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = vec("socket")
	button.size = vec("socket")
	var glow := HdStyleBox.new(load(ART + "card_glow.tres"), k())
	for st: String in ["normal", "disabled", "focus"]:
		button.add_theme_stylebox_override(st, StyleBoxEmpty.new())
	for st: String in ["hover", "pressed", "hover_pressed"]:
		button.add_theme_stylebox_override(st, glow)
	var picture := TextureRect.new()
	picture.name = "Icon"
	picture.texture = texture
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_SCALE
	picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(picture)
	if hotkey != "":
		_key_tab(button, hotkey)
	return button


static func _key_tab(button: Button, hotkey: String) -> void:
	var tab := Panel.new()
	tab.name = "KeyTab"
	var tab_box := StyleBoxFlat.new()
	tab_box.bg_color = Color(0, 0, 0, 0.7)
	tab_box.set_corner_radius_all(3)
	tab.add_theme_stylebox_override("panel", tab_box)
	tab.position = Vector2(2, 2)
	tab.size = Vector2(maxf(14, 7 * hotkey.length() + 6), 14)
	tab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(tab)
	var key := label(hotkey, BOLD_FONT, 10, KEY)
	key.name = "Hotkey"
	key.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	key.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	key.add_theme_constant_override("outline_size", 0)
	key.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tab.add_child(key)


## Lights a socket's ring (the mode chosen, the main Builder).
static func set_lit(button: Button, lit: bool) -> void:
	(button.get_node("Ring") as Control).visible = lit


## The six sockets of a card well, top row then bottom row, as the command card lays them.
static func lay_card(card: Control, buttons: Array) -> void:
	var step := vec("socket") + vec("gap")
	for i in buttons.size():
		var b: Control = buttons[i]
		b.position = Vector2(i % 3, i / 3) * step
		card.add_child(b)


## A thin gilt rule with its gem, under a title (the banner's pieces).
static func gilt_rule(width := 260.0) -> Control:
	var holder := Control.new()
	holder.name = "GiltRule"
	holder.custom_minimum_size = Vector2(width, 10)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	# (the painter paints the rule's left half; the right is it mirrored)
	for flip: bool in [false, true]:
		var line := TextureRect.new()
		line.texture = load(ART + "banner_rule.png")
		line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		line.stretch_mode = TextureRect.STRETCH_SCALE
		line.flip_h = flip
		line.anchor_left = 0.5 if flip else 0.0
		line.anchor_right = 1.0 if flip else 0.5
		line.anchor_bottom = 1.0
		line.offset_top = 3
		line.offset_bottom = -3
		line.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.add_child(line)
	var gem := TextureRect.new()
	gem.texture = load(ART + "banner_gem.png")
	gem.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	gem.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	gem.offset_left = -6
	gem.offset_right = 6
	gem.offset_top = -6
	gem.offset_bottom = 6
	gem.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(gem)
	return holder


## The end plate (plate.png) widened to any size: its rim caps and the crested centre keep
## their shape, the stone between them stretches.
class WidePlate:
	extends Control
	## Texels of plate.png: the rim caps end and begin at these columns, the stone the
	## plate widens with lies between SOURCE's columns (clear of the crest), the crest sits
	## between CREST's, and the top and bottom bands end and begin at these rows.
	const CAP_LEFT := 64
	const CAP_RIGHT := 856
	const SOURCE := [80, 340]
	const CREST := [360, 560]
	const TOP := 86
	const BOTTOM := 340
	var texture: Texture2D

	func _init() -> void:
		texture = load("res://ui/console/plate.png")
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _draw() -> void:
		var k := Shell.k()
		var tw := float(texture.get_width())
		var th := float(texture.get_height())
		var dx := [0.0, CAP_LEFT / k, size.x - (tw - CAP_RIGHT) / k, size.x]
		var sx := [[0.0, float(CAP_LEFT)], [float(SOURCE[0]), float(SOURCE[1])], [float(CAP_RIGHT), tw]]
		var dy := [0.0, TOP / k, maxf(TOP / k, size.y - (th - BOTTOM) / k), size.y]
		var sy := [[0.0, float(TOP)], [float(TOP), float(BOTTOM)], [float(BOTTOM), th]]
		for r in 3:
			for c in 3:
				var dst := Rect2(dx[c], dy[r], dx[c + 1] - dx[c], dy[r + 1] - dy[r])
				var from: Array = sx[c]
				var rows: Array = sy[r]
				var src := Rect2(from[0], rows[0], from[1] - from[0], rows[1] - rows[0])
				if dst.size.x > 0.0 and dst.size.y > 0.0:
					draw_texture_rect_region(texture, dst, src)
		# The crest and its gem, at their own size over the middle of the top band.
		var crest_w := (CREST[1] - CREST[0]) / k
		draw_texture_rect_region(
			texture,
			Rect2(size.x * 0.5 - crest_w * 0.5, 0.0, crest_w, TOP / k),
			Rect2(CREST[0], 0.0, CREST[1] - CREST[0], TOP)
		)


## Difficulty as one to three small gold stars, the rest dim.
class Stars:
	extends Control
	var count := 1

	func _init(stars := 1) -> void:
		count = stars
		custom_minimum_size = Vector2(44, 13)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		for i in 3:
			var c := Vector2(6.5 + i * 15, size.y * 0.5)
			var points := PackedVector2Array()
			for p in 10:
				var r := 6.0 if p % 2 == 0 else 2.6
				var a := -PI * 0.5 + p * PI / 5.0
				points.append(c + Vector2(cos(a), sin(a)) * r)
			draw_colored_polygon(points, Shell.GOLD if i < count else Color(0.4, 0.35, 0.28, 0.8))
