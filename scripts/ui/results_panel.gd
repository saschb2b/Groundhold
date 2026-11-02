## Results, the Ebb (design 5.8): an overlay on the finished hollow, on the end plate art
## widened. The title in the game's words, one line of the match (mode, its level where it
## is not Normal (M8), waves, time, lives left out of the level's own), the lives along the
## waves, then one row per player: Builder, kills, damage,
## help, towers (and how many forked), and one positive line picked from a fixed list by
## the player's best stat relative to the team (ties go to the lower seat; no line
## repeats; no MVP). Every number comes from the simulation, so every client shows the
## same. Play again goes back to the hub with the party kept; Hub does the same.
## It never times out into the hub. A desynced match adds a plain line that the games
## disagreed and a button for the report its game saved (Show report, Save report in the
## browser), never its user:// path. A match this game lost its link to (`link_lost`: the
## others play on) says so in its title and why in a plain line (shown["said"]). A match
## that stopped (desynced, called off, the link lost) says in which wave, not how many
## waves the mode has. A race (Tide Race, M6) shows one block per team, mine first, with
## both race times and the rule that decided it in one line (_compute_race). A duel
## (Undertow, M7) shows a block per side the same way, mine first, with the breach each
## dealt, the duel's titles and the rule that decided it (_compute_duel).
class_name ResultsPanel
extends CanvasLayer

const TITLES := {
	"won": "The Holdfast Holds",
	"lost": "The Holdfast Goes Under",
	"desynced": "The Lands Fell Out of Step",
	"aborted": "The Match Was Called Off",
	"draw": "The Tide Stands Still",
	"link_lost": "Your Link Was Lost",
}
## Under a lost link's line when the reconnect gave up: the server holds the seat, and the
## caretaker plays it (design 6.7).
const CARETAKER_LINE := "The caretaker plays your seat to the end of the match."
## The outcomes of a match that stopped before its end, for this game at least.
const STOPPED := ["desynced", "aborted", "link_lost"]
## Under a desynced match's line, when the game wrote its report (shown["report"]).
const REPORT_LINE := "The games disagreed, so the match was stopped. A report was saved."
## The positive lines, in the list's order: [key, text]. "most_<creep>" keys are filled
## per creep kind; "held" names the wave the seat killed most in ("Most kills in wave 11").
const LINES := ["held", "help", "kills", "damage", "most_creep", "towers", "unsold"]
const FALLBACK := ["Kept watch", "Held the line", "Stood fast", "Saw it through"]
## How much taller a race's plate stands, for its two blocks.
const RACE_TALLER := 56.0

var results := {}
var _rows: VBoxContainer


