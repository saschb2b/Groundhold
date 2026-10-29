## Loads generated .glb models once and hands out instances or bare meshes.
class_name Models
extends RefCounted

static var _scenes := {}
static var _meshes := {}


static func instance(path: String) -> Node3D:
	if not _scenes.has(path):
		_scenes[path] = load(path)
	return (_scenes[path] as PackedScene).instantiate() as Node3D


## The model as one mesh with its materials on the surfaces, for MultiMesh use.
## Models built in Blender keep one node per part (trunk, boughs), so every
## MeshInstance3D is baked into the model's space and merged.
static func mesh(path: String) -> Mesh:
	if _meshes.has(path):
		return _meshes[path]
	var node := instance(path)
	var parts: Array[MeshInstance3D] = []
	if node is MeshInstance3D:
		parts.append(node)
	for found: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		parts.append(found)
	var result: Mesh
	if parts.size() == 1 and parts[0] == node:
		result = parts[0].mesh
		_keep_materials(result, parts[0])
	else:
		result = _merge(node, parts)
	node.free()
	_meshes[path] = result
	return result


## Drops the cached scenes and meshes (on scene exit, so nothing outlives the game).
static func clear_cache() -> void:
	_scenes.clear()
	_meshes.clear()


## Imported materials may sit on the instance; MultiMesh only sees the mesh's own.
static func _keep_materials(target: Mesh, from: MeshInstance3D) -> void:
	for s in target.get_surface_count():
		if target.surface_get_material(s) == null:
			target.surface_set_material(s, from.get_active_material(s))


static func _merge(root: Node3D, parts: Array[MeshInstance3D]) -> ArrayMesh:
	var merged := ArrayMesh.new()
	for part in parts:
		var to_root := _relative(root, part)
		var normals := to_root.basis.inverse().transposed()
		for s in part.mesh.get_surface_count():
			var arrays := part.mesh.surface_get_arrays(s)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for i in verts.size():
				verts[i] = to_root * verts[i]
			arrays[Mesh.ARRAY_VERTEX] = verts
			if arrays[Mesh.ARRAY_NORMAL] != null:
				var n: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
				for i in n.size():
					n[i] = (normals * n[i]).normalized()
				arrays[Mesh.ARRAY_NORMAL] = n
			# Tangents and skinning do not survive the bake; static decor needs neither.
			arrays[Mesh.ARRAY_TANGENT] = null
			arrays[Mesh.ARRAY_BONES] = null
			arrays[Mesh.ARRAY_WEIGHTS] = null
			merged.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			merged.surface_set_material(merged.get_surface_count() - 1, part.get_active_material(s))
	return merged


static func _relative(root: Node3D, part: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var node: Node = part
	while node != null and node != root:
		if node is Node3D:
			t = (node as Node3D).transform * t
		node = node.get_parent()
	return t
