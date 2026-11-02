## A scripted player for balance tests and the --bot flag. In the classic match it works
## down the Lamplighter's classic plan (data/plans/lamplighter.json, the same plan the
## caretaker follows) and sends each step through the game's own input route, the build
## controller, as soon as it can pay. In any other mode it plays whatever Builder its seat
## has, the way the caretaker would (Caretaker.decide on the match's own plan for that
## Builder: alternative cells, the patching forks the team lacks), still through the build
## controller, so a Lookout's seat or a Lamplighter's High Water seat plays from the hub
## (tools/net/smoke.py --flow --bot). Use from a scenario:
##   {"eval": "resource('res://tests/bot.gd').new()", "as": "bot"}
##   {"repeat": 400, "steps": [{"eval": "bot.step(scene)"}, {"wait": 15}],
##    "until": "Game.state >= 2"}
##
## In a duel (M7, Undertow) it also plays the duel as the caretaker does (Caretaker._duel,
## contract-m7 §2), by the caretaker's own functions, but through the game's own duel orders
## (Game.cork, Game.uncork, Game.seawall), so a CORK carries the client's commitment to a salt
## of its own and its UNCORK reveals that salt: in the window both hollows share, before the
## plan spends, it corks the pack SimUndertow.pick_pack picks while Caretaker.cork_tier
## allows a cork (the cheapest tier, its corks within CORK_SHARE_PM of everything it holds),
## one order at a time, and the plan waits while a cork it would make is refused or does not
## go out, and while my hollow stands in a window the rival's wave keeps shut
## (Caretaker.holds_plan), so the gold is still there when it opens; in the wave it uncorks each bottle from uncork_after_t after the horn (the
## caretaker's moment, long before the client's own uncorking at auto_uncork_t), and again
## after Game's retry wait when its UNCORK was refused or lost; and it raises the Seawall when
## Caretaker.wants_seawall would. `played_window` is the shared window it has played (corked,
## or found nothing it may cork, and built for), which tests/net/flow_bot.gd's --ready-calls
## waits for in a duel, as the caretaker's Ready waits for its window. It prints a line per
## duel order and per thing the simulation did with one, which tools/net/smoke.py --mode
## undertow reads:
##   BOT cork <check> window <w> seq <seq>          a CORK sent
##   BOT uncork bottle <id> window <w> seq <seq>    an UNCORK sent
##   BOT seawall wave <w> seq <seq>                 a SEAWALL sent
##   BOT bottle <id> window <w> tier <t> corked     the simulation stood my bottle
##   BOT bottle <id> window <w> uncorked <check> by bot|client
##                                                  it took the reveal: an UNCORK of the
##                                                  bot's (Game settled that seq as run), or
##                                                  the client's own at auto_uncork_t
##   BOT bottle <id> window <w> fizzled
##   BOT walking wave <w> hollow <h> creeps <n>    my uncorked creeps on the rival's road
##   BOT seawall rose wave <w> charges <n>          the simulation spent a charge of mine
## Outside a duel none of this runs.
##
## Stacked waves (M8, design 2.7): with `stacking` on (off unless asked: main.gd's
## --bot-stacks, a scenario's `bot.stacking = true`), in a mode that stacks it calls the
## waves its plan's `stack` list names during the wave before, as the caretaker would
## (Caretaker.wants_stack: its builds it can pay for done, its step not holding Ready, at
## Normal only), through the build controller's horn and its second press, so the call goes
## out as a player's does. It prints `BOT stack wave <k> seq <seq>` for each call sent.
extends RefCounted

const BUILDER := "lamplighter"
## A second seat's plan, on other cells (a party of bots holds one road together).
const SEAT_PLANS := "res://tests/plans/lamplighter_seat%d.json"

