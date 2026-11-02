## What a player sees at a glance, in words, for `godot-agent play` (project setting
## godot_agent/play_describe): the playtest harness prints it after every batch of input.
##
## One screen at a time, the one on top: the name prompt, the Join panel, the Builders
## screen or the hub; the loading screen or Match Found; in a match the menu, the results
## plate or the match itself. For each, its words and every control a player can click,
## with the centre of its rect in viewport pixels (`@x,y`, a picture's pixels in the
## harness's 1280 x 720 window) and, for a greyed one, why. In a
## match: the mode, the wave and its phase, gold, lives, the selection's plate, the card,
## the cursor's cell as the build ghost and the build grid show it, the towers and creeps on
## screen, what got through this wave, banners and notices, the party strip and the rival
## line, the waves to come while their list shows, and the duel's tray and bar where a build
## has them. In a duel the wave line says "build window" only while my window is open for
## both hollows, "waiting for the window" while mine has cleared and the rival's wave still
## runs, so a `wait until build window` waits for the window. (M8) The hub's level words and
## the match's level beside its mode, a wave's call for the next on the horn (two presses,
## the question between them, as for a press in a window's last moments), and a rival
## bottle's candidates.
##
## It reads the views' nodes and the Game facade, as the screen shows them: nothing a player
## cannot see (no cell numbers, no ids, no exact health, no hidden state). `watch` is the few
## lines a `wait N until TEXT` reads: what a player glances at to know when to act.
extends RefCounted

const HUB := "res://scenes/hub.tscn"
const MATCH := "res://scenes/main.tscn"
## How many of a kind the lists name at most.
const MAX_LISTED := 10
## A tile as it looks (the build grid, shown while placing, covers only plain grass).
const TILE_WORDS := {
	".": "grass",
	"#": "road",
	"S": "the Welling",
	"E": "the Holdfast",
	"^": "high ground",
	"T": "trees",
	"~": "water",
	",": "grass with flowers",
	"L": "a lamp post",
}
## The lines `watch` keeps, by how they begin: the screen, the wave's phase (a duel's Surge
## names its waves "Surge 2/3"), a banner, the end plate, the menu, the connection.
const WATCHED := [
	"screen:", "Wave ", "Surge ", "before wave", "banner:", "end plate:", "menu:", "connection:", "paused"
]


static func describe(tree: SceneTree) -> PackedStringArray:
	var out := PackedStringArray()
	var session := tree.root.get_node_or_null("Session")
	var loading: Node = session.get_node_or_null("LoadingScreen") if session else null
	var found: Node = session.get_node_or_null("MatchFound") if session else null
	var scene := tree.current_scene
	if found and found.get("visible"):
		_match_found(tree, found, out)
	elif loading and loading.get("visible"):
		_loading(tree, loading, out)
	elif scene and scene.scene_file_path == HUB:
		_hub(tree, scene, out)
	elif scene and scene.scene_file_path == MATCH:
		_match(tree, scene, out)
	else:
		out.append("screen: %s" % (scene.scene_file_path if scene else "(none)"))
		_buttons(tree, tree.root, "buttons", out)
	_popup_tip(tree, out)
	return out


## What a player glances at to know when to act, for the harness's `wait N until TEXT`: the
## screen's line, the wave and its phase, a banner, the end plate, the menu. Words under the
## pointer, in a tooltip or a notice ("the next build window") never end a wait.
static func watch(tree: SceneTree) -> PackedStringArray:
	var out := PackedStringArray()
	for line in describe(tree):
		for start: String in WATCHED:
			if line.begins_with(start):
				out.append(line)
				break
	return out


# ── The hub's screens ──


static func _hub(tree: SceneTree, scene: Node, out: PackedStringArray) -> void:
	var shell := scene.find_child("Shell", true, false)
	if shell == null:
		shell = scene
	var prompt := shell.find_child("NamePrompt", true, false) as Control
	var join := shell.find_child("JoinPanel", true, false) as Control
	var builders := shell.find_child("BuildersScreen", true, false) as Control
	var hub := shell.find_child("HubPanel", true, false) as Control
	if prompt and prompt.is_visible_in_tree():
		out.append("screen: name prompt · %s" % _texts(prompt.find_child("Plate", true, false), 1)[0])
		var field := prompt.find_child("NameField", true, false) as LineEdit
		out.append(
			"name field @%s: '%s'%s" % [_at(tree, field), field.text, " (typing goes here)" if field.has_focus() else ""]
		)
		out.append("hint: %s" % _text(prompt.find_child("NameHint", true, false)))
		_buttons(tree, prompt, "buttons", out)
		out.append("Enter takes the name")
		return
	if builders and builders.is_visible_in_tree():
		_builders(tree, builders, out)
	elif hub:
		_hub_panel(tree, hub, out)
	else:
		out.append("screen: hub")
	if join and join.is_visible_in_tree():
		_join(tree, join, out)
	var notice := shell.find_child("Notice", false, false) as Label
	if notice == null:
		notice = shell.find_child("Notice", true, false) as Label
	if _showing(notice):
		out.append("notice: %s" % notice.text)
	if shell.has_method("pill_text") and str(shell.call("pill_text")) != "":
		out.append("queue: %s" % shell.call("pill_text"))


