## M2's art has landed (design 3.7, contract §5): every icon the display tables name, and
## the command card's Signal, is painted at its size, every new model and sound loads, and the Duskmoth flaps and glows
## by emission alone. A scenario runs it:
##   {"eval": "resource('res://tests/sim/art_m2_painted.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
## The model paths are the art's own; game.gd's display tables point at them (M2).
extends RefCounted

## Every tower form's model, and the heads the view seats and turns on some of them.
const TOWER_MODELS := [
	"skyward_loft", "iron_mortar", "iron_mortar_head", "rime_spire", "rime_spire_head",
	"perch_ballista", "perch_ballista_head", "siege_perch", "siege_perch_head",
	"pinning_ballista", "pinning_ballista_head", "hawk_roost", "falcon_roost", "kestrel_flock",
	"owls_eye", "owls_eye_head", "owls_glare", "owls_glare_head", "twin_gaze", "twin_gaze_head",
]
const PROJECTILES := ["ballista_bolt", "pinning_bolt", "hawk", "kestrel", "mortar_shell"]
const SOUNDS := ["ballista", "hawk", "mortar", "mark"]
const CREEP_PORTRAITS := ["duskmoth", "bristlesow"]
## Command icons and Builders' emblems are painted at twice their 54 px socket; marks at
## 64; a Builder's glyph (its framed face, rendered from M3's bust) at 128.
const COMMAND_SIZE := 108
const MARK_SIZE := 64
const FACE_SIZE := 128


## Every way the art falls short, as readable lines; [] when it has all landed.
static func problems() -> Array:
	var out := []
	_icons(out)
	_models(out)
	_duskmoth(out)
	return out


static func _icons(out: Array) -> void:
	for id: String in SimContent.TOWER_IDS:
		_painted(out, str(Game.TOWERS.get(id, {}).get("icon", "")), COMMAND_SIZE)
	for check: String in SimContent.CHECK_IDS:
		_painted(out, str(Game.CHECKS.get(check, {}).get("icon", "")), MARK_SIZE)
	for role: String in SimContent.ROLE_IDS:
		_painted(out, str(Game.ROLES.get(role, {}).get("icon", "")), MARK_SIZE)
	for builder: String in SimContent.BUILDER_IDS:
		_painted(out, str(Game.BUILDERS.get(builder, {}).get("glyph", "")), FACE_SIZE)
		_painted(out, str(Game.BUILDERS.get(builder, {}).get("emblem", "")), COMMAND_SIZE)
	for creep: String in CREEP_PORTRAITS:
		_painted(out, Game.ICON_DIR + creep + ".png", MARK_SIZE)
	# (the card's A slot: Signal sits beside the painted Q W E, Sell and the war horn)
	_painted(out, Game.SIGNAL_ICON, COMMAND_SIZE)


static func _painted(out: Array, path: String, size: int) -> void:
	if not Game.has_art(path):
		out.append("%s is not painted" % path)
		return
	var texture := Game.icon(path)
	if texture == Game.placeholder_icon():
		out.append("%s loads as the placeholder" % path)
	elif texture.get_width() != size or texture.get_height() != size:
		out.append("%s is %dx%d, not %d" % [path, texture.get_width(), texture.get_height(), size])


static func _models(out: Array) -> void:
	var paths := []
	for name: String in TOWER_MODELS:
		paths.append("res://models/towers/%s.glb" % name)
	for name: String in PROJECTILES:
		paths.append("res://models/projectiles/%s.glb" % name)
	paths.append("res://models/creeps/bristlesow.glb")
	for path: String in paths:
		if not ResourceLoader.exists(path):
			out.append("%s is missing" % path)
			continue
		var scene := load(path) as PackedScene
		if scene == null:
			out.append("%s does not load as a scene" % path)
			continue
		var node := scene.instantiate()
		if node.find_children("*", "MeshInstance3D", true, false).is_empty() and not node is MeshInstance3D:
			out.append("%s has no mesh" % path)
		node.free()
	for name: String in SOUNDS:
		var path := "res://sfx/%s.wav" % name
		if not ResourceLoader.exists(path) or not load(path) is AudioStreamWAV:
			out.append("%s is missing" % path)


## The Duskmoth hovers and flaps: a looping 'walk' that moves its wings, an emissive
## material for its glow, and no light of its own (WebGL 2 allows few; design 2.4).
static func _duskmoth(out: Array) -> void:
	var path := "res://models/creeps/duskmoth.glb"
	if not ResourceLoader.exists(path):
		out.append("%s is missing" % path)
		return
	var moth := (load(path) as PackedScene).instantiate()
	var players := moth.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty() or not (players[0] as AnimationPlayer).has_animation("walk"):
		out.append("the Duskmoth has no 'walk' (flap) animation")
	else:
		var walk := (players[0] as AnimationPlayer).get_animation("walk")
		var wing_tracks := 0
		for t in walk.get_track_count():
			var track := str(walk.track_get_path(t))
			if track.contains("fore_") or track.contains("hind_"):
				wing_tracks += 1
		if wing_tracks < 4:
			out.append("the Duskmoth's flap moves %d wing tracks, not all four wings" % wing_tracks)
	if not moth.find_children("*", "Light3D", true, false).is_empty():
		out.append("the Duskmoth carries a light; its glow must be emission only")
	var glowing := false
	for mesh_node: MeshInstance3D in moth.find_children("*", "MeshInstance3D", true, false):
		for s in mesh_node.mesh.get_surface_count():
			var material := mesh_node.get_active_material(s)
			if material is BaseMaterial3D and (material as BaseMaterial3D).emission_enabled:
				glowing = true
	if not glowing:
		out.append("the Duskmoth has no emissive glow")
	moth.free()
