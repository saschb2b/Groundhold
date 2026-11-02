## A hollow's rhythm (design 1.1): the build window counting down in ticks, the horn
## (when the window runs out or every seat is Ready), the spawns of a wave, and the clear
## that pays the bonus (and Hive Tithe, M6) and opens the next window. Every hollow keeps
## its own clock: in a race (M6) each team's windows, Ready and horn are its own. Under a
## shared clock (M7, the duel) SimUndertow.run_clock counts the one window and sounds the
## one horn, and a hollow here only spawns.
##
## (M8, design 2.7) Where the rules' stack_max is above 1 (High Water, Tide Race), waves
## stack: Ready is taken during a wave too (SimMatch.can_stack), and on the tick every
## present seat is Ready the stacked horn sounds (stack_wave): the next wave sets out at
## once, its first creep on the horn's tick and the rest on its own schedule, while what is
## left of the older wave keeps its own (SimHollow.behind), so the Welling sends both and
## their creeps walk among each other. It pays the window it skips and the stake. A wave is
## on the road from its horn until it clears; waves clear in order (check_clear), each
## paying its own bonus, and no window comes between stacked waves: the next opens once the
## last wave on the road clears.
@warning_ignore_start("integer_division")
class_name SimWaves
extends RefCounted


## Stage 2 of a tick: the window's countdown and the horn, then the wave's spawns; (M8) in a
## wave of a preset that stacks, the stacked horn first.
static func run_clock(m: SimMatch, h: SimRecords.SimHollow) -> void:
	if h.phase == SimTypes.PHASE_PREP and not m.over and not m.shared_clock:
		if _all_ready(m, h):
			# Everyone is Ready: the horn sounds at once and each seat is paid one gold
			# per whole second left on the countdown.
			var early := m.early_gold(h.id)
			if early > 0:
				for n in h.seats:
					m.add_gold(m.seat(n), early, "ready")
			start_wave(m, h, early)
		else:
			h.countdown_t -= 1
			if h.countdown_t <= 0:
				start_wave(m, h, 0)
	elif h.phase == SimTypes.PHASE_WAVE and m.stack_max > 1:
		# (on the tick the last Ready lands, whatever of the wave is still to come;
		# can_stack holds the horn while a seat is returning, and at stack_max)
		if m.can_stack(h.id) and _all_ready(m, h):
			stack_wave(m, h)
	if h.phase == SimTypes.PHASE_WAVE:
		_spawns(m, h)


## Every seat of the hollow is Ready; seats the caretaker plays count as Ready. The early
## horn is the players' call: a hollow with no player present (every seat caretaken) waits
## out its windows, so its caretakers build in them as they would beside a player
## (review M1 determinism 2: it sounded on each window's first tick, before they could).
## In a race (M6) the caretaker races too: a hollow it plays alone sounds the horn once
## every caretaken seat has said Ready, which it does when its window's build steps are
## done (Caretaker.think). (M8) The stacked horn asks the same in a wave: a hollow nobody is
## present at stacks only as its caretakers call, which they do in a race alone.
static func _all_ready(m: SimMatch, h: SimRecords.SimHollow) -> bool:
	var present := 0
	var called := true
	for n in h.seats:
		var s := m.seat(n)
		if s.state == SimTypes.SEAT_PRESENT:
			if not s.ready:
				return false
			present += 1
		elif not s.ready:
			called = false
	return present > 0 or (m.race and called and h.seats.size() > 0)


## A window's horn: the next wave sets out, its first creep at once.
static func start_wave(m: SimMatch, h: SimRecords.SimHollow, early: int) -> void:
	h.wave += 1
	h.countdown_t = 0
	h.queue = PackedInt32Array()
	h.cursor = 0
	h.spawn_wait_t = 0
	for n in h.seats:
		m.seat(n).ready = false
	if m.race:
		m.teams[h.team].wave_kills = 0
		m.teams[h.team].stack_kills = PackedInt32Array()
	var last := m.last_wave()
	if h.wave > last:
		h.wave = last
		finish(m, h)
		m.push_event(
			{"type": SimTypes.EV_WAVE, "hollow": h.id, "wave": h.wave, "phase": h.phase}
		)
		return
	h.phase = SimTypes.PHASE_WAVE
	_queue_wave(m, h)
	m.push_event(
		{
			"type": SimTypes.EV_WAVE,
			"hollow": h.id,
			"wave": h.wave,
			"phase": h.phase,
			"start": true,
			"early": early
		}
	)


