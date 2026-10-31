## What a client writes when its match ends "desynced" (design 6.7; docs/design/
## contract-m4.md): enough to replay its side to the first bad hash tick and compare it
## with another seat's dump. The results plate says a report was saved and offers it (Show
## report: its folder on the desktop; Save report: a download in the browser).
##
## Path: user://desync/<match>-<seat>.bin, the match id from MATCH_CONFIG in decimal and
## the seat as the game shows it (1 to 4): path_for(). Big-endian, in order:
##   "GHDD", u8 format (1), u16 protocol version, u32 build_seq, 8 bytes rules hash,
##   u32 match, u8 seat (1 to 4), u8 mode (wire id), u32 seed,
##   u8 n, then per seat: u8 team, u8 builder (wire id), u8 flags (no names: a dump may be
##   attached to a bug report),
##   u32 bad tick (MATCH_END's final_tick: the first hash tick the seats disagreed on),
##   u32 checkpoint tick, u32 length, its bytes (the last agreed checkpoint: the latest
##   kept before the bad tick, since every hash tick before it agreed; a bad tick that is
##   itself a checkpoint tick holds this game's own parted state, never the agreed one.
##   Tick 0 and no bytes when none is kept: tick 0 is built from MATCH_CONFIG),
##   u32 n, then every turn from the checkpoint's: u16 length, its TURN message as the
##   wire carries it (NetProtocol decodes it),
##   u32 length, the state at the bad tick (SimCodec bytes, re-simulated from the
##   checkpoint; length 0 when it could not be rebuilt),
##   u32 n, then every HASH this seat sent: u32 tick, 8 bytes hash.
##
## replay() runs a dump's turns from its checkpoint to any tick, so two seats' dumps can be
## compared tick by tick (the hash streams say where they part; the states say what).
@warning_ignore_start("integer_division")
class_name DesyncDump
extends RefCounted

const DIR := "user://desync/"
const MAGIC := "GHDD"
const FORMAT := 1


## Where the dump of `match_id`'s seat `seat` (1 to 4) goes.
static func path_for(match_id: int, seat: int) -> String:
	return "%s%d-%d.bin" % [DIR, match_id, seat]


## Writes `client`'s dump for a match that ended desynced at `bad_tick`, from what
## `checkpoints` kept; returns the path written, or "" when nothing was.
static func write(client: MatchClient, checkpoints: Checkpointing, bad_tick: int) -> String:
	if client.sim == null or client.match_id <= 0 or client.seat <= 0:
		return ""
	# (before the bad tick, not at it: a checkpoint kept there is this game's own state
	# after it parted, and KEPT = 2 still holds the one before)
	var base: Array = checkpoints.latest_at_or_before(bad_tick - 1)
	var from_tick := int(base[0])
	var from_bytes: PackedByteArray = base[1]
	var first_turn := from_tick / SimTypes.TURN_TICKS
	var turns := []
	for k in range(first_turn, client.source.complete_upto + 1):
		var wire := []
		for cmd: Dictionary in client.source.turns[k]:
			wire.append(RemoteSequencer.to_wire(cmd))
		turns.append(NetProtocol.encode("TURN", {"turn": k, "commands": wire}))
	var rules := SimContent.rules(client.mode)
	var state := PackedByteArray()
	var start: SimMatch = (
		SimMatch.new(rules, client.seat_list, client.match_seed)
		if from_bytes.is_empty()
		else SimMatch.deserialize(from_bytes, rules)
	)
	if start != null:
		var at := run_to(start, client.source.turns, bad_tick)
		if at != null:
			state = at.serialize()
	var b := StreamPeerBuffer.new()
	b.big_endian = true
	b.put_data(MAGIC.to_ascii_buffer())
	b.put_u8(FORMAT)
	b.put_u16(NetProtocol.number("version"))
	b.put_u32(client.build_seq)
	b.put_data(SimContent.rules_hash())
	b.put_u32(client.match_id)
	b.put_u8(client.seat)
	b.put_u8(int(client.config.get("mode", 0)))
	b.put_u32(client.match_seed & 0xFFFFFFFF)
	var listed: Array = client.config.get("seats", [])
	b.put_u8(listed.size())
	for entry: Dictionary in listed:
		b.put_u8(int(entry["team"]))
		b.put_u8(int(entry["builder"]))
		b.put_u8(int(entry["flags"]))
	b.put_u32(bad_tick)
	b.put_u32(from_tick)
	b.put_u32(from_bytes.size())
	b.put_data(from_bytes)
	b.put_u32(turns.size())
	for message: PackedByteArray in turns:
		b.put_u16(message.size())
		b.put_data(message)
	b.put_u32(state.size())
	b.put_data(state)
	var ticks: Array = client.sent_hashes.keys()
	ticks.sort()
	b.put_u32(ticks.size())
	for t: int in ticks:
		b.put_u32(t)
		b.put_data(str(client.sent_hashes[t]).hex_decode())
	var path := path_for(client.match_id, client.seat)
	DirAccess.make_dir_recursive_absolute(DIR)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_warning("DesyncDump: cannot write %s (%s)" % [path, error_string(FileAccess.get_open_error())])
		return ""
	file.store_buffer(b.data_array)
	file.close()
	return path


