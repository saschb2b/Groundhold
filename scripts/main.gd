## The app: assembles the hollow from the map file, starts the match and shows it.
##
## The rules run in a SimMatch (scripts/sim) fed turn by turn from a TurnSource; offline
## that is the in-process LocalSequencer. Each physics frame steps the simulation (one
## tick, or as many as the kit's `ticks_per_frame` asks for), then hands its events to the
## views: creeps, towers, projectiles, effects, and `Game`, the local seat's facade the
## HUD reads.
##
## Boot flags, after `--`:
##   --seed=N             the match seed (default 1)
##   --bot                the plan bot (tests/bot.gd) plays my seat through commands
##   --hash-log[=FILE]    print "HASH <tick> <hex>" every 60 ticks; also write them to FILE
##   --quit-after-match   print "RESULT <tick> <hex> <won|lost>" and quit when the match ends
##   --ticks-per-frame=N  fast-forward: N ticks per physics frame (offline)
##   --join=ADDRESS       play a networked match on that server (127.0.0.1, 192.168.1.20,
##                        host:port or a ws:// URL; see NetAddress): a MatchClient says
##                        HELLO, and begin() runs when the server's MATCH_CONFIG arrives;
##                        the server's turns feed the simulation at the playout's pace
##   --name=NAME          the name the others see (1-16 letters, digits, spaces, _ or -)
##   --shot-at=T1,T2,...  save the window as a PNG when the match reaches these ticks, into
##   --shot-dir=DIR       DIR (default user://shots) as seat<N>_t<tick>.png
## With --join and --quit-after-match the game quits once the server's MATCH_END comes,
## after printing "MATCH_END <outcome> <reason> <final tick>" (exit code 0 for a match
## that finished, 1 for a desync, an abort or a refusal).
##
## The game boots into the hub (scenes/hub.tscn); the session (scripts/session/) brings
## this scene up for the match it names: an offline one (Play, Try) or the networked one a
## server's MATCH_CONFIG opened on the session's connection, which says LOADED once the
## hollow stands. At the end it leaves to the results (scripts/ui/results_panel.gd), and
## Play again goes back to the hub with the party. Booted on its own (its flags, a test)
## it plays as before and ends on the console's end plate.
##
## Networked (M4, design 6.7 and 6.8): the connection overlay (scripts/ui/
## connection_overlay.gd) says when this world is not live (reconnecting, catching up, in
## another tab, desynced) from MatchClient.connection_state(); a RESYNC's checkpoint
## replaces the simulation and the views are built again from its records (_rebuild_views);
## orders wait while the client catches up (its RemoteSequencer is closed, and
## Game.command_refusal() says "Catching up"); the web build's WebBridge reports the tab's
## visibility to the client and flashes the page title while the tab is hidden; a desynced
## match's results name the dump.
##
## Helpers for tests and tools: cell_center(cell), build(kind, cell), fork(cell, branch),
## sell(cell), tower_at(cell), spawn(kind), settled(), state_hash_hex(), hash_at(tick),
## record(), replay_matches(), schedule(tick, name, a, b, c), tab_hidden(hidden),
## overlay().
extends Node3D

const MAP_FILE := "res://data/hollow.txt"
## The map's name, which the match opens with.
const MAP_NAME := "Wickhollow"
const MODE := "classic"
## The kit's fast-forward hook: simulation ticks to run per frame.
const TICKS_PER_FRAME_META := &"godot_agent_ticks_per_frame"
## How often (physics frames) the --bot flag's plan bot takes its next steps.
const BOT_EVERY := 15
## The connection overlay's canvas layer: over the HUD (1), under the results (10).
const OVERLAY_LAYER := 5
## What the page title flashes while the tab is hidden in a match (web build).
const FLASH_TEXT := "Groundhold · the caretaker keeps your seat"

var map: HollowMap
var sim: SimMatch
var source: TurnSource
var seat := 1
var seat_list := []
## The networked seat's conversation with the server (--join); null offline.
var client: MatchClient
## Ticks per physics frame when above 0; otherwise the kit's meta, or 1.
var ticks_per_frame := 0
## tick -> state hash (hex) at tick 0 and every 60th tick since.
var hashes := {}
## Parsed boot flags: name -> value ("true" for a bare flag).
var options := {}
## Simulation id -> view.
var tower_views := {}
var creep_views := {}

