## Team effects and Help (design 3.2). A creep holds one of each effect, as a strength,
## the tick it ends and the seat whose tower gave it; effects never stack, the strongest
## applies:
##   slow  each slowing hit: the strongest active slow applies, shrunk by a boss's
##         control resistance where the rules turn it on (a 45% slow on the Hollowtide
##         Crest is 22.5%), for the hit's own time: a stronger hit ends when its own
##         ticks run out, a hit as strong moves the end to the latest. A weaker hit that
##         outlasts the applying slow waits underneath it (SimCreep.slow_next) and takes
##         hold the tick the stronger one lapses (lapse_slow, stage 4), so pairing two
##         slows never leaves a creep less slowed than either would alone (M1 let a weaker
##         hit stretch the stronger slow without end)
##   mark  a marking tower (the Owl's Eye) re-picks the creeps with the most health in its
##         reach every cd_t ticks and keeps their marks fresh each tick while they stay in
##         reach; a mark lasts mark_t ticks past that. A weaker mark never stretches a
##         stronger one: it waits until the stronger lapses, then takes hold. Of two
##         marks as strong, the one that ends later holds the creep and its seat earns
##         the Help, so a sold or re-picked eye stops earning the tick its mark would
##         lapse first (a mark it leaves still lasts mark_t, so one eye can briefly hold
##         more creeps than it marks: a lingering mark, not a stacked one)
##   stun  (M6) a pulse (the Toll Tower) stands a ground creep still for stun_t ticks,
##         then leaves it immune for stun_immune_t, so stuns never chain: a pulse that
##         finds the creep stunned or immune stuns nothing. On a boss, where the rules
##         turn control resistance on, the stun is a 50% slow of the same length, not
##         shrunk again by the boss's resistance, and the immunity follows it as well
##   crack (M6) an aura: a creep inside a Chime Post's reach has crack_c less armour for
##         every hit, the strongest post's (of two as strong, the lower id's), refreshed
##         each tick before the towers act (refresh_cracks); fliers carry no armour and
##         are never cracked
##   haste (M6) an aura on towers: every tower whose cell centre lies within a Hive Hum's
##         reach, whoever built it, fires haste_pm faster (cooldown / (1 + haste)); the
##         strongest hum applies (of two as strong, the lower id), a hum hastens no hum,
##         and it is worked out again whenever a tower is built, forked or sold
##         (recompute_haste)
## A marked creep takes mark_pm per mille more from every hit (SimMatch._hurt).
##
## Help: a hit on a creep another seat's tower has slowed, stunned, marked or cracked, or
## from a tower another seat's hum hastens, adds the damage dealt to that seat's help_c,
## in full, once per distinct helper (EV_HELP), where the rules' "help" key is on.
## EV_STATUS tells views when an effect takes hold, is replaced by a stronger one or (a
## slow) is refreshed; a mark's per-tick refresh only moves its end, a stun is never
## refreshed (stuns never chain), and an aura that lapses (a crack, a haste) leaves the
## record at 0 without an event.
@warning_ignore_start("integer_division")
class_name SimEffects
extends RefCounted

## When one seat helped through several effects, EV_HELP names the one that helped the
## hit most directly, first in this list.
## Haste, the firing tower's own, comes after them: a seat that helped through an effect
## on the creep is named for that.
const HELP_ORDER := [SimTypes.EFFECT_MARK, SimTypes.EFFECT_CRACK, SimTypes.EFFECT_STUN, SimTypes.EFFECT_SLOW]
## A stun on a boss that resists control is this slow instead, for the stun's length.
const BOSS_STUN_SLOW_PM := 500


## A slow of `pm` per mille for `ticks` from `seat`'s tower `tower` (0: a debug write),
## shrunk by a boss's control resistance unless `resist` is false (a stun turned slow).
static func apply_slow(
	m: SimMatch, c: SimRecords.SimCreep, pm: int, ticks: int, seat: int, tower := 0,
	resist := true
) -> void:
	var strength := resisted(m, c, pm) if resist else pm
	var until := m.tick + ticks
	lapse_slow(m, c)
	var current := c.slow_pm if c.slow_until > m.tick else 0
	if strength < current:
		_wait_under(c, strength, until, seat)  # takes hold once the stronger one lapses
		return
	if strength > current and current > 0:
		var under := PackedInt32Array([c.slow_pm, c.slow_until, c.slow_seat])
		c.slow_until = until
		_wait_under(c, under[0], under[1], under[2])
	else:
		c.slow_until = maxi(c.slow_until, until) if strength == current else until
		_wait_under(c, 0, 0, 0)
	c.slow_pm = strength
	c.slow_seat = seat
	_status(m, SimTypes.EFFECT_SLOW, c.id, tower, c.slow_seat, c.slow_pm, c.slow_until)


