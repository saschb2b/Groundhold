---
name: music
description: Make Groundhold's music, ambience and sampled UI cues the way the owner asked (an agent with tools and free soundfonts, rules read from Blizzard's RTS-era scores, sketches for his ear before any piece, his word before anything ships) - pieces as Python code in art_src/music/pieces/, rendered through sample libraries in a Docker image, checked by numbers, spectrograms and a piano roll. Use when asked for music, a theme, a menu or hub track, a sting, an ambience bed, UI cue sounds from real instruments, a sketch round, when the front end's sound (front-end.md §4.6, F4) is built, or when a trailer's music is due (from 0.9.0).
---

# Groundhold's music

The owner's words that started this (2 November 2026): bring Cyberworld Endless's way of making its trailers'
music here, "a high quality approach and skills to generate very good music and sound effects with tools and
soundfonts"; and his bar for Groundhold: "I want Blizzard devs to be proud of us." Read `lessons.md` first (what
Cyberworld taught and every round here since), then `music_rules.md` before writing a note.

## The owner's gates

Anything that misses one is not sent to the owner as a candidate. They hold above any time box: work that cannot
pass them in its time waits; it is not cut short. Gates 2 to 5 are Cyberworld's, each from a piece the owner
refused there.

1. **Groundhold's world, not Warcraft's notes, not Wickhollow's flavour.** The music is the Causeway's and the
   Tide's (world.md): the Flats, the Holdfast, crews from every shore. Nothing that plays on every map (the hub,
   the queue, Match Found, Loading, a mode) carries lanterns, gourds, autumn or night (AGENTS.md); and nothing of
   Blizzard's (a note, a melody, a chord order, a recording) is ever in the repository.
2. **Grown from the references' habits and sounding like them.** The measure: music Blizzard's composers would be
   proud of (`music_rules.md`, The measure: a theme first, bronze not chrome, shape not loop, support never "listen
   to me", a place you can name). Numbers that match are the floor (Cyberworld's 0.16.0 read clean and sounded
   "rather random").
3. **The palette.** Real instruments from the free libraries in `art_src/music/palette.py` (VSCO 2 Community
   Edition and the Versilian Community Sample Library, both CC0; FluidR3 GM, MIT, for what they lack), rendered
   at 48 kHz in a hall. Never the kit's oscillator for music, never a library whose licence was not read at its
   source.
4. **Sketches for the owner's ear before any piece, always.** Two or three eight-bar sketches (20 to 40 s each),
   different takes within the rules, rendered to `.build/music-sketches/`, sent to him; he picks one, and only then
   is it grown into the piece. Never skipped for time.
5. **The owner hears it before it ships.** Nothing goes into `sfx/`, a music folder the game loads, a release or a
   trailer until he has heard that render and said so. A clean `check.py`, a spectrogram that looks right and tests
   that pass are the agent's own checks, never his approval.

## The parts

