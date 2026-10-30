## The canonical byte form of a match: every field that decides what happens next, in id
## order, big-endian. It is the checkpoint a reconnecting client loads and what the state
## hash covers. Numbers that come from the content tables (a tower's damage, its road
## stretches) are rebuilt on decode, not stored.
class_name SimCodec
extends RefCounted

const MAGIC := 0x47485331  # "GHS1"


static func encode(m: SimMatch) -> PackedByteArray:
	var b := StreamPeerBuffer.new()
	b.big_endian = true
	b.put_u32(MAGIC)
	b.put_u16(SimContent.SIM_VERSION)
	b.put_u8(SimContent.MODE_IDS.find(m.mode))
	b.put_u32(m.tick)
	b.put_u32(m.match_seed)
	b.put_u32(m.rng.state)
	b.put_u32(m.next_id)
	b.put_32(m.turn_applied)
	b.put_u8((1 if m.over else 0) | (2 if m.aborted else 0))
	b.put_u8(m.teams.size())
	for t in m.teams:
		b.put_32(t.lives)
		b.put_u32(t.kills)
		b.put_32(t.clear_tick)
	b.put_u8(m.hollows.size())
	for h in m.hollows:
		b.put_u8(h.team)
		b.put_u8(h.phase)
		b.put_u16(h.wave)
		b.put_32(h.countdown_t)
		b.put_u32(h.window_tick)
		b.put_u16(h.cursor)
		b.put_32(h.spawn_wait_t)
		b.put_u16(h.queue.size())
		for v in h.queue:
			b.put_32(v)
	b.put_u8(m.seats.size())
	for s in m.seats:
		b.put_u8(s.team)
		b.put_u8(SimContent.BUILDER_IDS.find(s.builder))
		b.put_32(s.gold)
		b.put_u8(1 if s.ready else 0)
		b.put_u8(s.state)
		b.put_u32(s.kills)
		b.put_64(s.damage_c)
		b.put_64(s.help_c)
		b.put_u16(s.towers)
		b.put_u16(s.forks)
		b.put_u16(s.plan_cursor)
		b.put_u8(s.signal_ticks.size())
		for v in s.signal_ticks:
			b.put_u32(v)
	b.put_u16(m.towers.size())
	for t in m.towers:
		b.put_u32(t.id)
		b.put_u8(t.owner)
		b.put_u8(t.hollow)
		b.put_u8(t.x)
		b.put_u8(t.z)
		b.put_u8(SimContent.TOWER_IDS.find(t.kind))
		b.put_8(t.branch)
		b.put_32(t.invested)
		b.put_u32(t.cooldown_until)
		b.put_u32(t.target)
		b.put_u32(t.kills)
		b.put_u32(t.shots)
		b.put_32(t.haste_pm)
		b.put_u8(t.haste_seat)
	b.put_u16(m.creeps.size())
	for c in m.creeps:
		b.put_u32(c.id)
		b.put_u8(c.hollow)
		b.put_u8(SimContent.CREEP_IDS.find(c.kind))
		b.put_32(c.dist_um)
		b.put_32(c.hp_c)
		b.put_32(c.max_hp_c)
		b.put_32(c.armor_c)
		b.put_32(c.speed_um_t)
		b.put_32(c.bounty)
		b.put_32(c.toll)
		b.put_u8((1 if c.winged else 0) | (2 if c.boss else 0))
		b.put_32(c.control_resist_pm)
		b.put_32(c.slow_pm)
		b.put_u32(c.slow_until)
		b.put_u8(c.slow_seat)
		b.put_u32(c.stun_until)
		b.put_u32(c.stun_immune_until)
		b.put_u8(c.stun_seat)
		b.put_32(c.mark_pm)
		b.put_u32(c.mark_until)
		b.put_u8(c.mark_seat)
		b.put_32(c.crack_c)
		b.put_u8(c.crack_seat)
		b.put_u8(c.sent_by)
	b.put_u16(m.shots.size())
	for s in m.shots:
		b.put_u32(s.id)
		b.put_u32(s.tower)
		b.put_u8(s.seat)
		b.put_u8(s.hollow)
		b.put_u8(SimContent.TOWER_IDS.find(s.kind))
		b.put_u32(s.target)
		b.put_u32(s.fire_tick)
		b.put_u32(s.land_tick)
		b.put_32(s.land_dist_um)
		b.put_32(s.dmg_c)
		b.put_32(s.splash_mm)
		b.put_32(s.slow_pm)
		b.put_32(s.slow_t)
		b.put_32(s.pierce_c)
	_encode_m2(b, m)
	return b.data_array