var _road_points := PackedVector3Array()
var _scheduled: Array = []
var _hash_file: FileAccess
var _bot: RefCounted
var _shots: PackedInt32Array = []
var _frames := 0
var _finished := false
## The match the session asked for ({} when booted on its own), and whether the session's
## connection is the client here (it outlives this scene).
var _spec := {}
var _session_client := false
var _results: ResultsPanel
## The Esc menu (scripts/ui/match_menu.gd); an offline match waits while it is open.
var _menu: MatchMenu
## Why this world is not live (networked); hidden offline.
var _overlay: ConnectionOverlay
## The browser around the web build (inert on desktop).
var _bridge := WebBridge.new()
## Whether "LINK LOST" was printed for the reconnect going on.
var _said_reconnecting := false
## What the results count from the match's events: kills by seat and creep kind and by
## seat and wave, towers sold by seat, and the team's lives after each wave.
var _tally := {"kind_kills": {}, "wave_kills": {}, "sold": {}, "lives": []}

@onready var terrain: Terrain = $Terrain
@onready var decor: Decor = $Decor
@onready var creeps: Node3D = $Creeps
@onready var towers: Node3D = $Towers
@onready var controller: BuildController = $BuildController
@onready var hud: Hud = $Hud
@onready var camera: CameraRig = $Camera


func _ready() -> void:
	options = _parse_flags(OS.get_cmdline_user_args())
	ticks_per_frame = int(options.get("ticks-per-frame", "0"))
	for t in str(options.get("shot-at", "")).split(",", false):
		_shots.append(t.to_int())
	map = HollowMap.load_file(MAP_FILE)
	_road_points = map.path_points()
	terrain.build(map)
	decor.build(map, terrain)
	_place_landmarks()
	_spec = Session.enter_match(self)
	if _spec.has("networked") and Session.client:
		_session_client = true
		play_through(Session.client)
		if Session.client.phase >= MatchClient.Phase.LOADING:
			_on_net_configured()
	elif _spec.has("offline"):
		var seats: Array = _spec["seats"]
		begin(str(_spec["mode"]), seats, int(_spec["seed"]), LocalSequencer.new(seats.size(), 1), 1)
	elif options.has("join"):
		_join_server(str(options["join"]))
	else:
		var match_seed := int(options.get("seed", "1"))
		begin(MODE, SimMatch.default_seats(1), match_seed, LocalSequencer.new(1, 1), 1)
	controller.setup(map, terrain, decor, self, towers)
	hud.setup(self)
	_menu = MatchMenu.new()
	add_child(_menu)
	_menu.setup(self)
	var overlay_layer := CanvasLayer.new()
	overlay_layer.name = "ConnectionLayer"
	overlay_layer.layer = OVERLAY_LAYER
	add_child(overlay_layer)
	_overlay = ConnectionOverlay.new()
	overlay_layer.add_child(_overlay)
	_bridge.visibility_changed.connect(_on_tab_hidden)
	_bridge.start()
	_frame_camera()
	_set_the_scene()
	Game.announce(MAP_NAME)
	if _session_client:
		Session.match_loaded()  # the hollow stands: LOADED


func _exit_tree() -> void:
	_bridge.stop()
	if client and _session_client:
		_unhook(client)  # (the session keeps its connection for the hub)
	elif client:
		client.close()
	Game.detach()
	if _hash_file:
		_hash_file.close()
	Models.clear_cache()
	Fx.clear_cache()
	BlobShadow.clear_cache()


## Starts a match: `mode`'s rules, one entry per seat ({"team", "builder", "caretaker"}),
## the seed, where the turns come from, and which seat this client plays. `existing` is a
## simulation already built from those (the MatchClient's, whose tick-0 hash it sent).
func begin(
	mode: String,
	seats: Array,
	match_seed: int,
	turns: TurnSource,
	my_seat: int,
	existing: SimMatch = null
) -> void:
	for view: Node in creep_views.values() + tower_views.values():
		view.queue_free()
	creep_views.clear()
	tower_views.clear()
	seat_list = seats
	seat = my_seat
	sim = existing if existing else SimMatch.new(SimContent.rules(mode), seat_list, match_seed)
	source = turns
	source.seat = my_seat
	hashes.clear()
	Fx.reset()
	Game.attach(sim, source, seat)
	if options.has("hash-log") and options["hash-log"] != "true":
		_hash_file = FileAccess.open(str(options["hash-log"]), FileAccess.WRITE)
	_record_hash()
	if options.has("bot"):
		_bot = load("res://tests/bot.gd").new()