| Part | Where |
| --- | --- |
| The libraries, their licences and sources, and every instrument with why it is in the palette | `art_src/music/palette.py` |
| The image the libraries and renderers live in (sfizz 1.2.3 patched to write float, FluidSynth, NumPy, SciPy, Pillow, ffmpeg) | `art_src/music/Dockerfile`, built as `groundhold-music` |
| A piece as code: `Score`, `Part`, notes in beats, chords, sections, roles, the MIDI writer | `art_src/music/score.py` |
| Rendering a piece (each part alone, dry, cached), the mix, the master; `--verify`, `--keys`, `--note`, `--calibrate`, `--stems` | `art_src/music/render.py`, `mix.py`, `sfz.py` |
| Each instrument's level (its median note to -30 LUFS) and its registers' loudness | `art_src/music/levels.json` (written by `render.py --calibrate`, never by hand) |
| The check by numbers, the spectrogram and the roll; `--ref` reads a reference recording | `art_src/music/check.py` |
| The pieces and the sketches; what the Causeway's share (the call) | `art_src/music/pieces/` |
| The Causeway's ambience bed, a seamless loop | `art_src/music/ambience.py` |
| The UI cues from the palette (beside `art_src/sfx/sfx.py`'s synthesized bells) | `art_src/music/cues.py`, `cues.json` |
| A sketch round in one go: render and check the sketches (and the bed, the cues), draft the gate report | `scripts/sketch_round.py SKETCH ... [--ambience] [--cues]` |
| The rules, with their sources | `music_rules.md` |
| What each round taught | `lessons.md` |

Everything runs from the host as `python3 art_src/music/<tool>.py ...`: the tool builds the image when it is missing
(once; it fetches about 1.5 GB of samples at pinned commits) and runs itself inside it with the checkout mounted at
`/src`, as you. Rebuild the image (`docker build -t groundhold-music art_src/music`) after `palette.py` changes, and
run `render.py --verify` (every instrument's samples are there) and `--calibrate` (levels.json) after.

## 1. The brief (before any note)

Write down, in a few lines:
- **What the piece is for and where it plays**: which state of the front end (`music_rules.md`, The pieces), how
  long, whether it loops, what plays before and after it (a crossfade from the hub into the queue, the match's
  horn after Loading).
- **The place**: what of the world it carries (world.md), and what it must not (gate 1).
- **The habits it draws on** (`music_rules.md`): which composer's practice or which front end, and why for this
  piece.
- **The takes**: two or three directions for the sketches, each a different answer within the rules (an
  orchestral statement, a band, an ambient handing-on, ...), each with the call (or the piece's own seed) at its
  heart.

## 2. Sketches (gate 4)

1. Write each sketch as a module in `art_src/music/pieces/` (`causeway_sketch_a.py`): `score()` returns a
   `Score`. Its docstring says what it is trying, bar by bar, and which habits it uses: that docstring is the proof
   it is in the manner of the references and not a copy.
2. Eight bars, 20 to 40 s with its tail, each take its own instruments and tempo; the same loudness target for all
   (-20 LUFS) so the owner compares the music, not the level.
3. `python3 art_src/music/render.py NAME_A NAME_B NAME_C --out .build/music-sketches --stems`: WAV, OGG, MP3, MIDI,
   `NAME.check.txt`, `NAME.spectrum.png`, `NAME.roll.png` and the stems.
4. Every sketch passes step 3 before the owner hears it.

## 3. Check it without ears

- `check.txt` reads "every rule met", or each `MISS` is fixed or explained (a rule can be wrong: say why, and
  change the rule in `music_rules.md` and `check.py` together, never quietly).
- The stem lines: no part covers the tune; each role sits in its band under it. Fix a balance with `gain_db`
  (levels.json has already levelled the libraries) and with velocity (a sample's layer changes its tone, not only
  its level).
- Look at `spectrum.png`: a swell or a bell cresting on its downbeat, no gap where the score plays, no click, no
  hum. Look at `roll.png`: the call's returns, the tune's contour, the bass in its octave.
- `check.py --ref FILE` reads a reference recording the owner gives (kept in `.build/`) by the same numbers; aim the
  bands and the loudness range at it.
- You cannot hear it. Say so, and ask the owner to listen.

## 4. The gate report

Goes with anything the owner is sent: one line for each gate, how it is met and the evidence (the world it carries
and what it leaves out; the habits used and the measure's five points; the instruments played and their
libraries; that these are sketches, or which sketch he chose and when; what still waits for his word), and what you
could not check (the music by ear).

## 5. Grow the chosen sketch into the piece

- The piece is its own module (`causeway_theme.py`), the sketch kept beside it. Bush's three parts at the
  `music_rules.md` lengths; the call handed between instruments; the ambient middle; the summation; the end left
  open into the ambience for the hub.
- For `AudioStreamInteractive`: write the piece's clips as separate renders that share its tempo and key (the
  hub, the queue's loop, Match Found's sting, Loading's loop), each cut on a bar so a transition can wait for the
  bar; `--stems` keeps each part for a later mix.
- A tempo whose bar is a whole number of frames when a trailer will cut to it (at 30 fps: 72 is 100 frames, 80 is
  90, 90 is 80; at 60 fps double them).

## 6. Into the game (only after gate 5)

- Music and the ambience go into the project as OGG Vorbis, recorded in `asset_manifest.json` with the command that
  regenerates them (as `cues.py --dest sfx` records its WAVs), never edited by hand; a style rule for them goes into
  `asset_style.json` with them (the sfx rule is 44.1 kHz mono, at most 1.6 s: music is 48 kHz stereo).
- UI cues: `python3 art_src/music/cues.py --dest sfx NAME` writes `sfx/NAME.wav` and its manifest entry; then
  `godot-agent asset check .`.
- Run `python3 tools/names_check.py` on everything written.

## The trailer, from 0.9.0

Groundhold gets a trailer with each minor release from 0.9.0, in Cyberworld's manner (its `trailer` skill), built
as its own skill then, beside this one. What carries over and what changes:

- **The owner's gates, kept**: the look is the game's world in the project's own style (the console's pieces, the
  Causeway's stage, the match's board), never a metaphor dressed over the footage; the music grows from the game's
  own theme (the call) and this skill's rules, in the palette, with sketches for his ear before the piece; he sees
  the cut before the tag.
- **The structure, kept** (Cyberworld's, from the two update trailers the owner pointed at): a cold open of two
  bars without words, the title card ("Groundhold", the release's name, "0.9.0 · out now"), one segment for each of
  the CHANGELOG's headlines (a section card, then two to four shots of a bar, one concrete caption each), a recap
  grid of everything else, the logo's stinger on the music's last cadence, an end card held still (where to play:
  the site and the desktop builds). 35 to 60 s; captions inside the safe area, never two words changing at once.
- **The footage, changed**: Groundhold's comes from scenarios and play sessions, not a ROM's scripted runs:
  `godot-agent scenario . tools/media -j 1 --renderer gl_compatibility --out RUN` (the shots the README and the
  site already take, extended with a trailer's moments), `godot-agent play` sessions replayed to a frame
  (`play replay FROM NAME --until FRAME`), and the race's and the duel's views; each shot rendered as the browser
  draws it (GL Compatibility), at 60 fps, its frames written by `--shot-at` or the kit's capture.
- **The music, changed**: no ROM to read; the piece is this skill's, cut to the trailer's bars (a tempo whose bar is
  whole frames), its sections on the slots (the call under the cold open, the theme with the title card, a lift
  into each segment, the summation's cadence on the stinger), rendered and checked here.
- **To build then**: `tools/trailers/vX_Y_Z.py` (the cut: shots, look, words, in bars and beats), its
  `vX_Y_Z_music.py` here in `pieces/`, contact sheets of the footage and of the drawn cut, an encode in the image's
  ffmpeg, and the places the trailer shows (the site's hero, the README, the release notes). Not before 0.9.0.

## Pitfalls met

- sfizz's renderer writes 16-bit and clips at full scale: the image patches it to write 32-bit float (its
  Dockerfile checks the patch took). A part alone must keep its headroom for the mix.
- The libraries' levels differ by up to 24 dB as recorded, and an instrument's registers by up to 15: render with
  `levels.json`, and read the stem lines, before trusting any balance (the first render of sketch C had the horn
  14 dB over the flute and the contrabass inaudible).
- A key struck again while it still sounds (a contrabass re-bowed each bar with its notes a hair long, a harp's
  string plucked while it rings) is one MIDI key: the first note's note-off released the second, and sketch C's
  contrabass sounded 7 dB under its part for it. `score.part_events` now ends the first where the second begins.
- A cymbal's crescendo crests later than its sample's name says once it is in the hall: start a 1.5 s swell about
  a beat and a half before its downbeat at 84, and look at the spectrogram.
- `showspectrumpic`'s FFT follows the picture's height: at 540 rows the bottom octaves smear and look like rumble;
  at 1024 rows a bin is still 23 Hz, so a bass note's main lobe paints everything under it down to 20 Hz. Below
  about 120 Hz read the bands' numbers and the stem lines, not the picture. A far bell's strike carries a thud:
  high-pass it (160 Hz).
- A loop's IIR filters start from silence: run them round the loop (`ambience.circ`) or the seam clicks.
- Air is written, not filtered in: VSCO's harp and horn and a flute's low octave keep almost nothing above 2 kHz
  (the stem lines' "above 2k"), so a shelf (`Part.air`) on them changes nothing heard; the violins (25-36% above
  2 kHz), their soft high tremolo, a glockenspiel and a less damped hall (`Score.hall_air`, `early`) bring it. The
  check's "air" line (2-6 kHz against 500-2000 Hz, dB) compares mixes: round 1 read -9 to -11 dB, round 2 -8 to -10.
- A harp moved high to brighten a texture sits in the tune's octave: its chord tones ring a semitone from the
  tune's held notes (D minor's F against the tune's E). Change the figure (`causeway.flats` plays D and E under D
  minor) and let it ring less under the tune.
- sfizz prints a line a block when a container cannot raise its threads' priority; `render.py` keeps it quiet
  unless the render fails.
- A heredoc holding Python with backticks or `$` must be quoted (`<<'EOF'`), as in Cyberworld.
