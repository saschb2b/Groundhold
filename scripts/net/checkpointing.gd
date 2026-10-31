## A networked client's checkpoints (design 6.7; docs/design/contract-m4.md): its own
## serialized state at the last two checkpoint ticks, uploaded in parts when the server's
## CHECKPOINT_ASK names one of them; and the parts of a checkpoint the server sends after
## RESYNC, put back together and checked before the client loads them.
##
## A checkpoint tick is a hash tick T (T a positive multiple of HASH_EVERY) where
##   T % CHECKPOINT_EVERY == 0, or some hollow's `wave` at T differs from its `wave` at
##   T - HASH_EVERY (the first hash tick at or after a horn).
## Every client reads it from its own simulation, so all of them flag the same ticks: HASH
## carries hash_flags.checkpoint on them, and the client keeps SimMatch.serialize() there.
## A checkpoint's digest (SHA-256 of its bytes, first 8 bytes) is the state hash HASH sent
## for its tick; the server keeps an upload only when the digest is the hash the seats
## agreed (protocol.py digest()). Tick 0 is never uploaded: every client builds it from
## MATCH_CONFIG, and LOADED's tick-0 hash is its agreed hash.
##
## Parts: CHECKPOINT_PART(tick, part, parts, data) in order from part 0, every one but the
## last exactly checkpoint_part (1,024) bytes, at most max_checkpoint_parts (64) of them,
## the same split both ways (protocol.py checkpoint_parts()).
##
## MatchClient calls it: at_hash_tick() after every hash tick (it keeps the bytes and gives
## HASH its flags and its hash, so the state is serialized once a hash tick), upload() for
## CHECKPOINT_ASK, and begin_download(), add_part(), download_done() and downloaded() for
## the parts behind a RESYNC. restart_at() sets it up again on a loaded checkpoint.
@warning_ignore_start("integer_division")
class_name Checkpointing
extends RefCounted

## How many checkpoint ticks a client keeps (protocol.json checkpoints_kept).
const KEPT := 2

## The checkpoint ticks kept, oldest first, and their bytes, by the same index.
var ticks := PackedInt32Array()
var kept: Array[PackedByteArray] = []
## The state hash at_hash_tick() computed last (the digest of the bytes it serialized).
var last_hash := PackedByteArray()

# (the hollows' waves at the last hash tick seen, and that tick: is_checkpoint_tick's
# `waves_then` when it is the hash tick just before)
var _waves := PackedInt32Array()
var _waves_tick := -1
# (the download behind a RESYNC: its tick, parts, digest and the bytes so far)
var _down_tick := -1
var _down_parts := 0
var _down_digest := PackedByteArray()
var _down_next := 0
var _down_bytes := PackedByteArray()


## Whether `tick` is a checkpoint tick: `waves_now` are the hollows' `wave` numbers at
## `tick`, `waves_then` at the hash tick before it (empty before the first hash tick).
static func is_checkpoint_tick(
	tick: int, waves_now: PackedInt32Array, waves_then: PackedInt32Array
) -> bool:
	if tick <= 0 or tick % SimTypes.HASH_EVERY != 0:
		return false
	if tick % SimTypes.CHECKPOINT_EVERY == 0:
		return true
	return not waves_then.is_empty() and waves_now != waves_then


## The hollows' `wave` numbers, in hollow order: what is_checkpoint_tick compares.
static func waves_of(sim: SimMatch) -> PackedInt32Array:
	var out := PackedInt32Array()
	for h in sim.hollows:
		out.append(h.wave)
	return out


## A checkpoint's digest: the first 8 bytes of SHA-256, equal to SimMatch.state_hash() of
## the state the bytes hold.
static func digest(bytes: PackedByteArray) -> PackedByteArray:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	if not bytes.is_empty():
		ctx.update(bytes)
	return ctx.finish().slice(0, NetProtocol.number("hash_bytes"))


## `bytes` as the CHECKPOINT_PART fields of `tick`, in order; [] for no bytes or for more
## than max_checkpoint_parts parts.
static func split(tick: int, bytes: PackedByteArray) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var size := NetProtocol.number("checkpoint_part")
	var parts := (bytes.size() + size - 1) / size
	if parts == 0 or parts > NetProtocol.number("max_checkpoint_parts"):
		return out
	for i in parts:
		out.append({"tick": tick, "part": i, "parts": parts, "data": bytes.slice(i * size, (i + 1) * size)})
	return out


