## Checks the live topologies (tests/net/live/) make of what a game kept or the server
## logged, as static helpers a step can call:
##   {"eval": "resource('res://tests/net/live_checks.gd')", "as": "Checks"}
##   {"eval": "Checks.dump_summary(scene.client.dump_path)", "as": "dump"}
extends RefCounted


## A desync dump read back (DesyncDump.read) and checked against itself: its fields, how
## many turns and hashes it holds, and whether its checkpoint, run through its turns
## (DesyncDump.replay), reaches every hash it says this seat sent from the checkpoint up to
## the bad tick ("replays": the dump is enough to replay this side). {} when `path` is no
## dump.
static func dump_summary(path: String) -> Dictionary:
	var dump := DesyncDump.read(path)
	if dump.is_empty():
		return {}
	var hashes: Dictionary = dump["hashes"]
	var ticks: Array = hashes.keys()
	ticks.sort()
	var from := int(dump["checkpoint_tick"])
	var bad := int(dump["bad_tick"])
	var checked := 0
	var replays := true
	var sim: SimMatch = DesyncDump.replay(dump, from)
	var log := _turn_log(dump)
	if sim == null:
		replays = false
	else:
		for t: int in ticks:
			if t < from or t >= bad:
				continue
			sim = DesyncDump.run_to(sim, log, t)
			if sim == null or sim.state_hash_hex() != str(hashes[t]):
				replays = false
				break
			checked += 1
	return {
		"match": int(dump["match"]),
		"seat": int(dump["seat"]),
		"bad_tick": bad,
		"checkpoint_tick": from,
		"checkpoint_bytes": (dump["checkpoint"] as PackedByteArray).size(),
		"turns": (dump["turns"] as Array).size(),
		"state_bytes": (dump["state"] as PackedByteArray).size(),
		"hashes": ticks.size(),
		"hash_at_bad": str(hashes.get(bad, "")),
		"replayed_hashes": checked,
		"replays": replays,
	}


## Copies the file at `from` (a user:// path) to `to` (an absolute path: the run's out
## folder, so a person can look at it after the kit removed the run's user://). True when
## it was copied.
static func copy_out(from: String, to: String) -> bool:
	if not FileAccess.file_exists(from):
		return false
	return DirAccess.copy_absolute(ProjectSettings.globalize_path(from), to) == OK


## Whether the file at `path` (a server's event log, say) holds `text`.
static func file_has(path: String, text: String) -> bool:
	return FileAccess.file_exists(path) and FileAccess.get_file_as_string(path).contains(text)


## How many lines of the file at `path` hold `text`.
static func lines_with(path: String, text: String) -> int:
	if not FileAccess.file_exists(path):
		return 0
	var count := 0
	for line: String in FileAccess.get_file_as_string(path).split("\n"):
		if line.contains(text):
			count += 1
	return count


static func _turn_log(dump: Dictionary) -> Array:
	var log := []
	for fields: Dictionary in dump["turns"]:
		var k := int(fields["turn"])
		while log.size() <= k:
			log.append(null)
		var commands := []
		for entry: Dictionary in fields["commands"]:
			commands.append(RemoteSequencer.from_wire(entry))
		log[k] = commands
	return log
