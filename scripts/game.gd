## The local seat's facade over the match, and the display tables (design 6.4).
##
## Autoloaded as `Game`. The rules run in the simulation (scripts/sim); `Game` shows the
## local seat's side of it: `gold` is mine, `lives` my team's, and `wave`, `state`,
## `countdown` and `kills` come from the simulation, with the same signals as before so
## the HUD reads one truth. Commands go out through `command()`; nothing here changes the
## match directly except the debug setters below.
##
## In an offline match the setters scenarios use (Game.gold = 300, Game.countdown = 0.1,
## Game.wave, Game.lives, spend, earn, lose_lives and a creep view's distance or speed)
## write into the local simulation at once and are logged with their tick, so a replay of
## the turn log reproduces them. A networked match refuses them.
##
## TOWERS and CREEPS hold names, keys, models and icons keyed by the simulation's ids;
## the numbers come from SimContent.
extends Node

signal gold_changed(gold: int)
signal lives_changed(lives: int)
signal wave_changed(wave: int)
signal state_changed(state: int)
signal announced(text: String)
## A short notice for the player, such as a refused order; not a ceremony like a wave title.
signal noticed(text: String)
## A command of mine ran (accepted) or was refused; `seq` is what command() returned.
signal settled(seq: int, accepted: bool)
## Someone's Ready changed, or a seat changed hands.
signal ready_changed
## A tower was built, upgraded or sold, by anyone.
signal towers_changed

enum State { PREP, WAVE, WON, LOST }

const TOWERS := {
	"arrow":
	{
		"name": "Arrow Tower",
		"hotkey": "A",
		"description": "Quick bolts at the creep closest to the hearth.",
		"projectile": "arrow",
		"model": "res://models/towers/arrow_tower.glb",
		"model_2": "res://models/towers/arrow_tower_2.glb",
		"pennant": Vector3(0.016, 2.27, 0),
		"muzzle": Vector3(0, 1.08, 0.12),
		"icon": "res://ui/icons/arrow_tower.png",
	},
	"cannon":
	{
		"name": "Cannon Tower",
		"hotkey": "C",
		"description": "Slow shells that burst and hit every creep nearby.",
		"projectile": "cannonball",
		"model": "res://models/towers/cannon_tower.glb",
		"model_2": "res://models/towers/cannon_tower_2.glb",
		"head": "res://models/towers/cannon_head.glb",
		"head_height": 0.77,
		"muzzle": Vector3(0, 1.04, 0),
		"icon": "res://ui/icons/cannon_tower.png",
	},
	"frost":
	{
		"name": "Frost Spire",
		"hotkey": "F",
		"description": "Ice shards that slow creeps for two seconds.",
		"projectile": "frost_shard",
		"model": "res://models/towers/frost_tower.glb",
		"model_2": "res://models/towers/frost_tower_2.glb",
		"head": "res://models/towers/frost_head.glb",
		"head_height": 1.42,
		"muzzle": Vector3(0, 1.6, 0),
		"icon": "res://ui/icons/frost_tower.png",
	},
}

const CREEPS := {
	"gourdling":
	{
		"name": "Gourdling",
		"model": "res://models/creeps/gourdling.glb",
		"stride": 1.0,
		"scale": 1.5,
		"color": Color("#d9772b"),
	},
	"scuttler":
	{
		"name": "Scuttler",
		"model": "res://models/creeps/scuttler.glb",
		"stride": 0.6075,
		"scale": 1.5,
		"color": Color("#6e4a82"),
	},
	"thornback":
	{
		"name": "Thornback",
		"model": "res://models/creeps/thornback.glb",
		"stride": 0.859,
		"scale": 1.35,
		"color": Color("#6b4a34"),
	},
	"hollow_king":
	{
		"name": "The Hollow King",
		"model": "res://models/creeps/hollow_king.glb",
		"stride": 0.756,
		"scale": 1.6,
		"color": Color("#b5541f"),
	},
}

const NOTICES := {
	SimTypes.REFUSE_CANNOT_BUILD_THERE: "Cannot build there",
	SimTypes.REFUSE_NOT_ENOUGH_GOLD: "Not enough gold",
	SimTypes.REFUSE_NOT_YOURS: "That tower is not yours",
	SimTypes.REFUSE_ALREADY_FORKED: "Already upgraded",
	SimTypes.REFUSE_NO_SUCH_TOWER: "That tower is gone",
	SimTypes.REFUSE_CARETAKEN: "The caretaker hands back at the next build window",
	SimTypes.REFUSE_RATE_LIMITED: "Too many signals",
}

## The match this client shows, the source its turns come from, and my seat in it.
var sim: SimMatch
var source: TurnSource
var seat := 1
## Gold my commands still waiting for their turn will spend: kept back when deciding
## what I can afford.
var pending_gold := 0

var gold: int:
	get:
		return _seat().gold if sim else start_gold()
	set(value):
		if debug(SimTypes.DBG_GOLD, seat, value):
			gold_changed.emit(gold)