## M2's fields (an Owl's Eye's marked creeps, a bouncing strike's chain, the slows
## waiting under a creep's applying one) follow in a block of their own, and only when
## one of them is away from its default: a match without them, every classic match among
## them, keeps the bytes and the state hashes it had in M1
## (contract_ids_keep_state_hashes). Records are named by their index in their list,
## which is in id order.
static func _encode_m2(b: StreamPeerBuffer, m: SimMatch) -> void:
	var eyes := PackedInt32Array()
	for i in m.towers.size():
		if not m.towers[i].marked.is_empty():
			eyes.append(i)
	var hops := PackedInt32Array()
	for i in m.shots.size():
		var s := m.shots[i]
		if s.bounce != 0 or s.bounces != 0 or s.bounce_mm != 0 or s.from_creep != 0 or not s.struck.is_empty():
			hops.append(i)
	var slowed := PackedInt32Array()
	for i in m.creeps.size():
		if not m.creeps[i].slow_next.is_empty():
			slowed.append(i)
	if eyes.is_empty() and hops.is_empty() and slowed.is_empty():
		return
	b.put_u16(eyes.size())
	for i in eyes:
		var t := m.towers[i]
		b.put_u16(i)
		b.put_u8(t.marked.size())
		for id in t.marked:
			b.put_u32(id)
	b.put_u16(hops.size())
	for i in hops:
		var s := m.shots[i]
		b.put_u16(i)
		b.put_u8(s.bounce)
		b.put_u8(s.bounces)
		b.put_32(s.bounce_mm)
		b.put_u32(s.from_creep)
		b.put_u8(s.struck.size())
		for id in s.struck:
			b.put_u32(id)
	b.put_u16(slowed.size())
	for i in slowed:
		var c := m.creeps[i]
		b.put_u16(i)
		@warning_ignore("integer_division")
		b.put_u8(c.slow_next.size() / 3)
		var k := 0
		while k < c.slow_next.size():
			b.put_32(c.slow_next[k])
			b.put_u32(c.slow_next[k + 1])
			b.put_u8(c.slow_next[k + 2])
			k += 3


static func _decode_m2(b: StreamPeerBuffer, m: SimMatch) -> void:
	if b.get_position() >= b.get_size():
		return
	var eye_count := b.get_u16()
	for k in eye_count:
		var t := m.towers[b.get_u16()]
		var n := b.get_u8()
		for j in n:
			t.marked.append(b.get_u32())
	var hop_count := b.get_u16()
	for k in hop_count:
		var s := m.shots[b.get_u16()]
		s.bounce = b.get_u8()
		s.bounces = b.get_u8()
		s.bounce_mm = b.get_32()
		s.from_creep = b.get_u32()
		var n := b.get_u8()
		for j in n:
			s.struck.append(b.get_u32())
	var slowed_count := b.get_u16()
	for k in slowed_count:
		var c := m.creeps[b.get_u16()]
		var n := b.get_u8()
		for j in n:
			c.slow_next.append(b.get_32())
			c.slow_next.append(b.get_u32())
			c.slow_next.append(b.get_u8())


