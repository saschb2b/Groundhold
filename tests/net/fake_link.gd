## A socket inside one process (test level 1, design 7.1): one MatchClient's link to the
## fake sequencer, with seeded latency and jitter in frames. Messages keep their order,
## as TCP keeps it: jitter only ever delays a message behind the one before it.
##
## The loopback scene owns the clock (`world.frame`); the fake sequencer reads what the
## client sent with take_up() and answers with push_down(). drop() closes the link from
## the server's end once what it already sent (an ERROR) has arrived, as the server
## lets a game read its ERROR before the close.
extends NetLink

var world
## One-way delay in frames, and up to this many frames more at random.
var latency := 0
var jitter := 0
## The fake sequencer's record of this connection.
var conn: Variant = null

var _up: Array = []  # [frame it arrives, bytes], client to server
var _down: Array = []  # server to client
var _last_up := 0
var _last_down := 0
var _rng := 1
# (the frame a server-side drop closes the link, after what was sent before it; -1 none)
var _drop_at := -1
var _drop_reason := ""
var _drop_code := 1008


func _init(owner_world: Variant, delay_frames := 0, jitter_frames := 0, seed_value := 1) -> void:
	world = owner_world
	latency = delay_frames
	jitter = jitter_frames
	_rng = maxi(1, seed_value & 0xFFFFFFFF)


func open(address_url: String) -> Error:
	url = address_url
	_status = Status.OPEN
	world.seq.accept(self)
	return OK


func poll() -> void:
	if _status != Status.OPEN:
		return
	while not _down.is_empty() and int(_down[0][0]) <= world.frame:
		_inbox.append(_down.pop_front()[1])
	if _drop_at >= 0 and world.frame >= _drop_at:
		close_code = _drop_code
		_close_with(_drop_reason)


func send(message: PackedByteArray) -> bool:
	if _status != Status.OPEN or _drop_at >= 0:
		return false
	_last_up = maxi(_last_up, world.frame + latency + _jitter())
	_up.append([_last_up, message])
	return true


func close(_code := 1000, reason := "") -> void:
	if _status == Status.OPEN and _drop_at < 0 and conn != null:
		world.seq.closed(self)
	_close_with(reason if reason != "" else "Closed")


## The server's end: messages from the client that have arrived by now.
func take_up() -> Array[PackedByteArray]:
	var out: Array[PackedByteArray] = []
	if _drop_at >= 0:
		return out  # (the server reads nothing more from a connection it dropped)
	while not _up.is_empty() and int(_up[0][0]) <= world.frame:
		out.append(_up.pop_front()[1])
	return out


## The server's end: a message on its way to the client.
func push_down(message: PackedByteArray) -> void:
	if _status != Status.OPEN or _drop_at >= 0:
		return
	_last_down = maxi(_last_down, world.frame + latency + _jitter())
	_down.append([_last_down, message])


## The server closes this link (after an ERROR, or at the end): it closes for the client
## once what was sent before has arrived.
func drop(reason: String, code := 1008) -> void:
	if _drop_at < 0:
		_drop_at = maxi(_last_down, world.frame)
		_drop_reason = reason
		_drop_code = code


## Whether the server's end is gone (dropped, or closed by the client).
func is_dropped() -> bool:
	return _drop_at >= 0 or is_closed()


## Messages waiting to reach the client (a stalled client's backlog).
func backlog() -> int:
	return _down.size()


func _jitter() -> int:
	if jitter <= 0:
		return 0
	_rng ^= (_rng << 13) & 0xFFFFFFFF
	_rng ^= _rng >> 17
	_rng ^= (_rng << 5) & 0xFFFFFFFF
	return _rng % (jitter + 1)
