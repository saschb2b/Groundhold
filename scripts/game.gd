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
## TOWERS and CREEPS hold names, models and icons keyed by the simulation's ids (TOWERS
## by tower form: a base and each of its branches); the numbers come from SimContent
## (form_stats()). CHECKS, ROLES, BUILDERS and PERKS do the same for SimContent's check,
## role, Builder and perk ids, and CARD_KEYS names the command card's keys: the M2/M3
## contract (docs/design/contract-m2m3.md) fixes every key and path here. Art another
## track has not painted yet loads as a placeholder through icon().
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

## The command card's six slots, top row then bottom row, with the same keys for every
## Builder (design 5.7, positional): Q, W, E place the kit's towers, or choose branch A
## and branch B on a selected, unforked tower of your own; A signals, S sells, D is
## Ready (N and Space too). The HUD and the build controller read these.
const CARD_KEYS := ["Q", "W", "E", "A", "S", "D"]
## A fork branch's mark in the tooltips and on the Builders screen's kit plate (the
## design's wireframe draws an arrow; the console's fonts carry this one).
const FORK_MARK := "›"
const CARD_KEYCODES := [KEY_Q, KEY_W, KEY_E, KEY_A, KEY_S, KEY_D]
const ICON_DIR := "res://ui/icons/"
## The Signal command's icon (design 3.7): a pennant over the ring a signal draws on the
## ground, from models/ui/signal_pennant.glb framed by icons.py like the card's others.
const SIGNAL_ICON := "res://ui/icons/signal.png"

