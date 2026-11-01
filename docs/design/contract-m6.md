# The M6 contract

M6 (the full roster, Tide Race and the queue, [`core-loop.md`](core-loop.md) §8) runs as four tracks from one commit,
this one: **A** rules, **B** art, **C** race views and **D** the queue. This page is what they build against.
Anything named here keeps its name and number until the tracks agree to change it; values marked *tunable* are the
design's, and track A may change them against the balance gates. [`world.md`](world.md) wins on names.

Decisions taken for M6 (§10's proposals, adopted): the queue only fills open seats and finds a rival, with
caretakers after 60 s; no public lobby browser. Duplicates are allowed inside a party and avoided between strangers.
A race is 1v1 or 2v2. The user's decision of 2026-11-01: **maps come after the modes**, each made for the mode it
serves, so Tide Race plays Wickhollow and its reflection and M6 adds no map.

`contract_m6_tables` (`tests/sim/contract_m6.gd`) guards §1 to §3, the event numbers, the queue's numbers, the
display entries and, once track A adds it, the `tide_race` preset. `contract_m2m3_tables` and
`contract_ids_keep_state_hashes` still hold: the lists only grew.

## 1. Ids (`scripts/sim/content.gd`), appended

| List | Appended, in order |
|---|---|
| `TOWER_IDS` (18 to 35) | the Bellfounder's bases `clapper_tower`, `toll_tower`, `chime_post`, branches `great_clapper`, `ringing_clapper`, `great_toll`, `sky_toll`, `deep_chime`, `long_chime`; the Beekeeper's bases `clay_hive`, `apiary`, `hive_hum`, branches `great_clay_hive`, `drowsy_clay_hive`, `royal_apiary`, `queens_guard`, `great_hum`, `long_hum` |
| `BUILDER_IDS` | `bellfounder` (2), `beekeeper` (3): their wire ids |
| `MODE_IDS` | `tide_race` (2): its wire id. `RULES` gains the preset in track A; until then `RULES.has("tide_race")` is false and the hub keeps the button greyed |
| `PERK_IDS` | `bronze_hand`, `hive_tithe` |

## 2. The two Builders (`BUILDERS`)

| Field | Bellfounder | Beekeeper |
|---|---|---|
| `name`, `title`, `home` | Ottilie Brass, the Bellfounder, Brackwater | Sefa Amberwell, the Beekeeper, Thousandwell |
| `role`, `difficulty` | `breaker`, 2 | `sweeper`, 3 |
| `covers` | swift, armored | swarm, winged |
| `patches` | swarm: `ringing_clapper`; winged: `sky_toll` | swift: `drowsy_clay_hive`; armored: `queens_guard` |
| `towers` (Q W E) | `clapper_tower`, `toll_tower`, `chime_post` | `clay_hive`, `apiary`, `hive_hum` |
| `perk` (*tunable*) | `bronze_hand`, `pierce_c` 200 | `hive_tithe`, `gold` 2, `cap` 12, `bases` [`clay_hive`, `hive_hum`] |
| `plan` | `bellfounder` (track A writes the file) | `beekeeper` (track A) |
| `glyph`, `accent` | `builder_bellfounder`, `0xC2A98A` | `builder_beekeeper`, `0xD0C294` |

## 3. Tower keys and the rules they carry

`TOWERS` holds both kits at the design's numbers (§3.4, *tunable*). The new keys (documented above `TOWERS`) and
what track A makes them do; the M2 rules hold for everything else:

- **Pulse** (`pulse`, the Toll Tower): no shot. Every `cd_t` it strikes every creep within `range_mm` at once,
  ground only unless `air`, dealing `dmg_c` through the armour rule, and emits `EV_PULSE` (19). Each struck ground
  creep is **stunned** `stun_t` ticks (speed 0), then immune for `stun_immune_t`, so stuns never chain. On a boss,
  where the rules turn `control_resist` on, a stun is a 50% slow of the same length, not scaled again. A struck
  flier gets `air_slow_pm` for `air_slow_t` instead (the Sky Toll).
- **Cloud** (`cloud_mm`, the Clay Hive): no shot. Every `cd_t` it aims as a tower does (`air` lets it pick a flier)
  and stings every creep, ground or air, within `cloud_mm` of that creep: `dmg_c` each, and `slow_pm` for `slow_t`
  where set (the Drowsy Clay Hive). `SimTower.cloud_creep` holds the creep the cloud last stung over (0: none), for
  the view.
- **Crack aura** (`crack_c`, team `crack`): creeps inside the post's `range_mm` have `crack_c` less armour against
  every hit; the strongest crack applies. Fliers carry no armour, so the post never reaches them.
- **Haste aura** (`haste_pm`, team `haste`): every tower whose cell centre lies within `range_mm` of the hum's,
  whoever built it, has its cooldown divided by `1 + haste_pm/1000`; the strongest hum applies; recomputed when any
  tower is built, forked or sold. A hum hastens no other hum.
- **`air_bonus_pm`** (the Apiary's forms): `raw` grows by this share against a winged creep.
- **Perks:** Bronze Hand adds `pierce_c` to every hit of the owner's towers (pulses and clouds too). Hive Tithe pays
  the owner `gold` per tower of hers on one of `bases` at every wave clear, at most `cap`, as `EV_GOLD` `why`
  `"tithe"`.
- **Help** for the new effects follows §3.2: a hit on a creep another seat's tower stunned or cracked, or from a
  tower another seat's hum hastens (`SimTower.haste_seat`), credits that seat. `HELP_ORDER` stays mark, crack, stun,
  slow, with haste counted for the firing tower.
- **Targeting** of the Apiary is `aim` `winged`, as the Hawk Roost's. The Toll Tower and the Clay Hive "pulse at
  everything in reach" (§3.2) through the rules above.

## 4. Tide Race in the simulation (track A)

- **Preset `tide_race`:** `high_water`'s keys with `teams` 2, `seats` [2, 4], `cap_t` 72000 (20 minutes, honoured
  now) and `race` `{"life_t": 600}`. Each team plays its own hollow (`SimHollow.id` = its team), built from the same
  map text; seats of team *t* stand on hollow *t*, as `SimMatch.setup` already lays out.
- **Seats on the wire:** `MATCH_CONFIG` lists seats in order with their team; a 1v1 is seat 0 on team 0 and seat 1
  on team 1, a 2v2 seats 0 and 1 on team 0 and 2 and 3 on team 1. `RemoteSequencer.from_wire` is unchanged.
- **Fairness:** both hollows get the same waves on the same ticks of their own clocks. Anything random a hollow
  draws comes from a stream of its own, seeded from the match seed and the hollow id, so a mirror plays out the
  same on both (`race_mirror_is_fair`).
- **Clocks:** each hollow's windows, Ready and horn are its own; health scales by its own seat count (§2.5).
- **Race time** = the tick the team cleared wave 12 plus `life_t` for every life it lost. **Win order** (§1.3):
  both cleared, the lower race time wins and equal ticks are a draw; a Holdfast fell on wave *W*, the other team
  wins once it clears *W* (both fell: the later wave, then more of that wave's creeps killed, then a draw); at the
  cap, waves cleared, then lives, then race time. The match is over as soon as the outcome is certain.
- **API** for every reader (`match_client._outcomes`, results, the strip): `SimMatch.outcomes()` (one MATCH_END
  outcome id per team, empty until decided), `race_time(team)` (-1 while unknown), `decided_by()` ("time",
  "fell", "cap", "draw" or ""), and `EV_RACE` (20) for "cleared", "fell" and "decided". The race's new state goes
  in the codec's trailing block, so High Water and classic checkpoints keep their bytes.
- **The caretaker** plays a race seat on its own hollow from the Builder's plan; Ready follows the plan's step
  `ready` hints if any, else it calls each wave when its build steps for the window are done.
- **Racing the caretaker** (offline, and online after the queue's 60 s): the rival team is caretaker seats with
  the same Builders as yours, a mirror.

## 5. Two hollows on screen (track C)

- Hollow *h* stands at a world offset of `Game.hollow_origin(h)` = (26 × *h* tiles, 0, 0), the second copy beyond a
  two-tile cliff band the terrain fills. Every position the simulation gives (`EV_BUILT`, `EV_EFFECT`,
  `EV_SIGNAL`, `EV_PULSE`, the road) is local to its hollow; views add the origin.
- The camera starts over your hollow; **Home** frames it, **V** jumps to the rival's and back. The minimap shows
  both, yours brighter. Orders on the rival's hollow are refused locally ("That is your rival's hollow").
- The resource strip's second line in a race: "Rival · Wave 7 · 18 lives · 6:12 +20 s" (§5.7).
- Loading: two rows of cards, team A above and team B below, a coverage row under each (§5.6). Results: one block
  per team, both race times, the deciding rule in one line, titles "You Outran the Tide", "Your Rival Outran the
  Tide", "Two Crews, One Time" (§5.8).
- Display entries: `Game.TOWERS` gets each M6 form's `model` (`res://models/towers/<form>.glb`), its `muzzle` or
  `bore`, `projectile` and `sound`. No M6 form turns a head. The Apiary's forms fire `bee`
  (`models/projectiles/bee.glb`); the Clapper Tower's strike is instant, shown by a `clap` effect. Fx: `bell_ring`
  on `EV_PULSE`, `bee_cloud` over `cloud_creep`, `chime_shimmer` on a cracked creep, a hum glow on a hastened
  tower; every view reads the records, not new events. A model or icon not built yet stands in as
  `Models.placeholder()` or `Game.placeholder_icon()`.

## 6. The queue (track D)

- **Wire:** unchanged messages (`QUEUE`, `QUEUE_STATE`, `MATCH_FOUND`, `ACCEPT`, `PARTY` `open` and `team`).
  New numbers in `protocol.json`: `accept_ms` 15000 (Match Found's window) and `caretaker_offer_ms` 60000.
- **Who queues:** the leader of a forming party, everyone Ready. High Water with open seats on and free: **Find
  players** fills the open seats with strangers up to four. A race party of one team (1 or 2 players): **Find a
  rival** finds one other team of the same size. Parties merge only by mode and rules hash.
- **Match Found** (always, since the queue only ever adds strangers): 15 s by the server's clock. Everyone accepts:
  the barrier opens as a strangers' match (45 s start with the seats loaded, 120 s ceiling). A decline or a
  timeout: the match dissolves; the decliner's party returns to forming; the others go back to the **front** of
  the queue with `NOTICE match_dissolved`.
- **Builders between strangers:** whoever queued first keeps their main; the other takes their backup; a seat
  still clashing gets a free Builder from the server's random number generator. The server writes the result into
  `MATCH_CONFIG`; no client rolls.
- **After 60 s queued:** `QUEUE_STATE` sets `caretaker_offer`, with `NOTICE caretakers_offered`. `QUEUE
  start_with_caretakers` starts at once: High Water fills the open seats with caretakers whose Builders cover
  what the party lacks (BUILDER_IDS order); a race gets a caretaker rival team mirroring the party.
- **Afterwards:** each party is its own again on its results plate; a player who came alone through the queue is
  queued again on Play again ("Entering queue..." until `QUEUE_STATE` says queued).
- **Client:** the session's QUEUED and MATCH_FOUND states, the hub's queue pill and primary button per §5.2's
  table, `scripts/ui/match_found.gd` per §5.5 (the server's countdown, Accept, decline), the race party's teams in
  the party well (the leader clicks a row to move it), and **Race the caretaker** for a party of one offline.

## 7. Art (track B)

The Bellfounder and the Beekeeper as chibi toon figures in the Builders' style (`AGENTS.md`): about 2.5 to 3 heads, a
face of a few flat shapes, one oversized hat or hood, and one oversized prop that reads as a **tool, never a
weapon**. Ottilie's is a bronze hand bell (her hammer stays small and on its chain); Sefa's is a bee smoker, under a
veiled straw hat. Each builds `models/builders/<id>.glb` and `<id>_bust.glb` (`art_src/blender/builders/<id>.py`,
colours in `palettes/builders.gpl` blocks of their own), the glyph `ui/icons/builder_<id>.png` (128 px) from the
bust and the emblem `ui/icons/emblem_<id>.png` (108 px) from the prop. Eighteen tower models
`models/towers/<form>.glb` (recipes `art_src/models/towers/<form>.json`; branches reuse their base and change the
crown or roof), their command icons `ui/icons/<form>.png` (108 px, from `models/ui/towers/<form>.glb`), the bee
projectile, and the sounds `toll`, `chime`, `bees`, `clap`, `match_found` and `countdown_tick` in `sfx/`.
`art_m6_painted` checks it all; `asset_manifest.json` lists every file.

## 8. Who owns what

| Track | Owns (writes) |
|---|---|
| A rules | `scripts/sim/*`, `data/plans/`, `tests/sim/` (not `art_*`), `tests/balance/`, `tools/gen_balance_scenarios.py`, `match_client.gd`'s `_outcomes`; scenarios `sim_*`, `race_*` of the simulation, the effect and perk scenarios, the M6 balance gates |
| B art | `art_src/models/`, `art_src/blender/`, `art_src/ui/icons.*`, `art_src/ui/renders/`, `models/` (not `models/causeway/`), `ui/icons/`, `sfx/`, `palettes/builders.gpl`, `tests/sim/art_m6_painted.gd` and its scenario |
| C views | `scripts/main.gd`, `terrain.gd`, `decor.gd`, `camera_rig.gd`, `minimap.gd`, `hud.gd`, `resource_strip.gd`, `build_controller.gd`, `tower.gd`, `creep.gd`, `projectile.gd`, `fx.gd`, `sfx.gd`, `scripts/game.gd`, `scripts/ui/loading_screen.gd`, `results_panel.gd`, `party_strip.gd`, `scenes/main.tscn`; `view_*`, `hud_*` and race view scenarios |
| D queue | `server/*`, `shared/net/*` (constants, README, transcripts), `scripts/session/*`, `scripts/ui/hub_panel.gd`, `match_found.gd`, `shell.gd`, `builders_screen.gd`, `tests/net/*`, `tools/net/smoke.py`, `flow_*` and `net_*` scenarios |

Each track adds its own newly named scenarios, only its own paths' `asset_manifest.json` entries, and its own lines
in `AGENTS.md` and `CHANGELOG.md` (`## Unreleased`). A, B and D start together; C starts on A's merge, because
two hollows and the new effects have to exist to be drawn, and takes B's art whenever it lands (the stand-ins
cover the gap). Until C merges, `Profile.fielded` keeps fielding a Lamplighter for the new Builders, whose towers
have no models in `Game.TOWERS` yet.

## 9. Acceptance

[`core-loop.md`](core-loop.md) §8 M6's list, by track. **A:** `stun_then_immune`, `toll_pulse_hits_all_ground`,
`cloud_hits_air_and_ground`, `crack_lowers_armor_for_all_and_credits_help`, `haste_any_owner`, `tithe_pays_capped`,
`bronze_hand_ignores_2`, `bot_wins_solo_bellfounder`, `bot_wins_solo_beekeeper`, `bot_wins_high_water_3p`,
`bot_wins_high_water_4p`, `idle_team_loses_3p`, `idle_team_loses_4p`, `coverage_holds_complementary_bb`,
`race_same_waves_both_hollows`, `race_independent_clocks`, `race_time_penalty_per_life`,
`race_rival_fell_clear_to_win`, `race_cap_20_minutes`, `race_mirror_is_fair`, `race_bots_both_finish`.
**C:** `race_rival_view_toggle`, `race_results_two_teams`, two hollows within the browser's frame budget under
`godot-agent run . --renderer gl_compatibility`. **D:** `test_queue` (merging, a decline requeues the others at the
front, the timeout, Builder clashes, the caretaker offer at 60 s, keying on the rules hash) and
`smoke.py --mode tide_race`. **B:** `art_m6_painted`. After the merge: the balance matrix, `--determinism`, and a
live Tide Race on the official server.