## (M8) The stacked horn: during wave `h.wave`, on the tick every present seat is Ready, the
## next wave is called. Each seat is paid the whole window it skips and the stake
## (SimMatch.stack_pay: the tolls of every creep of the waves on the road, walking or still
## to come, at the rules' stake_pm) in one EV_GOLD "stack"; every Ready is cleared. The
## called wave sets out at once, its first creep on this tick as at a window's horn and the
## rest on its own schedule, and what the older wave has still to send keeps the ticks it
## had (hold_back), so the two schedules run together. EV_WAVE says so with `stacked` and
## `stake` (those lives) beside `start` and `early` (each seat's pay). No window opens: the
## waves before it stay on the road until they clear.
static func stack_wave(m: SimMatch, h: SimRecords.SimHollow) -> void:
	var pay := m.stack_pay(h.id)
	var stake := m.road_tolls(h.id)
	var paid := int(pay[0]) + int(pay[1])
	if paid > 0:
		for n in h.seats:
			m.add_gold(m.seat(n), paid, "stack")
	h.wave += 1
	for n in h.seats:
		m.seat(n).ready = false
	if m.race:
		m.teams[h.team].stack_kills.append(0)
	hold_back(m, h)
	_queue_wave(m, h)
	m.push_event(
		{
			"type": SimTypes.EV_WAVE,
			"hollow": h.id,
			"wave": h.wave,
			"phase": h.phase,
			"start": true,
			"early": paid,
			"stacked": true,
			"stake": stake
		}
	)


## Wave `h.wave`'s spawns into the hollow's queue as [creep kind index, ticks before it]: the
## first creep at once, at a window's horn and (M8) at a stacked one alike.
static func _queue_wave(m: SimMatch, h: SimRecords.SimHollow) -> void:
	h.queue = PackedInt32Array()
	h.cursor = 0
	h.spawn_wait_t = 0
	var first := true
	for group: Dictionary in m.waves[SimUndertow.content_wave(m, h.wave) - 1]:
		var kind := SimContent.CREEP_IDS.find(str(group["creep"]))
		for i in int(group["count"]):
			h.queue.append(kind)
			h.queue.append(0 if first else int(group["interval_t"]))
			first = false


## (M8) At a stacked horn, before the called wave's spawns take the queue: the older wave's
## (`h.wave` - 1's, now that the horn has counted the called one) spawns still to come move
## to SimHollow.behind as [kind, wave, tick], each on the tick the queue would have sent it:
## the next once its wait runs out (on this tick, when it already has), each after it its own
## wait later. Stage 2 runs before this tick's spawns, so nothing is skipped or sent twice.
static func hold_back(m: SimMatch, h: SimRecords.SimHollow) -> void:
	var n := h.queue.size() / 2
	if h.cursor >= n:
		return
	var at := m.tick + maxi(0, h.spawn_wait_t)
	for i in range(h.cursor, n):
		if i > h.cursor:
			at += h.queue[2 * i + 1]
		h.behind.append(h.queue[2 * i])
		h.behind.append(h.wave - 1)
		h.behind.append(at)
	h.cursor = n


## Spawns every creep whose wait has run out; the first of a wave comes at once. (M8) The
## older waves' spawns a stacked horn held back come first, each on its own tick.
static func _spawns(m: SimMatch, h: SimRecords.SimHollow) -> void:
	if not h.behind.is_empty():
		_spawn_behind(m, h)
	var n := h.queue.size() / 2
	while h.cursor < n and h.spawn_wait_t <= 0:
		spawn(m, h, h.queue[2 * h.cursor])
		h.cursor += 1
		if h.cursor < n:
			h.spawn_wait_t += h.queue[2 * h.cursor + 1]
	if h.cursor < n:
		h.spawn_wait_t -= 1


