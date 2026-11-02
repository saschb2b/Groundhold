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

The owner's ear (2 November 2026): "A sounds the best. also really like C for its relaxing atmosphere. B is not my
jam. feels off."

What it teaches:
- **The orchestra is the hub's voice.** A's sampled orchestra in Bush's shape (a horn's call alone, the violins'
  tune with the horn under it, a strong close over Bb C to D with timpani) is the sound he hears as the game's.
  The hub's theme grows from it.
- **C's calm is the middle.** A harp turning high, the held low D, a rubbed glass, a far bell, and the call handed
  from flute to horn to violins, left open: what he liked "for its relaxing atmosphere" is the long ambient middle
  of Bush's three parts, and the queue's loop.
- **A band of its own, in a jig, is out.** B was as clean by the numbers as A (every rule met, its beat the
  clearest of the three) and still "feels off": the check cannot judge an idiom. Which part felt off is not known
  (the 12/8 lilt, the alto recorder's weak low register leading, the strumstick's thin samples, or a tavern band on
  the hub at all), so none of them leads again without asking; their instruments stay as colours inside the
  orchestra (`music_rules.md`, The world in sound).
- **Two of three landed**, so a round of three takes is worth its cost: it found the direction and the middle in
  one hearing.

## Round 2: A with C's calm, sketches D and E (2 November 2026)

The brief (from the owner's ear, through the coordinator): grow the hub's theme from A, borrowing C's calm, in
Bush's three parts (A's call and tune, C's texture as the long ambient middle, A's strong close), looping cleanly at
2 to 3 minutes; before the piece, two sketches of 30 to 40 s for his ear, both from A with C woven in; and more air,
since all three of round 1's mixes were dark.

