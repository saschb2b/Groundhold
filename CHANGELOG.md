# Changelog

## Unreleased

Resilience (M4): a dropped connection, a browser tab in the background or a game that fell out of step no longer
ends anyone's match.

What a player sees:

- When the connection drops, your world keeps running and a small bronze plate above the console says
  "Reconnecting... your towers keep firing". The game tries again every 2 s and gives up after 30 s. While you
  are gone the caretaker plays your seat with your gold. Once you are back in, the game loads the latest
  checkpoint everyone agreed on, the plate says "Catching up" with a bar, and your seat is yours again at the
  next build window. A party match keeps its party through all of it.
- A game joined straight to a server (`--join`) that crashed, or was closed or killed in the middle of a match,
  takes its seat back when you start it again the same way: it remembers the match and the seat on this
  computer until the match ends. If the match is over by then, it simply joins as a new game. (A game started
  again from the hub does not do this yet.)
- In the browser, a tab in the background tells the others ("in another tab") and flashes the page title. When
  you come back the game catches up, fetches any turns a full buffer lost, and says the caretaker keeps the seat
  until the next build window.
- With three or more players, a game whose state parts from the others' is reloaded from the latest agreed
  checkpoint and plays on; the same game parting a second time is taken out (the caretaker keeps its seat) and
  goes back to the party. Two players apart still end the match "out of step". Each game then saves a report,
  `user://desync/<match>-<seat>.bin`, and the plate names it: the report holds enough to replay that game's side
  up to the tick where they parted.
- Orders wait while the game reconnects or catches up, and the card says why.

The server:

- It compares every seat's state hash each second. At each checkpoint (every 30 s, and as each wave starts) it
  asks one game in turn to upload its state, and keeps the upload only if its fingerprint is the hash everyone
  agreed on; it keeps the last two and never reads them.
- It holds a dropped seat until the match ends, during maintenance and on a full server too, and gives it back
  to a resume from the same profile; a second window of that profile takes the seat over from the first.
- It sends a catch-up at 2 KB per 50 ms while the connection's unsent output stays under 4 KB, a pace a browser
  keeps up with, and the live turns queue behind it. A tab back from the background, or a player the party
  started without, catches up from the latest checkpoint when that is nearer, and gets control back only once
  its game says it is level.
- `/stats` counts desyncs, resyncs and rejoins.

The simulation:

- The caretaker takes over a seat mid-match without undoing the player's work: a plan step whose cell already
  holds one of the seat's towers counts as done, and it forks only the kind of tower its plan built on a cell.
- A seat changes state only when AWAY, BACK or LEFT or the next build window moves it, and the party strip hears
  of it only then.
- Each tick the creeps are sorted along the road once and every tower walks that order, instead of testing every
  creep: a busy tick (four seats at wave 11) steps at about 13,000 ticks a second natively, up from about 5,000,
  so 30 s of turns take about a seventh of a second. Every match plays exactly as before, down to its state
  hashes.

Fixes:

- A game started with `--join` (or any match flag) no longer prints an engine error as it leaves the hub for the
  match: the scene change waits for the hub to finish loading.
- A resync from a server further away than an hour of turns is refused instead of growing the turn log toward it.
- Every test loop that waits for something has a bound and says what never came (the server's tests also cap
  their own memory at 4 GB), after one such loop ran the machine out of memory.

For developers:

- The real-server topologies in `tests/net/live/` now cover the faults: a socket dropped mid-match, a whole game
  killed and started again, a minority of three resynced, and two seats apart ending with both dumps checked.
  `tools/net/shaper.py` puts latency, stalls and cuts in front of one game, and `smoke.py --shaper` and
  `--faults` play whole matches through it. The protocol's transcripts gained `m4_resilience`, recorded from the
  server. `sim_bench` measures the simulation's speed at a busy moment.
- `docs/design/contract-m4.md` fixed what the four tracks shared. The protocol stays version 1 (nothing has
  shipped): `HELLO`, `MATCH_CONFIG` and `RESYNC` got longer, so a game and a server from before M4 cannot talk
  to ones from after it.

The README and the site describe Groundhold as it is now: the hub, the Builders, parties, High Water on Wickhollow
and the results, each with a new screenshot drawn as the browser build draws it; how to play together (in the
browser online only, on desktop over your network, two windows on one computer); and what a player sees when a
link drops, in another tab and out of step. `play/?join=K7Q4M` hands a party code on to the game in its frame.

Builders and checks (M2): High Water is playable. Tamsin Wick, the Lamplighter, and Edda Greyplume, the Lookout,
hold Wickhollow together through twelve waves.

- High Water is a mode of its own on Wickhollow's twelve waves. Each early wave teaches one check: Swarm
  (Gourdlings), Swift (Scuttlers), Armored (Thornbacks) and Winged (the new Duskmoths). The Bristlesow, a larger,
  darker Thornback, comes at wave 6 and the Hollowtide Crest at wave 12. Creep health grows with every wave and
  with the number of players. The classic match plays as before, down to its state hashes.
- Armour takes a flat amount off every hit, never more than three quarters of it. Duskmoths fly: only towers that
  reach the sky aim at them, and splash leaves them alone. Bosses shake off part of every slow.
- Every tower forks once, for good, into one of two branches. The Lamplighter's second branches answer what she
  lacks: the Skyward Loft and the Rime Spire reach the sky, the Iron Mortar pierces armour. The Lookout builds
  Perch Ballistas, Hawk Roosts that hunt fliers first, Kestrel Flocks whose strikes fly on to two more creeps,
  and the Owl's Eye, whose mark makes every tower hit the strongest creep 20% harder.
