## The caretaker plays a seat nobody is at: an AWAY, RETURNING or LEFT player's, or a bot
## seat from tick 0 (the balance gates' bots are caretakers, design 4.4). It runs inside
## the simulation, so every client decides the same thing. It plays any seat and any
## Builder: it works down the Builder's plan (data/plans/<builder>.json,
## SimContent.plan_steps) with the seat's own gold, a step at a time as it can pay; it
## takes a step's alternative cells when another seat holds the first, skips steps nobody
## can do any more, takes a patching fork only while the team lacks the check it patches
## (else the deepening branch), and never sells. Its seat counts as Ready, so it never
## holds up a horn (SimMatch.ready_count, SimWaves).
##
## In a race (M6) it plays its seat on its own team's hollow, and it calls the waves: once
## a window's build steps are done (the next step waits for gold, or the plan is done) it
## says Ready, unless the step it waits on holds Ready (a plan step's "ready": false,
## SimContent.STEP_HOLDS_READY), so a hollow it plays alone races as a player would.
## (M8) It stacks there too: during wave k - 1 it says Ready for each wave k of its plan's
## `stack` list (SimContent.plan_stack), and in a crew of caretakers for each wave one of
## the crew's plans lists (stacks_wave), on the same terms, at Normal only (wants_stack),
## and the stacked horn sounds at the next tick's clock (stage 2; it thinks in stage 3), the
## called wave setting out at once among what the older still sends (SimWaves). Beside a
## present player in High Water it never calls a wave: it only counts as Ready.
##
## In a duel (M7, Undertow) it builds from its plan (a plan's "undertow" block where one is
## written) and says Ready in the window both hollows share once it has corked and built
## (it thinks on that window's first tick), so the shared horn waits for the player across
## the board, or the window's end, but never sounds before the caretaker had its window
## (SimUndertow._all_ready). It corks by a policy (contract-m7 §2): in the
## window both hollows share, while it has corks left, the cheapest tier it can pay for
## while its corks stay within CORK_SHARE_PM of everything it holds, so the plan keeps the
## rest (cork_tier), and before its plan spends: while its hollow stands in its window and
## the rival's still plays the wave, its plan waits (holds_plan), so on the shared window's
## first tick it corks first and builds after, the offered pack the rival's defence has
## shown it should (SimUndertow.pick_pack: the check that has leaked most, else fliers
## against a weak sky, else the pack its towers take longest to kill; never the rival's
## bottles), with salt 0, so its corks are not hidden; it uncorks them at
## uncork_after_t after the horn. In a wave it raises the
## Seawall once the creeps near its Holdfast would take CARETAKER_SEAWALL_TOLL lives or a
## boss stands there (wants_seawall). A bottle its player corked with a salt of their own
## it cannot reveal: it fizzles.
##
## Taking a seat mid-match (design 6.7, M4), it starts at the seat's plan cursor (0 for a
## player who never left) over towers the player built: a build step is done where the
## seat already has a tower on one of the step's cells, so it never builds a step twice
## or takes a cell meant for a teammate with the same Builder; a fork step forks only a
## tower of the kind the plan built there, so a player's cannon on an arrow's cell is not
## forked as if it were the arrow. Its towers keep firing throughout, as every tower does.
@warning_ignore_start("integer_division")
class_name Caretaker
extends RefCounted

## (M7) The most of what a duel seat holds (its gold, the gold in its towers and in its
## corks so far, worth()) the caretaker puts into corks. Tuned against the duel's gates
## (tests/balance/duel_*): the design's "while keeping its plan's next build", read as the
## gold above the next step, never corked (the plan always waits on a step it cannot pay
## yet: 0 corks in each of seeds 1 to 5 against a turtle and in the mirror, so
## duel_caretaker_plays_full_match fails), nor did corking only the gold the plan's builds
## leave (the plan first, then the cheapest tier from the rest: 0 again); corking whenever
## a cork was affordable starved the defence until it fell on wave 8 with five towers; a
## fifth of its worth corks about one window in two. This budget stands in for contract-m7
## §2's words, which no track changes alone: the tracks agree it at the merge.
const CORK_SHARE_PM := 200