## Builds the results from a finished match: the simulation's seats and teams, the names
## shown, the Builders chosen, the outcome, and `tally` (main.gd's count of the match's
## events: kills by seat and creep kind, kills by seat and wave, towers sold, lives after
## each wave).
static func compute(sim: SimMatch, names: Array, outcome: String, tally: Dictionary, shown_mode: String) -> Dictionary:
	var rows := []
	var team := sim.teams[0]
	# (design 5.8's "9 (4 forked)": the towers standing at the end and how many of them stand
	# forked; SimSeat.forks counts every fork made, a sold tower's too: playtest halv s2, P10)
	var forked_standing := {}
	for t in sim.towers:
		if t.branch >= 0:
			forked_standing[t.owner] = int(forked_standing.get(t.owner, 0)) + 1
	for s in sim.seats:
		var i := s.seat - 1
		rows.append(
			{
				"seat": s.seat,
				"team": s.team,
				"name": str(names[i]) if i < names.size() else "Seat %d" % s.seat,
				"builder": s.builder,
				"kills": s.kills,
				"damage_c": s.damage_c,
				"help_c": s.help_c,
				"towers": s.towers,
				"forks": int(forked_standing.get(s.seat, 0)),
				"left": s.state == SimTypes.SEAT_LEFT,
				"line": "",
			}
		)
	if sim.duel:
		return _compute_duel(sim, rows, outcome, tally)
	if sim.race:
		return _compute_race(sim, rows, outcome, tally, shown_mode)
	_pick_lines(rows, sim, tally)
	var lives := int(team.lives)
	var waves := sim.total_waves()
	var reached := sim.hollows[0].wave
	var minutes := sim.tick / 3600
	var seconds := (sim.tick / 60) % 60
	# (M8: the level named where it is not Normal, and the lives out of its own:
	# "High Water · Very Hard · 12 waves · 13:42 · 4 of 10 lives left")
	var mode := Game.mode_words(Profile.mode_name(shown_mode), MatchRules.level_played(sim.rules))
	var detail := "%s · %d waves · %d:%02d · %d of %d lives left" % [
		mode, waves, minutes, seconds, lives, int(sim.rules["lives"])
	]
	if outcome == "lost":
		# (on the oldest wave on its road, with two there: M8)
		var fell := mini(reached, sim.hollows[0].cleared + 1) if reached > 0 else 0
		detail = "%s · fell in wave %d of %d · %d:%02d" % [mode, fell, waves, minutes, seconds]
	elif outcome in STOPPED:
		var where := "stopped in wave %d of %d" % [reached, waves] if reached > 0 else "stopped before the first wave"
		detail = "%s · %s · %d:%02d" % [mode, where, minutes, seconds]
	return {
		"outcome": outcome,
		"title": str(TITLES.get(outcome, "The Ebb")),
		"detail": detail,
		"rows": rows,
		"lives": tally.get("lives", []),
		"max_lives": int(sim.rules["lives"]),
		"waves": waves,
	}


## A race's results (design 5.8, M6): the title from my team's outcome ("You Outran the
## Tide", "Your Rival Outran the Tide", "Two Crews, One Time"; a stopped match keeps its
## own), the match in one line, the rule that decided it in one line, and one block per
## team, mine first: its race time (the tick it cleared its last wave plus the rules' life_t
## a life lost, SimMatch.race_penalty_t, "12:41 +120 s"; where it set none, where it fell or
## how far it got), its lives with
## their line along its own waves, and its players' rows, each with a line picked against
## its own team.
static func _compute_race(
	sim: SimMatch, rows: Array, outcome: String, tally: Dictionary, shown_mode: String
) -> Dictionary:
	var mine := Game.my_team()
	var order := [mine] + range(sim.teams.size()).filter(func(t: int) -> bool: return t != mine)
	var blocks := []
	var by_team: Dictionary = tally.get("team_lives", {})
	for t: int in order:
		var team_rows := rows.filter(func(r: Dictionary) -> bool: return int(r["team"]) == t)
		_pick_lines(team_rows, sim, tally)
		var rec := sim.teams[t]
		blocks.append(
			{
				"team": t,
				"mine": t == mine,
				"name": "Your crew" if t == mine else "Rival crew",
				"time": race_time_text(sim, t),
				"lives": rec.lives,
				"lives_line": by_team.get(t, []),
				"seats": team_rows.map(func(r: Dictionary) -> int: return int(r["seat"])),
			}
		)
	var waves := sim.total_waves()
	var minutes := sim.tick / 3600
	var seconds := (sim.tick / 60) % 60
	# (M8: both crews play one level, named where it is not Normal)
	var mode := Game.mode_words(Profile.mode_name(shown_mode), MatchRules.level_played(sim.rules))
	var detail := "%s · %d waves · %d:%02d" % [mode, waves, minutes, seconds]
	var title := str(Game.RACE_TITLES.get(outcome, TITLES.get(outcome, "The Ebb")))
	var rule := Game.race_rule_line() if Game.RACE_TITLES.has(outcome) else ""
	if outcome in STOPPED:
		var reached := sim.hollows[sim.teams[mine].hollows[0]].wave
		var where := "stopped in wave %d of %d" % [reached, waves] if reached > 0 else "stopped before the first wave"
		detail = "%s · %s · %d:%02d" % [mode, where, minutes, seconds]
	return {
		"outcome": outcome,
		"race": true,
		"title": title,
		"detail": detail,
		"rule": rule,
		"rows": rows,
		"teams": blocks,
		"lives": tally.get("lives", []),
		"max_lives": int(sim.rules["lives"]),
		"waves": waves,
	}


