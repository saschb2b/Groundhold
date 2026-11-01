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
## A notice about a teammate's seat (design 5.7: "Ben's link dropped", "Ben is back"):
## held a little longer than a refused order's, since nobody pressed anything for it.
signal team_noticed(text: String)
## A command of mine ran (accepted) or was refused; `seq` is what command() returned.
signal settled(seq: int, accepted: bool)
## Someone's Ready changed, or a seat changed hands.
signal ready_changed
## A tower was built, upgraded or sold, by anyone.
signal towers_changed
## (M6) A race moved on (EV_RACE): a team cleared its last wave or fell, or the race was
## decided.
signal race_changed
## (M7) The duel moved on: a bottle corked, uncorked or fizzled, a breach, a Seawall, the
## Drift or the Surge, or the duel decided. The Drift tray and the duel bar read the
## records again.
signal duel_changed

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
## M6's forms (contract-m6.md §5) turn no head. Their effects come from the records and
## the pulse event, so they need no projectile: the Toll Tower's bell rings on EV_PULSE
## (Fx.bell_ring), a Clay Hive's bees swarm over the creep its cloud stings (Fx.bee_cloud),
## a Chime Post's crack shimmers on its creeps and a Hive Hum's haste glows under the
## towers it hastens. Their "sound" sounds when the pulse rings, the cloud forms, or the
## aura first takes hold. Two more keys:
##   projectile   "clap": the Clapper Tower's strike is instant, a clap on its creep
##                (Projectile.INSTANT), no model in flight
##   burst        "ring": a splash shows as a bronze ring through the crowd, not a blast
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
	# M6 (contract-m6.md §5): the Bellfounder's and the Beekeeper's forms, each its own
	# model (models/towers/<form>.glb), none with a head. Each muzzle is measured on its
	# model (art_src/models/towers/m6_kits.py's recipe): a bell's middle, between its lip
	# and its crown (the toll's ring bursts there); the middle row of a Clay Hive's pipe
	# mouths; an Apiary's top ring of bee holes, in the house's middle, so a bee leaves
	# through the wall toward its creep; the middle of a post's chimes or a straw hive.
	# Their sounds sit level with the M2 towers' as played (the loudest tenth of a second
	# of the file plus this gain): a strike or a pulse about -12 dB like the cannon's and
	# the mortar's, a frequent Apiary about -15 like the ballistas', an aura taking hold
	# about -12 to -14 like a new mark. The files (sfx/toll, chime, bees, clap) peak at
	# -1.5 dB, so no gain here is above 0.
	# The Bellfounder's: a bell frame whose clapper strikes at once, a belfry whose bell
	# rings a pulse, a post of chimes that cracks armour.
	"clapper_tower":
	{
		"name": "Clapper Tower",
		"description": "A bronze clapper that strikes hard at close range.",
		"icon": "res://ui/icons/clapper_tower.png",
		"model": "res://models/towers/clapper_tower.glb",
		"muzzle": Vector3(0, 0.92, 0),
		"projectile": "clap",
		"sound": ["clap", -1.0],
	},
	"toll_tower":
	{
		"name": "Toll Tower",
		"description": "Rings out a pulse that stuns every ground creep in reach.",
		"icon": "res://ui/icons/toll_tower.png",
		"model": "res://models/towers/toll_tower.glb",
		"muzzle": Vector3(0, 1.26, 0),
		"sound": ["toll", -2.0],
	},
	"chime_post":
	{
		"name": "Chime Post",
		"description": "Its hum cracks the armour of every creep in reach, for every tower.",
		"icon": "res://ui/icons/chime_post.png",
		"model": "res://models/towers/chime_post.glb",
		"muzzle": Vector3(0, 1.15, 0),
		"sound": ["chime", -1.0],
	},
	"great_clapper":
	{
		"name": "Great Clapper",
		"gain": "a far heavier strike",
		"icon": "res://ui/icons/great_clapper.png",
		"model": "res://models/towers/great_clapper.glb",
		"muzzle": Vector3(0, 1.04, 0),
		"projectile": "clap",
		"sound": ["clap", 0.0],
	},
	"ringing_clapper":
	{
		"name": "Ringing Clapper",
		"gain": "each strike rings through a crowd",
		"icon": "res://ui/icons/ringing_clapper.png",
		"model": "res://models/towers/ringing_clapper.glb",
		"muzzle": Vector3(0, 0.92, 0),
		"projectile": "clap",
		"burst": "ring",
		"sound": ["clap", -1.0],
	},
	"great_toll":
	{
		"name": "Great Toll",
		"gain": "a harder, wider pulse and a longer stun",
		"icon": "res://ui/icons/great_toll.png",
		"model": "res://models/towers/great_toll.glb",
		"muzzle": Vector3(0, 1.25, 0),
		"sound": ["toll", -1.0],
	},
	"sky_toll":
	{
		"name": "Sky Toll",
		"gain": "reaches fliers, slowing them by half for 2 s and striking them 80% harder",
		"icon": "res://ui/icons/sky_toll.png",
		"model": "res://models/towers/sky_toll.glb",
		"muzzle": Vector3(0, 1.94, 0),
		"sound": ["toll", -2.0],
	},
	"deep_chime":
	{
		"name": "Deep Chime",
		"gain": "cracks twice the armour",
		"icon": "res://ui/icons/deep_chime.png",
		"model": "res://models/towers/deep_chime.glb",
		"muzzle": Vector3(0, 1.12, 0),
		"sound": ["chime", 0.0],
	},
	"long_chime":
	{
		"name": "Long Chime",
		"gain": "cracks armour farther out",
		"icon": "res://ui/icons/long_chime.png",
		"model": "res://models/towers/long_chime.glb",
		"muzzle": Vector3(0, 1.2, 0),
		"sound": ["chime", -1.0],
	},
	# The Beekeeper's: clay pipe hives whose bees cloud over a creep, a hive house whose
	# bees fly at fliers first, a straw hive whose hum hastens every tower near it.
	"clay_hive":
	{
		"name": "Clay Hive",
		"description": "A bee cloud over the foremost creep stings all near it, on the ground or in the air.",
		"icon": "res://ui/icons/clay_hive.png",
		"model": "res://models/towers/clay_hive.glb",
		"muzzle": Vector3(0, 0.46, 0.3),
		"sound": ["bees", -2.0],
	},
	"apiary":
	{
		"name": "Apiary",
		"description": "Bees that hunt fliers first and sting them hardest.",
		"icon": "res://ui/icons/apiary.png",
		"model": "res://models/towers/apiary.glb",
		"muzzle": Vector3(0, 0.88, 0),
		"projectile": "bee",
		"sound": ["bees", -5.0],
	},
	"hive_hum":
	{
		"name": "Hive Hum",
		"description": "Every tower in reach fires faster, whoever built it.",
		"icon": "res://ui/icons/hive_hum.png",
		"model": "res://models/towers/hive_hum.glb",
		"muzzle": Vector3(0, 0.65, 0),
		"sound": ["bees", -4.0],
	},
	"great_clay_hive":
	{
		"name": "Great Clay Hive",
		"gain": "a wider cloud, sharper stings",
		"icon": "res://ui/icons/great_clay_hive.png",
		"model": "res://models/towers/great_clay_hive.glb",
		"muzzle": Vector3(0, 0.5, 0.3),
		"sound": ["bees", -1.0],
	},
	"drowsy_clay_hive":
	{
		"name": "Drowsy Clay Hive",
		"gain": "stung creeps slow by a quarter",
		"icon": "res://ui/icons/drowsy_clay_hive.png",
		"model": "res://models/towers/drowsy_clay_hive.glb",
		"muzzle": Vector3(0, 0.46, 0.3),
		"sound": ["bees", -2.0],
	},
	"royal_apiary":
	{
		"name": "Royal Apiary",
		"gain": "much harder stings",
		"icon": "res://ui/icons/royal_apiary.png",
		"model": "res://models/towers/royal_apiary.glb",
		"muzzle": Vector3(0, 1.13, 0),
		"projectile": "bee",
		"projectile_scale": 1.2,
		"sound": ["bees", -4.0],
	},
	"queens_guard":
	{
		"name": "Queen's Guard",
		"gain": "slower, far heavier stings that pierce armour",
		"icon": "res://ui/icons/queens_guard.png",
		"model": "res://models/towers/queens_guard.glb",
		"muzzle": Vector3(0, 0.83, 0),
		"projectile": "bee",
		"projectile_scale": 1.4,
		"sound": ["bees", -3.0],
	},
	"great_hum":
	{
		"name": "Great Hum",
		"gain": "a stronger hum",
		"icon": "res://ui/icons/great_hum.png",
		"model": "res://models/towers/great_hum.glb",
		"muzzle": Vector3(0, 0.77, 0),
		"sound": ["bees", -3.0],
	},
	"long_hum":
	{
		"name": "Long Hum",
		"gain": "hums farther out",
		"icon": "res://ui/icons/long_hum.png",
		"model": "res://models/towers/long_hum.glb",
		"muzzle": Vector3(0, 1.35, 0),
		"sound": ["bees", -4.0],
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
	"bellfounder":
	{
		"glyph": "res://ui/icons/builder_bellfounder.png",
		"portrait": "res://models/builders/bellfounder.glb",
		"bust": "res://models/builders/bellfounder_bust.glb",
		"emblem": "res://ui/icons/emblem_bellfounder.png",
	},
	"beekeeper":
	{
		"glyph": "res://ui/icons/builder_beekeeper.png",
		"portrait": "res://models/builders/beekeeper.glb",
		"bust": "res://models/builders/beekeeper_bust.glb",
		"emblem": "res://ui/icons/emblem_beekeeper.png",
	},
}

## The passives by SimContent.PERK_IDS; their numbers are SimContent.BUILDERS' "perk".
const PERKS := {
	"thrifty":
	{"name": "Thrifty", "text": "Her towers sell for 90%, not 70%."},
	"keen_sight": {"name": "Keen Sight", "text": "Her towers reach 0.4 tiles farther."},
	"bronze_hand": {"name": "Bronze Hand", "text": "Her hits ignore 2 armour."},
	"hive_tithe":
	{"name": "Hive Tithe", "text": "Each Clay Hive and Hive Hum pays her 2 gold at every wave clear, at most 12."},
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
	# (M7, the duel's: contract-m7.md §1)
	SimTypes.REFUSE_NO_CORKS_LEFT: "No corks left this window",
	# (REFUSE_TOO_EARLY's words name the duel's uncork_after_t: refusal_text)
	SimTypes.REFUSE_NOTHING_CORKED: "Nothing corked for this wave",
	SimTypes.REFUSE_BAD_REVEAL: "That bottle would not open",
	SimTypes.REFUSE_NO_CHARGE: "No Seawall charge",
	SimTypes.REFUSE_SEAWALL_STANDING: "The Seawall is still standing",
}
## An order aimed at the other team's hollow in a race, refused here before it goes out
## (contract-m6.md §5): the simulation reads a seat's cells on its own hollow, so the same
## cell sent would land on mine.
const RIVAL_HOLLOW := "That is your rival's hollow"
## An order given once the match is over for me (over()), refused here: MatchClient's
## own words for an order after MATCH_END.
const MATCH_OVER := "The match is over"
## What a wave's clear pays me beside its bonus, by EV_GOLD's why, as its banner names it
## (clear_title): the Beekeeper's Hive Tithe, and a duel's stipend.
const CLEAR_PAYS := {"tithe": "Tithe", "stipend": "Stipend"}
## MATCH_END's outcome names (protocol.json "outcomes") by SimTypes.OUTCOME_*.
const OUTCOME_NAMES := {
	SimTypes.OUTCOME_WON: "won",
	SimTypes.OUTCOME_LOST: "lost",
	SimTypes.OUTCOME_DRAW: "draw",
}
## A race's titles by my team's outcome (design 5.8).
const RACE_TITLES := {
	"won": "You Outran the Tide",
	"lost": "Your Rival Outran the Tide",
	"draw": "Two Crews, One Time",
}

