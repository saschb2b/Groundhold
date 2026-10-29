## Mouse and hotkeys on the battlefield: choose a tower, see where it fits, place it,
## select towers, upgrade, sell and call Ready. HUD buttons call the same methods.
##
## Nothing here changes the match: each order goes out as a command and runs when its
## turn comes (within 50 ms offline). Until then a placed tower stands as a pulsing ghost
## and its cost is kept back from the gold; the simulation confirms or refuses it.
##
## Networked, orders go out only while the match runs and its link holds, and no faster
## than the server's command bucket allows (Game.can_command): otherwise an order is
## refused here with the reason ("The match has not started", "No link to the server",
## "Not so fast"). Ready goes out one at a time: presses while one is on its way only
## change what the next one asks for, so mashing N costs one command per round trip.
class_name BuildController
extends Node3D

signal selection_changed(tower: Tower)
signal creep_selected(creep: Creep)
signal mode_changed(kind: String)

## How close (screen pixels) a click must land to a creep to select it.
const CREEP_PICK_RADIUS := 36.0

const ACTIONS := {
	"build_arrow": KEY_A,
	"build_cannon": KEY_C,
	"build_frost": KEY_F,
	"upgrade": KEY_U,
	"sell": KEY_S,
	"ready": KEY_N,
	"cancel": KEY_ESCAPE,
}

var map: HollowMap
var terrain: Terrain
var decor: Decor
## The scene: it knows which tower view stands on which cell.
var main: Node
var tower_parent: Node3D
## Tower kind being placed, or "" when not building.
var mode := ""
var hover_cell := Vector2i(-1, -1)
var selected: Tower
var selected_creep: Creep
## My commands waiting for their turn, by sequence number:
## {"what", "cost", "cell", "ghost", "on"}.
var pending := {}
## Ready as the latest press asked for it, still to be sent (one READY is on its way):
## -1 nothing waiting, 0 or 1.
var ready_wanted := -1

var _ghost: Node3D
var _ghost_material: StandardMaterial3D
var _range_ring: MeshInstance3D
var _range_material: StandardMaterial3D


func _ready() -> void:
	for action: String in ACTIONS:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = ACTIONS[action]
			InputMap.action_add_event(action, key)
	_range_material = StandardMaterial3D.new()
	_range_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_range_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_range_material.albedo_color = Color(0.5, 1.0, 0.5, 0.55)
	# Drawn over the rolling ground, which would otherwise hide parts of the ring.
	_range_material.no_depth_test = true
	_range_ring = MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.96
	torus.outer_radius = 1.0
	torus.rings = 48
	torus.ring_segments = 4
	_range_ring.mesh = torus
	_range_ring.material_override = _range_material
	_range_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_range_ring.visible = false
	add_child(_range_ring)
	_ghost_material = StandardMaterial3D.new()
	_ghost_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_ghost_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA


func setup(source: HollowMap, ground: Terrain, scenery: Decor, scene: Node, parent: Node3D) -> void:
	map = source
	terrain = ground
	decor = scenery
	main = scene
	tower_parent = parent
	Game.settled.connect(_on_settled)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_hover((event as InputEventMouseMotion).position)
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		var button := event as InputEventMouseButton
		_hover(button.position)
		if button.button_index == MOUSE_BUTTON_LEFT:
			if mode != "":
				if build(mode, hover_cell) and not button.shift_pressed:
					set_mode("")
			elif main.tower_at(hover_cell) != null:
				select(main.tower_at(hover_cell))
			else:
				select(null)
				select_creep(_creep_near(button.position))
		elif button.button_index == MOUSE_BUTTON_RIGHT:
			set_mode("")
			select(null)
	elif event.is_action_pressed("build_arrow"):
		set_mode("arrow")
	elif event.is_action_pressed("build_cannon"):
		set_mode("cannon")
	elif event.is_action_pressed("build_frost"):
		set_mode("frost")
	elif event.is_action_pressed("upgrade"):
		upgrade_selected()
	elif event.is_action_pressed("sell"):
		sell_selected()
	elif event.is_action_pressed("ready"):
		toggle_ready()
	elif event.is_action_pressed("cancel"):
		set_mode("")
		select(null)


func set_mode(kind: String) -> void:
	if kind != "" and Game.state in [Game.State.WON, Game.State.LOST]:
		return
	if kind != "" and not Game.accepts_commands():
		_refuse(Game.command_refusal())
		kind = ""
	elif kind != "" and not Game.can_afford(Game.tower_cost(kind)):
		Sfx.play("error")
		Game.notice("Not enough gold")
		kind = ""
	mode = kind
	if _ghost:
		_ghost.queue_free()
		_ghost = null
	if mode != "":
		select(null)
		_ghost = Models.instance(str(Game.TOWERS[mode]["model"]))
		for mi: MeshInstance3D in _meshes(_ghost):
			mi.material_override = _ghost_material
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(_ghost)
		Sfx.play("click", -6.0)
	terrain.show_grid(mode != "")
	_refresh_preview()
	mode_changed.emit(mode)


