## A hollow's rhythm (design 1.1): the build window counting down in ticks, the horn
## (when the window runs out or every seat is Ready), the spawns of a wave, and the clear
## that pays the bonus (and Hive Tithe, M6) and opens the next window. Every hollow keeps
## its own clock: in a race (M6) each team's windows, Ready and horn are its own. Under a
## shared clock (M7, the duel) SimUndertow.run_clock counts the one window and sounds the
## one horn, and a hollow here only spawns.
@warning_ignore_start("integer_division")
class_name SimWaves
extends RefCounted


## Stage 2 of a tick: the window's countdown and the horn, then the wave's spawns.
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
	if h.phase == SimTypes.PHASE_WAVE:
		_spawns(m, h)


## Every seat of the hollow is Ready; seats the caretaker plays count as Ready. The early
## horn is the players' call: a hollow with no player present (every seat caretaken) waits
## out its windows, so its caretakers build in them as they would beside a player
## (review M1 determinism 2: it sounded on each window's first tick, before they could).
## In a race (M6) the caretaker races too: a hollow it plays alone sounds the horn once
## every caretaken seat has said Ready, which it does when its window's build steps are
## done (Caretaker.think).
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
	var last := m.last_wave()
	if h.wave > last:
		h.wave = last
		finish(m, h)
		m.push_event(
			{"type": SimTypes.EV_WAVE, "hollow": h.id, "wave": h.wave, "phase": h.phase}
		)
		return
	h.phase = SimTypes.PHASE_WAVE
	var first := true
	for group: Dictionary in m.waves[SimUndertow.content_wave(m, h.wave) - 1]:
		var kind := SimContent.CREEP_IDS.find(str(group["creep"]))
		for i in int(group["count"]):
			h.queue.append(kind)
			h.queue.append(0 if first else int(group["interval_t"]))
			first = false
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


## Spawns every creep whose wait has run out; the first of a wave comes at once.
static func _spawns(m: SimMatch, h: SimRecords.SimHollow) -> void:
	var n := h.queue.size() / 2
	while h.cursor < n and h.spawn_wait_t <= 0:
		spawn(m, h, h.queue[2 * h.cursor])
		h.cursor += 1
		if h.cursor < n:
			h.spawn_wait_t += h.queue[2 * h.cursor + 1]
	if h.cursor < n:
		h.spawn_wait_t -= 1


## The maximum health, in hundredths, of a creep of `kind_id` spawned on hollow `h` in its
## wave `wave`: the table's, grown hp_growth_pm a wave after the first and scaled by the
## hollow's seats (hp_by_seats_pm); (M7) in a Surge wave the wave it repeats grows it, and
## the Surge's hp_pm on top. Spawns take it, and the wave list shows it ahead.
static func health_c(m: SimMatch, h: SimRecords.SimHollow, kind_id: String, wave: int) -> int:
	var data: Dictionary = SimContent.CREEPS[kind_id]
	var growth := int(m.rules["hp_growth_pm"]) * maxi(0, SimUndertow.content_wave(m, wave) - 1)
	var by_seats: Array = m.rules["hp_by_seats_pm"]
	var seats_pm := int(by_seats[clampi(h.seats.size(), 1, by_seats.size()) - 1])
	var hp := int(data["hp_c"]) * (1000 + growth) * seats_pm / 1000000
	if SimUndertow.surge_of(m, wave) > 0:
		hp = hp * int((SimUndertow.rules_of(m)["surge"] as Dictionary)["hp_pm"]) / 1000
	return hp


## A creep of kind index `kind` at the Welling, with this wave's and this team's health
## (health_c). `sent_by` is the seat whose uncorked pack it is (0 for the wave's own).
static func spawn(m: SimMatch, h: SimRecords.SimHollow, kind: int, sent_by := 0) -> SimRecords.SimCreep:
	var kind_id: String = SimContent.CREEP_IDS[kind]
	var data: Dictionary = SimContent.CREEPS[kind_id]
	var c := SimRecords.SimCreep.new()
	c.id = m.new_id()
	c.hollow = h.id
	c.kind = kind_id
	c.max_hp_c = health_c(m, h, kind_id, h.wave)
	c.hp_c = c.max_hp_c
	c.armor_c = int(data["armor_c"]) if bool(m.rules.get("armor", true)) else 0
	c.speed_um_t = int(data["speed_um_t"])
	c.bounty = int(data["bounty"])
	c.toll = int(data["toll"])
	c.winged = bool(data.get("winged", false))
	c.boss = bool(data.get("boss", false))
	c.control_resist_pm = int(data.get("control_resist_pm", 0))
	c.sent_by = sent_by
	m.add_creep(c)
	var event := {"type": SimTypes.EV_SPAWN, "id": c.id, "hollow": h.id, "kind": kind_id}
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
static func check_clear(m: SimMatch, h: SimRecords.SimHollow) -> void:
	if h.phase != SimTypes.PHASE_WAVE or h.cursor < h.queue.size() / 2:
		return
	if m.creeps_on(h.id) > 0:
		return
	if m.duel and SimUndertow.holds(m, h):
		return
	var bonus_rule: Array = m.rules["clear_bonus"]
	var bonus := int(bonus_rule[0]) + int(bonus_rule[1]) * SimUndertow.content_wave(m, h.wave)
	for n in h.seats:
		m.add_gold(m.seat(n), bonus, "clear")
	_tithe(m, h)
	if m.duel:
		SimUndertow.pay_stipends(m, h)
	if h.wave >= m.last_wave():
		finish(m, h)
	else:
		open_window(m, h, false)
	m.push_event(
		{
			"type": SimTypes.EV_WAVE,
			"hollow": h.id,
			"wave": h.wave,
			"phase": h.phase,
			"cleared": true,
			"bonus": bonus
		}
	)
	if m.duel and h.phase == SimTypes.PHASE_PREP:
		SimUndertow.window_opened(m, h)


## A hollow that cleared its last wave is done: its team's clear tick is now (the race
## time counts from it, M6), and a race says so (EV_RACE "cleared").
static func finish(m: SimMatch, h: SimRecords.SimHollow) -> void:
	h.phase = SimTypes.PHASE_DONE
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
## coming back from the caretaker gets its controls back here.
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
		s.ready = false
		if s.state == SimTypes.SEAT_RETURNING:
			s.state = SimTypes.SEAT_PRESENT
			m.push_event({"type": SimTypes.EV_SEAT, "seat": s.seat, "state": s.state})
