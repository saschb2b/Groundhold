# The loop's log

Newest last. One entry per report: score, what the session met, what it raised, misreads,
what it cost, and one change to the loop. The persona's own files are in
`.build/play/NAME/` (not committed): `diary.md`, `notes-sN.md`, `report-sN.md`,
`history*.txt`, `shots/`.

## Satisfaction

| Session | Persona | Score | What it met |
| --- | --- | --- | --- |
| 1 | halv | 6 (the audit: a 5 fits too) | High Water three times (Lamplighter twice, Beekeeper), Tide Race and Undertow against the caretaker; m7 at 622a3eb |
| 2 | halv | 6 (the audit: a 7 held at 6 by two open severity-3s) | High Water at Hard three times (Bellfounder lost, Lamplighter 3/15, Beekeeper 9/15) and Undertow against the caretaker; m8 at 624512b |

The four are in `personas/`, written from online research only (`research/`), on the owner's
brief that long years of Warcraft III custom-map tower defense are the crucial base: `halv` the
veteran first, then `ysr`, `teo` and the fresh `noa`.

## Lessons so far

The loop comes from another project of the owner's (a roguelike played through its own
`play.py` by a persona over seventy-odd sessions). These of its lessons carry over, each said
for Groundhold:

- **Pin the build.** A replay on a newer build parts from the session. Each session runs its
  own copy (`godot-agent play start NAME --pin`), kept across its restarts, and its replays use
  it by themselves; commit fixes freely while it plays.
- **Verify before fixing.** The persona sees stills and a state in words. Before touching code,
  replay the moment (`play replay`) and read what happened: an order "that was eaten" may have
  landed on the console, a tower "that never fired" may have stood out of range. Tell the
  persona in the next patch notes ("From the developers, after replaying your session: ..."); a
  misread seen twice goes into `persona.md`'s harness notes, which stops the report coming back.
- **Check "by design" in the design, not in memory.** Before changing a rule a report calls a
  bug, read what `docs/design/core-loop.md` and `world.md` decided and why. Change it where the
  play shows the design wrong, with the owner, and say the design's reason in the notes when it
  only reads wrong.
- **Sweep a class, not an instance.** One wave that surprised, one Builder's branch that read
  wrong: every wave's warning and every Builder's kit is checked the same way at once
  (`view_*` scenarios, the Builders screen through the harness, the sim harness).
- **Turn one report into a rate.** "The Lookout can't hold wave 9" is one match; the sim
  harness (`play_out`, the balance gates) plays a hundred, and the number sizes the problem and,
  kept as a gate, holds the fix.
- **Budget the persona, and watch the session, don't just wait for it.** Sessions ran far past
  their budget at one action a call. The watchdog (`scripts/watch_session.py`) wakes the loop
  every five minutes and on an alert; a pace note goes to the persona (pace only, never play).
- **A stalled agent stalls the persona, not the game.** The game is frozen between calls: a
  SendMessage ("go on from frame F with `godot-agent play do`") resumes it where it was. The
  watchdog's "no call for 10 minutes" is the signal.
- **A carried-over profile can miss the patch's headline.** Check that the headline lies where
  the persona's profile and goals will take it (its mode, its Builder, the wave it reaches); if
  not, the goals say where it is.
- **A patch note claims only what a check showed**, and says its limits as plainly as the
  change. A persona holds the game to its notes; an overstated note costs a session's trust.
