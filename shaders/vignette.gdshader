// A soft darkening toward the screen's corners and a touch of warmth in the
// middle: draws the eye to the field, as the strategy-game camera does.
shader_type canvas_item;

uniform float strength : hint_range(0.0, 1.0) = 0.42;

void fragment() {
	vec2 p = (UV - 0.5) * vec2(1.25, 1.0);
	float v = smoothstep(0.42, 0.95, length(p));
	COLOR = vec4(0.04, 0.03, 0.06, v * strength);
}
