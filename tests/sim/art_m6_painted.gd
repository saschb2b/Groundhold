## M6's art has landed (contract-m6.md §5 and §7): the Bellfounder's and the Beekeeper's eighteen tower forms each
## have a model at models/towers/<form>.glb standing on the ground inside its tile, a command icon painted at its
## size and the icon-only model it was rendered from; both Builders are one toon-shaded figure and bust each, a
## glyph and an emblem; the Apiary's bee and the six new sounds load. Every M6 model also keeps to its rules in
## asset_style.json, as `godot-agent asset check` reads them (CI runs the scenarios, not the asset check): its
## triangle budget, size and number of materials, and every vertex colour a paint of its palette; and each model the
## kit built from a recipe was built from the recipe on disk (asset_manifest.json keeps the recipe it was built from,
## and `asset regen` builds from that), so a recipe changed without its model rebuilt shows here.
## `python3 art_src/models/towers/m6_kits.py --check` holds the recipes to the script that writes them.
## A scenario runs it:
##   {"eval": "resource('res://tests/sim/art_m6_painted.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
## The paths are the contract's; game.gd's display tables point at them (track C).
extends RefCounted

## The M6 ids: TOWER_IDS 18 to 35 and BUILDER_IDS 2 and 3 (contract-m6.md §1).
const FIRST_M6_TOWER := 18
const M6_TOWERS := 18
const M6_BUILDERS := ["bellfounder", "beekeeper"]
const PROJECTILES := ["bee"]
const SOUNDS := ["toll", "chime", "bees", "clap", "match_found", "countdown_tick"]
## Command icons and emblems are painted at twice their 54 px socket; a Builder's glyph at 128.
const COMMAND_SIZE := 108
const FACE_SIZE := 128
## A tower stands on its tile (one unit) under the style's 2.4 height; a Builder is a chibi figure's height.
const TILE := 0.98
const TOWER_HEIGHT := 2.4
const TOON := "res://materials/builder_toon.tres"
## The emblems' props (models/ui/<prop>.glb), rendered for ui/icons/emblem_<builder>.png.
const EMBLEM_PROPS := ["hand_bell", "bee_smoker"]
const STYLE := "res://asset_style.json"
const MANIFEST := "res://asset_manifest.json"
## glTF's chunk kinds, and the colour component types the kit (float) and Blender (unsigned short) write, by size.
const GLB_MAGIC := 0x46546C67
const CHUNK_JSON := 0x4E4F534A
const CHUNK_BIN := 0x004E4942
const FLOAT := 5126
const USHORT := 5123
const UBYTE := 5121
const COMPONENT_BYTES := {FLOAT: 4, USHORT: 2, UBYTE: 1}


## Every way the art falls short, as readable lines; [] when it has all landed.
static func problems() -> Array:
	var out := []
	var forms := forms_m6()
	if forms.size() != M6_TOWERS:
		out.append("TOWER_IDS holds %d M6 forms, not %d" % [forms.size(), M6_TOWERS])
	for form: String in forms:
		_painted(out, Game.ICON_DIR + form + ".png", COMMAND_SIZE)
		_tower(out, "res://models/towers/%s.glb" % form)
		_scene(out, "res://models/ui/towers/%s.glb" % form)
	for builder: String in M6_BUILDERS:
		if not SimContent.BUILDER_IDS.has(builder):
			out.append("BUILDER_IDS lacks %s" % builder)
		_painted(out, Game.ICON_DIR + "builder_%s.png" % builder, FACE_SIZE)
		_painted(out, Game.ICON_DIR + "emblem_%s.png" % builder, COMMAND_SIZE)
		_figure(out, "res://models/builders/%s.glb" % builder, 0.8, 1.5)
		_figure(out, "res://models/builders/%s_bust.glb" % builder, 0.3, 0.9)
	for name: String in PROJECTILES:
		_scene(out, "res://models/projectiles/%s.glb" % name)
	for name: String in SOUNDS:
		_sound(out, "res://sfx/%s.wav" % name)
	var style: Variant = JSON.parse_string(FileAccess.get_file_as_string(STYLE))
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
	if not (style is Dictionary and manifest is Dictionary):
		out.append("asset_style.json or asset_manifest.json does not parse")
		return out
	for rel: String in models_m6():
		if ResourceLoader.exists("res://" + rel):   # (a missing model is reported above)
			_styled(out, rel, style)
			_built(out, rel, manifest)
	return out