## Tide Race (design 2.2, contract-m6.md §5): hollow h stands this many tiles along +x
## from the first, beyond a two-tile cliff band (the map is 24 wide). The board, the world
## the views stand in, counts cells across every hollow; the simulation's cells and
## millimetres are local to their hollow, so a view adds hollow_origin(h).
const HOLLOW_STRIDE := 26

## The match this client shows, the source its turns come from, and my seat in it.
var sim: SimMatch
var source: TurnSource
var seat := 1
## Gold my commands still waiting for their turn will spend: kept back when deciding
## what I can afford.
var pending_gold := 0
## The teammate notices said this match, oldest first (the last TEAM_NOTICES_KEPT), for
## scenarios.
var team_notices: Array[String] = []
const TEAM_NOTICES_KEPT := 32
## The lives my team had before the first it lost in my hollow's wave now running, and
## the lives after its latest loss (-1 while it lost none): the clear banner says how many
## the wave cost. Read from EV_LIVES in event order, as absolute counts, so a frame that
## runs many ticks, or turns run again after a resync, count each life once.
var _wave_lives_from := -1
var _wave_lives_now := -1
## What a clear of my hollow pays me beside its bonus, by EV_GOLD's why ("tithe": the Hive
## Tithe; "stipend": a duel's), read from the events that come before the clear's EV_WAVE in
## the same tick, so its banner names them; spent by that banner.
var _clear_pays := {}

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
	_attach_duel()
	gold_changed.emit(gold)
	lives_changed.emit(lives)
	wave_changed.emit(wave)
	state_changed.emit(state)


func detach() -> void:
	sim = null
	source = null
	pending_gold = 0
	team_notices.clear()
	forget_duel()
	_wave_lives_from = -1
	_wave_lives_now = -1
	_clear_pays.clear()


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
## link to the server", "Not so fast", "The caretaker hands back at the next build
## window"); "" when it would go out.
func command_refusal() -> String:
	if source == null:
		return "The match has not started"
	var why := source.refusal()
	if why == "" and caretaken():
		return NOTICES[SimTypes.REFUSE_CARETAKEN]
	return why


## Why an order of mine would be refused before it goes out, checked before its gold or
## its cell: the match or the link (accepts_commands()), the match over for me (over():
## online a decided race takes no order between the decision and MATCH_END, which closes
## the link's side), or my seat still the caretaker's (away, or back and waiting for the
## next build window, design 6.7), which the simulation would refuse anyway; "" when it
## may go. The bucket ("Not so fast") is the command's own.
func order_refusal() -> String:
	if not accepts_commands():
		return command_refusal()
	if over():
		return MATCH_OVER
	if caretaken():
		return NOTICES[SimTypes.REFUSE_CARETAKEN]
	return ""


## Whether the match is over for me: my hollow done or fallen, the match ended
## (SimMatch.over, the cap too), or a race decided while my hollow still plays (my rival
## cleared first, or fell and I cleared that wave: my hollow is in a window or a wave, but
## nothing it does counts any more).
func over() -> bool:
	if sim == null:
		return false
	return state == State.WON or state == State.LOST or sim.over or outcome() != ""


## Whether the caretaker plays my seat now (away, or back until the next build window).
func caretaken() -> bool:
	return sim != null and not sim.over and _seat().state != SimTypes.SEAT_PRESENT


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
					var why := str(e.get("why", ""))
					if CLEAR_PAYS.has(why):
						_clear_pays[why] = int(_clear_pays.get(why, 0)) + int(e["change"])
					gold_changed.emit(int(e["gold"]))
			SimTypes.EV_LIVES:
				if e["team"] == _seat().team:
					if int(e.get("change", 0)) < 0:
						if _wave_lives_from < 0:
							_wave_lives_from = int(e["lives"]) - int(e["change"])
						_wave_lives_now = int(e["lives"])
					lives_changed.emit(int(e["lives"]))
			SimTypes.EV_WAVE:
				if e["hollow"] == _seat().hollow:
					_on_wave(e)
			SimTypes.EV_READY, SimTypes.EV_SEAT:
				if e.get("seat", 0) == seat and e.has("seq"):
					settled.emit(int(e["seq"]), true)
				if int(e["type"]) == SimTypes.EV_SEAT and int(e["seat"]) != seat:
					_teammate_seat(int(e["seat"]), int(e["state"]))
				ready_changed.emit()
			SimTypes.EV_BUILT, SimTypes.EV_FORKED, SimTypes.EV_SOLD:
				if e["seat"] == seat and int(e["seq"]) > 0:
					settled.emit(int(e["seq"]), true)
				towers_changed.emit()
			SimTypes.EV_REJECTED:
				if e["seat"] == seat:
					_refused(e)
			SimTypes.EV_RACE:
				_on_race(e)
			SimTypes.EV_DRIFT, SimTypes.EV_CORK, SimTypes.EV_UNCORK, SimTypes.EV_FIZZLE, SimTypes.EV_BREACH, SimTypes.EV_SEAWALL, SimTypes.EV_SURGE:
				_on_duel(e)
		if int(e["type"]) in ORDER_EVENTS and int(e.get("seat", 0)) == seat and int(e.get("seq", 0)) > 0:
			_order_ran(int(e["seq"]))  # (after the event's own settling: what waits below it is lost)
	if is_duel():
		_duel_decided()


## A teammate's seat changed hands (EV_SEAT): the notice design 5.7 asks for, with their
## name. Not while my own game runs turns it missed (a catch-up replays changes the
## others saw long ago), and not for a rival team's seats.
func _teammate_seat(n: int, now: int) -> void:
	var s := sim.seat(n)
	if s == null or s.team != _seat().team:
		return
	if _catching_up():
		return
	var client := _scene_client()
	var who := seat_name(n)
	var text := ""
	match now:
		SimTypes.SEAT_AWAY:
			var hidden := false
			if client != null and n - 1 < client.link_flags.size():
				hidden = (client.link_flags[n - 1] & NetProtocol.enum_value("link_flags", "hidden")) != 0
			if hidden:
				text = "%s is in another tab: a caretaker builds meanwhile" % who
			elif sim.tick <= SimTypes.TURN_TICKS:
				text = "%s is still loading: a caretaker builds meanwhile" % who
			else:
				text = "%s's link dropped: a caretaker builds meanwhile" % who
		SimTypes.SEAT_RETURNING:
			text = "%s is back: the caretaker hands back at the next build window" % who
		SimTypes.SEAT_PRESENT:
			text = "%s builds again" % who
		SimTypes.SEAT_LEFT:
			text = "%s left the match: a caretaker keeps the seat" % who
	if text == "":
		return
	team_notices.append(text)
	if team_notices.size() > TEAM_NOTICES_KEPT:
		team_notices.remove_at(0)
	team_noticed.emit(text)


## Whether my game runs turns it missed or runs again: a networked catch-up (after a
## RESYNC, a rejoin, a hidden tab) or its link coming back. What they did was said when it
## happened, or happened while nobody here watched, so their moments are not said now: a
## teammate's seat changing hands, the duel's sounds and notices.
func _catching_up() -> bool:
	var client := _scene_client()
	return client != null and (client.catching_up or client.reconnecting)


## The networked match's client the current scene plays through, or null.
func _scene_client() -> MatchClient:
	var scene := get_tree().current_scene if is_inside_tree() else null
	if scene == null:
		return null
	var client: Variant = scene.get("client")
	return client as MatchClient if client is MatchClient else null


func _on_wave(e: Dictionary) -> void:
	if e.get("start", false):
		_wave_lives_from = -1  # (this wave has cost nothing yet)
		_wave_lives_now = -1
		_clear_pays.clear()
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
				announce(clear_title(int(e["wave"]), int(e["bonus"]), wave_lives_lost(), _clear_pays))
				_wave_lives_from = -1
				_wave_lives_now = -1
				_clear_pays = {}
		SimTypes.PHASE_WAVE:
			wave_changed.emit(wave)
		SimTypes.PHASE_DONE:
			state_changed.emit(State.WON)
			if is_race() or is_duel():
				return  # (my hollow is done; the race or the duel may not be: _on_race, _duel_decided)
			announce("The Holdfast stands. Victory!")
			Sfx.play("victory")
		SimTypes.PHASE_FALLEN:
			state_changed.emit(State.LOST)
			if is_race() or is_duel():
				return  # (a race falls to its win order, _on_race; a duel says its fall, _duel_decided)
			announce("The Holdfast has gone under")
			Sfx.play("defeat")


## The banner of a cleared wave: "Wave 6 cleared · +20 gold", and when creeps got through to
## the Holdfast in it, what they cost: "Wave 6 cleared · 5 lives lost · +20 gold"; then what
## else the clear paid me (`pays`, by EV_GOLD's why, CLEAR_PAYS), each by name: "Wave 1
## cleared · +10 gold · Tithe +4" (playtest halv s1, f43548: the Hive Tithe paid 4 at the
## clear, and the banner said only "+10 gold").
func clear_title(number: int, bonus: int, lost: int, pays := {}) -> String:
	var name := wave_name(number)
	var title := "%s cleared · +%d gold" % [name, bonus]
	if lost > 0:
		title = "%s cleared · %d %s lost · +%d gold" % [name, lost, "life" if lost == 1 else "lives", bonus]
	for why: String in CLEAR_PAYS:
		if int(pays.get(why, 0)) > 0:
			title += " · %s +%d" % [CLEAR_PAYS[why], int(pays[why])]
	return title


## The lives my team lost in my hollow's wave now running (or just cleared).
func wave_lives_lost() -> int:
	return maxi(0, _wave_lives_from - _wave_lives_now) if _wave_lives_from >= 0 else 0


## "Wave 5 · Duskmoths"; a wave with a boss is named for it ("Wave 6 · The Bristlesow"),
## and the last one is the "Final wave".
func _wave_title(number: int) -> String:
	var lead := "Final wave" if number == last_wave() else "Wave %d" % number
	if surge() > 0:
		lead = "Surge %d/%d" % [surge(), surge_waves()] if number < last_wave() else "The last Surge"
	var bosses := wave_bosses(content_wave(number) - 1)
	if not bosses.is_empty():
		return "%s · %s" % [lead, CREEPS[bosses[0]]["name"]]
	var groups := wave_groups(content_wave(number) - 1)
	if groups.is_empty():
		return lead
	var first: Dictionary = groups[0]
	var name := str(CREEPS[first["creep"]]["name"])
	return "%s · %s" % [lead, name + "s" if int(first["count"]) > 1 else name]