## What decide() says about a step.
const SKIP := 0  # nothing to do here any more: move on
const WAIT := 1  # possible once the seat has the gold
const BUILD := 2  # [BUILD, slot, x, z]
const FORK := 3  # [FORK, tower id, branch]


## Called at the window's start and every 30 ticks for each caretaken seat (in a duel also
## on the first tick of the window both hollows share and on the first tick a bottle may
## be uncorked, SimMatch.uncork_tick).
static func think(m: SimMatch, s: SimRecords.SimSeat) -> void:
	var steps: Array = m.plans.get(s.builder, [])
	if m.duel:
		_duel(m, s)
		if holds_plan(m, s):
			return  # (its window is not open for both yet: it corks first once it is)
	while s.plan_cursor < steps.size():
		var d := decide(m, s, steps[s.plan_cursor], s.gold)
		if d[0] == WAIT:
			break
		if d[0] == BUILD:
			m.execute_as(s.seat, SimTypes.CMD_BUILD, d[1], d[2], d[3])
		elif d[0] == FORK:
			m.execute_as(s.seat, SimTypes.CMD_FORK, d[1], d[2])
		s.plan_cursor += 1
	if m.race and not s.ready and m.hollows[s.hollow].phase == SimTypes.PHASE_PREP:
		if not holds_ready(steps, s.plan_cursor):
			m.execute_as(s.seat, SimTypes.CMD_READY, 1)
	# (M8) in a race's wave, the next wave where its plan stacks it
	if m.race and not s.ready and wants_stack(m, s, steps, s.plan_cursor):
		m.execute_as(s.seat, SimTypes.CMD_READY, 1)
	# (M7) in the window both hollows share, once it has corked and built: the horn waits
	# for this, and still for the player (SimUndertow._all_ready)
	if m.duel and not s.ready and SimUndertow.window_open(m):
		m.execute_as(s.seat, SimTypes.CMD_READY, 1)


## The duel's part of a think (M7): corks before the plan spends the window's gold, then
## its uncorkings and the Seawall in a wave.
static func _duel(m: SimMatch, s: SimRecords.SimSeat) -> void:
	var window := m.hollows[s.hollow].wave + 1
	if SimUndertow.window_open(m) and m.drift_window == window:
		while SimUndertow.corks_of(m, s.seat, window) < SimUndertow.corks_allowed(m, window):
			var tier := cork_tier(m, s)
			var pack := SimUndertow.pick_pack(m, s.seat)
			if tier < 0 or pack < 0:
				break
			var made := SimUndertow.corks_of(m, s.seat, window)
			var c := SimUndertow.commit(m.match_seed, s.seat, window, pack, 0, 0)
			m.execute_as(s.seat, SimTypes.CMD_CORK, tier, int(c[0]), int(c[1]))
			if SimUndertow.corks_of(m, s.seat, window) == made:
				break  # (refused: it never asks twice)
		return
	var from := m.uncork_tick()
	if from >= 0 and m.tick >= from:
		for b in SimUndertow.pending(m, s.seat):
			var pack := SimUndertow.salt_zero_pack(m, b)
			if pack >= 0:
				m.execute_as(s.seat, SimTypes.CMD_UNCORK, pack, 0, 0)
	if wants_seawall(m, s):
		m.execute_as(s.seat, SimTypes.CMD_SEAWALL)


## (M7) Whether seat `s`'s plan waits in a duel: its hollow has cleared and stands in its
## window while the rival's still plays the wave (its bottles may hold it), so the window is
## not open for both yet. Nothing is built meanwhile: on the shared window's first tick the
## caretaker corks before its plan spends (contract-m7 §2), and a tower built while its road
## stands empty would defend nothing sooner.
static func holds_plan(m: SimMatch, s: SimRecords.SimSeat) -> bool:
	return (
		m.duel and m.hollows[s.hollow].phase == SimTypes.PHASE_PREP and not SimUndertow.window_open(m)
	)


## The cheapest tier the open window offers that seat `s` can pay for, with `reserved` gold
## already promised, while all its corks stay within `share_pm` of its worth(); -1 if none.
static func cork_tier(
	m: SimMatch, s: SimRecords.SimSeat, reserved := 0, share_pm := CORK_SHARE_PM
) -> int:
	var window := m.hollows[s.hollow].wave + 1
	var tier := SimUndertow.cheapest_tier(m, window, s.gold - reserved)
	if tier < 0:
		return -1
	var corked := corked_gold(m, s.seat) + reserved
	var price := SimUndertow.cork_price(m, tier, window)
	if (corked + price) * 1000 > worth(m, s) * share_pm:
		return -1
	return tier