## Stage 4: once the applying slow's time is up, the strongest slow still waiting under
## it takes hold (EV_STATUS with tower 0), or none does.
static func lapse_slow(m: SimMatch, c: SimRecords.SimCreep) -> void:
	if c.slow_until > m.tick:
		return
	c.slow_pm = 0
	while not c.slow_next.is_empty():
		var next := c.slow_next.slice(0, 3)
		c.slow_next = c.slow_next.slice(3)
		if next[1] > m.tick:
			c.slow_pm = next[0]
			c.slow_until = next[1]
			c.slow_seat = next[2]
			_status(m, SimTypes.EFFECT_SLOW, c.id, 0, next[2], next[0], next[1])
			return


## Puts a slow of `pm` until `until` from `seat` under the applying one (pm 0: none, it
## only tidies), keeping what can still matter: the slows waiting under it, strongest
## first, each ending later than every slow above it. A slow that ends no later than a
## stronger or as strong one would never apply, and is dropped.
static func _wait_under(c: SimRecords.SimCreep, pm: int, until: int, seat: int) -> void:
	var out := PackedInt32Array()
	var reach := c.slow_until
	var placed := pm <= 0
	var i := 0
	while i < c.slow_next.size() or not placed:
		var entry: PackedInt32Array
		var mine := not placed and (
			i >= c.slow_next.size() or pm > c.slow_next[i]
			or (pm == c.slow_next[i] and until >= c.slow_next[i + 1])
		)
		if mine:
			entry = PackedInt32Array([pm, until, seat])
			placed = true
		else:
			entry = c.slow_next.slice(i, i + 3)
			i += 3
		if entry[1] > reach:
			out.append_array(entry)
			reach = entry[1]
	c.slow_next = out


## A control effect's strength on `c`: a boss's control resistance shrinks it when the
## rules turn resistance on.
static func resisted(m: SimMatch, c: SimRecords.SimCreep, pm: int) -> int:
	if resists(m, c):
		return pm * (1000 - c.control_resist_pm) / 1000
	return pm


## Whether the rules let `c` resist control: a boss, where control_resist is on.
static func resists(m: SimMatch, c: SimRecords.SimCreep) -> bool:
	return c.boss and bool(m.rules.get("control_resist", true))


## (M6) A stun of `ticks` from `seat`'s tower `tower`, followed by `immune_t` ticks in which
## no stun takes. A creep stunned or immune now is left as it is; a boss that resists
## control is slowed 50% for the stun's length instead (not shrunk again).
static func apply_stun(
	m: SimMatch, c: SimRecords.SimCreep, ticks: int, immune_t: int, seat: int, tower: int
) -> void:
	if ticks <= 0 or m.tick < c.stun_immune_until:
		return
	var until := m.tick + ticks
	c.stun_immune_until = until + maxi(0, immune_t)
	if resists(m, c):
		apply_slow(m, c, BOSS_STUN_SLOW_PM, ticks, seat, tower, false)
		return
	c.stun_until = until
	c.stun_seat = seat
	_status(m, SimTypes.EFFECT_STUN, c.id, tower, seat, 1000, until)


## (M6) Stage 5, before the towers act: every creep's crack, the strongest Chime Post's
## that reaches it (of two as strong, the lower id's; fliers never), from the posts the
## match lists (SimMatch.crack_posts). EV_STATUS when a crack takes hold or changes hands.
static func refresh_cracks(m: SimMatch, posts: Array[SimRecords.SimTower]) -> void:
	for c in m.creeps:
		var best := 0
		var seat := 0
		var from := 0
		if not c.winged:
			for t in posts:
				if t.hollow == c.hollow and t.crack_c > best and SimRoad.covers(t.intervals, c.dist_um):
					best = t.crack_c
					seat = t.owner
					from = t.id
		if best == c.crack_c and seat == c.crack_seat:
			continue
		c.crack_c = best
		c.crack_seat = seat
		if best > 0:
			_status(m, SimTypes.EFFECT_CRACK, c.id, from, seat, best, 0)


## (M6) Every tower's haste on hollow `hollow`: the strongest Hive Hum whose reach holds the
## tower's cell centre (of two as strong, the lower id), whoever built either; a hum
## hastens no hum. EV_STATUS (creep 0, tower: the hastened one) when a haste takes hold or
## changes; a tower out of every hum's reach goes back to 0.
static func recompute_haste(m: SimMatch, hollow: int) -> void:
	for t in m.towers:
		if t.hollow != hollow:
			continue
		var best := 0
		var seat := 0
		if t.hum_pm == 0:
			for hum in m.towers:
				if hum.hollow != hollow or hum.hum_pm <= best:
					continue
				var dx := SimRoad.centre_mm(hum.x) - SimRoad.centre_mm(t.x)
				var dz := SimRoad.centre_mm(hum.z) - SimRoad.centre_mm(t.z)
				if dx * dx + dz * dz <= hum.range_mm * hum.range_mm:
					best = hum.hum_pm
					seat = hum.owner
		if best == t.haste_pm and seat == t.haste_seat:
			continue
		t.haste_pm = best
		t.haste_seat = seat
		if best > 0:
			_status(m, SimTypes.EFFECT_HASTE, 0, t.id, seat, best, 0)


