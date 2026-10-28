// Contact shadow: a soft dark disc laid on the ground under a unit,
// tower or tree. It grounds things the way ambient occlusion does, and works in
// every renderer, including the web build's, which has no SSAO.
shader_type spatial;
// Plain alpha blending (not multiply): the Compatibility renderer of the web
// build draws multiply-blended quads as solid black.
render_mode blend_mix, unshaded, shadows_disabled, depth_draw_never, cull_disabled;

uniform float strength : hint_range(0.0, 1.0) = 0.55;

void fragment() {
	float d = length(UV - 0.5) * 2.0;
	ALBEDO = vec3(0.05, 0.045, 0.07);
	ALPHA = strength * (1.0 - smoothstep(0.2, 1.0, d));
}
