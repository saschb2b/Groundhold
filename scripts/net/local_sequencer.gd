## The in-process sequencer (design 6.2 and 6.3): solo, Try and tests run the same
## simulation through it as a networked match runs through the server. It seals a turn
## the moment the simulation asks for it, with a playout buffer of zero, so a command
## lands within one turn (3 ticks, 50 ms). Pausing stops it.
##
## Commands from any seat can be submitted (submit_as), so one sequencer can stand in
## for a whole party in tests: every client that asks for turn k gets the same list.
## It keeps the turn log and the debug writes, which is all a replay needs.
class_name LocalSequencer
extends TurnSource

var seat_count := 1
## While true no turn is sealed and the match stands still.
var paused := false
## Every sealed turn, by turn number: the turn log.
var turns: Array = []
## Debug writes as [tick, op, a, b, c], in the order they were made.
var debug_log: Array = []

var _pending: Array = []
var _last_seq := PackedInt32Array()
var _replaying := false
var _debug_cursor := 0


func _init(seats := 1, my_seat := 1) -> void:
	seat_count = maxi(1, seats)
	seat = my_seat
	# Index 0 counts the system seat's commands, 1 to n the players'.
	_last_seq.resize(seat_count + 1)


## A sequencer that hands out a recorded log instead of sealing new turns.
static func replaying(log_turns: Array, log_debug: Array, seats := 1) -> LocalSequencer:
	var source := LocalSequencer.new(seats)
	source.turns = log_turns
	source.debug_log = log_debug
	source._replaying = true
	return source


func submit(type: int, a := 0, b := 0, c := 0) -> int:
	return submit_as(seat, type, a, b, c)


## Queues a command as any seat; the sequencer stamps it with that seat and the seat's
## next sequence number.
func submit_as(from_seat: int, type: int, a := 0, b := 0, c := 0) -> int:
	if _replaying or from_seat < 1 or from_seat > seat_count:
		return -1
	_last_seq[from_seat] += 1
	var seq := _last_seq[from_seat]
	_pending.append(SimTypes.command(from_seat, seq, type, a, b, c))
	return seq


## Queues a system command (AWAY, BACK, LEFT, TIMEOUT) as the server would.
func system(type: int, a := 0) -> void:
	_last_seq[0] += 1
	_pending.append(SimTypes.command(SimTypes.SYSTEM_SEAT, _last_seq[0], type, a))


## Commands waiting for the next turn.
func pending() -> Array:
	return _pending


func has_turn(turn: int) -> bool:
	if _replaying:
		return turn < turns.size()
	return turn < turns.size() or not paused


func take_turn(turn: int) -> Array:
	if turn < turns.size():
		return turns[turn]
	# Sealed on demand; a turn nobody asked for (a gap) is empty.
	while turns.size() < turn:
		turns.append([])
	var sealed := SimTypes.order_turn(turn, _pending, seat_count)
	_pending = []
	turns.append(sealed)
	return sealed


func allows_debug() -> bool:
	return not _replaying


func record_debug(tick: int, op: int, a: int, b: int, c: int) -> void:
	if not _replaying:
		debug_log.append([tick, op, a, b, c])


func debug_at(tick: int) -> Array:
	if not _replaying:
		return []
	var out := []
	while _debug_cursor < debug_log.size() and int(debug_log[_debug_cursor][0]) <= tick:
		out.append(debug_log[_debug_cursor])
		_debug_cursor += 1
	return out


## Everything a replay needs: the match's set-up and its log.
func log_for(sim: SimMatch, seat_list: Array) -> Dictionary:
	return {
		"mode": sim.mode,
		"seed": sim.match_seed,
		"seats": seat_list,
		"turns": turns.duplicate(),
		"debug": debug_log.duplicate(),
	}


## Plays a recorded log into a fresh match up to `to_tick`. With `hashes`, records the
## state hash at every HASH_EVERY tick into it (tick -> hex).
static func replay(record: Dictionary, to_tick: int, hashes := {}) -> SimMatch:
	var seat_list: Array = record["seats"]
	var sim := SimMatch.new(SimContent.rules(str(record["mode"])), seat_list, int(record["seed"]))
	sim.events_on = false
	var source := LocalSequencer.replaying(record["turns"], record["debug"], seat_list.size())
	while sim.tick < to_tick:
		if source.advance(sim, 1) == 0:
			break
		if sim.tick % SimTypes.HASH_EVERY == 0:
			hashes[sim.tick] = sim.state_hash_hex()
	return sim
