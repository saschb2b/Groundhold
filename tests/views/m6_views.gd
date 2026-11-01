## Helpers for M6's view scenarios (view_m6_*, view_two_hollows, race_*): the checks every M6
## tower form's view must pass, whether the views show what the records hold, and where the
## road runs.
##   {"eval": "resource('res://tests/views/m6_views.gd').form_problems(scene)", "as": "found"}
##   {"eval": "resource('res://tests/views/m6_views.gd').effects_off_records(scene)", "as": "off"}
##
## A race on the match scene is Tide Race's own preset, through begin() as any match:
##   {"eval": "scene.begin('tide_race', [{'team': 0, 'builder': 'lamplighter'}, {'team': 1,
##     'builder': 'lookout'}], 1, resource('res://scripts/net/local_sequencer.gd').new(2, 1), 1)"}
## and from the hub as the game plays it: Play in Tide Race races the caretaker
## (Session.play_offline), building both hollows from the start.
extends RefCounted

const M6_FORMS := [
	"clapper_tower", "toll_tower", "chime_post",
	"great_clapper", "ringing_clapper", "great_toll", "sky_toll", "deep_chime", "long_chime",
	"clay_hive", "apiary", "hive_hum",
	"great_clay_hive", "drowsy_clay_hive", "royal_apiary", "queens_guard", "great_hum", "long_hum",
]
const CLAPS := ["clapper_tower", "great_clapper", "ringing_clapper"]
const BEES := ["apiary", "royal_apiary", "queens_guard"]


## Every way the M6 effects on screen part from the records the simulation wrote this
## tick, as readable lines ([] when they agree): a creep's stars while it is stunned, its
## shimmer while it is cracked, a tower's hum glow while it is hastened, a Clay Hive's cloud
## over the creep its record names (while that creep's view lives) and none otherwise.
static func effects_off_records(scene: Node) -> Array:
	var out := []
	var tick := Game.sim.tick
	for node in scene.get_tree().get_nodes_in_group("creeps"):
		var creep := node as Creep
		if creep == null or creep.dead:
			continue
		var shown: Dictionary = creep.effects_shown()
		if bool(shown["stars"]) != (creep.rec.stun_until > tick):
			out.append("%s: stars %s, stunned until %d at %d" % [creep.name, shown["stars"], creep.rec.stun_until, tick])
		if bool(shown["shimmer"]) != (creep.rec.crack_c > 0):
			out.append("%s: shimmer %s, crack %d" % [creep.name, shown["shimmer"], creep.rec.crack_c])
	for node in scene.get_tree().get_nodes_in_group("towers"):
		var tower := node as Tower
		if tower == null or tower.rec == null:
			continue
		var shown: Dictionary = tower.effects_shown()
		if bool(shown["hum"]) != (tower.rec.haste_pm > 0):
			out.append("%s: hum %s, haste %d" % [tower.name, shown["hum"], tower.rec.haste_pm])
		if tower.rec.cloud_mm > 0:
			var over := tower.rec.cloud_creep
			var view: Creep = (scene.get("creep_views") as Dictionary).get(over)
			var live := view != null and is_instance_valid(view) and not view.dead
			if bool(shown["cloud"]) != live or (live and int(shown["cloud_over"]) != over):
				out.append("%s: cloud %s over %d, the record's %d" % [tower.name, shown["cloud"], shown["cloud_over"], over])
	return out


## Whether any creep (`what`: "stars", "shimmer") or tower ("hum", "cloud") shows that effect.
static func shown_anywhere(scene: Node, what: String) -> bool:
	var group := "creeps" if what in ["stars", "shimmer", "rune"] else "towers"
	for node in scene.get_tree().get_nodes_in_group(group):
		if node.has_method("effects_shown") and bool(node.call("effects_shown").get(what, false)):
			return true
	return false


## The first creep view showing `what` ("stars", "shimmer"), or null.
static func creep_showing(scene: Node, what: String) -> Node:
	for node in scene.get_tree().get_nodes_in_group("creeps"):
		var creep := node as Creep
		if creep and not creep.dead and bool(creep.effects_shown().get(what, false)):
			return creep
	return null