static func _hub_panel(tree: SceneTree, hub: Control, out: PackedStringArray) -> void:
	var place := _text(hub.find_child("Place", true, false))
	var code := hub.find_child("CodeBox", true, false) as Control
	var where := place
	if code and code.is_visible_in_tree():
		where += " · party " + _text(code.find_child("Code", true, false))
	out.append("screen: hub · %s" % where)
	out.append("party %s: %s" % [_text(hub.find_child("PartyCount", true, false)), " | ".join(_party_rows(hub))])
	var invites := []
	for i in 4:
		var invite := hub.find_child("Member%d" % (i + 1), true, false)
		var button: Control = invite.find_child("Invite", false, false) if invite else null
		if button and button.is_visible_in_tree():
			invites.append("%s @%s" % [(button as Button).text, _at(tree, button)])
	if not invites.is_empty():
		out.append("open rows: %s" % " | ".join(invites))
	var open := hub.find_child("OpenSeats", true, false) as Button
	if open and open.is_visible_in_tree():
		out.append("%s @%s%s" % [open.text, _at(tree, open), " (greyed)" if open.disabled else ""])
	var arch := hub.find_child("Arch", true, false)
	if arch:
		out.append(
			"your Builder: %s · %s%s"
			% [_text(arch.find_child("Title", true, false)), _text(arch.find_child("Subtitle", true, false)), _stars(arch)]
		)
		out.append("team covers: %s" % _coverage(arch))
		out.append("mode: %s" % _text(arch.find_child("ModeLine", true, false)))
		_levels(tree, arch, out)
	var modes := []
	for id: String in Profile.HUB_MODES:
		var button := hub.find_child("Mode_" + id, true, false) as Button
		if button == null:
			continue
		var words := Shell.words_of(button)
		var lit := (button.get_node("Ring") as Control).visible
		modes.append(
			"%s @%s%s" % [words, _at(tree, button), " (chosen)" if lit else (" (greyed: %s)" % button.tooltip_text if button.disabled else "")]
		)
	out.append("modes: " + " | ".join(modes))
	var card := []
	var builders := hub.find_child("Builders", true, false) as Button
	if builders:
		card.append("Builders [B] @%s" % _at(tree, builders))
	var join := hub.find_child("Join", true, false) as Button
	if join:
		card.append("Join [J] @%s" % _at(tree, join))
	var primary := hub.find_child("Primary", true, false) as Button
	if primary:
		card.append(
			"%s [Enter] @%s%s"
			% [Shell.words_of(primary), _at(tree, primary), " (greyed)" if primary.disabled else ""]
		)
	out.append("buttons: " + " | ".join(card))
	var line := _text(hub.find_child("PrimaryLine", true, false))
	if line != "":
		out.append("line: " + line)
	var second := hub.find_child("QueueCancel", true, false) as Button
	if second and second.is_visible_in_tree():
		out.append("%s @%s" % [second.text, _at(tree, second)])


## (M8) The level's three words beside the mode line, each where it is: the one lit
## "(chosen)", all greyed with why in a mode without levels, "(the leader picks)" where my
## click picks nothing (a member's), and "(kept while the party is out of forming)" for a
## leader whose party is queued or playing.
static func _levels(tree: SceneTree, arch: Node, out: PackedStringArray) -> void:
	var words := []
	for id: String in SimContent.DIFFICULTY_IDS:
		var button := arch.find_child("Level_" + id, true, false) as Button
		if button == null or not button.is_visible_in_tree():
			continue
		var said := "%s @%s" % [button.text, _at(tree, button)]
		if bool(button.get_meta("lit", false)):
			said += " (chosen)"
		words.append(said)
	if words.is_empty():
		return
	var hub := arch.get_parent()
	var why := ""
	if not Session.offers_difficulty(Session.mode_id()):
		why = " (greyed: %s)" % Game.DUEL_LEVEL
	elif hub and hub.find_child("Level_normal", true, false) and (hub.find_child("Level_normal", true, false) as Button).disabled:
		why = " (the leader picks)" if not Session.is_leader() else " (kept while the party is out of forming)"
	out.append("level: " + " | ".join(words) + why)


## The party well's rows as they look: the seat's mark, the name, the Builder's face (the
## arch and the Builders screen put names to the faces), the leader's crown, the Ready tick.
static func _party_rows(hub: Control) -> Array:
	var said := []
	for row: Dictionary in hub.get("_rows"):
		var invite := row["invite"] as Button
		if invite.visible:
			said.append(invite.text)
			continue
		var parts := PackedStringArray()
		if (row["team"] as Control).visible:
			parts.append("team " + (row["team"] as Label).text)
		parts.append("%s (%s mark)" % [(row["name"] as Label).text, row["shape"]])
		var builder := str(row["builder_id"])
		if SimContent.BUILDERS.has(builder):
			parts.append("%s's face" % str(SimContent.BUILDERS[builder]["title"]).trim_prefix("the "))
		if (row["crown"] as Control).visible:
			parts.append("leader's crown")
		if (row["tick"] as Control).visible:
			parts.append("Ready tick")
		if (row["state"] as Label).text != "":
			parts.append((row["state"] as Label).text)
		said.append(", ".join(parts))
	return said