## A refusal's words for the notice: NOTICES', and for one the duel's timing decides, read
## from its rules ("The cork holds for 3 s after the horn", uncork_after_t), so the words
## follow the numbers. A refusal for the wrong moment (REFUSE_WRONG_PHASE, which NOTICES
## leaves out) says what moved on under the order of `cmd` (WRONG_MOMENT): the match over,
## or the horn or the wave's end that came before a duel's order ran, never a bare "Not
## now" (playtest halv s1, f106511).
func refusal_text(reason: int, cmd := 0) -> String:
	if reason == SimTypes.REFUSE_TOO_EARLY:
		return "The cork holds for %s after the horn" % duel_seconds("uncork_after_t")
	if reason == SimTypes.REFUSE_WRONG_PHASE:
		if sim != null and sim.over:
			return MATCH_OVER
		if WRONG_MOMENT.has(cmd):
			return str(WRONG_MOMENT[cmd])
	if reason == SimTypes.REFUSE_BAD_COMMAND and cmd == SimTypes.CMD_CORK:
		return str(WRONG_MOMENT[cmd])  # (its turn came in a later window, of another tier)
	return str(NOTICES.get(reason, "Not now"))


## One of the duel's timings (a duel_rules() key in ticks) as the copy says it: "3 s", "24 s",
## "2.5 s"; "" outside a duel.
func duel_seconds(key: String) -> String:
	if not is_duel():
		return ""
	return _seconds(int(duel_rules().get(key, 0)))


func _refused(e: Dictionary) -> void:
	settled.emit(int(e["seq"]), false)
	var reason: int = e["reason"]
	if not _duel_refused(e):
		return  # (an uncorking the client sent by itself: it tries again, unheard)
	if reason == SimTypes.REFUSE_WRONG_PHASE and int(e["cmd"]) == SimTypes.CMD_READY:
		return  # the horn had already sounded
	Sfx.play("error")
	notice(refusal_text(reason, int(e.get("cmd", 0))))


# ── Questions the HUD and the input ask ──


func total_waves() -> int:
	return sim.total_waves() if sim else 0


## The last wave the hollows play: total_waves(), and in a duel the Surge's after it
## (SimMatch.last_wave: 15 in Undertow). No Ready is asked for past it.
func last_wave() -> int:
	return sim.last_wave() if sim else 0


## The wave whose list wave `number` (1-based) plays: itself, and in a duel's Surge the
## wave it repeats (SimUndertow.content_wave: wave 13 plays wave 9 again).
func content_wave(number: int) -> int:
	return SimUndertow.content_wave(sim, number) if is_duel() else number


## Wave `index` (0-based) as groups {"creep", "count"}.
func wave_groups(index: int) -> Array:
	if sim == null or index < 0 or index >= sim.waves.size():
		return []
	return sim.waves[index]


## The health a creep of `kind` has when wave `number` (the match's, 1-based: a duel's
## Surge's grows as the wave it repeats, with the Surge's share on top) sends it onto my
## hollow, scaled by my hollow's seats, in whole points as its plate shows them
## (SimWaves.health_c, the very sum its spawn takes).
func wave_health(kind: String, number: int) -> int:
	if sim == null or not SimContent.CREEPS.has(kind):
		return 0
	return ceili(SimWaves.health_c(sim, _hollow(), kind, number) / 100.0)


## The armour a creep of `kind` wears in this match, as its plate shows it: none where the
## rules leave armour out (classic).
func creep_armor(kind: String) -> float:
	if sim == null or not bool(sim.rules.get("armor", true)) or not SimContent.CREEPS.has(kind):
		return 0.0
	return int(SimContent.CREEPS[kind]["armor_c"]) / 100.0


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


## [ready seats, seats] on my hollow; in a duel on both, whose one clock's horn waits for
## both seats (contract-m7.md §2; a caretaken seat counts as Ready).
func ready_count() -> Array:
	if sim == null:
		return [0, 1]
	if is_duel():
		var total := [0, 0]
		for h in sim.hollows:
			var count := sim.ready_count(h.id)
			total[0] += int(count[0])
			total[1] += int(count[1])
		return total
	return sim.ready_count(_seat().hollow)


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
## (Keen Sight's; my_range_bonus() for my own) and ignoring `pierce_c` more armour (Bronze
## Hand's, M6: SimMatch.pierce_bonus, which the simulation adds to every tower of its
## owner's). numbers() says what each number means; "form" is the form's id, "cost" the
## base's price and "fork_cost" a fork's.
func form_stats(kind: String, branch := -1, bonus_mm := 0, pierce_c := 0) -> Dictionary:
	var form := SimContent.tower_form(kind, branch)
	var stats: Dictionary = TOWERS[form].duplicate()
	var sim_stats := SimContent.tower_stats(kind, branch)
	if pierce_c > 0:
		sim_stats = sim_stats.duplicate()
		sim_stats["pierce_c"] = int(sim_stats.get("pierce_c", 0)) + pierce_c
	stats.merge(numbers(sim_stats, bonus_mm), true)
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
	# M6 (contract-m6.md §3): a pulse's stun in seconds, a cloud's reach in tiles, a crack
	# in armour, a hum's haste as a share
	if int(sim_stats.get("stun_t", 0)) > 0:
		out["stun"] = int(sim_stats["stun_t"]) / ticks
	if int(sim_stats.get("cloud_mm", 0)) > 0:
		out["cloud"] = int(sim_stats["cloud_mm"]) / 1000.0
	if int(sim_stats.get("crack_c", 0)) > 0:
		out["crack"] = int(sim_stats["crack_c"]) / 100.0
	if int(sim_stats.get("haste_pm", 0)) > 0:
		out["haste"] = int(sim_stats["haste_pm"]) / 1000.0
	# (any form with air_bonus_pm strikes fliers harder: the Apiary's, the Sky Toll's; a
	# pulse that reaches fliers slows them, not stuns them)
	if int(sim_stats.get("air_bonus_pm", 0)) > 0:
		out["air_bonus"] = int(sim_stats["air_bonus_pm"]) / 1000.0
	if int(sim_stats.get("air_slow_pm", 0)) > 0:
		out["air_slow"] = int(sim_stats["air_slow_pm"]) / 1000.0
		out["air_slow_time"] = int(sim_stats.get("air_slow_t", 0)) / ticks
	return out


## The command tooltip's body for kit slot `slot` (0 to 2) of `builder`: the tower's line,
## its numbers (reaching `bonus_mm` farther: Keen Sight's; ignoring `pierce_c` more
## armour: Bronze Hand's, as form_stats() counts them) and both branches with the fork's
## price, what each gains and the check a patching branch lifts. One source for the
## in-game card's Q W E and the Builders screen (design 5.4). A branch line starts with
## FORK_MARK, never a letter: the card's keys are positional, Q and W take the branches
## and A signals, so "A" or "B" before a branch would read as the key to press.
func kit_tip(builder: String, slot: int, bonus_mm := 0, pierce_c := 0) -> String:
	var kind := SimContent.kit_tower(builder, slot)
	var data := form_stats(kind, -1, bonus_mm, pierce_c)
	var lines := PackedStringArray([str(data.get("description", ""))])
	var parts := PackedStringArray()
	# (an aura deals nothing and has no cooldown to show: it holds what is in reach)
	var aura := float(data["damage"]) <= 0.0 and (data.has("crack") or data.has("haste"))
	if float(data["damage"]) > 0.0:
		parts.append("Damage %s" % _tip_num(float(data["damage"])))
	parts.append("Range %s" % _tip_num(float(data["range"])))
	if not aura:
		parts.append("Cooldown %ss" % _tip_num(float(data["cooldown"])))
	if data.has("splash"):
		parts.append("Splash %s" % _tip_num(float(data["splash"])))
	if data.has("slow"):
		parts.append("Slow %d%%" % roundi(float(data["slow"]) * 100.0))
	if data.has("pierce") and not aura:
		# (a form's own, and Bronze Hand's on every hit; an aura strikes nothing to pierce)
		parts.append("Pierce %s" % _tip_num(float(data["pierce"])))
	if data.has("mark"):
		parts.append("Mark +%d%%" % roundi(float(data["mark"]) * 100.0))
	if data.has("stun"):
		parts.append("Stun %ss" % _tip_num(float(data["stun"])))
	if data.has("cloud"):
		parts.append("Cloud %s" % _tip_num(float(data["cloud"])))
	if data.has("crack"):
		parts.append("Crack %s" % _tip_num(float(data["crack"])))
	if data.has("haste"):
		parts.append("Haste +%d%%" % roundi(float(data["haste"]) * 100.0))
	if data.has("air_bonus"):
		parts.append("Fliers +%d%%" % roundi(float(data["air_bonus"]) * 100.0))
	if not data.has("haste"):
		# (a hum hastens towers: it reaches no creep, on the ground or in the air)
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


## How much more armour my towers ignore (Bronze Hand where perks are on, M6), hundredths.
func my_pierce_bonus() -> int:
	return sim.pierce_bonus(seat) if sim else 0


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


## What a fork branch that patches `check` does, in the coverage grades' words (design 3.3:
## strong, passable through a fork branch, weak) with "passable" said in plain words, the
## same on the in-match card and the Builders screen: "Lifts Armored from weak to passable:
## enough to hold it alone" (a fork lifts a weakness so far, never to strong; every Builder
## can win alone with the right forks, a balance gate).
func lifts_line(check: String) -> String:
	return "Lifts %s from weak to passable: enough to hold it alone" % CHECKS[check]["name"]


## The checks creep `kind` tests in itself, as its plate's glyph shows them: the check it
## brings, and Winged as well when it flies and brings another ([] for none). A boss's
## stand beside it in the wave list, so its row says whether it flies or wears armour.
func creep_checks(kind: String) -> Array:
	var out := []
	var check := str(CREEPS.get(kind, {}).get("check", ""))
	if CHECKS.has(check):
		out.append(check)
	if bool(SimContent.CREEPS.get(kind, {}).get("winged", false)) and not out.has("winged"):
		out.append("winged")
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


# ── The hollows (M6: two in a race, one in High Water and classic) ──


## Where hollow `h` stands in the world (tiles as the board's units).
static func hollow_origin(h: int) -> Vector3:
	return Vector3(HOLLOW_STRIDE * h, 0, 0)


## How many hollows the match plays: two in a race, else one.
func hollow_count() -> int:
	return sim.hollows.size() if sim else 1


## The hollow my seat defends, and my team.
func my_hollow() -> int:
	return _seat().hollow if sim else 0


func my_team() -> int:
	return _seat().team if sim else 0


## The other team's hollow in a race; -1 when my team plays alone.
func rival_hollow() -> int:
	if sim == null:
		return -1
	for h in sim.hollows:
		if h.team != my_team():
			return h.id
	return -1


## The hollow a board cell lies in, or -1 for the cliff band between them and outside.
func hollow_at(board: Vector2i) -> int:
	if sim == null or board.x < 0 or board.y < 0:
		return -1
	@warning_ignore("integer_division")
	var h := board.x / HOLLOW_STRIDE
	if h >= sim.hollows.size():
		return -1
	var road := sim.hollows[h].road
	return h if board.x - HOLLOW_STRIDE * h < road.width and board.y < road.depth else -1


## A cell of hollow `h` as the board counts it, and back.
static func board_cell(h: int, cell: Vector2i) -> Vector2i:
	return cell + Vector2i(HOLLOW_STRIDE * h, 0)


static func local_cell(h: int, board: Vector2i) -> Vector2i:
	return board - Vector2i(HOLLOW_STRIDE * h, 0)


