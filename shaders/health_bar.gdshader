// A creep's health bar: one quad that always faces the camera, its dark trough and the
// fill inside it drawn together, the fill `fill` of the trough's inner width from its left
// end. (Two billboarded quads, as before, could not show it: a billboard drops the node's
// scale, so the fill never shrank, and the offset that kept its left end fixed was in the
// creep's turning frame, so the fill slid out of the trough. Review round 2.)
shader_type spatial;
render_mode unshaded, depth_test_disabled, cull_disabled, shadows_disabled, fog_disabled;

uniform float fill : hint_range(0.0, 1.0) = 1.0;
uniform vec4 fill_color : source_color = vec4(0.3, 0.9, 0.3, 1.0);
uniform vec4 trough_color : source_color = vec4(0.05, 0.04, 0.03, 0.85);
// The trough's rim round the fill, as a fraction of the quad's width and height.
uniform vec2 rim = vec2(0.037, 0.19);

void vertex() {
	// Facing the camera, at the node's place and scale.
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
		INV_VIEW_MATRIX[0] * length(MODEL_MATRIX[0].xyz),
		INV_VIEW_MATRIX[1] * length(MODEL_MATRIX[1].xyz),
		INV_VIEW_MATRIX[2] * length(MODEL_MATRIX[2].xyz),
		MODEL_MATRIX[3]
	);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
	vec2 inner = (UV - rim) / (vec2(1.0) - 2.0 * rim);
	bool lit = inner.x >= 0.0 && inner.x <= fill && inner.y >= 0.0 && inner.y <= 1.0;
	vec4 color = lit ? fill_color : trough_color;
	ALBEDO = color.rgb;
	ALPHA = color.a;
}