# ── Stepping ──


func _physics_process(_delta: float) -> void:
	if client:
		client.poll()
		_show_connection()
	_bridge.poll(Time.get_ticks_msec())
	if sim == null or paused():
		return
	source.poll()
	var ran := 0
	var budget := _ticks_this_frame()
	var began := Time.get_ticks_usec()
	var limit_usec := client.playout.budget_usec() if client and client.timed else 0
	while ran < budget:
		_submit_scheduled()
		if not source.prepare(sim):
			break
		sim.step()
		ran += 1
		if sim.tick % SimTypes.HASH_EVERY == 0:
			_record_hash()
		if _shots.has(sim.tick):
			_shot(sim.tick)
		if client:
			client.after_tick(sim.tick)
			if sim.over:
				break  # the match's last tick: RESULT is sent, nothing more to run
			if limit_usec > 0 and Time.get_ticks_usec() - began > limit_usec:
				break  # catching up: the rest next frame
	var events := sim.drain_events()
	Game.handle(events)
	if client:
		client.observe(events)
	_show(events)
	for view: Creep in creep_views.values():
		view.sync(ran)
	for view: Tower in tower_views.values():
		view.sync(ran)
	_frames += 1
	# (networked, the bot waits for the turns: commands before START go nowhere)
	var playing := client == null or client.phase == MatchClient.Phase.PLAYING
	if _bot and playing and _frames % BOT_EVERY == 0 and not sim.over:
		_bot.call("step", self)
	if sim.over and not _finished:
		_finished = true
		_on_match_over()
		if _spec.has("offline"):
			_show_results("aborted" if sim.aborted else ("won" if Game.state == Game.State.WON else "lost"))


# ── The Esc menu ──


## Whether the offline match waits: its Esc menu is open (a networked match plays on).
func paused() -> bool:
	return client == null and _menu != null and _menu.visible


## Esc with nothing to cancel (BuildController): the menu, while the match plays.
func open_menu() -> void:
	if sim == null or sim.over or _finished or _results != null:
		return
	if client and client.phase != MatchClient.Phase.PLAYING:
		return
	_menu.open()


func menu_open() -> bool:
	return _menu != null and _menu.visible


## The menu's Restart: the same offline match from its start (a Try stays a Try).
func restart() -> void:
	if client:
		return
	if _spec.has("offline"):
		Session.restart_match()
	else:
		get_tree().reload_current_scene()


## The menu's Leave to hub: online the server hears LEAVE_MATCH and the caretaker takes
## the seat; the party is kept.
func leave_to_hub() -> void:
	_menu.close()
	Session.to_hub()


func _ticks_this_frame() -> int:
	if client:
		return client.ticks_this_frame()  # the server's turns set the pace
	if ticks_per_frame > 0:
		return ticks_per_frame
	return maxi(0, int(Engine.get_meta(TICKS_PER_FRAME_META, 1)))


func _record_hash() -> void:
	var hex := sim.state_hash_hex()
	hashes[sim.tick] = hex
	if options.has("hash-log"):
		var line := "HASH %d %s" % [sim.tick, hex]
		print(line)
		if _hash_file:
			_hash_file.store_line(line)


func _on_match_over() -> void:
	if not options.has("quit-after-match"):
		return
	var won := Game.state == Game.State.WON
	print("RESULT %d %s %s" % [sim.tick, sim.state_hash_hex(), "won" if won else "lost"])
	if _hash_file:
		_hash_file.flush()
	if client == null:
		get_tree().quit(0)
	# (networked: the server's MATCH_END says whether everyone agreed; _on_net_ended quits)


## Saves what the window shows once this frame is drawn (--shot-at).
func _shot(tick: int) -> void:
	var dir := str(options.get("shot-dir", "user://shots"))
	DirAccess.make_dir_recursive_absolute(dir)
	var path := "%s/seat%d_t%d.png" % [dir, seat, tick]
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image and image.save_png(path) == OK:
		print("SHOT %s" % ProjectSettings.globalize_path(path))


# ── The network (--join) ──


func _join_server(address: String) -> void:
	# (one match at once on that server, no hub: the session's identity and name)
	var joining := Session.direct_client(str(options.get("name", "")), address)
	play_through(joining)
	print("JOIN %s as %s" % [NetAddress.url(address), client.player_name])
	if client.boot_resume:
		# (started again after a kill or a crash: its first HELLO asks the seat back)
		print("RESUME match %d seat %d" % [client.held_match, client.held_seat + 1])
	client.join(address)


