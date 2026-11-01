# Working on Groundhold

Godot 4.7.1, GDScript. The game boots into the hub, `scenes/hub.tscn` (the main scene); a match runs in
`scenes/main.tscn`, where `scripts/main.gd` builds the map, Wickhollow, from `data/hollow.txt`, starts the match
and shows it. The design for multiplayer is `docs/design/core-loop.md`;
the world and every name are `docs/design/world.md`, which wins where the two differ.

The game is Groundhold. Every map's road runs from the Welling, where the Tide wells up, to the Holdfast the
players keep; on Wickhollow, the one map so far, they are the sunken field gate and the mill-house hearth, whose
models keep their file names (`models/props/rift_gate.glb`, `hearth.glb`), as do `data/hollow.txt` and
`palettes/hollow.gpl`. Lanterns, gourds, autumn and night are Wickhollow's and Tamsin Wick's own flavour: keep
them out of the game's name, the site, the server, the protocol, mode names and anything that runs on every map.
On the wire the server (`server/groundhold_server`, set from `GROUNDHOLD_SERVER_*`) speaks `groundhold.v1` at
`/causeway`; the modes are `classic`, `high_water`, `tide_race` and `undertow`, the Builders `lamplighter`,
`lookout`, `bellfounder` and `beekeeper`, and the boss is `hollowtide_crest`. `python3 tools/names_check.py`
fails, with file and line, on a retired name anywhere in the tracked tree (CI runs it); its allowlist is short
and says why each entry is there.

The rules run in an integer simulation, `scripts/sim/` (design §6.4): `SimMatch` steps 60 ticks a second from
(rules, seats, seed, turns), and nothing else decides what happens. Its tables, in integer units (ticks,
millimetres, micrometres along the road, hundredths of health, per mille), are `scripts/sim/content.gd`; balance
lives there. Turns come from a `TurnSource` (`scripts/net/`): offline the `LocalSequencer` seals one every 3 ticks.
Creeps, towers, projectiles, effects and the HUD are views that read the simulation's records and events, and
`Game` (`scripts/game.gd`) is the local seat's facade plus the display tables (names, models, icons). Input
sends commands (`Game.command`); a placed tower stands as a ghost until its turn runs.

`docs/design/contract-m2m3.md` fixes what M2 and M3 share: the id lists in `content.gd` (append only: the codec
stores indexes, and `contract_ids_keep_state_hashes` holds the classic match to its recorded hashes), the
`BUILDERS` fields, the new event and effect numbers, the display tables' icon paths and the Q W E / A S D card.
Load icons through `Game.icon(path)`, which gives a placeholder for art not painted yet. `contract_m2m3_tables`
checks it all.

`docs/design/contract-m4.md` fixes what M4's tracks (server, client, simulation, docs) share: `protocol.json`'s
resilience numbers and fields (a resume `HELLO` names its held `match` and `seat`; `MATCH_CONFIG`'s `rejoin` flag;
`RESYNC`'s reason, open turn, checkpoint hash and parts; `VISIBILITY`'s `shown`, `hidden` and `catching_up`), whose
rules are `shared/net/README.md`'s Resilience (M4); the checkpoint tick, a checkpoint's digest and parts
(`Checkpointing`, `protocol.digest`, `protocol.checkpoint_parts`); the dump's path (`DesyncDump.path_for`); and the
seams `checkpointing.gd`, `desync_dump.gd`, `web_bridge.gd`, `connection_overlay.gd` and `catchup.py`, stubs until
their track writes them. `contract_m4_wire_and_seams` and `server/tests/test_contract_m4.py` check it.

`docs/design/contract-m6.md` fixes what M6's tracks (rules, art, race views, queue) share: the ids appended to
`content.gd` (the Bellfounder's and the Beekeeper's eighteen tower forms, `tide_race`, `bronze_hand`, `hive_tithe`),
both kits, the new tower keys and the rules they carry (a pulse's stun and its immunity, the bee cloud, the crack and
haste auras, `air_bonus_pm`), `EV_PULSE` 19 and `EV_RACE` 20, the race's `SimMatch.outcomes()`, `race_time()` and
`decided_by()`, `Game.hollow_origin(h)`, the queue's `accept_ms` and `caretaker_offer_ms`, and who owns which files. A
model not built yet loads as `Models.placeholder()`, as an unpainted icon does as `Game.placeholder_icon()`.
`contract_m6_tables` checks it.

Two hollows (Tide Race, design 2.2 and 5.7): `main.gd` builds the world for as many hollows as its simulation plays.
With two, `board` (a `HollowMap` of every copy side by side, hollow h at `Game.hollow_origin(h)`, 26 tiles along x,
the two-tile band between filled with high ground) is what terrain, decor, the minimap and the build controller
count cells on; `map` stays one hollow's. The simulation's cells and millimetres are local to their hollow, so a view
adds the origin (`Game.board_cell`, `local_cell`, `world_at`, `hollow_at`); `scene.tower_at(cell)`, `build`, `fork`,
`sell` and `cell_center` take cells of my hollow (as the plan bot plays a race seat), `tower_on(board_cell)` and
`board_center` any. The camera starts over my hollow, Home frames it, V shows the rival's and back
(`camera.viewing()`); the minimap veils the rival's (`dimmed()`); an order or a signal on the rival's hollow is refused
before it goes out (`Game.RIVAL_HOLLOW`). `race_second_hollow_orders` plays a seat of the second team through the
controller (its build, signal and fork land on its own hollow) and `view_second_hollow_events` draws the second
hollow's fire, splash, signal and pulse there (the rings are in groups `blasts` and `signal_rings` while they show).
A race on the match scene is Tide Race's own preset: from the hub, Play in Tide Race races the caretaker
(`Session.play_offline`) and the scene builds both hollows from its start, as a networked race's `MATCH_CONFIG`
does (`race_rival_view_toggle`, `race_offline_against_the_caretaker`, `race_loading_two_rows`); a view test may also
`scene.begin('tide_race', seats, seed, LocalSequencer.new(n, my_seat), my_seat)` over a scene that stood with one,
which builds the world again. `godot-agent run . --scene res://tests/views/two_hollows_run.tscn
--renderer gl_compatibility --frames 320` (or `one_hollow_run.tscn`) plays a busy match of each as the browser draws
it and prints a `HOLLOWS_FRAMES` line every 60 frames it timed (draw calls, primitives, frame and physics time as
p50/p95, after a warm-up that leaves out the second build); compare two runs of the same length on one renderer.
On llvmpipe, over 240 frames with the camera on my hollow, two hollows drew 513/586 draw calls and 1.64 M
primitives in 728 ms a frame, one 505/555 and 0.81 M in 626 ms: the rival's terrain and decor are drawn too (one
MultiMesh a model over the board). Those milliseconds are the software rasteriser's. On a real GPU (an Intel Arc
B390, Mesa's OpenGL 4.6, 1280 x 720) the frame budget of design M6's acceptance holds: `godot --path .
--rendering-method gl_compatibility --fixed-fps 60 --disable-vsync --quit-after 400 res://tests/views/two_hollows_run.tscn`
(one tick and one drawn frame each, as fast as they go) times 300 frames at 9.0/10.5 ms with two hollows and
7.4/8.8 ms with one, against 16.7 ms for 60 frames a second; `godot-agent run ... --visible` (vsync, a 120 Hz
screen) shows 8.4/17.6 ms, a frame with a tick in it sometimes waiting a second vblank. The browser's own costs
(WebAssembly, WebGL through the browser) come on top and are not in these numbers.
The race's views (M6, design 5.6 to 5.8) read the simulation's race: `Game.outcome()` is my team's
`SimMatch.outcomes()` entry ("won", "lost", "draw"; "" until decided), and `main.gd`'s offline results and `RESULT`
line take it (`main.outcome()`; a race is decided by its win order, not by my hollow's phase:
`race_offline_outcome_rival_fell`, `_time_lost`, `_draw`, `_cap`). Offline the scene steps a match no further once it
is over, so the results show the decided state. `Game.over()` is the match over for me: my hollow done or fallen,
the match over, or a race decided while my hollow still played (the rival cleared first, or fell and I cleared that
wave); from then `Game.order_refusal()` says "The match is over", so no tower, fork, sell, signal or Ready goes out
between the decision and `MATCH_END`, the card greys and the party strip hides its Ready marks
(`race_decided_takes_no_orders`). The strip's second line (`Game.rival_line()`, `Hud.rival_line()`, the
`RivalLine` plate under the strip) reads the rival team's record: "Rival · Wave 7 · 18 lives · 6:12 +20 s" (its race
clock so far, `SimMatch.race_penalty_t`), or after its `EV_RACE` "fell" "Your rival fell on wave 9. Clear wave 9 to
win" (`race_strip_rival_line`); my own clock leads it, "You 6:10 +10 s" (`Game.my_race_line()`,
`Hud.race_clock_line()`, gone once a Holdfast fell), and the hub's Tide Race tooltip and mode line say the win order
from the rules (`Game.race_rule_words(mode, short)`; `race_strip_my_clock_and_the_rule`). `EV_RACE` is
`Game.race_changed`: banners for a clear or a fall, and the decision's
title; a race's end plate waits for the decision, not for my hollow. The loading screen lays a race out in two rows
(`LoadingScreen.rows()`, `is_race()`; `Cards` and `CardsB`, `TeamRule`, `CoverageRow` and `CoverageB`), the results
one block per team, mine first (`ResultsPanel.team_lines()`, `race_time_text`; titles `Game.RACE_TITLES`, the rule
`Game.race_rule_line()` from `decided_by()`: "cleared first" only for a strictly earlier clear tick, else "Fewer lives
lost" (`race_offline_outcome_same_tick_lives`), and a draw names the rule that tied from the records,
`Game.draw_rule_line()`: the same race time, both fallen on one wave with as many killed, or the cap
(`race_offline_outcome_draw`, `_both_fell_draw`, `_cap_draw`)), and the party strip both teams, mine first
(`PartyStrip.seats_shown()`, the `RivalCaption`). `race_results_two_teams` pins the race seed 3 plays out (the rival
crew clears wave 12 first) and holds the plate to strings written out in the scenario, not to the functions that
make them.