## A point the simulation gives in millimetres on hollow `h`, on the ground of the world.
static func world_at(h: int, x_mm: int, z_mm: int) -> Vector3:
	return Vector3(x_mm / 1000.0, 0.0, z_mm / 1000.0) + hollow_origin(h)


# ── The race (M6, Tide Race: design 1.3, 5.7 and 5.8) ──


## Whether the match is a race: two teams, each on a hollow of its own. A duel, which plays
## the race's layout and may decide itself by the race's machinery, is never one here: its
## views are the duel's (is_duel()).
func is_race() -> bool:
	return sim != null and sim.race and not is_duel()


## The other team in a race; -1 when my team plays alone.
func rival_team() -> int:
	if not is_race():
		return -1
	return 1 - my_team() if sim.teams.size() == 2 else -1


## My team's outcome as the simulation decided it ("won", "lost" or "draw"), from
## SimMatch.outcomes(), one per team; "" while nothing is decided (a race until its win
## order is certain, any other match until it is over, and a match the server aborted).
func outcome() -> String:
	if sim == null:
		return ""
	var all := sim.outcomes()
	var team := my_team()
	if team < 0 or team >= all.size():
		return ""
	return OUTCOME_NAMES.get(int(all[team]), "")


## A race clock in ticks as people read it: "6:12", with "+20 s" when lost lives add to it.
static func race_clock(ticks: int, penalty_t := 0) -> String:
	@warning_ignore("integer_division")
	var seconds := maxi(0, ticks) / SimTypes.TICKS_PER_SECOND
	@warning_ignore("integer_division")
	var text := "%d:%02d" % [seconds / 60, seconds % 60]
	if penalty_t > 0:
		@warning_ignore("integer_division")
		text += " +%d s" % (penalty_t / SimTypes.TICKS_PER_SECOND)
	return text


## A team's race clock so far: the tick it cleared its last wave once it has (its race
## time, frozen), else the match's tick now; and what its lost lives add.
func race_clock_of(team: int) -> String:
	var t := sim.teams[team]
	var ticks := t.clear_tick if t.clear_tick >= 0 else sim.tick
	return race_clock(ticks, sim.race_penalty_t(team))


## The resource strip's second line in a race (design 5.7): the rival team's wave, lives
## and race clock so far with what its lost lives add ("Rival · Wave 7 · 18 lives · 6:12
## +20 s"); once its Holdfast went under, what I need to win ("Your rival fell on wave 9.
## Clear wave 9 to win"). "" outside a race.
func rival_line() -> String:
	var rival := rival_team()
	if rival < 0:
		return ""
	var t := sim.teams[rival]
	if t.fell_wave > 0:
		return "Your rival fell on wave %d. Clear wave %d to win" % [t.fell_wave, t.fell_wave]
	var h := sim.hollows[t.hollows[0]]
	var where := "Wave %d" % h.wave
	if h.phase == SimTypes.PHASE_DONE:
		where = "Wave %d cleared" % h.wave
	elif h.wave == 0:
		where = "Before wave 1"
	var lives := "%d %s" % [t.lives, "life" if t.lives == 1 else "lives"]
	return "Rival · %s · %s · %s" % [where, lives, race_clock_of(rival)]


## My team's race clock beside the rival line (design 1.3: "the strip shows both teams' race
## times as they go"): "You · 6:10 +10 s", its clock so far and what its lost lives add. ""
## outside a race and once a Holdfast fell: then clearing the wave it fell on decides, not
## the time.
func my_race_line() -> String:
	var rival := rival_team()
	if rival < 0:
		return ""
	var mine := my_team()
	if sim.teams[mine].fell_wave > 0 or sim.teams[rival].fell_wave > 0:
		return ""
	return "You · " + race_clock_of(mine)


## How a race is won, in a few words from mode `mode`'s rules (design 1.3's win order): "the
## lower time to clear wave 12 wins; each life lost adds 10 s", or `short` for a line with
## little room, "fastest clear of wave 12 wins, +10 s a life lost"; "" for a mode that is not
## a race.
static func race_rule_words(mode: String, short := false) -> String:
	var rules: Dictionary = SimContent.RULES.get(mode, {})
	if not rules.has("race"):
		return ""
	var waves := (SimContent.WAVES[rules["waves"]] as Array).size()
	var life := _seconds(int(rules["race"]["life_t"]))
	if short:
		return "fastest clear of wave %d wins, +%s a life lost" % [waves, life]
	return "the lower time to clear wave %d wins; each life lost adds %s" % [waves, life]


## The race's title from my team's view (design 5.8): "You Outran the Tide", "Your Rival
## Outran the Tide" or "Two Crews, One Time"; "" until it is decided.
func race_title() -> String:
	return str(RACE_TITLES.get(outcome(), "")) if is_race() else ""


## The rule that decided the race, in one line from my team's view (decided_by()): "You
## cleared wave 12 first", "Fewer lives lost: your race time is the lower" (a crew that
## cleared later, or on the same tick, and lost fewer lives), "Your rival fell on wave 9",
## "Twenty minutes: more waves cleared"; a draw names the rule that tied, which
## decided_by() does not say, from the teams' records (draw_rule_line()); "" until it is
## decided.
func race_rule_line() -> String:
	if not is_race():
		return ""
	var mine := my_team()
	var rival := rival_team()
	if rival < 0:
		return ""
	var by := sim.decided_by()
	var won := outcome() == "won"
	var me := sim.teams[mine]
	var them := sim.teams[rival]
	match by:
		"time":
			var winner := me if won else them
			var loser := them if won else me
			# (first only when strictly earlier: on the same tick lost lives decided it)
			var first := loser.clear_tick < 0 or winner.clear_tick < loser.clear_tick
			if first:
				return "%s wave %d first" % ["You cleared" if won else "Your rival cleared", total_waves()]
			return "%s: %s race time is the lower" % [
				"Fewer lives lost", "your" if won else "your rival's"
			]
		"fell":
			if me.fell_wave > 0 and them.fell_wave > 0:
				if me.fell_wave == them.fell_wave:
					return "Both fell on wave %d: %s more of it" % [
						me.fell_wave, "you killed" if won else "your rival killed"
					]
				return "Both fell: you on wave %d, your rival on wave %d" % [me.fell_wave, them.fell_wave]
			if won:
				return "Your rival fell on wave %d" % them.fell_wave
			return "You fell on wave %d" % me.fell_wave
		"cap":
			var minutes := _cap_words()
			if sim.cleared_waves(mine) != sim.cleared_waves(rival):
				return "%s: more waves cleared" % minutes
			if me.lives != them.lives:
				return "%s: more lives kept" % minutes
			return "%s: the lower race time" % minutes
		"draw":
			return draw_rule_line()
	return ""


## Which rule tied a drawn race (design 1.3), read from the records since decided_by()
## says only "draw": both Holdfasts fell on the same wave with as many of it killed; both
## crews cleared the last wave in the same race time; or at the cap, as many waves cleared
## and lives kept with no race time to tell them apart.
func draw_rule_line() -> String:
	var me := sim.teams[my_team()]
	var them := sim.teams[rival_team()]
	if me.fell_wave > 0 and them.fell_wave > 0:
		return "Both fell on wave %d with as many of its creeps killed" % me.fell_wave
	if sim.race_time(my_team()) >= 0 and sim.race_time(rival_team()) >= 0:
		return "Both cleared wave %d in the same race time" % total_waves()
	return "%s: as many waves cleared and lives kept" % _cap_words()


## The race's cap in words ("Twenty minutes", the rules' cap_t).
func _cap_words() -> String:
	@warning_ignore("integer_division")
	var minutes := int(sim.rules.get("cap_t", 0)) / (60 * SimTypes.TICKS_PER_SECOND)
	if minutes == 20:
		return "Twenty minutes"
	return "%d minutes" % minutes if minutes != 1 else "One minute"


## An EV_RACE (M6): a team cleared its last wave, fell, or the race was decided. The strip
## reads the records (rival_line()); the moments that are mine get their banner and sound.
func _on_race(e: Dictionary) -> void:
	race_changed.emit()
	if is_duel():
		return  # (a duel decided by the race's machinery: its banner and sound are _duel_decided's)
	var team := int(e.get("team", -1))
	match str(e.get("what", "")):
		"cleared":
			# (the first crew home sets the time to beat, design 1.3)
			if team == my_team():
				announce("All %d waves cleared · %s" % [total_waves(), race_clock_of(team)])
			else:
				announce("Your rival cleared all %d waves · %s" % [total_waves(), race_clock_of(team)])
		"fell":
			if team == my_team():
				announce("The Holdfast has gone under on wave %d" % int(e.get("wave", 0)))
			else:
				announce("Your rival fell on wave %d" % int(e.get("wave", 0)))
		"decided":
			announce(race_title())
			match outcome():
				"won":
					Sfx.play("victory")
				"lost":
					Sfx.play("defeat")


# ── The duel (M7, Undertow: design 1.4 and 5.7, contract-m7.md §3) ──
#
# The duel's rules are SimUndertow's (scripts/sim/sim_undertow.gd) and SimMatch's duel
# calls; everything here reads them directly. One clock for both hollows: a wave runs from
# the shared horn (SimMatch.horn_tick) until the last hollow clears it (SimUndertow.
# wave_running), so my hollow may stand in its window while the rival's still plays the wave
# my bottle holds back; corks go in only while the window is open for both
# (SimUndertow.window_open) and the Drift has drawn it (SimMatch.drift_window).

## The Drift's packs by map, then by the CHECK_IDS id a pack tests (SimContent.PACKS'
## keys, contract-m7.md §1): the name the tray shows and its icon, the portrait of the
## creep it sends with a bottle on it (art_src/ui/icons.py). No map's flavour reaches an id.
const PACKS := {
	"hollow":
	{
		"swarm": {"name": "Gourd Rush", "icon": "res://ui/icons/pack_hollow_swarm.png"},
		"swift": {"name": "Scuttle", "icon": "res://ui/icons/pack_hollow_swift.png"},
		"armored": {"name": "Thorn Herd", "icon": "res://ui/icons/pack_hollow_armored.png"},
		"winged": {"name": "Moth Cloud", "icon": "res://ui/icons/pack_hollow_winged.png"},
	},
}
## A corked bottle as the tray shows it (sea glass, corked and sealed), the Seawall's icon
## beside its F key, and the small bottle that glints over an uncorked creep.
const BOTTLE_ICON := "res://ui/icons/bottle.png"
const SEAWALL_ICON := "res://ui/icons/seawall.png"
const BOTTLE_MODEL := "res://models/ui/corked_bottle.glb"
## The duel's titles by my outcome (design 5.8, contract-m7.md §3).
const DUEL_TITLES := {
	"won": "The Tide Took Your Rival",
	"lost": "The Tide Took You",
	"draw": "Even Tide",
}
## The tiers as the tray and the rival's bottles name them.
const TIER_NAMES := ["I", "II", "III"]
## How long an uncorking the client sent by itself waits after a refusal (the cork still
## holding after a resync) before it goes again.
const UNCORK_RETRY_T := 30
## Why no cork goes out while one may still be on its way (_cork_unsure).
const CORK_UNSURE := "Your last cork is still on its way"
## Why Space opens nothing when my bottle of the wave stands but this game no longer holds its
## salt (a game started again offline, or a salts' file gone): it fizzles at fizzle_t.
const SALT_LOST := "That bottle's salt is lost: it will fizzle"
## Why no cork goes out while my hollow stands in its window but the rival's still plays the
## wave (the window opens for both together: SimUndertow.window_open); and why no Ready does
## then (ready_refusal).
const WINDOW_SHUT := "The window opens once both waves are over"
## A duel's order whose turn came when its moment had passed (REFUSE_WRONG_PHASE: a cork
## sent in the window's last ticks runs after the horn; an uncorking or a Seawall after the
## wave's end), and any order once my hollow is done, by command: refusal_text.
const WRONG_MOMENT := {
	SimTypes.CMD_CORK: "The horn sounded before your cork went in",
	SimTypes.CMD_UNCORK: "The wave was over before your uncorking went in",
	SimTypes.CMD_SEAWALL: "The wave was over before your Seawall went in",
	SimTypes.CMD_BUILD: MATCH_OVER,
	SimTypes.CMD_FORK: MATCH_OVER,
	SimTypes.CMD_SELL: MATCH_OVER,
	SimTypes.CMD_SIGNAL: MATCH_OVER,
}
## The events that name the seq of an order of mine that ran (or was refused): _order_ran.
const ORDER_EVENTS := [
	SimTypes.EV_BUILT, SimTypes.EV_FORKED, SimTypes.EV_SOLD, SimTypes.EV_READY, SimTypes.EV_REJECTED
]