## A duel's results (design 5.8, M7, contract-m7.md §3): the title from my outcome ("The
## Tide Took Your Rival", "The Tide Took You", "Even Tide"; a stopped match keeps its own),
## the match in one line, the rule that decided it in one line (a fall, more lives after
## the Surge, more breach dealt, a draw: Game.duel_rule_line), and a block per side, mine
## first: the breach it dealt (the lives its uncorked creeps took), its lives with their
## line along its own waves, and its player's row with a line picked against its own side.
static func _compute_duel(sim: SimMatch, rows: Array, outcome: String, tally: Dictionary) -> Dictionary:
	var mine := Game.my_team()
	var blocks := []
	var by_team: Dictionary = tally.get("team_lives", {})
	for t: int in [mine, 1 - mine]:
		var team_rows := rows.filter(func(r: Dictionary) -> bool: return int(r["team"]) == t)
		_pick_lines(team_rows, sim, tally)
		var side := Game.duel_side(t)
		blocks.append(
			{
				"team": t,
				"mine": t == mine,
				"name": "You" if t == mine else "Your rival",
				"time": "%d breach dealt" % int(side["breach"]),
				"breach": int(side["breach"]),
				"stipend": int(side["stipend"]),
				"lives": sim.teams[t].lives,
				"lives_line": by_team.get(t, []),
				"seats": team_rows.map(func(r: Dictionary) -> int: return int(r["seat"])),
			}
		)
	var waves := sim.total_waves()
	var minutes := sim.tick / 3600
	var seconds := (sim.tick / 60) % 60
	var mode := Profile.mode_name("undertow")
	var reached := sim.hollows[sim.teams[mine].hollows[0]].wave
	var detail := "%s · %d waves · %d:%02d" % [mode, waves, minutes, seconds]
	if SimUndertow.surge_of(sim, reached) > 0:
		detail = "%s · %d waves and the Surge · %d:%02d" % [mode, waves, minutes, seconds]
	if outcome in STOPPED:
		var where := "stopped in wave %d of %d" % [reached, waves] if reached > 0 else "stopped before the first wave"
		if SimUndertow.surge_of(sim, reached) > 0:
			where = "stopped in %s" % Game.wave_name(reached)
		detail = "%s · %s · %d:%02d" % [mode, where, minutes, seconds]
	return {
		"outcome": outcome,
		"race": true,
		"duel": true,
		"title": str(Game.DUEL_TITLES.get(outcome, TITLES.get(outcome, "The Ebb"))),
		"detail": detail,
		"rule": Game.duel_rule_line() if Game.DUEL_TITLES.has(outcome) else "",
		"rows": rows,
		"teams": blocks,
		"lives": tally.get("lives", []),
		"max_lives": int(sim.rules["lives"]),
		"waves": waves,
	}


