## Undertow, the duel (design 1.4; docs/design/contract-m7.md §2): one seat on each of two
## hollows, the race's layout, under one clock, with the rules of the preset's `duel` block.
##
##   The shared clock: a hollow that clears its wave opens its window, but the window counts
##     down only once every standing hollow has cleared (run_clock); then the horn sounds
##     for both together, when every seat is Ready (a caretaken one once it has played its
##     window) or the countdown ends, so each wave is a simultaneous reveal. A wave a corked
##     bottle is aimed at is not clear while the bottle waits for its reveal or its creeps
##     are still to come (holds, SimMatch.wave_held), so a pack always walks the wave it was
##     corked for, and the next window for both waits for it, up to fizzle_t after the horn.
##   The Drift: from window drift_from, each window offers `offered` of the four packs,
##     drawn from the match's SimRng when the window opens for both (EV_DRIFT), never
##     leaving out the pack the window before left out.
##   Cork and uncork: CORK(tier, commit) in a window charges the tier's price and stands a
##     bottle that holds the commitment only; UNCORK(pack, salt) during the wave, from
##     uncork_after_t after the horn, spawns the pack on the rival's road (sent_by) if the
##     commitment (commit()) matches and the pack was offered; a bottle with no valid reveal
##     by fizzle_t fizzles, its gold spent. An uncorking adds its tier's stipend, paid at
##     every wave clear of the seat's hollow (EV_GOLD "stipend").
##   Breach: an uncorked creep that reaches the rival's Holdfast takes its toll and pays its
##     sender breach_pay bounties (EV_BREACH); one killed pays its killer the bounty.
##   The Seawall: a charge every every_lives lives lost, at most `charges`; SEAWALL during a
##     wave stuns and wounds every creep near the seat's Holdfast (EV_SEAWALL).
##   The end: a Holdfast that falls loses at once (both on one tick: a draw). Both standing
##     after wave 12, the Surge plays waves 9 to 11 again (EV_SURGE); after the last, more
##     lives wins, then more breach dealt, then a draw (decide()).
##
## The state lives on the records (SimMatch.bottles, drift_*, horn_tick; SimSeat.stipend
## and the Seawall's; SimTeam.breach_dealt; SimHollow.sends) and in the codec's M7 block;
## this class holds the rules only. Nothing here runs outside a duel (SimMatch.duel).
@warning_ignore_start("integer_division")
class_name SimUndertow
extends RefCounted

## The caretaker raises its Seawall once the creeps inside the ring would take this many
## lives, or a boss stands in it (Caretaker.wants_seawall).
const CARETAKER_SEAWALL_TOLL := 3


# ── The commitment (contract §2) ──


## SHA-256 through HashingContext over the match seed (4 bytes big-endian), the seat
## (1-based, 1 byte), the window (the wave it precedes, 1 byte), the pack's CHECK_IDS index
## (1 byte) and the salt (salt_hi then salt_lo, 4 bytes big-endian each, of the unsigned
## 32-bit value). The commit is the digest's first 8 bytes as [b, c]: each 4 bytes read
## big-endian as an unsigned 32-bit number, carried as the signed i32 with the same bits.
static func commit(
	match_seed: int, seat: int, window: int, pack: int, salt_hi: int, salt_lo: int
) -> Array:
	var bytes := PackedByteArray()
	_put_be32(bytes, match_seed)
	bytes.append(seat & 0xFF)
	bytes.append(window & 0xFF)
	bytes.append(pack & 0xFF)
	_put_be32(bytes, salt_hi)
	_put_be32(bytes, salt_lo)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	var digest := ctx.finish()
	var hi := (digest[0] << 24) | (digest[1] << 16) | (digest[2] << 8) | digest[3]
	var lo := (digest[4] << 24) | (digest[5] << 16) | (digest[6] << 8) | digest[7]
	return [signed32(hi), signed32(lo)]


## The signed i32 with the bits of a 32-bit value.
static func signed32(value: int) -> int:
	var v := value & 0xFFFFFFFF
	return v - 0x100000000 if v >= 0x80000000 else v


static func _put_be32(bytes: PackedByteArray, value: int) -> void:
	var v := value & 0xFFFFFFFF
	bytes.append((v >> 24) & 0xFF)
	bytes.append((v >> 16) & 0xFF)
	bytes.append((v >> 8) & 0xFF)
	bytes.append(v & 0xFF)