## (M8) Spawns the creeps of SimHollow.behind whose tick has come, in its order (the oldest
## wave first), each with its own wave.
static func _spawn_behind(m: SimMatch, h: SimRecords.SimHollow) -> void:
	var keep := PackedInt32Array()
	var i := 0
	while i < h.behind.size():
		if h.behind[i + 2] <= m.tick:
			spawn(m, h, h.behind[i], 0, h.behind[i + 1])
		else:
			keep.append(h.behind[i])
			keep.append(h.behind[i + 1])
			keep.append(h.behind[i + 2])
		i += 3
	h.behind = keep


## The maximum health, in hundredths, of a creep of `kind_id` spawned on hollow `h` in its
## wave `wave`: the table's, grown hp_growth_pm a wave after the first and scaled by the
## hollow's seats (hp_by_seats_pm); (M8) then the level's: its hp_pm, or a boss's
## boss_hp_pm, per mille (nothing at Normal, which lays no key); (M7) in a Surge wave the
## wave it repeats grows it, and the Surge's hp_pm on top. Spawns take it, and the wave list
## shows it ahead.
static func health_c(m: SimMatch, h: SimRecords.SimHollow, kind_id: String, wave: int) -> int:
	var data: Dictionary = SimContent.CREEPS[kind_id]
	var growth := int(m.rules["hp_growth_pm"]) * maxi(0, SimUndertow.content_wave(m, wave) - 1)
	var by_seats: Array = m.rules["hp_by_seats_pm"]
	var seats_pm := int(by_seats[clampi(h.seats.size(), 1, by_seats.size()) - 1])
	var hp := int(data["hp_c"]) * (1000 + growth) * seats_pm / 1000000
	var level_pm := int(m.rules.get("boss_hp_pm" if bool(data.get("boss", false)) else "hp_pm", 1000))
	if level_pm != 1000:
		hp = hp * level_pm / 1000
	if SimUndertow.surge_of(m, wave) > 0:
		hp = hp * int((SimUndertow.rules_of(m)["surge"] as Dictionary)["hp_pm"]) / 1000
	return hp


## The armour, in hundredths, a creep of `kind_id` wears in match `m`: the table's where
## armour is on (none in classic), and (M8) a boss its level's boss_armor_c more. Spawns
## take it, and the wave list shows it ahead.
static func armor_c(m: SimMatch, kind_id: String) -> int:
	if not bool(m.rules.get("armor", true)):
		return 0
	var data: Dictionary = SimContent.CREEPS[kind_id]
	var armor := int(data["armor_c"])
	if bool(data.get("boss", false)):
		armor += int(m.rules.get("boss_armor_c", 0))
	return armor


## A creep of kind index `kind` at the Welling, with this wave's, this team's and (M8) the
## level's health (health_c) and armour (armor_c). `sent_by` is the seat whose uncorked pack
## it is (0 for the wave's own), whose creeps come stronger than the wave's own by the duel's
## send_hp_pm (SimUndertow.send_health_c). (M8) With a `wave`, it comes with that wave and grows by it
## (a creep an older wave still sends after a stacked horn); with 0, with its hollow's newest
## wave, or in a window (a debug write's) with the coming one, grown by the newest.
static func spawn(
	m: SimMatch, h: SimRecords.SimHollow, kind: int, sent_by := 0, wave := 0
) -> SimRecords.SimCreep:
	var kind_id: String = SimContent.CREEP_IDS[kind]
	var data: Dictionary = SimContent.CREEPS[kind_id]
	var c := SimRecords.SimCreep.new()
	c.id = m.new_id()
	c.hollow = h.id
	c.kind = kind_id
	c.wave = wave if wave > 0 else default_wave(h)
	var boss := bool(data.get("boss", false))
	# (a stacked creep grows by its own wave; a Surge's only ever comes in a duel, which
	# never stacks, so its own wave is the hollow's)
	c.max_hp_c = health_c(m, h, kind_id, wave if wave > 0 else h.wave)
	if sent_by != 0 and m.duel:
		c.max_hp_c = SimUndertow.send_health_c(m, c.max_hp_c, kind_id)
	c.hp_c = c.max_hp_c
	c.armor_c = armor_c(m, kind_id)
	c.speed_um_t = int(data["speed_um_t"])
	c.bounty = int(data["bounty"])
	c.toll = int(data["toll"])
	c.winged = bool(data.get("winged", false))
	c.boss = boss
	c.control_resist_pm = int(data.get("control_resist_pm", 0))
	c.sent_by = sent_by
	m.add_creep(c)
	# (M8: the creep's own wave, for a view that reads a frame of many ticks at once, where
	# the creep may be gone, or its hollow on another wave, by the time it reads the event)
	var event := {"type": SimTypes.EV_SPAWN, "id": c.id, "hollow": h.id, "kind": kind_id, "wave": c.wave}
	if sent_by != 0:
		event["sent_by"] = sent_by
	m.push_event(event)
	return c


