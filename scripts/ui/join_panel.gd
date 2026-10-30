## The Join panel (design 5.3), above the right wing, from Join (J). A party code (lower
## case, spaces and hyphens are fine; it joins as the fifth symbol lands), the official
## server online, servers heard on this network (Nearby, desktop only) and a typed server
## address: 192.168.1.20 becomes ws://192.168.1.20:8766/causeway, a name online
## wss://name/causeway (NetAddress, the address rule). Then Create a party here and Leave
## party. The browser cannot reach a LAN server, so it shows one line instead.
class_name JoinPanel
extends PanelContainer

const WEB_LINE := "LAN games need the desktop version. Friends on the web can join your party online."

var shell: Shell
## Whether this build may list and type LAN servers (desktop) or plays online only (web).
var lan := true
var _code: LineEdit
var _code_hint: Label
var _nearby_box: VBoxContainer
var _nearby: VBoxContainer
var _address: LineEdit
var _web_line: Label
var _leave: Button
var _shown_servers := []


func setup(owner: Shell) -> void:
	shell = owner
	name = "JoinPanel"
	lan = not OS.has_feature("web")
	add_theme_stylebox_override("panel", Shell.panel_box())
	Shell.crown(self)
	anchor_left = 1.0
	anchor_right = 1.0
	anchor_top = 1.0
	anchor_bottom = 1.0
	offset_left = -440
	offset_right = -14
	offset_bottom = -Shell.vec("wing").y + 6
	offset_top = offset_bottom
	grow_vertical = Control.GROW_DIRECTION_BEGIN
	visible = false
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	add_child(box)
	var head := HBoxContainer.new()
	box.add_child(head)
	var title := Shell.label("Join a party", Shell.TITLE_FONT, 18, Shell.GOLD)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(title)
	var close_button := _small("Close", close)
	close_button.name = "Close"
	head.add_child(close_button)
	var code_row := HBoxContainer.new()
	code_row.add_theme_constant_override("separation", 8)
	box.add_child(code_row)
	code_row.add_child(_v(Shell.caps("Code", 11)))
	_code = LineEdit.new()
	_code.name = "CodeField"
	_code.placeholder_text = "K7Q-4M"
	_code.custom_minimum_size = Vector2(110, 30)
	_code.max_length = 9
	_code.text_changed.connect(_on_code)
	_code.text_submitted.connect(func(_t: String) -> void: _on_code(_code.text))
	code_row.add_child(_code)
	_code_hint = _v(Shell.label("joins after 5 symbols", Shell.BODY_FONT, 12, Shell.DIM))
	_code_hint.name = "CodeHint"
	_code_hint.add_theme_constant_override("outline_size", 0)
	code_row.add_child(_code_hint)
	box.add_child(HSeparator.new())
	box.add_child(Shell.caps("Online", 11, Shell.GOLD))
	var official := HBoxContainer.new()
	official.add_theme_constant_override("separation", 10)
	box.add_child(official)
	official.add_child(_v(Shell.label("Official", Shell.BOLD_FONT, 14, Shell.TEXT)))
	var host := _v(Shell.label(Session.OFFICIAL, Shell.BODY_FONT, 13, Shell.DIM))
	host.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	host.add_theme_constant_override("outline_size", 0)
	official.add_child(host)
	var go_online := _small("Go", func() -> void: _go(Session.official_address))
	go_online.name = "GoOnline"
	official.add_child(go_online)
	box.add_child(HSeparator.new())
	_nearby_box = VBoxContainer.new()
	_nearby_box.name = "Nearby"
	_nearby_box.add_theme_constant_override("separation", 4)
	box.add_child(_nearby_box)
	var nearby_head := HBoxContainer.new()
	_nearby_box.add_child(nearby_head)
	var nearby_title := Shell.caps("Nearby (LAN)", 11, Shell.GOLD)
	nearby_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	nearby_head.add_child(nearby_title)
	nearby_head.add_child(Shell.caps("desktop only", 9))
	_nearby = VBoxContainer.new()
	_nearby.name = "NearbyList"
	_nearby.add_theme_constant_override("separation", 2)
	_nearby_box.add_child(_nearby)
	var address_row := HBoxContainer.new()
	address_row.add_theme_constant_override("separation", 8)
	_nearby_box.add_child(address_row)
	address_row.add_child(_v(Shell.label("Server address", Shell.BOLD_FONT, 13, Shell.TEXT)))
	_address = LineEdit.new()
	_address.name = "AddressField"
	_address.placeholder_text = "192.168.1.20"
	_address.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_address.custom_minimum_size.y = 30
	_address.text_submitted.connect(func(t: String) -> void: _go(t))
	address_row.add_child(_address)
	var go_address := _small("Go", func() -> void: _go(_address.text))
	go_address.name = "GoAddress"
	address_row.add_child(go_address)
	_web_line = Shell.label(WEB_LINE, Shell.BODY_FONT, 13, Shell.DIM)
	_web_line.name = "WebLine"
	_web_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_web_line.custom_minimum_size.x = 380
	_web_line.add_theme_constant_override("outline_size", 0)
	box.add_child(_web_line)
	box.add_child(HSeparator.new())
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 10)
	box.add_child(actions)
	var create := Button.new()
	create.name = "CreateParty"
	create.text = "Create a party here"
	create.focus_mode = Control.FOCUS_NONE
	create.add_theme_font_size_override("font_size", 13)
	create.custom_minimum_size = Vector2(0, 34)
	create.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	create.pressed.connect(Session.create_party)
	actions.add_child(create)
	_leave = Button.new()
	_leave.name = "LeaveParty"
	_leave.text = "Leave party"
	_leave.focus_mode = Control.FOCUS_NONE
	_leave.add_theme_font_size_override("font_size", 13)
	_leave.custom_minimum_size = Vector2(0, 34)
	_leave.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_leave.pressed.connect(Session.leave_party)
	actions.add_child(_leave)
	Session.beacon.changed.connect(refresh)
	set_lan(lan)