# ── The preset's numbers ──


static func rules_of(m: SimMatch) -> Dictionary:
	return m.rules["duel"]


static func _num(m: SimMatch, key: String) -> int:
	return int(rules_of(m)[key])


static func _seawall_num(m: SimMatch, key: String) -> int:
	return int((rules_of(m)["seawall"] as Dictionary)[key])


static func _surge_num(m: SimMatch, key: String) -> int:
	return int((rules_of(m)["surge"] as Dictionary)[key])


## The wave whose list (and tier) wave or window `wave` plays: itself up to the list's
## last, then the Surge's waves in turn (wave 13 plays wave 9 again).
static func content_wave(m: SimMatch, wave: int) -> int:
	var n := m.waves.size()
	if not m.duel or wave <= n:
		return wave
	var repeats: Array = (rules_of(m)["surge"] as Dictionary)["waves"]
	return int(repeats[clampi(wave - n - 1, 0, repeats.size() - 1)])


## 1 to 3 for a wave or window of the Surge, 0 otherwise.
static func surge_of(m: SimMatch, wave: int) -> int:
	return maxi(0, wave - m.waves.size()) if m.duel else 0


## The last wave the hollows play: the list's, and in a duel the Surge's after it.
static func last_wave(m: SimMatch) -> int:
	if not m.duel:
		return m.waves.size()
	return m.waves.size() + ((rules_of(m)["surge"] as Dictionary)["waves"] as Array).size()


## The tiers a cork may take in window `window`, in tier order.
static func tiers_in(m: SimMatch, window: int) -> PackedInt32Array:
	var out := PackedInt32Array()
	var w := content_wave(m, window)
	var tiers: Array = rules_of(m)["tiers"]
	for i in tiers.size():
		var span: Array = (tiers[i] as Dictionary)["windows"]
		if w >= int(span[0]) and w <= int(span[1]):
			out.append(i)
	return out


## What a cork of `tier` costs in window `window` (the Surge's at cork_price_pm).
static func cork_price(m: SimMatch, tier: int, window: int) -> int:
	var price := int((rules_of(m)["tiers"][tier] as Dictionary)["price"])
	if surge_of(m, window) > 0:
		return price * _surge_num(m, "cork_price_pm") / 1000
	return price


static func tier_stipend(m: SimMatch, tier: int) -> int:
	return int((rules_of(m)["tiers"][tier] as Dictionary)["stipend"])


## How many corks a seat may make in window `window`.
static func corks_allowed(m: SimMatch, window: int) -> int:
	if content_wave(m, window) >= _num(m, "corks_two_from"):
		return int(rules_of(m).get("corks_two", 2))
	return _num(m, "corks")


## How many bottles seat `seat` corked in window `window`.
static func corks_of(m: SimMatch, seat: int, window: int) -> int:
	var n := 0
	for b in m.bottle_list:
		if b.seat == seat and b.window == window:
			n += 1
	return n


## The cheapest tier window `window` offers that costs at most `gold`, or -1.
static func cheapest_tier(m: SimMatch, window: int, gold: int) -> int:
	var best := -1
	var best_price := 0
	for tier in tiers_in(m, window):
		var price := cork_price(m, tier, window)
		if price <= gold and (best < 0 or price < best_price):
			best = tier
			best_price = price
	return best


# ── The shared clock ──


## Whether the window is open for both: no standing hollow is in its wave and one is in its
## window. Corks are taken only then.
static func window_open(m: SimMatch) -> bool:
	var any := false
	for h in m.hollows:
		if h.phase == SimTypes.PHASE_WAVE:
			return false
		if h.phase == SimTypes.PHASE_PREP:
			any = true
	return any


## Whether a wave runs on any hollow: from the horn until the last standing hollow clears.
static func wave_running(m: SimMatch) -> bool:
	for h in m.hollows:
		if h.phase == SimTypes.PHASE_WAVE:
			return true
	return false