## My corks (contract-m7.md §3), by bottle id once the CORK ran: {"pack" (its CHECK_IDS
## id), "window", "tier", "hi", "lo" (the salt's halves), "uncork" (the UNCORK on its way,
## its seq, or -1), "retry" (no uncorking by itself before this tick), "seq" (its CORK's)},
## the id the loaded world gives the bottle the salt opens (_rekey_corks); and the CORKs still
## waiting for their turn, oldest first, by seq, each "unsure" once the link went or the turns
## jumped while it waited (its turn may still come, or never). The salt is 8 random bytes
## from Crypto and stays on this machine until the UNCORK reveals it; it outlives a lost link
## and a resync (attach() keeps it for the same match), and in a networked match a game
## killed or closed and started again (the salts' file, _keep_salts), not the match.
var _corks := {}
var _corks_waiting: Array = []
## UNCORKs waiting for their turn: seq -> bottle id; the seqs of those the client sent by
## itself (a refusal of one is not the player's); the SEAWALL on its way.
var _uncorks := {}
var _quiet := {}
var _seawall_seq := -1
## Bottles of mine that took their salt by commitment before their EV_CORK was handled (a
## CORK and the horn in one frame of several ticks, _drop_stale): the event still to come
## says the cork, as one that finds its waiting cork does.
var _unheard := {}
## The latest seq of mine an event named (EV_BUILT, EV_FORKED, EV_SOLD, EV_READY,
## EV_REJECTED). My orders run in their seq's order, so a duel order of mine still waiting
## below it never got its turn (a link that dropped it): _order_ran lets it go.
var _seq_ran := 0
## The match a networked game files my salts under (user://duel/<match>-<seat>.cfg; attach()
## takes it from the MatchClient), 0 offline, where a match never outlives its game.
var salt_match := 0
## A test's seam (tests/ui/duel_stage.gd): when valid, each cork's 8 bytes come from it
## instead of Crypto, so a scenario's commitments come out alike on every run (--determinism
## compares state hashes, and the bottles' commits are the match's). Never set in play.
var salt_source := Callable()
## Which match the corks belong to, and whether its decision was announced.
var _duel_key := ""
var _duel_said := false


## Whether the match is a duel (SimMatch.duel: its rules carry Undertow's duel block).
func is_duel() -> bool:
	return sim != null and sim.duel


## The rules' duel block (contract-m7.md §2), {} outside a duel.
func duel_rules() -> Dictionary:
	return SimUndertow.rules_of(sim) if is_duel() else {}


## My commitment to `pack` (a CHECK_IDS index) in `window` with the salt's halves:
## SimUndertow.commit's [b, c], or [] without a match.
func duel_commit(window: int, pack: int, salt_hi: int, salt_lo: int) -> Array:
	if sim == null:
		return []
	return SimUndertow.commit(sim.match_seed, seat, window, pack, salt_hi, salt_lo)


## The tick the latest shared horn sounded on (SimMatch.horn_tick), -1 before the first.
func horn_tick() -> int:
	return sim.horn_tick if is_duel() else -1


## Whether the duel's wave runs: from the shared horn until the last hollow clears it, so
## on my hollow too while it already stands in its window (SimUndertow.wave_running).
func duel_wave() -> bool:
	return is_duel() and SimUndertow.wave_running(sim)


## Why a Ready of mine would be refused before it goes out, where the reason is the duel's
## ("" otherwise): while my hollow stands in its window and the rival's still plays the wave,
## the window has not opened for both, and a Ready said now would sound the horn the moment
## it did, as soon as the caretaker or the rival said theirs, spending my window before I
## had it (playtest halv s1, f105004 to f105364; design 1.4: Ready in a duel's wave stays
## refused). D, N, Space and the card's horn all ask this.
func ready_refusal() -> String:
	if state == State.PREP and duel_wave():
		return WINDOW_SHUT
	return ""


## Whether the window is open for both hollows and the Drift has drawn it: corks go in only
## then (SimUndertow.window_open, SimMatch.drift_window).
func cork_window() -> bool:
	return is_duel() and SimUndertow.window_open(sim) and sim.drift_window == duel_window()


## The Surge's wave (1 to 3) that runs now or that the open window precedes, else 0
## (SimUndertow.surge_of: windows and waves 13 to 15).
func surge() -> int:
	if not is_duel():
		return 0
	var h := _hollow()
	var next := h.phase == SimTypes.PHASE_PREP and not SimUndertow.wave_running(sim)
	return SimUndertow.surge_of(sim, h.wave + 1 if next else h.wave)


## Wave `number` (the match's, 1-based) as the views name it: "Wave 9", and in a duel's
## Surge by the Surge, as the strip does ("Surge 2/3" for wave 14), never "Wave 14".
func wave_name(number: int) -> String:
	var n := SimUndertow.surge_of(sim, number) if is_duel() else 0
	return "Surge %d/%d" % [n, surge_waves()] if n > 0 else "Wave %d" % number


## How many waves the Surge plays (the rules' surge waves), 0 outside a duel.
func surge_waves() -> int:
	return (duel_rules()["surge"]["waves"] as Array).size() if is_duel() else 0


## Before each tick (main.gd's loop): the uncorking the client does by itself at
## auto_uncork_t after the horn (design 1.4), sent on the tick it falls due at any
## fast-forward, and the duel orders whose turn can no longer come let go.
func before_tick() -> void:
	if not is_duel():
		return
	_drop_stale()
	_auto_uncork()


## Duel orders whose turn can no longer come: a CORK waiting for a window this one has passed
## (every turn before now has run, and one after it is refused), a SEAWALL once the wave is over.
## A CORK whose bottle stands is not one of them, though its EV_CORK has not been handled yet:
## main.gd hands the events over once a frame, so in a frame of several ticks the horn may
## sound after the cork ran and before its event is read. Before anything is dropped, a
## standing bottle of mine takes the waiting salt it was committed with (_claim_corked).
func _drop_stale() -> void:
	var window := duel_window()
	for w: Dictionary in _corks_waiting:
		if int(w["window"]) < window:
			_claim_corked(true)
			break
	var kept := []
	for w: Dictionary in _corks_waiting:
		if int(w["window"]) < window:
			settled.emit(int(w["seq"]), false)
		else:
			kept.append(w)
	if kept.size() != _corks_waiting.size():
		_corks_waiting = kept
		_keep_salts()
		duel_changed.emit()
	if _seawall_seq >= 0 and _hollow().phase != SimTypes.PHASE_WAVE:
		settled.emit(_seawall_seq, false)
		_seawall_seq = -1
		duel_changed.emit()


## My bottles of the wave running are uncorked from auto_uncork_t after the horn, while the
## duel's wave runs on either hollow (mine may have cleared it while the rival's road still
## waits for my pack, in the Surge's last wave with my hollow done) and before the fizzle.
## The UNCORK goes out at auto_uncork_send_tick(), so it runs by auto_uncork_t however far
## this game runs behind the turns it holds.
func _auto_uncork() -> void:
	if not duel_wave() or _uncork_order_refusal() != "" or not can_command():
		return
	if sim.tick < auto_uncork_send_tick():
		return
	for b: Dictionary in my_bottles():
		if b["due"] and b["known"] and int(b["uncork"]) < 0 and sim.tick >= int(b["retry"]):
			var seq := _send_uncork(int(b["id"]))
			if seq >= 0:
				_quiet[seq] = true


# ── The duel's records, for the tray and the bar ──


## The bottles of seat `n` as the simulation keeps them (contract-m7.md §2: {id, tier,
## window, uncorked, fizzled}, the pack only once uncorked), oldest first.
func bottles_of(n: int) -> Array:
	return sim.bottles(n) if is_duel() else []


## My bottles still corked, oldest first, with what only this client knows: {"id" (-1
## while its CORK waits for its turn), "tier", "window", "pack" (its CHECK_IDS id, "" when
## this client does not hold its salt), "known", "caretaker" (the caretaker corked it while
## my seat was away: salt 0, its pack in plain sight, SimUndertow.salt_zero_pack; it uncorks
## it itself at uncork_after_t), "uncork" (its UNCORK's seq on the way, or -1), "retry",
## "waiting", "due" (it is the wave running's: SimUndertow.pending, until the fizzle),
## "auto" (the tick it is uncorked by itself while due: the client's at auto_uncork_t, the
## caretaker's at uncork_after_t; else -1), "fizzle" (the tick it fizzles without a reveal
## while due, else -1)}.
func my_bottles() -> Array:
	var out := []
	if not is_duel():
		return out
	var due := {}
	for b: SimRecords.SimBottle in SimUndertow.pending(sim, seat):
		due[b.id] = true
	var rules := duel_rules()
	for b: SimRecords.SimBottle in sim.bottle_list:
		if b.seat != seat or b.uncorked or b.fizzled:
			continue
		var mine: Dictionary = _corks.get(b.id, {})
		var pack := str(mine.get("pack", ""))
		var keeper := -1 if not mine.is_empty() else SimUndertow.salt_zero_pack(sim, b)
		if keeper >= 0:
			pack = SimContent.CHECK_IDS[keeper]
		var now := due.has(b.id)
		var auto := -1
		if now:
			auto = sim.uncork_tick() if keeper >= 0 else sim.horn_tick + int(rules["auto_uncork_t"])
		out.append(
			{
				"id": b.id, "tier": b.tier, "window": b.window, "pack": pack, "known": not mine.is_empty(),
				"caretaker": keeper >= 0, "uncork": int(mine.get("uncork", -1)),
				"retry": int(mine.get("retry", 0)), "waiting": false, "due": now, "auto": auto,
				"fizzle": sim.horn_tick + int(rules["fizzle_t"]) if now else -1,
			}
		)
	for w: Dictionary in _corks_waiting:
		if int(w["window"]) != duel_window():
			continue  # (a cork whose window has passed never stands: _drop_stale lets it go)
		out.append(
			{
				"id": -1, "tier": int(w["tier"]), "window": int(w["window"]), "pack": str(w["pack"]),
				"known": true, "caretaker": false, "uncork": -1, "retry": 0, "waiting": true, "due": false,
				"auto": -1, "fizzle": -1,
			}
		)
	return out