static func _builders(tree: SceneTree, screen: Control, out: PackedStringArray) -> void:
	out.append("screen: Builders · Esc goes back")
	var roster := []
	var lines: Array = screen.call("roster_lines")
	for i in lines.size():
		var cell := screen.find_child("Cell%d" % (i + 1), true, false) as Button
		var id := str(lines[i]).get_slice(" ", 0)
		if cell == null or id == "":
			continue
		var selected := (cell.get_node("Ring") as Control).visible
		# (a cell shows a face and its role's caption; the arch names the one shown)
		var who := "%s %s" % [i + 1, _text(cell.get_node("Role"))]
		var notes := PackedStringArray()
		if (cell.get_node("MainPip") as Control).visible:
			notes.append("your main's pip")
		if (cell.get_node("BackupPip") as Control).visible:
			notes.append("your backup's pip")
		if selected:
			notes.append("shown")
		roster.append("%s @%s%s" % [who, _at(tree, cell), " (%s)" % ", ".join(notes) if not notes.is_empty() else ""])
	out.append("roster [1-4]: " + " | ".join(roster))
	var info := screen.find_child("Info", true, false)
	if info:
		var head := _texts(info, 2)
		out.append("shown: %s%s" % [" · ".join(head), _stars(info)])
		out.append("passive: %s" % _text(info.find_child("Passive", true, false)))
		var strong: Node = info.find_child("Strong", true, false)
		var weak: Node = info.find_child("Weak", true, false)
		out.append(
			"strong against: %s · weak against: %s"
			% [_check_names(strong.call("lit") if strong else []), _check_names(weak.call("dim") if weak else [])]
		)
	var kit := []
	var selected := str(screen.get("selected"))
	for slot in 3:
		var button := screen.find_child("Tower%d" % (slot + 1), true, false) as Button
		if button == null or not SimContent.BUILDERS.has(selected):
			continue
		var tower := SimContent.kit_tower(selected, slot)
		kit.append(
			"%s %s %d @%s"
			% [Game.CARD_KEYS[slot], Game.TOWERS[tower]["name"], int(SimContent.TOWERS[tower]["cost"]), _at(tree, button)]
		)
	out.append("kit (hover for the tower's card): " + " | ".join(kit))
	var card := []
	for button_name: String in ["SetMain", "SetBackup", "Try"]:
		var button := screen.find_child(button_name, true, false) as Button
		if button:
			var why := ""
			if button.disabled:
				why = " (greyed: %s)" % (button.tooltip_text if button_name == "Try" else "already")
			card.append("%s @%s%s" % [Shell.words_of(button), _at(tree, button), why])
	var back := screen.find_child("Back", true, false) as Button
	if back:
		card.append("%s @%s" % [_label(back), _at(tree, back)])
	out.append("buttons: " + " | ".join(card))
	var plate := screen.find_child("Kit", true, false)
	if plate and (plate as Control).is_visible_in_tree() and SimContent.BUILDERS.has(selected):
		for slot in 3:
			var tower := SimContent.kit_tower(selected, slot)
			var branches := []
			for b in 2:
				var form := str(SimContent.BUILDERS[selected]["branches"][slot][b])
				var helps := SimContent.branch_helps(selected, form)
				branches.append(
					"%s %s +%d %s%s"
					% [
						Game.FORK_MARK,
						Game.TOWERS[form]["name"],
						int(SimContent.TOWERS[tower]["fork_cost"]),
						Game.TOWERS[form]["gain"],
						(" (%s glyph)" % Game.CHECKS[helps]["name"]) if helps != "" else ""
					]
				)
			out.append(
				"kit plate: %s %d %s"
				% [Game.TOWERS[tower]["name"], int(SimContent.TOWERS[tower]["cost"]), " ".join(branches)]
			)
	var tip := screen.find_child("TowerTip", true, false) as Control
	if tip and tip.is_visible_in_tree():
		out.append("tower card: " + " ".join(_texts(tip, 6)))


static func _join(tree: SceneTree, panel: Control, out: PackedStringArray) -> void:
	out.append("Join panel open (Esc closes)")
	for field_name: String in ["CodeField", "AddressField"]:
		var field := panel.find_child(field_name, true, false) as LineEdit
		if field and field.is_visible_in_tree():
			out.append(
				"%s @%s: '%s'%s%s"
				% [
					"party code" if field_name == "CodeField" else "server address",
					_at(tree, field),
					field.text,
					" (placeholder: %s)" % field.placeholder_text if field.text == "" and field.placeholder_text != "" else "",
					" (typing goes here)" if field.has_focus() else ""
				]
			)
	for label_name: String in ["CodeHint", "OfficialHost", "WebLine"]:
		var label := panel.find_child(label_name, true, false) as Label
		if _showing(label):
			out.append("%s: %s" % [label_name.to_snake_case().replace("_", " "), label.text])
	if panel.has_method("nearby_lines"):
		var near: Array = panel.call("nearby_lines")
		if not near.is_empty():
			out.append("nearby: " + " | ".join(near))
	_buttons(tree, panel, "join buttons", out)


static func _loading(tree: SceneTree, loading: Node, out: PackedStringArray) -> void:
	out.append("screen: loading · %s" % _text(loading.find_child("LoadingTitle", true, false)))
	if loading.has_method("card_lines"):
		out.append("cards: " + " | ".join(loading.call("card_lines")))
	if loading.has_method("line_text") and str(loading.call("line_text")) != "":
		out.append("line: " + str(loading.call("line_text")))
	_buttons(tree, loading, "buttons", out)


static func _match_found(tree: SceneTree, found: Node, out: PackedStringArray) -> void:
	out.append("screen: Match Found · Enter accepts, Esc declines")
	if found.has_method("lines"):
		var lines: Array = found.call("lines")
		out.append(" · ".join(lines.filter(func(l: Variant) -> bool: return str(l) != "")))
	_buttons(tree, found, "buttons", out)


# ── A match ──


