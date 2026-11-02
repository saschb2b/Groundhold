# The M7 contract

M7 (Undertow, [`core-loop.md`](core-loop.md) §1.4 and §8) runs as three tracks from one commit, this one: **A** rules
(the simulation, the caretaker's corking and the duel's balance gates), **B** the duel on screen (the Drift tray,
the duel bar, corking and uncorking from the client, the Seawall key, the duel's results, its art and sounds) and
**D** the duel around a match (Find a rival for a duel, Duel the caretaker, the hub's Undertow button). Anything
named here keeps its name and number until the tracks agree to change it; values marked *tunable* are the design's,
and track A may change them against the gates. [`world.md`](world.md) wins on names. Undertow plays Wickhollow and
its reflection, the race's layout; maps come after the modes (the user's decision of 2026-11-01).

`contract_m7_tables` (`tests/sim/contract_m7.gd`) guards the ids, the packs, the event numbers, the commitment's
bytes and, once track A adds it, the `undertow` preset.

## 1. Ids and tables

- `MODE_IDS` appends `undertow` (3, its wire id). `RULES` gains the preset in track A; until then the hub keeps the
  button greyed (`Profile.offers`).
- **Packs are checks.** A pack's id is the `CHECK_IDS` id it tests (`swarm`, `swift`, `armored`, `winged`), on the
  wire and in the codec as its `CHECK_IDS` index. `content.gd`'s `PACKS[map][check]` names the creep it sends and
  its count per tier: on the hollow, Gourdlings 6, 14, 20; Scuttlers 8, 17, 28; Thornbacks 3, 5, 9; Duskmoths 4,
  5, 7 (*tunable*; the Scuttle, the Thorn Herd and the tier II Moth Cloud retuned by the sends' pass, the owner's
  decision of 2 November 2026: 6, 10, 14; 2, 3, 5; and 6 before; then by the packs' matrix, each pack against the
  Builders weak to its check: the Gourd Rush 6, 10, 14, the Scuttle 8, 13, 18, the Thorn Herd 3, 5, 7 and the
  Moth Cloud 4, 5, 9 before). Display names are `Game`'s: `Game.PACKS[map][check]` = `name`, `icon` (Gourd Rush,
  Scuttle, Thorn Herd, Moth Cloud on Wickhollow), so no map's flavour reaches an id.
- **Events** (`sim_types.gd`): `EV_DRIFT` 21, `EV_CORK` 22, `EV_UNCORK` 23, `EV_FIZZLE` 24, `EV_BREACH` 25,
  `EV_SEAWALL` 26, `EV_SURGE` 27, with the fields their comments list. Refusals are M1's reserved ones:
  `NO_CORKS_LEFT` (7), `TOO_EARLY` (8), `NOTHING_CORKED` (9), `BAD_REVEAL` (10), `NO_CHARGE` (11),
  `SEAWALL_STANDING` (12); a cork outside a window or a seawall outside a wave is `WRONG_PHASE`.

## 2. The rules (track A; design §1.4)

