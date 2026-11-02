## Stages a duel on the match scene for the duel's view scenarios (contract-m7.md §3) on
## Undertow's own preset (RULES.undertow, SimUndertow): me on the first hollow (or the
## second) against a caretaker rival of my Builder, through a LocalSequencer, as
## `scene.begin` starts any match, with the client's salts fixed so two runs commit alike.
##   {"eval": "resource('res://tests/ui/duel_stage.gd').start(scene)"}
## The rules play themselves: the Drift draws a window's packs when it opens for both
## hollows, the caretaker corks by its own policy and uncorks at uncork_after_t, lost lives
## earn Seawall charges, stipends grow at the uncorking. What a scenario stages goes through
## the logged setters only (Game.lives, Game.gold, Game.countdown and Game.debug's ops), so
## a replay reproduces it: to_window(w) moves both hollows' waves in the first window so
## the next wave played opens window w, breach(by) walks a sender's creeps to the Holdfast
## they are sent at.
extends RefCounted

const SimUndertowScript := preload("res://scripts/sim/sim_undertow.gd")


## A duel of my seat (`my_seat`, 1 or 2) playing `mine` against a caretaker playing `rival`;
## with `rival_caretaker` false the rival's seat is a present player who sends nothing (a
## mirror whose hollows play alike while neither builds).
static func start(
	scene: Node, my_seat := 1, seed_value := 1, mine := "lamplighter", rival := "lamplighter",
	rival_caretaker := true
) -> bool:
	var seats := [{"team": 0, "builder": mine}, {"team": 1, "builder": rival}]
	if my_seat == 2:
		seats = [{"team": 0, "builder": rival}, {"team": 1, "builder": mine}]
	if rival_caretaker:
		seats[2 - my_seat]["caretaker"] = true
	scene.call("begin", "undertow", seats, seed_value, LocalSequencer.new(2, my_seat), my_seat)
	Game.salt_source = fixed_salts(seed_value)
	return Game.is_duel() and Game.sim.duel and not Game.sim.race and Game.sim.hollows.size() == 2


## My seat plays its plan as the caretaker would (tests/bot.gd through the build controller,
## every few frames, no corks), so my hollow holds its waves like the rival's.
static func defend(scene: Node) -> bool:
	scene.set("_bot", load("res://tests/bot.gd").new())
	return scene.get("_bot") != null


## In the first window, before the first horn: both hollows' waves move to `window` - 2, so
## the wave the next horn sounds is `window` - 1 and its clear opens window `window` (the
## Drift draws it then), with `lives` on both Holdfasts to hold that wave undefended, and my
## Ready said (the caretaker says its own once it has played its window).
static func to_window(window: int, lives := 200) -> bool:
	if Game.sim.horn_tick >= 0 or window < 2:
		return false
	for h in Game.sim.hollows:
		Game.debug(SimTypes.DBG_WAVE, h.id, window - 2)
	for t in Game.sim.teams:
		Game.debug(SimTypes.DBG_LIVES, t.id, lives)
	return Game.command(SimTypes.CMD_READY, 1) >= 0


## Seat `seat`'s gold set to `gold`, a logged write (Game.debug's DBG_GOLD), so replays
## reproduce it. In window 2 a caretaker rival given gold so corks within the half second
## it next thinks: since the sends' pass tier I costs 45 and its fifth of what it holds
## (Caretaker.CORK_SHARE_PM) first pays for one in window 3, where at 30 it did in window 2.
static func gold_for(seat: int, gold: int) -> bool:
	return Game.debug(SimTypes.DBG_GOLD, seat, gold)


## Whether window `window` is open for both hollows and the Drift has drawn its packs.
static func in_window(window: int) -> bool:
	return Game.duel_window() == window and Game.cork_window()


## Whether the duel's wave `wave` runs (from the shared horn, on either hollow).
static func in_wave(wave: int) -> bool:
	return Game.duel_wave() and Game.sim.hollows[0].wave == wave and Game.sim.hollows[1].wave == wave


## The ids of the creeps on the road that seat `by` uncorked (sent_by), oldest first.
static func sent_creeps(by: int) -> Array:
	var out := []
	for c in Game.sim.creeps:
		if c.sent_by == by:
			out.append(c.id)
	return out