func can_build(kind: String, cell: Vector2i) -> bool:
	return (
		Game.accepts_commands()
		and _cell_free(cell)
		and Game.can_afford(Game.tower_cost(kind))
		and Game.state not in [Game.State.WON, Game.State.LOST]
	)


## Sends a tower to be built; returns false (and says why) when the match, the cell or
## the gold does not allow it. The tower appears when the command runs.
func build(kind: String, cell: Vector2i) -> bool:
	if not can_build(kind, cell):
		if not Game.accepts_commands():
			_refuse(Game.command_refusal())
		elif not _cell_free(cell):
			_refuse("Cannot build there")
		else:
			_refuse("Not enough gold")
		return false
	var cost := Game.tower_cost(kind)
	var seq := Game.command(SimTypes.CMD_BUILD, Game.slot_of(kind), cell.x, cell.y)
	if seq < 0:
		_refuse(Game.command_refusal())
		return false
	_add_pending(seq, "build", cost, cell, _make_ghost(kind, cell))
	_refresh_preview()
	return true


## A grass cell with no tower on it and none on its way.
func _cell_free(cell: Vector2i) -> bool:
	if not map.buildable(cell) or main.tower_at(cell) != null:
		return false
	for seq: int in pending:
		if pending[seq]["what"] == "build" and pending[seq]["cell"] == cell:
			return false
	return true


func select_creep(creep: Creep) -> void:
	selected_creep = creep
	creep_selected.emit(creep)


func _creep_near(screen: Vector2) -> Creep:
	var camera := get_viewport().get_camera_3d()
	var best: Creep = null
	var best_distance := CREEP_PICK_RADIUS
	for node in get_tree().get_nodes_in_group("creeps"):
		var creep := node as Creep
		var at := camera.unproject_position(creep.aim_point())
		if at.distance_to(screen) < best_distance:
			best_distance = at.distance_to(screen)
			best = creep
	return best


func select(tower: Tower) -> void:
	if tower != null:
		selected_creep = null
	selected = tower
	_refresh_preview()
	selection_changed.emit(selected)


func upgrade_selected() -> bool:
	if selected == null or not is_instance_valid(selected) or selected.upgrade_cost() < 0:
		return false
	if not Game.accepts_commands():
		_refuse(Game.command_refusal())
		return false
	if selected.owner_seat != Game.seat:
		Sfx.play("error")
		Game.notice("That tower is not yours")
		return false
	if _pending_on(selected.cell, "fork"):
		return false
	var cost := selected.upgrade_cost()
	if not Game.can_afford(cost):
		Sfx.play("error")
		Game.notice("Not enough gold")
		return false
	var seq := Game.command(SimTypes.CMD_FORK, selected.id, 0)
	if seq < 0:
		_refuse(Game.command_refusal())
		return false
	_add_pending(seq, "fork", cost, selected.cell, null)
	return true


func sell_selected() -> bool:
	if selected == null or not is_instance_valid(selected):
		return false
	if not Game.accepts_commands():
		_refuse(Game.command_refusal())
		return false
	if selected.owner_seat != Game.seat:
		Sfx.play("error")
		Game.notice("That tower is not yours")
		return false
	if _pending_on(selected.cell, "sell"):
		return false
	var seq := Game.command(SimTypes.CMD_SELL, selected.id)
	if seq < 0:
		_refuse(Game.command_refusal())
		return false
	_add_pending(seq, "sell", 0, selected.cell, null)
	select(null)
	return true


## The war horn: Ready, or not Ready any more. When every seat is Ready the next wave
## comes at once and each second left pays every seat one gold. While a READY of mine is
## on its way, a press only changes what the next one will ask for (sent once it lands).
func toggle_ready() -> bool:
	if Game.state != Game.State.PREP or Game.wave >= Game.total_waves():
		return false
	if not Game.accepts_commands():
		_refuse(Game.command_refusal())
		return false
	var want := not wants_ready()
	ready_wanted = 1 if want else 0
	Sfx.play("click", -6.0)
	_send_ready()
	selection_changed.emit(selected)
	return true


## Ready as my last press asked for it, before the turn confirms.
func wants_ready() -> bool:
	if ready_wanted >= 0:
		return ready_wanted == 1
	for seq: int in pending:
		if pending[seq]["what"] == "ready":
			return bool(pending[seq]["on"])
	return Game.is_ready()


