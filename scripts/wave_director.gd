## Runs the waves: the build countdown, spawning each group at the rift gate,
## bounties and leaks, the wave-clear bonus, victory and defeat.
class_name WaveDirector
extends Node

signal creep_spawned(creep: Creep)

## Gold for clearing a wave: base plus a little per wave number.
const CLEAR_BONUS := 8
const CLEAR_BONUS_PER_WAVE := 2

var path := PackedVector3Array()
var creep_parent: Node3D
## Pending spawns for the current wave: [kind, seconds to wait before it].
var _queue: Array = []
var _spawn_wait := 0.0
var _spawned := 0


func setup(points: PackedVector3Array, parent: Node3D) -> void:
	path = points
	creep_parent = parent


func _physics_process(delta: float) -> void:
	match Game.state:
		Game.State.PREP:
			Game.countdown -= delta
			if Game.countdown <= 0.0:
				start_next_wave()
		Game.State.WAVE:
			_spawn_wait -= delta
			while not _queue.is_empty() and _spawn_wait <= 0.0:
				var entry: Array = _queue.pop_front()
				_spawn(str(entry[0]))
				_spawn_wait += float(_queue[0][1]) if not _queue.is_empty() else 0.0
			if _queue.is_empty() and get_tree().get_nodes_in_group("creeps").is_empty():
				_wave_cleared()


## Starts the next wave now. Calling it early during the countdown pays the
## seconds left as gold.
func start_next_wave() -> bool:
	if Game.state != Game.State.PREP or Game.wave >= Game.total_waves():
		return false
	var early := int(Game.countdown)
	if early > 0:
		Game.earn(early)
	Game.wave += 1
	Game.countdown = 0.0
	_queue.clear()
	for group: Dictionary in Game.WAVES[Game.wave - 1]:
		for i in int(group["count"]):
			_queue.append([group["creep"], float(group["interval"])])
	_spawn_wait = 0.0
	_spawned = 0
	Game.set_state(Game.State.WAVE)
	Game.wave_changed.emit(Game.wave)
	var first: String = Game.WAVES[Game.wave - 1][0]["creep"]
	var title := "Wave %d · %s" % [Game.wave, Game.CREEPS[first]["name"]]
	if Game.wave == Game.total_waves():
		title = "Final wave · The Hollow King"
	Game.announce(title)
	Sfx.play("wave", -6.0)
	return true


## Creeps still to come this wave plus those on the road.
func remaining() -> int:
	return _queue.size() + get_tree().get_nodes_in_group("creeps").size()


func _spawn(kind: String) -> void:
	var creep := Creep.new()
	creep.name = "%s_%d_%d" % [kind, Game.wave, _spawned]
	_spawned += 1
	creep.setup(kind, path, Game.hp_scale(Game.wave))
	creep.died.connect(_on_creep_died)
	creep.leaked.connect(_on_creep_leaked)
	creep_parent.add_child(creep)
	Fx.burst(
		get_tree(), path[0] + Vector3(0, 0.4, 0), Color(0.75, 0.5, 1.0), 10, 1.5, 0.06, 0.5, 0.5
	)
	creep_spawned.emit(creep)


func _on_creep_died(creep: Creep) -> void:
	Game.kills += 1
	Game.earn(creep.bounty)
	Sfx.play("coin", -8.0)


func _on_creep_leaked(creep: Creep) -> void:
	Game.lose_lives(creep.lives_cost)
	if Game.state == Game.State.LOST:
		Sfx.play("defeat")
		_queue.clear()


func _wave_cleared() -> void:
	if Game.state != Game.State.WAVE:
		return
	var bonus := CLEAR_BONUS + CLEAR_BONUS_PER_WAVE * Game.wave
	Game.earn(bonus)
	if Game.wave >= Game.total_waves():
		Game.set_state(Game.State.WON)
		Game.announce("The hearth burns on. Victory!")
		Sfx.play("victory")
		return
	Game.countdown = Game.BETWEEN_WAVES
	Game.set_state(Game.State.PREP)
	Game.announce("Wave %d cleared · +%d gold" % [Game.wave, bonus])