## Every tower form (SimContent.TOWER_IDS) has at least "name" and "icon"; a base also
## "description" (its tooltip line), a branch "gain" (a few words on what the fork
## changes, as the Builders screen lists it). The view's keys (Tower, Projectile):
##   model        the form's building; a fork swaps it for the branch's
##   head         a part on top that moves: "turn" toward the target (a gun, a ballista,
##                a telescope) or "spin" (head_motion: a frost crystal); seated at
##                head_height and drawn at head_scale
##   bore         where a shot leaves the head, in the head's own space (its front is +Z)
##   muzzle       where a shot leaves a tower without a turning head, over its cell
##   recoil       how far the head kicks back when it fires
##   projectile   the shot's model (Projectile.MODELS), at projectile_scale; a tower that
##                only marks has none
##   sound        [Sfx name, volume in dB] when it fires (the Owl's Eye: when it marks)
##   flash        the muzzle's light and sparks, [colour, size]; bows and birds have none
##   pennant      where the pennant pole stands on the model
##   shards       ice shards circling a spinning head
const TOWERS := {
	"arrow":
	{
		"name": "Arrow Tower",
		"description": "Quick bolts at the creep closest to the Holdfast.",
		"icon": "res://ui/icons/arrow_tower.png",
		"model": "res://models/towers/arrow_tower.glb",
		"pennant": Vector3(0.016, 2.27, 0),
		"muzzle": Vector3(0, 1.08, 0.12),
		"projectile": "arrow",
		"sound": ["arrow", -6.0],
		"flash": [Color(1.0, 0.9, 0.6), 0.6],
	},
	"cannon":
	{
		"name": "Cannon Tower",
		"description": "Slow shells that burst and hit every creep nearby.",
		"icon": "res://ui/icons/cannon_tower.png",
		"model": "res://models/towers/cannon_tower.glb",
		"head": "res://models/towers/cannon_head.glb",
		"head_height": 0.77,
		"bore": Vector3(0, 0.27, 0.36),
		"recoil": 0.07,
		"projectile": "cannonball",
		"sound": ["cannon", -3.0],
		"flash": [Color(1.0, 0.7, 0.3), 1.4],
	},
	"frost":
	{
		"name": "Frost Spire",
		"description": "Ice shards that slow creeps for two seconds.",
		"icon": "res://ui/icons/frost_tower.png",
		"model": "res://models/towers/frost_tower.glb",
		"head": "res://models/towers/frost_head.glb",
		"head_height": 1.42,
		"head_motion": "spin",
		"shards": 3,
		"muzzle": Vector3(0, 1.6, 0),
		"projectile": "frost_shard",
		"sound": ["frost", -6.0],
		"flash": [Color(0.6, 0.9, 1.0), 0.8],
	},
	"longbow_loft":
	{
		"name": "Longbow Loft",
		"gain": "faster, harder bolts",
		"icon": "res://ui/icons/longbow_loft.png",
		"model": "res://models/towers/arrow_tower_2.glb",
		"pennant": Vector3(0.016, 2.27, 0),
		"muzzle": Vector3(0, 1.08, 0.12),
		"projectile": "arrow",
		"sound": ["arrow", -6.0],
		"flash": [Color(1.0, 0.9, 0.6), 0.6],
	},
	"skyward_loft":
	{
		"name": "Skyward Loft",
		"gain": "reaches the sky",
		"icon": "res://ui/icons/skyward_loft.png",
		"model": "res://models/towers/skyward_loft.glb",
		"muzzle": Vector3(0, 1.46, 0.26),
		"projectile": "arrow",
		"sound": ["arrow", -6.0],
		"flash": [Color(0.85, 0.93, 1.0), 0.6],
	},
	"great_cannon":
	{
		"name": "Great Cannon",
		"gain": "bigger blast",
		"icon": "res://ui/icons/great_cannon.png",
		"model": "res://models/towers/cannon_tower_2.glb",
		"head": "res://models/towers/cannon_head.glb",
		"head_height": 0.77,
		"head_scale": 1.12,
		"bore": Vector3(0, 0.27, 0.36),
		"recoil": 0.08,
		"projectile": "cannonball",
		"sound": ["cannon", -3.0],
		"flash": [Color(1.0, 0.7, 0.3), 1.6],
	},
	"iron_mortar":
	{
		"name": "Iron Mortar",
		"gain": "pierces armour",
		"icon": "res://ui/icons/iron_mortar.png",
		"model": "res://models/towers/iron_mortar.glb",
		"head": "res://models/towers/iron_mortar_head.glb",
		"head_height": 0.77,
		"bore": Vector3(0, 0.36, 0.14),
		"recoil": 0.05,
		"projectile": "mortar_shell",
		"sound": ["mortar", -3.0],
		"flash": [Color(1.0, 0.62, 0.28), 1.5],
	},
	"deep_frost":
	{
		"name": "Deep Frost",
		"gain": "stronger slow",
		"icon": "res://ui/icons/deep_frost.png",
		"model": "res://models/towers/frost_tower_2.glb",
		"head": "res://models/towers/frost_head.glb",
		"head_height": 1.42,
		"head_scale": 1.12,
		"head_motion": "spin",
		"shards": 5,
		"muzzle": Vector3(0, 1.6, 0),
		"projectile": "frost_shard",
		"sound": ["frost", -6.0],
		"flash": [Color(0.6, 0.9, 1.0), 0.9],
	},
	"rime_spire":
	{
		"name": "Rime Spire",
		"gain": "reaches the sky",
		"icon": "res://ui/icons/rime_spire.png",
		"model": "res://models/towers/rime_spire.glb",
		"head": "res://models/towers/rime_spire_head.glb",
		"head_height": 1.42,
		"head_motion": "spin",
		"shards": 3,
		"muzzle": Vector3(0, 1.75, 0),
		"projectile": "frost_shard",
		"sound": ["frost", -6.0],
		"flash": [Color(0.75, 0.95, 1.0), 0.9],
	},
	"perch_ballista":
	{
		"name": "Perch Ballista",
		"description": "Heavy bolts that pierce armour and reach the sky.",
		"icon": "res://ui/icons/perch_ballista.png",
		"model": "res://models/towers/perch_ballista.glb",
		"head": "res://models/towers/perch_ballista_head.glb",
		"head_height": 1.05,
		"bore": Vector3(0, 0.27, 0.42),
		"recoil": 0.04,
		"projectile": "ballista_bolt",
		"sound": ["ballista", -4.0],
	},
	"hawk_roost":
	{
		"name": "Hawk Roost",
		"description": "Hawks that hunt fliers first.",
		"icon": "res://ui/icons/hawk_roost.png",
		"model": "res://models/towers/hawk_roost.glb",
		"muzzle": Vector3(0, 1.9, 0.05),
		"projectile": "hawk",
		"sound": ["hawk", -7.0],
	},
	"owls_eye":
	{
		"name": "Owl's Eye",
		"description": "Marks the toughest creep in reach: every tower hits it harder.",
		"icon": "res://ui/icons/owls_eye.png",
		"model": "res://models/towers/owls_eye.glb",
		"head": "res://models/towers/owls_eye_head.glb",
		"head_height": 0.99,
		"sound": ["mark", -8.0],
	},
	"siege_perch":
	{
		"name": "Siege Perch",
		"gain": "heavier bolts, deeper pierce",
		"icon": "res://ui/icons/siege_perch.png",
		"model": "res://models/towers/siege_perch.glb",
		"head": "res://models/towers/siege_perch_head.glb",
		"head_height": 1.05,
		"bore": Vector3(0, 0.3, 0.44),
		"recoil": 0.05,
		"projectile": "ballista_bolt",
		"projectile_scale": 1.25,
		"sound": ["ballista", -3.0],
	},
	"pinning_ballista":
	{
		"name": "Pinning Ballista",
		"gain": "every hit slows",
		"icon": "res://ui/icons/pinning_ballista.png",
		"model": "res://models/towers/pinning_ballista.glb",
		"head": "res://models/towers/pinning_ballista_head.glb",
		"head_height": 1.05,
		"bore": Vector3(0, 0.27, 0.42),
		"recoil": 0.04,
		"projectile": "pinning_bolt",
		"sound": ["ballista", -4.0],
	},
	"falcon_roost":
	{
		"name": "Falcon Roost",
		"gain": "faster, harder strikes",
		"icon": "res://ui/icons/falcon_roost.png",
		"model": "res://models/towers/falcon_roost.glb",
		"muzzle": Vector3(0, 2.05, 0.05),
		"projectile": "hawk",
		"projectile_scale": 1.2,
		"sound": ["hawk", -6.0],
	},
	"kestrel_flock":
	{
		"name": "Kestrel Flock",
		"gain": "strikes bounce to two more",
		"icon": "res://ui/icons/kestrel_flock.png",
		"model": "res://models/towers/kestrel_flock.glb",
		"muzzle": Vector3(0, 1.82, 0.05),
		"projectile": "kestrel",
		"sound": ["hawk", -8.0],
	},
	"owls_glare":
	{
		"name": "Owl's Glare",
		"gain": "a stronger mark",
		"icon": "res://ui/icons/owls_glare.png",
		"model": "res://models/towers/owls_glare.glb",
		"head": "res://models/towers/owls_glare_head.glb",
		"head_height": 0.99,
		"sound": ["mark", -7.0],
	},
	"twin_gaze":
	{
		"name": "Twin Gaze",
		"gain": "marks two at once",
		"icon": "res://ui/icons/twin_gaze.png",
		"model": "res://models/towers/twin_gaze.glb",
		"head": "res://models/towers/twin_gaze_head.glb",
		"head_height": 0.99,
		"sound": ["mark", -8.0],
	},
}