## Plays the match `joining` (a MatchClient, not yet or just connected) will be given:
## any match on screen goes, and the hollow waits for the server's MATCH_CONFIG. --join
## does this at boot; tests/net/loopback_main.gd does it with a fake sequencer.
func play_through(joining: MatchClient) -> void:
	for view: Node in creep_views.values() + tower_views.values():
		view.queue_free()
	creep_views.clear()
	tower_views.clear()
	sim = null
	source = null
	Game.detach()
	client = joining
	client.configured.connect(_on_net_configured)
	client.started.connect(func() -> void: Game.announce("The tide turns at " + MAP_NAME))
	client.ended.connect(_on_net_ended)
	client.failed.connect(_on_net_failed)
	client.resynced.connect(_on_resynced)
	client.connection_changed.connect(_on_connection_changed)


func _on_net_configured() -> void:
	begin(client.mode, client.seat_list, client.match_seed, client.source, client.seat, client.sim)
	_finished = false
	DisplayServer.window_set_title("Groundhold · %s · seat %d" % [client.player_name, client.seat])
	print("MATCH %d seat %d of %d seed %d" % [client.match_id, client.seat, client.seat_list.size(), client.match_seed])


func _on_net_ended(outcome: String, reason: String) -> void:
	print("MATCH_END %s %s %d" % [outcome, reason, client.final_tick])
	controller.forget_pending()
	# (no order goes out any more: the placement grid, the ghost and the lit slot go too)
	controller.set_mode("")
	if client.dump_path != "":
		print("DESYNC REPORT %s" % ProjectSettings.globalize_path(client.dump_path))
	if _session_client:
		_show_results(outcome)  # (its title says it: no banner over it)
	elif outcome == "desynced":
		Game.announce("The lands fell out of step")
	elif outcome == "aborted":
		Game.announce("The match was called off")
	if options.has("quit-after-match"):
		if _hash_file:
			_hash_file.flush()
		get_tree().quit(0 if outcome in ["won", "lost", "draw"] else 1)


func _on_net_failed(text: String) -> void:
	print("NET FAILED %s" % text)
	controller.forget_pending()
	controller.set_mode("")
	if _session_client:
		# (the way back to the hub: the link is this game's, the match goes on for the others,
		# and the plate says so in its own words, with no banner over it; a reconnect that
		# gave up leaves the seat to the caretaker, any other failure says its reason)
		_show_results("link_lost", ResultsPanel.CARETAKER_LINE if client.gave_up else text)
	else:
		Game.announce(text)
	if options.has("quit-after-match"):
		get_tree().quit(1)


## Disconnects this scene from a client the session keeps.
func _unhook(kept: MatchClient) -> void:
	for sig: Signal in [
		kept.configured, kept.started, kept.ended, kept.failed, kept.resynced, kept.connection_changed
	]:
		for c: Dictionary in sig.get_connections():
			var target: Callable = c["callable"]
			if target.get_object() == self:
				sig.disconnect(target)


# ── Resilience (M4) ──


## The overlay follows the client: reconnecting, catching up, in another tab, desynced.
func _show_connection() -> void:
	if _overlay == null:
		return
	var now: Array = client.connection_state()
	if _results != null:
		now = [ConnectionOverlay.State.NONE, -1, ""]  # (the results plate says it all)
	if now != [_overlay.state, _overlay.progress_pm, _overlay.detail]:
		_overlay.show_state(now[0], now[1], now[2])


## Reconnecting or catching up, no order goes out: the placement mode and the ghosts go,
## as when the link fails.
func _on_connection_changed() -> void:
	if client.reconnecting and not _said_reconnecting:
		print("LINK LOST reconnecting")  # (for tools/net/smoke.py --faults)
	_said_reconnecting = client.reconnecting
	if client.reconnecting or client.catching_up:
		controller.forget_pending()
		controller.set_mode("")


## The client loaded a RESYNC's checkpoint: its simulation replaces this one, and every
## creep and tower view is built again from the records (no event says they are there).
func _on_resynced() -> void:
	sim = client.sim
	print("RESYNC %s %d" % [str(client.resyncs[-1][0]), sim.tick])  # (smoke.py --faults reads it)
	_rebuild_views()
	hud.clear_messages()  # (a refusal while reconnecting, a wave's title: from before the jump)
	for t: int in hashes.keys():
		if t > sim.tick:
			hashes.erase(t)