## Every M6 model, as the style file and the manifest name it.
static func models_m6() -> Array:
	var out := []
	for form: String in forms_m6():
		out.append("models/towers/%s.glb" % form)
		out.append("models/ui/towers/%s.glb" % form)
	for builder: String in M6_BUILDERS:
		out.append("models/builders/%s.glb" % builder)
		out.append("models/builders/%s_bust.glb" % builder)
	for prop: String in EMBLEM_PROPS:
		out.append("models/ui/%s.glb" % prop)
	for name: String in PROJECTILES:
		out.append("models/projectiles/%s.glb" % name)
	return out


## The Bellfounder's and the Beekeeper's forms, in TOWER_IDS order.
static func forms_m6() -> Array:
	return SimContent.TOWER_IDS.slice(FIRST_M6_TOWER, FIRST_M6_TOWER + M6_TOWERS)


static func _painted(out: Array, path: String, size: int) -> void:
	if not Game.has_art(path):
		out.append("%s is not painted" % path)
		return
	var texture := Game.icon(path)
	if texture == Game.placeholder_icon():
		out.append("%s loads as the placeholder" % path)
	elif texture.get_width() != size or texture.get_height() != size:
		out.append("%s is %dx%d, not %d" % [path, texture.get_width(), texture.get_height(), size])


## The scene's meshes, or [] (with a line in `out`) when it is missing or has none.
static func _meshes(out: Array, path: String) -> Array:
	if not ResourceLoader.exists(path):
		out.append("%s is missing" % path)
		return []
	var scene := load(path) as PackedScene
	if scene == null:
		out.append("%s does not load as a scene" % path)
		return []
	var node := scene.instantiate()
	var meshes := node.find_children("*", "MeshInstance3D", true, false)
	if node is MeshInstance3D:
		meshes.append(node)
	var found := []
	for m: MeshInstance3D in meshes:
		found.append([m.mesh, m.get_active_material(0), m.transform])
	node.free()
	if found.is_empty():
		out.append("%s has no mesh" % path)
	return found


static func _scene(out: Array, path: String) -> void:
	_meshes(out, path)


## The box round every mesh of a model, in the model's own space.
static func _bounds(meshes: Array) -> AABB:
	var box := AABB()
	for k in meshes.size():
		var part: AABB = (meshes[k][2] as Transform3D) * (meshes[k][0] as Mesh).get_aabb()
		box = part if k == 0 else box.merge(part)
	return box


## A tower stands on the ground, inside its tile, under the height limit.
static func _tower(out: Array, path: String) -> void:
	var meshes := _meshes(out, path)
	if meshes.is_empty():
		return
	var box := _bounds(meshes)
	if absf(box.position.y) > 0.02:
		out.append("%s does not stand on the ground (its foot at %.3f)" % [path, box.position.y])
	if box.size.x > TILE or box.size.z > TILE:
		out.append("%s spills off its tile (%.2f x %.2f)" % [path, box.size.x, box.size.z])
	if box.size.y > TOWER_HEIGHT or box.size.y < 0.6:
		out.append("%s is %.2f tall, not a tower's height" % [path, box.size.y])


## A Builder model: one mesh in the Builders' toon material, standing on the ground, its footprint centred, as tall
## as a chibi figure (a bust: as its portrait frames it).
static func _figure(out: Array, path: String, low: float, high: float) -> void:
	var meshes := _meshes(out, path)
	if meshes.is_empty():
		return
	if meshes.size() != 1:
		out.append("%s is %d meshes, not one" % [path, meshes.size()])
	var material: Material = meshes[0][1]
	if material == null or material.resource_path != TOON:
		out.append("%s does not wear %s" % [path, TOON])
	var box := _bounds(meshes)
	if absf(box.position.y) > 0.02:
		out.append("%s does not stand on the ground (its foot at %.3f)" % [path, box.position.y])
	if absf(box.get_center().x) > 0.12 or absf(box.get_center().z) > 0.12:
		out.append("%s is not centred on its pivot" % path)
	if box.size.y < low or box.size.y > high:
		out.append("%s is %.2f tall, not %.1f to %.1f" % [path, box.size.y, low, high])


static func _sound(out: Array, path: String) -> void:
	if not ResourceLoader.exists(path):
		out.append("%s is missing" % path)
		return
	var stream := load(path) as AudioStreamWAV
	if stream == null:
		out.append("%s does not load as a sound" % path)
	elif stream.get_length() <= 0.0 or stream.get_length() > 1.6:
		out.append("%s lasts %.2f s, not up to 1.6" % [path, stream.get_length()])


# ── The style's rules, as `godot-agent asset check` reads them ──

