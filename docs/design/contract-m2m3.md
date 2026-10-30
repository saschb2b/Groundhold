# The M2 and M3 contract

M2 (Builders and checks) and M3 (the loop: hub, Builders screen, party, loading, results, LAN) run in parallel
from one commit, this one ([`core-loop.md`](core-loop.md) §8). This page is what both build against. Anything
named here keeps its name and its number until both tracks agree to change it; values marked *tunable* are the
design's and M2 may change them. [`world.md`](world.md) wins on names. Decisions taken for both (§10, adopted):
manage Builders is browse, set main and backup, Try, with everything unlocked; no Builder avatar on the map in v1;
High Water takes 1 to 4 players and duplicates are allowed; no public queue yet (M6); the command card's keys are
positional for every Builder.

Three scenarios guard it: `contract_m2m3_tables` (every table below, the wire's ids, the icon paths),
`contract_lookout_kit_resolves` (a Lookout seat plays its kit from the tables) and
`contract_ids_keep_state_hashes` (a classic match still reaches the state hashes recorded before the ids grew).

## 1. Ids (`scripts/sim/content.gd`)

The codec stores a mode, Builder, tower or creep as its index, so every list grows only at its end. A mode's and a
Builder's index is its id in `shared/net/protocol.json`.

| List | Ids, in order (index from 0) |
|---|---|
| `MODE_IDS` | `classic`, `high_water` |
| `BUILDER_IDS` | `lamplighter`, `lookout` |
| `CREEP_IDS` | `gourdling`, `scuttler`, `thornback`, `hollowtide_crest`, `duskmoth`, `bristlesow` |
| `TOWER_IDS` | `arrow`, `cannon`, `frost`; the Lamplighter's branches `longbow_loft`, `skyward_loft`, `great_cannon`, `iron_mortar`, `deep_frost`, `rime_spire`; the Lookout's bases `perch_ballista`, `hawk_roost`, `owls_eye` and branches `siege_perch`, `pinning_ballista`, `falcon_roost`, `kestrel_flock`, `owls_glare`, `twin_gaze` |
| `CHECK_IDS` (display order) | `swarm`, `swift`, `armored`, `winged` |
| `ROLE_IDS` | `warden`, `marksman`, `breaker`, `sweeper` |
| `PERK_IDS` | `thrifty`, `keen_sight` |

`TOWER_IDS` names every tower *form*. A `SimTower`'s kind is its base and its `branch` (−1, 0 for A, 1 for B) says
which form stands; `SimContent.tower_form(kind, branch)` gives the form's id, which display tables key by.
`RULES.has(mode)` says whether this build can play a mode: until M2 adds the `high_water` preset and `hollow12`,
only `classic` can, and the hub plays `classic` behind the High Water button.

## 2. `BUILDERS` fields

Every entry has exactly these thirteen fields (`BUILDER_FIELDS`). `rules_hash()` leaves out the display ones
(`BUILDER_DISPLAY_KEYS`: all but `covers`, `towers`, `branches`, `perk` and `plan`), so retitling never splits
matchmaking. Every field the simulation reads is hashed: the caretaker forks by the team's `covers` (it takes a
patching branch only while nobody covers the check), so `covers` is a rule, not a label; `contract_m2m3_tables`
follows every `SimContent` helper the simulation calls and fails on a read of a field the hash leaves out.

| Field | Meaning | Lamplighter | Lookout |
|---|---|---|---|
| `name`, `title`, `home` | display | Tamsin Wick, the Lamplighter, Wickhollow | Edda Greyplume, the Lookout, Fogholm |
| `role` | a `ROLE_IDS` id; a label, never a lock | `warden` | `marksman` |
| `difficulty` | stars, 1 to 3 | 1 | 2 |
| `covers` | checks it is strong against, `CHECK_IDS` order | swarm, swift | armored, winged |
| `patches` | `{check: [branch ids]}` lifting a weak check to passable | armored: iron_mortar; winged: skyward_loft, rime_spire | swarm: kestrel_flock; swift: pinning_ballista |
| `towers` | three bases, on Q, W, E | arrow, cannon, frost | perch_ballista, hawk_roost, owls_eye |
| `branches` | per tower `[A, B]` = `TOWERS[t].a.id`, `.b.id` | as §1 | as §1 |
| `perk` | `{"id", numbers}`, *tunable* | thrifty, `sell_pm` 900 | keen_sight, `range_mm` 400 |
| `plan` | `data/plans/<plan>.json`; empty until written | `lamplighter` | `lookout` (M2 writes it) |
| `glyph` | icon stem in `ui/icons/` | `builder_lamplighter` | `builder_lookout` |
| `accent` | `0xRRGGBB`, at most 35% saturated, never a seat colour | `0xD9C49B` | `0xAEB8C2` |

Helpers M3 reads instead of walking the tables: `SimContent.team_covers(builders)` (the coverage row: checks any
of them is strong against, duplicates once), `covers(builder, check)`, `branch_helps(builder, branch)` (the
check glyph beside a branch, or "") and `kit_tower(builder, slot)`.

## 3. Tower and creep keys

`TOWERS` carries every base above with both branches, at the design's numbers (*tunable*). Keys already honoured:
`builder`, `slot`, `cost`, `dmg_c`, `cd_t`, `range_mm`, `air`, `shot_um_t` (0: fires no shot, works by its team
effect), `min_flight_t`, `splash_mm`, `slow_pm`, `slow_t`, `pierce_c`, `fork_cost`, `a`, `b`, and `team` (`slow`,
`mark`; M6 adds `stun`, `crack`, `haste`). M2 makes the simulation honour `aim` (`first`, `winged`, `most_hp`),
`bounces`, `bounce_mm`, `mark_pm`, `marks`, `mark_t` and the perks, and adds the `high_water` preset (armour on)
with `hollow12`. `CREEPS` adds the Duskmoth (`winged`) and the Bristlesow (`boss`, `control_resist_pm` 300).

