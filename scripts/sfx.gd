## Sound effects by name, from a small pool of players. Autoloaded as `Sfx`.
##
## The same sound is not restarted more than once per 3 physics frames, so a
## volley of arrows reads as a volley instead of a wall of noise. Counting frames
## instead of wall-clock time keeps what plays identical between runs.
##
## A sound whose file is not recorded yet (M6's, before the art track's land) plays as
## silence, never an error: only the files that exist are loaded, and a name with none
## plays nothing (has_sound() says which).
##
## Every caller gives its own gain: a tower's is Game.TOWERS' "sound" [name, dB]. As played
## (the file's loudest tenth of a second plus that gain) the towers sit between about -19
## and -11 dB, a frequent shot quieter, a heavy one louder; the M6 files (toll, chime, bees,
## clap) are played at gains that keep them in that band (view_m6_sound_levels).
extends Node

const SOUNDS := {
	"arrow": ["res://sfx/arrow_1.wav", "res://sfx/arrow_2.wav", "res://sfx/arrow_3.wav"],
	"cannon": ["res://sfx/cannon.wav"],
	"mortar": ["res://sfx/mortar.wav"],
	"ballista": ["res://sfx/ballista.wav"],
	"hawk": ["res://sfx/hawk.wav"],
	"mark": ["res://sfx/mark.wav"],
	"explosion": ["res://sfx/explosion_1.wav", "res://sfx/explosion_2.wav"],
	"frost": ["res://sfx/frost_1.wav", "res://sfx/frost_2.wav"],
	"hit": ["res://sfx/hit_1.wav", "res://sfx/hit_2.wav", "res://sfx/hit_3.wav"],
	"creep_death": ["res://sfx/creep_death_1.wav", "res://sfx/creep_death_2.wav"],
	"coin": ["res://sfx/coin.wav"],
	"build": ["res://sfx/build.wav"],
	"upgrade": ["res://sfx/upgrade.wav"],
	"sell": ["res://sfx/sell.wav"],
	"wave": ["res://sfx/wave_horn.wav"],
	"leak": ["res://sfx/leak.wav"],
	"victory": ["res://sfx/victory.wav"],
	"defeat": ["res://sfx/defeat.wav"],
	"error": ["res://sfx/error.wav"],
	"click": ["res://sfx/click.wav"],
	# M6 (contract-m6.md §7): the Bellfounder's and the Beekeeper's towers, and the queue's
	# Match Found and its countdown (scripts/ui/match_found.gd)
	"toll": ["res://sfx/toll.wav"],
	"chime": ["res://sfx/chime.wav"],
	"bees": ["res://sfx/bees.wav"],
	"clap": ["res://sfx/clap.wav"],
	"match_found": ["res://sfx/match_found.wav"],
	"countdown_tick": ["res://sfx/countdown_tick.wav"],
	# M7 (contract-m7.md §3): the duel's cork and uncorking, a breach, the Seawall's surf
	"cork": ["res://sfx/cork.wav"],
	"uncork": ["res://sfx/uncork.wav"],
	"breach": ["res://sfx/breach.wav"],
	"seawall": ["res://sfx/seawall.wav"],
}
const POOL_SIZE := 12
const MIN_GAP_FRAMES := 3

var _streams := {}
var _players: Array[AudioStreamPlayer] = []
var _next := 0
var _last_played := {}
## Its own generator, apart from the simulation's, so sound choices never touch the rules.
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = 7
	process_mode = Node.PROCESS_MODE_ALWAYS
	for name: String in SOUNDS:
		var streams: Array[AudioStream] = []
		for path: String in SOUNDS[name]:
			if ResourceLoader.exists(path):
				streams.append(load(path))
		_streams[name] = streams
	for i in POOL_SIZE:
		var player := AudioStreamPlayer.new()
		add_child(player)
		_players.append(player)


## Whether `name` has a recorded take to play.
func has_sound(name: String) -> bool:
	return not (_streams.get(name, []) as Array).is_empty()


func play(name: String, volume_db := 0.0) -> void:
	var streams: Array = _streams.get(name, [])
	if streams.is_empty():
		return
	var now := Engine.get_physics_frames()
	if now - int(_last_played.get(name, -1000)) < MIN_GAP_FRAMES:
		return
	_last_played[name] = now
	var player := _players[_next]
	_next = (_next + 1) % _players.size()
	player.stream = streams[_rng.randi() % streams.size()]
	player.volume_db = volume_db
	player.pitch_scale = _rng.randf_range(0.94, 1.06)
	player.play()
