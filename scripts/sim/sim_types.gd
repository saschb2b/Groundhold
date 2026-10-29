## The simulation's shared vocabulary: command types, refusal reasons, event types,
## hollow phases, seat states and the debug writes an offline match may log. The turn
## sources, the server's sequencer and the views all use these numbers, so they are
## part of the contract between the tracks (design 6.4 and 6.5).
##
## A command is a Dictionary {seat, seq, type, a, b, c}: the seat that sent it (255 for
## the server's system commands), its sequence number from that seat, the type and three
## signed 32-bit arguments. A turn is an Array of commands in execution order.
class_name SimTypes
extends RefCounted

const TICKS_PER_SECOND := 60
## A turn covers three ticks (50 ms); turn k is applied at the start of tick 3k.
const TURN_TICKS := 3
## Clients hash the state every 60 ticks (design 6.7).
const HASH_EVERY := 60
## Seat number the sequencer stamps on its own commands (AWAY, BACK, LEFT, TIMEOUT).
const SYSTEM_SEAT := 255

# ── Commands a seat sends (CMD.type) ──
const CMD_BUILD := 1  # a slot 0..2, b x, c z
const CMD_FORK := 2  # a tower id, b branch 0 (A) or 1 (B)
const CMD_SELL := 3  # a tower id
const CMD_READY := 4  # a 1 ready, 0 not ready
const CMD_SIGNAL := 5  # a x mm, b z mm, c target id (0 for the ground)
const CMD_CORK := 6  # M7: a tier, b and c the commit's two 32-bit halves
const CMD_UNCORK := 7  # M7: a pack, b and c the salt's two 32-bit halves
const CMD_SEAWALL := 8  # M7
# ── System commands, stamped with SYSTEM_SEAT ──
const SYS_AWAY := 64  # a seat
const SYS_BACK := 65  # a seat
const SYS_LEFT := 66  # a seat
const SYS_TIMEOUT := 67  # the server's hard match cap

const COMMAND_NAMES := {
	CMD_BUILD: "BUILD",
	CMD_FORK: "FORK",
	CMD_SELL: "SELL",
	CMD_READY: "READY",
	CMD_SIGNAL: "SIGNAL",
	CMD_CORK: "CORK",
	CMD_UNCORK: "UNCORK",
	CMD_SEAWALL: "SEAWALL",
	SYS_AWAY: "AWAY",
	SYS_BACK: "BACK",
	SYS_LEFT: "LEFT",
	SYS_TIMEOUT: "TIMEOUT",
}
const COMMAND_TYPES := {
	"BUILD": CMD_BUILD,
	"FORK": CMD_FORK,
	"SELL": CMD_SELL,
	"READY": CMD_READY,
	"SIGNAL": CMD_SIGNAL,
	"CORK": CMD_CORK,
	"UNCORK": CMD_UNCORK,
	"SEAWALL": CMD_SEAWALL,
	"AWAY": SYS_AWAY,
	"BACK": SYS_BACK,
	"LEFT": SYS_LEFT,
	"TIMEOUT": SYS_TIMEOUT,
}

# ── Why a command was refused (the REJECTED event's reason) ──
const REFUSE_CANNOT_BUILD_THERE := 1
const REFUSE_NOT_ENOUGH_GOLD := 2
const REFUSE_WRONG_PHASE := 3
const REFUSE_NOT_YOURS := 4
const REFUSE_ALREADY_FORKED := 5
const REFUSE_RATE_LIMITED := 6
const REFUSE_NO_CORKS_LEFT := 7
const REFUSE_TOO_EARLY := 8
const REFUSE_NOTHING_CORKED := 9
const REFUSE_BAD_REVEAL := 10
const REFUSE_NO_CHARGE := 11
const REFUSE_SEAWALL_STANDING := 12
## The tower named by a FORK or SELL does not exist (sold, or never built).
const REFUSE_NO_SUCH_TOWER := 13
## Arguments out of range: a slot past the kit, a branch the tower does not have.
const REFUSE_BAD_COMMAND := 14
## The seat is played by the caretaker until the next build window.
const REFUSE_CARETAKEN := 15

const REFUSAL_NAMES := [
	"",
	"CANNOT_BUILD_THERE",
	"NOT_ENOUGH_GOLD",
	"WRONG_PHASE",
	"NOT_YOURS",
	"ALREADY_FORKED",
	"RATE_LIMITED",
	"NO_CORKS_LEFT",
	"TOO_EARLY",
	"NOTHING_CORKED",
	"BAD_REVEAL",
	"NO_CHARGE",
	"SEAWALL_STANDING",
	"NO_SUCH_TOWER",
	"BAD_COMMAND",
	"CARETAKEN",
]

