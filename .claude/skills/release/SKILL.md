---
name: release
description: Write a Groundhold release's page and its pictures - docs/releases/vX.Y.Z.md, which opens the GitHub release, with stills, GIFs and before/after compares rendered from the real game by tools/release/pictures.py, and the release's text built by tools/release/release_notes.py (the page pinned at the tag, then the downloads by system). Use when a release is being prepared, when asked for release notes, a release page, patch notes for players, release pictures or a before/after, or when the GitHub release's text or downloads block is to change.
---

# A release's page

Each release has a page for players, `docs/releases/vX.Y.Z.md`, in the shape Cyberworld Endless's releases have: a
picture first, a tagline, a paragraph, then a section per change a player will notice, each with pictures from the
real game and a short paragraph, and "Everything else". The GitHub release opens with it; the downloads follow,
written by the tool from the release's own table of files (`assemble.table_for`). The CHANGELOG keeps every detail
and stays as it is: the page is the CHANGELOG's section read as a player reads it, shorter and concrete. A release
without a page shows its CHANGELOG section, so a page is never required, but a minor release (0.N.0) gets one.

## The shape

```markdown
<p align="center">
<img src="media/v0.9.0/hero.webp" width="760" alt="what the picture shows, as a sentence">
</p>

<h2 align="center">A tagline of a few words.</h2>

<p align="center"><b>New in 0.9.0:</b> two sentences: what changed, as a player would tell a friend.</p>

<!-- downloads -->

---

## 📯 A change a player will notice

<p align="center"><img src="media/v0.9.0/compare-x.webp" width="640" alt="..."></p>

What it is, how to use it, and the numbers that matter, in a paragraph or two.

### A part of it (where the change has parts)

---

## Everything else

- One line each: the smaller changes and the fixes.
```

- The hero is the release's best picture: the new thing on screen, in play, at 1280 x 720 (shown at 760).
- The tagline says something of its own, never the first section's heading word for word.
- `<!-- downloads -->` under the summary is where the release's text puts one centred line of direct links (each
  system's file to pick first and the browser game): a player finds a download in ten seconds. GitHub gives a
  release's headings no anchors, so nothing links to `#download`.
- Short: Cyberworld's releases run about 600 words; a minor release's page aims under 1,200 before the downloads.
  A change that was work in progress inside this release (a fix to a feature that is itself new) is no bullet.
