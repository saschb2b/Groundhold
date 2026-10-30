// The bared Flats round the Causeway at low water (the hub's backdrop): wet sand, darker
// and smoother where it is wettest, and standing water in channels and pools that shines
// with the sky toward the horizon. The pattern repeats every `period` units along Z, so the
// backdrop's camera can drift along the road for ever. Nothing here moves with TIME.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec3 sand : source_color = vec3(0.45, 0.38, 0.28);
uniform vec3 sand_wet : source_color = vec3(0.24, 0.22, 0.18);
uniform vec3 water : source_color = vec3(0.10, 0.19, 0.24);
uniform vec3 sky_shine : source_color = vec3(0.80, 0.74, 0.60);
// Units along Z after which the flats repeat (the backdrop's tile).
uniform float period = 24.0;
// How far either side of the road the flats stay dry (its footing).
uniform float footing = 1.6;

varying vec3 world;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// Value noise whose lattice wraps every `cells` cells along y, so it tiles along Z.
float noise(vec2 p, float cells) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float y0 = mod(i.y, cells);
	float y1 = mod(i.y + 1.0, cells);
	float a = hash(vec2(i.x, y0));
	float b = hash(vec2(i.x + 1.0, y0));
	float c = hash(vec2(i.x, y1));
	float d = hash(vec2(i.x + 1.0, y1));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
	// (cell sizes 4, 2 and 1 units: 6, 12 and 24 cells to a period of 24)
	float cells = period / 4.0;
	float v = 0.0;
	float amp = 0.55;
	for (int o = 0; o < 3; o++) {
		v += noise(p, cells) * amp;
		p *= 2.0;
		cells *= 2.0;
		amp *= 0.5;
	}
	return v;
}

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = vec2(world.x, world.z) / 6.0;
	float n = fbm(p * 1.5);
	// channels run roughly along the road; the road's own footing stays dry
	float dry_band = smoothstep(footing, footing + 1.4, abs(world.x));
	float wet = smoothstep(0.38, 0.56, n);
	float pool = smoothstep(0.56, 0.6, n) * dry_band;
	// ripples the ebb left in the sand, across the flow
	float ripple = 0.5 + 0.5 * sin(world.x * 7.0 + world.z * 1.3 + n * 9.0);
	vec3 ground = mix(sand, sand_wet, wet) * (0.93 + 0.1 * ripple);
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	vec3 shine = mix(water, sky_shine, clamp(fresnel * 1.6, 0.0, 1.0));
	ALBEDO = mix(ground, shine, pool);
	ROUGHNESS = mix(mix(0.92, 0.55, wet), 0.06, pool);
	SPECULAR = mix(0.35, 0.8, pool);
	EMISSION = sky_shine * pool * fresnel * 0.35;
}
