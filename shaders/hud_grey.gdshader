// Greys a command icon the player cannot use right now. `grey` fades it to its luma,
// `value` sets how light the grey stays: readable when the command is only
// unaffordable, darker when it does not apply at all.
shader_type canvas_item;

uniform float grey : hint_range(0.0, 1.0) = 0.0;
uniform float value : hint_range(0.0, 1.0) = 0.72;

void fragment() {
	vec4 c = texture(TEXTURE, UV) * COLOR;
	float luma = dot(c.rgb, vec3(0.3, 0.59, 0.11));
	COLOR = vec4(mix(c.rgb, vec3(luma * value), grey), c.a);
}