static func _match(tree: SceneTree, scene: Node, out: PackedStringArray) -> void:
	var hud := scene.get_node_or_null("Hud")
	var results := scene.find_child("ResultsPanel", false, false)
	var menu: Node = scene.get("_menu")
	if results and results.get("visible") != false:
		_results(tree, results, out)
		return
	var sim: SimMatch = Game.sim
	var shown_mode := Profile.mode_name(str(Session.match_spec.get("shown_mode", sim.mode if sim else "")))
	# (M8: the level where it is not Normal, as the screens name it: "High Water · Hard")
	shown_mode = Game.mode_words(shown_mode, Game.level())
	var map_name := str((scene.get_script() as Script).get_script_constant_map().get("MAP_NAME", ""))
	var where := "offline" if scene.get("client") == null else "online"
	out.append("screen: match · %s on %s · %s" % [shown_mode, map_name, where])
	if menu and menu.get("visible"):
		# (a question, "Leave the match?", where this build asks one: Esc there is Stay)
		var asking := menu.has_method("asking") and str(menu.call("asking")) != ""
		out.append(
			"menu: %s · %s (%s)"
			% [
				_text(menu.find_child("MenuTitle", true, false)),
				_text(menu.find_child("MenuLine", true, false)),
				"Esc stays" if asking else "Esc closes"
			]
		)
		_buttons(tree, menu, "menu buttons", out)
		return
	if hud == null or sim == null:
		_buttons(tree, scene, "buttons", out)
		return
	var end := hud.find_child("EndPanel", true, false) as Control
	if end and end.is_visible_in_tree():
		out.append("end plate: " + " · ".join(_texts(end, 3)))
		_buttons(tree, end, "buttons", out)
		return
	var overlay := scene.find_child("ConnectionLayer", false, false)
	var plate: Node = overlay.get_child(0) if overlay and overlay.get_child_count() > 0 else null
	if plate and (plate as Control).is_visible_in_tree() and plate.has_method("lines"):
		var said: Array = plate.call("lines")
		if str(said[0]) != "":
			out.append("connection: %s" % " · ".join(said.filter(func(l: Variant) -> bool: return str(l) != "")))
	var wave_label := hud.find_child("Wave", true, false) as Label
	var countdown := _text(hud.find_child("Countdown", true, false)).trim_prefix("· ")
	var phase := "wave running" if Game.state == Game.State.WAVE else "build window"
	if Game.state == Game.State.PREP and Game.duel_wave():
		# (a duel's one clock: my hollow has cleared and the window opens once the rival's has
		# too; no build window yet, as the strip and the tray say, so `until build window` waits)
		phase = "waiting for the window"
	if Game.over():
		phase = "over"
	var phase_line := PackedStringArray([wave_label.text if wave_label.visible else "before wave 1", phase])
	if countdown != "":
		phase_line.append(countdown)
	out.append(" · ".join(phase_line))
	var checks: Array = hud.call("checks_shown")
	if not checks.is_empty():
		var said := []
		for pair: Array in checks:
			var creep := str(Game.CREEPS[pair[1]]["name"])
			said.append("%s (%s)" % [creep, "boss" if pair[0] == "boss" else Game.CHECKS[pair[0]]["name"]])
		out.append(("this wave: " if Game.state == Game.State.WAVE else "next wave: ") + ", ".join(said))
	out.append(
		"gold %s · lives %s/%d · you: %s, %s"
		% [
			_text(hud.find_child("Gold", true, false)),
			_text(hud.find_child("Lives", true, false)),
			Game.max_lives(),
			Game.seat_name(Game.seat),
			SimContent.BUILDERS[Game.builder()]["title"]
		]
	)
	var strip := hud.find_child("PartyStrip", true, false) as Control
	if strip and strip.is_visible_in_tree() and strip.has_method("lines"):
		out.append("party: " + " | ".join(strip.call("lines")))
	if str(hud.call("rival_line")) != "":
		out.append(str(hud.call("rival_line")))
	_duel(tree, hud, out)
	_info(hud, out)
	_card(tree, scene, hud, out)
	_cursor(tree, scene, out)
	_board(tree, scene, out)
	var banner := hud.find_child("Banner", true, false) as Control
	var title := hud.find_child("BannerTitle", true, false) as Label
	if banner and banner.is_visible_in_tree() and banner.modulate.a > 0.05 and title and title.text != "":
		out.append("banner: %s" % title.text)
	var notice := hud.find_child("Notice", true, false) as Label
	if _showing(notice):
		out.append("notice: %s" % notice.text)
	var tip := hud.find_child("Tooltip", true, false) as Control
	if tip and tip.is_visible_in_tree():
		out.append("card tip: " + " ".join(_texts(tip, 6)))
	var list := hud.find_child("WaveList", true, false)
	if list and (list as Control).is_visible_in_tree():
		out.append("waves to come (hovering the wave): " + " | ".join(_wave_rows(list)))
	var minimap := hud.find_child("Minimap", true, false) as Control
	if minimap:
		out.append("minimap @%s (click to look there)" % _at(tree, minimap))
	if scene.has_method("paused") and scene.call("paused"):
		out.append("paused")


## The wave list's rows as drawn: the wave (a duel's Surge's "S1", under the Surge's own
## line), its checks' glyphs, each creep's face and count ("boss" for a boss) with its health
## and armour where this build shows them, "wave 9 again" on a Surge's, and "now" on each
## wave on the road (M8: two or three when stacked).
static func _wave_rows(list: Node) -> Array:
	var said := []
	var rows := list.find_child("WaveRows", true, false)
	if rows == null:
		return said
	for row in rows.get_children():
		if row is Label:
			said.append((row as Label).text)  # (the Surge's line)
			continue
		var number := str(row.name).trim_prefix("WaveRow").to_int()
		if number <= 0:
			continue
		var index := Game.content_wave(number) - 1
		var checks := []
		for pair: Array in Game.wave_checks(index):
			checks.append(str(Game.CHECKS[pair[0]]["name"]))
		var creeps := []
		for group: Dictionary in Game.wave_groups(index):
			var boss := bool(SimContent.CREEPS[group["creep"]].get("boss", false))
			var creep := "%s %s" % [Game.CREEPS[group["creep"]]["name"], "boss" if boss else "×%d" % int(group["count"])]
			var numbers := row.get_node_or_null("Numbers_%s" % group["creep"]) as Label
			if numbers:
				creep += " " + numbers.text
			# (a boss's own checks' glyphs stand after it, where this build draws them)
			var own: Node = row.find_child("BossChecks_%s" % group["creep"], false, false)
			if boss and own and own.get_child_count() > 0:
				var names := []
				for glyph in own.get_children():
					names.append(str(Game.CHECKS[str(glyph.name).trim_prefix("BossCheck_")]["name"]))
				creep += " (%s)" % "/".join(names)
			creeps.append(creep)
		var again := row.get_node_or_null("Again") as Label
		var now := Game.state == Game.State.WAVE and (number == Game.wave or Game.waves_on_road().has(number))
		said.append(
			"%s %s: %s%s%s"
			% [
				(row.get_child(0) as Label).text,
				"/".join(checks) if not checks.is_empty() else "-",
				", ".join(creeps),
				(" · " + again.text) if again else "",
				" (now)" if now else ""
			]
		)
	return said