## Stage 7: a wave is clear when nothing is left to spawn and its road is empty (in a duel,
## M7, also no uncorked creep still to come and no rival bottle still corked for it,
## SimUndertow.holds). Each seat gets the clear bonus (a Surge wave the bonus of the wave it
## repeats), the Tithe and (M7) its stipend; then the next window opens, or the hollow is
## done. In a duel the window opens for both once both have cleared
## (SimUndertow.window_opened).
##
## (M8) With waves stacked, the oldest on the road clears first: wave k clears once every
## creep of waves 1 to k has set out (to_come_up_to: the newest's queue, the older waves'
## held back) and none of them is on the road, so a younger wave whose road is already
## empty clears in the same stage right after it. Each clear pays its own wave's bonus and
## the Tithe and says EV_WAVE cleared k; in a race the next wave's kills become the oldest's
## (SimTeam.stack_kills). No window opens until the last wave on the road has cleared.
static func check_clear(m: SimMatch, h: SimRecords.SimHollow) -> void:
	while h.phase == SimTypes.PHASE_WAVE:
		var k := h.cleared + 1
		if to_come_up_to(h, k):
			return
		if _on_road_up_to(m, h, k):
			return
		if m.duel and SimUndertow.holds(m, h):
			return
		_clear(m, h, mini(k, h.wave))


## (M8) Whether the Welling has still to send a creep of wave `k` or an older one on hollow
## `h`: the newest wave's queue once `k` is the newest, and the older waves' held back.
static func to_come_up_to(h: SimRecords.SimHollow, k: int) -> bool:
	if k >= h.wave and h.cursor < h.queue.size() / 2:
		return true
	var i := 1
	while i < h.behind.size():
		if h.behind[i] <= k:
			return true
		i += 3
	return false


## Whether a creep of wave `k` or an older one is still on hollow `h`'s road (every creep
## on it, once `k` is the newest wave).
static func _on_road_up_to(m: SimMatch, h: SimRecords.SimHollow, k: int) -> bool:
	for c in m.creeps:
		if c.hollow == h.id and c.wave <= k:
			return true
	return false


static func _clear(m: SimMatch, h: SimRecords.SimHollow, k: int) -> void:
	var bonus_rule: Array = m.rules["clear_bonus"]
	var bonus := int(bonus_rule[0]) + int(bonus_rule[1]) * SimUndertow.content_wave(m, k)
	for n in h.seats:
		m.add_gold(m.seat(n), bonus, "clear")
	_tithe(m, h)
	if m.duel:
		SimUndertow.pay_stipends(m, h)
	h.cleared = k
	if k < h.wave:
		if m.race:
			# (the next wave on the road is now the oldest: its kills are the ones a fall
			# would count)
			var team := m.teams[h.team]
			if not team.stack_kills.is_empty():
				team.wave_kills = team.stack_kills[0]
				team.stack_kills.remove_at(0)
	elif h.wave >= m.last_wave():
		finish(m, h)
	else:
		open_window(m, h, false)
	m.push_event(
		{
			"type": SimTypes.EV_WAVE,
			"hollow": h.id,
			"wave": k,
			"phase": h.phase,
			"cleared": true,
			"bonus": bonus
		}
	)
	if m.duel and h.phase == SimTypes.PHASE_PREP:
		SimUndertow.window_opened(m, h)