func _rebuild_views() -> void:
	for view: Node in creep_views.values() + tower_views.values():
		view.queue_free()
	creep_views.clear()
	tower_views.clear()
	controller.forget_pending()
	if controller.selected != null:
		controller.select(null)
	Game.attach(sim, source, seat)
	for rec in sim.towers:
		_built({"id": rec.id}, true)
	for rec in sim.creeps:
		_spawned(rec.id, true)


## The web build's tab was hidden or shown: the client tells the server, and the page
## title flashes while the tab is hidden in a match.
func _on_tab_hidden(now_hidden: bool) -> void:
	if client == null:
		return
	client.set_hidden(now_hidden)
	if now_hidden and client.phase == MatchClient.Phase.PLAYING:
		_bridge.flash_title(FLASH_TEXT)
	else:
		_bridge.stop_flash()


## Hides or shows the tab as the browser would (WebBridge's handler; for tests).
func tab_hidden(now_hidden: bool) -> void:
	_bridge.changed_to(now_hidden)


func overlay() -> ConnectionOverlay:
	return _overlay


# ── Results ──


## The match is over in a session's match: the results overlay on the finished hollow,
## instead of the console's end plate.
func _show_results(outcome: String, said := "") -> void:
	if _results or sim == null:
		return
	controller.set_mode("")
	hud.results_shown()  # (no notice or banner over the plate)
	var plate := hud.find_child("EndPanel", true, false) as Control
	if plate:
		plate.visible = false
	var names: Array = _spec.get("names", []) if _spec.has("offline") else Array(client.names)
	var shown_mode := str(_spec.get("shown_mode", Session.profile.mode))
	var shown := ResultsPanel.compute(sim, names, outcome, _tally, shown_mode)
	if said != "":
		shown["said"] = said
	if client and client.dump_path != "":
		# (a desynced match's plate offers the report each game wrote, design 6.7: a button,
		# not Godot's user:// path, which nobody could find)
		shown["report"] = client.dump_path
	_results = ResultsPanel.new()
	add_child(_results)
	_results.show_results(shown)
	Session.match_over(shown)


## Counts what the results need from this frame's events.
func _count(events: Array) -> void:
	for e: Dictionary in events:
		match int(e["type"]):
			SimTypes.EV_DIE:
				var by := int(e.get("seat", 0))
				if by <= 0:
					continue
				var kinds: Dictionary = _tally["kind_kills"].get_or_add(by, {})
				kinds[str(e["kind"])] = int(kinds.get(str(e["kind"]), 0)) + 1
				var waves: Dictionary = _tally["wave_kills"].get_or_add(by, {})
				var wave := sim.hollows[0].wave
				waves[wave] = int(waves.get(wave, 0)) + 1
			SimTypes.EV_SOLD:
				var sold: Dictionary = _tally["sold"]
				sold[int(e["seat"])] = int(sold.get(int(e["seat"]), 0)) + 1
			SimTypes.EV_WAVE:
				var done := int(e.get("phase", -1)) in [SimTypes.PHASE_DONE, SimTypes.PHASE_FALLEN]
				if e.get("cleared", false) or done:
					(_tally["lives"] as Array).append(sim.teams[0].lives)


# ── Events to views ──


func _show(events: Array) -> void:
	_count(events)
	for e: Dictionary in events:
		match int(e["type"]):
			SimTypes.EV_SPAWN:
				_spawned(int(e["id"]))
			SimTypes.EV_DIE:
				var view: Creep = creep_views.get(int(e["id"]))
				creep_views.erase(int(e["id"]))
				if view:
					view.die()
			SimTypes.EV_LEAK:
				var view: Creep = creep_views.get(int(e["id"]))
				creep_views.erase(int(e["id"]))
				if view:
					view.leak()
			SimTypes.EV_BUILT:
				_built(e)
			SimTypes.EV_FORKED:
				var view: Tower = tower_views.get(int(e["id"]))
				if view:
					view.forked()
					if controller.selected == view:
						controller.select(view)
			SimTypes.EV_SOLD:
				var view: Tower = tower_views.get(int(e["id"]))
				tower_views.erase(int(e["id"]))
				if view:
					if controller.selected == view:
						controller.select(null)
					view.sold(int(e["refund"]))
			SimTypes.EV_FIRE:
				var view: Tower = tower_views.get(int(e["tower"]))
				if view:
					view.fire(e, _road_point(int(e["land"])))
			SimTypes.EV_HIT:
				_hit(e)
			SimTypes.EV_EFFECT:
				if e["what"] == "splash":
					var at := Vector3(int(e["x"]) / 1000.0, 0.0, int(e["z"]) / 1000.0)
					Fx.explosion(get_tree(), at, int(e["r"]) / 1000.0)
					Sfx.play("explosion", -4.0)
			SimTypes.EV_SIGNAL:
				var at := Vector3(int(e["x"]) / 1000.0, 0.0, int(e["z"]) / 1000.0)
				Fx.ring(get_tree(), at, 0.9, Color(1.0, 0.85, 0.4, 0.9), 0.6)