## The rival's bottles still corked, oldest first: {"id", "tier", "window", "due" (its wave
## runs: it may be uncorked on my road now)}, never a pack (SimMatch.bottles holds none).
func rival_bottles() -> Array:
	var out := []
	var rival := duel_seat(1 - my_team()) if is_duel() else -1
	if rival < 0:
		return out
	var due := {}
	for b: SimRecords.SimBottle in SimUndertow.pending(sim, rival):
		due[b.id] = true
	for b: Dictionary in bottles_of(rival):
		if not bool(b["uncorked"]) and not bool(b["fizzled"]):
			out.append({"id": int(b["id"]), "tier": int(b["tier"]), "window": int(b["window"]), "due": due.has(int(b["id"]))})
	return out


## Why my hollow's wave stands with its road empty: it waits on the rival alone
## (SimMatch.wave_held: a rival's bottle for it still corked, up to the fizzle, or its
## uncorked pack still to come), so the strip does not say "0 creeps left" with nothing
## happening; "" otherwise.
func held_line() -> String:
	if not is_duel() or not sim.wave_held(my_hollow()):
		return ""
	for b: Dictionary in rival_bottles():
		if b["due"]:
			return "your rival's bottle is still corked"
	return "your rival's pack is still to come"


## The seat team `team` plays in a duel (one each), or -1.
func duel_seat(team: int) -> int:
	if sim == null:
		return -1
	for s in sim.seats:
		if s.team == team:
			return s.seat
	return -1


## One side of the duel bar (design 1.4): {"team", "seat", "lives", "breach" (the lives its
## uncorked creeps took from the other side), "stipend" (gold a wave), "charges" (Seawall),
## "ready_tick" (when the Seawall may burst again), "to_charge" (lives still to lose before
## the next charge, SimUndertow.lives_lost's count; 0 while it holds the most)}.
func duel_side(team: int) -> Dictionary:
	var n := duel_seat(team)
	var s: SimRecords.SimSeat = sim.seat(n) if sim and n > 0 else null
	var to_charge := 0
	if s != null and is_duel():
		var wall: Dictionary = duel_rules()["seawall"]
		if s.seawall_charges < int(wall["charges"]):
			to_charge = maxi(1, int(wall["every_lives"]) - s.seawall_lost)
	return {
		"team": team,
		"seat": n,
		"lives": sim.teams[team].lives if sim and team >= 0 and team < sim.teams.size() else 0,
		"breach": sim.breach_dealt(team) if sim else 0,
		"stipend": sim.stipend(n) if sim else 0,
		"charges": sim.seawall_charges(n) if sim else 0,
		"ready_tick": sim.seawall_ready_tick(n) if sim else 0,
		"to_charge": to_charge,
	}


## The Seawall in the duel's words, from the rules' seawall block (design 1.4): what F does
## and how it charges, "F, during a wave: surf bursts up round your Holdfast ...".
func seawall_rule_text() -> String:
	if not is_duel():
		return ""
	var wall: Dictionary = duel_rules()["seawall"]
	var reach := _tenths(roundi(int(wall["radius_mm"]) / 100.0))
	var share := roundi(int(wall["hp_pm"]) / 10.0)
	var boss_share := roundi(int(wall["boss_hp_pm"]) / 10.0)
	var boss_slow := roundi(int(wall["boss_slow_pm"]) / 10.0)
	return (
		"F, during a wave: surf bursts up round your Holdfast, and every creep within %s tiles of it is stunned for %s and loses %d%% of its health; a boss loses %d%% and is slowed %d%% instead. A charge for every %d lives you lose, at most %d; after a burst the next may come %s later."
		% [
			reach, _seconds(int(wall["stun_t"])), share, boss_share, boss_slow, int(wall["every_lives"]),
			int(wall["charges"]), _seconds(int(wall["cooldown_t"]))
		]
	)


## Ticks as the copy says them: "3 s", "2.5 s".
static func _seconds(ticks: int) -> String:
	if ticks % SimTypes.TICKS_PER_SECOND == 0:
		@warning_ignore("integer_division")
		return "%d s" % (ticks / SimTypes.TICKS_PER_SECOND)
	return "%.1f s" % (ticks / float(SimTypes.TICKS_PER_SECOND))


## Tenths as the copy says them: 30 is "3", 25 is "2.5".
static func _tenths(tenths: int) -> String:
	if tenths % 10 == 0:
		@warning_ignore("integer_division")
		return str(tenths / 10)
	return "%.1f" % (tenths / 10.0)


## The window the Drift tray speaks of: in a build window the wave it precedes, during a
## wave the next one; 0 outside a duel.
func duel_window() -> int:
	return _hollow().wave + 1 if is_duel() else 0


## The tier (0 to 2) a cork takes in `window` (SimUndertow.tiers_in: the Surge's windows
## take the tier of the wave they repeat); -1 before the Drift opens.
func duel_tier(window: int) -> int:
	if not is_duel() or window < int(duel_rules()["drift_from"]):
		return -1
	var tiers := SimUndertow.tiers_in(sim, window)
	return tiers[0] if not tiers.is_empty() else -1


## A cork's price in `window` (SimUndertow.cork_price: the Surge's at cork_price_pm of it);
## 0 without a Drift.
func cork_price(window: int) -> int:
	var t := duel_tier(window)
	return SimUndertow.cork_price(sim, t, window) if t >= 0 else 0


## The stipend a pack of `window`'s tier adds once uncorked, gold a wave: none in the Surge,
## whose stipends are still paid but no longer grow.
func stipend_gain(window: int) -> int:
	var t := duel_tier(window)
	if t < 0 or SimUndertow.surge_of(sim, window) > 0:
		return 0
	return SimUndertow.tier_stipend(sim, t)


## How many packs a seat may cork in `window` (SimUndertow.corks_allowed).
func corks_allowed(window: int) -> int:
	return SimUndertow.corks_allowed(sim, window) if is_duel() else 0


## Corks I have left in the tray's window (those waiting for their turn in it count).
func corks_left() -> int:
	if not is_duel():
		return 0
	var window := duel_window()
	var taken := SimUndertow.corks_of(sim, seat, window)
	for w: Dictionary in _corks_waiting:
		if int(w["window"]) == window:
			taken += 1
	return maxi(0, corks_allowed(window) - taken)


## The Drift's packs for the tray's window as CHECK_IDS ids, in CHECK_IDS order: the
## simulation's (SimMatch.drift_offer) once the window is open for both hollows and drawn;
## [] before drift_from, during the wave and while the rival's hollow still plays it.
func drift_packs() -> Array:
	if not cork_window():
		return []
	return sim.drift_offer()


## A pack as the tray shows it at tier `tier`: {"check", "name", "icon", "creep" (the
## kind it sends), "count"}.
func pack_info(check: String, tier: int) -> Dictionary:
	var map := str(sim.rules.get("map", "hollow")) if sim else "hollow"
	var shown: Dictionary = PACKS.get(map, PACKS["hollow"]).get(check, {})
	var rules: Dictionary = SimContent.PACKS.get(map, {}).get(check, {})
	var counts: Array = rules.get("counts", [0])
	return {
		"check": check,
		"name": str(shown.get("name", check.capitalize())),
		"icon": str(shown.get("icon", "")),
		"creep": str(rules.get("creep", "")),
		"count": int(counts[clampi(tier, 0, counts.size() - 1)]),
	}


# ── Corking, uncorking and the Seawall from this client ──


## Why corking `check` now would be refused before it goes out ("" when it may): the
## orders' own refusal, outside a build window of the Drift or a pack not in it, no cork
## left, short of gold.
func cork_refusal(check: String) -> String:
	if not is_duel():
		return "Not in a duel"
	var why := order_refusal()
	if why != "":
		return why
	if duel_tier(duel_window()) < 0:
		return "The Drift opens before wave %d" % int(duel_rules()["drift_from"])
	if state != State.PREP:
		return "Cork in the build window"
	if not cork_window():
		return WINDOW_SHUT
	if not drift_packs().has(check):
		return "That pack is not in the Drift now"
	if _cork_unsure():
		return CORK_UNSURE
	if corks_left() <= 0:
		return NOTICES[SimTypes.REFUSE_NO_CORKS_LEFT]
	if not can_afford(cork_price(duel_window())):
		return NOTICES[SimTypes.REFUSE_NOT_ENOUGH_GOLD]
	return ""


## Corks `check` from the tray's packs: a salt of 8 random bytes from Crypto, my commitment
## to the pack with it (SimUndertow.commit), and CORK(tier, b, c) for the next turn. The
## salt stays here until the uncorking. Returns the CORK's seq, or -1.
func cork(check: String) -> int:
	if cork_refusal(check) != "":
		return -1
	var salt := _new_salt()
	var hi := _i32(salt, 0)
	var lo := _i32(salt, 4)
	var window := duel_window()
	var tier := duel_tier(window)
	var c := duel_commit(window, SimContent.CHECK_IDS.find(check), hi, lo)
	if c.size() != 2:
		return -1
	var seq := command(SimTypes.CMD_CORK, tier, int(c[0]), int(c[1]))
	if seq >= 0:
		_corks_waiting.append(
			{"seq": seq, "pack": check, "window": window, "tier": tier, "hi": hi, "lo": lo, "unsure": false}
		)
		_keep_salts()  # (before its turn: a game killed now may still see the bottle stand)
		duel_changed.emit()
	return seq


## A cork's 8 bytes: from Crypto, or from a test's salt_source.
func _new_salt() -> PackedByteArray:
	if salt_source.is_valid():
		var made: Variant = salt_source.call()
		if made is PackedByteArray and (made as PackedByteArray).size() == 8:
			return made
	return Crypto.new().generate_random_bytes(8)


## Whether a cork of mine waits whose turn may never come (the link went while it waited).
## No other cork goes out meanwhile: until it is known whether it stood, the tray cannot
## say how many corks the window has left or what they cost me. It is known soon: its
## EV_CORK (by its seq), its refusal, a later order of mine running (_order_ran), a world
## loaded past its turn holding its bottle (_claim_corked, by commitment), or its window's end.
func _cork_unsure() -> bool:
	for w: Dictionary in _corks_waiting:
		if bool(w.get("unsure", false)):
			return true
	return false


## The bottle Space uncorks now: my oldest corked for the wave running (SimUndertow.pending:
## the duel's wave runs on either hollow, before the fizzle) whose salt is here and whose
## UNCORK is not on its way; -1 for none.
func next_to_uncork() -> int:
	if not duel_wave():
		return -1
	for b: Dictionary in my_bottles():
		if b["due"] and b["known"] and int(b["uncork"]) < 0:
			return int(b["id"])
	return -1


## Whether a bottle of mine is corked for the wave running (whether or not this client holds
## its salt, or its UNCORK is on its way): Space speaks of uncorking until it is gone.
func corked_for_wave() -> bool:
	for b: Dictionary in my_bottles():
		if b["due"]:
			return true
	return false