## Where each M6 form's muzzle must sit, measured on its model's recipe
## (art_src/models/towers/m6_kits.py; a model's units are the recipe's): the height span of
## the part a shot or a ring leaves from, and how far off the cell's centre it may stand
## (x, z). A bell between its lip and its crown (the toll's ring bursts there); the chimes
## between their feet and their hoop; a Clay Hive's middle rows of pipe mouths, at the
## front (z 0.30); an Apiary's top ring of bee holes, inside the house; a straw hive
## between its board and its cap.
const MUZZLE_SPANS := {
	"clapper_tower": [0.75, 1.10, Vector2(0, 0), 0.05],
	"great_clapper": [0.83, 1.26, Vector2(0, 0), 0.05],
	"ringing_clapper": [0.75, 1.10, Vector2(0, 0), 0.05],
	"toll_tower": [1.10, 1.42, Vector2(0, 0), 0.05],
	"great_toll": [1.06, 1.44, Vector2(0, 0), 0.05],
	"sky_toll": [1.80, 2.07, Vector2(0, 0), 0.05],
	"chime_post": [0.90, 1.32, Vector2(0, 0), 0.05],
	"deep_chime": [0.72, 1.42, Vector2(0, 0), 0.05],
	"long_chime": [1.00, 1.36, Vector2(0, 0), 0.05],
	"clay_hive": [0.34, 0.57, Vector2(0, 0.30), 0.03],
	"great_clay_hive": [0.31, 0.69, Vector2(0, 0.30), 0.03],
	"drowsy_clay_hive": [0.34, 0.57, Vector2(0, 0.30), 0.03],
	"apiary": [0.84, 0.92, Vector2(0, 0), 0.05],
	"royal_apiary": [1.09, 1.16, Vector2(0, 0), 0.05],
	"queens_guard": [0.80, 0.87, Vector2(0, 0), 0.05],
	"hive_hum": [0.44, 0.87, Vector2(0, 0), 0.05],
	"great_hum": [0.48, 1.05, Vector2(0, 0), 0.05],
	"long_hum": [1.18, 1.51, Vector2(0, 0), 0.05],
}


## Every M6 form whose muzzle (Game.TOWERS) sits off the part it belongs to (MUZZLE_SPANS)
## or outside its model's own height, as readable lines; [] when all sit right.
static func muzzle_problems() -> Array:
	var out := []
	for form: String in M6_FORMS:
		var spec: Array = MUZZLE_SPANS[form]
		var muzzle: Vector3 = Game.TOWERS[form].get("muzzle", Vector3(0, -1, 0))
		if muzzle.y < float(spec[0]) or muzzle.y > float(spec[1]):
			out.append("%s's muzzle at %.2f, not between %.2f and %.2f" % [form, muzzle.y, spec[0], spec[1]])
		var off := Vector2(muzzle.x, muzzle.z).distance_to(spec[2])
		if off > float(spec[3]):
			out.append("%s's muzzle %.2f off (%.2f, %.2f)" % [form, off, spec[2].x, spec[2].y])
		var model := Tower.model_of(form)
		var top := 0.0
		for mesh: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
			top = maxf(top, mesh.get_aabb().end.y)
		model.free()
		if muzzle.y > top:
			out.append("%s's muzzle at %.2f, over its model's top %.2f" % [form, muzzle.y, top])
	return out


