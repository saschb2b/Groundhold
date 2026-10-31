## Starts, kills and starts again whole games of this project, for a live topology
## (tests/net/live/net_restart_rejoins_live.json): a game killed mid-match (SIGKILL: no
## goodbye, no close frame, nothing flushed) and started again with the same user:// takes
## its seat back (design 6.7, Reconnect). The kit gives each topology client its own
## user:// (XDG_DATA_HOME); the games this driver starts inherit it, so a game started again
## finds the device key and the seat its first run noted (Identity.held_seat), as a player's
## game does after a crash or a closed window.
##
## Each game runs headless with its output on a pipe, read every frame: its HASH lines are
## printed here as they are (the kit compares this client's hash stream with the others':
## the first run's ticks, then the second's from its checkpoint on), every other line with
## the game's name in front, so its engine errors are this driver's to report (errors())
## rather than the kit's to misread as its own. Every game still running is killed when the
## driver leaves the tree; a scenario kills its own before it ends.
##
##   {"eval": "scene.launch('first', ['--join=127.0.0.1:{port}', '--hash-log', '--bot'])"}
##   {"wait_until": "scene.said('first', 'MATCH ')", "timeout": 900}
##   {"eval": "scene.kill('first')"}
##   {"wait_until": "not scene.running('first')", "timeout": 120}
##   {"assert": "scene.held_seat('127.0.0.1:{port}').size() == 2"}
extends Node

## A pipe read takes at most this many bytes, and at most READS of them a frame per pipe.
const CHUNK := 16384
const READS := 32
## The lines kept per game (the newest), so a long run cannot grow without bound.
const KEPT_LINES := 4000

## name -> {"pid", "io", "err", "rest": [stdout, stderr], "lines", "hash_tick", "errors"}
var games := {}


## Starts a headless game of this project with `args` (its own, after "--") as `name`.
## Returns its process id, or -1 when it could not start.
func launch(name: String, args: Array) -> int:
	var command := PackedStringArray(
		["--headless", "--path", ProjectSettings.globalize_path("res://"), "--max-fps", "60", "--"]
	)
	for a: Variant in args:
		command.append(str(a))
	var started: Dictionary = OS.execute_with_pipe(OS.get_executable_path(), command, false)
	if started.is_empty():
		push_error("restart_driver: %s could not start" % name)
		return -1
	games[name] = {
		"pid": int(started["pid"]),
		"io": started["stdio"],
		"err": started["stderr"],
		"rest": ["", ""],
		"lines": [],
		"hash_tick": -1,
		"errors": [],
	}
	print("[driver] %s started as process %d" % [name, int(started["pid"])])
	return int(started["pid"])


## Kills `name` at once (SIGKILL on Linux and macOS): no BYE, no close frame, no flush.
func kill(name: String) -> bool:
	if not running(name):
		return false
	_read(name)
	var ok := OS.kill(int(games[name]["pid"])) == OK
	# (the engine reaps what it kills: asking after it then is an error, so it is remembered)
	games[name]["gone"] = ok
	print("[driver] %s killed" % name)
	return ok


func running(name: String) -> bool:
	if not games.has(name) or bool(games[name].get("gone", false)):
		return false
	# (asked once more after the process was reaped, the engine reports an error: remembered)
	if not OS.is_process_running(int(games[name]["pid"])):
		games[name]["gone"] = true
		return false
	return true


## Whether `name` printed a line beginning with `prefix`.
func said(name: String, prefix: String) -> bool:
	return line(name, prefix) != ""


## The last line `name` printed that begins with `prefix`, "" for none.
func line(name: String, prefix: String) -> String:
	if not games.has(name):
		return ""
	var lines: Array = games[name]["lines"]
	for i in range(lines.size() - 1, -1, -1):
		if str(lines[i]).begins_with(prefix):
			return str(lines[i])
	return ""


## The highest tick `name` printed a HASH for, -1 before any.
func hash_tick(name: String) -> int:
	return int(games[name]["hash_tick"]) if games.has(name) else -1


## The engine and script errors `name` printed.
func errors(name: String) -> Array:
	return games[name]["errors"] if games.has(name) else []


## The seat a game of this user:// started now would ask back on the server at `address`
## (Identity.held_seat): [match, wire seat], or [] (none, or its game still runs).
func held_seat(address: String) -> Array:
	return Identity.held_seat(NetAddress.url(address))


## How many seats user://net.cfg notes for the server at `address`, running games' too.
func seats_noted(address: String) -> int:
	var where := Identity.origin(NetAddress.url(address))
	var count := 0
	for entry: Array in Identity._seats():
		if str(entry[0]) == where:
			count += 1
	return count


## Whether the file at `path` (a server's event log, say) holds `text`.
func file_has(path: String, text: String) -> bool:
	return FileAccess.file_exists(path) and FileAccess.get_file_as_string(path).contains(text)


func stop_all() -> void:
	for name: String in games.keys():
		if running(name):
			kill(name)


func _process(_delta: float) -> void:
	for name: String in games.keys():
		_read(name)


func _exit_tree() -> void:
	stop_all()


func _read(name: String) -> void:
	var game: Dictionary = games[name]
	for which in 2:
		var pipe: FileAccess = game["io"] if which == 0 else game["err"]
		if pipe == null:
			continue
		var got := ""
		for n in READS:
			var bytes := pipe.get_buffer(CHUNK)
			if bytes.is_empty():
				break
			got += bytes.get_string_from_utf8()
			if bytes.size() < CHUNK:
				break
		if got == "":
			continue
		var text: String = str(game["rest"][which]) + got
		var parts := text.split("\n")
		game["rest"][which] = parts[parts.size() - 1]  # (a line not ended yet: the rest next time)
		for i in parts.size() - 1:
			_take(name, game, parts[i].strip_edges(false, true))


func _take(name: String, game: Dictionary, text: String) -> void:
	var lines: Array = game["lines"]
	lines.append(text)
	if lines.size() > KEPT_LINES:
		lines.pop_front()
	if text.begins_with("HASH "):
		print(text)  # (as it is: the kit reads this client's hash stream from these)
		game["hash_tick"] = maxi(int(game["hash_tick"]), text.split(" ")[1].to_int())
		return
	if text.begins_with("ERROR:") or text.begins_with("SCRIPT ERROR:") or text.begins_with("USER ERROR:"):
		(game["errors"] as Array).append(text)
	print("[%s] %s" % [name, text])