- **A check of anything that reacts to an event runs without the event too** (a scenario must
  fail without the fix: AGENTS.md's rule).
- **A question the session exists for gets a path to it.** When a session is meant to judge one
  system (a Builder's kit, the race's clock, the late waves), the goals point the persona at it
  rather than hoping it gets there.
- **Save the report verbatim** the moment it arrives (`scripts/save_report.py`); the notes and
  the diary are the persona's, the report is the developers'.
- **Pick a session's pictures by time, not by number**: `shots/` numbers go on across starts of
  one name (`.next`), so take the newest by modification time, as the watchdog does.
- **One persona at a time unless the owner asks for more**: each costs an hour of tokens
  ("it eats my tokens", the owner of the other project, after four at once).

## The harness's costs (measured while building it)

On this machine (llvmpipe, Mesa 26, 16 cores), Groundhold 0.7.0 pinned, High Water alone, the
window at 1280 x 720, from `history.txt`'s `wall` and `pictures` fields:

| What | GL Compatibility | Forward+ (Vulkan) |
| --- | --- | --- |
| A batch of 600 frames and its one picture | 1.1 s | 142 s |
| A one-frame batch (its picture) | 0.7 to 0.9 s | 0.44 s |
| So: an undrawn frame | 0.4 ms (0.67 ms with `until` reads) | 0.24 s |
| A picture: drawing it, then handing it over | 0.65 s, then 3 ms raw (0.27 s as a PNG made in the game) | 0.25 s, then 0.19 s |
| `play start` to the first picture (pinned copy imported once, 2 to 3 s) | 1.8 s | 2.5 s |
| A session's memory in a match | 0.86 GB | |

With Vulkan on a software GPU a frame costs its Vulkan work drawn or not; only the
Compatibility renderer turns an undrawn frame into processing alone. So every session runs
`--renderer gl_compatibility` (the browser build's look, too). The pictures are the cost: the
proof's won match (below) took 20 calls and 90 s of game time for 28,903 frames and 109
pictures, of which drawing was 70 s. Hence the persona's batching advice: whole build windows
in a call, whole waves in a call with `wait N until`, sheets of five to ten pictures.

## Building the harness: what it taught

- **A wait slept through a build window.** Alone, a build window is ten seconds (600 frames);
  a call that waited 900 frames for the wave's last creeps woke with "next in 1 s". The kit's
  `wait N until TEXT` ends when the state says it (`wait 3600 until build window|screen:
  results`), as a player looks up when the wave ends.
- **The replay's checks found two bugs of the harness itself.** A `wait until` skipped its
  sheet's pictures and with them the batch's last one, so a batch ended on a picture 80 frames
  old (the replay's pixel check); and the reads of its text kept a rhythm per piece of the
  sheet, so a replay without the sheet stopped two frames later (the replay's frame check).
  Both fixed in the kit, each with a test that fails without the fix.
- **The first launch drew a random device key**, and from it the generated name the name
  prompt offers: a fresh session's replay showed another name from its first picture.
  `tools/play/user/net.cfg` (the project setting `godot_agent/play_user`) seeds every fresh
  `user://` with a fixed key, as the scenarios' `user_files` do.
- **Pictures in a replay without sheets differ in the trees.** `materials/foliage.gdshader`
  sways by the shader's `TIME`, which advances only on drawn frames: `play replay --no-sheets`
  (16 s to mid-match, against 48 s with every sheet) matches every frame and state, not the
  sway. Replay with sheets when the pixels matter.
- **Positions are the viewport's.** The first hook multiplied by the root's final transform;
  headless that transform is not the identity, and the scenario's clicks and the hook's places
  parted. Both speak viewport pixels, which the window at the project's own size makes the
  picture's.
- **Godot's own tooltips** open as internal children of the hovered control, not of the root;
  the pointer is not in a viewport's picture (the kit draws it); a pointer that has not moved
  since a screen changed hovers nothing in Godot (the hook says so instead of "off the board").
- **The describe hook loads once per start**: after editing it, start the session again.
- **Sheets of four narrow columns lost the creeps**: up to nine pictures now stand in three.
- **Watching a whole match fast** needed a rendered run that draws only its captures
  (`draw_only_captures`): the plan bot and a caretaker partner through all twelve waves of High
  Water at eight ticks a frame, 17 pictures, in 26 s (SKILL.md's recipe).
- **A click on a red ghost is refused**, and in a batch that places and then calls the wave the
  notice is gone by the batch's end: the persona's notes say to read the next state's towers
  (or move first and read the ghost's colour) before calling the wave.

## The harness's review: what it taught

A developer played the pinned harness end to end (two starts, 38 batches, a won High Water
match) and replayed it before any persona did. What it found, and what changed:

- **The watchdog's loop was inverted.** `watch_session.py --alert` exits 1 when it wants a look,
  and the documented `until ... --alert; do sleep 300; done` ended at once on a healthy session
  and slept through every alert. Now `for i in 1 2 3; do sleep 300; ... --alert || break; done`:
  it wakes the loop at the first alert or after 15 minutes. Run a watchdog against a session
  that is healthy and one that has stopped before trusting it.
- **A restart hid the moments before it.** Each start renamed the last history, but a replay
  read only the newest, and `--until` past its end replayed all of it and said "every frame and
  state as the original's". Now `play replay --start K` replays any start, a frame past a start
  is refused naming where each start ends, each start keeps its log (`log-K`), and `play start`
  prints "start K" for the persona's notes.
- **The words said more than the screen.** "Free grass near the cursor" listed cells a player
  reads off the build grid (`shaders/terrain.gdshader` draws it on buildable cells while placing:
  shot 0024 shows it), "meadow" named what looks like grass with flowers, the furthest creep's
  exact health stood where the screen has a small bar, and the hub's party line spoke ids
  ("diamond Grimhold lamplighter"). Each now reads as it looks: the ghost's colour and whether the
  grid covers the cell, "grass with flowers", "its health bar about 50% full", "Grimhold (diamond
  mark), Lamplighter's face", the roster by its captions (WARDEN), a forked slot as "the branch
  this tower took", not "placing it".
- **The words said less than the screen** where the screen is dense: the results plate's
  Damage, Help and Towers columns and its lives line, the waves-to-come list's rows, and what
  got through in a wave (a player sees it walk in; a sheet every five seconds misses it). Each
  is in the words now.
- **A wait ended on a word under the pointer.** `wait 6000 until screen: results|end plate|over`
  stopped mid-wave on "cursor 640,200: over water". A wait now reads only the hook's `watch`
  lines (the screen, the wave's line, a banner, the end plate, the menu); online notices that
  say "the next build window" would have ended every wave's wait at once.
- **A sheet is shrunk to the reader's image budget whatever its columns**, so ten pictures of a
  wave read as small as on four columns: the persona's wave call is `--every 600` (four to six
  pictures), and a closer look is a short call of its own.
- **A restart without `--renderer` drew with Vulkan**: Groundhold's desktop default is Forward+,
  where 600 frames cost 142 s on this machine and a long wave's wait outruns the call's timeout.
  A session now keeps its last start's renderer, and `godot_agent/play_renderer` in
  `project.godot` sets GL Compatibility for every first start.
- **The first session's prompt read like a returning player's** (a diary and notes that did not
  exist, "your profile continues", an empty patch-notes heading): `persona.md` has a first
  session's part and a later one's, and `persona_prompt.py` takes the last session and the
  patch notes only from session 2 on.

## Session 0: the harness's proof (no persona; the developer through `play do` only)

`kestrel`, fresh and pinned (c7073b9): the name prompt answered (ctrl+a, Wren, Enter), the
Tide Race button hovered (its tooltip), Play clicked at the place the state named, a Cannon
Tower and an Arrow Tower placed by clicking cells, every wave called with Space and run to its
end with `wait until` and a sheet, forks against the armoured and the winged waves, and the
results: THE HOLDFAST HOLDS, twelve waves in 8:00, 15 of 20 lives (the Bristlesow, wave 6's
boss, took five). Twenty calls. A replay to frame 12,000 matched all ten batches' frames,
states and the last picture's pixels; without sheets, the frames and states.

First things a persona will meet (found by the harness's probing; not changed here, as they
are views' and screens' work, and listed for triage):

- The hub's Tide Race button says "Comes with a later version" on hover, though it plays.
- The hub offers High Water alone, with no caretaker partner (design 1.5 has Solo, Try and
  Race the caretaker), so a player alone never meets the co-op the mode is named for.
- The Ready slot's price and its tooltip differ by a gold at the same moment (+9 on the card,
  +10 in the tip).
- The results give a player with no tower and no kill "Kept watch", and a won match "Held wave
  11".
- Playing idle, the Holdfast fell in wave 2 at 1:35; the Bristlesow leaked five lives through
  six towers twice.

## Session 1: halv, 6 (1 November 2026)

Pinned at m7 622a3eb, before the duel's finishing pass (B2) merged; 168 batches, 29 minutes of
the agent's wall time, about 370k tokens; five matches in one start (and a first start that only
pinned). The audit (`audit-s1.md`) struck three claims and downgraded four; the score stands.

- **Raised and fixed the same day** (eight commits, each with a scenario failing without it): a
  creep that leaked stayed the selection, so Esc opened the menu and the next build click hit
  Leave to hub, which asked nothing (a whole match lost); the menu now asks with Stay as the
  default. The Builders screen's tower card stayed the first Builder's; the clear banner said
  nothing of a leak; a boss's own checks were missing from the wave list; "Held wave 11" (now
  "Most kills in wave 11"); "passable" unexplained.
- **Met on the pinned build, fixed by then on m7**: the Drift tray lit before the window opened
  for both, a Ready said early that spent the window, "Wave 13 of 12".
- **Owner's decisions from it** (design M8, `contract-m8.md`): waves stack (calling early was
  "a button you always press"), Hard and Very Hard (one build won 16/20 and 20/20), a rival's
  bottle names its window's three packs (the duel's sends read as unreadable), and a fork pass
  (the Beekeeper's last pair "not a real choice").
- **Misreads and overreach** (the audit's): the wave list did show wave 12's checks; "within 10%
  at every armour" was 12% at armour 6; "the harness slept through the Surge's window" was most
  likely an early Ready on the pinned build, which today's Space no longer says.
- **Still open for round two**: the Surge absent from the wave list until it starts, the
  Seawall unexplained (its countdown not noticed), creep health and armour readable only on the
  field, the race's own clock and rule not on screen, the Tithe not named in the clear banner.

**Loop changes from it:**
- The auditor earns its place: three struck claims, a severity read down, a highlight with no
  frame; it reads 30-odd pictures, so give it the frames to check, not the whole folder.
- The watchdog counted five matches as one "long match": its snapshots five minutes apart missed
  the results screens between them. A match now also ends where the mode changes or the wave goes
  back (`watch_session.py`).
- Pin after merging what is in flight, or say in the goals which screens were fixed after the
  pin: this session spent its duel on a build two fix passes old.
- A persona given "your choice" took every mode in one evening: good coverage, but each got one
  match; the next session's goals name the mode to go deep in.

## Session 2: halv, 6 (2 November 2026)

Pinned at m8 624512b; 183 batches, 29 minutes of the agent's time, about 360k tokens. Hard gave him the close wave 12
he asked for (the Crest dead at 78 of 3,938 with 3 lives left), and the fork pass a real choice in the Beekeeper's
last pair; two severity-3s held the score: the duel's D-Ready still took his window, and the Sky Toll's tip promised
one tower held the fliers alone. The audit struck a cost the report blamed on P1, a "one tower short" that was a
road's length, and a "do what they say" with no frame, and downgraded P2, P4 and the score's reading (6 to 7).

- **The pin missed a release's fixes.** m8 was branched from m7 before 0.8.0's last fix round, so five of the patch
  notes' promises (health and armour in the wave list, the Surge listed, the Seawall's tip, the duel's Ready held,
  the Tithe named) were not in his build; he reported each as "not as played". The audit caught that they existed
  on m7-rc. Merged main into m8 the same day (keeping both sides: health on every row with several waves on the
  road, banners with the Tithe and the lives per wave).
- **Fixed from it**: what one patch tower holds alone, measured per level and cell (a Sky Toll holds wave 5 only
  inside a bend: 7 of 206 cells), the hub's level words standing still, numbers to two decimals, the results'
  forks counted as they stand. Measured for the owner: an uncorked pack breaches 25% of the time (none in a
  Beekeeper mirror); the owner chose stronger packs and a fairer stipend.
- **AGENTS.md reached the persona**: the session put the repository's AGENTS.md into its context unasked; it said
  it did not use it, and the audit found one word ("stake") that only the design and AGENTS.md use. A persona's
  agent inherits the project's instructions.

**Loop changes from it:**
- After a release, merge main into the next milestone's branch at once, and pin only a build that holds every fix
  the patch notes name; write the patch notes from `git log <last pin>..<pin>`, never from memory of what was done.
- Run personas so the project's instructions do not reach them (a session or agent outside the repository's
  instruction files, or say in the prompt that they are a developer's and must be ignored), and let the auditor
  keep checking for the design's words.
- A persona's wait slept through a Surge window again: the harness's duel words now watch "Surge" lines and say
  "waiting for the window" while the rival's wave runs (merged from main).


## Session 3: halv, 6 (2 November 2026)

Pinned at m8 705155c (the sends pass merged, every fix the patch notes named in the build); 150 batches, 29 minutes of the
agent's time, about 357k tokens. Three Undertow duels against the caretaker (lost on wave 12, lost on wave 7, won on wave
10 by a send: the session's own goal) and two High Water at Very Hard (fell in wave 8; left at 5/10 after wave 6). Every
patch-note item held as played, the five session 2 missed among them; the duel "now plays as a duel", which alone would
have been a 7. The score stayed 6 on one severity 3: Very Hard alone is a wall at wave 6, not a close wave 12. The audit
(`audit-s3.md`) upheld H3-01's twelve sends, struck "the caretaker's sends that hurt me were only Moth Clouds" (one was
the wave's own creeps, one a Thorn Herd) and a cork "that read my juggle" (corked before it), and read H3-02 down to 2:
both Very Hard builds left the bottom leg bare with gold unspent.

- **The persona found a gate that passed what the owner's words rule out.** Read from the gates' own `summary.bosses`
  the same hour: at Very Hard every solo plan leaks the Bristlesow (−5 of 10) and falls to a Crest it has worn to 6 to
  26% of its health (one of the six crews won), and `bot_reaches_crest_very_hard_*` passed, reading "a close wave 12" as "stands until wave 12's horn".
  Hard is the close wave 12 (the Crest dies at 72 to 80 s, just before its leak). So the audit's downgrade of the
  persona's build does not touch the finding: the plans, which know the map, lose the same way. A pass retunes Very
  Hard and tightens the gate to the boss's health left. (I first read the summary's "3868/5250" as health left; it is
  damage dealt. Say which a number is before quoting it to the owner.)