## How loud a sound file plays at its loudest: the RMS of its loudest tenth of a second, in
## dB of full scale (a 16-bit PCM WAV, read from the project's file: the import is
## compressed). A sound's level as people hear a shot is this plus the gain it is played at.
static func loudest_db(path: String) -> float:
	var bytes := FileAccess.get_file_as_bytes(path)
	var channels := 1
	var rate := 44100
	var at := -1
	var length := 0
	var pos := 12
	while pos + 8 <= bytes.size():
		var id := bytes.slice(pos, pos + 4).get_string_from_ascii()
		var size := bytes.decode_u32(pos + 4)
		if id == "fmt ":
			channels = bytes.decode_u16(pos + 10)
			rate = bytes.decode_u32(pos + 12)
		elif id == "data":
			at = pos + 8
			length = mini(size, bytes.size() - at)
			break
		pos += 8 + size + size % 2
	if at < 0:
		return -INF
	@warning_ignore("integer_division")
	var count := length / 2
	@warning_ignore("integer_division")
	var window := rate * channels / 10
	@warning_ignore("integer_division")
	var hop := maxi(1, window / 4)
	var best := 0.0
	var start := 0
	while start < maxi(1, count - window):
		var sum := 0.0
		var end := mini(count, start + window)
		for i in range(start, end):
			var v := bytes.decode_s16(at + 2 * i) / 32768.0
			sum += v * v
		best = maxf(best, sqrt(sum / maxi(1, end - start)))
		start += hop
	return 20.0 * log(best) / log(10.0) if best > 0.0 else -INF


## Every tower form's sound as played, in dB: the mean of its takes' loudest_db() plus the
## gain Game.TOWERS gives it.
static func sound_levels() -> Dictionary:
	var out := {}
	var files := {}
	for form: String in Game.TOWERS:
		var sound: Array = Game.TOWERS[form].get("sound", [])
		if sound.is_empty():
			continue
		var name := str(sound[0])
		if not files.has(name):
			var total := 0.0
			var takes: Array = Sfx.SOUNDS.get(name, [])
			for path: String in takes:
				total += loudest_db(path)
			files[name] = total / maxi(1, takes.size())
		out[form] = float(files[name]) + float(sound[1])
	return out


## Every M6 form whose sound plays more than `room` dB from the M2 towers' (their median as
## played), as readable lines; [] when all sit level.
static func sound_level_problems(room := 3.0) -> Array:
	var levels := sound_levels()
	var others := []
	for form: String in levels:
		if not M6_FORMS.has(form):
			others.append(levels[form])
	others.sort()
	@warning_ignore("integer_division")
	var mid := others.size() / 2
	var median: float = others[mid] if others.size() % 2 == 1 else (others[mid - 1] + others[mid]) * 0.5
	var out := []
	for form: String in M6_FORMS:
		var level: float = levels.get(form, -INF)
		if absf(level - median) > room:
			out.append("%s plays at %.1f dB, the M2 towers at %.1f" % [form, level, median])
	return out


## A small red bead at every tower's muzzle (test captures only), to see where shots and
## rings leave from.
static func mark_muzzles(scene: Node) -> int:
	var marked := 0
	for node in scene.get_tree().get_nodes_in_group("towers"):
		var tower := node as Tower
		var bead := MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius = 0.045
		sphere.height = 0.09
		var red := StandardMaterial3D.new()
		red.albedo_color = Color(1, 0.1, 0.1)
		red.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		red.no_depth_test = true
		sphere.material = red
		bead.mesh = sphere
		bead.name = "MuzzleBead"
		scene.add_child(bead)
		bead.global_position = tower.muzzle_point()
		marked += 1
	return marked