## After the step that reached hash tick `tick` (MatchClient.after_tick): keeps the state
## when it is a checkpoint tick (dropping the oldest past KEPT) and returns HASH's flags,
## hash_flags.checkpoint or 0. `last_hash` is the state hash there.
func at_hash_tick(sim: SimMatch, tick: int) -> int:
	var bytes := sim.serialize()
	last_hash = digest(bytes)
	var now := waves_of(sim)
	var then := _waves if _waves_tick == tick - SimTypes.HASH_EVERY else PackedInt32Array()
	_waves = now
	_waves_tick = tick
	if not is_checkpoint_tick(tick, now, then):
		return 0
	keep(tick, bytes)
	return int(NetProtocol.spec()["hash_flags"]["checkpoint"])


## Keeps `bytes` as the checkpoint at `tick` (replacing one kept there), the oldest going
## past KEPT.
func keep(tick: int, bytes: PackedByteArray) -> void:
	var i := ticks.find(tick)
	if i >= 0:
		ticks.remove_at(i)
		kept.remove_at(i)
	# (ticks stay in order: a tick past a later one kept drops that one, as after a load)
	while not ticks.is_empty() and ticks[ticks.size() - 1] > tick:
		ticks.remove_at(ticks.size() - 1)
		kept.pop_back()
	ticks.append(tick)
	kept.append(bytes)
	while ticks.size() > KEPT:
		ticks.remove_at(0)
		kept.pop_front()


## The simulation was loaded from a checkpoint (RESYNC) or built again at tick 0: what was
## kept past it is gone (it may hold the state that went apart), the loaded bytes are kept
## as its checkpoint, and the waves count from it.
func restart_at(sim: SimMatch, bytes: PackedByteArray) -> void:
	while not ticks.is_empty() and ticks[ticks.size() - 1] >= sim.tick:
		ticks.remove_at(ticks.size() - 1)
		kept.pop_back()
	if sim.tick > 0 and not bytes.is_empty():
		keep(sim.tick, bytes)
	_waves = waves_of(sim)
	_waves_tick = sim.tick


## The latest checkpoint kept at or before `tick`: [tick, bytes], or [0, empty] for none
## (tick 0 is built from MATCH_CONFIG).
func latest_at_or_before(tick: int) -> Array:
	for i in range(ticks.size() - 1, -1, -1):
		if ticks[i] <= tick:
			return [ticks[i], kept[i]]
	return [0, PackedByteArray()]


func has_tick(tick: int) -> bool:
	return ticks.has(tick)


## The bytes kept for `tick`, or empty.
func bytes_at(tick: int) -> PackedByteArray:
	var i := ticks.find(tick)
	return kept[i] if i >= 0 else PackedByteArray()


## CHECKPOINT_ASK(tick): the parts to send, or [] when `tick` is not kept (the server then
## waits checkpoint_wait_ms and asks another seat).
func upload(tick: int) -> Array[Dictionary]:
	return split(tick, bytes_at(tick))


## RESYNC: expects `parts` parts of `tick` whose digest must be `digest_expected`.
func begin_download(tick: int, parts: int, digest_expected: PackedByteArray) -> void:
	_down_tick = tick
	_down_parts = parts
	_down_digest = digest_expected
	_down_next = 0
	_down_bytes = PackedByteArray()


## One CHECKPOINT_PART of the download (its decoded fields); false when it does not belong
## (another tick, out of order, a part past `parts`, a changed count, a short part before
## the last).
func add_part(fields: Dictionary) -> bool:
	if _down_tick < 0 or download_done():
		return false
	var data: PackedByteArray = fields["data"]
	var size := NetProtocol.number("checkpoint_part")
	if int(fields["tick"]) != _down_tick or int(fields["part"]) != _down_next or int(fields["parts"]) != _down_parts:
		return false
	var last := _down_next == _down_parts - 1
	if data.is_empty() or data.size() > size or (not last and data.size() != size):
		return false
	_down_bytes.append_array(data)
	_down_next += 1
	return true


## Whether every part arrived.
func download_done() -> bool:
	return _down_tick >= 0 and _down_next >= _down_parts


## How many parts of the download have arrived, and of how many: [got, parts].
func download_progress() -> Array:
	return [_down_next, _down_parts] if _down_tick >= 0 else [0, 0]


## The downloaded bytes when they are whole and their digest is RESYNC's; else empty (the
## client then fails the link: a server never sends a checkpoint it did not check).
func downloaded() -> PackedByteArray:
	if not download_done() or _down_parts == 0 or digest(_down_bytes) != _down_digest:
		return PackedByteArray()
	return _down_bytes


## Forgets the download (it was loaded, or the link that sent it is gone).
func end_download() -> void:
	_down_tick = -1
	_down_parts = 0
	_down_next = 0
	_down_bytes = PackedByteArray()
