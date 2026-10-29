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
## Helpers for tests and tools: cell_center(cell), build(kind, cell), fork(cell),
## sell(cell), tower_at(cell), spawn(kind), settled(), state_hash_hex(), hash_at(tick),
## record(), replay_matches(), schedule(tick, name, a, b, c).
extends Node3D

const MAP_FILE := "res://data/hollow.txt"
const MODE := "classic"
## The kit's fast-forward hook: simulation ticks to run per frame.
const TICKS_PER_FRAME_META := &"godot_agent_ticks_per_frame"
## How often (physics frames) the --bot flag's plan bot takes its next steps.
const BOT_EVERY := 15

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
	if options.has("join"):
		_join_server(str(options["join"]))
	else:
		var match_seed := int(options.get("seed", "1"))
		begin(MODE, SimMatch.default_seats(1), match_seed, LocalSequencer.new(1, 1), 1)
	controller.setup(map, terrain, decor, self, towers)
	hud.setup(self)
	_frame_camera()
	_set_the_scene()
	Game.announce("Lantern Hollow")


func _exit_tree() -> void:
	if client:
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
	if sim == null:
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
	var joining := MatchClient.new()
	joining.player_name = str(options.get("name", "Player %d" % (OS.get_process_id() % 1000)))
	joining.token = _net_token()
	joining.build_seq = _build_seq()
	joining.web = OS.has_feature("web")
	play_through(joining)
	print("JOIN %s as %s" % [NetAddress.url(address), client.player_name])
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
	client.started.connect(func() -> void: Game.announce("The rift stirs"))
	client.ended.connect(_on_net_ended)
	client.failed.connect(_on_net_failed)


func _on_net_configured() -> void:
	begin(client.mode, client.seat_list, client.match_seed, client.source, client.seat, client.sim)
	_finished = false
	DisplayServer.window_set_title("Lantern Hollow · %s · seat %d" % [client.player_name, client.seat])
	print("MATCH %d seat %d of %d seed %d" % [client.match_id, client.seat, client.seat_list.size(), client.match_seed])


func _on_net_ended(outcome: String, reason: String) -> void:
	print("MATCH_END %s %s %d" % [outcome, reason, client.final_tick])
	controller.forget_pending()
	# (no order goes out any more: the placement grid, the ghost and the lit slot go too)
	controller.set_mode("")
	if outcome == "desynced":
		Game.announce("The hollows fell out of step")
	elif outcome == "aborted":
		Game.announce("The match was called off")
	if options.has("quit-after-match"):
		if _hash_file:
			_hash_file.flush()
		get_tree().quit(0 if outcome in ["won", "lost", "draw"] else 1)


func _on_net_failed(text: String) -> void:
	print("NET FAILED %s" % text)
	Game.announce(text)
	controller.forget_pending()
	controller.set_mode("")
	if options.has("quit-after-match"):
		get_tree().quit(1)


## This computer's token for servers (design 6.10): 16 random bytes kept in user://net.cfg.
## Two windows on one computer share it, which M1's server allows.
func _net_token() -> PackedByteArray:
	var cfg := ConfigFile.new()
	var path := "user://net.cfg"
	cfg.load(path)
	var hex := str(cfg.get_value("identity", "token", ""))
	if hex.length() == 32:
		return hex.hex_decode()
	var token := Crypto.new().generate_random_bytes(16)
	cfg.set_value("identity", "token", token.hex_encode())
	cfg.save(path)
	return token


## The CI run number (data/build.json, written by the release build), else 0.
func _build_seq() -> int:
	if not FileAccess.file_exists("res://data/build.json"):
		return 0
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/build.json"))
	return int((parsed as Dictionary).get("build_seq", 0)) if parsed is Dictionary else 0


# ── Events to views ──


func _show(events: Array) -> void:
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


func _spawned(id: int) -> void:
	var rec := sim.creep(id)
	if rec == null:
		return  # spawned and gone within one frame
	var view := Creep.new()
	view.name = "%s_%d" % [rec.kind, id]
	view.setup(rec, _road_points)
	creeps.add_child(view)
	creep_views[id] = view
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


func _built(e: Dictionary) -> void:
	var rec := sim.tower(int(e["id"]))
	if rec == null:
		return
	var cell := Vector2i(rec.x, rec.z)
	var view := Tower.new()
	view.name = "%s_%d_%d" % [rec.kind, cell.x, cell.y]
	towers.add_child(view)
	view.setup(rec, terrain.surface(cell), creep_views)
	tower_views[rec.id] = view
	decor.clear_cell(cell)
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


## Orders the tower on `cell` upgraded (fork branch A), as the U key would.
func fork(cell: Vector2i) -> bool:
	var previous := controller.selected
	controller.select(tower_at(cell))
	var ok := controller.upgrade_selected()
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


## A creep of `kind` at the rift gate now (a scenario setter, logged for replays).
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


func _place_landmarks() -> void:
	var gate := Models.instance("res://models/props/rift_gate.glb")
	gate.name = "RiftGate"
	gate.position = map.center(map.spawn)
	gate.add_to_group("landmarks")
	add_child(gate)
	BlobShadow.under(gate, 0.75)
	var glow := OmniLight3D.new()
	glow.light_color = Color(0.7, 0.45, 1.0)
	glow.light_energy = 1.6
	glow.omni_range = 2.5
	glow.position = Vector3(0, 0.6, 0)
	gate.add_child(glow)

	var hearth := Models.instance("res://models/props/hearth.glb")
	hearth.name = "Hearth"
	hearth.position = map.center(map.hearth)
	hearth.add_to_group("landmarks")
	add_child(hearth)
	BlobShadow.under(hearth, 0.8)
	var fire := OmniLight3D.new()
	fire.light_color = Color(1.0, 0.7, 0.35)
	fire.light_energy = 2.2
	fire.omni_range = 3.5
	fire.position = Vector3(0, 1.1, 0)
	hearth.add_child(fire)


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


## Starts close enough to see the units, over the first stretch of road.
func _frame_camera() -> void:
	var rig := camera as CameraRig
	rig.setup(Rect2(0, 0, map.width, map.depth), Vector3(9.0, 0, 6.5), 12.5, 21.0)
