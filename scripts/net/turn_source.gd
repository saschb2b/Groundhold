## Where a match's turns come from (design 6.2 and 6.3): the in-process LocalSequencer
## for solo, Try, tests and replays, or the server through a RemoteSequencer. Either way
## the client submits its seat's commands here and asks for turn k before it simulates
## tick 3k; it never waits for another client, only for the turns.
##
## A command is SimTypes.command(seat, seq, type, a, b, c); a turn is an Array of them in
## the order the sequencer listed them (SimTypes.order_turn).
##
## Subclasses override submit, has_turn, take_turn and, if they read a socket, poll.
## prepare() and advance() are the driver's loop and stay as they are.
@warning_ignore_start("integer_division")
class_name TurnSource
extends RefCounted

## The seat this client commands (1-based).
var seat := 1


## Queues a command from this client's seat for the next turn. Returns its sequence
## number, or -1 when the source takes no commands (a replay).
func submit(_type: int, _a := 0, _b := 0, _c := 0) -> int:
	return -1


## Whether submit() would send a command now. Offline always; networked only while the
## match runs and its link holds (not before START, not after MATCH_END or a lost link).
func accepts_commands() -> bool:
	return true


## Whether a command submitted now would go out: accepts_commands(), and for a networked
## match a token in the command bucket.
func can_submit() -> bool:
	return accepts_commands()


## Why submit() would return -1 now, for the player ("The match has not started", "Not so
## fast"); "" when it would send.
func refusal() -> String:
	return ""


## Whether turn `turn`'s commands have arrived.
func has_turn(_turn: int) -> bool:
	return false


## Turn `turn`'s commands in execution order. Called once has_turn(turn) is true.
func take_turn(_turn: int) -> Array:
	return []


## Once per frame, before stepping: a network source reads its socket here.
func poll() -> void:
	pass


## Whether scenario setters may write into the match (offline only; a server refuses).
func allows_debug() -> bool:
	return false


## Logs a debug write made at the start of `tick`, so a replay reproduces it.
func record_debug(_tick: int, _op: int, _a: int, _b: int, _c: int) -> void:
	pass


## Debug writes to apply at the start of `tick` when replaying; each is returned once.
func debug_at(_tick: int) -> Array:
	return []


## Gets `sim` ready to step its current tick: replays any debug write logged for it and,
## at a turn boundary, applies the turn. False when that turn has not arrived yet, so
## the caller waits (the world pauses for this client only).
func prepare(sim: SimMatch) -> bool:
	for entry: Array in debug_at(sim.tick):
		sim.debug(entry[1], entry[2], entry[3], entry[4])
	if sim.tick % SimTypes.TURN_TICKS != 0:
		return true
	var turn := sim.tick / SimTypes.TURN_TICKS
	if sim.turn_applied >= turn:
		return true
	if not has_turn(turn):
		return false
	sim.apply_turn(turn, take_turn(turn))
	return true


## Steps `sim` by up to `max_ticks` ticks while its turns are here; calls `on_tick` with
## the new tick after each step. Returns how many ticks ran.
func advance(sim: SimMatch, max_ticks: int, on_tick := Callable()) -> int:
	var ran := 0
	while ran < max_ticks:
		if not prepare(sim):
			break
		sim.step()
		ran += 1
		if on_tick.is_valid():
			on_tick.call(sim.tick)
	return ran
