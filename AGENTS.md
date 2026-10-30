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
  `scene.state_hash_hex()`.
- The modes are presets in `content.gd`'s `RULES`: `classic` (M1's eight waves, no armour, perks or Help, its
  state hashes held by `contract_ids_keep_state_hashes`) and `high_water` (`hollow12`, armour, boss control
  resistance, perks, Help). Whom a tower picks and where a bounce goes are `sim_targeting.gd`'s; slows, marks and
  Help `sim_effects.gd`'s: the strongest slow with time left applies, for its own time, and a weaker one waits under it
  (`SimCreep.slow_next`) until it lapses. The codec stores M2's fields (an Owl's Eye's picks, a bounce chain, the slows
  waiting) in a trailing block written only when one is set, so classic checkpoints keep their bytes. `SimContent.rules_hash()` is one per build,
  over every mode: HELLO carries it before a party picks its mode, and MATCH_CONFIG and LOADED repeat it. It covers
  every `BUILDERS` field the simulation reads (the caretaker forks by `covers`); `contract_m2m3_tables` checks that.
- A Builder's plan (`data/plans/<builder>.json`) is what the caretaker and the bots play: `steps` for every mode,
  a mode's own under its name (the Lamplighter keeps M1's under `classic`, which `tests/bot.gd` and the README's
  shots play); a step may name `alt` cells for a second seat with the same Builder and a fork may `patch` a check,
  which the caretaker takes only while nobody on the team covers it.
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

- The main scene is the hub, so a scenario of the match names it: `"scene": "res://scenes/main.tscn"`.
- `tests/net/loopback_hub.gd` runs the session against the fake sequencer in lobby mode (`flow_*` scenarios): add
  it under `Session` (it outlives scene changes), `start()`, then `host(name, main)`, `member(...)`,
  `set_member(name, "ready" | "reload" | "main", value)`, `load_member(name, per_mille, loaded)`, `finish(outcome)`.
  The fake numbers rows and keeps the results plate as the server does, closes a connection silent for 15 s and takes
  the leader's Start without from 30 s of loading. The loading screen lives at `/root/Session/LoadingScreen`.
- The hub's boot flags: `--server=ADDRESS` connects the hub at its first opening and makes a party there (or joins
  `--code=K7Q4M`'s); `--name=NAME` and `--main=lookout` set this run's name and main without saving them.
  `--flow-bot` hands the hub to `tests/net/flow_bot.gd`, which makes or joins a party (`--code-out=FILE` writes the
  code, `--code-in=FILE` waits for it), says Ready or starts once `--party=N` are there, lets the session play the
  match (`--bot` plays the seat: `tests/bot.gd` plays any Builder outside classic as the caretaker would,
  `--ready-calls` calls every wave), presses Play again and prints a `FLOW ...` line per step;
  `--quit-after-flow` quits once everyone is back. `tests/net/live/flow_*_live.json` and `smoke.py --flow` use it.

Verify changes with godot-agent ([godot-agent-kit](https://github.com/saschb2b/godot-agent-kit): clone it and run
its `install.sh` for the CLI, the MCP server and the skill, which explains each command):

- `godot-agent check .` after editing scripts; `--resources` after editing scenes or `.tres` files;
  `--sim-lint scripts/sim` after touching the simulation.
- `python3 tools/names_check.py` after renaming anything or writing copy: no retired name in the tracked tree.
- `godot-agent scenario . tests/scenarios --headless` runs every gameplay test (about a hundred) in about forty
  seconds. Add a scenario in `tests/scenarios/` for each behaviour you change, and make sure it fails without
  your change.
- `godot-agent scenario . --determinism` before a release: every scenario twice, state and pixels compared.
- Balance changes: `bot_wins` must still win with half the lives left, `idle_player_loses` must still lose
  (both play High Water solo in the sim harness; `bot_wins_classic` and `idle_player_loses_classic` keep the
  classic match through the game's input route). Then `godot-agent scenario . tests/balance --headless`: every
  `bot_wins*` wins with half the lives, every `idle_*` and `*_loses` loses, every `coverage_*` holds and
  `high_water_length_2p` lasts 11 to 15 minutes. The gates are written by `python3 tools/gen_balance_scenarios.py`
  (edit its `CASES`, not the files; `--check` says whether they are current), and each keeps the match summary,
  its bosses and its leak table per wave in the watches.
- `godot-agent run . --renderer gl_compatibility` shows the scene as the browser build draws it.
- The server: `python3 -m unittest discover -s server/tests -t server/tests` (Python 3.11+).
- Networking against the real server: `godot-agent scenario . tests/net/live --headless` (five topology
  scenarios, among them a party by code from the hub, about two minutes) and `python3 tools/net/smoke.py
  --clients 2 --turn-ms 10`, a whole classic match by two headless bots in about 80 s with equal hash streams
  (`--turn-ms` is the server's dev-match turn length). `python3 tools/net/smoke.py --flow` plays the loop against
  the server's hub: two games boot into the hub, one makes a party and the other joins by its code, Ready, Start,
  loading, a High Water match with a Lamplighter and a Lookout played by the plan bots (about eight minutes; the
  hub's matches keep the protocol's 50 ms turns), the results, and both back in the party; `--no-bot` only calls
  the waves, so the Tide wins in about a minute and a half.
- By hand, a dev match: `python3 server/main.py --dev-match classic:2 --host 127.0.0.1`, then two windows of
  `godot --path . -- --join=127.0.0.1 --name=Tamsin` (add `--bot` to let the plan bot play a seat; seat 2's bot
  follows `tests/plans/lamplighter_seat2.json`).
- By hand, the hub: `python3 server/main.py --host 127.0.0.1 --state-dir /tmp/groundhold-state` (no `--dev-match`:
  the server keeps parties), then `godot --path . -- --server=127.0.0.1 --name=Tamsin` and a second window with
  `--name=Edda --main=lookout --code=<the code on the first window's strip>`; or open the game plainly and use Join
  (J): the address `127.0.0.1` makes a party there, a code joins one. Both Ready, the leader starts, and Play again
  brings both back to the party.

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
`Game.TOWERS` holds each tower form's view (model, a head that turns or spins, its bore or muzzle, its shot and
sound); `Tower.model_of(form)` stands one still for the placement ghosts. Views read the simulation's records after
each step (a creep's slow, stun and mark, an Owl's Eye's marked creeps), so team effects need no events. The
command card's slots are `CardQ`, `CardW`, `CardE`, `Signal`, `Sell` and `Ready`; `Hud.card()` says what each holds
and `Hud.checks_shown()` what the strip shows, for `hud_*` scenarios; `view_*` scenarios cover the views.
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
`godot-agent asset check .` must stay clean. `godot-agent scenario . tools/media` re-renders the README's shots.
