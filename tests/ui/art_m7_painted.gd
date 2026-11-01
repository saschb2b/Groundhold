## M7's art has landed (contract-m7.md §3, track B): the Drift's four pack icons for Wickhollow
## (Game.PACKS), the corked bottle and the Seawall as icons, the corked bottle's model (the
## glint over a sent creep) and the Seawall's (its icon's), the console's tray and bottle
## sockets with layout.json's room for them, and the cork, uncork, breach and seawall sounds.
## Each M7 model keeps to its asset_style.json rules and was built from the recipe on disk,
## held by art_m6_painted.gd's checks (CI runs the scenarios, not the asset check).
##   {"eval": "resource('res://tests/ui/art_m7_painted.gd').problems()", "as": "found"}
##   {"assert": "found == []"}
extends RefCounted

const M6 := preload("res://tests/sim/art_m6_painted.gd")
## The duel's icons are drawn at about 20 to 48 px, sharp at 64.
const ICON_SIZE := 64
const MODELS := ["models/ui/corked_bottle.glb", "models/ui/seawall.glb"]
const PIECES := ["drift_tray", "bottle_socket", "bottle_socket_lit"]
const SOUNDS := ["cork", "uncork", "breach", "seawall"]


## Every way the art falls short, as readable lines; [] when it has all landed.
static func problems() -> Array:
	var out := []
	for check: String in SimContent.CHECK_IDS:
		var pack: Dictionary = Game.PACKS["hollow"].get(check, {})
		if pack.is_empty():
			out.append("Game.PACKS.hollow lacks %s" % check)
			continue
		M6._painted(out, str(pack["icon"]), ICON_SIZE)
	M6._painted(out, Game.BOTTLE_ICON, ICON_SIZE)
	M6._painted(out, Game.SEAWALL_ICON, ICON_SIZE)
	M6._scene(out, Game.BOTTLE_MODEL)
	for piece: String in PIECES:
		var box := load("res://ui/console/%s.tres" % piece) as StyleBoxTexture
		if box == null or box.texture == null:
			out.append("ui/console/%s.tres does not load with its texture" % piece)
	var layout: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://ui/console/layout.json"))
	if not (layout is Dictionary and (layout as Dictionary).has("tray") and (layout as Dictionary).has("shadow")):
		out.append("layout.json lacks the tray's room or the pieces' shadow")
	for name: String in SOUNDS:
		M6._sound(out, "res://sfx/%s.wav" % name)
		if not Sfx.has_sound(name):
			out.append("Sfx does not play %s" % name)
	var style: Variant = JSON.parse_string(FileAccess.get_file_as_string(M6.STYLE))
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(M6.MANIFEST))
	if not (style is Dictionary and manifest is Dictionary):
		out.append("asset_style.json or asset_manifest.json does not parse")
		return out
	for rel: String in MODELS:
		if ResourceLoader.exists("res://" + rel):
			M6._styled(out, rel, style)
			M6._built(out, rel, manifest)
		else:
			out.append("%s is missing" % rel)
	return out
