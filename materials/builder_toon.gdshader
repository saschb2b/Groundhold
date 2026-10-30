// Groundhold Builder toon, v1. Builders only; towers and creeps keep painted.gdshader.
// Vertex colour = the flat swatch (linear). Vertex alpha = shade class:
//   1.00 cloth, hair, leather, metal   0.75 skin   0.50 face paint   0.25 unlit glint
// Two tones with a crisp terminator. The shadow side is albedo * tint, chosen here rather
// than by the scene's ambient, so the portrait, the hub and every map shade a Builder alike.
shader_type spatial;
render_mode ambient_light_disabled, specular_disabled, shadows_disabled;

uniform vec3 shadow_tint : source_color = vec3(0.64, 0.59, 0.68);      // #a397ad
uniform vec3 skin_shadow_tint : source_color = vec3(0.88, 0.68, 0.66); // #e0ada8
uniform float paint_contrast : hint_range(0.0, 1.0) = 0.4;
uniform float terminator : hint_range(-0.5, 0.5) = 0.0;
uniform float softness : hint_range(0.001, 0.1) = 0.02;
uniform float rim_width : hint_range(0.05, 0.7) = 0.45;
uniform float back_rim : hint_range(0.0, 2.0) = 0.8;
uniform float front_rim : hint_range(0.0, 1.0) = 0.12;
// The Compatibility renderer (the browser build) draws the same vertex colours darker and
// more saturated than Forward+. BuilderFigure sets these there from code (on the board and,
// on its own copy, in the portrait); at their defaults they change nothing. The swatches
// themselves never change.
uniform float compat_lift : hint_range(0.1, 3.0) = 1.0;   // multiplies albedo and emission
uniform float compat_gamma : hint_range(0.2, 1.0) = 1.0;  // < 1 lifts the dark swatches (and their hues) more

varying vec3 shade_tint;

vec3 swatch(vec3 c) {
	return pow(c, vec3(compat_gamma)) * compat_lift;
}

void fragment() {
	float shade_class = COLOR.a;
	vec3 tint = shadow_tint;
	if (shade_class < 0.875) {
		tint = shade_class > 0.625 ? skin_shadow_tint : mix(vec3(1.0), shadow_tint, paint_contrast);
	}
	bool unlit = shade_class < 0.375;
	vec3 base = swatch(COLOR.rgb);
	ALBEDO = unlit ? vec3(0.0) : base;
	// the shadow tone, lit by nothing; a glint keeps its full brightness in either renderer
	EMISSION = unlit ? pow(COLOR.rgb, vec3(compat_gamma)) : base * tint;
	shade_tint = tint;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;  // no reflections
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float edge = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float rim = smoothstep(1.0 - rim_width - softness, 1.0 - rim_width + softness, edge) * step(0.0, ndl);
	vec3 energy = LIGHT_COLOR / PI;
	if (LIGHT_IS_DIRECTIONAL && dot(LIGHT, VIEW) < -0.2) {
		// A light from behind the Builder draws only a crisp rim.
		DIFFUSE_LIGHT += energy * rim * back_rim;
	} else {
		float lit = smoothstep(terminator - softness, terminator + softness, ndl) * ATTENUATION;
		DIFFUSE_LIGHT += energy * lit * ((vec3(1.0) - shade_tint) + rim * front_rim);
	}
}
