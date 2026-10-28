// Painted terrain from the tile map. Each kind of ground is a hand-painted,
// seamless texture (textures/, from `godot-agent asset texture`) sampled in world
// space. One texel per cell of map_tex says what the cell is (R road, G meadow,
// B high ground, A buildable); bilinear sampling plus noise turns the square
// tiles into ragged, overgrown borders. Two scales of every texture are mixed
// so the repeat does not show, and large patches tint the grass toward autumn.
shader_type spatial;
render_mode specular_disabled;

uniform sampler2D map_tex : filter_linear, repeat_disable;
uniform sampler2D grass_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D meadow_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D path_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D mud_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
// R: water depth, G: how much a point belongs to the pond (from terrain.gd).
uniform sampler2D shore_tex : filter_linear, repeat_disable;
uniform vec2 map_size = vec2(24.0, 16.0);
// World units one texture covers.
uniform float texture_span = 2.2;
uniform vec3 autumn : source_color = vec3(0.86, 0.66, 0.3);
uniform float water_level = -0.1;
uniform vec3 grid_color : source_color = vec3(0.95, 0.92, 0.65);
uniform float show_grid = 0.0;
uniform vec2 hover_cell = vec2(-10.0);
uniform vec3 hover_color : source_color = vec3(0.4, 1.0, 0.4);

varying vec3 world_pos;
varying vec3 world_normal;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), u.x), u.y);
}

float fbm(vec2 p) {
	return 0.5 * noise(p) + 0.3 * noise(p * 2.03 + 7.1) + 0.2 * noise(p * 4.01 + 3.3);
}

// A texture at its own scale, blended with a rotated, larger copy where the
// noise says so: no visible grid of repeats from the strategy camera.
vec3 painted(sampler2D tex, vec2 p) {
	vec2 uv = p / texture_span;
	vec3 near = texture(tex, uv).rgb;
	vec2 q = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * uv * 0.47 + vec2(0.31, 0.17);
	vec3 far = texture(tex, q).rgb;
	return mix(near, far, smoothstep(0.3, 0.7, noise(p * 0.55)));
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 xz = world_pos.xz;
	vec4 m = texture(map_tex, xz / map_size);
	float n = fbm(xz * 1.6);
	float fine = noise(xz * 9.0);

	// Grass, tinted toward autumn in large patches, meadow where the map says so.
	vec3 grass = painted(grass_tex, xz);
	float patch = smoothstep(0.58, 0.8, fbm(xz * 0.3 + 11.0));
	grass = mix(grass, grass * autumn * 1.35, patch * 0.75);
	// Broad light and shade across the field, as a painter blocks in a meadow.
	grass *= 0.84 + 0.3 * fbm(xz * 0.38 + 4.0);
	// Darker clumps, and bare earth showing through here and there.
	grass *= 1.0 - 0.22 * smoothstep(0.58, 0.72, fbm(xz * 1.1 + 21.0));
	float bare = smoothstep(0.72, 0.78, fbm(xz * 0.45 + 33.0) + (fine - 0.5) * 0.12);
	grass = mix(grass, painted(path_tex, xz + 9.0) * 0.9, bare);
	grass = mix(grass, painted(meadow_tex, xz + 3.7), smoothstep(0.25, 0.6, m.g + (n - 0.5) * 0.4));

	// The road: ragged edges where grass creeps over, a shadowed lip along them.
	vec3 path = painted(path_tex, xz);
	float edge_noise = (n - 0.5) * 0.55 + (fine - 0.5) * 0.18;
	float road_mask = m.r + edge_noise;
	float road = smoothstep(0.46, 0.54, road_mask);
	float lip = smoothstep(0.46, 0.53, road_mask) * (1.0 - smoothstep(0.53, 0.68, road_mask));
	path *= 1.0 - 0.32 * lip;
	vec3 col = mix(grass, path, road);
	// Grass right at the edge is a touch darker, as if it were taller there.
	col *= 1.0 - 0.15 * smoothstep(0.32, 0.46, road_mask) * (1.0 - road);

	// High ground: grass worn through to rock.
	float high = smoothstep(0.55, 0.7, world_pos.y);
	vec3 rock = painted(rock_tex, xz);
	col = mix(col, mix(grass * 0.9, rock, smoothstep(0.42, 0.62, n)), high);

	// Cliff walls: rock projected onto the wall's own plane.
	float wall = 1.0 - smoothstep(0.35, 0.65, world_normal.y);
	vec2 wall_uv = abs(world_normal.x) > abs(world_normal.z) ? world_pos.zy : world_pos.xy;
	vec3 cliff = painted(rock_tex, wall_uv * 1.3) * (0.78 + 0.22 * smoothstep(0.0, 0.9, world_pos.y));
	col = mix(col, cliff, wall);

	// Shore: only around the pond (not in every dip of the rolling grass). Wet
	// grass, a sandy bank along the waterline, mud on the bed.
	float above = world_pos.y - water_level;
	float dip = smoothstep(0.08, 0.22, texture(shore_tex, xz / map_size).g);
	col *= 1.0 - 0.22 * (1.0 - smoothstep(0.0, 0.08, above)) * dip;
	col = mix(col, painted(sand_tex, xz), smoothstep(0.07, 0.0, above) * dip);
	col = mix(col, painted(mud_tex, xz), smoothstep(0.08, 0.3, -above));

	// Build grid over buildable cells, and the hovered cell.
	vec2 cell = floor(xz);
	vec2 f = fract(xz);
	float edge = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
	float line = 1.0 - smoothstep(0.015, 0.045, edge);
	float buildable = texelFetch(map_tex, ivec2(cell), 0).a;
	col = mix(col, grid_color, line * buildable * show_grid * 0.55 * (1.0 - wall));
	float hovered = step(distance(cell, hover_cell), 0.1) * (1.0 - wall);
	col = mix(col, hover_color, hovered * (0.25 + 0.6 * line));

	ALBEDO = col;
	ROUGHNESS = 0.95;
}
