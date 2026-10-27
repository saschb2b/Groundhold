// Painted terrain from the tile map. One texel per cell of map_tex holds what the
// cell is (R road, G meadow, B high ground, A buildable); bilinear sampling plus
// noise turns the square tiles into organic edges, the way strategy-game
// terrain blends its tiles.
shader_type spatial;
render_mode specular_disabled;

uniform sampler2D map_tex : filter_linear, repeat_disable;
uniform vec2 map_size = vec2(24.0, 16.0);
uniform vec3 grass_a : source_color = vec3(0.30, 0.47, 0.18);
uniform vec3 grass_b : source_color = vec3(0.42, 0.56, 0.22);
uniform vec3 grass_autumn : source_color = vec3(0.62, 0.50, 0.20);
uniform vec3 dirt_a : source_color = vec3(0.47, 0.34, 0.22);
uniform vec3 dirt_b : source_color = vec3(0.58, 0.44, 0.29);
uniform vec3 rock_a : source_color = vec3(0.42, 0.40, 0.38);
uniform vec3 rock_b : source_color = vec3(0.56, 0.53, 0.49);
uniform vec3 mud : source_color = vec3(0.24, 0.22, 0.16);
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

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 xz = world_pos.xz;
	vec4 m = texture(map_tex, xz / map_size);
	float n = fbm(xz * 1.6);

	vec3 grass = mix(grass_a, grass_b, smoothstep(0.35, 0.7, fbm(xz * 0.5)));
	grass = mix(grass, grass_autumn, smoothstep(0.62, 0.8, fbm(xz * 0.33 + 11.0)) * 0.6);
	grass = mix(grass, mix(grass_b, vec3(0.75, 0.62, 0.25), 0.5), m.g * 0.45);
	grass *= 0.88 + 0.24 * noise(xz * 11.0);

	vec3 dirt = mix(dirt_a, dirt_b, noise(xz * 5.0));
	dirt = mix(dirt, dirt_b * 1.25, step(0.86, noise(xz * 17.0)) * 0.7);
	dirt *= 0.9 + 0.15 * noise(xz * 23.0);
	float road = smoothstep(0.4, 0.6, m.r + (n - 0.5) * 0.6);
	vec3 col = mix(grass, dirt, road);

	// High ground: grass worn through to rock.
	float high = smoothstep(0.55, 0.7, world_pos.y);
	vec3 rock_top = mix(rock_a, rock_b, noise(xz * 3.0));
	col = mix(col, mix(grass * 0.85, rock_top, smoothstep(0.45, 0.65, n)), high);

	// Cliff walls and pond banks: layered rock.
	float wall = 1.0 - smoothstep(0.35, 0.65, world_normal.y);
	float strata = fract(world_pos.y * 5.0 + noise(xz * 2.0 + world_pos.y) * 0.8);
	vec3 cliff = mix(rock_a * 0.85, rock_b, smoothstep(0.2, 0.8, strata)) * (0.85 + 0.25 * noise(xz * 7.0 + world_pos.y * 4.0));
	col = mix(col, cliff, wall);
	col = mix(col, mud, smoothstep(-0.1, -0.3, world_pos.y));

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