var plan: Array = SimContent.plan(BUILDER)
var done := 0
var log: Array[String] = []
var _seat := 1
## (M7) The duel's orders it sent: CORKs, UNCORKs and SEAWALLs, each a count.
var corks_sent := 0
var uncorks_sent := 0
var seawalls_sent := 0
## (M7) Its UNCORKs Game has not settled yet (seq -> bottle id), and the bottles whose
## uncorking was one of them (bottle id -> seq): Game.settled named that seq as run.
var _uncorking := {}
var uncorked_by_me := {}
## (M7) The last window both hollows share that it played (corked, or nothing it may cork,
## and built for), -1 before.
var played_window := -1
## (M7) What it said of the simulation: its bottles (id -> "corked", "uncorked" or
## "fizzled"), the waves whose sent creeps it saw walk the rival's road (wave -> how many),
## its Seawall charges at the last step.
var bottles_said := {}
var walked := {}
var _charges := -1
## (M8) Whether it stacks its plan's waves (off unless asked), and the waves it called.
var stacking := false
var stacks_sent: Array[int] = []


## Takes the next steps of the plan it can afford. Returns how many steps are done.
## A step waits while an earlier order of its own is still on its way.
func step(main: Node) -> int:
	var sim: SimMatch = main.get("sim")
	if sim != null and sim.mode != "classic":
		return _step_as_caretaker(main, sim)
	if Game.seat != _seat:
		_seat = Game.seat
		plan = plan_for(_seat)
	while done < plan.size():
		var entry: Dictionary = plan[done]
		var at: Array = entry["cell"]
		var cell := Vector2i(int(at[0]), int(at[1]))
		var what := "build %s" % entry["build"] if entry.has("build") else "upgrade"
		if entry.has("build"):
			var kind := str(entry["build"])
			if not Game.can_afford(Game.tower_cost(kind)):
				return done
			if main.tower_at(cell) != null or not main.build(kind, cell):
				log.append("could not build %s at %s" % [kind, cell])
		else:
			var tower: Tower = main.tower_at(cell)
			if tower == null and not main.settled():
				return done  # its build has not landed yet
			if tower == null or tower.upgrade_cost() < 0 or tower.owner_seat != Game.seat:
				log.append("nothing to upgrade at %s" % cell)
			elif not Game.can_afford(tower.upgrade_cost()):
				return done
			elif not main.fork(cell):
				log.append("could not upgrade at %s" % cell)
		log.append("wave %d: %s at %s" % [Game.wave, what, cell])
		done += 1
	return done


## Any Builder, any mode but classic: the seat's plan as the caretaker reads it, one step
## at a time; a step waits while an order of mine is still on its way, so a fork never
## races the build it forks and gold is never counted twice. In a duel the duel's orders
## come first (_duel), as the caretaker corks before its plan spends.
func _step_as_caretaker(main: Node, sim: SimMatch) -> int:
	var s := sim.seat(Game.seat)
	var steps: Array = sim.plans.get(s.builder, [])
	if sim.duel and not _duel(main, sim, s):
		return done
	if Caretaker.holds_plan(sim, s):
		return done  # (my window is not open for both yet: it corks first once it is)
	while done < steps.size():
		if not main.settled():
			return done
		var d := Caretaker.decide(sim, s, steps[done], s.gold)
		if d[0] == Caretaker.WAIT:
			break
		if d[0] == Caretaker.BUILD:
			var kind := SimContent.kit_tower(s.builder, d[1])
			var cell := Vector2i(d[2], d[3])
			if not main.build(kind, cell):
				log.append("could not build %s at %s" % [kind, cell])
			else:
				log.append("wave %d: build %s at %s" % [Game.wave, kind, cell])
		elif d[0] == Caretaker.FORK:
			var tower := sim.tower(d[1])
			var cell := Vector2i(tower.x, tower.z)
			if not main.fork(cell, d[2]):
				log.append("could not fork %s at %s" % [tower.kind, cell])
			else:
				log.append("wave %d: fork %s at %s to %s" % [Game.wave, tower.kind, cell, "AB"[d[2]]])
		done += 1
	if sim.duel and main.settled() and shared_window(sim, s) > 0:
		played_window = shared_window(sim, s)  # (corked or nothing to cork, and the plan waits or is done)
	if stacking and not sim.duel:
		_stack(main, sim, s, steps)
	return done