`docs/design/contract-m7.md` fixes what M7's tracks (rules, the duel on screen, around the match) share:
`undertow` (mode 3), the Drift's packs keyed by check (`SimContent.PACKS[map][check]`, names in `Game.PACKS`),
`EV_DRIFT` 21 to `EV_SURGE` 27, the commitment's exact bytes (`SimUndertow.commit`), the `undertow` preset's
`duel` keys, and who owns which files. `contract_m7_tables` checks it.

The duel on screen (M7, track B; contract-m7 §3). `Game` is a duel's client side and reads the duel's rules directly:
`is_duel()` (`SimMatch.duel`), `duel_rules()` (`SimUndertow.rules_of`), `horn_tick()` (`SimMatch.horn_tick`), the
tiers, prices and corks of a window (`SimUndertow.tiers_in`, `cork_price`, `corks_allowed`, `corks_of`), the bottles
(`SimMatch.bottles(seat)`, `SimUndertow.pending` for those of the wave running), the sides (`breach_dealt`, `stipend`,
`seawall_charges`, `seawall_ready_tick`) and the Surge (`surge()` from `SimUndertow.surge_of`: the wave running, or in a
window the one it precedes; `surge_waves()`, `last_wave()` 15, `content_wave(n)`, so the strip says "Surge 2/3", the
wave banner and the strip's glyphs are the repeated wave's, and Ready is asked for up to the last). One clock: the
duel's wave runs from the shared horn until the last hollow clears (`duel_wave()`, `SimUndertow.wave_running`), so my
hollow may stand in its window while the rival's still waits for my bottle; corks go in only once the window is open for
both and drawn (`cork_window()`; else "The window opens once both waves are over", and the countdown says the rival's
wave still runs), the tray's packs are `SimMatch.drift_offer()` only then, uncorking and the client's own at
`auto_uncork_t` work while the duel's wave runs on either hollow, and no Ready goes out then: Space only uncorks, and
D, N, Space with nothing to uncork and the card's horn are refused before they go out with the window's words
(`Game.ready_refusal()`; the card's Ready greys and its tooltip says why), since a Ready said while the rival's wave
still runs would sound the horn on the tick the window opened, the caretaker Ready on its first tick
(`hud_duel_ready_waits_for_the_window`); a duel order whose turn comes after its moment (a cork run after the horn, an
uncorking or a Seawall after the wave's end) is told what passed (`refusal_text(reason, cmd)`, `WRONG_MOMENT`), never a
bare "Not now". In the Surge's last wave my hollow
may be done while the rival's still waits for my bottle: the simulation takes the UNCORK until the duel is decided, so
an uncorking meets the orders' refusal without my hollow's end (`_uncork_order_refusal`), while `over()` still shuts
every other order, build, fork, sell, signal, Ready, cork and Seawall (`view_duel_uncork_after_my_last_clear`). A bottle whose salt is not on this
machine shows "lost", Space says so, and its fizzle is told, as a rival's is; a wave held for the rival's bottle or
pack with my road empty (`SimMatch.wave_held`) says so on the strip (`Game.held_line()`), not "0 creeps left"
(`hud_drift_tray_asks_the_drift_in_a_build_window`, `view_duel_auto_uncork_at_24s`, `view_duel_fizzle_shown`,
`hud_duel_surge_strip`, `hud_duel_wave_held`; from the first window the wave list goes on into the Surge, under its
line (`SurgeHead`), as S1 to S3, each "wave 9 again" (`hud_duel_wave_list_shows_the_surge`), and
`Game.wave_name(n)` names waves 13 to 15 by it for the clear banner, a creep's line and a fall's rule; `duel_stage.cork_as(n, check)` and `ready_as(n)` play a rival seat no
client plays through the sequencer). `Game.cork(check)` draws an 8-byte salt from
`Crypto`, sends `CORK(tier, b, c)` with `SimUndertow.commit`'s halves and keeps the salt by bottle (`_corks`, through
a resync or a rejoin of the same match, never sent before the uncorking); networked it also files the salts in
`user://duel/<match>-<seat>.cfg` from the CORK to the duel's end (`Game.salt_match`, from the `MatchClient`), so a
game killed and started again takes them back with its seat, and a bottle a loaded checkpoint holds whose `EV_CORK`
this client never saw takes the waiting salt it was committed with (`_claim_corked`, by window and
`SimUndertow.commit`). Every attach first gives each kept salt to the bottle of the loaded world it opens, by the same
commitment, never by the id it was kept under (`_rekey_corks`: a RESYNC(desync)'s world may number bottles otherwise,
a refused build shifting `next_id`): one whose bottle is spent there goes, one no bottle there holds waits for its CORK
again, unsure, which the turns run again bring by its seq (`view_duel_resync_rekeys_salts`, through
`duel_stage.loaded_checkpoint` and `renumbered_checkpoint`). `EV_CORK` goes to its waiting cork by its seq, so a bottle the caretaker corked for my seat while
it was away (salt 0) takes no salt of mine and shows its pack (`my_bottles()`'s `caretaker`;
`hud_duel_caretaker_cork_takes_no_salt`, `view_duel_rejoin_claims_its_own_bottle`). An order the link drops is never
answered, so nothing waits on one: `BuildController.forget_pending` calls `Game.forget_duel_orders()` (the Seawall
and the uncorkings may go again; a waiting cork keeps its salt but is unsure, and no other cork goes out until it is
known), `_order_ran` lets go of a duel order still waiting below a later order of mine that ran (my orders run in
their seq's order), and `_drop_stale` of a cork whose window or a Seawall whose wave is over (`hud_duel_lost_orders`,
`view_duel_salts_survive_a_restart`), though a standing bottle of mine first takes the waiting salt it was committed
with (`_claim_corked`): `main.gd` hands the events over once a frame, so in a frame of several ticks the horn may move
the window on before the CORK's own `EV_CORK` is read (`view_duel_cork_survives_a_multitick_horn`). `uncork(id)` sends `UNCORK(pack, salt_hi,
salt_lo)`, Space (`BuildController.press_space`) or a click on a bottle corked for the duel's wave (on either hollow:
the tray's socket answers while `my_bottles()`'s `due`, `view_duel_uncork_by_click_in_the_rivals_wave`) and only from
`uncork_after_t` after the horn; `Game.before_tick()`, called by `main.gd` before every tick, sends the uncorking
itself at `auto_uncork_t` on the tick it falls due at any fast-forward, earlier by the ticks an order sent now runs
ahead of the simulation (`auto_uncork_send_tick()`, `TurnSource.order_lead`: 0 offline, online the turns held and not
run yet), so a game up to a second behind its turns, which still takes orders, has it run by `auto_uncork_t` with the
trip left in the second to `fizzle_t` (`view_duel_auto_uncork_while_behind`, its 30-frame hang read through
`loopback_main.gd`'s `sealed_turns`); F is `seawall()`; keys 1
to 3 cork the Drift tray's packs (both nothing, silent, outside a duel); each refusal is said here before anything
goes out (`cork_refusal`, `uncork_refusal`, `seawall_refusal`), its seconds read from `duel_rules()`
(`refusal_text(reason)`, `duel_seconds(key)`, the tray's words too: `hud_duel_timings_follow_the_rules`). While the client
catches up or reconnects (`_catching_up()`, as for a teammate's seat notice) the duel's events still change my corks and
orders but say nothing, no sound, notice or rival's moment from the turns a resync or a rejoin runs again
(`view_duel_catch_up_says_no_old_moments`). `my_bottles()`, `rival_bottles()` (tier only), `duel_side(team)`,
`drift_packs()`, `cork_price(window)`, `duel_title()` and `duel_rule_line()` feed the views: the Drift tray
(`scripts/ui/drift_tray.gd`, `packs_shown()`, `mine_shown()`, `rivals_shown()`, `tip_shown()`) on the left wing over the
minimap, the duel bar (`duel_bar.gd`, `lines()`; hovering a side's Seawall or its caption, `tip_shown()`, says
`Game.seawall_rule_text()` from the rules' seawall block and where it stands, `hud_duel_seawall_tip`) under the strip, the end plate (`Hud.end_plate()`) and the results
(`ResultsPanel._compute_duel`: a block per side with its breach dealt). `Fx.seawall` sends a breaking ring of surf
from EV_SEAWALL's `x`, `z` (the road's end, where the rules measure the ring) out to its `r` in about 0.6 s and fades
it by 1.05 s: one mesh in palettes/hollow.gpl's water (frost_dark, frost, snow) with foam broken along its crest, a
following swell and a little spray, see-through throughout, drawn by a shader that keeps it on the hollow's floor:
`Fx.shore_mask(map)` (one pixel a tile, the share of its 3 x 3 that is not high ground; main.gd makes it once) lays the
wave down and thins it out over the last tile and a half before the hollow's cliffs, and nothing shows off the board
(group `seawalls`, meta `radius`); `Fx.uncork` rings the Welling a pack wells up at, and a creep with `sent_by` carries
`Fx.sent_bottle` (`Creep.effects_shown().bottle`). The duel scenarios play the real preset through
`tests/ui/duel_stage.gd`: `start(scene, my_seat, seed, mine, rival, rival_caretaker)` (against the caretaker, or with
`rival_caretaker` false a present seat that never acts, so two idle hollows play alike), `defend(scene)` (my seat
plays its plan through `tests/bot.gd`), `to_window(w)` (both hollows' waves moved in the first window, so the next
horn's wave opens window `w` and the Drift draws it), `in_window(w)`, `in_wave(w)`, `leak_all(hollow)` and
`breach(by)` (the logged creep-distance setter), `forget_salts()`, fixed salts (`Game.salt_source`,
`fixed_salt(seed, n)`, so two runs commit alike), and `partner_cork`, `partner_uncork`, `partner_ready` for
`tests/net/loopback_main.gd`'s partner once its fake's `seq.mode` is set to `undertow` before the partner joins
(`view_duel_networked_tray`). `view_duel_client_commit_matches_contract` holds `Game.duel_commit` and
`SimUndertow.commit` to digests worked out apart from the game; `view_duel_results_titles` plays each deciding rule
(a fall, both on one tick, and through the Surge's last wave lives, breach and a draw);
`view_duel_offline_against_the_caretaker` is Duel the caretaker from the hub and `view_duel_loading_two_rows` the
duel's loading barrier. B's duel scenarios are `view_duel_*` and `hud_duel*` (track A owns `duel_*`). The art: the tray and its bottle sockets are `console.py`'s
(`drift_tray`, `bottle_socket`, `bottle_socket_lit`), the corked bottle and the Seawall are mesh recipes
(`art_src/models/corked_bottle.json`, `seawall.json`), `icons.py` cuts `bottle.png` and `seawall.png` out of their
renders and lays the bottle over each creep's framed portrait for the pack icons (`pack_hollow_<check>.png`), and
`sfx.py`'s sweeps and washes make `cork`, `uncork`, `breach` and `seawall`.

Multiplayer is server-sequenced lockstep (design §6): the Python server in `server/` never simulates, it closes a
turn every 50 ms and sends every game the commands that arrived. The wire contract is `shared/net/protocol.json`;
`NetProtocol` (`scripts/net/protocol.gd`) and the server's codec are both built from it. A networked game
(`--join`) runs a `MatchClient` (`match_client.gd`): HELLO, the server's MATCH_CONFIG, LOADED, START, then the
server's turns through a `RemoteSequencer` (the same `TurnSource` seam as offline) at the pace `Playout` sets; it
sends HASH every 60 ticks and RESULT at the end. Seats are 0-based on the wire and 1-based in the simulation;
`RemoteSequencer.from_wire` converts. The party strip (`scripts/ui/party_strip.gd`) shows every seat.

Without `--dev-match` the server has a hub (`lobby.py`, `party.py`, `holds.py`; `shared/net/README.md`, The
hub): parties by lenient code, Ready and the 3 s countdown, the loading barrier's 4/15/30/45/120 s timers, the
results and back to the party (`LEAVE_MATCH` after `MATCH_END`), rows held 40 s after a drop; `PARTY_STATE`'s
`you` is the recipient's own row (members are rows 0 to 3, not sessions). Every server timer
runs on `server.clock`, so its tests (`HubTest` in `server/tests/support.py`) move a `ManualClock` and never wait
on the wall. Its state directory (`--state-dir`, default `server-data/`) keeps `identity.key` and
`moderation.json`; `--admin`, `--backup` and `--restore` work on it. `shared/net/transcripts/m3_*` are the hub's
conversations recorded from the real server; `protocol_golden_m3` decodes them with the GDScript codec.
The queue (M6, `queue.py`; README, The queue) takes a forming party's leader's `QUEUE enter` (everyone Ready; High
Water with open seats on and free, a race as one team of 1 or 2), keyed on mode and rules hash, earliest first
(High Water fills four with the earliest tickets that fit; a race pairs teams of one size); `MATCH_FOUND` gives
everyone `accept_ms` to `ACCEPT`, and a decline, a leave or the timeout dissolves it: the refusing party to
forming, the others to the front with `NOTICE match_dissolved`. Strangers on one team are unclashed (main, backup,
then a free Builder from `Server.queue_rng`); after `caretaker_offer_ms` `start_with_caretakers` forms the party's
match with caretaker seats (no player, `caretaker` flag, `LOAD_STATE` gone; covering what the party lacks, or a
race's mirror). `test_queue.py` holds it, `m6_*` are its transcripts and `protocol_golden_m6` decodes them.
In a match the server serves README's Resilience (M4; `match.py`, `catchup.py`): it asks one seat in rotation for
each agreed checkpoint tick and keeps the upload only if `SHA-256[:8]` is the agreed hash (the last two), resyncs a
minority of three or more (apart twice: `MATCH_END desynced_twice` to that seat, `LEFT`), seats a resume `HELLO`
naming its held seat (`ERROR` 12 to the old link, `MATCH_CONFIG` rejoin, `RESYNC` rejoin; else `NOTICE
no_held_seat`), holds `BACK` for a connection catching up until its `shown`, and paces every `RESYNC` at 2 KB per
50 ms of its clock while the output is under 4 KB. `m4_resilience` is that recorded; `protocol_golden_m4` decodes it.

- No floats, trigonometry, engine RNG, clocks, `delta`, Nodes or dictionary iteration in `scripts/sim/`:
  `godot-agent check . --sim-lint scripts/sim` and the `sim_lint_clean` scenario (`tests/sim/sim_lint.gd`, which
  also catches `.keys()`, rounding, `Engine.`, `.length()` and an unexplained `sort_custom`) must stay clean;
  a line that must keep a token says why with `# sim-lint: allow <token> <reason>`. Ties break by id; the
  match's randomness is its own `SimRng`.