## The selection's plate in the console's middle: a tower, a creep, the tower being placed,
## or the Holdfast when nothing is selected.
static func _info(hud: Node, out: PackedStringArray) -> void:
	var info := hud.find_child("Info", true, false)
	if info == null:
		return
	var stats := info.find_child("Stats", true, false)
	var cells: Array = stats.get_meta("cells", []) if stats else []
	var said := PackedStringArray()
	for cell: Array in cells:
		said.append("%s %s" % [str(cell[0]).to_lower(), cell[1]])
	var line := _text(info.find_child("Subtitle", true, false))
	out.append(
		"plate: %s%s%s"
		% [
			_text(info.find_child("Title", true, false)),
			(" · " + line) if line != "" else "",
			(" · " + ", ".join(said)) if not said.is_empty() else ""
		]
	)


## The command card: Q W E, then A S D, each with its price, where it is, and why it is greyed.
static func _card(tree: SceneTree, scene: Node, hud: Node, out: PackedStringArray) -> void:
	var controller: BuildController = scene.get("controller")
	var slots: Array = hud.call("card")
	var rows := [[], []]
	for i in slots.size():
		var slot: Dictionary = slots[i]
		var what := str(slot["what"])
		var button := hud.find_child(Hud.SLOT_NODES[i], true, false) as Control
		var words := str(slot["key"])
		if Game.TOWERS.has(what):
			words += " " + str(Game.TOWERS[what]["name"])
			if bool(slot["hammer"]):
				words += " (fork)"
		elif what in ["signal", "sell", "ready"]:
			words += " " + what.capitalize()
		else:
			words += " empty"
		if str(slot["cost"]) != "":
			words += " " + str(slot["cost"])
		words += " @" + _at(tree, button)
		match str(slot["state"]):
			"poor":
				words += " (greyed: not enough gold)"
			"idle":
				if what != "":
					words += " (greyed: %s)" % _idle_why(i, what, controller)
			"lit":
				words += " (lit: the branch this tower took)"
		if bool(slot["active"]) and str(slot["state"]) != "lit":
			var ready_words := "you are Ready"
			if Game.state == Game.State.WAVE:
				ready_words = "you called %s" % Game.wave_name(Game.called_wave()).to_lower()
			words += " (lit: %s)" % {"ready": ready_words, "signal": "signalling: click where"}.get(what, "placing it")
		elif what == "ready" and str(slot["state"]) == "ok" and Game.state == Game.State.WAVE:
			# (M8: in a wave the horn calls the next, which sets out at once, by two presses)
			words += " (calls %s now: press twice)" % Game.wave_name(Game.called_wave()).to_lower()
			if controller.call_armed():
				words += " (asking: press again)"
		elif what == "ready" and str(slot["state"]) == "ok" and Game.late_in_window():
			# (M8: in a window's last moments a press may land after the horn: two presses)
			words += " (the horn is about to sound: press twice to call %s)" % Game.wave_name(Game.wave + 2).to_lower()
			if controller.call_armed():
				words += " (asking: press again)"
		rows[i / 3].append(words)
	out.append("card: " + " | ".join(rows[0]))
	out.append("card: " + " | ".join(rows[1]))


static func _idle_why(slot: int, what: String, controller: BuildController) -> String:
	if Game.over():
		return "the match is over"
	if Game.order_refusal() != "":
		return Game.order_refusal()
	match what:
		"sell":
			if controller.selected and is_instance_valid(controller.selected):
				return "a teammate's tower"
			return "select a tower of yours"
		"ready":
			if Game.state == Game.State.WAVE:
				# (M8: why no call can stack, in the screen's words)
				return Game.stack_refusal().to_lower() if Game.stack_refusal() != "" else "a wave is running"
			if Game.has_method("ready_refusal") and Game.ready_refusal() != "":
				return Game.ready_refusal().to_lower()  # (a duel's window not open for both yet)
			return "no wave left"
	if slot < 3 and controller.my_tower_selected():
		if controller.selected.branch >= 0:
			return "a fork is final"
		if controller.fork_pending(controller.selected.board_cell):
			return "a fork is on its way"
	return "not now"


## The cursor's cell as the screen shows it: what lies there, and while placing a tower the
## ghost's colour (green: it can stand there; red: it cannot) and whether the build grid,
## which shows while placing, covers the cell. Other cells a player reads off the grid in the
## picture, as a player scans it.
static func _cursor(tree: SceneTree, scene: Node, out: PackedStringArray) -> void:
	var controller: BuildController = scene.get("controller")
	if not Engine.has_meta("godot_agent_pointer"):
		return  # (the harness says where the pointer stands; before its first move, nowhere)
	var pointer: Variant = Engine.get_meta("godot_agent_pointer")
	var board: HollowMap = scene.get("board")
	var cell := controller.hover_cell
	if not pointer is Vector2 or board == null:
		return
	var at := "%d,%d" % [roundi(pointer.x), roundi(pointer.y)]
	var hovered := tree.root.gui_get_hovered_control()
	if hovered:
		out.append("cursor %s: over %s" % [at, _hover_words(hovered)])
		return
	if not board.inside(cell):
		# (the board takes the pointer from its moves: one that has not moved since the match
		# began is nowhere for it yet)
		out.append("cursor %s: %s" % [at, "off the board" if controller.hover_cell != Vector2i(-1, -1) else "not moved since the match began"])
		return
	var there := str(TILE_WORDS.get(board.tile(cell), "ground"))
	var tower: Tower = scene.call("tower_on", cell)
	if tower:
		there = _tower_words(tower)
	if controller.mode != "":
		var ok := controller.can_build(controller.mode, cell)
		if tower == null:
			# (the grid covers plain grass, and in a race only my own hollow's)
			var gridded := board.buildable(cell) and not controller.on_rival_hollow(cell)
			there += " in the build grid" if gridded else ", no build grid there"
		out.append(
			"placing %s: cursor %s over %s, ghost %s"
			% [Game.TOWERS[controller.mode]["name"], at, there, "green (it can stand here)" if ok else "red (it cannot stand here)"]
		)
	elif controller.signaling:
		out.append("signalling: cursor %s over %s (click to signal there)" % [at, there])
	else:
		out.append("cursor %s: over %s" % [at, there])


