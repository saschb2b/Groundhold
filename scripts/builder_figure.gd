## A Builder's figure: the generated chibi model (models/builders/<id>.glb, lit by
## materials/builder_toon), standing on a contact shadow, with the toon material tuned for
## the renderer that draws it. Place Builders through here, so none looks stuck on the grass
## and the browser build draws them like the desktop one.
class_name BuilderFigure
extends RefCounted

const TOON := preload("res://materials/builder_toon.tres")
## Under the Compatibility renderer the same vertex colours come out darker and more
## saturated than in Forward+, the towers' too, and the dark swatches (Tamsin's chestnut hat,
## Edda's ink coat) crush to near black. The gamma brings the darks and their hues back; the
## lift then sets each Builder's lit side against the arrow tower beside it as in Forward+
## (within about 10%, measured on the builders' game capture in both renderers).
const COMPAT := {"compat_lift": 0.39, "compat_gamma": 0.34}
const FORWARD := {"compat_lift": 1.0, "compat_gamma": 1.0}
## The portrait's viewport is re-encoded under Compatibility (portrait.gd), so it has no towers
## to match and needs only the dark swatches brought back: its own copy of the material.
const PORTRAIT_COMPAT := {"compat_lift": 0.95, "compat_gamma": 0.78}
## The contact shadow's radius by Builder: a little wider than the coat's hem.
const SHADOW := {"lamplighter": 0.3, "lookout": 0.26}

static var _portrait_toon: ShaderMaterial


static func model_path(id: String, bust := false) -> String:
	return "res://models/builders/%s%s.glb" % [id, "_bust" if bust else ""]


## The full figure, feet on its origin, on its own contact shadow.
static func spawn(id: String) -> Node3D:
	tune_for_renderer()
	var figure := Models.instance(model_path(id))
	BlobShadow.under(figure, float(SHADOW.get(id, 0.28)))
	return figure


## Sets the shared toon material for `method` (the running renderer by default).
static func tune_for_renderer(method := RenderingServer.get_current_rendering_method()) -> void:
	var values: Dictionary = COMPAT if method == "gl_compatibility" else FORWARD
	for key: String in values:
		TOON.set_shader_parameter(key, values[key])


## Dresses a model shown in the portrait (a Builder's bust) in the portrait's own copy of the
## toon material under Compatibility; under Forward+ it keeps the shared one.
static func dress_for_portrait(model: Node, method := RenderingServer.get_current_rendering_method()) -> void:
	if method != "gl_compatibility":
		return
	if _portrait_toon == null:
		_portrait_toon = TOON.duplicate() as ShaderMaterial
		for key: String in PORTRAIT_COMPAT:
			_portrait_toon.set_shader_parameter(key, PORTRAIT_COMPAT[key])
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		for s in mi.mesh.get_surface_count():
			if mi.get_active_material(s) == TOON:
				mi.set_surface_override_material(s, _portrait_toon)
