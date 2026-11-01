---
name: playtest-loop
description: Iterate on Groundhold with a persona playtester (an agent that plays the game through `godot-agent play`, one batch of input at a time, reading a picture and the state in words after each) until the player is genuinely satisfied - pin a build, launch a session with patch notes, watch it, triage its report (already fixed, misread, by design, real bug or design gap), fix and verify with a scenario, commit, and improve this loop after every report. Use when asked to playtest the game, run another playtest session, act on a playtester's report, or continue the playtest loop.
---

# The playtest loop

A persona (who it is: `personas/NAME.md`, written from the research in `research/`) plays
Groundhold through the kit's play harness, `godot-agent play`, a batch
of input at a time: after each batch it reads the state in words (`tools/play/describe.gd`)
and a picture, keeps notes, and at the end reports like a player. You fix what the reports
raise, in short commits, and send the persona back in with patch notes, until it is
genuinely satisfied. Each iteration also improves the loop: `lessons.md` is its log.

Read `lessons.md` first: the satisfaction trend, what the last sessions raised, the
harness's costs and the loop's own lessons.

## Who plays

Four personas, each its own session NAME and memory (`.build/play/NAME/`), all with long years
of Warcraft III custom-map tower defense as the base but the fresh one:

| NAME | Who | Send it to |
| --- | --- | --- |
| `halv` | Halvard, the WC3 custom-map TD veteran (Element TD, Legion TD, Wintermaul), the base | High Water, the Builders and forks, balance, readability |
| `ysr` | Yusra, the send-duel player (Legion TD 2 ranked) | Undertow and Tide Race, the caretaker as a rival |
| `teo` | Teo, the co-op regular who hosts the group's night | the hub, parties, the queue, caretaker partners, the results |
| `noa` | Noa, the fresh tester (no PC TD; no game guide in her prompt) | the first five minutes; replaced after three sessions by `fresh2`, ... (a new file, name and history) |

Run them in turn as the work asks (the Veteran after a balance or kit change, the Duelist after
a duel or race change, the Co-op Regular after a hub or queue change, a fresh tester every few
iterations), one at a time unless the owner asks for more. Different personas find different
problems; where another model family is at hand, let it play or audit a session too
(`research/methods.md`).

## The harness in one screen

```sh
godot-agent play start NAME --renderer gl_compatibility [--fresh] [--pin]   # first picture
godot-agent play do NAME "key Enter; wait 30" [--every 600] [--grid]       # a batch
godot-agent play do NAME "key Space; wait 60; wait 3600 until build window|screen: results" --every 600
godot-agent play stop NAME
godot-agent play list
godot-agent play replay NAME rp --until FRAME [--start K] [--no-sheets]    # a moment again
```