## What the hovered control is to a player: the button it belongs to, a part of the HUD,
## what its tooltip calls it, else the console (its frame and ornaments are not named).
static func _hover_words(hovered: Control) -> String:
	var n: Node = hovered
	while n != null:
		var duel := _duel_part(n)
		if duel != "":
			return duel
		if n is BaseButton:
			return "the %s button" % _label(n as Control)
		if n.name in ["Minimap", "TopBar", "WaveArea", "PartyStrip"]:
			return {"Minimap": "the minimap", "TopBar": "the strip", "WaveArea": "the wave (its list shows)", "PartyStrip": "the party strip"}[str(n.name)]
		n = n.get_parent()
	if hovered.tooltip_text != "":
		return hovered.tooltip_text.get_slice(":", 0).get_slice(".", 0)
	return "the console"


## A part of a duel's tray or bar as a player names it ("" for anything else): a pack of the
## Drift by its key and name, my bottle, the rival's, a side's Seawall, (M8) the rival's
## corked bottles at the end of its Seawall's cell.
static func _duel_part(n: Node) -> String:
	var parent := n.get_parent()
	if parent == null:
		return ""
	var where := str(n.name)
	if where == "Corked" and n.find_parent("DuelBar"):
		return "your rival's corked bottles on the duel bar"
	if where in ["Seawall0", "SeawallHead"] and n.find_parent("DuelBar"):
		return "your Seawall on the duel bar"
	if where == "Seawall1" and n.find_parent("DuelBar"):
		return "your rival's Seawall on the duel bar"
	if not n.find_parent("DriftTray"):
		return ""
	if where.begins_with("Pack") and n.has_meta("check"):
		var check := str(n.get_meta("check"))
		var key := where.trim_prefix("Pack")
		return "the Drift's pack %s%s" % [key, (" (%s)" % Game.pack_info(check, 0)["name"]) if check != "" else ", empty"]
	if where.begins_with("Mine"):
		return "your bottle %s" % where.trim_prefix("Mine")
	if where.begins_with("Rival") and where.length() == 6:
		return "your rival's bottle %s" % where.trim_prefix("Rival")
	return ""


## The Welling and the Holdfast, the towers and the creeps on screen, where they stand.
static func _board(tree: SceneTree, scene: Node, out: PackedStringArray) -> void:
	var camera := tree.root.get_camera_3d()
	if camera == null:
		return
	var view := Rect2(Vector2.ZERO, tree.root.get_visible_rect().size)
	# The road's two ends on each hollow (a race has two: yours and the rival's).
	var ends := []
	for h in Game.hollow_count():
		var whose := "" if Game.hollow_count() == 1 else ("your " if h == Game.my_hollow() else "the rival's ")
		var marks := []
		for mark: String in ["Welling", "Holdfast"]:
			var node := scene.get_node_or_null(mark + ("" if h == 0 else "_%d" % h)) as Node3D
			if node == null:
				continue
			var p := camera.unproject_position(node.global_position)
			var shown := not camera.is_position_behind(node.global_position) and view.has_point(p)
			marks.append("%s %s" % [mark, ("@%d,%d" % [roundi(p.x), roundi(p.y)]) if shown else "off screen"])
		if not marks.is_empty():
			ends.append("%sroad from the %s" % [whose, " to the ".join(marks)])
	if not ends.is_empty():
		var said := " · ".join(ends)
		out.append(said[0].to_upper() + said.substr(1))
	var mine := []
	var others := 0
	var views: Dictionary = scene.get("tower_views")
	var ids := views.keys()
	ids.sort()
	for id: int in ids:
		var tower: Tower = views[id]
		var p := camera.unproject_position(tower.global_position)
		if not view.has_point(p):
			continue
		if tower.owner_seat == Game.seat:
			mine.append("%s @%d,%d" % [Game.TOWERS[tower.form]["name"], roundi(p.x), roundi(p.y)])
		else:
			others += 1
	if not mine.is_empty() or others > 0:
		var listed := mine.slice(0, MAX_LISTED)
		if mine.size() > MAX_LISTED:
			listed.append("and %d more" % (mine.size() - MAX_LISTED))
		out.append(
			"your towers: %s%s"
			% [", ".join(listed) if not listed.is_empty() else "none on screen", (" · others' towers: %d" % others) if others > 0 else ""]
		)
	var creeps := {}
	var lead: Creep = null
	for node in tree.get_nodes_in_group("creeps"):
		var creep := node as Creep
		if creep == null or creep.dead or not view.has_point(camera.unproject_position(creep.aim_point())):
			continue
		var creep_name := str(Game.CREEPS[creep.kind]["name"])
		creeps[creep_name] = int(creeps.get(creep_name, 0)) + 1
		if lead == null or creep.distance > lead.distance:
			lead = creep
	if lead:
		var counts := []
		var names := creeps.keys()
		names.sort()
		for creep_name: String in names:
			counts.append("%d %s" % [creeps[creep_name], creep_name])
		var p := camera.unproject_position(lead.aim_point())
		out.append(
			"creeps on screen: %s · the furthest along: %s @%d,%d, %s"
			% [", ".join(counts), Game.CREEPS[lead.kind]["name"], roundi(p.x), roundi(p.y), _bar_words(lead)]
		)
	_got_through(scene, out)


## A creep's health as its bar shows it: hidden while unhurt, else about how full.
static func _bar_words(creep: Creep) -> String:
	var fill := creep.bar_shown()
	if fill < 0.0:
		return "unhurt (no health bar)"
	var tenths := roundi(fill * 10.0)
	return "its health bar almost empty" if tenths == 0 else "its health bar about %d%% full" % (tenths * 10)