- Slows and marks never stack; the strongest applies. A hit on a creep a teammate slowed or marked counts as that
  teammate's Help. Perks: the Lamplighter's towers sell for 90%, the Lookout's reach 0.4 tiles farther.
- The command card is the same for every Builder: Q, W and E place your three towers, or choose a branch on your
  own tower; A signals, S sells, D is Ready (N and Space too). This replaces A, C, F, U, S and N. A teammate's
  tower names its owner and cannot be sold. Tooltips say what a fork changes in numbers and which check it lifts.
- The strip shows the next wave's checks, each beside the portrait of the creep that brings it; hovering the wave
  lists every wave to come. Every tower form stands as its own model, Duskmoths hover and glow without lights,
  marked creeps wear a gold rune, and the minimap shows towers in their owners' colours.
- The caretaker plays either Builder and forks for what the team lacks. Balance gates (`tests/balance/`) check
  each Builder alone, the pair, idle teams and the match's length. Tuned to pass them: health grows 25% a wave
  (was 20%), two players face twice the health (was 1.85 times), the Bristlesow has 500 health (was 900), and
  waves 3 and 5 come a little slower.

The hub, parties and the way back (M3): the game opens on the Causeway at low water, where a party forms before a
match and comes back to after it.

- The hub shows your party, your Builder in the arch with the checks the party covers, the modes and one button.
  Alone, Play starts an offline match at once. A first launch asks for the name the others see.
- Builders (B) shows each Builder's role, perk and kit with both branches, with the command card's own tooltips;
  there you set your main and backup, or Try one in a practice match.
- Join (J) takes a party code in any case, with or without its hyphen, lists servers on the home network
  (desktop only) and takes an address: `192.168.1.20` means the LAN, a name means online.
- In a party the leader starts once everyone is Ready, and anyone can cancel the 3-2-1. Loading shows a card per
  player (Connecting, a percentage, Checking, Ready, Slow from 15 s) and names whom everyone waits for. The results
  give each player's numbers and one line of praise; Play again goes back to the hub with the party as it was.
- A server started without `--dev-match` keeps parties by code: Ready and the countdown, the loading timers (4,
  15, 30, 45 and 120 s), the results and the way back, and a dropped player's place held for 40 s. Servers on a
  home network announce themselves. Identities need no accounts: stable on one server, unlinkable across servers.
  Hosts get moderation, the day's totals at `/stats`, retention and daily backups.
- Tamsin Wick and Edda Greyplume stand as figures: the hub's arch shows your main's head and shoulders, the
  Builders screen the whole figure, and party rows, loading cards and the party strip show their faces. The
  console gained the pieces these screens are drawn from, and the Causeway's props are modelled.

M2 and M3 together.

- From the hub, the Lamplighter and the Lookout play as themselves and High Water by its own rules; the stand-ins
  (a Lamplighter for the Lookout, the classic match behind High Water) are gone.
- A build now has one rules hash for every mode. Before, a game said hello with classic's hash, so a party's High
  Water match on a real server could never match it.
- The server tells each party member its own row (`you` in `PARTY_STATE`), and Play again tells it the player has
  left the results. The protocol's transcripts were recorded again.
- `python3 tools/net/smoke.py --flow` plays the loop with two headless games against the real server: a party by
  code, Ready and Start, loading, a High Water match with a Lamplighter and a Lookout, the results, and both back
  in the party with equal hash streams. `tests/net/live/flow_party_by_code_live.json` does the same up to the
  match. CI runs both, and the balance gates.

The Builders' new look: Tamsin and Edda are chibi toon figures now, after League's champions in spirit and The
Wind Waker and A Hat in Time in style: about three heads tall, faces of a few flat shapes, one big hat or hood and
one big tool each (Tamsin's lamp pole, Edda's spyglass), lit in two tones with a crisp edge so a Builder stands out
from the painted towers. Their portraits, busts and icons are rebuilt from the same scripts, and the browser build
lights them like the desktop one.

Fixes from the first review of M2 and M3.

- Two slows on one creep: the stronger one lasts only its own time, and a weaker slow with time left takes over
  the moment it lapses, so a teammate's slow never leaves a creep walking free.
- The rules hash covers the checks each Builder covers, which the caretaker's forks follow, so two builds that
  differ there are never matched together.
- The game never sends its device key: each server gets its own token, derived from the key and the server's
  address, so no server can sign in as you elsewhere or link you across servers.
- A Try, or Play alone, while in a party on a server keeps the connection and the party.
- The server refuses party changes from a player whose match is running, a row held through a long match can
  still be taken back after 40 s, and a LOADED that crosses the loading limit no longer costs the party row.
- Esc in a match opens a small menu: Resume, Restart (offline) and Leave to hub. An offline match waits while it
  is open. From 30 s of loading the leader can start without a stuck player.
- A match opens with the camera on the Welling, the Holdfast and the band where both Builders build. The card's
  Signal has its own icon, a pennant over the ring a signal draws. Tooltips mark fork branches with a sign
  instead of "A" and "B", which read like the A key.
- The hub stands on the Causeway at low water in 3D: the road, tide poles, cairns and wrack under a low sun,
  with the camera drifting along the road. Text fields, rules, panels, loading cards and bars use the console's
  painted pieces. Long names end in an ellipsis instead of being cut, and every perk shows in full.

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
