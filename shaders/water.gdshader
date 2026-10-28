// Pond surface. A depth map from the terrain (0 at the shore, 1 at the deepest)
// drives the look: see-through turquoise shallows over the sandy bank, deep blue
// in the middle, a foam line that laps at the shore, and moving ripples that
// catch the sun. `t` is advanced by the game clock (not TIME) so captures repeat.
shader_type spatial;
render_mode blend_mix, cull_back, specular_schlick_ggx;

uniform sampler2D depth_tex : filter_linear, repeat_disable;
uniform vec2 map_size = vec2(24.0, 16.0);
uniform float t = 0.0;
uniform vec3 shallow : source_color = vec3(0.36, 0.72, 0.66);
uniform vec3 mid : source_color = vec3(0.13, 0.46, 0.55);
uniform vec3 deep : source_color = vec3(0.05, 0.2, 0.33);
uniform vec3 foam_color : source_color = vec3(0.93, 0.97, 0.92);

varying vec3 world;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), u.x), u.y);
}

// Two ripple layers drifting across each other.
float ripples(vec2 p) {
	return 0.6 * noise(p * 2.4 + vec2(t * 0.11, t * 0.07)) + 0.4 * noise(p * 4.1 - vec2(t * 0.09, -t * 0.05));
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 xz = world.xz;
	float d = texture(depth_tex, xz / map_size).r;

	float h = ripples(xz);
	float e = 0.04;
	vec3 n = normalize(vec3((h - ripples(xz + vec2(e, 0.0))) * 3.0, 1.0, (h - ripples(xz + vec2(0.0, e))) * 3.0));
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);

	vec3 col = mix(shallow, mid, smoothstep(0.02, 0.35, d));
	col = mix(col, deep, smoothstep(0.35, 0.95, d));
	// Light dancing on the bottom of the shallows.
	col += vec3(0.1, 0.12, 0.08) * smoothstep(0.62, 0.85, h) * (1.0 - smoothstep(0.1, 0.5, d));

	// Foam: a solid rim at the waterline and a lapping band that moves outward.
	float rim = 1.0 - smoothstep(0.0, 0.07, d);
	float band = sin(d * 38.0 - t * 2.2 + noise(xz * 1.7) * 5.0) * 0.5 + 0.5;
	float lap = smoothstep(0.62, 0.9, band) * (1.0 - smoothstep(0.04, 0.22, d));
	float foam = clamp(rim + lap * 0.8, 0.0, 1.0) * (0.55 + 0.45 * noise(xz * 7.0 + t * 0.3));
	col = mix(col, foam_color, foam);

	// Glints: the sun caught on ripple crests, drifting with the water.
	float sparkle = noise(xz * 34.0 + vec2(t * 0.8, -t * 0.5)) * noise(xz * 23.0 - vec2(t * 0.4, t * 0.3));
	// Fade glints where one pixel covers several of them (far away), or they alias.
	float glint_fade = 1.0 - smoothstep(0.02, 0.05, fwidth(xz.x));
	col += vec3(1.0, 0.95, 0.8) * smoothstep(0.66, 0.82, sparkle) * 0.3 * smoothstep(0.05, 0.3, d) * glint_fade;

	ALBEDO = col;
	// The sandy bank shows through the shallows; the middle is opaque.
	ALPHA = clamp(mix(0.5, 0.94, smoothstep(0.0, 0.45, d)) + foam * 0.5, 0.0, 1.0);
	ROUGHNESS = mix(0.06, 0.4, foam);
	SPECULAR = 0.75;
	METALLIC = 0.0;
}
