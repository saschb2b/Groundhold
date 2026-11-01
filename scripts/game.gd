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
}
## An order aimed at the other team's hollow in a race, refused here before it goes out
## (contract-m6.md §5): the simulation reads a seat's cells on its own hollow, so the same
## cell sent would land on mine.
const RIVAL_HOLLOW := "That is your rival's hollow"
## An order given once the match is over for me (over()), refused here: MatchClient's
## own words for an order after MATCH_END.
const MATCH_OVER := "The match is over"
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
	team_notices.clear()


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


## A teammate's seat changed hands (EV_SEAT): the notice design 5.7 asks for, with their
## name. Not while my own game runs turns it missed (a catch-up replays changes the
## others saw long ago), and not for a rival team's seats.
func _teammate_seat(n: int, now: int) -> void:
	var s := sim.seat(n)
	if s == null or s.team != _seat().team:
		return
	var client := _scene_client()
	if client != null and (client.catching_up or client.reconnecting):
		return
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


## The networked match's client the current scene plays through, or null.
func _scene_client() -> MatchClient:
	var scene := get_tree().current_scene if is_inside_tree() else null
	if scene == null:
		return null
	var client: Variant = scene.get("client")
	return client as MatchClient if client is MatchClient else null


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
			if is_race():
				return  # (my hollow is done, the race may not be: EV_RACE says, _on_race)
			announce("The Holdfast stands. Victory!")
			Sfx.play("victory")
		SimTypes.PHASE_FALLEN:
			state_changed.emit(State.LOST)
			if is_race():
				return  # (a fall decides a race only once the rival clears that wave)
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


## Whether the match is a race: two teams, each on a hollow of its own.
func is_race() -> bool:
	return sim != null and sim.race


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


func _seat() -> SimRecords.SimSeat:
	return sim.seat(seat)


func _team() -> SimRecords.SimTeam:
	return sim.teams[_seat().team]


func _hollow() -> SimRecords.SimHollow:
	return sim.hollows[_seat().hollow]
