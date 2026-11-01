## Reads and stagings for the duel's flow_* and bot scenarios (M7, track D): seats_seen()
## answers "" before the simulation stands, and press() presses a button only where it
## stands and is enabled.
##   {"eval": "resource('res://tests/net/duel_checks.gd').seats_seen()", "as": "seats"}
## start_duel(scene) stages a duel on the match scene (my seat against a caretaker, through a
## LocalSequencer) for the plan bot's duel scenarios (bot_duels_through_its_orders,
## bot_duel_refused_orders), with salts that come out alike on every run; sent(seat, type)
## reads the orders its turns carried, step_until_cork(bot, scene) steps the plan bot up to
## the moment it would cork, spoil_next(type) makes the next turn's order of that type one
## the simulation refuses, and refuse_orders(on) has the sequencer take no order.
extends RefCounted


## The simulation's seats as the match plays them, "team:builder:state" each in seat order
## ("0:lamplighter:present 1:lamplighter:caretaker"); "" without a simulation.
static func seats_seen() -> String:
	if Game.sim == null:
		return ""
	var out := []
	for seat: SimRecords.SimSeat in Game.sim.seats:
		out.append("%d:%s:%s" % [seat.team, seat.builder, SimTypes.SEAT_NAMES[seat.state]])
	return " ".join(out)


## Presses the button named `button_name` where it stands and is enabled; false otherwise.
static func press(button_name: String) -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	var found := tree.root.find_child(button_name, true, false) as BaseButton
	if found == null or found.disabled or not found.is_visible_in_tree():
		return false
	found.pressed.emit()
	return true


# ── A duel on the match scene, offline ──


## Begins Undertow on the match scene `scene`: my seat 1 (a Lamplighter, on team 0) against
## a caretaker Lamplighter on team 1, through a LocalSequencer, as Duel the caretaker plays
## it. Each of my corks takes its salt from fixed_salt(seed, n) for the n-th, not from
## Crypto, so two runs of a scenario commit alike (--determinism compares state hashes, and
## the bottles' commits are the match's). Returns whether the match is a duel.
static func start_duel(scene: Node, seed_value := 1) -> bool:
	var seats := [{"team": 0, "builder": "lamplighter"}, {"team": 1, "builder": "lamplighter", "caretaker": true}]
	scene.call("begin", "undertow", seats, seed_value, LocalSequencer.new(2, 1), 1)
	var drawn := [0]
	Game.salt_source = func() -> PackedByteArray:
		drawn[0] += 1
		return fixed_salt(seed_value, int(drawn[0]))
	return Game.is_duel()


## The n-th fixed salt for `seed_value`: the first 8 bytes of SHA-256 over the seed and n,
## each as 8 bytes little-endian.
static func fixed_salt(seed_value: int, n: int) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(16)
	bytes.encode_s64(0, seed_value)
	bytes.encode_s64(8, n)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	return ctx.finish().slice(0, 8)


## The commands of type `type` seat `n` sent, as the offline match's turns carried them:
## [turn, a, b, c] each, oldest first.
static func sent(n: int, type: int) -> Array:
	var out := []
	var local := Game.source as LocalSequencer
	if local == null:
		return out
	for t in local.turns.size():
		for cmd: Dictionary in local.turns[t]:
			if int(cmd["seat"]) == n and int(cmd["type"]) == type:
				out.append([t, int(cmd["a"]), int(cmd["b"]), int(cmd["c"])])
	return out


## Spoils my order of type `type` waiting for the next turn of the offline match (its `b`
## flipped in its lowest bit, so an UNCORK reveals a salt its bottle was never committed to
## and the simulation refuses it: BAD_REVEAL). The turn log keeps the spoiled order, so a
## replay refuses it too. Returns its seq, or -1 when none waits.
static func spoil_next(type: int) -> int:
	var local := Game.source as LocalSequencer
	if local == null:
		return -1
	for cmd: Dictionary in local.pending():
		if int(cmd["seat"]) == local.seat and int(cmd["type"]) == type:
			cmd["b"] = int(cmd["b"]) ^ 1
			return int(cmd["seq"])
	return -1


## While `on`, the offline match's sequencer takes no order: its submit gives -1, as a full
## command bucket's "Not so fast" does online. It does so by standing as a replaying one,
## which also seals no turn and replays its debug log, so a scenario turns it off again in
## the same frame (no step between, nothing stepped meanwhile).
static func refuse_orders(on: bool) -> void:
	var local := Game.source as LocalSequencer
	if local != null:
		local.set("_replaying", on)


## Steps the plan bot `bot` (tests/bot.gd) on `scene` unless it would cork now (a cork due by
## its policy, bot.cork_due, and nothing of mine on its way), so a scenario can stage what
## meets that cork. Returns whether the cork is due (the bot not stepped).
static func step_until_cork(bot: RefCounted, scene: Node) -> bool:
	var sim: SimMatch = Game.sim
	if sim != null and str(bot.call("cork_due", sim, sim.seat(Game.seat))) != "" and bool(scene.call("settled")):
		return true
	bot.call("step", scene)
	return false