## 4. Simulation vocabulary (`scripts/sim/sim_types.gd`)

No existing number changes. New: `EV_STATUS` 17 (effect, creep, tower, seat, amount, until) and `EV_HELP` 18
(seat, by, creep, effect, dmg); effects `EFFECT_SLOW` 1, `STUN` 2, `MARK` 3, `CRACK` 4, `HASTE` 5
(`SimTypes.effect(name)`). Event fields M2 adds: `EV_FIRE` `from`, `form`; `EV_HIT` `raw`, `armor`, `bounce`;
`EV_FORKED` `form`; a reader takes a missing one as 0 or "". No new refusal: a fork on a teammate's tower is
`NOT_YOURS`, a second fork `ALREADY_FORKED`, a branch or slot that does not exist `BAD_COMMAND`. Results read
`SimSeat`'s `kills`, `damage_c`, `help_c`, `towers` and `forks`.

## 5. Display tables and art paths (`scripts/game.gd`)

Read every path through `Game.icon(path)`: art not painted yet comes back as a placeholder ring, never an error
(`Game.has_art(path)` tells). M2 paints everything under `ui/icons/`; M3 builds the portrait models.

| Table | Per id | Paths |
|---|---|---|
| `Game.CHECKS` | `name`, `glyph` (Froth, Runnel, Ballast, Spindrift), `icon` | `ui/icons/check_swarm.png`, `check_swift.png`, `check_armored.png`, `check_winged.png` |
| `Game.ROLES` | `name`, `icon` | `ui/icons/role_<role>.png` |
| `Game.BUILDERS` | `glyph` (party rows, strip, results), `portrait` (arch, cards; `Portrait.show_model`) | `ui/icons/builder_<id>.png`, `models/builders/<id>.glb` |
| `Game.PERKS` | `name`, `text` | |
| `Game.TOWERS` | every form: `name`, `icon`; a base `description`, a branch `gain` | `ui/icons/<form>.png` (the three M1 bases keep `<kind>_tower.png`) |

## 6. Keys

The command card has six fixed slots with the same keys for every Builder, `Game.CARD_KEYS` = Q W E / A S D.
Nothing selected or placing: Q, W, E the kit's towers; A Signal; S Sell (idle); D Ready (N and Space too). Your
unforked tower: Q branch A, W branch B, E idle. Your forked tower: the branch taken lit, the other idle. A
teammate's tower or a creep: as nothing selected, Sell idle. The Builders screen shows the kit on Q, W, E with the
in-game tooltip. M2 moves the HUD onto this and drops `Game.TOWERS`' `hotkey`.

## 7. Who owns what

| Track | Owns (writes) |
|---|---|
| M2 | `scripts/sim/*`, `data/plans/`, `tests/sim/`, `tests/balance/`, `tools/gen_balance_scenarios.py`; `scripts/game.gd`, `hud.gd`, `resource_strip.gd`, `portrait.gd`, `build_controller.gd`, `minimap.gd`, `creep.gd`, `tower.gd`, `projectile.gd`, `fx.gd`; `art_src/models/`, `art_src/blender/` (not `builders/`), `art_src/ui/icons.*`, `models/` (not `models/builders/`), `ui/icons/`, `sfx/` |
| M3 | `server/*`, `shared/net/*`, `scripts/session/`, `scripts/net/beacon_listener.gd`, `scripts/ui/` (not `party_strip.gd`), `scenes/hub.tscn`, `scripts/main.gd`, `project.godot`; `art_src/ui/console.*`, `ui/console/`, `art_src/blender/builders/`, `models/builders/`; `tests/net/fake_sequencer.gd`, `tests/scenarios/flow_*.json` |

Each track adds its own, newly named scenario and test files, only its own paths' entries in
`asset_manifest.json`, and its own lines in `AGENTS.md` and `CHANGELOG.md`.
M3 reads `content.gd` and `game.gd` and writes neither; M2 never touches the hub, the session or the server.
Until M2 merges, a Lookout can be browsed, chosen as main or backup and counted in the coverage row, but matches
and Try field Lamplighters: its views, mechanics and art arrive with M2.

## 8. Since the merge

M2 and M3 are one branch now, and these points of the contract moved:

- The stand-ins are gone: `RULES` has `high_water`, so the hub plays it by its own rules, and the Lookout's towers
  have views, so matches and Try field her as herself. `Profile.fielded` and `Profile.played_mode` remain for
  M6's Builders and modes.
- `SimContent.rules_hash()` takes no mode: one hash per build, over every mode's plans and map. HELLO carries it
  before a party picks its mode, so it has to fit every mode the party may play.
- `PARTY_STATE` gained `you` after `leader`: the recipient's own member number (255 outside a party). Members are
  rows 0 to 3, so a game cannot find its row from its session.
- `Game.BUILDERS` gained `bust` (the head and shoulders the hub's arch shows; the glyph is rendered from it) and
  `emblem` (`ui/icons/emblem_<id>.png`, the Builder's signature prop as a command button, on the hub's B). The
  glyph at `ui/icons/builder_<id>.png` is M3's framed face, 128 px; M2's prop glyph became the emblem.
- `Game.kit_tip(builder, slot, bonus_mm)` is the one body of a kit tower's tooltip, for the card and the Builders
  screen alike.