## (M8) Calls the next wave during this one where the plan's stack list names it and the
## caretaker's rule says it would now (Caretaker.wants_stack, `done` its plan cursor): two
## presses of the horn through the build controller, the second sending it.
func _stack(main: Node, sim: SimMatch, s: SimRecords.SimSeat, steps: Array) -> void:
	if not main.settled():
		return
	var controller: BuildController = main.get("controller")
	if controller == null or controller.wants_ready():
		return
	if not Caretaker.wants_stack(sim, s, steps, done):
		return
	var wave := sim.hollows[s.hollow].wave + 1
	if stacks_sent.has(wave):
		return  # (called once: taken back or refused, it is not pressed again)
	controller.toggle_ready()  # (the first press asks)
	if not controller.toggle_ready():  # (the second sends it)
		return
	stacks_sent.append(wave)
	var seq := -1
	for n: int in controller.pending:
		if controller.pending[n]["what"] == "ready":
			seq = n
	_say("stack wave %d seq %d" % [wave, seq])


# ── The duel (M7) ──


## The duel's orders for this step: the caretaker's policy, sent through Game's duel orders.
## Returns whether the plan may spend now: not while a CORK of mine is on its way, nor while
## a cork is still to make in this window.
func _duel(main: Node, sim: SimMatch, s: SimRecords.SimSeat) -> bool:
	_report(sim, s)
	if cork_waiting():
		return false
	var window := shared_window(sim, s)
	if window > 0:
		var check := cork_due(sim, s)
		if check == "":
			return true  # (no Drift in this window, its corks made, or nothing it may cork)
		if not main.settled():
			return false  # (a build of mine still on its way: its gold is not spent yet)
		# (a cork refused before it goes out or sent nowhere, catching up, short of gold, a
		# full command bucket's "Not so fast": the plan waits and the cork goes again at the
		# next step; the window is not played without it)
		if Game.cork_refusal(check) != "":
			return false
		var seq := Game.cork(check)
		if seq < 0:
			return false
		corks_sent += 1
		_say("cork %s window %d seq %d" % [check, window, seq])
		return false
	var from := sim.uncork_tick()
	if from >= 0 and sim.tick >= from:
		_uncork(sim, s)
	if Caretaker.wants_seawall(sim, s) and Game.seawall_refusal() == "":
		var seq := Game.seawall()
		if seq >= 0:
			seawalls_sent += 1
			_say("seawall wave %d seq %d" % [sim.hollows[s.hollow].wave, seq])
	return true


## Uncorks my bottles corked for the wave running whose UNCORK is not on its way (Game's
## my_bottles "uncork": mine, or the client's own at auto_uncork_t), once Game's retry wait
## after a refusal has passed: one refused or lost (Game.settled false) goes again.
func _uncork(sim: SimMatch, s: SimRecords.SimSeat) -> void:
	if not Game.settled.is_connected(_settled):
		Game.settled.connect(_settled)
	var wave := sim.hollows[s.hollow].wave
	for b: Dictionary in Game.my_bottles():
		var id := int(b["id"])
		if id < 0 or int(b["window"]) != wave or not bool(b["known"]) or int(b["uncork"]) >= 0:
			continue
		if sim.tick < int(b["retry"]):
			continue
		var seq := Game.uncork(id)
		if seq >= 0:
			uncorks_sent += 1
			_uncorking[seq] = id
			_say("uncork bottle %d window %d seq %d" % [id, int(b["window"]), seq])