## A match from its bytes and the rules it was made with; null when the bytes are not a
## checkpoint of this simulation version.
static func decode(bytes: PackedByteArray, rules: Dictionary, text := "") -> SimMatch:
	var b := StreamPeerBuffer.new()
	b.big_endian = true
	b.data_array = bytes
	if b.get_u32() != MAGIC or b.get_u16() != SimContent.SIM_VERSION:
		push_error("not a checkpoint of simulation version %d" % SimContent.SIM_VERSION)
		return null
	b.get_u8()  # the mode; the rules passed in decide
	var m := SimMatch.new()
	m.tick = b.get_u32()
	var start_seed := b.get_u32()
	m.setup(rules, start_seed, text)
	m.rng.state = b.get_u32()
	m.next_id = b.get_u32()
	m.turn_applied = b.get_32()
	var flags := b.get_u8()
	m.over = (flags & 1) != 0
	m.aborted = (flags & 2) != 0
	var team_count := b.get_u8()
	if team_count != m.teams.size():
		push_error("checkpoint has %d teams, the rules %d" % [team_count, m.teams.size()])
		return null
	for t in m.teams:
		t.lives = b.get_32()
		t.kills = b.get_u32()
		t.clear_tick = b.get_32()
	b.get_u8()
	for h in m.hollows:
		h.team = b.get_u8()
		h.phase = b.get_u8()
		h.wave = b.get_u16()
		h.countdown_t = b.get_32()
		h.window_tick = b.get_u32()
		h.cursor = b.get_u16()
		h.spawn_wait_t = b.get_32()
		var queue_size := b.get_u16()
		h.queue = PackedInt32Array()
		for i in queue_size:
			h.queue.append(b.get_32())
	var seat_count := b.get_u8()
	for i in seat_count:
		var team := b.get_u8()
		var builder: String = SimContent.BUILDER_IDS[b.get_u8()]
		var s := m.add_seat(team, builder, SimTypes.SEAT_PRESENT)
		s.gold = b.get_32()
		s.ready = b.get_u8() != 0
		s.state = b.get_u8()
		s.kills = b.get_u32()
		s.damage_c = b.get_64()
		s.help_c = b.get_64()
		s.towers = b.get_u16()
		s.forks = b.get_u16()
		s.plan_cursor = b.get_u16()
		var signal_count := b.get_u8()
		for k in signal_count:
			s.signal_ticks.append(b.get_u32())
	var tower_count := b.get_u16()
	for i in tower_count:
		var t := SimRecords.SimTower.new()
		t.id = b.get_u32()
		t.owner = b.get_u8()
		t.hollow = b.get_u8()
		t.x = b.get_u8()
		t.z = b.get_u8()
		t.kind = SimContent.TOWER_IDS[b.get_u8()]
		t.branch = b.get_8()
		t.invested = b.get_32()
		t.cooldown_until = b.get_u32()
		t.target = b.get_u32()
		t.kills = b.get_u32()
		t.shots = b.get_u32()
		t.haste_pm = b.get_32()
		t.haste_seat = b.get_u8()
		m.towers.append(t)
	var creep_count := b.get_u16()
	for i in creep_count:
		var c := SimRecords.SimCreep.new()
		c.id = b.get_u32()
		c.hollow = b.get_u8()
		c.kind = SimContent.CREEP_IDS[b.get_u8()]
		c.dist_um = b.get_32()
		c.hp_c = b.get_32()
		c.max_hp_c = b.get_32()
		c.armor_c = b.get_32()
		c.speed_um_t = b.get_32()
		c.bounty = b.get_32()
		c.toll = b.get_32()
		var creep_flags := b.get_u8()
		c.winged = (creep_flags & 1) != 0
		c.boss = (creep_flags & 2) != 0
		c.control_resist_pm = b.get_32()
		c.slow_pm = b.get_32()
		c.slow_until = b.get_u32()
		c.slow_seat = b.get_u8()
		c.stun_until = b.get_u32()
		c.stun_immune_until = b.get_u32()
		c.stun_seat = b.get_u8()
		c.mark_pm = b.get_32()
		c.mark_until = b.get_u32()
		c.mark_seat = b.get_u8()
		c.crack_c = b.get_32()
		c.crack_seat = b.get_u8()
		c.sent_by = b.get_u8()
		m.creeps.append(c)
	var shot_count := b.get_u16()
	for i in shot_count:
		var s := SimRecords.SimShot.new()
		s.id = b.get_u32()
		s.tower = b.get_u32()
		s.seat = b.get_u8()
		s.hollow = b.get_u8()
		s.kind = SimContent.TOWER_IDS[b.get_u8()]
		s.target = b.get_u32()
		s.fire_tick = b.get_u32()
		s.land_tick = b.get_u32()
		s.land_dist_um = b.get_32()
		s.dmg_c = b.get_32()
		s.splash_mm = b.get_32()
		s.slow_pm = b.get_32()
		s.slow_t = b.get_32()
		s.pierce_c = b.get_32()
		m.shots.append(s)
	_decode_m2(b, m)
	m.reindex()
	return m
