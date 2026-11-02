# What the music has taught

## What Cyberworld Endless taught (October 2026)

Read from its trailer skill (`.claude/skills/trailer/` there: SKILL.md, music_rules.md, lessons.md), its tools
(`tools/trailer_music.py`, `trailer_soundfont.py`, `tools/trailers/`) and the owner's words on each trailer. Six
trailers and four sketch rounds, from "very ai-ish" to "sounds awesome" and "approved".

1. **The sound alone does not fix it.** A piece the owner called "very ai-ish. Doesn't truly feel like a MMBN
   theme" was rendered again through a better kit and measured nearly the same: the writing and the arrangement
   were most of the gap, the samples the rest. What read as generic: a wall of held notes with no gaps, one rhythm
   cell in fifteen of twenty-three bars, every phrase ending on a long note, plain harmony at the cadences, static
   stereo, nothing in the low middle.
2. **Sketches before the piece, always.** Three eight-bar sketches in different moods, rendered for the owner's ear,
   before any full piece, and he chose by ear each time. The one piece written without sketches
   came back "rather random... I hear no usage of the soundfont we loved", and the sketch step became a gate.
3. **Numbers are the floor.** Band balance and punch near the reference's, "busier than the source: none", and the
   owner still heard "all over the place" when the writing was not disciplined. So the discipline rules: one idea
   at a time, only the lead moves freely, a part enters at a section's head, the palette he approved first.
4. **A seed he can name.** Every approved piece grew from one source song chosen for what the release was about,
   and kept its tempo, groove, harmonic language and the parts' jobs audible, never its notes. Here the seed is
   Blizzard's RTS-era practice as its composers describe it, and the Causeway's own call.
5. **The palette he loved is a gate.** He missed the soundfont the one time it was left out. The libraries are
   chosen for their licences (FluidR3 GM, MIT, kept over GeneralUser GS for the certainty of its samples' origin)
   and live in a Docker image, never in git.
6. **His measure, written down.** "Music that would make Akari Kaida proud" became five points checked before he
   hears anything. Here: "I want Blizzard devs to be proud of us" (`music_rules.md`, The measure).
7. **He hears it before it ships.** The agent's checks are never his approval; the gate report says what was not
   checked: the music by ear.
8. **Write the lesson into the skill**, not into memory: the owner asked that a lesson from one round hold for
   every round after it.

What does not carry over: the GBA's sound (MP2K, 8-bit samples, squares), reading a ROM, Battle Network's busy
battle grammar. What does: the loop.

## Round 1: the Causeway's theme, sketches A, B and C (2 November 2026)

The brief: the hub's music (front-end.md §4.6 and §8, decision 3: "the sound and music are made the way Cyberworld
Endless makes its trailers' music"), a place where crews meet and set out over the flats; and the ambience bed of
wind, water and a far bell.

What was built: the music image (VSCO 2 CE and VCSL at pinned commits, FluidR3 GM, sfizz patched to float,
FluidSynth), pieces as code, the renderer, the check, the ambience bed, the sampled cues, `levels.json`.

The sketches, all in D around the call (A, D, E: the match's horn on A made into a tune), all at -20 LUFS:
- **A, "The Holdfast's call"**: the orchestra, 84 a minute, D Dorian to a Mixolydian major close; horn alone, then
  violins with the horn as counter, then a summation over Bb C to D with timpani. Nearest Warcraft III's in-game
  pieces as Bush describes them.
- **B, "The crossroads band"**: a folk band from every shore in a 12/8 jig at 63 (dotted quarter): strumstick,
  bassoon, frame drum, bowed psaltery, alto recorder's tune, fiddle and folk harp at the end. Nearest Hearthstone's
  tavern band.
- **C, "Low water"**: sparse, 66, D Mixolydian, a long hall: harp and a rubbed glass over a contrabass D, the call
  handed flute to horn to violins, left open on the ninth. Nearest WoW's zone music as Hayes and Bush describe it.

What the numbers caught before anyone listened:
- The libraries' own levels: in C's first render the horn sat 14 dB over the flute and the contrabass 24 dB under
  the tune, inaudible. `render.py --calibrate` now levels every instrument's median note, and the check's stem
  lines hold each role under the tune.
- An instrument's registers differ as much: the horn's top third is 8 dB over its middle, a recorder's bottom
  15 dB under; the harp's low octave muddied C's middle (84% of its energy between 120 and 500 Hz) until its
  ostinato moved up an octave.
- A's summation first jumped 8 dB in a bar; held to about 5 (Brower: no sudden loud sounds).
- Thin lines down the spectrogram at every bar of C: its contrabass re-bowed each bar with each note a little long,
  so each note-off cut the next note short (one MIDI key). Fixed in the MIDI writer; the contrabass came up 7 dB.
- A far bell's strike thud lit the bottom of C's first bar; a far bell is high-passed now.
- The bands stay dark beside pop: 1 to 4% from 2 to 6 kHz. No target is set until a reference is read.

Waiting for the owner: which sketch to grow, or none; whether the cues and the ambience are the right direction;
whether to keep generating or to commission a theme (front-end.md §8, decision 3).
