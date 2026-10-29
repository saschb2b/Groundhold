## The determinism lint for scripts/sim, as a scenario can run it (design 7.5 #2 and the
## M1 acceptance `sim_lint_clean`). It holds the kit's forbidden tokens
## (`godot-agent check . --sim-lint scripts/sim`) and the ones the kit's list misses:
## dictionary iteration (`for k in d`, `.keys()`, `.values()`), float rounding (`ceil`,
## `floor`, `round` and their kin), `Engine.`, `.length()` (a vector's is a float),
## `sort_custom` (needs an id tie-break, said in its allow comment), `.hash()`,
## `RandomNumberGenerator`, `randomize`, `OS.`, `await` and `call_deferred`; and since
## review M1 determinism 2, the float constants `TAU`, `PI`, `INF` and `NAN`, `sort()`
## (on records it orders by address; on ints it says so in its allow comment),
## `get_instance_id`, `to_float` and iterating what a function typed `-> Dictionary`
## returns (`for k in SimContent.rules("classic"):`).
##
## Strings and comments are not code; a line may allow a token with
## `# sim-lint: allow <token> <reason>`, as the kit's lint takes it.
extends RefCounted

## [token, regular expression] on a line with its strings and comment taken out.
const RULES := [
	["float", "\\bfloat\\b"],
	["float constants", "\\b(TAU|PI|INF|NAN)\\b"],
	["float literal", "(?<![\\w.])\\d+\\.\\d*(?![\\w.])|(?<![\\w.])\\.\\d+\\b|\\b\\d+[eE][+-]?\\d+\\b"],
	["trigonometry", "\\b(sin|cos|tan|asin|acos|atan|atan2|sqrt|pow|exp|log)\\s*\\("],
	["lerp", "\\b(lerp|lerpf|lerp_angle|inverse_lerp|smoothstep|move_toward)\\s*\\("],
	["engine random", "\\b(randf|randi|randfn|randf_range|randi_range|randomize|seed)\\s*\\("],
	["RandomNumberGenerator", "\\bRandomNumberGenerator\\b"],
	["shuffle", "\\.shuffle\\s*\\("],
	["pick_random", "\\.pick_random\\s*\\("],
	["vectors", "\\b(Vector2|Vector3|Vector4|Basis|Transform2D|Transform3D|Quaternion|Plane|Rect2)\\b(?!i)"],
	["look_at", "\\blook_at\\s*\\("],
	["get_tree", "\\bget_tree\\s*\\("],
	["get_nodes_in_group", "\\bget_nodes_in_group\\b"],
	["Time.", "\\bTime\\."],
	["OS.", "\\bOS\\."],
	["Engine.", "\\bEngine\\."],
	["delta", "\\bdelta\\b"],
	["time_scale", "\\btime_scale\\b"],
	["Node types", "\\b(Node|Node2D|Node3D|Control|CanvasItem)\\b"],
	["hash(", "\\bhash\\s*\\(|\\.hash\\s*\\("],
	["rounding", "\\b(ceil|floor|round|ceilf|floorf|roundf|ceili|floori|roundi|snapped|snappedf|snappedi|fmod|fposmod|absf|signf|clampf|minf|maxf|is_equal_approx|is_zero_approx)\\s*\\("],
	["length()", "\\.length\\s*\\(\\s*\\)"],
	["keys()", "\\.keys\\s*\\("],
	["values()", "\\.values\\s*\\("],
	["sort_custom", "\\bsort_custom\\b"],
	["sort()", "\\.sort\\s*\\(\\s*\\)"],
	["get_instance_id", "\\bget_instance_id\\b"],
	["to_float", "\\.to_float\\s*\\("],
	["await", "\\bawait\\b"],
	["call_deferred", "\\bcall_deferred\\b"],
]


## Every forbidden token in the .gd files of `dir`, as "file:line token: code".
static func scan(dir: String) -> Array:
	var out := []
	var names := Array(DirAccess.get_files_at(dir))
	names.sort()
	var texts := {}
	for file: String in names:
		if file.ends_with(".gd"):
			texts[file] = FileAccess.get_file_as_string(dir.path_join(file))
	var dictionaries := _dictionary_names(texts.values())
	for file: String in names:
		if texts.has(file):
			out.append_array(scan_text(file, str(texts[file]), dictionaries))
	return out