## A team's race time as the results show it: "12:41 +20 s" (the tick it cleared its last
## wave, and what its lost lives added); without one, "fell on wave 9", or where its race
## clock stood when the race was decided ("on wave 12 at 7:20"; M8: "on waves 11–12 at
## 7:20" with stacked waves on its road, SimMatch.waves_on_road).
static func race_time_text(sim: SimMatch, team: int) -> String:
	var rec := sim.teams[team]
	if sim.race_time(team) >= 0:
		return Game.race_clock(rec.clear_tick, sim.race_penalty_t(team))
	if rec.fell_wave > 0:
		return "fell on wave %d" % rec.fell_wave
	var on := sim.waves_on_road(rec.hollows[0])
	var where := "wave %d" % maxi(1, sim.hollows[rec.hollows[0]].wave)
	if on.size() >= 2:
		where = "waves %d–%d" % [on[0], on[on.size() - 1]]
	return "on %s at %s" % [where, Game.race_clock(sim.tick, sim.race_penalty_t(team))]


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
					# (the wave the seat killed most in, said as what it counts: "Held wave 11" read
					# as nothing to two players)
					var text := "Most kills in wave %d" % int(best_wave[r_i][1])
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
	var race := bool(shown.get("race", false))
	var plate := Shell.WidePlate.new()
	plate.name = "ResultsPlate"
	plate.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	plate.offset_left = -470
	plate.offset_right = 470
	# (a race's two blocks stand on a taller plate)
	plate.offset_top = -250 - RACE_TALLER * 0.5 if race else -250.0
	plate.offset_bottom = 200 + RACE_TALLER * 0.5 if race else 200.0
	root.add_child(plate)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	Shell.place(box, Rect2(46, 64, 848, 360 + (RACE_TALLER if race else 0.0)))
	plate.add_child(box)
	var title := Shell.label(str(shown["title"]).to_upper(), Shell.TITLE_FONT, 26, Shell.GOLD)
	title.name = "ResultsTitle"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	var detail := Shell.label(str(shown["detail"]), Shell.BODY_FONT, 15, Shell.TEXT)
	detail.name = "ResultsDetail"
	detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(detail)
	var report := str(shown.get("report", ""))
	if report != "":
		# (a desync: what happened, in plain words; the report is behind a button)
		var said := Shell.label(REPORT_LINE, Shell.BODY_FONT, 14, Shell.DIM)
		said.name = "ResultsReport"
		said.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box.add_child(said)
	elif str(shown.get("said", "")) != "":
		# (a lost link: what happens now, in plain words)
		var said := Shell.label(str(shown["said"]), Shell.BODY_FONT, 14, Shell.DIM)
		said.name = "ResultsSaid"
		said.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box.add_child(said)
	if race:
		var rule := Shell.label(str(shown.get("rule", "")), Shell.BOLD_FONT, 15, Shell.GOLD)
		rule.name = "ResultsRule"
		rule.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		rule.visible = rule.text != ""
		box.add_child(rule)
		box.add_child(Shell.gilt_rule(300))
	else:
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
	if race:
		for block: Dictionary in shown["teams"]:
			_rows.add_child(_team_head(block, shown))
			for r: Dictionary in shown["rows"]:
				if (block["seats"] as Array).has(int(r["seat"])):
					_rows.add_child(_player_row(r))
	else:
		for r: Dictionary in shown["rows"]:
			_rows.add_child(_player_row(r))
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
	if report != "":
		var keep := Button.new()
		keep.name = "ResultsShowReport"
		keep.text = "Save report" if OS.has_feature("web") else "Show report"
		keep.tooltip_text = "This game's state and the match's turns, where the games parted. Send it to whoever fixes the game, with the other players' reports"
		keep.focus_mode = Control.FOCUS_NONE
		keep.flat = true
		keep.add_theme_color_override("font_color", Shell.DIM)
		for st: String in ["normal", "hover", "pressed", "hover_pressed"]:
			keep.add_theme_stylebox_override(st, StyleBoxEmpty.new())
		keep.pressed.connect(func() -> void: show_report(report))
		foot.add_child(keep)


## The desync report at `path` (a user:// file): in the browser a download of it (its
## user:// lives in IndexedDB, out of reach); on the desktop its folder opens with the
## file selected.
static func show_report(path: String) -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.download_buffer(FileAccess.get_file_as_bytes(path), "groundhold-" + path.get_file())
	else:
		OS.shell_show_in_file_manager(ProjectSettings.globalize_path(path), true)


