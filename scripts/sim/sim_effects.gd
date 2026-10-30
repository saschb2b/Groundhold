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
## A marked creep takes mark_pm per mille more from every hit (SimMatch._hurt).
##
## Help: a hit on a creep another seat's tower has slowed or marked adds the damage dealt
## to that seat's help_c, in full, once per distinct helper (EV_HELP), where the rules'
## "help" key is on. EV_STATUS tells views when an effect takes hold, is replaced by a
## stronger one or (a slow) is refreshed; a mark's per-tick refresh only moves its end.
@warning_ignore_start("integer_division")
class_name SimEffects
extends RefCounted

## When one seat helped through several effects, EV_HELP names the one that helped the
## hit most directly, first in this list.
const HELP_ORDER := [SimTypes.EFFECT_MARK, SimTypes.EFFECT_CRACK, SimTypes.EFFECT_STUN, SimTypes.EFFECT_SLOW]


## A slow of `pm` per mille for `ticks` from `seat`'s tower `tower` (0: a debug write).
static func apply_slow(
	m: SimMatch, c: SimRecords.SimCreep, pm: int, ticks: int, seat: int, tower := 0
) -> void:
	var strength := resisted(m, c, pm)
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
	if c.boss and bool(m.rules.get("control_resist", true)):
		return pm * (1000 - c.control_resist_pm) / 1000
	return pm


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
## ticks and marks the ones it holds that are still in reach.
static func team_tower(m: SimMatch, t: SimRecords.SimTower) -> void:
	if t.team != SimTypes.EFFECT_MARK or t.marks <= 0:
		return
	if m.tick >= t.cooldown_until:
		t.marked = SimTargeting.strongest(m, t, t.marks, PackedInt32Array())
		t.cooldown_until = m.tick + t.cd_t
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
## for each, the effect named in its EV_HELP, as pairs [seat, effect, ...]. Read before
## the hit's own effects land.
static func helpers(m: SimMatch, c: SimRecords.SimCreep, by: int) -> PackedInt32Array:
	var out := PackedInt32Array()
	if not bool(m.rules.get("help", true)):
		return out
	# The seat behind each effect active on the creep now, in HELP_ORDER (0: none).
	var given := PackedInt32Array()
	given.append(c.mark_seat if c.mark_until > m.tick and c.mark_pm > 0 else 0)
	given.append(c.crack_seat if c.crack_c > 0 else 0)
	given.append(c.stun_seat if c.stun_until > m.tick else 0)
	given.append(c.slow_seat if c.slow_until > m.tick and c.slow_pm > 0 else 0)
	for s in m.seats:
		if s.seat == by:
			continue
		for k in HELP_ORDER.size():
			if given[k] == s.seat:
				out.append(s.seat)
				out.append(HELP_ORDER[k])
				break
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
