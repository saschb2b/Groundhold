## A socket inside one process (test level 1, design 7.1): one MatchClient's link to the
## fake sequencer, with seeded latency and jitter in frames. Messages keep their order,
## as TCP keeps it: jitter only ever delays a message behind the one before it.
##
## The loopback scene owns the clock (`world.frame`); the fake sequencer reads what the
## client sent with take_up() and answers with push_down(). drop() closes the link from
## the server's end once what it already sent (an ERROR) has arrived, as the server
## lets a game read its ERROR before the close.
##
## Faults (M4, design 7.2): cut() loses the link at once, both ways, with what was on its
## way (a cable pulled: the client sees 1006); a world that refuses links for a while
## (world.refuses(link)) makes open() fail as a server that does not answer, and one that
## black-holes them (world.black_holes(link)) leaves them connecting for good; hide() and
## buffer_hidden() model a background tab: the client does not read, and what arrives
## fills the engine's inbound buffer (`inbound_bytes`, NetLink's 1 MiB unless a test sets
## less), dropping whole messages that no longer fit; corrupt_parts flips a byte of every
## CHECKPOINT_PART the client uploads; delay() changes the latency and jitter mid-run;
## mute() lets nothing through either way and never closes (a stalled router, Wi-Fi gone),
## and abort() is the client dropping such a link with no handshake (the server is not told).
extends NetLink

var world
## One-way delay in frames, and up to this many frames more at random.
var latency := 0
var jitter := 0
## The fake sequencer's record of this connection.
var conn: Variant = null
## Which loopback client this link belongs to (1-based; 0 unknown), for world.refuses().
var client_index := 0
## The engine's inbound buffer while the client does not read (a hidden tab), in bytes.
var inbound_bytes := NetLink.INBOUND_BYTES
## Whole messages dropped because the inbound buffer was full.
var dropped := 0
## Every CHECKPOINT_PART this client sends goes up with one byte of its data flipped.
var corrupt_parts := false
## Bytes the client sent, and that went down to it (what a shaper or a budget counts).
var bytes_up := 0
var bytes_down := 0
## mute(): whatever either end sends is lost, and the link stays open.
var muted := false

var _up: Array = []  # [frame it arrives, bytes], client to server
var _down: Array = []  # server to client
var _last_up := 0
var _last_down := 0
var _rng := 1
# (the frame a server-side drop closes the link, after what was sent before it; -1 none)
var _drop_at := -1
var _drop_reason := ""
var _drop_code := 1008
var _inbox_bytes := 0


func _init(owner_world: Variant, delay_frames := 0, jitter_frames := 0, seed_value := 1) -> void:
	world = owner_world
	latency = delay_frames
	jitter = jitter_frames
	_rng = maxi(1, seed_value & 0xFFFFFFFF)


func open(address_url: String) -> Error:
	url = address_url
	if world.has_method("refuses") and world.refuses(self):
		close_code = 1006
		_close_with("No server answers at " + url)
		return ERR_CANT_CONNECT
	if world.has_method("black_holes") and world.black_holes(self):
		_status = Status.CONNECTING  # (its SYN goes nowhere: it never opens nor fails)
		return OK
	_status = Status.OPEN
	world.seq.accept(self)
	return OK


func poll() -> void:
	if _status != Status.OPEN:
		return
	while not _down.is_empty() and int(_down[0][0]) <= world.frame:
		_inbox.append(_down.pop_front()[1])
	_inbox_bytes = 0
	if _drop_at >= 0 and world.frame >= _drop_at:
		close_code = _drop_code
		_close_with(_drop_reason)


## While the client does not read (a hidden tab): what has arrived goes into the inbound
## buffer as the browser delivers it, and a message that does not fit is dropped whole.
func buffer_hidden() -> void:
	if _status != Status.OPEN:
		return
	while not _down.is_empty() and int(_down[0][0]) <= world.frame:
		var message: PackedByteArray = _down.pop_front()[1]
		if _inbox_bytes + message.size() > inbound_bytes:
			dropped += 1
			continue
		_inbox_bytes += message.size()
		_inbox.append(message)


func send(message: PackedByteArray) -> bool:
	if _status != Status.OPEN or _drop_at >= 0:
		return false
	if muted:
		return true  # (written, and lost on the way)
	if corrupt_parts and not message.is_empty() and message[0] == NetProtocol.message_id("CHECKPOINT_PART"):
		message = message.duplicate()
		message[message.size() - 1] ^= 0x5A
	_last_up = maxi(_last_up, world.frame + latency + _jitter())
	_up.append([_last_up, message])
	bytes_up += message.size()
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
	if _status != Status.OPEN or _drop_at >= 0 or muted:
		return
	_last_down = maxi(_last_down, world.frame + latency + _jitter())
	_down.append([_last_down, message])
	bytes_down += message.size()


## The server closes this link (after an ERROR, or at the end): it closes for the client
## once what was sent before has arrived.
func drop(reason: String, code := 1008) -> void:
	if _drop_at < 0:
		_drop_at = maxi(_last_down, world.frame)
		_drop_reason = reason
		_drop_code = code


## The link is lost at once, both ways (a cable pulled): what was on its way is gone, the
## client sees the close (1006) and the server stops reading it. The seat is held.
func cut() -> void:
	if _status != Status.OPEN:
		return
	_down.clear()
	_up.clear()
	_drop_at = world.frame
	_drop_reason = "The connection closed"
	_drop_code = 1006
	close_code = 1006
	_close_with(_drop_reason)


## Nothing gets through either way from now on (`on`), what was on its way included, and
## neither end learns of it: the link stays open (a stalled router, a hotspot gone).
func mute(on := true) -> void:
	muted = on
	if on:
		_down.clear()
		_up.clear()


## The client drops the link at once, with no handshake (MatchClient on a link gone
## silent): the server reads nothing more from it and is not told, so the seat is held.
func abort(reason: String) -> void:
	if _status == Status.OPEN:
		_down.clear()
		_up.clear()
		_drop_at = world.frame
		_drop_reason = reason
		_drop_code = 1006
	close_code = 1006
	_close_with(reason)


## Another latency and jitter, in frames, from now on (a shaper's change).
func delay(delay_frames: int, jitter_frames := 0) -> void:
	latency = delay_frames
	jitter = jitter_frames


## Whether the server's end is gone (dropped, or closed by the client).
func is_dropped() -> bool:
	return _drop_at >= 0 or is_closed()


## Messages waiting to reach the client (a stalled client's backlog).
func backlog() -> int:
	return _down.size()


## Bytes on their way to the client and not yet there: the server's unsent output, as the
## catch-up's pacing reads it.
func in_flight() -> int:
	var total := 0
	for entry: Array in _down:
		total += (entry[1] as PackedByteArray).size()
	return total


func _jitter() -> int:
	if jitter <= 0:
		return 0
	_rng ^= (_rng << 13) & 0xFFFFFFFF
	_rng ^= _rng >> 17
	_rng ^= (_rng << 5) & 0xFFFFFFFF
	return _rng % (jitter + 1)