- A scenario setter (`Game.gold = 300`, `Game.countdown`, `Game.wave`, `Game.lives`, a creep view's `distance`
  or `speed`, `scene.spawn(kind)`) writes into the offline match and is logged, so replays reproduce it.
- After an order (`scene.build`, a click, a key) wait for its turn: `{"wait_until": "scene.settled()"}`.
- Fast-forward with the scenario key `"ticks_per_frame"` (or a `set_ticks_per_frame` step), never `time_scale`.
- `tests/sim/sim_harness.tscn` runs bare simulations (several fed one turn log, thousands of ticks per call)
  for `sim_*`, `coop_*` and `turn_order_*` scenarios, the rules scenarios and the balance gates: `scene.spawn(kind,
  dist)`, `scene.hold(id)`, `scene.debug(op, ...)` stage creeps on every client; `scene.hits(tower, creep)`,
  `hit_values`, `status_amounts`, `help_total` and `events_where` read what happened; `scene.play_out([seats by
  command])` plays a match out with caretaken seats playing themselves. Main-scene scenarios watch
  `scene.state_hash_hex()`. `scene.stall(k, ticks)` freezes client k (2 or more) while the others play and
  `scene.catch_up(k, 8)` brings it back 8 ticks a call (it and `play_out` stop with an error when no turn comes,
  as with the sequencer paused: every wait in a test has a bound, `sim_harness_waits_are_bounded`); `seat_state(seat)`, `seat_moves(seat)` (its SEAT events),
  `refusal_ticks(seat)`, `since(list, tick)` and `owner_at(x, z)` read the seats (an Expression evaluates both
  sides of `or`, so never write `tower_at(x, z).owner` behind a null test).
- Seat states (design 6.7, `sim_*` scenarios): AWAY takes a present or returning seat in the turn it comes, before
  that turn's orders; BACK makes an away seat returning; LEFT takes any seat to the end; only
  `SimWaves.open_window` makes a returning seat present, in the stage that clears the wave, so the window's first
  tick is the player's. A SEAT event comes only when the state moves. The caretaker plays every state but present,
  from the seat's plan cursor: taking a seat mid-match it counts a build step done where the seat already has a
  tower on one of the step's cells, and forks only the kind the plan built on a cell
  (`sim_caretaker_takes_a_seat_mid_match`).