func _spawned(id: int, quiet := false) -> void:
	var rec := sim.creep(id)
	if rec == null:
		return  # spawned and gone within one frame
	var view := Creep.new()
	view.name = "%s_%d" % [rec.kind, id]
	view.setup(rec, _road_points)
	creeps.add_child(view)
	creep_views[id] = view
	if quiet:
		return  # (built again from a checkpoint: it was already on the road)
	Fx.burst(
		get_tree(),
		_road_points[0] + Vector3(0, 0.4, 0),
		Color(0.75, 0.5, 1.0),
		10,
		1.5,
		0.06,
		0.5,
		0.5
	)


func _built(e: Dictionary, quiet := false) -> void:
	var rec := sim.tower(int(e["id"]))
	if rec == null:
		return
	var cell := Vector2i(rec.x, rec.z)
	var view := Tower.new()
	view.name = "%s_%d_%d" % [rec.kind, cell.x, cell.y]
	towers.add_child(view)
	# (built again from a checkpoint, quiet: it already stood, so it neither rises nor dusts)
	view.setup(rec, terrain.surface(cell), creep_views, not quiet)
	tower_views[rec.id] = view
	decor.clear_cell(cell)
	if quiet:
		return
	Fx.burst(
		get_tree(),
		terrain.surface(cell) + Vector3(0, 0.1, 0),
		Color(0.6, 0.5, 0.35, 0.9),
		14,
		1.2,
		0.08,
		0.6,
		0.3
	)
	Sfx.play("build")


func _hit(e: Dictionary) -> void:
	# A hit comes before the death it causes, so the creep's view is still listed.
	var view: Creep = creep_views.get(int(e["creep"]))
	if view == null:
		return
	view.hit()
	if e["splash"]:
		return  # the burst already shows
	var at := view.aim_point()
	if e["kind"] == "frost":
		Fx.burst(get_tree(), at, Color(0.6, 0.9, 1.0), 10, 1.6, 0.05, 0.45, -2.0)
	else:
		Fx.burst(get_tree(), at, Color(0.95, 0.85, 0.6), 5, 1.4, 0.04, 0.3)
	Sfx.play("hit", -10.0)


## A road distance (micrometres) as a point on the ground; the origin for -1.
func _road_point(dist_um: int) -> Vector3:
	if dist_um < 0:
		return Vector3.ZERO
	var road := sim.hollows[0].road
	return Vector3(road.x_at(dist_um) / 1000.0, 0.0, road.z_at(dist_um) / 1000.0)


# ── Helpers for tests and tools ──


func cell_center(cell: Vector2i) -> Vector3:
	return terrain.surface(cell)


## Orders a tower built, as a click would; false when refused before sending.
func build(kind: String, cell: Vector2i) -> bool:
	return controller.build(kind, cell)


## Orders the tower on `cell` forked to `branch` (0 for A, 1 for B), as Q or W on my
## selected tower would.
func fork(cell: Vector2i, branch := 0) -> bool:
	var previous := controller.selected
	controller.select(tower_at(cell))
	var ok := controller.fork_selected(branch)
	controller.select(previous if is_instance_valid(previous) else null)
	return ok


## Orders the tower on `cell` sold, as the S key would.
func sell(cell: Vector2i) -> bool:
	controller.select(tower_at(cell))
	return controller.sell_selected()


func tower_at(cell: Vector2i) -> Tower:
	if sim == null:
		return null
	var rec := sim.tower_at(0, cell.x, cell.y)
	return tower_views.get(rec.id) if rec else null