## Sends the Ready the player wants when none is on its way and the bucket has room;
## a want that matches the simulation already is dropped.
func _send_ready() -> void:
	if ready_wanted < 0 or _pending_ready() or not Game.can_command():
		return
	var want := ready_wanted == 1
	ready_wanted = -1
	if want == Game.is_ready():
		return
	if Game.state != Game.State.PREP or Game.wave >= Game.total_waves():
		return
	var seq := Game.command(SimTypes.CMD_READY, 1 if want else 0)
	if seq >= 0:
		_add_pending(seq, "ready", 0, Vector2i(-1, -1), null, want)


func _pending_ready() -> bool:
	for seq: int in pending:
		if pending[seq]["what"] == "ready":
			return true
	return false


func _physics_process(_delta: float) -> void:
	if ready_wanted >= 0:
		if not Game.accepts_commands():
			ready_wanted = -1
		else:
			_send_ready()


## No order of mine is still waiting for its turn, nor a Ready still to be sent.
func settled() -> bool:
	return pending.is_empty() and ready_wanted < 0


## Orders whose turn will never come (the link is gone, or the match ended): their
## ghosts go and their gold is no longer held back.
func forget_pending() -> void:
	for seq: int in pending:
		var ghost: Node3D = pending[seq]["ghost"]
		if ghost and is_instance_valid(ghost):
			ghost.queue_free()
	pending.clear()
	ready_wanted = -1
	_count_pending()
	if map:
		_refresh_preview()
	selection_changed.emit(selected)


## An order that cannot go out: the error sound and why (when there is a why: a replay
## takes no orders and says nothing).
func _refuse(reason: String) -> void:
	Sfx.play("error")
	if reason != "":
		Game.notice(reason)


func _pending_on(cell: Vector2i, what: String) -> bool:
	for seq: int in pending:
		if pending[seq]["what"] == what and pending[seq]["cell"] == cell:
			return true
	return false


func _add_pending(
	seq: int, what: String, cost: int, cell: Vector2i, ghost: Node3D, on := false
) -> void:
	pending[seq] = {"what": what, "cost": cost, "cell": cell, "ghost": ghost, "on": on}
	_count_pending()


func _on_settled(seq: int, _accepted: bool) -> void:
	if not pending.has(seq):
		return
	var ghost: Node3D = pending[seq]["ghost"]
	if ghost and is_instance_valid(ghost):
		ghost.queue_free()
	pending.erase(seq)
	_count_pending()
	_refresh_preview()
	_send_ready()
	selection_changed.emit(selected)


func _count_pending() -> void:
	var total := 0
	for seq: int in pending:
		total += int(pending[seq]["cost"])
	Game.pending_gold = total
	Game.gold_changed.emit(Game.gold)


## A tower ordered but not yet built: its model, pale and breathing.
func _make_ghost(kind: String, cell: Vector2i) -> Node3D:
	var ghost := Models.instance(str(Game.TOWERS[kind]["model"]))
	ghost.name = "Pending_%d_%d" % [cell.x, cell.y]
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = Color(1.0, 0.93, 0.75, 0.45)
	for mi: MeshInstance3D in _meshes(ghost):
		mi.material_override = material
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ghost.position = terrain.surface(cell)
	add_child(ghost)
	var pulse := ghost.create_tween().set_loops()
	pulse.tween_property(material, "albedo_color:a", 0.2, 0.25)
	pulse.tween_property(material, "albedo_color:a", 0.45, 0.25)
	return ghost


func _hover(screen: Vector2) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	var cell := Vector2i(-1, -1)
	if direction.y < -0.001:
		var hit := origin + direction * (-origin.y / direction.y)
		cell = map.cell_at(hit)
	if cell != hover_cell:
		hover_cell = cell
		_refresh_preview()


func _refresh_preview() -> void:
	var show_cell := mode != "" and map.inside(hover_cell)
	if _ghost:
		_ghost.visible = show_cell
		if show_cell:
			var ok := can_build(mode, hover_cell)
			_ghost.position = terrain.surface(hover_cell)
			_ghost_material.albedo_color = (
				Color(0.4, 1.0, 0.45, 0.5) if ok else Color(1.0, 0.3, 0.25, 0.5)
			)
			terrain.set_hover(hover_cell, ok)
			_show_range(_ghost.position, float(Game.tower_stats(mode, 1)["range"]), ok)
			return
	terrain.set_hover(Vector2i(-100, -100), true)
	if selected and is_instance_valid(selected):
		_show_range(selected.global_position, selected.range_radius(), true)
	else:
		_range_ring.visible = false


func _show_range(at: Vector3, radius: float, ok: bool) -> void:
	_range_ring.visible = true
	_range_ring.position = Vector3(at.x, 0.06, at.z)
	_range_ring.scale = Vector3(radius, 1.0, radius)
	_range_material.albedo_color = Color(0.5, 1.0, 0.5, 0.6) if ok else Color(1.0, 0.4, 0.3, 0.6)


func _meshes(node: Node) -> Array:
	var found: Array = node.find_children("*", "MeshInstance3D", true, false)
	if node is MeshInstance3D:
		found.append(node)
	return found