## Why uncorking bottle `id` (-1: the next, next_to_uncork()) would be refused before it
## goes out ("" when it may): the orders' refusal (but for my hollow done while the duel's
## wave still runs undecided: _uncork_order_refusal), outside the duel's wave, nothing corked
## for it, the cork holding for uncork_after_t after the horn.
func uncork_refusal(id := -1) -> String:
	if not is_duel():
		return "Not in a duel"
	var why := _uncork_order_refusal()
	if why != "":
		return why
	if not duel_wave():
		return "Uncork during the wave"
	var bottle := id if id >= 0 else next_to_uncork()
	var corked := false
	var lost := false
	for b: Dictionary in my_bottles():
		corked = corked or (bottle >= 0 and int(b["id"]) == bottle and b["due"] and b["known"])
		# (Space speaks of any bottle of the wave whose salt is gone, a click of its own)
		var gone: bool = b["due"] and not b["known"] and not b["caretaker"]
		lost = lost or (gone and (id < 0 or int(b["id"]) == id))
	if not corked:
		return SALT_LOST if lost else NOTICES[SimTypes.REFUSE_NOTHING_CORKED]
	if sim.tick < sim.uncork_tick():
		return refusal_text(SimTypes.REFUSE_TOO_EARLY)
	return ""


## The tick of this game's simulation the client's own uncorking goes out on (-1 before the
## first horn): auto_uncork_t after the horn, less the ticks an order sent now runs ahead of
## the simulation (TurnSource.order_lead: online the turns held and not run yet), so a game
## running behind the server's turns sends it early enough to run by auto_uncork_t, its trip
## there and back left in the margin to fizzle_t; never before uncork_after_t.
func auto_uncork_send_tick() -> int:
	if not is_duel() or sim.horn_tick < 0:
		return -1
	var lead := source.order_lead(sim) if source != null else 0
	return maxi(sim.uncork_tick(), sim.horn_tick + int(duel_rules()["auto_uncork_t"]) - lead)


## The orders' own refusal (order_refusal()) as an uncorking meets it: my hollow done does not
## end the duel for my bottles. In the Surge's last wave my hollow may clear while the rival's
## still waits for my bottle (SimUndertow.holds), and the simulation takes its UNCORK until the
## duel is decided (a fall decides at once), so while the duel's wave runs undecided the
## match is not over for an uncorking; every other order still is (over()).
func _uncork_order_refusal() -> String:
	if state == State.WON and accepts_commands() and not sim.over and outcome() == "" and duel_wave():
		return NOTICES[SimTypes.REFUSE_CARETAKEN] if caretaken() else ""
	return order_refusal()


## Uncorks bottle `id` (-1: the next): UNCORK(pack, salt_hi, salt_lo) for the next turn.
## Returns its seq, or -1.
func uncork(id := -1) -> int:
	var bottle := id if id >= 0 else next_to_uncork()
	if uncork_refusal(bottle) != "":
		return -1
	return _send_uncork(bottle)


func _send_uncork(id: int) -> int:
	var b: Dictionary = _corks.get(id, {})
	if b.is_empty() or int(b["uncork"]) >= 0:
		return -1
	var seq := command(SimTypes.CMD_UNCORK, SimContent.CHECK_IDS.find(str(b["pack"])), int(b["hi"]), int(b["lo"]))
	if seq >= 0:
		b["uncork"] = seq
		_uncorks[seq] = id
		duel_changed.emit()
	return seq


## Why bursting a Seawall now would be refused ("" when it may): the orders' refusal,
## outside a duel's wave, no charge, the last one still standing.
func seawall_refusal() -> String:
	if not is_duel():
		return "Not in a duel"
	var why := order_refusal()
	if why != "":
		return why
	if state != State.WAVE:
		return "The Seawall bursts during a wave"
	var mine := duel_side(my_team())
	if int(mine["charges"]) <= 0:
		return NOTICES[SimTypes.REFUSE_NO_CHARGE]
	if sim.tick < int(mine["ready_tick"]) or _seawall_seq >= 0:
		return NOTICES[SimTypes.REFUSE_SEAWALL_STANDING]
	return ""


## F: a Seawall round my Holdfast, SEAWALL for the next turn. Returns its seq, or -1.
func seawall() -> int:
	if seawall_refusal() != "":
		return -1
	var seq := command(SimTypes.CMD_SEAWALL)
	if seq >= 0:
		_seawall_seq = seq
		duel_changed.emit()
	return seq


## Forgets the corks: a new match (main.gd's begin offline, detach()). The salts' file
## stays: a game closed mid-match takes its seat back when it starts again.
func forget_duel() -> void:
	salt_match = 0
	salt_source = Callable()
	_forget_corks()


func _forget_corks() -> void:
	_corks.clear()
	_corks_waiting.clear()
	_uncorks.clear()
	_quiet.clear()
	_unheard.clear()
	_seawall_seq = -1
	_seq_ran = 0
	_duel_key = ""
	_duel_said = false


## Orders whose turn may never come (BuildController.forget_pending: the link went, the turns
## jumped, the match ended). The Seawall and the uncorkings may go again: one whose turn did
## come is refused by the rules (an uncorking the client sends by itself unheard). A cork keeps
## its salt, since its turn may still come in the turns run again, but is unsure: no other
## cork goes out until it is known (_cork_unsure).
func forget_duel_orders() -> void:
	_seawall_seq = -1
	for seq: int in _uncorks.keys():
		var id := int(_uncorks[seq])
		if _corks.has(id) and int(_corks[id]["uncork"]) == seq:
			_corks[id]["uncork"] = -1
			_corks[id]["retry"] = 0
	_uncorks.clear()
	for w: Dictionary in _corks_waiting:
		w["unsure"] = true
	duel_changed.emit()


## An order of mine with `seq` ran (its event named it). My orders run in their seq's order,
## so a duel order still waiting below it never got its turn: it goes, its gold no longer held
## back (settled), an uncorking free to go again.
func _order_ran(seq: int) -> void:
	if seq <= _seq_ran:
		return
	_seq_ran = seq
	var changed := false
	var kept := []
	for w: Dictionary in _corks_waiting:
		if int(w["seq"]) < seq:
			settled.emit(int(w["seq"]), false)
		else:
			kept.append(w)
	if kept.size() != _corks_waiting.size():
		_corks_waiting = kept
		_keep_salts()
		changed = true
	for lost: int in _uncorks.keys():
		if lost < seq:
			var id := int(_uncorks[lost])
			_uncorks.erase(lost)
			_quiet.erase(lost)
			if _corks.has(id) and int(_corks[id]["uncork"]) == lost:
				_corks[id]["uncork"] = -1
				_corks[id]["retry"] = 0
			settled.emit(lost, false)
			changed = true
	if _seawall_seq >= 0 and _seawall_seq < seq:
		settled.emit(_seawall_seq, false)
		_seawall_seq = -1
		changed = true
	if changed:
		duel_changed.emit()


## attach(): the corks stay for the same match (a resync, a rejoin); a game started again
## takes them from the salts' file. Each salt goes to the bottle of the loaded world it opens
## (_rekey_corks), and a bottle the loaded world holds whose EV_CORK this client never saw
## takes the waiting salt it was committed with (_claim_corked). A world loaded in the middle
## of a wave keeps its horn in the record (SimMatch.horn_tick), so the uncorking at 24 s holds.
func _attach_duel() -> void:
	var client := _scene_client()
	if client != null and client.match_id > 0:
		salt_match = client.match_id
	var key := "%s:%d:%d" % [sim.mode, sim.match_seed, seat]
	if key != _duel_key:
		_forget_corks()
		_duel_key = key
		_restore_salts()
	if not is_duel():
		return
	_rekey_corks()
	_claim_corked()
	_duel_said = outcome() != ""


## My salts, by the bottle of the loaded world each opens: of its window, the bottle of mine
## whose commit its pack and salt give (SimUndertow.commit), never the id it was kept under.
## A world loaded under the same match may number its bottles otherwise than the one this
## client ran (a RESYNC(desync): a build that stood here and was refused there shifts
## next_id), and a salt left under another id would show my bottle "lost" (it fizzles) or
## open the wrong one. A salt whose bottle that world holds uncorked or fizzled is spent; one
## no bottle there holds waits for its CORK again, unsure: the turns run again may bring it
## (its EV_CORK by its seq, or _claim_corked), or its window ends (_drop_stale).
func _rekey_corks() -> void:
	if _corks.is_empty():
		return
	var keyed := {}
	var moved := {}  # (the id a salt was kept under -> its bottle's id in this world)
	var changed := false
	for id: int in _corks:
		var c: Dictionary = _corks[id]
		var window := int(c["window"])
		var commit := duel_commit(window, SimContent.CHECK_IDS.find(str(c["pack"])), int(c["hi"]), int(c["lo"]))
		var opens: SimRecords.SimBottle = null
		for b: SimRecords.SimBottle in sim.bottle_list:
			if b.seat == seat and b.window == window and commit.size() == 2 and b.commit_hi == int(commit[0]) and b.commit_lo == int(commit[1]):
				opens = b
				break
		if opens == null:
			_corks_waiting.append(
				{
					"seq": int(c.get("seq", 0)), "pack": c["pack"], "window": window, "tier": int(c["tier"]),
					"hi": int(c["hi"]), "lo": int(c["lo"]), "unsure": true,
				}
			)
			changed = true
		elif opens.uncorked or opens.fizzled:
			changed = true  # (spent there)
		else:
			keyed[opens.id] = c
			moved[id] = opens.id
			changed = changed or opens.id != id
	if not changed:
		return
	_corks = keyed
	_corks_waiting.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a["seq"]) < int(b["seq"]))
	for seq: int in _uncorks.keys():
		var id := int(_uncorks[seq])
		if moved.has(id):
			_uncorks[seq] = moved[id]
		else:
			_uncorks.erase(seq)  # (its bottle is spent, or not corked in this world)
			_quiet.erase(seq)
			settled.emit(seq, false)
	var unheard := {}
	for id: int in _unheard:
		if moved.has(id):
			unheard[moved[id]] = true
	_unheard = unheard
	_keep_salts()
	duel_changed.emit()


## Bottles of mine still corked with no salt here, whose CORK ran in turns this client did not
## run itself (a checkpoint loaded past it), take the waiting cork whose commitment they hold:
## of their window, its pack and salt giving the bottle's commit (SimUndertow.commit), so a
## bottle the caretaker corked for my seat while it was away (salt 0) never takes the salt
## of a cork of mine the link lost. Oldest waiting first, to the lowest id. `unheard`: the
## bottles' EV_CORK is still to be handled this frame (_drop_stale), and says the cork then.
func _claim_corked(unheard := false) -> void:
	var claimed := false
	for b: SimRecords.SimBottle in sim.bottle_list:
		if b.seat != seat or b.uncorked or b.fizzled or _corks.has(b.id):
			continue
		for i in _corks_waiting.size():
			var w: Dictionary = _corks_waiting[i]
			if int(w["window"]) != b.window:
				continue
			var c := duel_commit(b.window, SimContent.CHECK_IDS.find(str(w["pack"])), int(w["hi"]), int(w["lo"]))
			if c.size() == 2 and int(c[0]) == b.commit_hi and int(c[1]) == b.commit_lo:
				_corks_waiting.remove_at(i)
				_corks[b.id] = {
					"pack": w["pack"], "window": int(w["window"]), "tier": int(w["tier"]),
					"hi": int(w["hi"]), "lo": int(w["lo"]), "uncork": -1, "retry": 0, "seq": int(w["seq"]),
				}
				if unheard:
					_unheard[b.id] = true
				settled.emit(int(w["seq"]), true)
				claimed = true
				break
	if claimed:
		_keep_salts()
		duel_changed.emit()