## Every way an M6 form's view breaks the contract (contract-m6.md §5), as readable lines:
## each of the eighteen forms stands on the board (the scene's towers) as its own model, or
## as the stand-in while its art is missing, with no head, a muzzle, a sound, and the
## clap or the bee where it fires; its placement ghost builds; and the Bellfounder and the
## Beekeeper are fielded as themselves.
static func form_problems(scene: Node) -> Array:
	var out := []
	var shown := {}
	for node in scene.get_tree().get_nodes_in_group("towers"):
		shown[str(node.get("form"))] = node
	for form: String in M6_FORMS:
		var data: Dictionary = Game.TOWERS.get(form, {})
		var model := str(data.get("model", ""))
		if model != "res://models/towers/%s.glb" % form:
			out.append("%s's model is %s, not models/towers/%s.glb" % [form, model, form])
		if data.has("head"):
			out.append("%s turns a head" % form)
		if not data.has("muzzle") and not data.has("bore"):
			out.append("%s has no muzzle" % form)
		if (data.get("sound", []) as Array).size() != 2:
			out.append("%s has no sound" % form)
		if CLAPS.has(form) and str(data.get("projectile", "")) != "clap":
			out.append("%s does not strike with a clap" % form)
		if BEES.has(form) and str(data.get("projectile", "")) != "bee":
			out.append("%s does not fire bees" % form)
		if not CLAPS.has(form) and not BEES.has(form) and data.has("projectile"):
			out.append("%s fires a %s, but works without a shot" % [form, data["projectile"]])
		var ghost := Tower.model_of(form) if model != "" else null
		if ghost == null:
			out.append("%s has no placement ghost" % form)
		else:
			ghost.free()
		var view: Node = shown.get(form)
		if view == null:
			out.append("%s does not stand on the board" % form)
			continue
		var base: Node3D = view.get("_base")
		var built := ResourceLoader.exists(model)
		if built and (base == null or base.scene_file_path != model):
			out.append("%s does not stand as its model" % form)
		if not built and (base == null or base.name != "Placeholder"):
			out.append("%s's art is missing but it does not stand as the stand-in" % form)
		if view.get("_head") != null:
			out.append("%s's view seats a head" % form)
	for builder: String in ["bellfounder", "beekeeper"]:
		if Profile.fielded(builder) != builder:
			out.append("%s is fielded as %s" % [builder, Profile.fielded(builder)])
	return out


## A projectile or a sound not made yet is harmless (contract-m6.md §5): a stand-in bead
## flies, a missing sound plays as silence. [] when both hold, for a name that will never
## exist and for M6's own (bee, toll, chime, bees, clap) whichever way their art stands.
static func stand_in_problems() -> Array:
	var out := []
	var bead := Projectile.model_for("never_built")
	if bead == null or bead.name != "StandIn":
		out.append("a shot without a model does not fly the stand-in")
	if bead:
		bead.free()
	var bee := Projectile.model_for("bee")
	var bee_built := ResourceLoader.exists(str(Projectile.MODELS.get("bee", "")))
	if bee == null or (bee.name == "StandIn") == bee_built:
		out.append("the bee does not fly %s" % ("its model" if bee_built else "the stand-in"))
	if bee:
		bee.free()
	for name: String in ["never_recorded", "toll", "chime", "bees", "clap"]:
		Sfx.play(name, -80.0)
		var recorded := ResourceLoader.exists("res://sfx/%s.wav" % name)
		if Sfx.has_sound(name) != recorded:
			out.append("Sfx.has_sound(%s) is %s, but its file %s" % [name, not recorded, "is missing" if not recorded else "exists"])
	return out


## Pieces of decor standing on the cliff band between the hollows.
static func band_decor(scene: Node) -> int:
	var decor: Decor = scene.get("decor")
	var map: HollowMap = scene.get("map")
	var total := 0
	for z in map.depth:
		for x in range(map.width, Game.HOLLOW_STRIDE):
			total += decor.count_on(Vector2i(x, z))
	return total


## How far apart two points stand on the ground, height aside; each a Vector3 or a Node3D
## (its global position).
static func ground_gap(a: Variant, b: Variant) -> float:
	var p: Vector3 = (a as Node3D).global_position if a is Node3D else a
	var q: Vector3 = (b as Node3D).global_position if b is Node3D else b
	return Vector2(p.x - q.x, p.z - q.z).length()


## How far a creep view stands from where its own hollow's road puts it at its distance.
static func off_its_road(creep: Node) -> float:
	var rec: SimRecords.SimCreep = creep.get("rec")
	var road := Game.sim.hollows[rec.hollow].road
	var at := Game.world_at(rec.hollow, road.x_at(rec.dist_um), road.z_at(rec.dist_um))
	var p: Vector3 = (creep as Node3D).global_position
	return Vector2(p.x - at.x, p.z - at.z).length()