## What reached the Holdfast in the waves the strip speaks of, as a player saw it walk in: the
## creeps and the lives they cost, of every wave on the road (M8: "got through waves 6–7"
## with two stacked), or in a window of the wave just cleared.
static func _got_through(scene: Node, out: PackedStringArray) -> void:
	if not scene.has_method("leaks_in") or Game.wave <= 0:
		return
	var on := Array(Game.waves_on_road()) if Game.state == Game.State.WAVE else []
	var waves := on if not on.is_empty() else [Game.wave]
	var kinds := {}
	var lives := 0
	for wave: int in waves:
		var leaks: Dictionary = scene.call("leaks_in", wave)
		if leaks.is_empty():
			continue
		for kind: String in leaks["kinds"]:
			kinds[kind] = int(kinds.get(kind, 0)) + int(leaks["kinds"][kind])
		lives += int(leaks["lives"])
	if kinds.is_empty():
		return
	var names := []
	for kind: String in kinds:
		var count := int(kinds[kind])
		# (plural as the plate says it: "Next: 18 Gourdlings")
		names.append("%d %s%s" % [count, Game.CREEPS[kind]["name"], "s" if count > 1 else ""])
	names.sort()
	var where := "in wave %d" % Game.wave
	if not on.is_empty():
		where = "this wave" if on.size() == 1 else Game.road_words().to_lower()
	out.append("got through %s: %s (-%d lives)" % [where, ", ".join(names), lives])


static func _tower_words(tower: Tower) -> String:
	var whose := "your" if tower.owner_seat == Game.seat else "%s's" % Game.seat_name(tower.owner_seat)
	return "%s %s" % [whose, Game.TOWERS[tower.form]["name"]]


## The duel's Drift tray and bar (Undertow), where this build has them, as they look: the
## bar's two rows (and the Seawall's plate while it is hovered); the tray's head (the tier
## and its price, "NEXT WINDOW" or "FROM WAVE 2") and its packs, each with its key, price,
## place and, greyed, the reason a cork would get; my bottles with the pack each holds and
## what its socket says; the rival's by tier.
static func _duel(tree: SceneTree, hud: Node, out: PackedStringArray) -> void:
	if hud.has_method("duel_bar"):
		var bar: Variant = hud.call("duel_bar")
		if bar is Control and (bar as Control).is_visible_in_tree():
			out.append("duel: " + " | ".join(bar.call("lines")))
			if bar.has_method("tip_shown"):
				var said: Array = bar.call("tip_shown")
				if str(said[0]) != "":
					out.append("duel tip: %s · %s" % [said[0], str(said[1]).replace("\n", " ")])
	if not hud.has_method("drift_tray"):
		return
	var tray: Variant = hud.call("drift_tray")
	if not tray is Control or not (tray as Control).is_visible_in_tree():
		return
	var head := _text((tray as Control).find_child("Tier", true, false))
	var price := _text((tray as Control).find_child("Price", true, false))
	if price != "":
		head += " %s gold" % price
	var packs := []
	var shown: Array = tray.call("packs_shown")
	for i in shown.size():
		var pack: Dictionary = shown[i]
		var button := (tray as Control).find_child("Pack%d" % (i + 1), true, false) as Control
		var state := str(pack.get("state", "ok"))
		var why := ""
		if state != "ok":
			# (the reason a cork gets now, as the pack's tip and the notice say it)
			why = " (greyed: %s)" % Game.cork_refusal(str(pack.get("check", ""))).to_lower()
		packs.append(
			"[%s] %s %s @%s%s" % [pack.get("key", ""), pack.get("name", ""), pack.get("price", ""), _at(tree, button), why]
		)
	if packs.is_empty():
		out.append("drift · %s: no packs to cork yet" % head)
	else:
		out.append("drift · %s (click or 1-3 to cork): %s" % [head, " | ".join(packs)])
	var bottles := []
	var mine: Array = tray.call("mine_shown")
	for i in mine.size():
		var bottle: Dictionary = mine[i]
		var button := (tray as Control).find_child("Mine%d" % (i + 1), true, false) as Control
		var check := str(bottle.get("pack", ""))
		# (its socket shows the pack's face: named here as the tray's tip names it)
		var holds := str(Game.pack_info(check, 0)["name"]) if check != "" else "a bottle"
		bottles.append(
			"%s %s @%s%s%s"
			% [
				holds,
				bottle.get("text", ""),
				_at(tree, button),
				" [Space]" if bottle.get("space", false) else "",
				" (lit)" if bottle.get("lit", false) else ""
			]
		)
	if not bottles.is_empty():
		out.append("your bottles: " + " | ".join(bottles))
	var rivals: Array = tray.call("rivals_shown")
	if not rivals.is_empty():
		# (M8: each with the packs it may hold, as the icons under it show them)
		var said := PackedStringArray()
		for r: Dictionary in rivals:
			said.append(_rival_words(r))
		out.append("rival's bottles: " + ", ".join(said))
	var tip: Array = tray.call("tip_shown")
	if str(tip[0]) != "":
		out.append("tray tip: %s · %s" % [tip[0], str(tip[1]).replace("\n", " ")])


## A rival's bottle as the tray shows it: "tier I (one of Gourd Rush, Scuttle or Thorn
## Herd)", its candidates by their packs' names (M8).
static func _rival_words(r: Dictionary) -> String:
	var names := PackedStringArray()
	for check: Variant in r.get("candidates", []):
		names.append(str(Game.pack_info(str(check), 0)["name"]))
	var said := "tier " + str(r.get("tier", ""))
	if names.size() == 1:
		return said + " (holds %s)" % names[0]
	if names.size() > 1:
		said += " (one of %s or %s)" % [", ".join(names.slice(0, names.size() - 1)), names[names.size() - 1]]
	return said


static func _results(tree: SceneTree, results: Node, out: PackedStringArray) -> void:
	out.append("screen: results · %s" % _text(results.find_child("ResultsTitle", true, false)))
	out.append(_text(results.find_child("ResultsDetail", true, false)))
	for label_name: String in ["ResultsSaid", "ResultsRule", "ResultsReport"]:
		var label := results.find_child(label_name, true, false) as Label
		if _showing(label):
			out.append(label.text)
	if results.has_method("team_lines"):
		for line: String in results.call("team_lines"):
			out.append("team: " + line)
	for child in results.find_children("*", "", true, false):
		if child is ResultsPanel.LivesLine and (child as Control).is_visible_in_tree():
			var whose := ""
			if child.name == "TeamLivesLine":
				whose = " (%s)" % _text(child.get_parent().find_child("TeamName", false, false)).to_lower()
			out.append("lives line%s: %s" % [whose, _lives_words(child as ResultsPanel.LivesLine)])
	var rows := results.find_child("Rows", true, false)
	if rows:
		for row in rows.get_children():
			var cells := _texts(row, 12)
			if row is HBoxContainer and cells[0] != "":
				out.append(("columns: " if row.name == "Header" else "row: ") + " | ".join(cells))
	_buttons(tree, results, "buttons", out)