## A model keeps to its merged rule: triangles, size, materials and palette.
static func _styled(out: Array, rel: String, style: Dictionary) -> void:
	var rule := rule_for(style, rel, "model")
	var glb := _glb("res://" + rel)
	if glb.is_empty():
		out.append("%s is not a glTF binary" % rel)
		return
	var doc: Dictionary = glb["doc"]
	var tris := 0
	var colors := {}
	var painted := false
	for mesh_index: int in _mesh_uses(doc):
		for prim: Dictionary in doc["meshes"][mesh_index]["primitives"]:
			if int(prim.get("mode", 4)) != 4:
				continue
			var attributes: Dictionary = prim["attributes"]
			var counted: int = int(prim["indices"]) if prim.has("indices") else int(attributes["POSITION"])
			tris += int(doc["accessors"][counted]["count"]) / 3
			if attributes.has("COLOR_0"):
				painted = true
				for rgb: Array in _colors(glb, int(attributes["COLOR_0"])):
					colors["%d,%d,%d" % rgb] = rgb
	if rule.has("max_tris") and tris > int(rule["max_tris"]):
		out.append("%s has %d triangles, over its %d" % [rel, tris, int(rule["max_tris"])])
	var materials: int = (doc.get("materials", []) as Array).size()
	if rule.has("max_materials") and materials > int(rule["max_materials"]):
		out.append("%s has %d materials, over its %d" % [rel, materials, int(rule["max_materials"])])
	if rule.has("max_size"):
		var size := _bounds(_meshes(out, "res://" + rel)).size
		var limit: Array = rule["max_size"]
		for axis in 3:
			if limit[axis] != null and snappedf(size[axis], 0.001) > float(limit[axis]):
				out.append("%s is %.3f along %s, over its %.2f" % [rel, size[axis], "xyz"[axis], float(limit[axis])])
	if not rule.has("palette"):
		return
	if not painted:
		out.append("%s carries no vertex colours, so its palette cannot be held" % rel)
		return
	var palette := _palette(style, String(rule["palette"]))
	var tolerance := float(rule.get("palette_tolerance", 24))
	var misses := []
	for key: String in _sorted_keys(colors):
		if not _paint_matches(colors[key], palette, tolerance):
			misses.append("#%02x%02x%02x" % colors[key])
	if not misses.is_empty():
		out.append("%s has %d vertex colours outside the %s palette, e.g. %s" % [rel, misses.size(),
				rule["palette"], ", ".join(misses.slice(0, 4))])


## A model the kit built from a recipe: the manifest's recipe (what `asset regen` builds) is the recipe on disk.
static func _built(out: Array, rel: String, manifest: Dictionary) -> void:
	var entry: Dictionary = (manifest.get("assets", {}) as Dictionary).get(rel, {})
	if entry.is_empty():
		out.append("%s has no entry in asset_manifest.json" % rel)
	elif entry.get("tool") == "mesh":
		var source := "res://" + String(entry["source"])
		var on_disk: Variant = JSON.parse_string(FileAccess.get_file_as_string(source))
		if on_disk == null:
			out.append("%s's recipe %s does not parse" % [rel, entry["source"]])
		elif on_disk != entry["recipe"]:
			out.append("%s was not built from %s as it stands (asset_manifest.json holds another recipe)" % [rel,
					entry["source"]])


## Every rule matching the path, in order, later keys winning; a null lifts a constraint (the kit's Style.rule_for).
static func rule_for(style: Dictionary, rel: String, kind: String) -> Dictionary:
	var merged := {}
	for rule: Dictionary in style.get("rules", []):
		var patterns: Array = rule["match"] if rule["match"] is Array else [rule["match"]]
		var hit := false
		for pattern: String in patterns:
			hit = hit or _glob(pattern).search(rel) != null
		if not hit or not rule.has(kind):
			continue
		var part: Dictionary = rule[kind]
		for key: String in _sorted_keys(part):
			if part[key] == null:
				merged.erase(key)
			elif part[key] is Dictionary and merged.get(key) is Dictionary:
				merged[key] = (merged[key] as Dictionary).merged(part[key], true)
			else:
				merged[key] = part[key]
	return merged


## The kit's glob: ** any depth, * and ? within one folder, {a,b} alternatives.
static func _glob(pattern: String) -> RegEx:
	var out := ""
	var i := 0
	while i < pattern.length():
		if pattern.substr(i, 3) == "**/":
			out += "(?:.*/)?"
			i += 3
			continue
		if pattern.substr(i, 2) == "**":
			out += ".*"
			i += 2
			continue
		var c := pattern[i]
		if c == "*":
			out += "[^/]*"
		elif c == "?":
			out += "[^/]"
		elif c == "{":
			var end := pattern.find("}", i)
			var options := []
			for option: String in pattern.substr(i + 1, end - i - 1).split(","):
				options.append(_escaped(option))
			out += "(?:" + "|".join(options) + ")"
			i = end
		else:
			out += _escaped(c)
		i += 1
	return RegEx.create_from_string("^" + out + "$")