## The four checks (design 3.2) by SimContent.CHECK_IDS, with their glyphs: the tide
## forms every land's wrack takes (world.md), so they hold on every map. Each map shows
## its own teaching creep's portrait beside the glyph (M2).
const CHECKS := {
	"swarm": {"name": "Swarm", "glyph": "Froth", "icon": "res://ui/icons/check_swarm.png"},
	"swift": {"name": "Swift", "glyph": "Runnel", "icon": "res://ui/icons/check_swift.png"},
	"armored":
	{"name": "Armored", "glyph": "Ballast", "icon": "res://ui/icons/check_armored.png"},
	"winged":
	{"name": "Winged", "glyph": "Spindrift", "icon": "res://ui/icons/check_winged.png"},
}

## The roles (design 3.1) by SimContent.ROLE_IDS.
const ROLES := {
	"warden": {"name": "Warden", "icon": "res://ui/icons/role_warden.png"},
	"marksman": {"name": "Marksman", "icon": "res://ui/icons/role_marksman.png"},
	"breaker": {"name": "Breaker", "icon": "res://ui/icons/role_breaker.png"},
	"sweeper": {"name": "Sweeper", "icon": "res://ui/icons/role_sweeper.png"},
}

## The Builders' art by SimContent.BUILDER_IDS: "glyph" is the Builder's framed face on
## party rows, the roster, loading cards and result rows (ICON_DIR +
## SimContent.BUILDERS[id].glyph + ".png", 128 px, rendered from the figure's bust);
## "portrait" the posed figure the Builders screen's arch shows whole (Portrait.show_model);
## "bust" its head and shoulders, which the hub's arch shows, as a portrait window frames
## a face (the glyph is rendered from it); "emblem" the Builder's signature prop as a
## command button (the hub's Builders button shows your main's). Name, title and home are
## SimContent.BUILDERS'.
const BUILDERS := {
	"lamplighter":
	{
		"glyph": "res://ui/icons/builder_lamplighter.png",
		"portrait": "res://models/builders/lamplighter.glb",
		"bust": "res://models/builders/lamplighter_bust.glb",
		"emblem": "res://ui/icons/emblem_lamplighter.png",
	},
	"lookout":
	{
		"glyph": "res://ui/icons/builder_lookout.png",
		"portrait": "res://models/builders/lookout.glb",
		"bust": "res://models/builders/lookout_bust.glb",
		"emblem": "res://ui/icons/emblem_lookout.png",
	},
}