## What seat `s` holds: its gold, the gold in its standing towers and in its corks so far.
static func worth(m: SimMatch, s: SimRecords.SimSeat) -> int:
	var total := s.gold + corked_gold(m, s.seat)
	for t in m.towers:
		if t.owner == s.seat:
			total += t.invested
	return total


## The gold seat `seat` has put into corks.
static func corked_gold(m: SimMatch, seat: int) -> int:
	var total := 0
	for b in m.bottle_list:
		if b.seat == seat:
			total += b.price
	return total


## Whether seat `s` would raise its Seawall now: in its wave, with a charge and the wall
## down, once the creeps inside the ring carry CARETAKER_SEAWALL_TOLL lives or a boss.
static func wants_seawall(m: SimMatch, s: SimRecords.SimSeat) -> bool:
	var h := m.hollows[s.hollow]
	if not m.duel or h.phase != SimTypes.PHASE_WAVE:
		return false
	if s.seawall_charges <= 0 or m.tick < s.seawall_ready:
		return false
	var toll := 0
	for c in SimUndertow.in_ring(m, h):
		if c.boss:
			return true
		toll += c.toll
	return toll >= SimUndertow.CARETAKER_SEAWALL_TOLL


## (M8, contract-m8 §2) Whether seat `s` stacks now, its plan's builds it can pay for done
## and `cursor` the step it waits on: during wave k - 1 of a wave k it stacks
## (stacks_wave), at Normal only, while the hollow can take another wave
## (SimMatch.can_stack) and that step does not hold Ready ("ready": false). The caretaker
## asks it where it calls waves itself (a race); the sim harness's seats played by command
## that stack their plan's list ask it too.
static func wants_stack(m: SimMatch, s: SimRecords.SimSeat, steps: Array, cursor: int) -> bool:
	if m.level != 0:
		return false  # (it never stacks at Hard or Very Hard)
	var h := m.hollows[s.hollow]
	if h.phase != SimTypes.PHASE_WAVE or not m.can_stack(h.id):
		return false
	if not stacks_wave(m, s, h.wave + 1):
		return false
	return not holds_ready(steps, cursor)


## (M8, contract-m8 §2) Whether seat `s` stacks wave `wave`: its own plan's stack list has
## it, or, on a hollow nobody is present at (its caretakers call the waves, a race's crew of
## two), one of the hollow's seats' plans lists it. The stacked horn waits for every
## caretaker's Ready, each said once its own builds are paid as for a window's horn, so a
## crew of caretakers stacks every wave one of its plans lists, as each of them alone would,
## and not only the waves both list (Lamplighter and Lookout list none alike). Beside a
## present seat only its own list counts: there the players call.
static func stacks_wave(m: SimMatch, s: SimRecords.SimSeat, wave: int) -> bool:
	var own: PackedInt32Array = m.stacks.get(s.builder, PackedInt32Array())
	if own.has(wave):
		return true
	var h := m.hollows[s.hollow]
	for n in h.seats:
		if m.seat(n).state == SimTypes.SEAT_PRESENT:
			return false
	for n in h.seats:
		var list: PackedInt32Array = m.stacks.get(m.seat(n).builder, PackedInt32Array())
		if list.has(wave):
			return true
	return false


## Whether the step at `cursor` (the one the caretaker waits on) holds its Ready in a race.
static func holds_ready(steps: Array, cursor: int) -> bool:
	if cursor < 0 or cursor >= steps.size():
		return false
	var step: PackedInt32Array = steps[cursor]
	return step.size() > 5 and (step[5] & SimContent.STEP_HOLDS_READY) != 0


