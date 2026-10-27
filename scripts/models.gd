## Loads generated .glb models once and hands out instances or bare meshes.
class_name Models
extends RefCounted

static var _scenes := {}
static var _meshes := {}


static func instance(path: String) -> Node3D:
	if not _scenes.has(path):
		_scenes[path] = load(path)
	return (_scenes[path] as PackedScene).instantiate() as Node3D


## The model's mesh with its materials on the surfaces, for MultiMesh use.
static func mesh(path: String) -> Mesh:
	if _meshes.has(path):
		return _meshes[path]
	var node := instance(path)
	var found: MeshInstance3D = node if node is MeshInstance3D else null
	if found == null:
		found = node.find_children("*", "MeshInstance3D", true, false).front() as MeshInstance3D
	var result: Mesh = found.mesh
	# Imported materials may sit on the instance; MultiMesh only sees the mesh's own.
	for s in result.get_surface_count():
		if result.surface_get_material(s) == null:
			result.surface_set_material(s, found.get_active_material(s))
	node.free()
	_meshes[path] = result
	return result


## Drops the cached scenes and meshes (on scene exit, so nothing outlives the game).
static func clear_cache() -> void:
	_scenes.clear()
	_meshes.clear()
