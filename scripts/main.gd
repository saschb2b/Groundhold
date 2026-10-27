## Assembles the hollow from the map file and wires the systems together.
##
## Helpers for tests and tools: cell_center(cell), build(kind, cell), tower_at(cell).
extends Node3D

const MAP_FILE := "res://data/hollow.txt"

var map: HollowMap

@onready var terrain: Terrain = $Terrain
@onready var decor: Decor = $Decor
@onready var creeps: Node3D = $Creeps
@onready var towers: Node3D = $Towers
@onready var waves: WaveDirector = $WaveDirector
@onready var controller: BuildController = $BuildController
@onready var hud: Hud = $Hud
@onready var camera: CameraRig = $Camera


func _ready() -> void:
	Game.reset()
	map = HollowMap.load_file(MAP_FILE)
	terrain.build(map)
	decor.build(map)
	_place_landmarks()
	waves.setup(map.path_points(), creeps)
	controller.setup(map, terrain, decor, waves, towers)
	hud.setup(self)
	_frame_camera()
	Game.announce("Lantern Hollow · the first creeps come in %d s" % int(Game.FIRST_PREP))


func _exit_tree() -> void:
	Models.clear_cache()
	Fx.clear_cache()


func cell_center(cell: Vector2i) -> Vector3:
	return map.center(cell)


func build(kind: String, cell: Vector2i) -> bool:
	return controller.build(kind, cell)


func tower_at(cell: Vector2i) -> Tower:
	return controller.towers.get(cell)


func _place_landmarks() -> void:
	var gate := Models.instance("res://models/props/rift_gate.glb")
	gate.name = "RiftGate"
	gate.position = map.center(map.spawn)
	gate.add_to_group("landmarks")
	add_child(gate)
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
	var fire := OmniLight3D.new()
	fire.light_color = Color(1.0, 0.7, 0.35)
	fire.light_energy = 2.2
	fire.omni_range = 3.5
	fire.position = Vector3(0, 1.1, 0)
	hearth.add_child(fire)


## Starts close enough to see the units, over the first stretch of road.
func _frame_camera() -> void:
	var rig := camera as CameraRig
	rig.setup(Rect2(0, 0, map.width, map.depth), Vector3(9.0, 0, 6.5), 12.5, 21.0)