## The passives by SimContent.PERK_IDS; their numbers are SimContent.BUILDERS' "perk".
const PERKS := {
	"thrifty":
	{"name": "Thrifty", "text": "Her towers sell for 90%, not 70%."},
	"keen_sight": {"name": "Keen Sight", "text": "Her towers reach 0.4 tiles farther."},
}

## Creeps by SimContent.CREEP_IDS: "icon" is the framed portrait the strip and the wave
## list set beside a check's glyph, "check" the check (CHECKS) the creep teaches on this
## map (design 3.2: its portrait sits beside that glyph), "stride" the walking speed its
## walk cycle was made for (its build script prints it; for a flier, its flap cycle's),
## "hover" how high a winged creep flies over the road, in metres.
const CREEPS := {
	"gourdling":
	{
		"name": "Gourdling",
		"model": "res://models/creeps/gourdling.glb",
		"icon": "res://ui/icons/gourdling.png",
		"check": "swarm",
		"stride": 1.0,
		"scale": 1.5,
		"color": Color("#d9772b"),
	},
	"scuttler":
	{
		"name": "Scuttler",
		"model": "res://models/creeps/scuttler.glb",
		"icon": "res://ui/icons/scuttler.png",
		"check": "swift",
		"stride": 0.6075,
		"scale": 1.5,
		"color": Color("#6e4a82"),
	},
	"thornback":
	{
		"name": "Thornback",
		"model": "res://models/creeps/thornback.glb",
		"icon": "res://ui/icons/thornback.png",
		"check": "armored",
		"stride": 0.859,
		"scale": 1.35,
		"color": Color("#6b4a34"),
	},
	"hollowtide_crest":
	{
		"name": "The Hollowtide Crest",
		"model": "res://models/creeps/hollowtide_crest.glb",
		"icon": "res://ui/icons/hollowtide_crest.png",
		"check": "armored",
		"stride": 0.756,
		"scale": 1.6,
		"color": Color("#b5541f"),
	},
	"duskmoth":
	{
		"name": "Duskmoth",
		"model": "res://models/creeps/duskmoth.glb",
		"icon": "res://ui/icons/duskmoth.png",
		"check": "winged",
		# (art_src/blender/duskmoth.py: three flaps a second at 1.5 tiles a second)
		"stride": 1.5,
		"scale": 1.5,
		"hover": 1.0,
		"color": Color("#c98a4b"),
	},
	"bristlesow":
	{
		"name": "The Bristlesow",
		"model": "res://models/creeps/bristlesow.glb",
		"icon": "res://ui/icons/bristlesow.png",
		"check": "armored",
		# (the Thornback's cycle at game_scale 2.7, twice its 1.35: twice its stride)
		"stride": 1.718,
		"scale": 2.7,
		"color": Color("#4a3324"),
	},
}