- Speed: stage 5 sorts the creeps along the road once (`SimMatch.by_distance`, between `open_look` and
  `close_look`) and each tower walks that order with its own stretches (`SimTargeting.furthest`);
  `sim_targeting_walk_matches_scan` holds it to a scan of every creep. `sim_bench` (`tests/sim/sim_bench.gd`)
  steps four seats at wave 11 natively, prints a `SIM_BENCH` line and fails below its `FLOOR` (4,000 ticks a
  second, room for a CI runner; 12,000 to 15,000 measured on a laptop, 4,300 to 5,200 with M3's scan) or when the
  walk is not 3 times faster than the scan on the same ticks (`LOOK_FLOOR_PC`; about 8.7 measured), which holds on
  any machine: run it after anything that touches a busy tick. M6's kits step on a board of their own
  (`M6_BUILDERS`, two Bellfounders and two Beekeepers), held to the same floor and to `M6_FLOOR_PC` (80) of the
  first board's rate in the same process (about 100 measured; about 72 while a waiting Toll Tower scanned every
  creep, before `SimMatch._pulse` asked the walk first).
- The modes are presets in `content.gd`'s `RULES`: `classic` (M1's eight waves, no armour, perks or Help, its
  state hashes held by `contract_ids_keep_state_hashes`) and `high_water` (`hollow12`, armour, boss control
  resistance, perks, Help). Whom a tower picks and where a bounce goes are `sim_targeting.gd`'s; slows, marks and
  Help `sim_effects.gd`'s: the strongest slow with time left applies, for its own time, and a weaker one waits under it
  (`SimCreep.slow_next`) until it lapses. The codec stores M2's fields (an Owl's Eye's picks, a bounce chain, the slows
  waiting) in a trailing block written only when one is set, so classic checkpoints keep their bytes. `SimContent.rules_hash()` is one per build,
  over every mode: HELLO carries it before a party picks its mode, and MATCH_CONFIG and LOADED repeat it. It covers
  every `BUILDERS` field the simulation reads (the caretaker forks by `covers`); `contract_m2m3_tables` checks that.
- A Builder's plan (`data/plans/<builder>.json`) is what the caretaker and the bots play: `steps` for every mode,
  a mode's own under its name (the Lamplighter keeps M1's under `classic`, which `tests/bot.gd` plays in the
  classic match); a step may name `alt` cells for a second seat with the same Builder and a fork may `patch` a check,
  which the caretaker takes only while nobody on the team covers it.
- M6's tower rules (contract-m6 §3; `stun_then_immune`, `toll_pulse_hits_all_ground`, `cloud_hits_air_and_ground`,
  `crack_lowers_armor_for_all_and_credits_help`, `stun_credits_help`, `haste_any_owner`, `apiary_bonus_to_fliers`,
  `tithe_pays_capped`, `bronze_hand_ignores_2`): a pulse (the Toll Tower) and a bee cloud (the Clay Hive) fire no shot; their strikes are
  gathered while stage 5 looks along the road and land after it (`SimMatch._strike_all`, id 0), so no creep dies
  during the look. A stun leaves the creep immune for `stun_immune_t` (`SimEffects.apply_stun`); on a boss that
  resists control it is a 50% slow, not shrunk again. Cracks are refreshed for every creep at the start of stage 5
  from `SimMatch.crack_posts`; haste is worked out again on every build, fork and sell
  (`SimEffects.recompute_haste`), the strongest of each applying, and `helpers()` names haste last, for the tower
  that dealt the hit. Bronze Hand is in `SimTower.pierce_c`, Hive Tithe pays in stage 7. `air_bonus_pm` works on
  any form that has it: the Apiary's, and since the balance pass the Sky Toll's (80%, so its 9 is 16.2 to a
  flier), so a view shows a form's numbers from the table's keys, not from its name. The codec's M6 block
  (`cloud_creep`, an Apiary bolt's `air_bonus_pm`, the race) follows M2's and is written only when one is set
  (`sim_checkpoint_roundtrip_m6`, which also fells a team mid-wave and plays the decided race on:
  `busy_match.gd`'s `fall`, and `roundtrip_chain` compares the race's state across every trip).
- Tide Race (`tide_race` in `RULES`, contract-m6 §4): team t's seats on hollow t, each hollow with its own clock,
  Ready and health scaling (`race_same_waves_both_hollows`, `race_independent_clocks`). `SimMatch._decide_race` takes
  design 1.3's win order at the end of a tick, once, as soon as the outcome is certain: `outcomes()` (one per team,
  `SimTypes.OUTCOME_*`, empty until decided; High Water's too, which `match_client.gd`'s RESULT sends),
  `race_time(team)`, `race_penalty_t(team)` (the rival line's "+20 s"), `decided_by()` and `EV_RACE`; the 20-minute
  `cap_t` ends any mode that sets one (`race_time_penalty_per_life`, `race_rival_fell_clear_to_win`,
  `race_cap_20_minutes`). In a race the caretaker calls its waves once its window's builds are done, unless the step
  it waits on says `"ready": false` (`sim_caretaker_calls_waves_in_a_race`). The sim harness takes `"teams"` and
  `"play_on"` (`SimMatch.play_on`, a test switch: a decided race plays on), `spawn(kind, dist, hollow)`,
  `tower_on(hollow, x, z)`, `play_out(seats, every, limit, ready_at_once)` and reads `race_summary()`,
  `decided_tick()`, `wave_spawns(hollow, wave)`, `pulses(tower)`, `rows(type, fields, where)` and
  `creep_report(kind)` (a balance pass's per-creep damage).
- Undertow (`undertow` in `RULES`, contract-m7 §2) is `SimUndertow`'s (`scripts/sim/sim_undertow.gd`; `SimMatch.duel`
  and `shared_clock` from the rules, never state): the race's layout, one seat a team, under one clock
  (`SimUndertow.run_clock`): a hollow that clears opens its window but it counts only once both have cleared, and the
  horn sounds for both when every seat is Ready and one of them is present, or the countdown ends
  (`duel_shared_clock_one_horn`): a caretaken seat says Ready once it has corked and built, and the caretaker thinks
  on the shared window's first tick (`SimUndertow.shared_window_tick`), so a player's Ready never takes its window
  (`duel_caretaker_has_its_window_before_a_ready_horn`). When the window opens for both, the Drift draws `offered`
  packs from the match's `SimRng`, never leaving out last window's left-out (`EV_DRIFT`; SimMatch's query of the open
  window's packs is the contract's); a window is "the wave it precedes", the Surge's 13 to 15 (their tier and health
  are the wave they repeat's, `SimUndertow.content_wave`). CORK(tier, commit) in the shared window stands a
  `SimRecords.SimBottle` (in `SimMatch.bottle_list`) holding only the commitment (`SimUndertow.commit`, the
  contract's bytes); UNCORK(pack, salt) from `uncork_after_t` after the horn reveals the first matching bottle and
  queues its pack on the rival's road (`SimHollow.sends`, one every `pack_interval_t`, `sent_by` the seat); at
  `fizzle_t` after the horn a bottle of that wave still corked fizzles. A wave a rival's bottle is corked for, or
  whose sends are still to come, does not clear (`SimUndertow.holds`), so a pack always walks its own wave: the
  defender's road may stand empty while its wave waits, up to `fizzle_t` after the horn, and since the window opens
  only once both have cleared, the sender's bottle holds back both hollows' next window that long
  (`fizzle_without_reveal`; `SimMatch.wave_held(hollow)` tells a view; contract-m7 §2). Stipends grow at the uncorking (not in the Surge) and pay at each clear;
  breaches pay the sender `breach_pay` bounties (`EV_BREACH`, `breach_dealt(team)`); the Seawall charges from
  `set_lives` and bursts on SEAWALL (`seawall_charges(seat)`, `seawall_ready_tick(seat)`); the decision (a fall at
  once, both on one tick a draw; after the Surge lives, then breach, then a draw) is `SimUndertow.decide`, in the
  race's record (`outcomes()`, `decided_by()` adds "lives" and "breach") and `EV_RACE` "decided". `bottles(seat)`
  never shows a corked pack. The codec's M7 block follows M6's (written empty then) only in a duel. The caretaker
  corks in the shared window, before its plan spends, while its corks stay within `Caretaker.CORK_SHARE_PM` of what
  it holds (contract-m7 §2's "while keeping its plan's next build", read as keeping that step's gold, never corks:
  the budget stands in for it until the tracks agree a wording), the pack the rival's towers take longest to kill
  (`SimUndertow.weakest_pack`), salt 0, uncorks at `uncork_after_t` (`SimMatch.uncork_tick`) and raises the Seawall
  when the creeps in its ring carry 3 lives or a boss (`Caretaker.wants_seawall`). Its plan waits while its hollow
  stands in its window and the rival's still plays the wave (`Caretaker.holds_plan`: a tower built on an empty road
  defends nothing sooner), so on the shared window's first tick it corks with the gold it kept and builds after
  (`duel_caretaker_corks_before_its_plan_spends`: 8 corks where it spent in the wait and corked 5; the plan bot waits
  alike). The sim harness plays duels by command in the gates' styles (`duel_out(styles, options)`: turtle,
  balanced, reckless, counter_cork, random, the three on the caretaker's budget holding their plan as it does,
  `CARETAKER_BUDGET_STYLES`, while the reckless one builds in the wait: holding too, it beat the turtle in 3 of 5;
  `duel_series(cfg, styles, seeds)` with cfg `builders_by_seed`, counting `distinct` matches and each seat's
  `leading_picks`; `duel_line()`; `horns_before_ready(seat)`; `builds_while_held(seat)`) and drives one by hand:
  `duel_to_window(w)`, `run_to_horn()`, `run_to_window()`, `cork(seat, pack, salt_hi, salt_lo)`, `uncork(...)`, `sent_fates(seat)`,
  `ring_ids(hollow)`, `drift_draws(seed, n)`; a scenario setter that moves a hollow's wave (`DBG_WAVE`, which now
  reaches the Surge's) parts a corked bottle from its wave, so set it after the uncorking (`surge_freezes_stipend`,
  `tiebreak_lives_then_breach`). `sim_checkpoint_roundtrip_undertow` round-trips a whole busy duel (`busy_match.gd`'s
  `duel_log`; `roundtrip_chain` compares `duel_state`), decided by a fall in the Surge's second wave and played on
  (`play_on`), so the decision is round-tripped too.