- **Preset `undertow`:** `high_water`'s keys with `teams` 2, `seats` [2, 2], `clock` `"shared"` (both hollows' windows,
  Ready and horn are one: the horn sounds when both seats are Ready or the shared countdown ends) and a `duel` block
  (*tunable*): `drift_from` 2; `offered` 3; `tiers` `[{"windows": [2, 4], "price": 45, "stipend": 4}, {"windows":
  [5, 8], "price": 55, "stipend": 6}, {"windows": [9, 12], "price": 85, "stipend": 12}]` (the sends' pass: tier I
  was 30 and tier III's stipend 8, so a tier paid back about its price from its first window: 124%, 120% and 99%,
  where they were 187%, 120% and 66%); `corks` 1, and
  `corks_two` 2 from window `corks_two_from` 9; `uncork_after_t` 180 (3 s after the horn), `auto_uncork_t` 1440
  (24 s, the client's), `fizzle_t` 1500 (25 s); `pack_interval_t` 30 (an uncorked pack's creeps set out half a
  second apart); `breach_pay` 2 (times the bounty); `send_hp_pm` 1250 (the sends' pass: an uncorked creep's health,
  per mille of the wave's own of its kind, so a sent creep comes a quarter stronger); `pack_hp_pm` `{"swarm": 1500,
  "swift": 1400}` and `pack_gap_t` `{"swarm": 15, "armored": 60}` (the packs' matrix: a pack's own premium in place of
  `send_hp_pm` and its own spacing in place of `pack_interval_t`, by the check it tests, so a Gourdling comes half
  again as strong and a Scuttler two fifths, a Gourd Rush a quarter second apart and a Thorn Herd a second apart);
  `seawall` `{"every_lives": 4, "charges": 2,
  "radius_mm": 3000, "stun_t": 120, "hp_pm": 250, "boss_hp_pm": 80, "boss_slow_pm": 500, "cooldown_t": 900}`;
  `surge` `{"waves": [9, 10, 11], "hp_pm": 1350, "window_t": 480, "cork_price_pm": 500}`.
- **The Drift:** from window `drift_from`, each window offers `offered` of the four packs, drawn from the match's
  `SimRng` (identical on both sides, so both see the same offer); the left-out pack is never left out twice in a row.
  `EV_DRIFT` names them. `SimMatch.drift_offer()` gives the current window's.
- **Cork:** `CORK(a = tier index, b, c = the commit's two halves)` in a window, for a pack of that tier offered in
  this window, charges the tier's price at once and stands a bottle (`EV_CORK`; the rival sees tier and price only).
  At most `corks` per window. `UNCORK(a = pack, b, c = the salt's two halves)` during the next wave, from
  `uncork_after_t` after the horn: the simulation recomputes the commit and spawns the pack on the **rival's** road
  (`sent_by` the seat, each creep with its pack's premium on its wave's health, `pack_hp_pm` or else `send_hp_pm`,
  and `pack_gap_t` or else `pack_interval_t` after the one before) only if it matches and the pack was offered in
  the bottle's window; otherwise `BAD_REVEAL`.
  A bottle with no valid reveal by `fizzle_t` fizzles (`EV_FIZZLE`): the gold stays spent. A wave a rival's bottle
  is corked for does not clear while the bottle is corked or its pack is still to come (`SimUndertow.holds`), so a
  fast wave never ends before its sender may uncork: the defender's road may stand empty while its wave waits (up
  to `fizzle_t` after the horn; `SimMatch.wave_held(hollow)` tells a view), and since the next window opens for both
  hollows only once both have cleared, the bottle holds back both hollows' window that long. The stipend's gain starts at the uncorking; stipends pay at
  each wave clear as `EV_GOLD` `why` `"stipend"`, and in the Surge they are still paid but no longer grow.
- **The commitment** (both the client and the simulation compute it, through `SimUndertow.commit(match_seed, seat,
  window, pack, salt_hi, salt_lo) -> [b, c]`): SHA-256 through `HashingContext` over, in order, the match seed as 4
  bytes big-endian, the seat (1-based, as the simulation numbers it) as 1 byte, the window (the wave it precedes) as
  1 byte, the pack's `CHECK_IDS` index as 1 byte, and the salt as 8 bytes (`salt_hi` then `salt_lo`, each 4 bytes
  big-endian of the unsigned 32-bit value). The first 8 bytes of the digest are the commit: `b` its first 4 bytes and
  `c` its next 4, each read big-endian as an unsigned 32-bit number and carried as the signed `i32` with the same
  bits (subtract 2³² from 2³¹ up). The salt's halves travel in `UNCORK` the same way. A caretaker corks with salt 0
  (its corks are not hidden).
- **Breach:** an uncorked creep that reaches the rival's Holdfast takes its toll and pays its sender `breach_pay`
  times its bounty (`EV_BREACH`); one killed pays its killer the normal bounty.
- **Seawall:** each `every_lives` lives a Holdfast loses add a charge, at most `charges`. `SEAWALL` (no arguments)
  during a wave spends one: every creep within `radius_mm` of the seat's Holdfast is stunned `stun_t` and loses
  `hp_pm` of its maximum health; a boss loses `boss_hp_pm` and is slowed `boss_slow_pm` instead. Cooldown
  `cooldown_t` (`SEAWALL_STANDING` meanwhile). `EV_SEAWALL`.
- **End:** a Holdfast that falls loses at once (both on one tick: a draw). If both stand after wave 12, the Surge
  repeats `surge.waves` with `hp_pm` health, windows of `window_t`, stipends frozen and corks at `cork_price_pm` of
  their price (`EV_SURGE`). After the third surge wave, more lives wins, then more breach dealt (lives taken by
  uncorked creeps), then a draw. `SimMatch.outcomes()` and `decided_by()` (adding "fell", "lives", "breach", "draw")
  serve the duel as the race; `breach_dealt(team)`, `stipend(seat)`, `bottles(seat)` (each `{id, tier, window,
  uncorked, fizzled}`; the pack only once uncorked), `seawall_charges(seat)` and `seawall_ready_tick(seat)` are for
  the views. All new state goes in the codec's trailing block (written only when set), so earlier modes keep their
  checkpoint bytes.
