// Pond surface. `t` is driven by the game clock (not TIME) so captures repeat exactly.
shader_type spatial;
render_mode blend_mix, specular_schlick_ggx, cull_back;

uniform vec3 deep : source_color = vec3(0.10, 0.27, 0.33);
uniform vec3 shallow : source_color = vec3(0.24, 0.48, 0.52);
uniform float t = 0.0;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), u.x), u.y);
}

void fragment() {
	vec3 world = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float ripple = noise(world.xz * 4.0 + vec2(t * 0.3, t * 0.2)) * noise(world.xz * 6.0 - vec2(t * 0.25, 0.0));
	ALBEDO = mix(deep, shallow, ripple);
	ALPHA = 0.82;
	ROUGHNESS = 0.15;
	METALLIC = 0.0;
	SPECULAR = 0.6;
	EMISSION = vec3(0.9, 0.8, 0.5) * smoothstep(0.55, 0.75, ripple) * 0.25;
}