A session is one Godot process on its own Xvfb display, frozen between calls; its files are
in `.build/play/NAME/` (ignored by git): `user/` (its user://: the profile, kept between
starts), `user0/` (as the session began), `history.txt` (every batch with its start and end
frame, its state's hash, its picture and what it cost), `state.txt`, `shots/`, `log`, and with
`--pin` `game/` (the project at the pinned commit). Each start keeps the one before as
`history-K.txt`, `user0-K/` and `log-K` (K from 1; `play start` prints "start K", and every start
counts its frames from 0 again). Always GL Compatibility: the browser build's look, and on this
machine's software GPU the only renderer whose undrawn frames are cheap (lessons.md, The
harness's costs); `project.godot`'s `godot_agent/play_renderer` sets it for every first start,
and a restart keeps its last start's renderer. A fresh user:// starts from
`tools/play/user/` (a fixed device key), so a first-time player's generated name, and with it
the replay, are the same every time.

## One iteration

1. **Pin.** Commit what the persona should play, then
   `godot-agent play start NAME --pin --renderer gl_compatibility` (add `--fresh` for a new
   persona, never for a returning one): the session copies the project at HEAD into
   `.build/play/NAME/game/`, imports it once and runs that copy on every later start, so
   committing meanwhile changes nothing for it and its replays stay exact. Look at the first
   picture, then `godot-agent play stop NAME`. A session launched on a broken build is stopped
   at once (TaskStop, then `play stop`), its profile put back (`rm -rf user; cp -rp user0 user`
   in `.build/play/NAME/`, delete `notes-sN.md`), pinned again and launched again.
2. **Patch notes** (player-facing, in the prompt): what changed since the last pinned build
   (`git log --oneline <last pin>..HEAD`; the pin is `game.pin` and `history.txt`'s `pin`),
   and "From the developers, after replaying your session: ..." for each report that turned
   out to be a misread. A patch note claims only what a check showed (a scenario, a replay, a
   picture), and says a change's limits as plainly as the change. Check that the headline
   lies where the persona will go this session (its mode, its Builder, the wave it reaches);
   if not, say where it is in the goals.
3. **Launch** the persona as a background agent (Agent tool, `run_in_background: true`) with
   the prompt `scripts/persona_prompt.py` prints: `persona_prompt.py 1 GOALS --name halv` for a
   persona's first session (started `--fresh` in step 1: no memory, no patch notes), and
   `persona_prompt.py N GOALS --last LAST --notes NOTES --name halv` after it (the last session
   in two sentences, never its score, and the patch notes, each in a file). GOALS opens with the
   session card: the mode, the Builder (or "your choice"), the party (alone, caretaker partners,
   a caretaker rival), about how many calls, today's mood in a line, and one goal of the
   persona's own ("try the Beekeeper", "beat High Water without leaking a boss"), never "check
   our fix"; then what to judge. Who plays is `personas/NAME.md` (`--persona ID` for another
   instance of one persona, `halv2`). About 220 `do` calls, an hour to an hour and a half.
4. **While it plays, watch it**, whatever else you do meanwhile:
   - Keep the watchdog running from the launch to the report, and look every time it wakes
     you: at its first alert, or after 15 minutes without one:

     ```sh
     for i in 1 2 3; do sleep 300; python3 .claude/skills/playtest-loop/scripts/watch_session.py NAME --alert || break; done
     ```

     (in the background; start it again after each look). `--alert` exits 1 when it wants a look
     and 0 while all is well, so the loop breaks on an alert; `until ... --alert` would end at
     once while all is well and sleep through every alert. It prints the calls against the
     budget, what the screen shows, the pace in frames a call and pictures a call, the
     current match's length in calls, and the minutes since the last note and the last call,
     and says "look:" when the budget is spent, no note came for 20 minutes, no call for 10,
     the pace in a match falls under 150 frames a call, pictures run over 10 a call, a match
     runs past 120 calls, or the game stopped.
   - Each look: read the latest picture it names and the notes' tail. A game problem (a
     soft-lock, a crash, a wall) is yours to fix or to stop the session for; a harness
     problem (tiny batches, a sheet every call, the budget spent) gets a short SendMessage to
     the persona about pace only, never about how to play.
   - Read `.build/play/NAME/notes-sN.md` as it grows; start on its issues before the report
     comes (the session runs a pinned copy, so commit freely).
   - Sweep ahead: test what the persona will reach next (its next mode, the waves it has not
     seen, a Builder it means to try) with the recipes below. New ground is where each
     session's new problems come from.
5. **Save the report** verbatim to `.build/play/NAME/report-sN.md`:
   `scripts/save_report.py AGENT_OUTPUT .build/play/NAME/report-sN.md` reads it from the
   agent's output file. Then add the session's line to `.build/play/NAME/ledger.md` (session,
   date, score, the patch notes it played under), which the persona opens only after it has
   rated the next session: earlier scores in sight pull a rating toward them
   (`research/methods.md`), so it rates blind and compares afterwards.
5b. **Audit the report** before triage: a separate agent (another model family where one is
   at hand) runs `auditor.md` over the persona's file, the report, its notes and the pictures
   the report names, and writes its table to `.build/play/NAME/audit-sN.md`: problems with no
   evidence, knowledge the screen never gave, suggestions written as observations, a score
   against its severities, drift from the persona, praise with no moment behind it. Triage
   reads the report through it.
6. **Triage** every problem into one of:
   - *Already fixed* after the pinned build: say so in the next patch notes.
   - *Misread*: verify by replay (below) before touching code. The persona sees stills and
     words; a tower "that never fired" may be out of range, a click "that was eaten" may have
     landed on the console. Tell the persona in the next notes; a misread seen twice goes into
     `persona.md`'s harness notes.
   - *By design*: check `docs/design/core-loop.md` and `docs/design/world.md` (which wins where
     they differ). Change a designed rule only with the owner; say the design's reason in
     the notes when it reads as a bug.
   - *Real bug or design gap*: fix it. A single sighting of something a rule makes (a leak
     that looks unfair, a wave that feels unwinnable) is first measured over many matches
     with the sim harness (`play_out`, the balance gates): the number sizes the problem and,
     kept as a check, holds the fix.
7. **Fix, verify, commit** per AGENTS.md: a scenario in `tests/scenarios/` for the behaviour
   (failing without the fix), `godot-agent check .`, `python3 tools/names_check.py`, the
   balance gates for any tuned number, a picture of every visual fix (looked at, never judged
   from the code), a line in CHANGELOG.md's Unreleased section for what a player notices. One
   commit per change: the subject states the new behaviour, the body why and the evidence. No
   AI co-author trailer. Never commit anything from `.build/`.