## One player's row: name, Builder, kills, damage, help, towers and the line picked.
func _player_row(r: Dictionary) -> HBoxContainer:
	var cells := []
	var builder_title := str(SimContent.BUILDERS[r["builder"]]["title"]).trim_prefix("the ")
	if bool(r["left"]):
		cells = [r["name"], builder_title, "", "", "", "", "left the match; the caretaker finished"]
	else:
		cells = [
			r["name"], builder_title, str(r["kills"]), _short(int(r["damage_c"]) / 100),
			_short(int(r["help_c"]) / 100), "%d (%d forked)" % [r["towers"], r["forks"]], r["line"]
		]
	return _row(cells, false, int(r["seat"]) - 1, str(r["builder"]))


## A race team's head over its rows: "YOUR CREW" or "RIVAL CREW", its race time, its lives
## and the line of them along its own waves, over a thin bronze rule. A duel's side: "YOU" or
## "YOUR RIVAL", the breach it dealt in the race time's place.
func _team_head(block: Dictionary, shown: Dictionary) -> VBoxContainer:
	var holder := VBoxContainer.new()
	holder.name = "Team%d" % (int(block["team"]) + 1)
	holder.add_theme_constant_override("separation", 2)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 4)
	holder.add_child(gap)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 12)
	holder.add_child(head)
	var rule := ColorRect.new()
	rule.color = Color("#5c4b33")
	rule.custom_minimum_size = Vector2(0, 1)
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(rule)
	var name_label := Shell.caps(str(block["name"]), 12, Shell.GOLD if bool(block["mine"]) else Shell.DIM)
	name_label.name = "TeamName"
	name_label.custom_minimum_size.x = 104
	name_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(name_label)
	var time := Shell.label(str(block["time"]), Shell.BOLD_FONT, 16, PartyStrip.MINE if bool(block["mine"]) else Shell.TEXT)
	time.name = "TeamTime"
	# (wide enough for "on wave 12 at 12:58 +20 s", so both crews' lives line up)
	time.custom_minimum_size.x = 200
	time.add_theme_constant_override("outline_size", 0)
	head.add_child(time)
	var top := int(shown.get("max_lives", 20))
	var lives := Shell.label("%d of %d lives" % [int(block["lives"]), top], Shell.BODY_FONT, 14, Shell.TEXT)
	lives.name = "TeamLives"
	lives.custom_minimum_size.x = 104
	lives.add_theme_constant_override("outline_size", 0)
	head.add_child(lives)
	var line := LivesLine.new()
	line.name = "TeamLivesLine"
	line.values = block.get("lives_line", [])
	line.top = top
	line.waves = int(shown.get("waves", 1))
	# (the lives along the waves to the right, clear of the numbers' columns, no rule of
	# its own: the head's rule runs under it)
	line.span = Vector2(0.3, 0.7)
	line.baseline = false
	line.custom_minimum_size = Vector2(0, 24)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(line)
	return holder


## The race's team blocks as one line each, for tests: "Your crew 12:41 +20 s 18 of 20
## lives: Sascha, Ana" (empty outside a race).
func team_lines() -> Array[String]:
	var out: Array[String] = []
	for block: Dictionary in results.get("teams", []):
		var who := []
		for r: Dictionary in results["rows"]:
			if (block["seats"] as Array).has(int(r["seat"])):
				who.append(str(r["name"]))
		out.append(
			"%s %s %d of %d lives: %s" % [
				block["name"], block["time"], int(block["lives"]), int(results["max_lives"]), ", ".join(who)
			]
		)
	return out


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
	# (the Builder's face and title need 108 at most, "12 (12 forked)" 93, so the line keeps
	# 162 of the plate's 848: "Most kills in wave 11" is 147)
	var widths := [160, 130, 54, 70, 60, 104, 0]
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
	## Where the line runs across the control: from x (a share of its width), for y.
	var span := Vector2(0.2, 0.6)
	## Whether a dim rule marks no lives under it.
	var baseline := true

	func _init() -> void:
		custom_minimum_size = Vector2(0, 34)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var left := size.x * span.x
		var width := size.x * span.y
		if baseline:
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