- **The caretaker** in a duel builds from its plan and corks by a policy (the cheapest tier, while its corks stay
  within `CORK_SHARE_PM`, a fifth, of everything it holds, corked before the plan spends: a plan always waits on a
  step it cannot pay yet, so "keeping its plan's next build" never corks; the pack the rival's defence has shown it
  should send, all of it public and never a rival's bottle, `SimUndertow.pick_pack`: the offered check of which the
  most creeps have reached the rival's Holdfast so far, from two (`SimTeam.leaked`, in the codec's M7 block), else
  the winged pack where the rival's towers deal a flier less than half what they deal the ground, else the one its
  towers take longest to kill, `weakest_pack`; since the sends' pass, `CARETAKER_VERSION` 6, where it was
  `weakest_pack` alone; uncorked at `uncork_after_t`), so `duel_caretaker_plays_full_match` and Duel
  the caretaker have a rival. It plays the first tick of the shared window (`SimUndertow.shared_window_tick`) and
  only then says Ready, so a player's instant Ready never takes its window. While its hollow stands in its window
  and the rival's still plays the wave, its plan waits (`Caretaker.holds_plan`), so on that first tick it corks
  before it builds.

## 3. The duel on screen (track B)

The client holds each bottle's salt (8 bytes from `Crypto`, never sent before the uncorking), keyed by bottle,
through link losses (a world loaded after a resync or a rejoin is matched to the salts by the bottles' commitments,
since it may number its bottles otherwise); it uncorks by itself at `auto_uncork_t` after the horn if the player has not (a networked game
sends that UNCORK ahead by the turns it holds and has not run, so it runs then however far behind it plays, the trip
left in the margin to `fizzle_t`). **Space** or a
click on a corked bottle uncorks during a duel wave (Space is Ready elsewhere); **F** spends a Seawall charge. The
**Drift tray** shows the window's three packs with their tier price and Q-row-free keys (click to cork), your corked
bottles, and the rival's bottles as corked shapes with their tier. The **duel bar** shows both sides' lives, breach
dealt, stipends and Seawall charges. Results get the duel titles ("The Tide Took Your Rival", "The Tide Took You",
"Even Tide") and the deciding rule. Art: the tray and bottle pieces in `art_src/ui/console.json` and `console.py`,
pack icons, the Seawall's burst, and sounds `cork`, `uncork`, `breach`, `seawall`.

## 4. Around the match (track D)

Find a rival for a duel through the queue (one player each side; Builder clashes never apply across sides);
Duel the caretaker offline and after the queue's 60 s offer (the rival a caretaker of your Builder); the hub's
Undertow button once `RULES` has the preset; `smoke.py --mode undertow`; the fake sequencer and `flow_*` scenarios
for the duel's queue and party.

## 5. Who owns what

| Track | Owns (writes) |
|---|---|
| A rules | `scripts/sim/*` (with the new `sim_undertow.gd`), `data/plans/`, `tests/sim/` (not `art_*`), `tests/balance/`, `tools/gen_balance_scenarios.py`; `sim_*`, `duel_*` and rules scenarios |
| B duel on screen | `scripts/main.gd`, `game.gd`, `hud.gd`, `resource_strip.gd`, `build_controller.gd`, `tower.gd`, `creep.gd`, `projectile.gd`, `fx.gd`, `sfx.gd`, `scripts/ui/duel_bar.gd`, `drift_tray.gd`, `loading_screen.gd`, `results_panel.gd`, `party_strip.gd`, `scenes/main.tscn`; `art_src/`, `ui/`, `models/`, `sfx/`, `asset_manifest.json`'s own entries; `view_*`, `hud_*` and duel view scenarios |
| D around the match | `server/*`, `shared/net/*`, `scripts/session/*`, `scripts/ui/hub_panel.gd`, `match_found.gd`, `shell.gd`, `builders_screen.gd`, `tests/net/*`, `tools/net/smoke.py`, `flow_*` and `net_*` scenarios |

Each track adds only newly named scenarios and its own lines in `AGENTS.md` and `CHANGELOG.md` (`## Unreleased`).
All three start together; B reaches A's not-yet-merged API through guarded access gathered in one place in
`game.gd`, as M6's views did, and a short finishing pass after the merge switches it to direct calls and plays the
duel scenarios on the real preset.

## 6. Acceptance

**A:** core-loop §8 M7's list (`drift_same_for_both_sides`, `drift_seeded`, `drift_never_skips_a_check_twice`,
`cork_commit_hides_pack`, `uncork_reveal_checked`, `uncork_auto_at_24s`, `fizzle_without_reveal`,
`uncorked_creeps_pay_defender`, `breach_pays_double`, `seawall_charges_every_four`, `seawall_stuns_near_holdfast`,
`surge_freezes_stipend`, `tiebreak_lives_then_breach`, `duel_caretaker_plays_full_match`) and §4.4's duel gates
(`duel_mirror_is_draw`, `duel_turtle_holds`, `duel_balanced_beats_turtle`, `duel_turtle_beats_reckless`,
`duel_counter_cork_beats_random`, `duel_seawall_saves`). **B:** the tray, bar, uncork, Seawall and duel results
scenarios, and the client's commitment matching the simulation's. **D:** `test_queue`'s duel cases,
`smoke.py --mode undertow`, the duel's `flow_*`. After the merge: the whole suite, the gates, `--determinism`, every
smoke, the live scenarios.