## The line numbers a file's tokens are on, one per caught token (for the lint's own
## test), knowing the dictionaries `dir` declares (SimContent.TOWERS, ...).
static func scan_file_lines(path: String, dir := "res://scripts/sim") -> Array:
	var texts := []
	for file: String in DirAccess.get_files_at(dir):
		if file.ends_with(".gd"):
			texts.append(FileAccess.get_file_as_string(dir.path_join(file)))
	var out := []
	var text := FileAccess.get_file_as_string(path)
	for found: String in scan_text(path.get_file(), text, _dictionary_names(texts)):
		out.append(found.get_slice(":", 1).to_int())
	return out


## The tokens one file's text holds. `dictionaries` names the Dictionary variables and
## constants other files declare (SimContent.TOWERS, ...), so iterating one is caught.
static func scan_text(file: String, text: String, dictionaries := []) -> Array:
	var out := []
	var known: Array = dictionaries + _dictionary_names([text])
	var rules := []
	for rule: Array in RULES:
		var re := RegEx.new()
		re.compile(str(rule[1]))
		rules.append([rule[0], re])
	var iterate := RegEx.new()
	iterate.compile("\\bfor\\s+\\w+(\\s*:\\s*\\w+)?\\s+in\\s+([\\w.]+)\\s*(:|\\()")
	var lines := text.split("\n")
	for i in lines.size():
		var raw: String = lines[i]
		var allowed := _allowed(raw)
		var code := _code(raw)
		for rule: Array in rules:
			if allowed.has(str(rule[0])):
				continue
			if (rule[1] as RegEx).search(code) != null:
				out.append("%s:%d %s: %s" % [file, i + 1, rule[0], raw.strip_edges()])
		var m := iterate.search(code)
		if m != null and not allowed.has("dictionary iteration"):
			var target := m.get_string(2)
			if known.has(target) or known.has(target.get_slice(".", target.get_slice_count(".") - 1)):
				out.append("%s:%d dictionary iteration: %s" % [file, i + 1, raw.strip_edges()])
	return out


## Names declared as dictionaries: `var d := {}`, `var d: Dictionary`, `const D := {`,
## parameters typed `d: Dictionary`, and functions typed `-> Dictionary` (iterating what
## one returns is caught as `for k in f(...):`).
static func _dictionary_names(texts: Array) -> Array:
	var out := []
	var re := RegEx.new()
	re.compile(
		"\\b(?:var|const)\\s+(\\w+)\\s*(?::=\\s*\\{|:\\s*Dictionary\\b|=\\s*\\{)|(\\w+)\\s*:\\s*Dictionary\\b"
		+ "|\\bfunc\\s+(\\w+)\\s*\\([^)]*\\)\\s*->\\s*Dictionary\\b"
	)
	for text: Variant in texts:
		for m: RegExMatch in re.search_all(str(text)):
			var name := ""
			for group in [1, 2, 3]:
				if name == "":
					name = m.get_string(group)
			if name != "" and not out.has(name):
				out.append(name)
	return out


## The tokens a line's comment allows: `# sim-lint: allow <token> <reason>`; the token may
## hold spaces when it is one of RULES' names.
static func _allowed(line: String) -> Array:
	var at := line.find("# sim-lint: allow ")
	if at < 0:
		return []
	var rest := line.substr(at + 18)
	var out := []
	for rule: Array in RULES:
		if rest.begins_with(str(rule[0])):
			out.append(rule[0])
	if rest.begins_with("dictionary iteration"):
		out.append("dictionary iteration")
	return out


## A line without its string literals and its comment.
static func _code(line: String) -> String:
	var out := ""
	var quote := ""
	var i := 0
	while i < line.length():
		var ch := line[i]
		if quote != "":
			if ch == "\\":
				i += 2
				continue
			if ch == quote:
				quote = ""
				out += ch
		elif ch == "\"" or ch == "'":
			quote = ch
			out += ch
		elif ch == "#":
			break
		else:
			out += ch
		i += 1
	return out
