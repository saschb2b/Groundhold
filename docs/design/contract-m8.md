# The M8 contract

M8 answers the first playtest of the Warcraft III tower defense veteran (`halv`, session 1): waves that stack (P6),
Hard and Very Hard (P5), a rival bottle's candidates (P3) and a fork pass (P7) ([`core-loop.md`](core-loop.md)
§2.7, §2.6, §1.4, §3.8 and §8 M8). It runs as four tracks from one commit, this one: **A** rules (stacked waves and
the levels in the simulation, the caretaker's calls, the candidates query, the new balance gates), **B** views and
the hub (stacked waves on screen, the level's words in the hub and wherever the mode is named, the candidates in
the Drift tray and the duel bar), **C** server and protocol (the level in the party, the queue and `MATCH_CONFIG`,
protocol version 2, the session's side) and **D** the fork pass (every fork pair measured and spread), which starts
on A's merge. Anything named here keeps its name and number until the tracks agree to change it; values marked
*tunable* are the design's first proposal, and A (stacking, the levels) or D (the forks) may change them against
the gates. [`world.md`](world.md) wins on names.

The owner's decisions of 1 November 2026, after the report: waves stack, as sending early did in Element TD, and
the early-call bonus pays for the risk; a party-wide difficulty, Normal by default, with Hard and Very Hard ("more
creep health, fewer lives, a tougher boss"), and the queue matching on it; a rival's corked bottle names which of
its window's packs it may hold, still not which one; a balance pass spreads the fork pairs so each branch has its
own job. And of 2 November 2026, after A's first stacking showed stacking every wave was always the best play (its
horn waited for the newest wave's last creep, so a skipped window cost nothing): the waves truly overlap, the
called wave setting out the moment the horn sounds, among the current wave's creeps (§2; core-loop §10, item 18).

`contract_m8_tables` (`tests/sim/contract_m8.gd`) guards §1's ids, keys and numbers, §5's protocol fields and,
once a track adds them, the presets' keys, the `DIFFICULTIES` table and the plans' `stack` lists. It checks what
exists and skips what a track has not written yet, as `contract_m7_tables` did. `contract_m2m3_tables`,
`contract_m6_tables`, `contract_m7_tables` and `contract_ids_keep_state_hashes` still hold.

## 1. Ids, keys and numbers

- **Levels.** `SimContent.DIFFICULTY_IDS` = `["normal", "hard", "very_hard"]`, append only: a level's index is its
  wire id (`protocol.json` `difficulties`: `normal` 0, `hard` 1, `very_hard` 2) and what the codec stores.
  `SimContent.DIFFICULTIES[id]` holds the keys a level lays over a preset (§3); `normal` is `{}`.
- **Preset keys** (A, in `RULES`, documented above it):
  - `stack_max`: how many waves a hollow's road holds at once; 1 or absent, no stacking.
  - `stake_pm`: what a stacked horn pays for each life the waves on the road could still take, per mille of a
    gold.
  - `levels`: the preset takes a level.

  | Preset | `stack_max` | `stake_pm` | `levels` |
  |---|---|---|---|
  | `classic` | absent (M1's game, untouched) | absent | absent |
  | `high_water` | 3 (*tunable*; tuned from 2 by A, §2) | 400 (*tunable*; tuned from 1000) | true |
  | `tide_race` | 3 (*tunable*; tuned from 2) | 400 (*tunable*; tuned from 1000) | true |
  | `undertow` | 1 | absent | absent |

- **`protocol.json` `modes`:** `high_water` and `tide_race` gain `"levels": true`, the server's copy of which modes
  take a level (it never reads `content.gd`); `contract_m8_tables` holds the two to agree.
- **Refusal** `REFUSE_NO_STACK` 16 (`sim_types.gd`): a Ready in a wave of a preset that stacks, while the wave
  cannot take another (§2). A preset that never stacks refuses a Ready in its waves as `WRONG_PHASE`, as before.
- **No new event number.** `EV_WAVE` at a stacked horn adds `stacked` (true) and `stake` (the lives on the road,
  not gold: its `early` is what the horn paid each seat, in gold); (the review) `EV_SPAWN`, `EV_DIE` and `EV_LEAK`
  add `wave`, the creep's `SimCreep.wave`, which a view reading a frame of many ticks needs (events are not hashed); `EV_GOLD` `why` `"stack"` is a stacked horn's
  pay, the window's part and the stake's part together; `"ready"` stays a window's.
- **`SimContent.CARETAKER_VERSION` 5:** the caretaker stacks (§2).
- **A plan's `stack`** (A, `data/plans/<builder>.json`): the waves its caretaker and its plan bot call during the
  wave before; at the top level for every preset that stacks, and a mode block may hold its own. First lists
  (*tunable*), each Builder's own checks called during a wave of its own checks, never behind a boss: the
  Lamplighter `[2, 3]`, the Lookout `[5]`, the Bellfounder `[4]`, the Beekeeper `[2]`. A listed wave is 2 to 12.
- **The rules hash** covers `DIFFICULTIES` and every plan's `stack` list besides what it covered, and (the review)
  `SimContent.ORDERS_VERSION` 2, the READY that names its wave (§2). It stays one hash per build for every mode and
  every level, so `HELLO` is unchanged.

## 2. Stacked waves (track A; design §2.7)

- **When Ready is taken.** In a build window, as before. In a wave of a preset whose `stack_max` is above 1, a
  present seat's `READY 1` is taken (`EV_READY`) while the hollow has fewer than `stack_max` waves on its road, the
  newest is not the last wave, no seat of the hollow is returning from the caretaker (its hand-back needs a
  window), and the match is not over; otherwise `NO_STACK`. `READY 0` is always taken. (The review) A `READY 1`
  names the wave it calls in `b`, the hollow's newest plus one, in a window as in a wave, and is taken only for that
  wave, or for `b` 0, which names none (the caretaker's, and every turn log recorded before): one naming another is
  `WRONG_PHASE`, so a window's press that lands after its horn, online, never calls the wave after it, alone, nor
  stands as a call for it beside a partner and carries into the next window. The game names the wave in every
  mode (`BuildController._send_ready`, `Game.called_wave()`); a press late in a window asks for a second press while
  the countdown is within the order's lead, its trip there and back (`Game.order_trip()`, `MatchClient.rtt_ms` in
  whole turns) and a turn (`Game.late_in_window()`), and that second press goes out once the window's horn has
  sounded, naming the wave after it.
- **The stacked horn** sounds in stage 2 of the tick on which every present seat of the hollow is Ready (a seat
  the caretaker plays counts as Ready, as in a window): a player's Ready lands in stage 1, so its horn sounds in the
  same tick; a caretaker says it in stage 3, so its horn sounds in the next. Nothing else waits: the newest wave
  may still be setting out. The called wave sets out at once, its first creep in that stage 2 as at a window's
  horn (its queue's first wait 0) and the rest at its groups' `interval_t`. What the older wave has still to send
  moves, at the horn and before that tick's spawns, to `SimHollow.behind` as `[creep kind index, wave, tick]`, each
  on the tick its queue would have sent it (`SimWaves.hold_back`), and the Welling sends both: each tick, first the
  `behind` entries whose tick has come, in their order (the oldest wave first), then the newest wave's queue
  (`SimWaves._spawns`). `SimHollow.queue`, `cursor` and `spawn_wait_t` stay the newest wave's schedule, as the M1
  to M7 records say. A creep comes with its own wave and grows by it (`SimWaves.spawn(m, h, kind, sent_by,
  wave)`). Every horn clears every Ready. A hollow nobody is present at stacks only as its caretaker calls (below).
- **On the road.** A wave is on the road from its horn until it clears. `SimHollow.wave` stays the newest wave
  called. New state: `SimHollow.cleared`, the waves cleared in order, `SimHollow.behind` (above), and
  `SimCreep.wave`, the wave a creep came with (an uncorked creep's is the wave it walks, in a duel). The phase is
  `WAVE` while any wave is on the road. `spawns_left(hollow)` counts every wave's spawns still to come.
- **Clears** (stage 7). Wave *k* clears when every creep of waves 1 to *k* has set out (`SimWaves.to_come_up_to`:
  the newest wave's queue, the older waves' `behind`) and none of them is on the road, so waves clear in order, and
  a younger wave whose road is empty clears in the same stage right after the older. Each clear pays each seat the
  clear bonus of its own wave (`clear_bonus`: 8 + 2 × *k*) and the Hive Tithe, and says `EV_WAVE` `cleared` *k*.
- **Windows.** No window comes between stacked waves. When the last wave on the road clears, the next window opens
  with the preset's `window_t`, or the hollow is done after its last wave. A seat's Ready from a wave that clears
  before its horn stands into that window (`open_window` clears no Ready said in the wave before it).
- **Pay.** A window's horn pays one gold per whole second left, as before. A stacked horn pays each seat of the
  hollow the whole window it skips (`window_t` for the hollow's seat count, in whole seconds) plus `stake_pm` per
  mille of the **stake**, rounded down: the lives the waves on the road could still take at the horn, the tolls of
  every creep on the hollow's road and of every creep the Welling has still to send (the newest wave's queue from
  its cursor and `behind`), so a call made while the older wave is still setting out stakes all of it. One
  `EV_GOLD` `"stack"`. Bounties pay at each kill, as before.
- **A race.** Each hollow stacks on its own clock. Race time counts as before: the last wave's clear tick plus
  `life_t` a life lost. `cleared_waves(team)` is the hollow's `cleared` (its last wave once done). A team that falls
  fell on its oldest wave on the road, its waves cleared plus one (in a window, the wave it faced, as before), and
  `fell_kills` counts the kills of that wave's creeps, whichever horn they came with. A fall drops what `behind`
  still held. Nothing else of Tide Race changes.
- **No stacking in Undertow or classic.** Their Ready in a wave stays refused as before; the duel's shared clock,
  Drift and corks are M7's, unchanged.
- **The caretaker** says Ready during wave *k* − 1 for each wave *k* of its plan's `stack`, once the build steps it
  can pay for now are done and the step it waits on does not hold Ready (`"ready": false`), so at its first think
  in that wave where nothing it can pay for is left to build, and wave *k* walks with *k* − 1, wherever it calls
  waves itself: in a race (as M6's caretaker calls each window's wave), and for the sim harness's seats played by
  command that stack. It never stacks at Hard or Very Hard. Beside a present player it only counts as Ready, as
  before. On a hollow nobody is present at, a crew of caretakers (a race team of two: Race the caretaker for a
  party of two, the queue's caretaker mirror) says it for each wave *k* one of the crew's plans lists
  (`Caretaker.stacks_wave`), each once its own builds are paid: the horn still waits for every caretaker's Ready,
  and the crew stacks what each of them alone would, not only the waves both list (Lamplighter and Lookout list
  none alike; `sim_caretaker_crew_stacks_every_list`).
- **The codec's M8 block** follows M7's and is written only when the match holds what the M1 to M7 records cannot
  say: a hollow with two or more waves on its road, an older wave's spawns still to come (`behind`), a creep of an
  older wave than its hollow's newest, a race's kills of a stacked wave, or a level other than Normal (its
  `DIFFICULTY_IDS` index; decode refuses bytes whose level is not the rules'). It holds the level (u8), then per
  hollow its `cleared` (u16) and its `behind` (a u16 count, then u8 kind, u16 wave, u32 tick each), the creeps of
  another wave than their hollow's newest (a u16 count, then u16 index and u16 wave each), and per team its
  `stack_kills` (a u8 count, then u32 each). classic, and every Normal match nobody stacked in, keep their
  checkpoint bytes and state hashes: every High Water and duel gate's summary is the same before and after A's
  merge.
- **API** for the views and the tests: `SimMatch.waves_on_road(hollow) -> PackedInt32Array` (oldest first),
  `can_stack(hollow) -> bool` (a present seat's Ready in this wave would be taken), `stack_pay(hollow) -> Array`
  (`[window part, stake part]`, both in gold, were the stacked horn to sound now: the window's whole seconds and
  `stake_pm` per mille of the stake, rounded down; `[0, 0]` outside a wave; the two were one number only at
  `stake_pm` 1000), `road_tolls(hollow)` (the stake itself, in lives: the creeps walking and, in a wave, those still
  to come), `spawns_left(hollow)` (every wave's still to come), `cleared_waves(team)` as above, `SimCreep.wave`,
  `SimHollow.behind`. The sim harness: `play_out(by_command, every, limit, ready_at_once, stacking)`, where
  `stacking` maps a seat played by command to `"plan"` (it also stacks its plan's list) or `"all"` (it stacks every
  wave it may), and `cfg` takes `"difficulty"`.

## 3. The levels (A rules, C wire, B screens; design §2.6)

| Level (wire id) | On screen | `hp_pm` (creeps) | `boss_hp_pm` | `boss_armor_c` | `lives` |
|---|---|---|---|---|---|
| `normal` (0) | Normal | 1000 | 1000 | 0 | the preset's (20) |
| `hard` (1) | Hard | 1300 | 1500 | 100 | 15 |
| `very_hard` (2) | Very Hard | 1600 | 2000 | 200 | 10 |

Every number but Normal's is *tunable* by A against the gates. As tuned (`content.gd`'s `DIFFICULTIES` says why):
Hard 1100, 1500, 100 and 15; Very Hard 1150, 1550, 100 and 10. A's gates took both levels' creep health down from the
first numbers. Very Hard's bosses came down from 2000 and 200 on 2 November 2026, after the playtest `halv` s3 (H3-02)
found Very Hard "a wall at wave 6, not a close wave 12" and its gates were held to the owner's "a close wave 12"
(core-loop §10, item 16) on the Crest: it dies, or reaches the Holdfast with at most a quarter of its health left; a
win keeps at most half the lives; and at least half of the six crews (each Builder alone, the two complementary
pairs) win (`difficulty_very_hard_half_win`). Each level keeps fewer lives and more creep and boss health than the
level before, as `contract_m8_tables` holds, so Very Hard's Bristlesow has more health than Hard's.

The owner decided the wave-6 boss at Normal on 2 November 2026 ("Yes, at Normal"; core-loop §10, item 19): every
Builder's plan alone kills the Bristlesow at Normal (`bot_kills_bristlesow_solo_*`), where the Lamplighter's and the
Lookout's had leaked it for 5 lives. Normal still lays nothing and the Bristlesow's own numbers stay. The plans answer
it (A's files): the Lamplighter's High Water opening forks an Iron Mortar before her third arrow and the Lookout's
builds a Siege Perch before her second Kestrel Flock. Their duels keep the orders before it (the plans' `undertow`
blocks), so no duel gate moved. At Hard and Very Hard the Bristlesow stays a toll that a strong opening comes near.

- **`SimContent.rules(mode, difficulty := "normal")`:** the preset, with `"difficulty"` set to the level played
  and, where the preset has `levels`, the level's keys laid over it: `lives` replaced; `hp_pm`, `boss_hp_pm` and
  `boss_armor_c` added. A preset without `levels` plays Normal whatever is asked:
  `SimContent.level_of(mode, difficulty)` is the level a match of that mode plays.
- **At spawn** (`SimWaves.spawn`): `max_hp_c = hp_c × (1000 + growth) × seats_pm / 1000000` as before, then
  `× level_pm / 1000`, with `level_pm` the rules' `boss_hp_pm` for a boss and `hp_pm` for any other creep (absent:
  1000); a boss's `armor_c` gains `boss_armor_c` where `armor` is on. At Normal nothing changes. Bounties, tolls,
  gold, windows, waves and counts are the preset's at every level.
- **Everywhere a mode travels, its level travels with it:** `MATCH_CONFIG` (§5), `Session.match_spec`
  `"difficulty"`, the replay record (`LocalSequencer`'s `"difficulty"`), the desync dump (format 2: a u8 level
  after the mode; `DesyncDump.read` takes format 1 as Normal), the sim harness's `cfg`.
- **The party's** (C): the leader picks it like the mode (`PARTY difficulty`); a change clears every Ready and
  stops a countdown; refused while queued; a party keeps it through a mode change. A new party starts at its
  creator's: the game sends `PARTY difficulty` after its `create` when its profile's level is not Normal.
- **Offline and in a party of one,** the profile's: `Profile.difficulty`, saved in `user://profile.cfg` beside the
  mode. Session's API for B (C writes it): `Session.difficulty_id()` (the party's where in one, else the
  profile's), `Session.set_difficulty(id)` (the profile's always, and the party's when the leader), and
  `Session.offers_difficulty(mode)` (from `protocol.json`'s `levels`). Every match the hub starts plays the level
  the hub shows: Play, Try and Race the caretaker; Duel the caretaker and a classic boot play Normal.
- **On screen** (B): `Game.DIFFICULTIES[id]` = `name`, `tip`. The hub's three words beside the mode line, the
  party's lit, the leader's click picking (core-loop §5.2), grey in Undertow; a level other than Normal named
  wherever the mode is: the hub's mode line, Match Found, the loading title, the results' subtitle, the Esc menu
  and Try's tooltip. Lives read out of the level's own ("4 of 10 lives left").
- **The caretaker** plays the same plan at every level and stacks only at Normal.
- **The queue** (C): keyed on mode, rules hash and the level the match plays (`level_of`, so every duellist meets
  at Normal); the caretaker offer after 60 s and Start with caretakers keep the party's level.

## 4. A rival bottle's candidates (A query, B views; design §1.4)

- **The hidden-information rule** (contract-m7 §2 and §3: the rival sees a corked bottle's tier and price only)
  now reads: **a rival's corked bottle shows its tier and its candidates, the packs its window offered at that
  tier, and never which one.** The commitment still hides the pack. Nothing is added to `CORK`, to the bottle or to
  the state: the Drift is the same for both sides and lies in every client's state (`EV_DRIFT`,
  `SimMatch.drift_packs`), so the candidates are what a careful player could already work out, now on screen. With
  one tier a window, as the preset has it, a bottle's candidates are its window's three offered packs; a window that
  ever offers two tiers would narrow them.
- **A:** `SimUndertow.candidates(m, bottle) -> PackedInt32Array`, the `CHECK_IDS` indexes of the packs offered in
  the bottle's window at its tier, in `CHECK_IDS` order; `SimMatch.bottles(seat)` gives a corked bottle's
  `candidates` as `CHECK_IDS` ids beside its tier. A corked bottle's window is always the Drift's current one (its
  wave cannot clear while it is corked, so no window opens to draw again), so the query reads `drift_packs`; it
  never reads the commitment.
- **B**, the duel's views:
  - **The Drift tray:** under each rival bottle, its candidates' pack icons, small and dim, beside the tier
    numeral; `DriftTray.rivals_shown()` gains `candidates`.
  - **The bottle's tooltip:** "Your rival's bottle · Tier II, corked for wave 7. It holds one of: 14 Gourdlings
    (Gourd Rush), 5 Thornbacks (Thorn Herd) or 5 Duskmoths (Moth Cloud). Which one stays hidden until it is
    uncorked." Counts are the bottle's tier's (`SimContent.PACKS`), names `Game.PACKS`'. When the rival corked two
    bottles in one window, each tooltip adds "Both may hold the same pack."
  - **The duel bar:** the rival's row ends with its corked bottles' candidates by check while one is corked for the
    coming or running wave: "Rival · 18 lives · 0 breach · +6 a wave · Seawall 1 · corked II: Swarm, Armored or
    Winged" (`DuelBar.lines()`), the checks a defender holds gold for.
  - My own bottles, the uncorking and the fizzle are shown as in M7.

## 5. The protocol (track C)

The difficulty's change, and only that. Stacked waves are the simulation's alone and need no message.

- **`version` 2,** subprotocol `groundhold.v2` (the upgrade already accepts any `groundhold.vN`): a layout changes,
  so a game of version 1 hears `ERROR` 2 and a version-2 game at a version-1 server hears 17 (server README, "A
  change of the protocol's version": tag promptly after the merge).
- **Numbered values:** `difficulties` = `{"normal": 0, "hard": 1, "very_hard": 2}`; `modes.high_water.levels` and
  `modes.tide_race.levels` = true.
- **`PARTY` op `difficulty` (12):** `[["difficulty", "u8"]]`. The leader's, while forming: every Ready cleared, a
  countdown stopped, the party's `PARTY_STATE` to every member. A member's, or one while queued, loading or in a
  match, is answered to the asker alone with the party as it is; a level past 2 is `ERROR` 6.
- **`PARTY_STATE`:** `["difficulty", "u8"]` after `mode`. The no-party state says 0.
- **`MATCH_CONFIG`:** `["difficulty", "u8"]` after `mode`: the level the match plays (`level_of`: 0 for a mode
  without levels), from the party or from the queue's key, and on a rejoin the match's own.
- **Unchanged:** `HELLO` (its rules hash covers every level), `LOADED`, `MATCH_FOUND` (the queue matches one level,
  so each party's own is the match's), `QUEUE`, `QUEUE_STATE`, `ACCEPT`, `RESULT`, `MATCH_END`, the beacon, every
  message of a match and the commands' layouts (`READY`'s new refusal is the simulation's). One range moves (the
  review): `READY`'s `b`, 0 before, is 0 to 65535, the wave a `READY 1` calls (§2); the server checks only the
  range, `test_contract_m8.py` and `test_turn_stamping.py` hold it, and no transcript records a `READY` naming a
  wave, so none changes.
- **The server:** `party.py` (the party's `difficulty`, `set_difficulty`), `queue.py` (tickets keyed on mode, rules
  hash and level; `waiting` and `look` by all three), the match's `MATCH_CONFIG`, `--dev-match MODE:N[:LEVEL]`
  (`high_water:2:hard`), `/stats` matches by mode and level, and the README's byte tables
  (`server/tools/protocol_tables.py`).
- **Transcripts:** every one is re-recorded (each carries the version and the changed layouts) with
  `python3 server/tools/record_transcripts.py`, and `protocol_golden_m1` to `_m7` follow; new: `m8_difficulty` (a
  leader sets Hard, a member's `difficulty` refused, a Hard party queued beside a Normal one and not merged with
  it, `MATCH_CONFIG` with level 1), decoded by `protocol_golden_m8`.

## 6. The fork pass (track D, after A's merge; design §3.8)

- **The bench,** `tests/sim/fork_bench.gd` (D): bare simulations in the sim harness, High Water at Normal, one seat
  of the form's Builder with its perk, the form built and forked on the bench cell (8, 11); both branches of a pair
  on the same cell against the same creeps. It reads health removed (each hit's damage less the killing hit's
  overkill) from the HIT events. Its measures, each defined in core-loop §3.8: `single(creep)`, `crowd(creep)`,
  `control(creep)` and `lift(lane)`; `measure(form, job) -> int` and `pairs() -> Array` (per pair: both branches on
  both jobs), and a `FORK_BENCH` line a pair.
- **Each branch's job** is core-loop §3.8's table: from §3.4's deepen and patch, and the check a branch helps.
- **The gate,** `fork_pairs_apart` (tests/balance, written by the generator): on its own job each branch does at
  least `JOB_MARGIN_PM` (250, *tunable*) more than its sibling (a sibling that cannot do the job is apart); no
  branch is 10% ahead on both jobs; a patch's measure on its job is at most 90% of the best form, base or branch,
  of a Builder strong against that check. Its watches hold the bench's lines.
- **The numbers** live in `content.gd`'s `TOWERS`, each changed one with its reason beside it. The numbers classic
  plays never change: the Lamplighter's three bases and her three A branches (Longbow Loft, Great Cannon, Deep
  Frost). `fork_branch_stats` and every scenario that pins a form's numbers (`apiary_bonus_to_fliers`) follow.
- **First proposals** are core-loop §3.8's: the Royal Apiary 28 every 0.8 s with +100% to fliers; the Queen's Guard
  54 every 1.4 s, pierces 4, no flier bonus, aiming at the most health in reach (`"aim": "most_hp"`, which
  `SimTargeting` already serves); the Iron Mortar every 1.3 s; the Kestrel Flock 10 a strike; Twin Gaze +25% on
  each of two; the Long Hum 18%; the Ringing Clapper and the Long Chime measured first.
- **Acceptance:** `fork_pairs_apart`, and every balance gate after the pass with its bar unchanged (the plans move
  first where one fails; D owns `data/plans/` from A's merge); `sim_bench` above its floors (a Queen's Guard that
  aims at the most health walks the road differently from one that takes the first).
- **What the pass set** (D): the bench as `fork_bench.gd` writes it (a crowd's line at three times wave 7's health,
  holding and lifting lines at fifty times, so no measure saturates; a `single` at every creep health the game plays,
  one to four seats at every level, and a crowd or a hold on every cell the base's Builder's plan builds it on, a pair
  apart at each; the Sky Toll's job measured by a flier's damage and its hold on a line of fliers, its slow held to
  the patch ceiling), its numbers and the reasons beside each in `content.gd`'s `TOWERS`, the table before and after
  in core-loop §3.8. One stated exception: the Sky Toll's damage to a flock is not held, since on its bends it does
  what the Royal Apiary does there, as the Bellfounder's one tower for the sky at Hard needs (core-loop §3.8). The four gates A held (§9, core-loop §4.4: the Bellfounder and the Lookout alone at Hard and Very
  Hard) stand by the Clapper Tower's 35 and two plan orders, and the generator's `HELD` is empty. Beside the pass,
  the owner's decision of 2 November 2026 raised Tide Race's `race.life_t` from 600 to 3600 ticks (contract-m6 §4's
  number; `contract_m6_tables` holds the new one), held by `race_pair_stacking_every_wave_not_dominant`.

## 7. Who owns what

| Track | Owns (writes) |
|---|---|
| A rules | `scripts/sim/*`, `data/plans/`, `tests/sim/` (not `art_*`, `fork_*`), `tests/balance/`, `tools/gen_balance_scenarios.py`; scenarios `sim_*`, `stack_*`, `difficulty_*`, `race_*` of the simulation, `bottle_candidates_*`, and the gates of core-loop §4.4 but `fork_pairs_apart` |
| B views and hub | `scripts/main.gd`, `game.gd`, `hud.gd`, `resource_strip.gd`, `build_controller.gd`, `scripts/ui/*` (`hub_panel.gd`, `shell.gd`, `builders_screen.gd`, `loading_screen.gd`, `results_panel.gd`, `match_found.gd`, `match_menu.gd`, `party_strip.gd`, `drift_tray.gd`, `duel_bar.gd`), `scenes/`, `tests/bot.gd` (it can stack its plan's list through the game's input route, off unless asked, so `bot_wins_classic` and the smokes play as before), `tools/play/describe.gd` (the new words), `art_src/`, `ui/`; scenarios `view_*`, `hud_*` |
| C server and protocol | `server/*`, `shared/net/*`, `scripts/net/*`, `scripts/session/*`, `tests/net/*`, `tools/net/smoke.py`; scenarios `flow_*`, `net_*`, `protocol_golden_*` |
| D fork pass | from A's merge: `scripts/sim/content.gd`'s `TOWERS` numbers and their reasons, `tests/sim/fork_bench.gd`, `fork_branch_stats.gd`, the scenarios that pin a form's numbers, `data/plans/`, `tools/gen_balance_scenarios.py` and `tests/balance/` |

Each track adds only newly named scenarios and its own lines in `AGENTS.md` and `CHANGELOG.md` (`## Unreleased`).

## 8. Order

- **Day 0, a seam commit** before the tracks branch: `DIFFICULTY_IDS` and a `DIFFICULTIES` table holding `normal`
  only in `content.gd`, `REFUSE_NO_STACK` in `sim_types.gd`, `difficulties` and the two `levels` flags in
  `protocol.json` (no message changed yet, so the version stays 1 until C's change), and `tests/sim/contract_m8.gd`
  with `contract_m8_tables`.
- **A, B and C start together.** B reaches A's and C's API not merged yet (`SimMatch.waves_on_road`, `can_stack`,
  `stack_pay`, `SimUndertow.candidates`; `Session.difficulty_id`, `set_difficulty`, `offers_difficulty`) through
  guarded access gathered in one place in `game.gd`, as M6's and M7's views did, and a short finishing pass after
  both merge switches it to direct calls and plays B's scenarios on the real rules and a real party. C's server
  and A's rules share only `protocol.json`'s `levels` and the wire ids, which day 0 fixes.
- **D starts on A's merge:** balance follows the rules, and the stacking and level gates must stand before the
  pass is held to them. D changes no view file; where a form's job changes its words (the Queen's Guard's aim),
  D writes the line into `Game.TOWERS` in its own commit after B's merge.

## 9. Acceptance

**A:** `stack_ready_in_a_wave` (taken in a wave; the horn sounds on the tick the Ready lands, the called wave's
first creep on that tick and the older wave's schedule untouched), `sim_stacked_waves_spawn_together` (both
schedules on one tick, the older's creep first, each creep its own wave's health, a checkpoint and a client joined
from it while both send), `stack_at_most_three` (`NO_STACK` with three on the road and in the last wave; named
`stack_at_most_two` while `stack_max` was 2), `stack_pays_window_and_stake` (the window's whole seconds plus the
tolls of the creeps on the road and still to come, `EV_GOLD` "stack"),
`stack_clears_in_order` (a younger wave with an empty road clears right after the older; each clear pays its own
bonus and Tithe once), `stack_no_window_between`, `stack_ready_carries_into_window`, `stack_ready_names_its_wave` (the
review: a READY 1 taken only for the wave its `b` names), `stack_waits_for_returning`,
`stack_not_in_classic_or_duel` (`WRONG_PHASE` in both; `contract_ids_keep_state_hashes` still green),
`race_stacked_fall_wave` (the oldest wave on the road, its own creeps' kills),
`sim_caretaker_stacks_its_list_in_a_race`, `difficulty_rules_apply` (lives, creep and boss health, boss armour
exactly by §3's formula), `difficulty_normal_changes_nothing` (High Water at Normal hashes as before A),
`sim_checkpoint_roundtrip_m8` (a stacked race at Hard, round-tripped while two waves walk and while two send),
`bottle_candidates_are_its_window_offer` (the same on both clients, never a pack id before the uncorking), and
core-loop §4.4's stacking and level gates; every earlier gate's summary unchanged but `race_mirror_is_fair` and
`race_bots_both_finish`, which hold their bars.

**B:** `hud_stack_ready_in_a_wave` (the second press, "Waves 6–7 / 12", the Ready tooltip's pay),
`hud_stack_refusals_said`, `view_stack_banners`, `view_difficulty_hub_words` (the leader's pick, a member's words
that answer no click, Undertow's grey), `view_difficulty_named` (Match Found, loading, results, the Esc menu,
Try's tooltip), `view_duel_bottle_candidates` (tray, tooltip and bar from the real preset, on both clients alike),
`bot_stacks_through_its_orders` (the plan bot's stacked calls go out through the game's input route, the second
press included; `bot_wins_classic` still green), and after the review `hud_stack_late_press_race_latency_2` to `_4`
and `hud_stack_late_press_partner_latency_2` to `_4` (online, 100 to 200 ms each way: a press late in a window asks
for a second by the order's lead and trip, a READY that lands after the horn calls nothing, and the second press
waits for the horn).

**C:** Python `test_party_flow` (the op, its refusals, Ready cleared, a countdown stopped), `test_queue` (the level
in the key; a Hard party never meets a Normal one; a duel at Normal whatever its party chose), `test_versions`
(version 1 hears 2), `test_contract_m8.py`, the re-recorded transcripts, `protocol_golden_m8`,
`flow_difficulty_party_and_queue` (through the lobby fake), `net_rejoin_keeps_level` (a rejoin's `MATCH_CONFIG`
builds the same level), `smoke.py --flow --difficulty hard`.

**D:** `fork_pairs_apart`, `fork_branch_stats`, every balance gate, `sim_bench`.

**After the merges:** the whole suite, every gate, `--determinism`, every smoke, the live scenarios against a
version-2 server.