# ── Events (drain_events); each is a Dictionary with "type" and "tick" ──
const EV_SPAWN := 1  # id, hollow, kind
const EV_FIRE := 2  # tower, shot, target, kind, flight, land (road micrometres, -1 when homing)
const EV_HIT := 3  # creep, shot, tower, seat, kind, dmg, splash
const EV_EFFECT := 4  # what ("splash"), shot, hollow, x, z, r (millimetres)
const EV_DIE := 5  # id, kind, hollow, tower, seat, bounty
const EV_LEAK := 6  # id, kind, hollow, team, toll
const EV_BUILT := 7  # id, seat, seq, kind, hollow, x, z
const EV_FORKED := 8  # id, seat, seq, branch
const EV_SOLD := 9  # id, seat, seq, refund, hollow, x, z
const EV_GOLD := 10  # seat, gold, change, why
const EV_LIVES := 11  # team, lives, change
const EV_WAVE := 12  # hollow, wave, phase; start and early at the horn, cleared and bonus at a clear
const EV_READY := 13  # seat, on
const EV_SIGNAL := 14  # seat, x, z, target
const EV_SEAT := 15  # seat, state
const EV_REJECTED := 16  # seat, seq, cmd, reason

const EVENT_TYPES := {
	"SPAWN": EV_SPAWN,
	"FIRE": EV_FIRE,
	"HIT": EV_HIT,
	"EFFECT": EV_EFFECT,
	"DIE": EV_DIE,
	"LEAK": EV_LEAK,
	"BUILT": EV_BUILT,
	"FORKED": EV_FORKED,
	"SOLD": EV_SOLD,
	"GOLD": EV_GOLD,
	"LIVES": EV_LIVES,
	"WAVE": EV_WAVE,
	"READY": EV_READY,
	"SIGNAL": EV_SIGNAL,
	"SEAT": EV_SEAT,
	"REJECTED": EV_REJECTED,
}

# ── Hollow phases ──
const PHASE_PREP := 0
const PHASE_WAVE := 1
const PHASE_DONE := 2
const PHASE_FALLEN := 3

# ── Seat states: every state but PRESENT is played by the caretaker ──
const SEAT_PRESENT := 0
const SEAT_AWAY := 1
const SEAT_RETURNING := 2
const SEAT_CARETAKER := 3
const SEAT_LEFT := 4

# ── Debug writes: an offline match's scenario setters, logged with their tick ──
const DBG_GOLD := 1  # a seat, b gold
const DBG_LIVES := 2  # a team, b lives
const DBG_WAVE := 3  # a hollow, b wave
const DBG_COUNTDOWN := 4  # a hollow, b ticks
const DBG_CREEP_DIST := 5  # a creep id, b micrometres
const DBG_CREEP_SPEED := 6  # a creep id, b micrometres per tick
const DBG_SPAWN := 7  # a hollow, b creep kind index
const DBG_SLOW := 8  # a creep id, b per mille, c ticks
const DBG_TOWER_KILLS := 9  # a tower id, b kills
const DBG_KILLS := 10  # a team, b kills


static func command(seat: int, seq: int, type: int, a := 0, b := 0, c := 0) -> Dictionary:
	return {"seat": seat, "seq": seq, "type": type, "a": a, "b": b, "c": c}


## The command type for a name such as "BUILD", or 0.
static func command_type(name: String) -> int:
	return int(COMMAND_TYPES.get(name.to_upper(), 0))


## The event type for a name such as "DIE", or 0.
static func event_type(name: String) -> int:
	return int(EVENT_TYPES.get(name.to_upper(), 0))


static func refusal_name(reason: int) -> String:
	return REFUSAL_NAMES[reason] if reason >= 0 and reason < REFUSAL_NAMES.size() else str(reason)


## The order a sequencer lists a turn's commands in (design 6.3): system commands first,
## then the seats in rotation, starting with seat (turn mod seats) + 1 so nobody always
## wins a contested cell, then by sequence number. The server's sequencer and the
## LocalSequencer must both use exactly this order.
static func order_turn(turn: int, commands: Array, seat_count: int) -> Array:
	var sorted := commands.duplicate()
	sorted.sort_custom(  # sim-lint: allow sort_custom the key is unique (seat rotation, then seq)
		func(x: Dictionary, y: Dictionary) -> bool:
			return _order_key(turn, x, seat_count) < _order_key(turn, y, seat_count)
	)
	return sorted


## One integer per command: system first, then rotation position, then sequence number.
## Commands from one seat never share a sequence number, so the key is unique.
static func _order_key(turn: int, cmd: Dictionary, seat_count: int) -> int:
	var seat: int = cmd["seat"]
	var place := 0
	if seat != SYSTEM_SEAT:
		var n := maxi(1, seat_count)
		place = 1 + posmod(seat - 1 - posmod(turn, n), n)
	return place * 1000000 + int(cmd["seq"])
