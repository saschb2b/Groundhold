## The server's turns behind the TurnSource interface (design 6.3): the same simulation
## loop that plays solo through the LocalSequencer plays a networked match through this.
##
## The MatchClient hands it every TURN the server sends; the simulation asks for turn k
## before it runs tick 3k and waits while it has not arrived. My commands go out through
## `send` (a CMD each) and come back stamped inside some later turn, the same turn for
## every client.
##
## Seats are 0-based on the wire (0 to 3, 255 the server) and 1-based in the simulation;
## the conversion happens here, for the stamped seat and for the seat a system command
## (AWAY, BACK, LEFT) names. The order of a turn's commands is the server's, never
## re-sorted: SimTypes.order_turn is the same rule, and the server already applied it.
##
## The server's CMD bucket (protocol.json buckets.cmd: 10 deep, 5 a second) is mirrored
## here with CMD_RESERVE tokens kept back, so a burst the network bunches up on its way
## never empties the server's: over it, a command is refused here ("Not so fast") rather
## than costing the connection (ERROR 8).
class_name RemoteSequencer
extends TurnSource

## The furthest past the last turn with none missing below it that a TURN may be: an
## hour of turns (the server's match cap). A TURN beyond it is refused, and the link
## fails. (Measured from what is complete, never from the highest seen, so a chain of
## TURNs each an hour past the last cannot walk the log toward any size.)
const MAX_TURNS_AHEAD := 72000
## Tokens of the server's CMD bucket this side never spends: 400 ms of network jitter.
const CMD_RESERVE := 2

## Every turn received, by number (null for one not received yet): the match's turn log.
var turns: Array = []
## The highest turn number below which every turn has arrived, minus one.
var complete_upto := -1
## The highest turn number seen.
var highest := -1
## Sends a CMD: called with (seq, type, a, b, c). Set by the MatchClient.
var send: Callable
## While false (before START, after MATCH_END, or a refused seat) submit() sends nothing;
## `closed_note` says why to the player.
var open := true
var closed_note := ""
## Milliseconds of the MatchClient's clock, for the command bucket. Without it the
## bucket never runs dry.
var clock := Callable()

var _seq := 0
# (the bucket in thousandths of a command, as of _filled_at; -1: full, not started)
var _tokens_pm := -1
var _filled_at := 0


func submit(type: int, a := 0, b := 0, c := 0) -> int:
	if not can_submit():
		return -1
	# (CMD.seq is a u16 the server wants increasing: a match never sends 65,535 commands,
	# five a second being the most its bucket lets through)
	if _seq >= 0xFFFF:
		return -1
	_tokens_pm -= 1000
	_seq += 1
	send.call(_seq, type, a, b, c)
	return _seq


func accepts_commands() -> bool:
	return open and send.is_valid()


func can_submit() -> bool:
	if not accepts_commands():
		return false
	_refill()
	return _tokens_pm >= (1 + CMD_RESERVE) * 1000


func refusal() -> String:
	if not accepts_commands():
		return closed_note if closed_note != "" else "The match has not started"
	if not can_submit():
		return "Not so fast"
	return ""


func _refill() -> void:
	var bucket: Dictionary = NetProtocol.spec()["buckets"]["cmd"]
	var full := int(bucket["burst"]) * 1000
	if not clock.is_valid():
		_tokens_pm = full
		return
	var now := int(clock.call())
	if _tokens_pm < 0:
		_tokens_pm = full
	else:
		# (refill a second, in thousandths of a command per millisecond)
		_tokens_pm = mini(full, _tokens_pm + maxi(0, now - _filled_at) * int(bucket["refill"]))
	_filled_at = now


## A TURN as the codec decoded it: its number and the stamped commands in order. False
## for a turn number no server sends (more than an hour past the turns complete).
func receive_turn(turn: int, wire_commands: Array) -> bool:
	if turn > complete_upto + 1 + MAX_TURNS_AHEAD:
		return false
	if turn < turns.size() and turns[turn] != null:
		return true  # a repeat (TURN_REQUEST overlaps what was already here)
	var commands := []
	for entry: Dictionary in wire_commands:
		commands.append(from_wire(entry))
	while turns.size() <= turn:
		turns.append(null)
	turns[turn] = commands
	highest = maxi(highest, turn)
	while complete_upto + 1 < turns.size() and turns[complete_upto + 1] != null:
		complete_upto += 1
	return true


## A wire command as the simulation reads it: 1-based seats.
static func from_wire(entry: Dictionary) -> Dictionary:
	var seat_no: int = entry["seat"]
	var type: int = entry["type"]
	var a: int = entry["a"]
	if seat_no == SimTypes.SYSTEM_SEAT:
		if type in [SimTypes.SYS_AWAY, SimTypes.SYS_BACK, SimTypes.SYS_LEFT]:
			a += 1
		return SimTypes.command(SimTypes.SYSTEM_SEAT, int(entry["seq"]), type, a, entry["b"], entry["c"])
	return SimTypes.command(seat_no + 1, int(entry["seq"]), type, a, entry["b"], entry["c"])


## The first turn number missing below the highest one seen, or -1 when there is no gap.
func first_gap() -> int:
	return complete_upto + 1 if complete_upto < highest else -1


func has_turn(turn: int) -> bool:
	return turn < turns.size() and turns[turn] != null


func take_turn(turn: int) -> Array:
	return turns[turn]


## How many ticks `sim` could run now with the turns that are here.
func ticks_available(sim: SimMatch) -> int:
	if sim == null:
		return 0
	return maxi(0, (complete_upto + 1) * SimTypes.TURN_TICKS - sim.tick)


## Everything a replay needs, as LocalSequencer.log_for gives it (the turns received so far).
func log_for(sim: SimMatch, seat_list: Array) -> Dictionary:
	var done := turns.slice(0, complete_upto + 1)
	return {"mode": sim.mode, "seed": sim.match_seed, "seats": seat_list, "turns": done, "debug": []}