func _process(_delta: float) -> void:
	if visible and lan and Session.beacon.servers() != _shown_servers:
		refresh()


## Esc closes the panel, even while a field holds the keys.
func _input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if visible and key and key.pressed and not key.echo and key.keycode == KEY_ESCAPE:
		close()
		get_viewport().set_input_as_handled()


func open() -> void:
	visible = true
	if lan:
		Session.beacon.listen()
	refresh()
	_code.grab_focus()


func close() -> void:
	if visible:
		visible = false
		Session.beacon.stop()
		# (the hub's keys, B J Enter, are the hub's again)
		_code.release_focus()
		_address.release_focus()


func toggle() -> void:
	if visible:
		close()
	else:
		open()


## The desktop shows Nearby and the address field; the browser one line instead.
func set_lan(on: bool) -> void:
	lan = on
	_nearby_box.visible = on
	_web_line.visible = not on


func refresh() -> void:
	if _leave == null:
		return
	_leave.disabled = Session.where == "offline"
	_shown_servers = Session.beacon.servers()
	for child in _nearby.get_children():
		child.free()
	if _shown_servers.is_empty():
		var none := Shell.label("No server heard on this network", Shell.BODY_FONT, 12, Color("#6f6455"))
		none.add_theme_constant_override("outline_size", 0)
		_nearby.add_child(none)
	for s: Dictionary in _shown_servers:
		var row := HBoxContainer.new()
		row.name = "Server_" + str(s["join"]).replace(".", "_").replace(":", "_")
		row.add_theme_constant_override("separation", 10)
		var title := _v(Shell.label(str(s["name"]) if str(s["name"]) != "" else str(s["address"]), Shell.BOLD_FONT, 14, Shell.TEXT))
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(title)
		var parties := int(s["parties"])
		row.add_child(_v(Shell.label("%d %s" % [parties, "party" if parties == 1 else "parties"], Shell.BODY_FONT, 12, Shell.DIM)))
		row.add_child(_v(Shell.label(str(s["join"]), Shell.BODY_FONT, 12, Shell.DIM)))
		row.add_child(_small("Go", _go.bind(str(s["join"]))))
		_nearby.add_child(row)


## The Nearby rows as text, for tests: "Sascha's server 192.168.1.20".
func nearby_lines() -> Array[String]:
	var out: Array[String] = []
	for s: Dictionary in Session.beacon.servers():
		out.append("%s %s" % [s["name"], s["join"]])
	return out


## What a typed address connects to (the address rule), "" for none.
static func url_for(typed: String) -> String:
	return NetAddress.url(typed)


func _on_code(text: String) -> void:
	var code := Session.clean_code(text)
	var bad := ""
	for c in code:
		if not Session.CODE_SYMBOLS.contains(c):
			bad = c
	if bad != "":
		_code_hint.text = "No %s in a code: 2-9 and consonants" % bad
		_code_hint.add_theme_color_override("font_color", Shell.AMBER)
		return
	_code_hint.add_theme_color_override("font_color", Shell.DIM)
	if code.length() < Session.CODE_LENGTH:
		_code_hint.text = "joins after 5 symbols"
		return
	if code.length() > Session.CODE_LENGTH:
		_code_hint.text = "A code has 5 symbols"
		return
	_code_hint.text = "Joining %s ..." % Session.show_code(code)
	if Session.join_code(code):
		close()


func _go(address: String) -> void:
	if address.strip_edges() == "":
		return
	if Session.connect_to(address):
		close()


func _small(text: String, action: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(56, 30)
	b.add_theme_font_size_override("font_size", 13)
	b.pressed.connect(action)
	return b


func _v(l: Label) -> Label:
	l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return l