## Stage 2 before the hollows' spawns: the one countdown and the one horn. The hollows'
## countdowns stand still while any hollow still plays its wave, and run together after.
static func run_clock(m: SimMatch) -> void:
	if m.over:
		return
	var open := PackedInt32Array()
	for h in m.hollows:
		if h.phase == SimTypes.PHASE_WAVE:
			return
		if h.phase == SimTypes.PHASE_PREP:
			open.append(h.id)
	if open.is_empty():
		return
	if _all_ready(m, open):
		var early := m.early_gold(open[0])
		if early > 0:
			for id in open:
				for n in m.hollows[id].seats:
					m.add_gold(m.seat(n), early, "ready")
		_horn(m, open, early)
		return
	for id in open:
		m.hollows[id].countdown_t -= 1
	if m.hollows[open[0]].countdown_t <= 0:
		_horn(m, open, 0)


## Every seat on the open hollows is Ready, and one of them is present. A seat the
## caretaker plays is Ready once it has said so, which it does when it has corked and
## built for the window (Caretaker.think, on the window's first tick for both,
## SimMatch._caretakers), so a player's Ready never sounds the horn before the caretaker
## had its window; a duel nobody is present at waits out its windows, as High Water's.
static func _all_ready(m: SimMatch, open: PackedInt32Array) -> bool:
	var present := 0
	for id in open:
		for n in m.hollows[id].seats:
			var s := m.seat(n)
			if not s.ready:
				return false
			if s.state == SimTypes.SEAT_PRESENT:
				present += 1
	return present > 0


## The first tick of the window both hollows share (the latest hollow's window_tick, the
## tick after the clear that opened it for both), or -1 while it is not open.
static func shared_window_tick(m: SimMatch) -> int:
	if not window_open(m):
		return -1
	var first := -1
	for h in m.hollows:
		if h.phase == SimTypes.PHASE_PREP:
			first = maxi(first, h.window_tick)
	return first


static func _horn(m: SimMatch, open: PackedInt32Array, early: int) -> void:
	m.horn_tick = m.tick
	for id in open:
		SimWaves.start_wave(m, m.hollows[id], early)


## After hollow `h` opened a window (SimWaves.open_window): once no hollow plays its wave
## any more, the window is open for both. Their countdowns start level, the Surge says so
## before its waves, and from drift_from the Drift draws its packs.
static func window_opened(m: SimMatch, h: SimRecords.SimHollow) -> void:
	if wave_running(m):
		return
	for other in m.hollows:
		if other.phase == SimTypes.PHASE_PREP:
			other.countdown_t = h.countdown_t
	var window := h.wave + 1
	var surge := surge_of(m, window)
	if surge > 0:
		m.push_event(
			{
				"type": SimTypes.EV_SURGE,
				"surge": surge,
				"wave": content_wave(m, window),
				"window": window,
			}
		)
	if window >= _num(m, "drift_from"):
		draw_drift(m, window)


## The window's length for hollow `h` opening before its next wave: the Surge's are short.
static func window_length(m: SimMatch, h: SimRecords.SimHollow, otherwise: int) -> int:
	if surge_of(m, h.wave + 1) > 0:
		return _surge_num(m, "window_t")
	return otherwise


# ── The Drift ──


## Draws window `window`'s packs from the match's SimRng: the packs left out are drawn
## from those the window before did not leave out, the rest are offered in CHECK_IDS order.
static func draw_drift(m: SimMatch, window: int) -> void:
	var count := SimContent.CHECK_IDS.size()
	var offered := clampi(_num(m, "offered"), 1, count)
	var pool := PackedInt32Array()
	for i in count:
		if (m.drift_left & (1 << i)) == 0:
			pool.append(i)
	var left := 0
	for k in count - offered:
		if pool.is_empty():
			for i in count:
				if (left & (1 << i)) == 0:
					pool.append(i)
		var j := m.rng.below(pool.size())
		left |= 1 << pool[j]
		pool.remove_at(j)
	m.drift_window = window
	m.drift_left = left
	m.drift_packs = PackedInt32Array()
	var ids := []
	var left_out := ""
	for i in count:
		if (left & (1 << i)) == 0:
			m.drift_packs.append(i)
			ids.append(SimContent.CHECK_IDS[i])
		elif left_out == "":
			left_out = SimContent.CHECK_IDS[i]
	m.push_event(
		{"type": SimTypes.EV_DRIFT, "window": window, "packs": ids, "left_out": left_out}
	)


# ── Commands ──


