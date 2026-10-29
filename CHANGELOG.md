# Changelog

## Unreleased

The game is called Groundhold now, after its world (`docs/design/world.md`).

- The game, the site and the server are called Groundhold. The map it plays on is Wickhollow, whose road runs
  from the Welling to the Holdfast, and its last wave brings the Hollowtide Crest. Lanterns, gourds and the
  autumn night stay Wickhollow's own.
- Ids and the protocol follow the name: the server is `server/groundhold_server` (set from
  `GROUNDHOLD_SERVER_*`, built as `groundhold-server.pyz`) and speaks `groundhold.v1` at `/causeway`. On the wire
  the modes are `classic`, `high_water`, `tide_race` and `undertow`, the second Builder is the `lookout`, a
  send is corked and uncorked (`CORK`, `UNCORK`, refused with `NO_CORKS_LEFT` and `NOTHING_CORKED`), and the
  comeback is the `SEAWALL` (`SEAWALL_STANDING`); every id keeps its number. The boss's id is `hollowtide_crest`.
- The repository is `saschb2b/Groundhold` and the site moved to https://saschb2b.github.io/Groundhold/. GitHub
  forwards the old repository address; the old site address does not forward.
- `tools/names_check.py` fails on a retired name anywhere in the tracked tree, and CI runs it next to the
  simulation lint.

The same game on a new engine room: the first step towards playing together (design M1a).

- Every rule now runs in an integer simulation (`scripts/sim/`) that steps 60 ticks a second from the match's
  seed and its turns, with no floats, clocks or scene tree. The same orders give the same match on any machine
  and at any speed; a state hash every second and a checkpoint prove it.
- Solo plays as before: the same eight waves, towers, prices and bounties. Orders go through an in-process turn
  source and land within 50 ms; a tower you place shows as a pulsing ghost, its cost greyed out of your gold,
  until then.
- Next Wave is now **Ready** (still <kbd>N</kbd>, still the war horn): when everyone is Ready the horn sounds at
  once and each second left pays a gold. With company the strip shows how many are Ready.
- Two to four seats already work in the simulation: shared lives, own gold, every kill's full bounty to every
  seat, only the owner upgrades or sells, and contested cells go to each seat in turn.
- Creeps, towers, shells and effects are views of the simulation; a cannon's barrel no longer decides where its
  shell lands.
- Boot flags `--seed`, `--bot`, `--hash-log`, `--quit-after-match` and `--ticks-per-frame` for headless runs.
- Tests fast-forward tick-exactly with `ticks_per_frame`; new scenarios check tick exactness, replays,
  checkpoints, range by road intervals, the co-op rules and the turn order.

One road, two players: a match over a server (design M1b).

- `server/` is the multiplayer server, forked from Cyberworld Endless's: a turn sequencer that never simulates.
  `python3 server/main.py --dev-match classic:2` forms a match from the first two games that join.
- `--join=127.0.0.1` joins it. The game says HELLO, builds the match the server describes, checks its tick-0
  state against everyone's, and plays the server's turns at 60 ticks a second behind a small buffer sized from
  its ping. A stalled game stalls alone and catches up at up to 8 ticks a frame; a state hash goes up every
  second, and two games that part end the match "desynced".
- A party strip at the top left shows each player's glyph in their seat colour, name, gold, link and Ready mark;
  "away", "caretaker" and "left" replace the gold while the caretaker holds a seat. Before the match it says
  where the link stands.
- `--name`, and `--shot-at`/`--shot-dir` to save the window at given ticks. The plan bot plays any seat; seat 2
  builds on its own cells.
- The wire contract (`shared/net/protocol.json`) is read by the game at runtime; a scenario decodes the server's
  recorded transcripts byte for byte. Loopback scenarios run two clients against a fake sequencer in one
  process; `tests/net/live/` runs them against the real server; `tools/net/smoke.py` plays a whole match with
  two headless games and compares their hash streams.
- The server ends a match only on a result most of the present players agree on; with two, both. A player
  still on the way is waited for, and one whose game has played past someone's claimed end disagrees, so the
  match ends "desynced" rather than on one player's word. A result, like a hash, is bounded by the turns
  sealed.
- Asking the server for missing turns costs it at most 100 turns per request and one answer per quarter
  second, so no game can stall everyone else's turns by asking.
- Orders wait for the match: before it starts, and after the link is lost, the commands are greyed, the
  countdown and the horn's early gold are hidden, and a key or click says why ("The match has not started",
  "No link to the server"). Orders that will never land drop their ghosts.