var lives: int:
	get:
		return _team().lives if sim else max_lives()
	set(value):
		if sim and debug(SimTypes.DBG_LIVES, _seat().team, maxi(0, value)):
			lives_changed.emit(lives)

## 1-based index of the current or last wave; 0 before the first.
var wave: int:
	get:
		return _hollow().wave if sim else 0
	set(value):
		if sim and debug(SimTypes.DBG_WAVE, _seat().hollow, value):
			wave_changed.emit(wave)

var state: State:
	get:
		if sim == null:
			return State.PREP
		match _hollow().phase:
			SimTypes.PHASE_WAVE:
				return State.WAVE
			SimTypes.PHASE_DONE:
				return State.WON
			SimTypes.PHASE_FALLEN:
				return State.LOST
		return State.PREP
	set(_value):
		push_warning("Game.state follows the simulation; it cannot be set")

## Seconds until the next wave while in PREP.
var countdown: float:
	get:
		return _hollow().countdown_t / float(SimTypes.TICKS_PER_SECOND) if sim else 0.0
	set(value):
		if sim:
			debug(SimTypes.DBG_COUNTDOWN, _seat().hollow, ceili(value * SimTypes.TICKS_PER_SECOND))

## Creeps the team has killed.
var kills: int:
	get:
		return _team().kills if sim else 0
	set(value):
		if sim:
			debug(SimTypes.DBG_KILLS, _seat().team, value)


func attach(match_sim: SimMatch, turns: TurnSource, my_seat: int) -> void:
	sim = match_sim
	source = turns
	seat = my_seat
	pending_gold = 0
	gold_changed.emit(gold)
	lives_changed.emit(lives)
	wave_changed.emit(wave)
	state_changed.emit(state)


func detach() -> void:
	sim = null
	source = null
	pending_gold = 0


## Sends a command from my seat for the next turn; returns its sequence number, or -1
## (command_refusal() says why).
func command(type: int, a := 0, b := 0, c := 0) -> int:
	if source == null:
		return -1
	return source.submit(type, a, b, c)


## Whether my orders go out now: always offline; networked only while the match runs and
## its link holds (not before START, not after MATCH_END or a lost link).
func accepts_commands() -> bool:
	return source != null and source.accepts_commands()


## Whether an order given now would go out (accepts_commands(), and room in the command
## bucket online).
func can_command() -> bool:
	return source != null and source.can_submit()


## Why an order given now goes nowhere, for the notice ("The match has not started", "No
## link to the server", "Not so fast"); "" when it would go out.
func command_refusal() -> String:
	if source == null:
		return "The match has not started"
	return source.refusal()


## Writes a scenario setter into the local match at once and logs it with its tick.
## Returns false where that is not allowed (no match, or a networked one).
func debug(op: int, a: int, b := 0, c := 0) -> bool:
	if sim == null or source == null or not source.allows_debug():
		push_warning("debug writes only work in an offline match")
		return false
	source.record_debug(sim.tick, op, a, b, c)
	sim.debug(op, a, b, c)
	return true


## Reacts to the simulation's events for my seat, my team and my hollow.
func handle(events: Array) -> void:
	if sim == null:
		return
	for e: Dictionary in events:
		match int(e["type"]):
			SimTypes.EV_GOLD:
				if e["seat"] == seat:
					gold_changed.emit(int(e["gold"]))
			SimTypes.EV_LIVES:
				if e["team"] == _seat().team:
					lives_changed.emit(int(e["lives"]))
			SimTypes.EV_WAVE:
				if e["hollow"] == _seat().hollow:
					_on_wave(e)
			SimTypes.EV_READY, SimTypes.EV_SEAT:
				if e.get("seat", 0) == seat and e.has("seq"):
					settled.emit(int(e["seq"]), true)
				ready_changed.emit()
			SimTypes.EV_BUILT, SimTypes.EV_FORKED, SimTypes.EV_SOLD:
				if e["seat"] == seat and int(e["seq"]) > 0:
					settled.emit(int(e["seq"]), true)
				towers_changed.emit()
			SimTypes.EV_REJECTED:
				if e["seat"] == seat:
					_refused(e)


func _on_wave(e: Dictionary) -> void:
	if e.get("start", false):
		wave_changed.emit(wave)
		state_changed.emit(state)
		announce(_wave_title(int(e["wave"])))
		Sfx.play("wave", -6.0)
		return
	match int(e["phase"]):
		SimTypes.PHASE_PREP:
			wave_changed.emit(wave)
			state_changed.emit(state)
			if e.get("cleared", false):
				announce("Wave %d cleared · +%d gold" % [int(e["wave"]), int(e["bonus"])])
		SimTypes.PHASE_WAVE:
			wave_changed.emit(wave)
		SimTypes.PHASE_DONE:
			state_changed.emit(State.WON)
			announce("The hearth burns on. Victory!")
			Sfx.play("victory")
		SimTypes.PHASE_FALLEN:
			state_changed.emit(State.LOST)
			announce("The hearth has gone dark")
			Sfx.play("defeat")