## A mark of `pm` per mille on `c` from `seat`'s tower, lasting `ticks` from now.
static func apply_mark(
	m: SimMatch, c: SimRecords.SimCreep, pm: int, ticks: int, seat: int, tower: int
) -> void:
	var active := c.mark_until > m.tick
	var current := c.mark_pm if active else 0
	if pm < current:
		return  # a stronger mark holds; this one takes over once that one lapses
	var until := m.tick + ticks
	if pm > current or not active:
		c.mark_pm = pm
		c.mark_seat = seat
		c.mark_until = until
		_status(m, SimTypes.EFFECT_MARK, c.id, tower, seat, pm, until)
	elif until > c.mark_until:
		# A mark as strong that ends later is the one holding the creep now: it takes the
		# credit. While two eyes refresh it every tick, the first to refresh (the lower id)
		# keeps it; once that one stops, the other takes over on its next refresh.
		c.mark_until = until
		if c.mark_seat != seat:
			c.mark_seat = seat
			_status(m, SimTypes.EFFECT_MARK, c.id, tower, seat, pm, until)


## Stage 5 for a tower that fires no shot: the Owl's Eye re-picks its creeps every cd_t
## ticks (sooner where a hum hastens it) and marks the ones it holds that are still in
## reach.
static func team_tower(m: SimMatch, t: SimRecords.SimTower) -> void:
	if t.team != SimTypes.EFFECT_MARK or t.marks <= 0:
		return
	if m.tick >= t.cooldown_until:
		t.marked = SimTargeting.strongest(m, t, t.marks, PackedInt32Array())
		t.cooldown_until = m.tick + m.cooldown_of(t)
	var i := 0
	while i < t.marked.size():
		var c := m.creep(t.marked[i])
		if c == null or not m.in_range(t, c):
			t.marked.remove_at(i)
			continue
		apply_mark(m, c, t.mark_pm, t.mark_t, t.owner, t.id)
		i += 1


## A lapsed mark leaves no trace on the record (stage 4, with the slow's).
static func expire(m: SimMatch, c: SimRecords.SimCreep) -> void:
	if c.mark_pm != 0 and c.mark_until <= m.tick:
		c.mark_pm = 0
		c.mark_seat = 0


## The seats whose effects on `c` helped a hit by `by` (in seat order, each once) and,
## for each, the effect named in its EV_HELP, as pairs [seat, effect, ...]: the effects on
## the creep in HELP_ORDER, then the haste on `from`, the tower that dealt the hit (null
## when it is gone). Read before the hit's own effects land.
static func helpers(
	m: SimMatch, c: SimRecords.SimCreep, by: int, from: SimRecords.SimTower = null
) -> PackedInt32Array:
	var out := PackedInt32Array()
	if not bool(m.rules.get("help", true)):
		return out
	# The seat behind each effect active on the creep now, in HELP_ORDER (0: none).
	var given := PackedInt32Array()
	given.append(c.mark_seat if c.mark_until > m.tick and c.mark_pm > 0 else 0)
	given.append(c.crack_seat if c.crack_c > 0 else 0)
	given.append(c.stun_seat if c.stun_until > m.tick else 0)
	given.append(c.slow_seat if c.slow_until > m.tick and c.slow_pm > 0 else 0)
	var hasted := from.haste_seat if from != null and from.haste_pm > 0 else 0
	for s in m.seats:
		if s.seat == by:
			continue
		var named := 0
		for k in HELP_ORDER.size():
			if given[k] == s.seat:
				named = HELP_ORDER[k]
				break
		if named == 0 and hasted == s.seat:
			named = SimTypes.EFFECT_HASTE
		if named != 0:
			out.append(s.seat)
			out.append(named)
	return out


## Credits `dealt` to each helper of a hit by `by` on `c` (pairs from helpers()).
static func credit(
	m: SimMatch, c: SimRecords.SimCreep, by: int, helped: PackedInt32Array, dealt: int
) -> void:
	if dealt <= 0:
		return
	var k := 0
	while k < helped.size():
		var s := m.seat(helped[k])
		if s:
			s.help_c += dealt
			m.push_event(
				{
					"type": SimTypes.EV_HELP,
					"seat": s.seat,
					"by": by,
					"creep": c.id,
					"effect": helped[k + 1],
					"dmg": dealt,
				}
			)
		k += 2


static func _status(
	m: SimMatch, effect: int, creep: int, tower: int, seat: int, amount: int, until: int
) -> void:
	m.push_event(
		{
			"type": SimTypes.EV_STATUS,
			"effect": effect,
			"creep": creep,
			"tower": tower,
			"seat": seat,
			"amount": amount,
			"until": until,
		}
	)