- Boot flags after `--`: `--seed=N`, `--bot`, `--hash-log[=file]`, `--quit-after-match`, `--ticks-per-frame=N`;
  networked: `--join=ADDRESS` (`127.0.0.1`, `192.168.1.20`, `host:port` or a `ws://` URL), `--name=NAME`;
  `--shot-at=T1,T2 --shot-dir=DIR` saves the window at those ticks.
- `tests/net/loopback_match.tscn` runs N `MatchClient`s against `tests/net/fake_sequencer.gd` (the server's match
  side in GDScript, counting frames) over `fake_link.gd`s with latency and jitter: deterministic `net_*`
  scenarios (`scene.start(...)`, `scene.client(k)`, `scene.run_turns(n)`, `scene.stall(k, turns)`,
  `scene.hashes_agree()`). `tests/net/loopback_main.gd` does the same for the main scene: add it and
  `start()` it to test what a networked window shows and refuses (its HUD, input and party strip). Orders
  go out only while `Game.accepts_commands()`; online, `RemoteSequencer` mirrors the server's command
  bucket, and `Game.command_refusal()` says why an order went nowhere. Change a message in `protocol.json` only together with the server, re-record the
  transcripts (`python3 server/tools/record_transcripts.py`) and keep `protocol_golden_m1` green.
- The client's side of Resilience (M4) is `MatchClient`'s: at each hash tick `Checkpointing` serializes the state
  once (its digest is the HASH; at a checkpoint tick it keeps the bytes and flags it, and uploads them on
  `CHECKPOINT_ASK`); a `RESYNC` (bounded like a `TURN`) is downloaded, checked against its hash, loaded, and its
  turns run again (`resynced`: `main.gd` builds its views again); more than `Playout.CATCH_UP_TURNS` behind it says
  `VISIBILITY catching_up` and takes no orders ("Catching up") until level; a link lost mid-match or while the
  match loads keeps the world and sends a resume `HELLO` (the same token, `held_match`, `held_seat`) every 2 s,
  giving up after 30 s (back while it loads, it says `LOADED` again if it had loaded); `WebBridge`
  reports a hidden tab (`hidden`, then `catching_up` or `shown`) and flashes the page title; a desynced end writes
  `DesyncDump`'s file. `connection_state()` is what `ConnectionOverlay` shows (reconnecting, catching up, in another
  tab, desynced). The fakes serve it all: `scene.cut(k, frames)`, `hide(k, frames, inbound_bytes)`,
  `corrupt(k, field, value)`, `corrupt_uploads(k)`, `delay(k, ...)`, `lose_turns`, `push_resync`, `bots(true)` and
  `run_until(expr, frames)` in `loopback_match.gd`; `cut` and `hide` in `loopback_main.gd`; `cut` in
  `loopback_hub.gd`. `view_connection_overlay` draws the overlay's states in seconds when rendered;
  `net_overlay_states` follows them headless (a rendered run of it is a long one on software Vulkan).
- A `--join` game killed or closed mid-match takes its seat back when it starts again: `Identity` notes the seat in
  `user://net.cfg` from `MATCH_CONFIG` to `MATCH_END` (`hold_seat`, `held_seat`, `release_seat`; a seat a running
  window plays is skipped where `/proc` tells), `Session.direct_client` hands it to `MatchClient.resume_seat`, and
  the first `HELLO` is a resume naming it: `MATCH_CONFIG(rejoin)` builds the match, `RESYNC(rejoin)` loads the
  checkpoint, and `NOTICE no_held_seat` forgets the note and joins afresh. The note also keeps a sequence floor
  above every `CMD` number the seat sent (raised 64 at a time), so the game started again numbers its orders above
  them. `scene.kill_game(k)` and `boot_again(k)` in `loopback_match.gd` do it against the fake
  (`net_restarted_game_*`); `tests/net/restart_driver.tscn` kills and starts whole games for a live topology.