## The results' line of lives along the waves, as it reads: where it falls, where it ends.
static func _lives_words(line: ResultsPanel.LivesLine) -> String:
	if line.values.is_empty():
		return "empty"
	var falls := []
	var before := line.top
	for i in line.values.size():
		if int(line.values[i]) < before:
			falls.append(str(i + 1))
		before = int(line.values[i])
	var shape := "level all the way" if falls.is_empty() else "falls on wave%s %s" % ["s" if falls.size() > 1 else "", ", ".join(falls)]
	return "%s, %d waves, ends at %d of %d" % [shape, line.values.size(), int(line.values[-1]), line.top]


# ── Pieces ──


## Every clickable control under `root` a player sees: its words and where it is.
static func _buttons(tree: SceneTree, root: Node, caption: String, out: PackedStringArray) -> void:
	var found: Array[Control] = []
	_collect(root, found)
	var said := []
	var view := Rect2(Vector2.ZERO, tree.root.get_visible_rect().size)
	for control in found:
		var p := control.get_global_transform_with_canvas() * (control.size * 0.5)
		if not view.has_point(p):
			continue
		var disabled := control is BaseButton and (control as BaseButton).disabled
		said.append("%s @%s%s" % [_label(control), _at(tree, control), " (greyed)" if disabled else ""])
	if not said.is_empty():
		out.append("%s: %s" % [caption, " | ".join(said)])


static func _collect(n: Node, out: Array[Control]) -> void:
	if n is CanvasItem and not (n as CanvasItem).is_visible_in_tree():
		return
	if n is CanvasLayer and not (n as CanvasLayer).visible:
		return
	if n is BaseButton:
		out.append(n as Control)
		return
	for child in n.get_children():
		_collect(child, out)


## A control's words: a socket's, a button's text, else the first clause of its tooltip.
static func _label(control: Control) -> String:
	if control == null:
		return "?"
	var words := control.get_node_or_null("Words") as Label
	if words and words.text != "":
		return words.text.replace("\n", " ")
	if control is Button and (control as Button).text != "":
		return (control as Button).text
	if control is LineEdit:
		return "field '%s'" % (control as LineEdit).text
	if control.has_meta("what"):
		# (a command card slot: its key and what it holds, as the card shows them)
		var what := str(control.get_meta("what"))
		var key := control.get_node_or_null("KeyTab/Hotkey") as Label
		var name_shown := str(Game.TOWERS[what]["name"]) if Game.TOWERS.has(what) else what.capitalize()
		return ("%s %s" % [key.text, name_shown] if key else name_shown).strip_edges()
	if control.tooltip_text != "":
		return control.tooltip_text.get_slice(":", 0).get_slice(".", 0)
	return str(control.name)


## The centre of a control's rect in viewport pixels, the coordinates the harness clicks in
## (a picture's pixels, the window standing at the project's 1280 x 720).
static func _at(_tree: SceneTree, control: Control) -> String:
	if control == null:
		return "?"
	var p := control.get_global_transform_with_canvas() * (control.size * 0.5)
	return "%d,%d" % [roundi(p.x), roundi(p.y)]


static func _text(node: Node) -> String:
	if node is Label:
		return (node as Label).text.replace("\n", " ")
	if node is RichTextLabel:
		return (node as RichTextLabel).get_parsed_text()
	return ""


## The visible labels under `node`, top to bottom, at most `limit`.
static func _texts(node: Node, limit: int) -> PackedStringArray:
	var out := PackedStringArray()
	if node == null:
		return PackedStringArray([""])
	_gather(node, out, limit)
	return out if not out.is_empty() else PackedStringArray([""])


static func _gather(n: Node, out: PackedStringArray, limit: int) -> void:
	if out.size() >= limit or (n is CanvasItem and not (n as CanvasItem).is_visible_in_tree()):
		return
	if n is Label and (n as Label).text.strip_edges() != "":
		out.append((n as Label).text.strip_edges().replace("\n", " "))
	for child in n.get_children():
		_gather(child, out, limit)


static func _showing(label: Label) -> bool:
	return label != null and label.is_visible_in_tree() and label.modulate.a > 0.05 and label.text != ""


static func _stars(node: Node) -> String:
	for child in node.find_children("*", "", true, false):
		if child is Shell.Stars:
			return " · difficulty %d of 3" % int(child.get("count"))
	return ""


static func _coverage(node: Node) -> String:
	for child in node.find_children("*", "", true, false):
		if child is CoverageRow:
			var lit: Array = child.call("lit")
			var dim: Array = child.call("dim")
			return "%s · not covered: %s" % [_check_names(lit), _check_names(dim)]
	return "?"


static func _check_names(checks: Array) -> String:
	if checks.is_empty():
		return "none"
	return ", ".join(checks.map(func(c: Variant) -> String: return str(Game.CHECKS[str(c)]["name"])))


## Godot's own tooltip, when one has opened over the hovered control (its popup is the
## control's internal child).
static func _popup_tip(tree: SceneTree, out: PackedStringArray) -> void:
	var hovered := tree.root.gui_get_hovered_control()
	var owners: Array[Node] = [tree.root]
	if hovered:
		owners.push_front(hovered)
	for owner in owners:
		for child in owner.get_children(true):
			if child is PopupPanel and (child as Window).visible:
				var words := _texts(child, 3)
				if words[0] != "":
					out.append("tooltip: " + " ".join(words))
				return
