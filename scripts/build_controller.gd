## Mouse and hotkeys on the battlefield: choose a tower, see where it fits, place
## it, select towers, upgrade and sell. HUD buttons call the same methods.
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
	"next_wave": KEY_N,
	"cancel": KEY_ESCAPE,
}

var map: HollowMap
var terrain: Terrain
var decor: Decor
var waves: WaveDirector
var tower_parent: Node3D
## Tower kind being placed, or "" when not building.
var mode := ""
var hover_cell := Vector2i(-1, -1)
var selected: Tower
var selected_creep: Creep
var towers := {}

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


func setup(
	source: HollowMap, ground: Terrain, scenery: Decor, director: WaveDirector, parent: Node3D
) -> void:
	map = source
	terrain = ground
	decor = scenery
	waves = director
	tower_parent = parent


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
			elif towers.has(hover_cell):
				select(towers.get(hover_cell))
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
	elif event.is_action_pressed("next_wave"):
		waves.start_next_wave()
	elif event.is_action_pressed("cancel"):
		set_mode("")
		select(null)


func set_mode(kind: String) -> void:
	if kind != "" and Game.state in [Game.State.WON, Game.State.LOST]:
		return
	if kind != "" and not Game.can_afford(int(Game.TOWERS[kind]["cost"])):
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
		map.buildable(cell)
		and not towers.has(cell)
		and Game.can_afford(int(Game.TOWERS[kind]["cost"]))
		and Game.state not in [Game.State.WON, Game.State.LOST]
	)


## Places a tower; returns false (and says why) when the cell or gold does not allow it.
func build(kind: String, cell: Vector2i) -> bool:
	if not can_build(kind, cell):
		Sfx.play("error")
		if not map.buildable(cell) or towers.has(cell):
			Game.notice("Cannot build there")
		else:
			Game.notice("Not enough gold")
		return false
	Game.spend(int(Game.TOWERS[kind]["cost"]))
	var tower := Tower.new()
	tower.name = "%s_%d_%d" % [kind, cell.x, cell.y]
	tower_parent.add_child(tower)
	tower.setup(kind, cell, terrain.surface(cell))
	towers[cell] = tower
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
	_refresh_preview()
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
	if selected == null or selected.upgrade_cost() < 0:
		return false
	if not Game.spend(selected.upgrade_cost()):
		Sfx.play("error")
		Game.notice("Not enough gold")
		return false
	selected.upgrade()
	Sfx.play("upgrade")
	_refresh_preview()
	selection_changed.emit(selected)
	return true


func sell_selected() -> bool:
	if selected == null:
		return false
	var tower := selected
	Game.earn(tower.sell_value())
	Fx.floating_text(
		get_tree(),
		tower.global_position + Vector3(0, 0.8, 0),
		"+%d" % tower.sell_value(),
		Color(1.0, 0.85, 0.3)
	)
	Fx.burst(
		get_tree(),
		tower.global_position + Vector3(0, 0.3, 0),
		Color(0.6, 0.5, 0.35, 0.9),
		16,
		1.5,
		0.08,
		0.6
	)
	towers.erase(tower.cell)
	tower.remove_from_group("towers")
	tower.queue_free()
	Sfx.play("sell")
	select(null)
	return true


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
			_show_range(_ghost.position, float(Game.TOWERS[mode]["range"]), ok)
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