static func _escaped(text: String) -> String:
	var out := ""
	for c in text:
		out += ("\\" + c) if ".^$+()[]{}|\\".contains(c) else c
	return out


## A palette by its name in the style: the .gpl's "R G B name" lines, as RGB triples (the kit's read_palette).
static func _palette(style: Dictionary, name: String) -> Array:
	var out := []
	var path := "res://" + String((style.get("palettes", {}) as Dictionary).get(name, name))
	for line: String in FileAccess.get_file_as_string(path).split("\n"):
		var words := line.replace("\t", " ").strip_edges().split(" ", false)
		if words.size() >= 3 and words[0].is_valid_int() and words[1].is_valid_int() and words[2].is_valid_int():
			out.append([words[0].to_int(), words[1].to_int(), words[2].to_int()])
	return out


## Same paint under different light (the kit's test): the colour is k times a palette colour, k in [0.5, 1.25],
## to within the tolerance.
static func _paint_matches(color: Array, palette: Array, tolerance: float) -> bool:
	for p: Array in palette:
		var dot := float(color[0] * p[0] + color[1] * p[1] + color[2] * p[2])
		var norm := float(p[0] * p[0] + p[1] * p[1] + p[2] * p[2])
		var k := clampf(dot / (norm if norm > 0.0 else 1.0), 0.5, 1.25)
		var d := Vector3(color[0] - k * p[0], color[1] - k * p[1], color[2] - k * p[2])
		if d.length() <= tolerance:
			return true
	return false


## A .glb's JSON and binary chunks, or {} when it is not one.
static func _glb(path: String) -> Dictionary:
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < 20 or bytes.decode_u32(0) != GLB_MAGIC:
		return {}
	var doc: Variant = null
	var bin := PackedByteArray()
	var offset := 12
	while offset + 8 <= bytes.size():
		var length := bytes.decode_u32(offset)
		var kind := bytes.decode_u32(offset + 4)
		var chunk := bytes.slice(offset + 8, offset + 8 + length)
		if kind == CHUNK_JSON:
			doc = JSON.parse_string(chunk.get_string_from_utf8())
		elif kind == CHUNK_BIN:
			bin = chunk
		offset += 8 + length
	return {"doc": doc, "bin": bin} if doc is Dictionary else {}


## The mesh of every node the scene reaches, once per node (as the kit counts them).
static func _mesh_uses(doc: Dictionary) -> Array:
	var out := []
	var scenes: Array = doc.get("scenes", [])
	var roots: Array = scenes[int(doc.get("scene", 0))].get("nodes", []) if not scenes.is_empty() else []
	var stack := roots.duplicate()
	while not stack.is_empty():
		var node: Dictionary = doc["nodes"][int(stack.pop_back())]
		if node.has("mesh"):
			out.append(int(node["mesh"]))
		stack.append_array(node.get("children", []))
	return out


## An accessor's colours, in sRGB 0 to 255 (glTF keeps them linear), as the kit reads them.
static func _colors(glb: Dictionary, index: int) -> Array:
	var doc: Dictionary = glb["doc"]
	var bin: PackedByteArray = glb["bin"]
	var acc: Dictionary = doc["accessors"][index]
	var view: Dictionary = doc["bufferViews"][int(acc["bufferView"])]
	var kind := int(acc["componentType"])
	var size: int = COMPONENT_BYTES[kind]
	var width := 4 if acc["type"] == "VEC4" else 3
	var start := int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
	var stride := int(view.get("byteStride", size * width))
	var out := []
	for i in int(acc["count"]):
		var rgb := []
		for c in 3:
			var at := start + i * stride + c * size
			var v := 0.0
			if kind == FLOAT:
				v = bin.decode_float(at)
			elif kind == USHORT:
				v = bin.decode_u16(at) / 65535.0
			else:
				v = bin.decode_u8(at) / 255.0
			var lin := clampf(v, 0.0, 1.0)
			var srgb := lin * 12.92 if lin <= 0.0031308 else 1.055 * pow(lin, 1.0 / 2.4) - 0.055
			rgb.append(roundi(srgb * 255.0))
		out.append(rgb)
	return out


## A dictionary's keys in order, so a report reads the same every run.
static func _sorted_keys(d: Dictionary) -> Array:
	var keys := d.keys()
	keys.sort()
	return keys