## Game's word on an order of mine (EV_UNCORK's settling names the UNCORK on its way for the
## bottle; a refusal, a loss or a fizzle settles it false). Only one UNCORK of a bottle is on
## its way at a time; the one case this cannot tell apart is an older UNCORK forgotten with
## the link (Game.forget_duel_orders) whose turn still comes while a newer one is on its way.
func _settled(seq: int, accepted: bool) -> void:
	if not _uncorking.has(seq):
		return
	var id := int(_uncorking[seq])
	_uncorking.erase(seq)
	if accepted:
		uncorked_by_me[id] = seq


## The pack the caretaker's policy corks now, as its CHECK_IDS id: in the window both
## hollows share, once the Drift has drawn its packs and while a cork is left in it, the
## pack SimUndertow.pick_pack picks if Caretaker.cork_tier allows a cork; "" for none.
static func cork_due(sim: SimMatch, s: SimRecords.SimSeat) -> String:
	var window := shared_window(sim, s)
	if window <= 0 or sim.drift_window != window or Game.corks_left() <= 0:
		return ""
	if Caretaker.cork_tier(sim, s) < 0:
		return ""  # (the plan keeps the gold)
	var pack := SimUndertow.pick_pack(sim, s.seat)
	return str(SimContent.CHECK_IDS[pack]) if pack >= 0 else ""


## The window both hollows share while it is open (the wave it precedes; from drift_from
## the caretaker corks in it once the Drift has drawn its packs, Caretaker._duel), else 0.
static func shared_window(sim: SimMatch, s: SimRecords.SimSeat) -> int:
	return sim.hollows[s.hollow].wave + 1 if SimUndertow.window_open(sim) else 0


## Whether a CORK of mine still waits for its turn (Game.my_bottles' "waiting").
static func cork_waiting() -> bool:
	for b: Dictionary in Game.my_bottles():
		if bool(b.get("waiting", false)):
			return true
	return false


## Says what the simulation did with my duel orders since the last step (the BOT lines).
func _report(sim: SimMatch, s: SimRecords.SimSeat) -> void:
	for b: Dictionary in sim.bottles(s.seat):
		var id := int(b["id"])
		var now := "fizzled" if bool(b["fizzled"]) else ("uncorked" if bool(b["uncorked"]) else "corked")
		var said := str(bottles_said.get(id, ""))
		if said == now:
			continue
		if said == "":
			_say("bottle %d window %d tier %d corked" % [id, int(b["window"]), int(b["tier"])])
		if now == "uncorked":
			var by := "bot" if uncorked_by_me.has(id) else "client"
			_say("bottle %d window %d uncorked %s by %s" % [id, int(b["window"]), str(b["pack"]), by])
		elif now == "fizzled":
			_say("bottle %d window %d fizzled" % [id, int(b["window"])])
		bottles_said[id] = now
	var rival := SimUndertow.rival_hollow(sim, s)
	var wave := sim.hollows[s.hollow].wave
	if rival != null and not walked.has(wave):
		var walking := 0
		for c in sim.creeps:
			if c.sent_by == s.seat and c.hollow == rival.id and c.alive and c.dist_um > 0:
				walking += 1
		if walking > 0:
			walked[wave] = walking
			_say("walking wave %d hollow %d creeps %d" % [wave, rival.id, walking])
	if _charges >= 0 and s.seawall_charges < _charges:
		_say("seawall rose wave %d charges %d" % [wave, s.seawall_charges])
	_charges = s.seawall_charges


func _say(line: String) -> void:
	log.append(line)
	print("BOT " + line)


## Seat 1 plays the Builder's own plan; seat k > 1 its own plan from tests/plans/ if one
## is there.
static func plan_for(seat: int) -> Array:
	var path := SEAT_PLANS % seat
	if seat > 1 and FileAccess.file_exists(path):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if parsed is Dictionary:
			return (parsed as Dictionary).get("steps", [])
	return SimContent.plan(BUILDER)