## A dump read back as a Dictionary of the fields above ({} when `path` is not a dump):
## "format", "version", "build_seq", "rules_hash", "match", "seat", "mode", "seed", "seats"
## ([{"team", "builder", "flags"}]), "bad_tick", "checkpoint_tick", "checkpoint",
## "turns" (decoded TURN fields), "state", "hashes" (tick -> hex).
static func read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var b := StreamPeerBuffer.new()
	b.big_endian = true
	b.data_array = FileAccess.get_file_as_bytes(path)
	if b.get_size() < 4 or b.get_data(4)[1].get_string_from_ascii() != MAGIC:
		return {}
	var out := {"format": b.get_u8(), "version": b.get_u16(), "build_seq": b.get_u32()}
	if int(out["format"]) != FORMAT:
		return {}
	out["rules_hash"] = _bytes(b, 8)
	out["match"] = b.get_u32()
	out["seat"] = b.get_u8()
	out["mode"] = b.get_u8()
	out["seed"] = b.get_u32()
	var seats := []
	for i in b.get_u8():
		seats.append({"team": b.get_u8(), "builder": b.get_u8(), "flags": b.get_u8()})
	out["seats"] = seats
	out["bad_tick"] = b.get_u32()
	out["checkpoint_tick"] = b.get_u32()
	out["checkpoint"] = _bytes(b, b.get_u32())
	var turns := []
	for i in b.get_u32():
		var message := NetProtocol.decode(_bytes(b, b.get_u16()))
		if message.get("type", "") != "TURN":
			return {}
		turns.append(message["fields"])
	out["turns"] = turns
	out["state"] = _bytes(b, b.get_u32())
	var hashes := {}
	for i in b.get_u32():
		var tick := b.get_u32()
		hashes[tick] = _bytes(b, 8).hex_encode()
	out["hashes"] = hashes
	if b.get_position() != b.get_size():
		return {}
	return out


## The dump's simulation at `tick`: its checkpoint (or tick 0) run through its turns; null
## when the turns end first.
static func replay(dump: Dictionary, tick: int) -> SimMatch:
	var mode := NetProtocol.enum_name("modes", int(dump["mode"]))
	var rules := SimContent.rules(mode)
	var sim: SimMatch
	if (dump["checkpoint"] as PackedByteArray).is_empty():
		var seats := []
		for entry: Dictionary in dump["seats"]:
			var builder := Profile.fielded(NetProtocol.enum_name("builders", int(entry["builder"])))
			seats.append({"team": int(entry["team"]), "builder": builder, "caretaker": (int(entry["flags"]) & 1) != 0})
		sim = SimMatch.new(rules, seats, int(dump["seed"]))
	else:
		sim = SimMatch.deserialize(dump["checkpoint"], rules)
	var log := []
	for fields: Dictionary in dump["turns"]:
		var k := int(fields["turn"])
		while log.size() <= k:
			log.append(null)
		var commands := []
		for entry: Dictionary in fields["commands"]:
			commands.append(RemoteSequencer.from_wire(entry))
		log[k] = commands
	return run_to(sim, log, tick)


## Runs `sim` through `turns` (by number; null for one not here) to `tick`; null when a
## turn it needs is missing.
static func run_to(sim: SimMatch, turns: Array, tick: int) -> SimMatch:
	while sim.tick < tick:
		if sim.tick % SimTypes.TURN_TICKS == 0 and sim.turn_applied < sim.tick / SimTypes.TURN_TICKS:
			var k := sim.tick / SimTypes.TURN_TICKS
			if k >= turns.size() or turns[k] == null:
				return null
			sim.apply_turn(k, turns[k])
		sim.step()
	return sim


static func _bytes(b: StreamPeerBuffer, count: int) -> PackedByteArray:
	if count <= 0:
		return PackedByteArray()
	var got: Array = b.get_data(count)
	return got[1] if int(got[0]) == OK else PackedByteArray()