func _wave_title(number: int) -> String:
	if number == total_waves():
		return "Final wave · The Hollow King"
	var first: String = wave_groups(number - 1)[0]["creep"]
	return "Wave %d · %s" % [number, CREEPS[first]["name"]]


func _refused(e: Dictionary) -> void:
	settled.emit(int(e["seq"]), false)
	var reason: int = e["reason"]
	if reason == SimTypes.REFUSE_WRONG_PHASE and int(e["cmd"]) == SimTypes.CMD_READY:
		return  # the horn had already sounded
	Sfx.play("error")
	notice(str(NOTICES.get(reason, "Not now")))


# ── Questions the HUD and the input ask ──


func total_waves() -> int:
	return sim.total_waves() if sim else 0


## Wave `index` (0-based) as groups {"creep", "count"}.
func wave_groups(index: int) -> Array:
	if sim == null or index < 0 or index >= sim.waves.size():
		return []
	return sim.waves[index]


func can_afford(cost: int) -> bool:
	return gold - pending_gold >= cost


func start_gold() -> int:
	return int(SimContent.RULES["classic"]["start_gold"])


func max_lives() -> int:
	return int(sim.rules["lives"]) if sim else int(SimContent.RULES["classic"]["lives"])


## Takes gold at once (a scenario setter); false when there is not enough.
func spend(cost: int) -> bool:
	if gold < cost:
		return false
	gold = gold - cost
	return true


func earn(amount: int) -> void:
	gold = gold + amount


func lose_lives(amount: int) -> void:
	if state == State.LOST or state == State.WON:
		return
	lives = maxi(0, lives - amount)


func announce(text: String) -> void:
	announced.emit(text)


func notice(text: String) -> void:
	noticed.emit(text)


## Creeps still to come this wave plus those on the road.
func creeps_left() -> int:
	if sim == null:
		return 0
	return sim.spawns_left(_seat().hollow) + sim.creeps_on(_seat().hollow)


## Spawns of this wave still to come.
func spawns_left() -> int:
	return sim.spawns_left(_seat().hollow) if sim else 0


## Gold an early horn pays each seat now.
func early_gold() -> int:
	return sim.early_gold(_seat().hollow) if sim else 0


func is_ready() -> bool:
	return sim != null and _seat().ready


## [ready seats, seats] on my hollow.
func ready_count() -> Array:
	return sim.ready_count(_seat().hollow) if sim else [0, 1]


func seat_count() -> int:
	return sim.seats.size() if sim else 1


## Towers standing on my hollow, everyone's.
func tower_count() -> int:
	if sim == null:
		return 0
	var hollow := _seat().hollow
	return sim.towers.filter(func(t: SimRecords.SimTower) -> bool: return t.hollow == hollow).size()


func sell_share() -> int:
	return int(sim.rules["sell_pm"]) if sim else int(SimContent.RULES["classic"]["sell_pm"])


## A tower's numbers at a level for people: damage, range in tiles, cooldown in seconds,
## splash, slow as a fraction, its cost, and the display table's names and models.
func tower_stats(kind: String, level: int) -> Dictionary:
	var stats: Dictionary = TOWERS[kind].duplicate()
	var sim_stats := SimContent.tower_stats(kind, 0 if level >= 2 else -1)
	stats["cost"] = int(sim_stats["cost"])
	stats["damage"] = sim_stats["dmg_c"] / 100.0
	stats["range"] = sim_stats["range_mm"] / 1000.0
	stats["cooldown"] = sim_stats["cd_t"] / float(SimTypes.TICKS_PER_SECOND)
	if int(sim_stats.get("splash_mm", 0)) > 0:
		stats["splash"] = sim_stats["splash_mm"] / 1000.0
	if int(sim_stats.get("slow_pm", 0)) > 0:
		stats["slow"] = sim_stats["slow_pm"] / 1000.0
		stats["slow_time"] = sim_stats["slow_t"] / float(SimTypes.TICKS_PER_SECOND)
	return stats


func tower_cost(kind: String) -> int:
	return int(SimContent.TOWERS[kind]["cost"])


func fork_cost(kind: String) -> int:
	return int(SimContent.TOWERS[kind]["fork_cost"])


## The kit slot (0 to 2) my Builder places `kind` from, or -1.
func slot_of(kind: String) -> int:
	var builder := _seat().builder if sim else "lamplighter"
	return (SimContent.BUILDERS[builder]["towers"] as Array).find(kind)


func _seat() -> SimRecords.SimSeat:
	return sim.seat(seat)


func _team() -> SimRecords.SimTeam:
	return sim.teams[_seat().team]


func _hollow() -> SimRecords.SimHollow:
	return sim.hollows[_seat().hollow]