## A group of at least this many creeps that teach Swarm is a pack and shows the Swarm
## glyph beside other checks (design 2.3: wave 4's eight Gourdlings walk beside
## Thornbacks and show only Armored; wave 11's sixteen are a pack). A wave of nothing
## else is a swarm at any count (classic's first, eight Gourdlings).
const SWARM_PACK := 10

const NOTICES := {
	SimTypes.REFUSE_CANNOT_BUILD_THERE: "Cannot build there",
	SimTypes.REFUSE_NOT_ENOUGH_GOLD: "Not enough gold",
	SimTypes.REFUSE_NOT_YOURS: "That tower is not yours",
	SimTypes.REFUSE_ALREADY_FORKED: "A fork is final",
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
			announce("The Holdfast stands. Victory!")
			Sfx.play("victory")
		SimTypes.PHASE_FALLEN:
			state_changed.emit(State.LOST)
			announce("The Holdfast has gone under")
			Sfx.play("defeat")


## "Wave 5 · Duskmoths"; a wave with a boss is named for it ("Wave 6 · The Bristlesow"),
## and the last one is the "Final wave".
func _wave_title(number: int) -> String:
	var lead := "Final wave" if number == total_waves() else "Wave %d" % number
	var bosses := wave_bosses(number - 1)
	if not bosses.is_empty():
		return "%s · %s" % [lead, CREEPS[bosses[0]]["name"]]
	var groups := wave_groups(number - 1)
	if groups.is_empty():
		return lead
	var first: Dictionary = groups[0]
	var name := str(CREEPS[first["creep"]]["name"])
	return "%s · %s" % [lead, name + "s" if int(first["count"]) > 1 else name]


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


## A tower form's numbers for people, with the display table's keys: the base `kind`
## standing as `branch` (-1 unforked, 0 for A, 1 for B), reaching `bonus_mm` farther
## (Keen Sight's; my_range_bonus() for my own). numbers() says what each number means;
## "form" is the form's id, "cost" the base's price and "fork_cost" a fork's.
func form_stats(kind: String, branch := -1, bonus_mm := 0) -> Dictionary:
	var form := SimContent.tower_form(kind, branch)
	var stats: Dictionary = TOWERS[form].duplicate()
	stats.merge(numbers(SimContent.tower_stats(kind, branch), bonus_mm), true)
	stats["form"] = form
	stats["cost"] = int(SimContent.TOWERS[kind]["cost"])
	stats["fork_cost"] = int(SimContent.TOWERS[kind]["fork_cost"])
	return stats


## Tower numbers in the simulation's units (SimContent.TOWERS' keys, or a SimTower's
## resolved fields under the same names) for people: "damage" per hit, "range" in tiles,
## "cooldown" in seconds, "air" whether it reaches the sky, and where they apply "splash"
## (radius in tiles), "slow" (a fraction) for "slow_time" seconds, "pierce" (armour it
## ignores), "mark" (the extra share a marked creep takes) on "marks" creeps, and
## "bounces" (creeps a strike flies on to) within "bounce_range".
static func numbers(sim_stats: Dictionary, bonus_mm := 0) -> Dictionary:
	var ticks := float(SimTypes.TICKS_PER_SECOND)
	var out := {
		"damage": int(sim_stats.get("dmg_c", 0)) / 100.0,
		"range": (int(sim_stats.get("range_mm", 0)) + bonus_mm) / 1000.0,
		"cooldown": int(sim_stats.get("cd_t", 0)) / ticks,
		"air": bool(sim_stats.get("air", false)),
	}
	if int(sim_stats.get("splash_mm", 0)) > 0:
		out["splash"] = int(sim_stats["splash_mm"]) / 1000.0
	if int(sim_stats.get("slow_pm", 0)) > 0:
		out["slow"] = int(sim_stats["slow_pm"]) / 1000.0
		out["slow_time"] = int(sim_stats.get("slow_t", 0)) / ticks
	if int(sim_stats.get("pierce_c", 0)) > 0:
		out["pierce"] = int(sim_stats["pierce_c"]) / 100.0
	if int(sim_stats.get("mark_pm", 0)) > 0:
		out["mark"] = int(sim_stats["mark_pm"]) / 1000.0
		out["marks"] = int(sim_stats.get("marks", 1))
	if int(sim_stats.get("bounces", 0)) > 0:
		out["bounces"] = int(sim_stats["bounces"])
		out["bounce_range"] = int(sim_stats.get("bounce_mm", 0)) / 1000.0
	return out


## The command tooltip's body for kit slot `slot` (0 to 2) of `builder`: the tower's line,
## its numbers (reaching `bonus_mm` farther: Keen Sight's) and both branches with the
## fork's price, what each gains and the check a patching branch lifts. One source for the
## in-game card's Q W E and the Builders screen (design 5.4). A branch line starts with
## FORK_MARK, never a letter: the card's keys are positional, Q and W take the branches
## and A signals, so "A" or "B" before a branch would read as the key to press.
func kit_tip(builder: String, slot: int, bonus_mm := 0) -> String:
	var kind := SimContent.kit_tower(builder, slot)
	var data := form_stats(kind, -1, bonus_mm)
	var lines := PackedStringArray([str(data.get("description", ""))])
	var parts := PackedStringArray()
	if float(data["damage"]) > 0.0:
		parts.append("Damage %s" % _tip_num(float(data["damage"])))
	parts.append("Range %s" % _tip_num(float(data["range"])))
	parts.append("Cooldown %ss" % _tip_num(float(data["cooldown"])))
	if data.has("splash"):
		parts.append("Splash %s" % _tip_num(float(data["splash"])))
	if data.has("slow"):
		parts.append("Slow %d%%" % roundi(float(data["slow"]) * 100.0))
	if data.has("mark"):
		parts.append("Mark +%d%%" % roundi(float(data["mark"]) * 100.0))
	parts.append("Hits fliers" if bool(data["air"]) else "Ground only")
	lines.append(" · ".join(parts))
	for b in 2:
		var branch_id := str(SimContent.BUILDERS[builder]["branches"][slot][b])
		var line := "%s %s +%d: %s" % [FORK_MARK, TOWERS[branch_id]["name"], int(data["fork_cost"]), TOWERS[branch_id]["gain"]]
		var helps := SimContent.branch_helps(builder, branch_id)
		if helps != "":
			line += " (%s)" % CHECKS[helps]["name"]
		lines.append(line)
	return "\n".join(lines)


static func _tip_num(value: float) -> String:
	return str(roundi(value)) if is_equal_approx(value, roundf(value)) else "%.1f" % value


## The numbers at a level, as M1 counted them: level 2 is fork branch A.
func tower_stats(kind: String, level: int) -> Dictionary:
	return form_stats(kind, 0 if level >= 2 else -1, my_range_bonus())


func tower_cost(kind: String) -> int:
	return int(SimContent.TOWERS[kind]["cost"])


func fork_cost(kind: String) -> int:
	return int(SimContent.TOWERS[kind]["fork_cost"])


## The Builder my seat plays.
func builder() -> String:
	return _seat().builder if sim else "lamplighter"


## Seat `n`'s name as the others see it: the server's names in a networked match, the
## names the scene was given for an offline one, else "Seat 2".
func seat_name(n: int) -> String:
	var scene := get_tree().current_scene if is_inside_tree() else null
	var names: Variant = []
	if scene:
		var client: Variant = scene.get("client")
		if client is MatchClient:
			names = (client as MatchClient).names
		elif scene.get("_spec") is Dictionary:
			names = (scene.get("_spec") as Dictionary).get("names", [])
	if names is Array and n >= 1 and n - 1 < (names as Array).size():
		return str(names[n - 1])
	return "Seat %d" % n


## My Builder's tower on kit slot `slot` (0, 1, 2: Q, W, E), or "".
func kit_tower(slot: int) -> String:
	return SimContent.kit_tower(builder(), slot)


## How much farther my towers reach (Keen Sight where perks are on), millimetres.
func my_range_bonus() -> int:
	return sim.range_bonus(seat) if sim else 0


## The checks wave `index` (0-based) tests, in the order its groups come, each once with
## the creep that brings it: [[check, creep], ...]. Swarm counts for a pack (SWARM_PACK)
## or when the wave brings nothing else; a boss shows the check it teaches like any
## creep (wave_bosses() names it).
func wave_checks(index: int) -> Array:
	var out := []
	var seen := []
	var small_swarm := ""
	for group: Dictionary in wave_groups(index):
		var creep := str(group["creep"])
		var check := str(CREEPS.get(creep, {}).get("check", ""))
		if check == "" or seen.has(check):
			continue
		if check == "swarm" and int(group["count"]) < SWARM_PACK:
			if small_swarm == "":
				small_swarm = creep
			continue
		seen.append(check)
		out.append([check, creep])
	if out.is_empty() and small_swarm != "":
		out.append(["swarm", small_swarm])
	return out


## The bosses wave `index` (0-based) sends, in order.
func wave_bosses(index: int) -> Array:
	var out := []
	for group: Dictionary in wave_groups(index):
		var creep := str(group["creep"])
		if bool(SimContent.CREEPS.get(creep, {}).get("boss", false)) and not out.has(creep):
			out.append(creep)
	return out


## Whether the art at `path` exists yet (icons and models another track paints later).
func has_art(path: String) -> bool:
	return path != "" and ResourceLoader.exists(path)


## The icon at `path`, or, until that art is painted, a quiet ring in the HUD's dim
## bronze, so no screen fails on art that lands later. Read every path in the tables
## above through this.
func icon(path: String) -> Texture2D:
	if has_art(path):
		var texture := load(path) as Texture2D
		if texture:
			return texture
	return placeholder_icon()


static var _placeholder: Texture2D


## The stand-in icon: transparent with a thin dim ring, 64 pixels square.
static func placeholder_icon() -> Texture2D:
	if _placeholder == null:
		var size := 64
		var image := Image.create_empty(size, size, false, Image.FORMAT_RGBA8)
		var ring := Color("#a3957d", 0.8)
		var centre := Vector2(size, size) / 2.0
		for y in size:
			for x in size:
				var d := (Vector2(x, y) + Vector2(0.5, 0.5)).distance_to(centre)
				if absf(d - size * 0.36) < 1.5:
					image.set_pixel(x, y, ring)
		_placeholder = ImageTexture.create_from_image(image)
	return _placeholder


## A Builder's own tint (SimContent.BUILDERS' "accent") as a colour.
func builder_accent(builder: String) -> Color:
	return Color.hex((int(SimContent.BUILDERS[builder]["accent"]) << 8) | 0xFF)


## How a Builder's glyph is drawn: as painted, or in the Builder's accent while it is
## still the placeholder ring, so two Builders read apart before their art lands.
func glyph_tint(builder: String) -> Color:
	return Color.WHITE if has_art(str(BUILDERS[builder]["glyph"])) else builder_accent(builder)


## The kit slot (0 to 2) my Builder places `kind` from, or -1.
func slot_of(kind: String) -> int:
	return (SimContent.BUILDERS[builder()]["towers"] as Array).find(kind)


func _seat() -> SimRecords.SimSeat:
	return sim.seat(seat)


func _team() -> SimRecords.SimTeam:
	return sim.teams[_seat().team]


func _hollow() -> SimRecords.SimHollow:
	return sim.hollows[_seat().hollow]
