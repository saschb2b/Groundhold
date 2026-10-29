## How many ticks a networked client runs this frame (design 6.3).
##
## A client may run tick t only once the turn holding it has arrived. It keeps a small
## buffer of turns, B, so the jitter of the network does not stall it:
##   B = clamp(ceil((ping mean + 2 x ping spread) / turn), 2, 6) over the last 10 pings.
## It plays 60 ticks a second, 5% slower while it holds fewer than B turns and 5% faster
## while it holds more than B + 1, so the buffer settles near B. More than 20 turns
## behind (a stall, a hidden tab), it catches up at up to 8 ticks a frame within 8 ms;
## with nothing buffered it waits: the world pauses for this player only.
##
## Arithmetic is integer per mille, so a run fed the same arrivals plays the same frames.
@warning_ignore_start("integer_division")
class_name Playout
extends RefCounted

const MIN_TURNS := 2
const MAX_TURNS := 6
const SAMPLES := 10
## Pings timed across a frame longer than this are not samples (the browser lesson).
const SLOW_FRAME_MS := 50
const CATCH_UP_TURNS := 20
const CATCH_UP_TICKS := 8
const CATCH_UP_USEC := 8000
## +-5% around the nominal rate, per mille.
const DRIFT_PM := 50

## The server's turn length and ticks per turn (WELCOME).
var turn_ms := 50
var turn_ticks := 3
## Frames per second the host calls ticks_for_frame at (physics ticks).
var frames_per_second := 60
## B, in turns.
var target_turns := MIN_TURNS
## False until the first B turns have arrived: the first tick waits for a full buffer.
var started := false
var catching_up := false

var _samples: Array[int] = []
var _acc_pm := 0


## A round trip, in milliseconds, from a PING's PONG.
func add_sample(rtt_ms: int) -> void:
	_samples.append(maxi(0, rtt_ms))
	while _samples.size() > SAMPLES:
		_samples.pop_front()
	target_turns = buffer_for(_samples, turn_ms)


## B for a list of round trips.
static func buffer_for(samples: Array[int], turn_length_ms: int) -> int:
	if samples.is_empty():
		return MIN_TURNS
	var total := 0
	for s in samples:
		total += s
	var mean := float(total) / samples.size()
	var spread := 0.0
	for s in samples:
		spread += (s - mean) * (s - mean)
	spread = sqrt(spread / samples.size())
	var turns := ceili((mean + 2.0 * spread) / maxi(1, turn_length_ms))
	return clampi(turns, MIN_TURNS, MAX_TURNS)


## The ticks to run this frame when `available` ticks' turns are here.
func ticks_for_frame(available: int) -> int:
	if available <= 0:
		_acc_pm = mini(_acc_pm, 0)
		return 0
	var buffered := available / turn_ticks
	if not started:
		if buffered < target_turns:
			return 0
		started = true
	if buffered > CATCH_UP_TURNS:
		catching_up = true
	if catching_up:
		if buffered > target_turns + 1:
			return mini(CATCH_UP_TICKS, available)
		catching_up = false
	var rate := 1000
	if buffered > target_turns + 1:
		rate += DRIFT_PM
	elif buffered < target_turns:
		rate -= DRIFT_PM
	_acc_pm += nominal_pm() * rate / 1000
	var ticks := mini(_acc_pm / 1000, available)
	_acc_pm -= ticks * 1000
	# (no credit is banked while the buffer runs dry)
	_acc_pm = mini(_acc_pm, 1000)
	return ticks


## Ticks per frame at the nominal rate, per mille: 1000 for 3 ticks per 50 ms at 60 frames.
func nominal_pm() -> int:
	return turn_ticks * 1000 * 1000 / maxi(1, turn_ms * frames_per_second)


## The time a frame may spend catching up, in microseconds; 0 for no limit.
func budget_usec() -> int:
	return CATCH_UP_USEC if catching_up else 0