## What plan step `step` (a SimContent.plan_steps entry) asks of seat `s` now, given
## `gold` to spend and `claimed` cells (z * width + x) that orders still on their way
## will build on. Returns [SKIP], [WAIT], [BUILD, slot, x, z] or [FORK, tower, branch].
static func decide(
	m: SimMatch, s: SimRecords.SimSeat, step: PackedInt32Array, gold: int,
	claimed := PackedInt32Array()
) -> PackedInt32Array:
	var h := m.hollows[s.hollow]
	if step[0] == 0:
		var kind := SimContent.kit_tower(s.builder, step[1])
		if kind == "" or own_on(m, h, s, step):
			return PackedInt32Array([SKIP])
		var cell := free_cell(m, h, step, claimed)
		if cell < 0:
			return PackedInt32Array([SKIP])
		if gold < int(SimContent.TOWERS[kind]["cost"]):
			return PackedInt32Array([WAIT])
		return PackedInt32Array([BUILD, step[1], cell % h.road.width, cell / h.road.width])
	var t := own_unforked(m, h, s, step)
	if t == null:
		return PackedInt32Array([SKIP])
	var branch := fork_branch(m, s, step)
	if not SimContent.has_branch(t.kind, branch):
		return PackedInt32Array([SKIP])
	if gold < int(SimContent.TOWERS[t.kind]["fork_cost"]):
		return PackedInt32Array([WAIT])
	return PackedInt32Array([FORK, t.id, branch])


## The step's cells in order of preference, as z * width + x: its cell, then its "alt"s
## (from index 6 of a SimContent.plan_steps entry).
static func cells(h: SimRecords.SimHollow, step: PackedInt32Array) -> PackedInt32Array:
	var out := PackedInt32Array()
	out.append(step[3] * h.road.width + step[2])
	var i := 6
	while i + 1 < step.size():
		out.append(step[i + 1] * h.road.width + step[i])
		i += 2
	return out


## The first of the step's cells a tower can go on now, or -1.
static func free_cell(
	m: SimMatch, h: SimRecords.SimHollow, step: PackedInt32Array, claimed: PackedInt32Array
) -> int:
	for cell in cells(h, step):
		var x := cell % h.road.width
		var z := cell / h.road.width
		if h.road.buildable(x, z) and h.occupied[cell] == 0 and not claimed.has(cell):
			return cell
	return -1


## Whether the seat has a tower on one of the step's cells: a build step it (or its
## player) has done already.
static func own_on(
	m: SimMatch, h: SimRecords.SimHollow, s: SimRecords.SimSeat, step: PackedInt32Array
) -> bool:
	for cell in cells(h, step):
		var t := m.tower(h.occupied[cell])
		if t != null and t.owner == s.seat:
			return true
	return false


## The seat's unforked tower on the first of the step's cells that holds one of the kind
## the plan builds there (planned_kind), or null.
static func own_unforked(
	m: SimMatch, h: SimRecords.SimHollow, s: SimRecords.SimSeat, step: PackedInt32Array
) -> SimRecords.SimTower:
	var kind := planned_kind(m, s.builder, step)
	for cell in cells(h, step):
		var t := m.tower(h.occupied[cell])
		if t != null and t.owner == s.seat and t.branch == -1 and (kind == "" or t.kind == kind):
			return t
	return null


## The tower kind the Builder's plan builds on a fork step's cell: the kit tower of the
## first build step on the same cell, or "" when the plan builds nothing there (a plan a
## test writes may fork any tower).
static func planned_kind(m: SimMatch, builder: String, step: PackedInt32Array) -> String:
	for other: PackedInt32Array in m.plans.get(builder, []):
		if other[0] == 0 and other[2] == step[2] and other[3] == step[3]:
			return SimContent.kit_tower(builder, other[1])
	return ""


## The branch a fork step takes for seat `s`: the step's own, unless it patches a check
## (step[4]) a Builder of the seat's team already covers; then the other one.
static func fork_branch(m: SimMatch, s: SimRecords.SimSeat, step: PackedInt32Array) -> int:
	var branch := step[1]
	if step.size() > 4 and step[4] >= 0 and team_covers(m, s.team, step[4]):
		return 1 - branch
	return branch


## Whether a Builder on team `team` is strong against check CHECK_IDS[check].
static func team_covers(m: SimMatch, team: int, check: int) -> bool:
	var builders := []
	for other in m.seats:
		if other.team == team:
			builders.append(other.builder)
	return SimContent.team_covers(builders).has(SimContent.CHECK_IDS[check])
