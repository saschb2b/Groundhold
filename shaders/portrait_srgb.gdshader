// The browser's Compatibility renderer hands a transparent SubViewport over in linear
// colour, so the portrait came out dark there; this encodes it the way Forward+ does.
shader_type canvas_item;

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	COLOR = vec4(pow(c.rgb, vec3(1.0 / 2.2)), c.a);
}