- **The Bristlesow leaked in all 8 of his matches' sides this session** (his five, the caretaker's three duels) and in
  every session before: the plans leak it at Normal with the Lamplighter and the Lookout and at Hard with every
  Builder. A wave-6 boss that a −5 is the expected price of at every level is a design question for the owner, not a
  number to tune quietly.
- **Only the Moth Cloud breached** in his sends (6 of 7; the Gourd Rush, the Scuttle and the Thorn Herd 0 of 5, a tier
  III Thorn Herd among them at a Lamplighter on 4 lives, "weak against Armored"): ten of the twelve in one Lamplighter
  mirror, so a pass measures every pack against every Builder before changing anything.
- AGENTS.md reached him again; the prompt's new rule made him say so in the card, and the audit found no word or
  number taken from it.

**Loop changes from it:**
- A gate's pass condition must put the design's words in numbers that can fail: a "close" wave read from how much of
  the boss is left, not from the wave reached. When a persona calls a level a wall, read the gates' summaries for that
  level before judging the persona's build: the plans are the best play the project has.
- A persona's report can be right about the game and wrong about its own play at once; the audit reads the play, the
  gates read the game. Triage needs both.
- GOALS no longer ends with "would you play it on your own time": `persona.md` adds that line (session 3's prompt said
  it twice).