- The game keeps to the server's command rate itself. Ready goes out one at a time and the last press counts,
  so mashing <kbd>N</kbd> no longer costs the connection; any other order past the limit says "Not so fast".
  When the server does refuse a game, the game now reads why before the connection closes.
- Upgrade and Sell grey out for a partner's tower; my plate on the party strip shows my gold less what my
  orders on their way will spend, and keeps its width when the Ready mark goes; the Holdfast counts every
  tower standing, a partner's too.
- The caretaker acts on the first tick of a build window, not up to half a second later; a portrait turns
  from its subject's front when something new is selected.

## 0.5.0 · 2026-10-29

A smaller, crafted console.

- The 208 px bar is gone. A low bronze-over-stone console holds the minimap and the command card on two wings,
  and rises only at the centre into an arched portrait window with a keystone and an amber gem; between them
  the hollow shows through. Gold, lives and the wave hang from a slim strip at the top right.
- The command card holds only its six commands: the three towers, Upgrade (a hammer), Sell (a purse) and Next
  Wave (a war horn). Each icon has its own coloured backdrop, a cost on a shaded foot and a hotkey tab.
  Tooltips give the hotkey, the cost and, for an upgrade, the numbers it changes.
- The info shows numbers, not prose: damage, range, cooldown and slow or splash for a tower; health, speed,
  bounty and toll (the lives it would take) for a creep.
- Wave titles get a gilt rule fitted to the text; "Cannot build there" and "Not enough gold" are small notices
  over the console instead.
- The console is painted at twice its size, so it stays sharp at 1080p and above, and the portrait looks the
  same in the browser as on desktop.
- Fixed: the portrait sometimes framed a newly selected creep tiny or not at all.

## 0.4.0 · 2026-10-29

Hand-modelled plants and creatures, built in Blender.

- Pines with tiers of drooping needle boughs, dark blue-green inside and lit at the tips, and broadleaf
  trees with gnarled trunks and lumpy, layered crowns in green, amber and red. Foliage is painted cards that
  sway in the wind.
- New bushes, ferns, grass tufts, reeds, flowers, mushrooms, mossy rocks, a cut stump, lobed pumpkins and
  lily pads. Ferns now grow in the woods.
- The creeps are rebuilt as rigged models with walk cycles that keep pace with the ground and slow down
  under frost. The gourdling is a jack-o'-lantern goblin on root legs, the scuttler a glossy purple beetle
  with glowing eyes, the thornback a quilled boar, and the Hollow King a crowned pumpkin lord in a cloak
  who carries a lantern sceptre.
- Every model is a Blender build script in `art_src/blender/`, rebuilt with `godot-agent asset blender`.

## 0.3.0 · 2026-10-28

Richer light and forests.

- Tall layered pines with jagged, drooping boughs, dark at the base and bright at the tips, and broadleaf
  trees in green, amber and red with lit crowns. Woods are dense, with stumps among them.
- A low late-afternoon sun from the upper left: faces toward the camera are lit and long, crisp shadows fall
  away. Soft contact shadows under every creep, tower, tree and landmark; SSAO on desktop.
- Deeper greens with darker clumps and bare earth showing through, light haze at the far edge of the view,
  warmer colour grading and a vignette.

## 0.2.0 · 2026-10-28

The ground and the water get the hand-painted treatment.

- Painted, seamless ground textures: grass with blade strokes and autumn patches, a meadow with flowers,
  a pebbled dirt road, sand, mud and stone. The road's borders are ragged, with grass creeping over them.
- The grass rolls in gentle rises and dips; the road stays level, and towers and props stand on the ground.
- The pond is a rounded bowl with sloping sandy banks instead of square tiles: turquoise shallows into deep
  blue, a foam line that laps at the shore, drifting ripples with sun glints, reeds and lily pads.

## 0.1.0 · 2026-10-28

The first public build, playable in the browser.

- A tiled hollow at dusk: a winding road from the rift gate to the hearth, cliffs, a pond, autumn woods and meadows.
- Three towers with an upgrade each: the Arrow Tower, the Cannon Tower (splash, a turning bronze cannon that recoils)
  and the Frost Spire (slows, a floating crystal with orbiting shards). Sell any tower for 70% of what it cost.
- Eight waves of Gourdlings, Scuttlers and Thornbacks, ending with the Hollow King.
- A Warcraft III style console: a minimap you can click, a live 3D portrait of the selection, its stats, and a
  command card of framed icon buttons with hotkeys and tooltips.
- Muzzle flashes, impacts, death bursts with floating gold, build dust, blast rings and frost novas, and a sound for
  each of them.
- Pan and zoom with the arrow keys, the wheel, middle-drag or the minimap.