What was made: A's theme and C's flats now live once in `pieces/causeway.py` (THEME, FLATS), so the sketches and
the piece play the same notes. Both sketches are in D at 80 (a bar 3 s, 90 frames at 30 fps), eleven bars, about
38 s, at -20 LUFS:
- **D, "The call, then the flats"**: A's order. The horn's call alone, with C's high harp and glass already there;
  A's four bars of tune; then the half close opens onto D major and the orchestra thins to C's flats (the flute's
  call, the horn's turn with voices under it, the violins leaving E hanging over C on the D pedal). The first half
  of the hub's piece, cut short.
- **E, "The flats, then the call"**: a calmer A. C's opening, the flute's call, A's tune softer, A's close held to
  about 4 dB over the tune, then the horn echoing the call quietly over bar 1's floor, so the end runs into the
  start: the hub's loop in miniature.

The air: the harp kept high throughout, the strings in their upper velocity layer with a 3 dB shelf from 3 kHz, a
soft high violin tremolo over the flats, a glockenspiel's glint at a section's head, and a hall less damped above
3.5 kHz (0.8 of its reverb time against 0.55) with louder early reflections (1.3 against 0.9). By the check's air
line (2-6 kHz against 500-2000 Hz): A -9.3 dB and C -11.2 in round 1; D -10.3 (mostly C's dark texture: the harp,
the horn and the low flute keep almost nothing above 2 kHz), E -7.6 (its violins and tremolo longer). A little,
not much: more would mean writing higher (the flute's call an octave up) or a shelf on the master, which is the
owner's ear to ask for.

Caught on the way: the harp moved high rang its D minor F a semitone over the tune's held E (the figure under D
minor is now D and E, and the harp rings less under the tune); the flute and the echoing horn sat more than 4 dB
under the violins until raised; the voices and the glass sat under their roles' floors.

Waiting for the owner: D or E (or a mix: E's opening and echo around D's order), and whether the air is enough.
Then the piece: Bush's three parts at 2 to 3 minutes, looping, from the chosen sketch.

## Round 3: the hub's theme grown from E (2 November 2026)

The owner's ear on round 2: "Grow E". He did not ask for more brightness, so round 2's air stays.

What was made: `pieces/causeway_theme.py`, a seamless loop of 44 bars in D at 80 (2:12), in Bush's three parts.
I, the theme (0:00-0:42): four bars of C's flats, the flute's call, A's tune on the violins, then the horn taking
the tune an octave down with the violins' descant over it. II, the ambient middle (0:42-1:42): C's texture over the
held low D, the call handed at a distance from the flute to the horn to the violins and to the flute again, each
time in a rhythm of its own and left open, two bars of breath after each; then four bars where the pedal lets go
and the roots walk back toward the tune. III, the summation (1:42-2:12): A's tune at full voice with the horns
under it, the close over Bb C onto D major, the horn's echo, and three bars of the flats that turn into bar 1.
`render.py` folds a loop round (its tail onto its start), and the check reads its seam (2 dB between its last and
first 100 ms, its step five times under a typical one). `ambience.py --under causeway_theme` lays a bed of the same
length under it at -28 LUFS: together -19.4 LUFS.

What the numbers caught: the horn's tune handed on sat 4 dB over the violins' (its top third is loud) until
softened; the middle's horn statement stood out the same way; the middle's statements, quieter than the theme's by
design, fell foul of the leads' 4 dB rule, so they became role `distant` with their own band; the call in the same
rhythm in nearly every statement read 90% of bars sharing a rhythm, so the middle's calls now each have their own
(augmented, turned) and a whole piece may reach 85%; the glass's and the contrabass's first notes were silent.

That last one was not the writing: sfizz 1.2.3, rendering faster than real time, loses notes at random (a held note
plays a fraction of a second and stops), differently from one render to the next. It had taken notes out of
renders the owner already heard: sketch B's first bars of bassoon, D's flute call in the flats, and E's tune in its
first bars, roots under it and some of its close. So the E he chose was missing notes he will now hear. `render.py`
renders in blocks of 32 (far fewer losses), throws away a render that loses a note, and keeps a part's fullest
render once it has come out twice: three clean renders of all five sketches came out byte for byte the same. Every
sketch was rendered again so: A and C lost nothing (they differ from what he heard 40 dB under the music, the
smaller blocks' rounding); B, D and E differ where their notes had been lost (E by 9 dB in its fifth bar).

Waiting for the owner: the theme by ear (`.build/music/causeway_theme.mp3`, and with the bed under it,
`causeway_theme_with_ambience.mp3` and `_twice.mp3` for the seam); then F4 places it (SKILL.md, Placing the hub's
music).

The owner's ear (2 November 2026), asked whether the theme is good enough to grow the next pieces from: "Yes, make
the next".

What it teaches: the hub's theme is approved (gate 5 met for it), and its score (`pieces/causeway.py`'s call, tune
and flats, and `causeway_theme.py`'s close) is now the source every other front-end piece grows from, as the
theme's middle grew from C. The loop the owner approved is the one rendered whole (after the lost-note fix); he has
not said whether he wants Warcraft III's gap between loops, so the file stays gapless.

## Round 4: the queue, Match Found and Loading, from the approved theme (2 November 2026)

The brief (the coordinator, from the owner's "Yes, make the next"): sketches of 30 to 40 s for the front end's other
music states, grown from the theme's score, each handing over from the hub on the next bar; orchestral, A's colours,
C's calm, no folk jig.

What was made, all in D at 80 so any of them lands on the hub's bar line:
- **The queue, "Waiting on the tide"** (`causeway_queue.py`): a 12-bar loop at -23 LUFS, a patient pulse of
  plucked celli (D, A) under the contrabass's D, a soft tick of plucked violins on every beat, the flats slowed, and
  the call far off every four bars (flute, then the horn on the match horn's A, then the violins), left open.
- **Match Found, "The tide turns"** (`causeway_found.py`): a two-bar sting, a harp running up Bb and C over a
  swelling tremolo and timpani roll, then the call on the violins and horns over D major with the far bell.
- **Loading, "Walking out"** (`causeway_loading.py`): the call turned into a march on a rope field drum, timpani and
  low strings in eighths: setting out, the horns' march call, A's tune over the march, and four bars that loop
  (`loop_from`) ending on the horns' A, so the match's horn lands as the arrival.
- `handover.py` renders each as the front end will switch to it: the hub's last three bars, then the clip on the
  next bar line, the hub fading over a beat; and the queue into the sting, the way Match Found really comes.

What the numbers caught: a seam read against a bed's rule (3 dB) failed every loop with a downbeat (a bar's attacks
follow a bar's decay), so a piece's seam is now read against its own bar lines' rises; Loading's loop then still
rose less across its seam than its bars do, because its roll and held A ran into the bar line, so the roll ends an
eighth early and the A releases half a beat before the loop returns, a breath; a sting is one gesture, so no bar of
it is asked to come back; a queue whose call is only ever far off reads its distant statements as the tune; the
sting's harp run sat over the violins' call until brought down.

The owner's verdict on 2 November 2026, after hearing the three handed over from the hub: "Yes, keep them". The
queue, Match Found and Loading are approved as they are; with the hub's theme they are the front end's music set
for F4. What it teaches: growing every state from one approved score, and letting the owner hear the handover as
the game will play it, made the set land in one round.