## A creep of `kind` at the Welling now (a scenario setter, logged for replays).
func spawn(kind: String) -> void:
	Game.debug(SimTypes.DBG_SPAWN, 0, SimContent.CREEP_IDS.find(kind))


## None of my commands is still waiting for its turn.
func settled() -> bool:
	return controller.settled()


func state_hash_hex() -> String:
	return sim.state_hash_hex()


func hash_at(tick: int) -> String:
	return str(hashes.get(tick, ""))


## Everything a replay needs: the set-up, the turn log and the debug writes (offline).
func record() -> Dictionary:
	var local := source as LocalSequencer
	return local.log_for(sim, seat_list) if local else {}


## Replays the turn log into a fresh simulation with no views and compares its hash at
## every hash tick so far with the ones this match recorded.
func replay_matches() -> bool:
	var last := sim.tick - sim.tick % SimTypes.HASH_EVERY
	var replayed := {}
	LocalSequencer.replay(record(), last, replayed)
	if replayed.is_empty() or not replayed.has(last):
		return false
	for tick: int in replayed:
		if hashes.get(tick, "") != replayed[tick]:
			return false
	return true


## Queues a command from my seat to be sent when the simulation reaches `tick`, so a
## scenario's orders land on the same ticks at any speed.
func schedule(tick: int, name: String, a := 0, b := 0, c := 0) -> void:
	_scheduled.append([tick, SimTypes.command_type(name), a, b, c])


func _submit_scheduled() -> void:
	while not _scheduled.is_empty() and int(_scheduled[0][0]) <= sim.tick:
		var entry: Array = _scheduled.pop_front()
		source.submit(entry[1], entry[2], entry[3], entry[4])


static func _parse_flags(args: PackedStringArray) -> Dictionary:
	var result := {}
	for arg in args:
		if not arg.begins_with("--"):
			continue
		var pair := arg.substr(2).split("=", true, 1)
		result[pair[0]] = pair[1] if pair.size() > 1 else "true"
	return result


# ── The world ──


## The road's two ends: the Welling, where the Tide wells up and the creeps start, and the
## Holdfast they walk to. Wickhollow's are the sunken field gate and the mill-house hearth.
func _place_landmarks() -> void:
	var welling := Models.instance("res://models/props/rift_gate.glb")
	welling.name = "Welling"
	welling.position = map.center(map.spawn)
	welling.add_to_group("landmarks")
	add_child(welling)
	BlobShadow.under(welling, 0.75)
	var glow := OmniLight3D.new()
	glow.light_color = Color(0.7, 0.45, 1.0)
	glow.light_energy = 1.6
	glow.omni_range = 2.5
	glow.position = Vector3(0, 0.6, 0)
	welling.add_child(glow)

	var holdfast := Models.instance("res://models/props/hearth.glb")
	holdfast.name = "Holdfast"
	holdfast.position = map.center(map.holdfast)
	holdfast.add_to_group("landmarks")
	add_child(holdfast)
	BlobShadow.under(holdfast, 0.8)
	var fire := OmniLight3D.new()
	fire.light_color = Color(1.0, 0.7, 0.35)
	fire.light_energy = 2.2
	fire.omni_range = 3.5
	fire.position = Vector3(0, 1.1, 0)
	holdfast.add_child(fire)


## Late-afternoon light and a painterly frame: a low sun from the upper left lights
## the faces toward the camera and throws long shadows away to the right, haze
## softens the far edge, and the corners darken. SSAO only shows on desktop (Forward+);
## blob shadows and the vignette carry the look in the browser build too.
func _set_the_scene() -> void:
	var sun: DirectionalLight3D = $Sun
	sun.basis = Basis.looking_at(Vector3(0.62, -0.55, -0.56).normalized(), Vector3.UP)
	var layer := CanvasLayer.new()
	layer.name = "Vignette"
	layer.layer = 0
	var shade := ColorRect.new()
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/vignette.gdshader")
	shade.material = material
	layer.add_child(shade)
	add_child(layer)


## Starts on what the players defend and where they build: the Welling, the Holdfast and
## the band between the road's two lower stretches, where both Builders' plans stand, all
## above the console and clear of the strips at the top (view_match_frames_the_band).
## Home shows the whole map; the wheel brings the units closer.
func _frame_camera() -> void:
	var rig := camera as CameraRig
	rig.setup(Rect2(0, 0, map.width, map.depth), Vector3(11.5, 0, 10.5), 20.5, 21.0)