## (M8) The wave a creep spawned on hollow `h` now comes with: the newest, or the coming one
## in a window.
static func default_wave(h: SimRecords.SimHollow) -> int:
	return h.wave + 1 if h.phase == SimTypes.PHASE_PREP else h.wave


## (M8) The waves hollow `h` has cleared as the M1 to M7 records say it: all of them in a
## window and once done, all but the one on the road in a wave, and in a race all but the
## one its Holdfast fell on. The codec's M8 block holds `cleared` only where it differs.
static func default_cleared(m: SimMatch, h: SimRecords.SimHollow) -> int:
	match h.phase:
		SimTypes.PHASE_PREP, SimTypes.PHASE_DONE:
			return h.wave
		SimTypes.PHASE_FALLEN:
			if m.race and m.teams[h.team].fell_wave > 0:
				return m.teams[h.team].fell_wave - 1
	return maxi(0, h.wave - 1)


## A hollow that cleared its last wave is done: its team's clear tick is now (the race
## time counts from it, M6), and a race says so (EV_RACE "cleared").
static func finish(m: SimMatch, h: SimRecords.SimHollow) -> void:
	h.phase = SimTypes.PHASE_DONE
	h.cleared = h.wave
	var team := m.teams[h.team]
	if team.clear_tick < 0:
		team.clear_tick = m.tick
		if m.race:
			m.race_event("cleared", team.id, h.wave)


## Hive Tithe (M6, design 3.4), where perks are on: at every wave clear each seat of the
## hollow whose perk it is gets its `gold` for each of its towers on one of the perk's
## `bases`, at most `cap` (EV_GOLD why "tithe").
static func _tithe(m: SimMatch, h: SimRecords.SimHollow) -> void:
	if not bool(m.rules.get("perks", true)):
		return
	for n in h.seats:
		var s := m.seat(n)
		var each := SimContent.perk_value(s.builder, "hive_tithe", "gold", 0)
		if each <= 0:
			continue
		var bases := SimContent.perk_list(s.builder, "hive_tithe", "bases")
		var count := 0
		for t in m.towers:
			if t.owner == s.seat and bases.has(t.kind):
				count += 1
		var pay := mini(count * each, SimContent.perk_value(s.builder, "hive_tithe", "cap", 0))
		if pay > 0:
			m.add_gold(s, pay, "tithe")


## A build window: first windows are longer, and longer again with company. A seat
## coming back from the caretaker gets its controls back here. (M8) A present seat's Ready
## said during the wave before (a stacked call whose horn had not sounded: a partner was
## not Ready yet) stands into the window; a caretaken seat's is cleared, so its caretaker
## builds in the window before it says Ready again (a race's), as it would have.
static func open_window(m: SimMatch, h: SimRecords.SimHollow, first: bool) -> void:
	h.phase = SimTypes.PHASE_PREP
	var table: Array = m.rules["window_first_t" if first else "window_t"]
	h.countdown_t = int(table[clampi(h.seats.size(), 1, table.size()) - 1])
	if m.duel:
		h.countdown_t = SimUndertow.window_length(m, h, h.countdown_t)
	# (the window's first tick: the match's first, or the tick after the stage 7 that
	# opened it)
	h.window_tick = 0 if first else m.tick + 1
	for n in h.seats:
		var s := m.seat(n)
		if s.state != SimTypes.SEAT_PRESENT:
			s.ready = false
		if s.state == SimTypes.SEAT_RETURNING:
			s.state = SimTypes.SEAT_PRESENT
			m.push_event({"type": SimTypes.EV_SEAT, "seat": s.seat, "state": s.state})