## CORK(a = tier, b and c = the commit's halves) in the window both hollows share, for a
## tier this window offers: the price at once, and a bottle.
static func cork(m: SimMatch, s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var h := m.hollows[s.hollow]
	var window := h.wave + 1
	if h.phase != SimTypes.PHASE_PREP or not window_open(m) or m.drift_window != window:
		m.reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	var tier := int(cmd["a"])
	if not tiers_in(m, window).has(tier):
		m.reject(s, cmd, SimTypes.REFUSE_BAD_COMMAND)
		return
	if corks_of(m, s.seat, window) >= corks_allowed(m, window):
		m.reject(s, cmd, SimTypes.REFUSE_NO_CORKS_LEFT)
		return
	var price := cork_price(m, tier, window)
	if s.gold < price:
		m.reject(s, cmd, SimTypes.REFUSE_NOT_ENOUGH_GOLD)
		return
	var b := SimRecords.SimBottle.new()
	b.id = m.new_id()
	b.seat = s.seat
	b.tier = tier
	b.window = window
	b.commit_hi = signed32(int(cmd["b"]))
	b.commit_lo = signed32(int(cmd["c"]))
	b.price = price
	m.bottle_list.append(b)
	m.push_event(
		{
			"type": SimTypes.EV_CORK,
			"seat": s.seat,
			"seq": cmd["seq"],
			"team": s.team,
			"tier": tier,
			"window": window,
			"bottle": b.id,
			"price": price,
		}
	)
	m.add_gold(s, -price, "cork")


## The seat's bottles still corked for the wave that runs: uncorked or fizzled ones never,
## and none from fizzle_t after the horn on.
static func pending(m: SimMatch, seat: int) -> Array[SimRecords.SimBottle]:
	var out: Array[SimRecords.SimBottle] = []
	if m.horn_tick < 0 or m.tick >= m.horn_tick + _num(m, "fizzle_t"):
		return out
	var s := m.seat(seat)
	var wave := m.hollows[s.hollow].wave if s else -1
	for b in m.bottle_list:
		if b.seat == seat and b.window == wave and not b.uncorked and not b.fizzled:
			out.append(b)
	return out


## UNCORK(a = pack, b and c = the salt's halves) during the wave, from uncork_after_t
## after the horn: the first of the seat's corked bottles whose commitment the reveal
## matches, for a pack its window offered, is uncorked and its pack sent.
static func uncork(m: SimMatch, s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	if not wave_running(m):
		m.reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	var corked := pending(m, s.seat)
	if corked.is_empty():
		m.reject(s, cmd, SimTypes.REFUSE_NOTHING_CORKED)
		return
	if m.tick < m.horn_tick + _num(m, "uncork_after_t"):
		m.reject(s, cmd, SimTypes.REFUSE_TOO_EARLY)
		return
	var pack := int(cmd["a"])
	var found: SimRecords.SimBottle = null
	if pack >= 0 and pack < SimContent.CHECK_IDS.size():
		for b in corked:
			if m.drift_window != b.window or not m.drift_packs.has(pack):
				continue
			var c := commit(m.match_seed, s.seat, b.window, pack, int(cmd["b"]), int(cmd["c"]))
			if int(c[0]) == b.commit_hi and int(c[1]) == b.commit_lo:
				found = b
				break
	if found == null:
		m.reject(s, cmd, SimTypes.REFUSE_BAD_REVEAL)
		return
	found.uncorked = true
	found.pack = pack
	if surge_of(m, found.window) == 0:
		s.stipend += tier_stipend(m, found.tier)
	var rival := rival_hollow(m, s)
	var creeps := _send(m, s, found, rival)
	m.push_event(
		{
			"type": SimTypes.EV_UNCORK,
			"seat": s.seat,
			"seq": cmd["seq"],
			"bottle": found.id,
			"pack": SimContent.CHECK_IDS[pack],
			"creeps": creeps,
			"hollow": rival.id if rival else -1,
			"stipend": s.stipend,
		}
	)


## The hollow seat `s`'s packs walk: the other team's.
static func rival_hollow(m: SimMatch, s: SimRecords.SimSeat) -> SimRecords.SimHollow:
	if m.teams.size() < 2:
		return null
	return m.hollows[m.teams[(s.team + 1) % m.teams.size()].hollows[0]]


## Queues bottle `b`'s pack on the rival's road, its first creep this tick and the others
## pack_interval_t apart. Returns how many.
static func _send(
	m: SimMatch, s: SimRecords.SimSeat, b: SimRecords.SimBottle, rival: SimRecords.SimHollow
) -> int:
	if rival == null:
		return 0
	var pack: Dictionary = (SimContent.PACKS[str(m.rules["map"])] as Dictionary)[SimContent.CHECK_IDS[b.pack]]
	var kind := SimContent.CREEP_IDS.find(str(pack["creep"]))
	var count := int((pack["counts"] as Array)[b.tier])
	var gap := maxi(0, _num(m, "pack_interval_t"))
	for k in count:
		rival.sends.append(kind)
		rival.sends.append(s.seat)
		rival.sends.append(m.tick + k * gap)
	return count


## SEAWALL during the seat's wave, with a charge and the last one's cooldown run out:
## every creep within radius_mm of its Holdfast is stunned stun_t and loses hp_pm of its
## maximum health; a boss loses boss_hp_pm and is slowed boss_slow_pm for stun_t instead.
static func seawall(m: SimMatch, s: SimRecords.SimSeat, cmd: Dictionary) -> void:
	var h := m.hollows[s.hollow]
	if h.phase != SimTypes.PHASE_WAVE:
		m.reject(s, cmd, SimTypes.REFUSE_WRONG_PHASE)
		return
	if s.seawall_charges <= 0:
		m.reject(s, cmd, SimTypes.REFUSE_NO_CHARGE)
		return
	if m.tick < s.seawall_ready:
		m.reject(s, cmd, SimTypes.REFUSE_SEAWALL_STANDING)
		return
	s.seawall_charges -= 1
	s.seawall_ready = m.tick + _seawall_num(m, "cooldown_t")
	var stun_t := _seawall_num(m, "stun_t")
	var inside := in_ring(m, h)
	for c in inside:
		var share := _seawall_num(m, "boss_hp_pm" if c.boss else "hp_pm")
		var dealt := c.max_hp_c * share / 1000
		if c.boss:
			SimEffects.apply_slow(m, c, _seawall_num(m, "boss_slow_pm"), stun_t, s.seat, 0, false)
		else:
			c.stun_until = maxi(c.stun_until, m.tick + stun_t)
			c.stun_seat = s.seat
			m.push_event(
				{
					"type": SimTypes.EV_STATUS,
					"effect": SimTypes.EFFECT_STUN,
					"creep": c.id,
					"tower": 0,
					"seat": s.seat,
					"amount": 1000,
					"until": c.stun_until,
				}
			)
		c.hp_c -= dealt
		s.damage_c += dealt
	for c in inside:
		if c.alive and c.hp_c <= 0:
			m.kill(c, s.seat)
	var road := h.road
	m.push_event(
		{
			"type": SimTypes.EV_SEAWALL,
			"seat": s.seat,
			"seq": cmd["seq"],
			"hollow": h.id,
			"x": road.x_at(road.length_um),
			"z": road.z_at(road.length_um),
			"r": _seawall_num(m, "radius_mm"),
			"struck": inside.size(),
			"charges": s.seawall_charges,
			"ready": s.seawall_ready,
		}
	)


## The creeps on hollow `h` within the Seawall's radius of its Holdfast, in id order.
static func in_ring(m: SimMatch, h: SimRecords.SimHollow) -> Array[SimRecords.SimCreep]:
	var out: Array[SimRecords.SimCreep] = []
	var road := h.road
	var x := road.x_at(road.length_um)
	var z := road.z_at(road.length_um)
	var r := _seawall_num(m, "radius_mm")
	for c in m.creeps:
		if c.hollow != h.id:
			continue
		var dx := road.x_at(c.dist_um) - x
		var dz := road.z_at(c.dist_um) - z
		if dx * dx + dz * dz <= r * r:
			out.append(c)
	return out


# ── The duel's stage (stage 2, after the hollows' clocks and spawns) ──


## Fizzles the bottles of the wave the horn started that are still corked at fizzle_t after
## it (a bottle corked in a window that opened before then waits for its own horn), then
## spawns the uncorked creeps whose tick has come, hollow by hollow, in the order they were
## sent.
static func run_stage(m: SimMatch) -> void:
	if m.horn_tick >= 0 and m.tick == m.horn_tick + _num(m, "fizzle_t"):
		for b in m.bottle_list:
			if not b.uncorked and not b.fizzled and b.window == m.hollows[m.seat(b.seat).hollow].wave:
				b.fizzled = true
				m.push_event({"type": SimTypes.EV_FIZZLE, "seat": b.seat, "bottle": b.id})
	for h in m.hollows:
		if h.sends.is_empty() or h.phase != SimTypes.PHASE_WAVE:
			continue
		var keep := PackedInt32Array()
		var i := 0
		while i < h.sends.size():
			if h.sends[i + 2] <= m.tick:
				SimWaves.spawn(m, h, h.sends[i], h.sends[i + 1])
			else:
				keep.append(h.sends[i])
				keep.append(h.sends[i + 1])
				keep.append(h.sends[i + 2])
			i += 3
		h.sends = keep


## Whether hollow `h`'s wave must wait before it clears: uncorked creeps still to come on
## its road, or a rival's bottle for this wave still corked (its reveal may yet come).
static func holds(m: SimMatch, h: SimRecords.SimHollow) -> bool:
	if not h.sends.is_empty():
		return true
	for b in m.bottle_list:
		if not b.uncorked and not b.fizzled and b.window == h.wave and m.seat(b.seat).team != h.team:
			return true
	return false


## At a wave clear: each seat of the hollow is paid its stipend.
static func pay_stipends(m: SimMatch, h: SimRecords.SimHollow) -> void:
	for n in h.seats:
		var s := m.seat(n)
		if s.stipend > 0:
			m.add_gold(s, s.stipend, "stipend")


## An uncorked creep reached the Holdfast of team `team`, taking `taken` lives: its sender's
## team has dealt them, and the sender is paid breach_pay bounties.
static func breach(m: SimMatch, c: SimRecords.SimCreep, team: SimRecords.SimTeam, taken: int) -> void:
	var sender := m.seat(c.sent_by)
	if sender == null:
		return
	var pay := _num(m, "breach_pay") * c.bounty
	m.teams[sender.team].breach_dealt += taken
	m.push_event(
		{
			"type": SimTypes.EV_BREACH,
			"creep": c.id,
			"kind": c.kind,
			"by": sender.seat,
			"team": team.id,
			"toll": c.toll,
			"pay": pay,
		}
	)
	if pay > 0:
		m.add_gold(sender, pay, "breach")


## Team `team` lost `lost` lives: every every_lives of them charges its seats' Seawalls,
## up to `charges` held.
static func lives_lost(m: SimMatch, team: SimRecords.SimTeam, lost: int) -> void:
	var every := maxi(1, _seawall_num(m, "every_lives"))
	var most := _seawall_num(m, "charges")
	for s in m.seats:
		if s.team != team.id:
			continue
		s.seawall_lost += lost
		while s.seawall_lost >= every:
			s.seawall_lost -= every
			s.seawall_charges = mini(most, s.seawall_charges + 1)


# ── The end ──


## Stage 8 of a duel: a fallen Holdfast loses at once (both on one tick: a draw); both
## done after the Surge, more lives wins, then more breach dealt, then a draw. Decides at
## most once, into the race's record (SimMatch.race_rule, race_outcomes) and EV_RACE
## "decided", which the views of both competitive modes read.
static func decide(m: SimMatch) -> void:
	if m.teams.size() != 2:
		return
	var a := m.teams[0]
	var b := m.teams[1]
	var ha := m.hollows[a.hollows[0]]
	var hb := m.hollows[b.hollows[0]]
	var fell_a := ha.phase == SimTypes.PHASE_FALLEN
	var fell_b := hb.phase == SimTypes.PHASE_FALLEN
	var winner := -2  # -2 open, -1 a draw, else the winning team
	var rule := ""
	if fell_a or fell_b:
		rule = "fell"
		winner = -1 if fell_a and fell_b else (1 if fell_a else 0)
	elif ha.phase == SimTypes.PHASE_DONE and hb.phase == SimTypes.PHASE_DONE:
		rule = "lives"
		winner = SimMatch._better(a.lives, b.lives)
		if winner == -1:
			rule = "breach"
			winner = SimMatch._better(a.breach_dealt, b.breach_dealt)
	if winner == -2:
		return
	if winner == -1:
		rule = "draw"
	m.race_rule = SimTypes.RACE_RULES.find(rule)
	m.race_outcomes = PackedInt32Array()
	for t in m.teams:
		if winner == -1:
			m.race_outcomes.append(SimTypes.OUTCOME_DRAW)
		else:
			m.race_outcomes.append(SimTypes.OUTCOME_WON if t.id == winner else SimTypes.OUTCOME_LOST)
	m.race_event(
		"decided", winner, m.cleared_waves(maxi(winner, 0)),
		{"outcomes": Array(m.race_outcomes), "rule": rule}
	)


# ── What the caretaker and the bots read ──


## The pack bottle `b` holds when it was corked with salt 0 (a caretaker's, whose corks
## are not hidden): its window's offered pack whose commitment it is, or -1.
static func salt_zero_pack(m: SimMatch, b: SimRecords.SimBottle) -> int:
	if m.drift_window != b.window:
		return -1
	for pack in m.drift_packs:
		var c := commit(m.match_seed, b.seat, b.window, pack, 0, 0)
		if int(c[0]) == b.commit_hi and int(c[1]) == b.commit_lo:
			return pack
	return -1


## The offered pack the rival's coverage is weakest against (the caretaker's pick,
## contract §2): the one its standing towers take longest to kill (pack_threat), ties to
## the earlier check; -1 when the window offers nothing.
static func weakest_pack(m: SimMatch, seat: int) -> int:
	var s := m.seat(seat)
	var rival := (s.team + 1) % maxi(1, m.teams.size())
	var window := m.hollows[s.hollow].wave + 1
	var tiers := tiers_in(m, window)
	var tier := tiers[0] if not tiers.is_empty() else 0
	var best := -1
	var best_threat := 0
	for pack in m.drift_packs:
		var threat := pack_threat(m, rival, pack, tier)
		if best < 0 or threat > best_threat:
			best = pack
			best_threat = threat
	return best


## How hard pack CHECK_IDS[pack] at `tier` is for team `team`'s standing towers: its
## creeps' health (before the wave's growth, the same for every pack of a window) over the
## damage those towers deal it in a minute, each tower's hit through the creep's armour
## (less its pierce, at least a quarter, as SimMatch._hurt) at its own rate, fliers only
## from towers that reach the sky (with their air bonus), and a splash, a bee cloud or a
## pulse counted three times and a bounce once more per bounce against a pack of three or
## more. Higher is weaker coverage; integers in thousandths of a minute.
static func pack_threat(m: SimMatch, team: int, pack: int, tier: int) -> int:
	var spec: Dictionary = (SimContent.PACKS[str(m.rules["map"])] as Dictionary)[SimContent.CHECK_IDS[pack]]
	var data: Dictionary = SimContent.CREEPS[str(spec["creep"])]
	var count := int((spec["counts"] as Array)[tier])
	var winged := bool(data.get("winged", false))
	var armor := int(data["armor_c"]) if bool(m.rules.get("armor", true)) else 0
	var per_minute := 0
	for t in m.towers:
		var owner := m.seat(t.owner)
		if owner == null or owner.team != team or t.dmg_c <= 0 or (winged and not t.air):
			continue
		var left := maxi(0, armor - t.pierce_c)
		var hit := maxi(t.dmg_c - left, t.dmg_c / 4)
		if winged and t.air_bonus_pm > 0:
			hit = hit * (1000 + t.air_bonus_pm) / 1000
		var area := 1
		if count >= 3:
			if t.cloud_mm > 0 or t.pulse or (t.splash_mm > 0 and not winged):
				area = 3
			elif t.bounces > 0:
				area = 1 + t.bounces
		per_minute += hit * area * SimTypes.TICKS_PER_SECOND * 60 / m.cooldown_of(t)
	return count * int(data["hp_c"]) * 1000 / maxi(1, per_minute)


## The seat's bottles as the views show them: {id, tier, window, price, uncorked,
## fizzled}, and the pack (a CHECK_IDS id) only once it is uncorked.
static func bottles_of(m: SimMatch, seat: int) -> Array:
	var out := []
	for b in m.bottle_list:
		if b.seat != seat:
			continue
		var row := {
			"id": b.id,
			"tier": b.tier,
			"window": b.window,
			"price": b.price,
			"uncorked": b.uncorked,
			"fizzled": b.fizzled,
		}
		if b.uncorked:
			row["pack"] = SimContent.CHECK_IDS[b.pack]
		out.append(row)
	return out