The loop around a match (design §5, M3) is the `Session` autoload (`scripts/session/session.gd`): OFFLINE,
CONNECTING, HUB, COUNTDOWN, (QUEUED, MATCH_FOUND: M6), LOADING, IN_MATCH, RESULTS. It keeps the `Profile` (name,
main, backup, mode in `user://profile.cfg`), this install's `Identity` (a device key in `user://net.cfg` that never
leaves it: each server gets its own HELLO token, `Identity.token_for(url)`, shared/net/README.md The token) and
one `MatchClient` with `keep_link` as the connection to a server, which carries the party from match to match
(`defer_loaded`: LOADED waits until the match scene stands). The hub's `Shell` (`scripts/ui/shell.gd`) draws the
console's pieces and the Causeway and holds the screens (`hub_panel.gd`, `builders_screen.gd`, `join_panel.gd`,
`name_prompt.gd`); the loading screen is the session's own layer; `main.gd` asks `Session.enter_match()` what to
play and leaves to `results_panel.gd`. Booted on its own, or with match flags (`--join`, `--seed`, `--bot`, ...),
which the hub hands on, the match scene plays as before and ends on the console's end plate. The Lamplighter and
the Lookout play as themselves and High Water by its own rules; `Profile.fielded` and `Profile.played_mode` stand
a Lamplighter and `classic` in only for a Builder or mode this build cannot show yet (M6's). The client finds its
own party row by `PARTY_STATE`'s `you`; Play again and Hub send `LEAVE_MATCH` after `MATCH_END`.
`Session.play_offline(builder, try, company, company_builder)` adds caretaker partners of any Builder; while it plays,
the session still polls its server connection, so a Try keeps the party. In a match, Esc with nothing to cancel opens
the menu (`scripts/ui/match_menu.gd`): Resume, Restart (offline), Leave to hub; an offline match waits while it is up.
From 30 s of loading the leader's loading screen offers Start without the slow seat (`Session.start_without()`).
The queue's side (M6): `Session.primary()` follows design 5.2's table (Find players with open seats on,
`Session.set_open`; Find a rival in a race; "Entering queue..." and "Leaving queue..." while `queue_request` is on its
way; Cancel · 0:42 queued, Esc too; after the offer Start with caretakers or Race the caretaker, with Cancel as its
`second`), the hub's party well lists a race by team (A, B) and the leader's click on a row is `PARTY team`
(`Session.move_team`), the Shell's queue pill reads `Session.queue_text()`, and `MATCH_FOUND` opens
`scripts/ui/match_found.gd` (the session's own layer, `/root/Session/MatchFound`: `lines()`, Accept, decline, Enter and
Esc; its sounds load only where track B's files exist). `requeue_after` makes Play again queue a player who came
alone through Match Found (not after a start with caretakers, the party's own match). Queued, only the leader may
leave the queue, so `Session.try_refusal()` keeps a member's Try (disabled on the Builders screen, with why) until
the party is out of it. Open seats are a one-team mode's: `Session.open_seats()` is false in a race, and the server
turns them off with the mode. Offline, a race party of one plays `Session.offline_match(mode, builder)` (its seats
`Session.offline_seats`): a caretaker rival team with the same Builders, offered only where `Profile.offers`.
Undertow around the match (M7, contract-m7 §4): `Session.is_duel(mode)` is a two-team mode of one seat a side
(`team_seats`), and the queue serves it with the race's rules: a party of one finds a rival (one stranger, both
mains kept: a clash never crosses the sides), a party of two is both sides and starts, `can_move` lets no row onto a
duel's side already taken (a race's rows move freely, so a race of four regroups through 3-1), and a party larger
than the duel waits ("A duel is one against one": the leader's Start, while a member may still say Ready). Duel the
caretaker (`caretaker_word`) is the offline match of my seat against one caretaker of my Builder (company is clamped
to a team's seats), and after the queue's offer the server's `start_with_caretakers` sets the same rival; the offer's
notice is said in the mode's words (`offer_text`), Match Found says "Undertow · 1v1 · ~15 min", the mode line "1v1",
and Play again queues a duellist who came alone. The hub's Undertow button lights once `Profile.offers("undertow")`.
The `flow_duel_*` scenarios play the duel on track A's preset (a match the queue forms loads and plays on
Undertow's own rules), and `tests/net/duel_checks.gd` reads the simulation's seats (`seats_seen()`, "" before it
stands) and presses a button only where it stands; its `start_duel(scene)` stages a duel against a caretaker with
fixed salts, on which `bot_duels_through_its_orders` holds the plan bot's corking, uncorking and Seawall to the
turns, and `bot_duel_refused_orders` its refused orders (`step_until_cork`, `spoil_next`, `refuse_orders`): a cork
refused or sent nowhere is no played window and goes again, an UNCORK the simulation refused is sent again after
Game's retry wait, and one the client's own uncorking at 24 s made is said to be the client's. `m7_duel` is the
server's duel recorded; `protocol_golden_m7` decodes it.

- The main scene is the hub, so a scenario of the match names it: `"scene": "res://scenes/main.tscn"`.
- `tests/net/loopback_hub.gd` runs the session against the fake sequencer in lobby mode (`flow_*` scenarios): add
  it under `Session` (it outlives scene changes), `start()`, then `host(name, main)`, `member(...)`,
  `set_member(name, "ready" | "reload" | "main", value)`, `load_member(name, per_mille, loaded)`, `finish(outcome)`.
  The fake numbers rows and keeps the results plate as the server does, closes a connection silent for 15 s and takes
  the leader's Start without from 30 s of loading. The loading screen lives at `/root/Session/LoadingScreen`.
  The queue (M6): `stranger(name, main, backup, accepts)` queues a scripted stranger (strangers fill the open seats or
  a race's rival team in the order they came), `stranger_answer(name, yes)`, `member_answer(name, yes)`,
  `party_mode('tide_race')`, `party_open(on)` and `queue_party()` (a scripted leader's); the fake keeps open seats and
  teams, answers `QUEUE` and `ACCEPT` as `queue.py` does, and counts `accept_ms` and `caretaker_offer_ms` in frames
  (`seq.queue_log`, `seq.ticket`, `seq.found`, `seq.strangers`).
- The hub's boot flags: `--server=ADDRESS` connects the hub at its first opening and makes a party there (or joins
  `--code=K7Q4M`'s); `--name=NAME` and `--main=lookout` set this run's name and main without saving them.
  `--flow-bot` hands the hub to `tests/net/flow_bot.gd`, which makes or joins a party (`--code-out=FILE` writes the
  code, `--code-in=FILE` waits for it), says Ready or starts once `--party=N` are there, lets the session play the
  match (`--bot` plays the seat: `tests/bot.gd` plays any Builder outside classic as the caretaker would, a duel's
  corks, uncorkings and Seawall too, printing a `BOT ...` line for each; `--ready-calls` calls every wave, in a duel
  once the bot has played the shared window), presses Play again and prints a `FLOW ...` line per step;
  `--quit-after-flow` quits once everyone is back. `tests/net/live/flow_*_live.json` and `smoke.py --flow` use it.
  `--queue` plays the queue instead, alone: open seats, Find players, Accept, the match, and Play again until it is
  queued again (`smoke.py --flow --queue`). `--mode=undertow` (a mode the hub offers, unsaved like `--main`) makes
  the party in that mode; with `--queue` the bot finds a rival instead (`smoke.py --flow --queue --mode undertow`).
  `loopback_hub.gd`'s `finish(outcome, per_team)` ends a race or a duel one outcome a team (`["won", "lost"]`).

Verify changes with godot-agent ([godot-agent-kit](https://github.com/saschb2b/godot-agent-kit): clone it and run
its `install.sh` for the CLI, the MCP server and the skill, which explains each command):

- `godot-agent check .` after editing scripts; `--resources` after editing scenes or `.tres` files;
  `--sim-lint scripts/sim` after touching the simulation.
- `python3 tools/names_check.py` after renaming anything or writing copy: no retired name in the tracked tree.
- `godot-agent scenario . tests/scenarios --headless` runs every gameplay test (about a hundred) in about forty
  seconds. Add a scenario in `tests/scenarios/` for each behaviour you change, and make sure it fails without
  your change.
- `godot-agent scenario . --determinism` before a release: every scenario twice, state and pixels compared.
  Where the virtual display draws on a software GPU (the summary says so: llvmpipe), the long rendered
  matches time out at 180 s even with `-j 1`; compare those again with `--determinism --headless` (state
  only). A scenario showing the hub's first-launch name pins the device key with the kit's `user_files`
  (`{"net.cfg": "[identity]\ntoken=..."}`), or the name differs on every run.
- Balance changes: `bot_wins` must still win with half the lives left, `idle_player_loses` must still lose
  (both play High Water solo in the sim harness; `bot_wins_classic` and `idle_player_loses_classic` keep the
  classic match through the game's input route). Then `godot-agent scenario . tests/balance --headless`: every
  `bot_wins*` wins with half the lives, every `idle_*` and `*_loses` loses, every `coverage_*` holds and
  `high_water_length_2p` lasts 11 to 15 minutes. The gates are written by `python3 tools/gen_balance_scenarios.py`
  (edit its `CASES`, not the files; `--check` says whether they are current), and each keeps the match summary,
  its bosses and its leak table per wave in the watches. M6 adds every Builder alone, three and four seats, the
  Bellfounder with the Beekeeper (`coverage_holds_complementary_bb`), each M2 Builder beside each M6 one, whose
  plans share build cells (`bot_wins_lamplighter_bellfounder`, `_lamplighter_beekeeper`, `_lookout_bellfounder`,
  `_lookout_beekeeper`), and the race's two: `race_mirror_is_fair` (the
  same plan on both hollows draws) and `race_bots_both_finish` (a bot calling every wave against one waiting out
  every window, played on past the decision: both finish, the lower race time won). A tuned number says why beside
  it in `content.gd`; balance is the plans' first, then the M6 kits' numbers (they are the contract's *tunable*).
  M7 adds the duel's six, each a mirror of Builders: over a series each seed puts the next Builder of the
  generator's `DUEL_ROSTER` (Lamplighter, Lookout, Bellfounder, Beekeeper, Lamplighter) on both seats, since the
  match's `SimRng` feeds only the Drift and two Lamplighter duels of two seeds often played one match
  (`duel_mirror_is_draw`: four seeds of caretakers, every one a draw with both records equal; `duel_turtle_holds`:
  two Lamplighters, 10 lives through the Surge; `duel_balanced_beats_turtle`, `duel_turtle_beats_reckless`,
  `duel_counter_cork_beats_random`: at least 3 of seeds 1 to 5, the counter-corker's most-uncorked pack not the same
  in every match; `duel_seawall_saves`: the defender raising its Seawall beats a reckless corker in at least 3 of 5
  and in more than without it), each a `duel_series` keeping one line per match and holding its matches to being
  all different. The duel's numbers are the `duel` block's (all *tunable*) and the caretaker's `CORK_SHARE_PM`;
  measured (the same counts since the styles on the caretaker's budget hold their plan in the wait): balanced 3 of
  5 (the Lamplighters and the Lookouts win, the Bellfounders and the Beekeepers lose to the turtle on lives),
  reckless loses 4 of 5, counter_cork 4 of 5 and a draw, the Seawall turns 1 of 5 into 4 of 5. A
  duel through the Surge lasts 13.2 to 15.2 minutes; one a Holdfast's fall ends may be over by wave 7, in 6.5.
- `godot-agent run . --renderer gl_compatibility` shows the scene as the browser build draws it.
- The server: `python3 -m unittest discover -s server/tests -t server/tests` (Python 3.11+).
- Networking against the real server: `godot-agent scenario . tests/net/live --headless -j 1` (nine topology
  scenarios, about seven minutes: among them a party by code from the hub and the faults below) and `python3 tools/net/smoke.py
  --clients 2 --turn-ms 10`, a whole classic match by two headless bots in about 80 s with equal hash streams
  (`--turn-ms` is the server's dev-match turn length); `--mode tide_race` (2 or 4 clients, two teams) checks that
  the RESULTs share their tick and hash and the teams' outcomes answer each other, and can pass only once
  `content.gd` has the `tide_race` preset; `--mode undertow --turn-ms 10` (two clients, seat 1 against seat 2,
  about three minutes) checks a duel the same way and as a duel: the plan bot (`tests/bot.gd`) duels as the
  caretaker would through `Game.cork`, `uncork` and `seawall` (Caretaker's `cork_tier` budget,
  `SimUndertow.weakest_pack`, uncorked from `uncork_after_t`, `Caretaker.wants_seawall`), so its `CORK`, `UNCORK`
  and `SEAWALL` cross the real server, and the smoke reads each game's `BOT` lines (`bottle ... corked`, `uncorked
  ... by bot` when Game settled the bot's own `UNCORK` as the one that ran, `walking`; `duel_game`,
  `duel_problems`): both games corked and their bots uncorked, an uncorked pack
  walked the rival's road, the hash streams agree, one outcome a side (seed 1 corked four to six packs a side in two
  runs, each decided after the Surge, with a Seawall or two; the bots' timing over the wire makes runs differ).
  `smoke.py --flow --queue --mode undertow` (about twelve minutes, the hub's 50 ms turns; its default `--timeout`
  1500 s) has two games alone find each other as rivals through the real server's queue, duel one a side with
  their own mains (`--bot` plays the duel as above and is checked so, one outcome a side; its `--ready-calls` wait
  for the bot's `played_window`, so a Ready on both sides never takes a window from the corking), and Play again
  queues each again; `--no-bot` only calls the waves. `server/tests/test_duel_commands.py`
  holds the server's CMD path for the duel's orders (any 32-bit halves, stamped and resent as sent; one outside
  its limits lets that seat go and closes only its link).
  `python3 tools/net/smoke.py --flow` plays the loop against
  the server's hub: two games boot into the hub, one makes a party and the other joins by its code, Ready, Start,
  loading, a High Water match with a Lamplighter and a Lookout played by the plan bots (about eight minutes; the
  hub's matches keep the protocol's 50 ms turns), the results, and both back in the party; `--no-bot` only calls
  the waves, so the Tide wins in about a minute and a half; `--linger 20` keeps both on the results for 20 s, past
  the server's 15 s of silence, before Play again. `smoke.py --flow --queue --no-bot` plays the queue (M6) against
  the real server in about 100 s: four games, each a party of one with open seats, Find players, the server merges
  them, Match Found to all four and every Accept, a High Water match of strangers whose Builders the server
  unclashed (all mains Lamplighters: four different Builders in `MATCH_CONFIG`), the results, and Play again
  queueing each again; the flow scenarios' fake does the queue's rules in GDScript, and this is where they meet the
  server's. `smoke.py --shaper --turn-ms 10` plays the last
  client through `tools/net/shaper.py` (150 ± 50 ms each way and a 3 s stall) and checks that the other's tick rate
  never drops below 0.8 of the server's pace; `--faults` cuts that client's link for 8 s and checks it rejoins and
  finishes (`--server` runs another checkout's `server/main.py`). `python3 -m unittest tools/net/test_shaper.py`
  holds the shaper itself.
- The fault tests against the real server (M4), one at a time, never two topologies or smokes at once:
  `net_reconnect_live` (a socket dropped, the seat AWAY, the rejoin and the hand-back), `net_restart_rejoins_live`
  (a whole game killed with SIGKILL and started again with the same `user://`), `net_minority_desync_resyncs_live`
  (three games, one's gold written by a bug: `RESYNC(desync)`, level again) and `net_two_seat_desync_dumps_live`
  (two apart: `MATCH_END desynced`, each dump read back and copied into the run's folder as `client<k>_<match>-<seat>.bin`).
  Their servers keep `--event-log {out}/events.jsonl` (`drop`, `away`, `rejoin`, `resync`, `desync`, `checkpoint`,
  `end`), which the steps read with `live_checks.gd`'s `file_has`. Then
  `smoke.py --faults --turn-ms 10` and `smoke.py --shaper --turn-ms 10`, about 85 s each.
- A desync dump, `user://desync/<match>-<seat>.bin` (on Linux `~/.local/share/godot/app_userdata/Groundhold/desync/`;
  its layout is `scripts/net/desync_dump.gd`'s header): `DesyncDump.read(path)` gives its fields (the bad tick, the
  last checkpoint kept before it, every turn since, the state at the bad tick, the seat's hash stream), and
  `DesyncDump.replay(dump, tick)` runs the checkpoint through the turns to any tick. Both seats' dumps name the
  same bad tick (the first hash tick they disagreed on); to see what parted, load each dump's `state` with
  `SimMatch.deserialize(state, SimContent.rules(mode))` and compare the records (seats' gold, towers, creeps), or replay each from its checkpoint
  to a tick before the bad one and step both a tick at a time until their `state_hash()` differs. `tests/net/live_checks.gd`'s `dump_summary(path)` does the
  self-check (the checkpoint replays every hash the seat sent up to the bad tick) from a step:
  `{"eval": "resource('res://tests/net/live_checks.gd').dump_summary('user://desync/1-2.bin')"}`.
- By hand, a dev match: `python3 server/main.py --dev-match classic:2 --host 127.0.0.1`, then two windows of
  `godot --path . -- --join=127.0.0.1 --name=Tamsin` (add `--bot` to let the plan bot play a seat; seat 2's bot
  follows `tests/plans/lamplighter_seat2.json`).
- By hand, the hub: `python3 server/main.py --host 127.0.0.1 --state-dir /tmp/groundhold-state` (no `--dev-match`:
  the server keeps parties), then `godot --path . -- --server=127.0.0.1 --name=Tamsin` and a second window with
  `--name=Edda --main=lookout --code=<the code on the first window's strip>`; or open the game plainly and use Join
  (J): the address `127.0.0.1` makes a party there, a code joins one. Both Ready, the leader starts, and Play again
  brings both back to the party.

Playtests (`.claude/skills/playtest-loop/`): a persona agent plays the game through the kit's play harness,
`godot-agent play start NAME [--fresh] [--pin]` (GL Compatibility, from the project setting
`godot_agent/play_renderer`, kept across a session's starts), then `play do NAME "COMMANDS" [--every N] [--grid]`
a batch at a time (`wait 3600 until build window|screen: results` lets a wave run to its end), `play stop
NAME`, and `play replay FROM NAME --until FRAME [--start K]` to see a moment again (every batch's frame and
state checked; K picks an earlier start, each counting its frames from 0). A session is one Godot process
frozen between calls, its files in `.build/play/NAME/` (ignored: its `user://`, `history.txt` and an earlier
start's `history-K.txt`, `shots/`, a pinned copy). After each batch it prints `tools/play/describe.gd`
(project setting `godot_agent/play_describe`): what a player sees at a glance on every screen and where to
click (`@x,y`), never what a player cannot see (the build grid, not a list of free cells; a creep's health
bar, not its number); its `watch` lines (the screen, the wave's line, a Surge's too, a banner) are all a `wait
until` reads; `play_describe_says_what_shows` holds both, and `play_describe_says_what_a_duel_shows` a duel's
tray (its head, packs by name with why one greys, my bottles by their pack, the rival's by tier), its bar and the
Seawall's plate, and its wave line, "build window" only once the window is open for both ("waiting for the window"
while the rival's wave still runs). A fresh session's `user://` starts from `tools/play/user/` (a fixed
device key, so the first launch's generated name, and its replays, are the same every time). Play in GL
Compatibility: on llvmpipe an undrawn frame costs about 0.4 ms there and 0.24 s in Forward+; a picture about
two thirds of a second. The loop (pin, patch notes, launch, watch, triage, fix, improve) is the skill's `SKILL.md`, its log
`lessons.md`; who plays is `personas/NAME.md`, written from `research/`: `halv` (a Warcraft III custom-map TD
veteran, the base), `ysr` (a send-duel player), `teo` (a co-op regular) and `noa` (a fresh tester, who rotates and
gets no game guide); each report is rated blind (`ledger.md` read only after) and audited (`auditor.md`).

Releases (design §7.6 and M5; `server/README.md`, At a release, is the checklist). A tag `vX.Y.Z` runs
`.github/workflows/release.yml`: `gate` (`tools/release/gate.py plan`, then `check`: the tag, `project.godot`'s
`config/version` and a dated `## X.Y.Z · YYYY-MM-DD` section of `CHANGELOG.md` agree, and `on-main`: the tag is on
`main`, or nothing builds; a heading still `· TBD` is a release being prepared), `desktop` (Godot and its templates
checked against Godot's `SHA512-SUMS.txt`, the `Linux`, `Windows` and `macOS` presets exported with `data/build.json`
stamped, the Linux build booted headless by `desktop_smoke.py`, each packed by `package.py` as
`groundhold-<platform>.zip`), `server-native` and `server-image` (called with the gate's commit, version and `push`;
each server archive holds one folder, `groundhold-server-<version>-<target>/`; the image's `X.Y` and `latest` move
only for the newest release, `deploy.py newest`), `publish` (`assemble.py`: exactly `assemble.FILES` plus
`SHA256SUMS.txt`; the notes are `gate.py notes`) and, last, `deploy` (`deploy.py push` force-moves the `release`
branch the Coolify app tracks, on a tag push only to the newest release tag, `--newest-only`, while a run by hand may
roll back; `deploy.py coolify` calls Coolify's deploy API after a move when the `COOLIFY_*` secrets are set). Run by
hand it is a dry run unless told otherwise: nothing published, the files kept as the `release-dry-run` artifact. Only
GitHub and the user's session push tags, change secrets or make the ghcr package public; an agent never does.

- `assemble.FILES` is the one list of a release's files (versionless names, so `releases/latest/download/<file>`
  links last): README.md, `server/README.md`, the site and the `README-first.txt` templates may name only those, and
  the READMEs must name all of them (`tools/release/test_workflows.py`). The self-host Compose pulls the image
  `server-image.yml` pushes. Change a file's name in `assemble.py`, `package.py` or `server/release.py` together.
- The official server's policy is `server/README.md`'s The official server and `web/policy.html` (published beside
  the site's `index.html`); `server/tests/test_policy.py` holds both to `deploy/coolify/server.ini`, the kick and
  name rules and `data/net.json`. Change the settings and both pages together.
- Test the release's steps: `python3 -m unittest discover -s tools/release -t tools/release` (the gate and plan, the
  desktop zips, the files, the deploy against a bare repository and a fake Coolify, and the workflows' shape with
  PyYAML). Locally, as far as GitHub's runners go: `python3 server/release.py` (the zipapp's archive, smoke-tested
  outside the checkout); in a venv with `server/requirements-build.txt`, `server/release.py --native --target
  linux-x64`; `bash deploy/check.sh` (Docker: the image and both stacks, removed afterwards; never beside another
  Docker or Godot job); and the desktop build: `python3 tools/release/stamp.py build-json --build-seq 0`, `godot
  --headless --path . --import`, `mkdir -p build/desktop/linux && godot --headless --path . --export-release "Linux"
  build/desktop/linux/groundhold.x86_64` (Godot makes no export folder itself), `python3
  tools/release/desktop_smoke.py build/desktop/linux/groundhold.x86_64`, `python3 tools/release/package.py --version
  0.6.0 --platform linux-x64 build/desktop/linux --out dist`. Delete `data/build.json` afterwards (it is ignored by
  git, but a local run reads it as its build number). The export templates are Godot 4.7.1's
  (`~/.local/share/godot/export_templates/4.7.1.stable`).

Assets are generated, never hand-edited: change the recipe in `art_src/models/` and rebuild with
`godot-agent asset mesh`, or the Blender build script in `art_src/blender/` (plants, rocks, creeps) and rebuild
with `godot-agent asset blender`; `godot-agent asset regen . <path>` rebuilds anything listed in
`asset_manifest.json`. The console art and the command icons come from the game's own painters,
`art_src/ui/console.py` and `art_src/ui/icons.py` (Pillow; their specs sit beside them), and `asset regen` reruns
them too. The HUD places itself by the `ui/console/layout.json` the painter writes. A creep's `stride` in `Game.CREEPS` is the walking speed its walk cycle was made for;
its build script prints the value.
A tower whose head turns (cannon, frost, Iron Mortar, Rime Spire, the Lookout's ballistas and telescopes) is two
models, `models/towers/<form>.glb` and `<form>_head.glb`; its command icon is rendered from an icon-only model in
`models/ui/towers/` (recipe in `art_src/models/tower_icons/`) that seats the head, then framed by `icons.py`,
which also paints the check glyphs and role icons from the shapes `icons.json` lists under `marks`. The
Bristlesow is `art_src/blender/thornback.py` built with `--param tint=0.66 --param game_scale=2.7`; the Duskmoth
(`duskmoth.py`) hangs from its origin, and the view lifts it to hover. `art_m2_painted` checks M2's art is in place.
The Bellfounder's and the Beekeeper's eighteen forms (M6; none turns a head) are written by
`art_src/models/towers/m6_kits.py`: each form's recipe and its icon-only one, from shared pieces (the turf dike, the
bell, the cistern steps, the clay pipe, the bee), so a branch keeps its base, and the emblems' props
(`hand_bell.json`, `bee_smoker.json`). Edit the script, not the JSON, and run it again; `m6_kits.py --check` exits 1
when a recipe is not the script's output or a model's manifest entry holds another recipe. The Toll Tower's icons
render at pitch 14 so the bell shows under the roof. The sounds the kit's one-oscillator synth cannot make (bells from
inharmonic partials over a strike, the bee swarm) come from the game's own `art_src/sfx/sfx.py` and `sfx.json`, which
`asset regen` reruns; `countdown_tick` is the kit's `blip`. `art_m6_painted` checks M6's art is in place, and holds
every M6 model to its `asset_style.json` rules (triangles, size, materials, palette) and to the recipe it was built
from, since CI runs the scenarios but not `asset check`.
`Game.TOWERS` holds each tower form's view (model, a head that turns or spins, its bore or muzzle, its shot and
sound); `Tower.model_of(form)` stands one still for the placement ghosts. Views read the simulation's records after
each step (a creep's slow, stun and mark, an Owl's Eye's marked creeps), so team effects need no events. M6's
forms turn no head; the Clapper Tower's strike is instant (`projectile` `clap`, `Projectile.INSTANT`: a clap on its
creep), the Apiary's shot a `bee`, and a shot model or a sound not made yet is a stand-in bead
(`Projectile.model_for`) or silence (`Sfx.has_sound`). Their effects are `fx.gd`'s, from the records and `EV_PULSE`:
`bell_ring` (the pulse; `Tower.pulse`), `bee_cloud` over the record's `cloud_creep`, `chime_shimmer` on a creep with
`crack_c`, `hum_glow` under a tower with `haste_pm`; `Tower.effects_shown()` and `Creep.effects_shown()` say which
show (`view_m6_effects` plays the real simulation's pulses, stuns, cracks, clouds and haste and holds the views to
the records at every step, `m6_views.gd`'s `effects_off_records`). Each M6 muzzle is measured on its model (a bell's
middle, a Clay Hive's middle row of pipe mouths, an Apiary's top ring of bee holes; `view_m6_muzzles`), and their
sounds sit level with the M2 towers' as played (the file's loudest tenth of a second plus the gain in `Game.TOWERS`). The
command card's slots are `CardQ`, `CardW`, `CardE`, `Signal`, `Sell` and `Ready`; `Hud.card()` says what each holds
and `Hud.checks_shown()` what the strip shows, `Hud.wave_list_lines()` the waves to come (each creep's count, its
health at that wave, `Game.wave_health` from the very sum its spawn takes, `SimWaves.health_c`, and its armour,
`hud_wave_list_health_and_armour`), for `hud_*` scenarios; `view_*` scenarios cover the views.
The screens outside a match draw with the console's own pieces (`panel`, whose stone tile-fits, with
`panel_jewel` on its top edge; `card_frame` and `card_frame_lit`; `portrait_plate` over `portrait_plate_bg`;
`field`, `field_focus`; `bar_trough`, `bar_fill`; `divider`), each `.tres` through `HdStyleBox` at the layout's
scale, placed by the same `layout.json`. The Builders are chibi toon figures (about 2.5 to 3 heads, a face of a few
flat shapes, one oversized hat or hood and one oversized prop that reads as a tool, never as a weapon), built by
Blender scripts in `art_src/blender/builders/` with the kit's `chibi` and `gab` helpers and their colours from
`palettes/builders.gpl`; each also builds the `_bust.glb` its `ui/icons/builder_<id>.png` is rendered from (the
params are in the script's docstring and the manifest). They wear `materials/builder_toon` (two tones, a crisp
terminator), which `BuilderFigure` (`scripts/builder_figure.gd`) levels for the compatibility renderer; the towers
and creeps keep the painted look, so anything cel-shaded on the board is a Builder. `Game.BUILDERS` names them: `portrait` (the whole
figure, the Builders screen's arch), `bust` (the hub's arch), `glyph` (the framed face: party rows, the party
strip, loading cards, results) and `emblem` (`ui/icons/emblem_<id>.png`, the Builder's signature prop framed by
`icons.py` as a command button: the hub's Builders button). The hub's backdrop props, the Causeway's road
(2 units, chains along +Z), tide pole, cairn and wrack, come from `art_src/blender/causeway/causeway.py`
(`--param piece=road`, ...) into `models/causeway/`; like the hub, they belong to no map. `CausewayView`
(`scripts/ui/causeway_view.gd`) stands them in a 3D world of its own behind the hub and the loading screen, over the
flats of `shaders/flats.gdshader`, its camera drifting along the road.
The card's Signal icon is `models/ui/signal_pennant.glb` (recipe `art_src/models/signal_pennant.json`), rendered and
framed by `icons.py` like the others. A fork branch is marked `Game.FORK_MARK` in tooltips, never "A" or "B".
`godot-agent asset check .` must stay clean. `godot-agent scenario . tools/media -j 1 --renderer gl_compatibility
--out RUN` re-renders the README's and the site's shots as the browser build draws them (`hub`, `builders`, `party`
through the lobby fake, a High Water match with the 1200 x 630 `social` card and its `results`, and `catching_up`,
the connection overlay's plate), one rendered run at a time; `python3 tools/media/publish.py RUN` turns them into
`docs/media/*.webp` and `social.jpg`, which the Pages build copies to the site's `media/`.
The site's `web/play/index.html` hands `?join=` on to the game's frame; `python3 -m unittest discover -s
tests/web -t tests/web` runs its script under Node.