8. **Improve the loop** (below), then go to 1 at once: other work (a release, a feature, the
   owner's questions) runs beside the loop while the persona plays, never instead of it.

Stop when a report gives 9 or more, the persona wants to keep playing for reasons of its own
(a Builder to master, a mode to beat, a friend to bring), would recommend it without a major
caveat, and two sessions in a row raise nothing of severity 3 or 4, for every persona that
still plays (a fresh tester's first session counts for the first five minutes). Then refresh the README's and the
site's shots (`tools/media`) if what they show changed.

## Improve the loop after every report

Append to `lessons.md`: the session, its satisfaction, the fixes it confirmed, its top
problems, the misreads, what the iteration cost (calls, pictures, wall time), and one change
to the loop. Then act on the pattern, not the instance:

- A misread seen twice goes into `persona.md`'s harness notes.
- A procedure done by hand twice becomes a script in `scripts/`.
- A class of problem found late becomes a sweep in step 4 for everything of that class (every
  Builder's kit, every wave's checks, every screen's text).
- Something the persona could not tell from the state or the picture goes into
  `tools/play/describe.gd`, if a player sees it on screen (never what a player cannot see),
  with its line in `play_describe_says_what_shows`.
- Satisfaction stuck for three sessions: find what each session met for the first time; the
  loop is reacting, so sweep further ahead.
- A step that cost more than it gave: change or cut it here.

## Recipes

**Replay a report's moment** (a pinned session's replay runs its pinned copy by itself):

```sh
godot-agent play replay NAME rp --until FRAME     # every batch's frame and state checked
godot-agent play do rp "move 640 300; wait 30" --every 5 --grid
godot-agent play stop rp
```

The replay prints "every frame and state as the original's" and whether its last picture has
the original's pixels; a difference names the first batch that parted. A moment of an earlier
start (the persona restarted its game; its notes say "start K, frame F") is
`play replay NAME rp --start K --until F`: every start counts frames from 0, and a frame past the
start's end is refused with where each start ends. `--no-sheets` replays
three times faster (only each batch's last picture is drawn) with the same frames and states;
its pictures differ in the trees' sway (`materials/foliage.gdshader` moves by `TIME`, which
advances only on drawn frames), so replay with sheets when the pixels matter. The persona's frame
numbers come from its own history; take them from `history.txt` (`# frame N`), not from its
guesses. To read what the state does not say, replay to the moment and write a throwaway
scenario that sets the same match up (`Session.play_offline(...)`, a `seed`) and asserts on
`Game` and `scene`.

**Sweep ahead with scenarios and the sim harness.** A rule question (does the Lookout hold
wave 9 alone, does a race decide right) is answered in `tests/sim/sim_harness.tscn` with
`scene.play_out(...)` and the balance gates (`godot-agent scenario . tests/balance --headless`,
AGENTS.md); a screen question by a `flow_*`, `hud_*` or `view_*` scenario like the ones the
persona's screens already have.

**Watch a whole match fast**: the plan bot plays seat 1 and a caretaker its partner, at
eight ticks a frame, and only every 300th frame is drawn and kept
(`draw_only_captures`): a whole High Water match in about 25 s, its contact sheet and, with
`godot-agent clip`, a GIF. Change the Builders, the company or the mode in `play_offline`:

```sh
godot-agent scenario . --renderer gl_compatibility --inline '{"name": "watch", "seed": 1,
  "ticks_per_frame": 8, "capture_every": 300, "draw_only_captures": true, "timeout_frames": 12000,
  "user_files": {"profile.cfg": "[profile]\nname=\"Watcher\"\nnamed=true\n"},
  "steps": [{"wait": 3}, {"eval": "Session.play_offline(\"lamplighter\", false, 1, \"lookout\")"},
    {"wait_until": "scene_path() == \"res://scenes/main.tscn\"", "timeout": 300},
    {"wait_until": "Game.sim != null", "timeout": 60},
    {"set": "scene._bot", "value_expr": "resource(\"res://tests/bot.gd\").new()"},
    {"wait_until": "Game.over()", "timeout": 11000}, {"capture": "end"}]}'
godot-agent clip ~/.cache/godot-agent/runs/Groundhold/<time>/watch -o /tmp/watch.gif
```

**A session of another persona, or several at once**: each NAME is its own session and
folder (`play list`); run a second persona under its own NAME. Every session is one Godot
process of about 1 GB: mind the machine's other jobs.

## Pitfalls

- The describe hook loads once per start: after editing `tools/play/describe.gd`, start the
  session again (a pinned session keeps the pinned commit's hook).
- `wait N until TEXT` reads only the hook's `watch` lines (the screen, the wave's line, a banner,
  the end plate, the menu), so a word under the pointer, in a tooltip or in a notice ("the next
  build window", online) never ends a wait early.
- `do` refuses a batch with an unknown command or key before anything runs; the frame does not
  move. Key names are Godot's (`Space`, `Enter`, `Escape`, `Home`, `Up`, `Q`, `shift+q`).
- A call interrupted mid-batch (Ctrl-C, a killed agent) leaves the game ahead of
  `history.txt`; the next batch writes a `# note:` there and replays part from that point.
- Wall-clock timers in the game see the time between calls (the frames stand still, the clock
  does not): the online queue's and the hub's countdowns. Offline play has none that matter.
- A headless session (`--headless`) has no pictures and lays the screen out by itself; play
  with pictures.
