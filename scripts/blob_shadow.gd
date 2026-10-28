## A soft contact shadow under something standing on the ground.
class_name BlobShadow
extends MeshInstance3D

const SHADER := preload("res://shaders/blob_shadow.gdshader")

static var _mesh: PlaneMesh
static var _material: ShaderMaterial


static func under(parent: Node3D, radius: float, lift := 0.03) -> BlobShadow:
	if _mesh == null:
		_mesh = PlaneMesh.new()
		_mesh.size = Vector2.ONE
		_material = ShaderMaterial.new()
		_material.shader = SHADER
	var blob := BlobShadow.new()
	blob.mesh = _mesh
	blob.material_override = _material
	blob.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	blob.scale = Vector3(radius * 2.0, 1.0, radius * 2.0)
	blob.position.y = lift
	parent.add_child(blob)
	return blob


static func clear_cache() -> void:
	_mesh = null
	_material = null