## Every creep seat `by` sent that walks now is set at the end of its road, so it reaches
## the Holdfast on the next tick: a breach. Returns how many.
static func breach(by: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.sent_by == by:
			Game.debug(SimTypes.DBG_CREEP_DIST, c.id, Game.sim.hollows[c.hollow].road.length_um)
			n += 1
	return n


## Every creep on hollow `hollow` is set at the end of its road (it leaks on the next tick),
## so the hollow clears its wave as soon as its spawns are out. Returns how many.
static func leak_all(hollow: int) -> int:
	var n := 0
	for c in Game.sim.creeps:
		if c.hollow == hollow:
			Game.debug(SimTypes.DBG_CREEP_DIST, c.id, Game.sim.hollows[hollow].road.length_um)
			n += 1
	return n


## Both Holdfasts go under on one tick (two lives writes before the next step).
static func fall_together() -> void:
	Game.debug(SimTypes.DBG_LIVES, 0, 0)
	Game.debug(SimTypes.DBG_LIVES, 1, 0)


## The session's results plate over the scene as main.gd shows it at a match's end, from
## the simulation's records and my outcome (without the session's state change).
static func show_results(scene: Node, names := ["Sascha", "Edda"]) -> ResultsPanel:
	var old := scene.get_node_or_null("ResultsPanel")
	if old:
		old.free()
	var shown := ResultsPanel.compute(Game.sim, names, Game.outcome(), {}, "undertow")
	var panel := ResultsPanel.new()
	scene.add_child(panel)
	panel.show_results(shown)
	return panel


## Salts that come out alike on every run (Game.salt_source): the n-th cork's is
## fixed_salt(seed, n). The real client draws them from Crypto; a test's two runs must commit
## alike, since --determinism compares state hashes and the bottles' commits are the match's.
static func fixed_salts(seed_value: int) -> Callable:
	var drawn := [0]
	return func() -> PackedByteArray:
		drawn[0] += 1
		return salt_bytes(seed_value, int(drawn[0]))


## The n-th fixed salt for `seed_value`: the first 8 bytes of SHA-256 over n, then the
## seed, each as 8 bytes big-endian.
static func salt_bytes(seed_value: int, n: int) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(16)
	bytes.encode_s64(0, seed_value)
	bytes.encode_s64(8, n)
	bytes.reverse()  # (encode_s64 writes little-endian; reversed, n leads, both big-endian)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	return ctx.finish().slice(0, 8)


## The n-th fixed salt's halves as an UNCORK carries them, [hi, lo].
static func fixed_salt(seed_value: int, n: int) -> Array:
	var salt := salt_bytes(seed_value, n)
	return [Game._i32(salt, 0), Game._i32(salt, 4)]


## Without the seam, a cork's salt is 8 bytes from Crypto, two never alike.
static func crypto_salts() -> bool:
	var kept: Callable = Game.salt_source
	Game.salt_source = Callable()
	var a := Game._new_salt()
	var b := Game._new_salt()
	Game.salt_source = kept
	return a.size() == 8 and b.size() == 8 and a != b


# ── Orders lost on their way (MatchClient._send with the link closed drops a CMD unheard) ──


## Whether the salts' file of match `match_id` for my seat is on this machine (Game.salt_match).
static func salts_kept(match_id: int) -> bool:
	return FileAccess.file_exists("user://duel/%d-%d.cfg" % [match_id, Game.seat])


## Drops my last command still waiting for its turn, as a link that closed under it would.
static func lose_last() -> bool:
	var waiting: Array = (Game.source as LocalSequencer).pending()
	for i in range(waiting.size() - 1, -1, -1):
		if int(waiting[i]["seat"]) == Game.seat:
			waiting.remove_at(i)
			return true
	return false


## Key 1 to 3 (slot 0 to 2) corks, and the CORK never reaches the turns.
static func cork_lost(scene: Node, slot: int) -> bool:
	return scene.controller.cork_slot(slot) and lose_last()


## Space uncorks, and the UNCORK never reaches the turns.
static func uncork_lost(scene: Node) -> bool:
	return scene.controller.press_space() and lose_last()


## F bursts a Seawall, and the SEAWALL never reaches the turns.
static func seawall_lost(scene: Node) -> bool:
	return scene.controller.seawall() and lose_last()


## The game is killed right after a cork goes out (key 1 to 3): its CORK reaches the turns,
## but nothing this game held does (its pending orders and Game's memory of the duel: the
## salts' file is what a game started again has).
static func cork_then_die(scene: Node, slot: int) -> bool:
	var sent: bool = scene.controller.cork_slot(slot)
	scene.controller.forget_pending()
	Game.forget_duel()
	return sent


## The game forgets its corks as one started again offline does (no salts' file): the
## bottles stand, but no salt here opens them.
static func forget_salts() -> void:
	var kept: Callable = Game.salt_source
	Game.forget_duel()
	Game.salt_source = kept


## A checkpoint of the match as another world may hold it after a RESYNC(desync): Game.sim
## serialized and loaded back, with seat `n`'s bottles numbered otherwise (each takes the
## next free id, as a world where an id went to something else first numbers them), the
## list kept in id order. Stand it as the scene's world and rebuild the views to attach it.
static func renumbered_checkpoint(n: int) -> SimMatch:
	var loaded := SimMatch.deserialize(Game.sim.serialize(), SimContent.rules(Game.sim.mode))
	for b in loaded.bottle_list:
		if b.seat == n:
			b.id = loaded.next_id
			loaded.next_id += 1
	loaded.bottle_list.sort_custom(func(a: SimRecords.SimBottle, b: SimRecords.SimBottle) -> bool: return a.id < b.id)
	return loaded


## A checkpoint `bytes` (Game.sim.serialize() earlier) loaded as another world may hold it
## after a RESYNC(desync): `ids_ahead` ids went to something else first there, so what its
## turns stand from now on is numbered that much higher than here.
static func loaded_checkpoint(bytes: PackedByteArray, ids_ahead := 0) -> SimMatch:
	var loaded := SimMatch.deserialize(bytes, SimContent.rules(Game.sim.mode))
	loaded.next_id += ids_ahead
	return loaded


## The simulation's record of bottle `id` (SimMatch.bottle_list), or null.
static func record(id: int) -> SimRecords.SimBottle:
	for b in Game.sim.bottle_list:
		if b.id == id:
			return b
	return null


## The pack (a CHECK_IDS id) bottle `id` holds if it was corked with salt 0, as the caretaker
## corks (SimUndertow.salt_zero_pack), else "".
static func salt_zero_pack(id: int) -> String:
	var b := record(id)
	var pack := SimUndertowScript.salt_zero_pack(Game.sim, b) if b != null else -1
	return SimContent.CHECK_IDS[pack] if pack >= 0 else ""


## The commitment the contract's bytes give (SimUndertow.commit), for checks.
static func commit(match_seed: int, seat: int, window: int, pack: int, hi: int, lo: int) -> Array:
	return SimUndertowScript.commit(match_seed, seat, window, pack, hi, lo)


## The commands of `type` seat `n` sent in the turn log so far, oldest first, each
## [turn, a, b, c].
static func sent(n: int, type: int) -> Array:
	var out := []
	var log_turns: Array = (Game.source as LocalSequencer).turns
	for t in log_turns.size():
		for cmd: Dictionary in log_turns[t]:
			if int(cmd["seat"]) == n and int(cmd["type"]) == type:
				out.append([t, int(cmd["a"]), int(cmd["b"]), int(cmd["c"])])
	return out


## What corking and uncorking sent from seat `n`, held to the contract's commitment: one
## line per problem, [] when every UNCORK reveals the salt its CORK committed to (the
## CORK's b and c are SimUndertow.commit over the seed, the seat, the window, the pack and
## that salt), no CORK carries the salt itself, and no two corks share a salt.
static func commit_problems(n: int) -> Array:
	var out := []
	var corks := sent(n, SimTypes.CMD_CORK)
	var uncorks := sent(n, SimTypes.CMD_UNCORK)
	if corks.is_empty() or uncorks.size() != corks.size():
		out.append("%d corks and %d uncorks were sent" % [corks.size(), uncorks.size()])
		return out
	var bottles := Game.bottles_of(n)
	if bottles.size() != corks.size():
		out.append("%d corks sent, %d bottles kept" % [corks.size(), bottles.size()])
		return out
	var salts := {}
	for i in corks.size():
		var cork: Array = corks[i]
		var open: Array = uncorks[i]
		# (the window each bottle was corked in, as the simulation keeps it, in cork order)
		var window := int(bottles[i]["window"])
		var want := commit(Game.sim.match_seed, n, window, int(open[1]), int(open[2]), int(open[3]))
		if [int(cork[2]), int(cork[3])] != want:
			out.append("cork %d's commit %s is not the contract's %s for window %d, pack %d" % [i, [cork[2], cork[3]], want, window, open[1]])
		if [int(cork[2]), int(cork[3])] == [int(open[2]), int(open[3])]:
			out.append("cork %d carried its salt" % i)
		var key := "%d:%d" % [open[2], open[3]]
		if salts.has(key):
			out.append("cork %d reused a salt" % i)
		salts[key] = true
		var tier := int(SimUndertowScript.tiers_in(Game.sim, window)[0])
		if int(cork[1]) != tier:
			out.append("cork %d named tier %d, not %d" % [i, cork[1], tier])
		if str(bottles[i].get("pack", "")) != SimContent.CHECK_IDS[int(open[1])]:
			out.append("bottle %d holds %s, not the pack its UNCORK revealed" % [i, bottles[i].get("pack", "")])
	return out


# ── A seat no client here plays (a mirror's present rival: start(..., false)) ──


## Seat `n` corks `check` with the salt [hi, lo], as its own game would send it: CORK(tier,
## commit) through the sequencer as that seat. Returns its seq, or -1.
static func cork_as(n: int, check: String, hi := 5, lo := 6) -> int:
	var sim := Game.sim
	var window := sim.hollows[sim.seat(n).hollow].wave + 1
	var c := commit(sim.match_seed, n, window, SimContent.CHECK_IDS.find(check), hi, lo)
	var tier := int(SimUndertowScript.tiers_in(sim, window)[0])
	return (Game.source as LocalSequencer).submit_as(n, SimTypes.CMD_CORK, tier, int(c[0]), int(c[1]))


## Seat `n` says Ready, as its own game would.
static func ready_as(n: int) -> int:
	return (Game.source as LocalSequencer).submit_as(n, SimTypes.CMD_READY, 1)


# ── A networked duel (tests/net/loopback_main.gd: my window and a headless partner) ──


## The loopback's partner (seat 2 on the wire's seat 1) corks pack `check` with a salt it
## keeps: CORK(tier, commit) through its own MatchClient. Returns [hi, lo], the salt.
static func partner_cork(loop: Node, check: String, hi := 11, lo := 22) -> Array:
	var partner: MatchClient = loop.get("partner")
	var sim := partner.sim
	var window := sim.hollows[sim.seat(partner.seat).hollow].wave + 1
	var pack := SimContent.CHECK_IDS.find(check)
	var c := commit(sim.match_seed, partner.seat, window, pack, hi, lo)
	var tier := int(SimUndertowScript.tiers_in(sim, window)[0])
	partner.cmd(SimTypes.CMD_CORK, tier, int(c[0]), int(c[1]))
	return [hi, lo]


## The loopback's partner uncorks pack `check` with the salt it corked it with.
static func partner_uncork(loop: Node, check: String, hi := 11, lo := 22) -> bool:
	var partner: MatchClient = loop.get("partner")
	return partner.cmd(SimTypes.CMD_UNCORK, SimContent.CHECK_IDS.find(check), hi, lo) >= 0


## How many of the moments said this match (Game.team_notices: a teammate's, a rival's)
## begin with `prefix`.
static func said(prefix: String) -> int:
	var n := 0
	for text: String in Game.team_notices:
		if text.begins_with(prefix):
			n += 1
	return n


## The loopback's partner says Ready.
static func partner_ready(loop: Node) -> bool:
	var partner: MatchClient = loop.get("partner")
	return partner.cmd(SimTypes.CMD_READY, 1) >= 0
