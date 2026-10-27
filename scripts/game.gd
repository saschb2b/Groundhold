## Game state and rules: gold, lives, waves, and the tower and creep tables.
##
## Autoloaded as `Game`. The scene's WaveDirector advances the waves; everything
## that changes gold or lives goes through here so the HUD and tests see one truth.
extends Node

signal gold_changed(gold: int)
signal lives_changed(lives: int)
signal wave_changed(wave: int)
signal state_changed(state: int)
signal announced(text: String)

enum State { PREP, WAVE, WON, LOST }

const START_GOLD := 120
const START_LIVES := 20
const FIRST_PREP := 15.0
const BETWEEN_WAVES := 10.0
const SELL_REFUND := 0.7
const HP_GROWTH_PER_WAVE := 0.22

const TOWERS := {
	"arrow":
	{
		"name": "Arrow Tower",
		"hotkey": "A",
		"description": "Quick bolts at the creep closest to the hearth.",
		"cost": 40,
		"damage": 8.0,
		"range": 3.2,
		"cooldown": 0.5,
		"projectile": "arrow",
		"speed": 14.0,
		"model": "res://models/towers/arrow_tower.glb",
		"model_2": "res://models/towers/arrow_tower_2.glb",
		"pennant": Vector3(0.016, 2.27, 0),
		"muzzle": Vector3(0, 1.08, 0.12),
		"icon": "res://ui/icons/arrow_tower.png",
		"upgrade": {"cost": 60, "damage": 16.0, "range": 3.6, "cooldown": 0.4},
	},
	"cannon":
	{
		"name": "Cannon Tower",
		"hotkey": "C",
		"description": "Slow shells that burst and hit every creep nearby.",
		"cost": 70,
		"damage": 20.0,
		"range": 3.0,
		"cooldown": 1.5,
		"projectile": "cannonball",
		"speed": 6.0,
		"splash": 1.1,
		"model": "res://models/towers/cannon_tower.glb",
		"model_2": "res://models/towers/cannon_tower_2.glb",
		"head": "res://models/towers/cannon_head.glb",
		"head_height": 0.77,
		"muzzle": Vector3(0, 1.04, 0),
		"icon": "res://ui/icons/cannon_tower.png",
		"upgrade": {"cost": 80, "damage": 40.0, "range": 3.3, "cooldown": 1.3, "splash": 1.35},
	},
	"frost":
	{
		"name": "Frost Spire",
		"hotkey": "F",
		"description": "Ice shards that slow creeps for two seconds.",
		"cost": 60,
		"damage": 4.0,
		"range": 2.8,
		"cooldown": 0.9,
		"projectile": "frost_shard",
		"speed": 9.0,
		"slow": 0.45,
		"slow_time": 2.0,
		"model": "res://models/towers/frost_tower.glb",
		"model_2": "res://models/towers/frost_tower_2.glb",
		"head": "res://models/towers/frost_head.glb",
		"head_height": 1.42,
		"muzzle": Vector3(0, 1.6, 0),
		"icon": "res://ui/icons/frost_tower.png",
		"upgrade": {"cost": 60, "damage": 8.0, "range": 3.2, "slow": 0.6},
	},
}

const CREEPS := {
	"gourdling":
	{
		"name": "Gourdling",
		"hp": 24.0,
		"speed": 1.3,
		"bounty": 3,
		"lives": 1,
		"model": "res://models/creeps/gourdling.glb",
		"scale": 1.5,
		"color": Color("#d9772b"),
	},
	"scuttler":
	{
		"name": "Scuttler",
		"hp": 16.0,
		"speed": 2.0,
		"bounty": 2,
		"lives": 1,
		"model": "res://models/creeps/scuttler.glb",
		"scale": 1.5,
		"color": Color("#6e4a82"),
	},
	"thornback":
	{
		"name": "Thornback",
		"hp": 80.0,
		"speed": 0.85,
		"bounty": 6,
		"lives": 2,
		"model": "res://models/creeps/thornback.glb",
		"scale": 1.35,
		"color": Color("#6b4a34"),
	},
	"hollow_king":
	{
		"name": "The Hollow King",
		"hp": 700.0,
		"speed": 0.6,
		"bounty": 60,
		"lives": 10,
		"model": "res://models/creeps/hollow_king.glb",
		"scale": 1.6,
		"color": Color("#b5541f"),
	},
}

## Each wave is a list of groups spawned one after another.
const WAVES := [
	[{"creep": "gourdling", "count": 8, "interval": 0.9}],
	[{"creep": "gourdling", "count": 12, "interval": 0.8}],
	[{"creep": "scuttler", "count": 12, "interval": 0.5}],
	[
		{"creep": "gourdling", "count": 8, "interval": 0.7},
		{"creep": "thornback", "count": 4, "interval": 1.4}
	],
	[{"creep": "scuttler", "count": 16, "interval": 0.45}],
	[{"creep": "thornback", "count": 8, "interval": 1.2}],
	[
		{"creep": "gourdling", "count": 12, "interval": 0.5},
		{"creep": "scuttler", "count": 10, "interval": 0.4}
	],
	[
		{"creep": "thornback", "count": 5, "interval": 1.0},
		{"creep": "hollow_king", "count": 1, "interval": 3.0}
	],
]

var gold := START_GOLD
var lives := START_LIVES
## 1-based index of the current or last wave; 0 before the first.
var wave := 0
var state: State = State.PREP
## Seconds until the next wave starts while in PREP.
var countdown := FIRST_PREP
var kills := 0
## Gameplay randomness (spawn jitter, effects); seeded so runs repeat exactly.
var rng := RandomNumberGenerator.new()


func _ready() -> void:
	reset()


func reset() -> void:
	gold = START_GOLD
	lives = START_LIVES
	wave = 0
	kills = 0
	countdown = FIRST_PREP
	rng.seed = 1
	set_state(State.PREP)
	gold_changed.emit(gold)
	lives_changed.emit(lives)
	wave_changed.emit(wave)


func total_waves() -> int:
	return WAVES.size()


func set_state(value: State) -> void:
	state = value
	state_changed.emit(state)


func can_afford(cost: int) -> bool:
	return gold >= cost


func spend(cost: int) -> bool:
	if gold < cost:
		return false
	gold -= cost
	gold_changed.emit(gold)
	return true


func earn(amount: int) -> void:
	gold += amount
	gold_changed.emit(gold)


func lose_lives(amount: int) -> void:
	if state == State.LOST or state == State.WON:
		return
	lives = maxi(0, lives - amount)
	lives_changed.emit(lives)
	if lives == 0:
		set_state(State.LOST)
		announce("The hearth has gone dark")


func announce(text: String) -> void:
	announced.emit(text)


## Creep health multiplier for a wave: later waves are tougher.
func hp_scale(for_wave: int) -> float:
	return 1.0 + HP_GROWTH_PER_WAVE * maxi(0, for_wave - 1)


## Tower stats at a level: the base table, with the upgrade applied at level 2.
func tower_stats(kind: String, level: int) -> Dictionary:
	var stats: Dictionary = TOWERS[kind].duplicate()
	if level >= 2:
		stats.merge(TOWERS[kind]["upgrade"], true)
	return stats