# ── The salts' file (a networked match: a game started again takes its seat back) ──


func _salt_path() -> String:
	return "user://duel/%d-%d.cfg" % [salt_match, seat]


## Writes my salts where a game started again finds them (networked only: salt_match).
func _keep_salts() -> void:
	if salt_match <= 0 or sim == null:
		return
	var path := _salt_path()
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := ConfigFile.new()
	file.set_value("salts", "match", _duel_key)
	file.set_value("salts", "corks", _corks)
	file.set_value("salts", "waiting", _corks_waiting)
	if file.save(path) != OK:
		push_warning("Game: the salts could not be kept at %s" % path)


## Takes back the salts this match's file holds (a game started again): the corks by
## bottle, nothing on its way any more, the waiting ones unsure.
func _restore_salts() -> void:
	if salt_match <= 0:
		return
	var file := ConfigFile.new()
	if file.load(_salt_path()) != OK or str(file.get_value("salts", "match", "")) != _duel_key:
		return
	var corks: Variant = file.get_value("salts", "corks", {})
	var waiting: Variant = file.get_value("salts", "waiting", [])
	if corks is Dictionary:
		for id: Variant in corks:
			var c: Dictionary = (corks[id] as Dictionary).duplicate()
			c["uncork"] = -1
			c["retry"] = 0
			_corks[int(id)] = c
	if waiting is Array:
		for w: Variant in waiting:
			var copy: Dictionary = (w as Dictionary).duplicate()
			copy["unsure"] = true
			_corks_waiting.append(copy)


## The match is over for my bottles: its salts' file goes.
func _drop_salts() -> void:
	if salt_match > 0 and FileAccess.file_exists(_salt_path()):
		DirAccess.remove_absolute(_salt_path())


## main.gd at MATCH_END (decided or not): no bottle of this match matters any more.
func match_ended() -> void:
	_drop_salts()


## The 4 bytes at `at` of `bytes`, big-endian, as the signed i32 with their bits.
static func _i32(bytes: PackedByteArray, at: int) -> int:
	var v := (bytes[at] << 24) | (bytes[at + 1] << 16) | (bytes[at + 2] << 8) | bytes[at + 3]
	return v - 0x100000000 if v >= 0x80000000 else v


# ── The duel's events ──


## The duel's events: what they change of my corks and orders always, and their sounds and
## notices only while my game runs live turns (not the turns a catch-up runs again or
## missed, _catching_up: a resync or a rejoin would say every cork, uncorking, fizzle,
## breach and Seawall since its checkpoint again, all at once).
func _on_duel(e: Dictionary) -> void:
	var mine := int(e.get("seat", 0)) == seat
	var live := not _catching_up()
	match int(e["type"]):
		SimTypes.EV_CORK:
			if mine:
				_corked(e, live)
			elif live:
				Sfx.play("cork", -10.0)
				_say_rival("Your rival corked a tier %s bottle" % _tier_name(int(e.get("tier", 0))))
		SimTypes.EV_UNCORK:
			var pack := pack_info(_check_of(e.get("pack", "")), 0)
			if mine:
				_uncorked(e)
				if live:
					Sfx.play("uncork", -3.0)
					notice("%s walks your rival's road" % pack["name"])
			elif live:
				Sfx.play("uncork", -5.0)
				_say_rival("Your rival uncorked a %s on your road" % pack["name"])
		SimTypes.EV_FIZZLE:
			if live:
				Sfx.play("cork", -12.0)
			if mine:
				var id := int(e.get("bottle", -1))
				for seq: int in _uncorks.keys():
					if int(_uncorks[seq]) == id:
						_uncorks.erase(seq)
						_quiet.erase(seq)
						settled.emit(seq, false)
				_corks.erase(id)
				if live:
					notice("Your bottle fizzled: nothing walks, the gold stays spent")
			elif live:
				_say_rival("Your rival's bottle fizzled")
		SimTypes.EV_BREACH:
			if live and int(e.get("by", 0)) == seat:
				Sfx.play("breach", -3.0)
				notice("Breach · +%d gold" % int(e.get("pay", 0)))
			elif live:
				Sfx.play("breach", -6.0)
		SimTypes.EV_SEAWALL:
			if live:
				Sfx.play("seawall", -2.0 if mine else -8.0)
			if mine and _seawall_seq >= 0:
				settled.emit(_seawall_seq, true)
				_seawall_seq = -1
		SimTypes.EV_SURGE:
			if live:
				announce("The Surge %d/%d · wave %d again" % [int(e["surge"]), surge_waves(), int(e["wave"])])
	duel_changed.emit()


## EV_CORK of mine: the waiting CORK it ran, by the seq the event names (SimUndertow.cork),
## keeps its salt under the bottle's id now. A bottle already known is a resync's turns
## running again, or one that took its salt before its event was read (_drop_stale: it is
## said now); one whose seq no waiting cork has is not this client's (the caretaker's,
## seq 0, while the seat was away), and takes no salt of mine. `live`: the cork is heard
## (not in the turns a catch-up runs, _on_duel).
func _corked(e: Dictionary, live := true) -> void:
	var id := int(e.get("bottle", -1))
	if _corks.has(id):
		if _unheard.erase(id) and live:
			Sfx.play("cork", -4.0)
		return
	var at := -1
	for i in _corks_waiting.size():
		if int(_corks_waiting[i]["seq"]) == int(e["seq"]):
			at = i
	if at < 0:
		# (a cork of my seat no waiting cork has the seq of: the caretaker's, seq 0, while I was
		# away, which no salt of mine opens; or one of mine a resync sent back to waiting under
		# a seq it no longer knew, which takes its salt by commitment)
		_claim_corked()
		return
	var w: Dictionary = _corks_waiting.pop_at(at)
	_corks[id] = {
		"pack": w["pack"], "window": int(e.get("window", w["window"])), "tier": int(w["tier"]),
		"hi": int(w["hi"]), "lo": int(w["lo"]), "uncork": -1, "retry": 0, "seq": int(w["seq"]),
	}
	_keep_salts()
	settled.emit(int(w["seq"]), true)
	if live:
		Sfx.play("cork", -4.0)


## EV_UNCORK of mine: its UNCORK ran, and its salt is spent.
func _uncorked(e: Dictionary) -> void:
	var id := int(e.get("bottle", -1))
	for seq: int in _uncorks.keys():
		if int(_uncorks[seq]) == id:
			_uncorks.erase(seq)
			_quiet.erase(seq)
			settled.emit(seq, true)
	_corks.erase(id)


## A refusal of a duel order of mine: what waited for it goes; false for an uncorking the
## client sent by itself (it tries again unheard).
func _duel_refused(e: Dictionary) -> bool:
	var seq := int(e.get("seq", -1))
	match int(e.get("cmd", 0)):
		SimTypes.CMD_CORK:
			for i in _corks_waiting.size():
				if int(_corks_waiting[i]["seq"]) == seq:
					_corks_waiting.remove_at(i)
					_keep_salts()
					break
			duel_changed.emit()
		SimTypes.CMD_UNCORK:
			var id := int(_uncorks.get(seq, -1))
			_uncorks.erase(seq)
			if _corks.has(id) and int(_corks[id]["uncork"]) == seq:
				_corks[id]["uncork"] = -1
				_corks[id]["retry"] = sim.tick + UNCORK_RETRY_T
			duel_changed.emit()
			if _quiet.erase(seq):
				return false
		SimTypes.CMD_SEAWALL:
			if seq == _seawall_seq:
				_seawall_seq = -1
			duel_changed.emit()
	return true


## A rival's moment, held like a teammate's notice (nobody here pressed anything for it);
## not one from the turns a catch-up runs (_catching_up).
func _say_rival(text: String) -> void:
	if _catching_up():
		return
	team_notices.append(text)
	if team_notices.size() > TEAM_NOTICES_KEPT:
		team_notices.remove_at(0)
	team_noticed.emit(text)


## Once the duel is decided: its title and sound, once.
func _duel_decided() -> void:
	if _duel_said or outcome() == "":
		return
	_duel_said = true
	_drop_salts()
	duel_changed.emit()
	announce(duel_title())
	match outcome():
		"won":
			Sfx.play("victory")
		"lost":
			Sfx.play("defeat")


## The duel's title from my side (design 5.8): "The Tide Took Your Rival", "The Tide Took
## You" or "Even Tide"; "" until it is decided.
func duel_title() -> String:
	return str(DUEL_TITLES.get(outcome(), "")) if is_duel() else ""


## The rule that decided the duel, in one line from my side (decided_by(), contract-m7.md
## §2): a fall ("Your rival's Holdfast fell on wave 9"), more lives after the Surge ("You
## kept more lives after the Surge, 14 to 9"), more breach dealt, or a draw (both
## Holdfasts on one tick, or level on both after the Surge); "" until it is decided.
func duel_rule_line() -> String:
	if not is_duel() or outcome() == "":
		return ""
	var me := duel_side(my_team())
	var them := duel_side(1 - my_team())
	var won := outcome() == "won"
	var both_fell := int(me["lives"]) <= 0 and int(them["lives"]) <= 0
	match sim.decided_by():
		"fell":
			if both_fell:
				return "Both Holdfasts fell on the same tick"
			if won:
				return "Your rival's Holdfast fell %s" % _fell_words(1 - my_team())
			return "Your Holdfast fell %s" % _fell_words(my_team())
		"lives":
			return "%s more lives after the Surge, %d to %d" % [
				"You kept" if won else "Your rival kept",
				maxi(int(me["lives"]), int(them["lives"])), mini(int(me["lives"]), int(them["lives"]))
			]
		"breach":
			return "Level on lives after the Surge: %s more breach, %d to %d" % [
				"you dealt" if won else "your rival dealt",
				maxi(int(me["breach"]), int(them["breach"])), mini(int(me["breach"]), int(them["breach"]))
			]
		"draw":
			if both_fell:
				return "Both Holdfasts fell on the same tick"
			return "Level after the Surge: as many lives kept and as much breach dealt"
	return ""


## The wave team `team`'s Holdfast fell on: the race's record where it is kept, else its
## hollow's wave.
func _fell_on(team: int) -> int:
	var t := sim.teams[team]
	return t.fell_wave if t.fell_wave > 0 else maxi(1, sim.hollows[t.hollows[0]].wave)


## Where team `team`'s Holdfast fell, as the rule line says it: "on wave 9", or in the
## Surge "in Surge 2/3".
func _fell_words(team: int) -> String:
	var n := _fell_on(team)
	var s := SimUndertow.surge_of(sim, n)
	return "in Surge %d/%d" % [s, surge_waves()] if s > 0 else "on wave %d" % n


static func _tier_name(tier: int) -> String:
	return TIER_NAMES[clampi(tier, 0, TIER_NAMES.size() - 1)]


## A pack as an event names it (a CHECK_IDS id or its index) as its id.
static func _check_of(v: Variant) -> String:
	if v is int and int(v) >= 0 and int(v) < SimContent.CHECK_IDS.size():
		return SimContent.CHECK_IDS[int(v)]
	return str(v)


func _seat() -> SimRecords.SimSeat:
	return sim.seat(seat)


func _team() -> SimRecords.SimTeam:
	return sim.teams[_seat().team]


func _hollow() -> SimRecords.SimHollow:
	return sim.hollows[_seat().hollow]