- A line only hosts need (the server's health check) goes in the frontmatter's `hosts:`, which the downloads' server
  fold shows, not in "Everything else".
- One emoji heading a section (`## 📯 ...`), none in subsections. Sections apart by `---`.
- Every picture centred in its own `<p align="center">`; two or three in one row when they belong together.
- `docs/releases/index.md` lists the page with its tagline, newest first; `--check` holds it.

## The words

Write as a player reads, short and concrete: what you see, what you press, what it costs and pays, what changed
from before. No internal names: no file, function, scene, scenario, gate, track or milestone names ("M8"), no
`SimMatch`, no "the caretaker's plan list"; say "the caretaker", "the Lamplighter", "the horn", "the waves to come".
The team's shorthand is no player's either (0.9.0's page review): "call early", not "stack"; "in a party", not
"with company"; "the build time between waves", not "the window"; the creep types (Swarm, Swift, Armored, Winged),
not "checks"; "the caretaker playing a Builder solo", not "the caretaker's openings"; and the first time a word
names a control or a stranger, say what it is: "the horn (Ready, <kbd>D</kbd>)", "the caretaker, the AI that plays a
seat no one fills".
Name keys as the game does (<kbd>D</kbd>). Numbers from the CHANGELOG and the game, never rounded into something
new. The release's own words on screen are quoted as they read ("Call wave 8 now? Press again"). Run the
`no-slop` pass over the page before it is done.

## The pictures

From the real game, always: scenarios rendered as the browser build draws them, never a mock-up or an edited
screenshot. Each release keeps its own in `tools/release/shots/vX.Y.Z/*.json`: a godot-agent scenario (the kind in
`tools/media/`) with a `"pictures"` list saying what to cut from its captures (`pictures.py`'s docstring: a still,
a clip, a pair, a compare, a compare of several captures; `crops` stacks several regions of one capture). Then:

```bash
python3 tools/release/pictures.py v0.9.0                 # render every scenario, write docs/releases/media/v0.9.0/
python3 tools/release/pictures.py v0.9.0 drift_tray      # one scenario
python3 tools/release/pictures.py v0.9.0 --again         # recut from the last renders (crops, widths), nothing rendered
```

- **Before and after** wherever something visible changed: a `"compare"` entry runs the same scenario on the
  release before (a worktree of its tag in `.build/before/`, imported once) and on this tree, and pastes the old
  capture beside the new under their versions, in the game's font, the old one dim and the new one gold. Write the
  scenario so both builds can run it; where the old build lacks what the new one has, its `"before"` keys replace
  the steps (`hub_levels.json`). Prefer `"layout": "stack"` for a wide strip of UI, so its text keeps its size.
- **A GIF** where the change moves: capture one label every 5 frames at one tick a frame (12 fps, real time) for 3
  to 6 seconds, `"clip"` with a crop and a `"hold"` of a second or so on its last frame; the tool keeps it under 4 MB
  with fewer colours, then a smaller width.
- **Stage through the game's own setters only** (`Game.lives`, `Game.gold`, `Game.debug`'s logged writes, the plan
  bot, `scene.begin`), and only to reach a moment quickly, never to show what the game would not do: a breach is a
  pack that really broke through, three waves on the road are three waves the horn called. Say what was staged in
  the scenario's description.
- **Look at every picture** before it goes in the page (Read the file): the moment is the one the text describes,
  the words in it are legible at the width the page shows it, nothing is cut off, no tooltip covers what matters.
- **Crop to the change.** A compare shows one change: crop away what is the same in both (a command card both
  builds share, a Builder's name), and pick a moment where nothing else differs (0.9.0's first race compare also
  showed "Wave 1" become "Waves 1–3"). Several tooltips of one change go in one picture (`compare` with a list). A
  thing the text names must be big enough to see at the page's width (a creep of 25 px is not): frame the camera
  closer (`scene.camera.look_from`) rather than crop a wide shot.
- **A state the game reaches.** Lives lost before the first wave, or a moment no match comes to, is a staged lie
  even through the logged setters; play to a real moment (the plan bot) and set only what a real match would show
  there.
- **A GIF reads at its own pace:** the control that starts it in frame, a question or prompt on screen at least a
  second and a half, and the payoff held (`"hold"`) before it loops.
- **People in pictures** are personas (Edda, Ana), never the owner's or a player's real name.
- **Alt text** says what the picture shows in about thirty words, the key words on screen quoted, a compare
  naming both versions: "The duel bar, 0.8.0 above 0.9.0: ...". Never what the picture cannot show ("D is
  pressed").
- **Sizes:** a still at its crop's own pixels where it is UI (no downscaling text), the hero 1280 x 720 shown at
  760, a compare at most about 820 wide; WebP stills (under 1 MB), GIFs under 4 MB, at 640 to 800. The page's
  `width` is at most the file's own.
- **Claim nothing the pictures do not show.** If the text says the caretaker sends what you could see, the picture
  must not be read as showing it unless it does; describe what is on screen, and let the paragraph say the rest.

Godot runs one process at a time on this machine; `pictures.py` renders with `-j 1` and `--renderer
gl_compatibility` (with `"draw_only_captures": true` a scenario draws only what it captures: 0.9.0's seven render in
under three minutes on llvmpipe). A scenario failing an assert makes no pictures: fix the scenario, not the check.
When the page is done, `git worktree remove --force .build/before/<tag>` lets the old tree go (a worktree left in
`.build/` stays registered with the repository).

## The release's text

`python3 tools/release/release_notes.py vX.Y.Z` prints what GitHub shows: the page without its frontmatter, every
relative path pinned at the tag (pictures as raw files, links to the blob view, so the page renders in the
repository before the tag and the release keeps its pictures after main moves on), then `---` and the downloads.
`release.yml`'s publish job runs it with `--dist dist` (each file's size, the checksums folded in) and `--title`
("Groundhold vX.Y.Z"; a page's frontmatter `stage: beta` adds " (beta)": none is set until the owner names a
stage).

- The downloads come from the release's own table of files, never from names typed into the page:
  `assemble.table_for(version)`, `assemble.TABLE` (the one table of the current release's files, whose names,
  `assemble.FILES`, `assemble.py` checks the built files against) or, for 0.6.0 to 0.9.0, `assemble.ZIPS` (one zip a
  system), so a page written for an older release downloads what it really attached. By system (Windows, macOS,
  Linux): the file marked `first` in bold with its size and its words, the others on a smaller "Also:" line; a file
  that only serves another (the AppImage's `.zsync`) is linked in that file's words (`inside`, `{link}`). Then,
  each folded: **Your system will not start it?** (the steps without Terminal first, Terminal for "is damaged"),
  **Host a server** (the archives, the image, the page's `hosts:` line) and **Checksums**. A new file is a new row
  of `TABLE`, with `pack_*.py` making it under that name.
- A release already published (its text redone after the tag): `gh release view vX.Y.Z --json assets >
  assets.json`, then `release_notes.py vX.Y.Z --assets assets.json`, which fails unless the release attaches exactly
  its table's files and adds their sizes and GitHub's digests as the sums.
- `python3 tools/release/release_notes.py --check` holds every page to the rules above (a tagline, alt text and a
  width on each picture, the picture in the page's own media folder and under its size, every path there, the page
  in the index); `test_release_notes.py` runs it over the tree, so CI's release tests do too.
- A page written after its tag was pushed: its pictures are not at the tag, so build the text with
  `--ref <a commit on main that has them>`. Editing a published release (`gh release edit`) is the owner's, from his
  session; an agent prepares the text and says so.

## Order at a release

1. The CHANGELOG's section is written (the gate needs it).
2. Shots: `tools/release/shots/vX.Y.Z/`, one scenario per thing to show, compares against the previous tag.
3. `pictures.py`, then look at every picture.
4. The page and its line in `docs/releases/index.md`; `release_notes.py --check`; `release_notes.py vX.Y.Z` read
   through once as GitHub will show it.
5. Commit the page, its pictures and the shots together, before the tag.
