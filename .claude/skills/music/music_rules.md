# Writing Groundhold's music

What makes a piece sound like it belongs beside Blizzard's RTS-era scores (Warcraft III above all) and not like
generic game music, written as rules to compose from, with Groundhold's own world in them. The owner's bar: "I want
Blizzard devs to be proud of us." The habits come from:

- **The composers' own words** (marked with their name): Tracy W. Bush to Massively's Justin Olivetti (Engadget,
  17 September 2013, <https://www.engadget.com/2013-09-17-jukebox-heroes-tracy-w-bush-opens-up-about-wow-dungeon-runner.html>);
  Jason Hayes to IGN's WoW Vault (2005, republished by Blizzplanet,
  <https://blizzplanet.substack.com/p/jason_hayes_interview_at_wowvault_ign>) and to Experience Gaming (GameBanshee,
  2005, <https://www.gamebanshee.com/8c6c>); Glenn Stafford and Derek Duke at BlizzCon 2008
  (<https://www.engadget.com/2008-10-13-blizzcon-2008-blizzard-sound.html>); Russell Brower on Mists of Pandaria
  (Blizzard, 2013, <https://worldofwarcraft.blizzard.com/news/9762739/the-music-of-mists-an-interview-with-russell-brower>)
  and to Destructoid (<https://www.destructoid.com/exclusive-meet-diablo-iiis-sound-team-samples-included/>); Peter
  McConnell and Eric Dodds on Hearthstone's tavern (Destructoid, 2013, <https://www.destructoid.com/?p=130841>).
- **Documents** (*doc*): the games' credits (<https://warcraft.wiki.gg/wiki/Warcraft_III_credits>,
  <https://warcraft.wiki.gg/wiki/Warcraft_III:_The_Frozen_Throne_credits>), the soundtrack's track list and lengths
  (<https://warcraft.wiki.gg/wiki/Warcraft_III:_Reign_of_Chaos_Soundtrack>), Garritan's page naming Warcraft III
  among its users (<https://www.garritan.com/spotlight/whos-using-it/interactive-games/>), Reforged's patch notes
  (2.0.0, <https://news.blizzard.com/en-us/article/24167122/warcraft-iii-reforged-patch-notes-patch-2-0-0>; 3.0.0,
  <https://us.forums.blizzard.com/en/warcraft3/t/warcraft-iii-reforged-forsaken-kingdom-patch-notes/38400>), WoW's
  zone music table (<https://wowdev.wiki/DB/ZoneMusic>) and login screen
  (<https://warcraft.wiki.gg/wiki/Login_screen>), Warcraft II's in-game tracks
  (<https://www.vgmpf.com/Wiki/index.php?title=Warcraft_II:_Tides_of_Darkness_(DOS)>).
- **Critics** (*critic*, an opinion): PC Games' review (Thomas Weiss, 2002,
  <http://www.pcgames.de/WarCraft-3-Reign-of-Chaos-Spiel-41725/Tests/Echtzeit-Strategie-in-Perfektion-65210/>),
  English Wikipedia's Audio section on Reign of Chaos, RPGFan (Josh Gregory, 2003).
- **Ours** (*ours*): our own reading of the genre and of orchestral practice where no source speaks (no written
  harmonic analysis of any Warcraft III track was found, 2 November 2026: modes, chords and tempos are ours until
  the owner's ear or a reference says otherwise). An *ours* rule is the first to change when the owner hears it.

Never take notes, melodies, chord orders or recordings: habits only, as Cyberworld's trailers took Battle Network's
(`lessons.md`). A recording the owner hands over for a reference stays in `.build/` and is read only by numbers
(`check.py --ref`); nothing of Blizzard's enters the repository.

## The measure: music Blizzard's composers would be proud of

Matching numbers is the floor, never the measure (Cyberworld's 0.16.0 read "busier than the source: none" and still
sounded "rather random" to the owner). What the bar asks, from the composers' words and the rules below:

- **A theme first.** A tune a player hums after the hub, stated by one instrument, answered, handed to another and
  coming back. Every Causeway piece grows from the call (below). If the tune cannot be sung back, it is not ready.
- **Bronze, not chrome.** Brower calls Warcraft's sound "bronze-age" (Destructoid): horn, strings, harp, wood, skin
  and bells in a hall, played by samples of real players (palette.py). No synthesizer, drum kit, riser or pad
  that a listener would name as electronic.
- **Shape, not loop.** Bush's three parts: a theme to build on, an ambient middle, a strong summation (*Bush*). A
  piece goes somewhere, and the player feels it answer them (his "illusion of interactivity").
- **Support, never "listen to me".** Brower: the music supports and immerses and must not demand attention; it is
  about contrast, and loud lands only after quiet; and no sudden loud sounds (*Brower*). The hub's music lets you
  read and click.
- **A place you can name.** The Causeway at low water: a raised road over the Flats, wind and water and a far
  bell, crews from every shore meeting and setting out (world.md). Not Wickhollow, never night (below).

Before the owner hears anything, say in the gate report (SKILL.md) how each of these five is met.

**The owner's ear so far** (his words, verbatim; each one a gate note the rules below now carry):
- 2 November 2026, on the first three sketches: "A sounds the best. also really like C for its relaxing
  atmosphere. B is not my jam. feels off." A, the orchestra (a horn's call, the violins' tune, a strong close over
  Bb C to D), and C, the sparse daylight (a harp high, the held low D, the call handed from flute to horn to
  violins, left open), landed; B, a folk band in a 12/8 jig with an alto recorder's tune, did not. All three had met
  every rule check.py held: the idiom is the ear's to judge, not the numbers'.

## What Blizzard's RTS-era music does

**Form.**
1. Warcraft III's in-game pieces run about four to five minutes (Reign of Chaos' album: 3:58 to 5:14, *doc*), in
   three parts: an opening theme, an ambient middle, a strong close (*Bush*). Players built during the theme,
   scouted during the middle and fought during the close, and heard the music as answering them (*Bush*).
2. The score was not interactive (*Bush*). Short cues exist: the album's shortest pieces are 1:08 and 1:12
   (*doc*); Warcraft II's victory cues ran 35 to 40 s, its defeats 43 to 55 s (*doc*).
3. Warcraft III cycles a people's pieces, and its map music plays after the current piece ends (`SetMapMusic`,
   *doc*); a community note puts 20 to 40 s between them (unverified). WoW's zone music has a silence of its own
   length between pieces (*doc*), and its pieces are often left unresolved, so a mood carries into the silence and
   the next piece reinforces it (*Bush*).

**The sound.**
1. Warcraft III's in-game music was made in-house with sample libraries: Garritan Orchestral Strings were used in
   its production (*doc*), and Hayes' rig of the time ran Vienna, Siedlaczek, Vitous and Garritan's libraries
   (*Hayes*). Live orchestra and choir were recorded for the cinematics (*doc*, the credits), and only a few times
   in all (*Hayes*). A sampled orchestra played with care is the genre's own sound, not a compromise.
2. Each people has its colour: the night elves' flutes over nature (*critic*, PC Games), "ambient" and wind-voiced
   (*critic*, Wikipedia); the humans' hymns and choir (*critic*); the orcs' trombones, drums and shouts; the
   undead's wind-like, atonal sounds (*critic*). Alliance and Horde each get their own melodic devices and tone
   colours (*Brower*).
3. Bush wrote the night elves' music (*Bush*); for WoW's Tanaris he used large reverbs to suggest vast distance
   and chose samples for a place's feel rather than an instrument's name (*Bush*).
4. WoW's zone music strips the orchestra down: a few instruments state a theme, it builds a little, the melody
   passes to another instrument and it fades, with little structure (*Bush*, crediting Hayes); it should work like
   light or fog, felt more than heard, and the thematic pieces play only at the places that matter (*Hayes*).
5. Ambience never stops, so players hear it more than the music (*Brower*).

**Front ends.**
1. Reforged's main menu changes its music and its ambience together with the chosen theme (3.0.0, *doc*): a menu
   is a pair, a music bed and an ambience bed.
2. WoW's login screen plays one long piece, a journey through its themes, kept from expansion to expansion
   (*Brower*, *doc*); players waited through all of it before logging in (*Brower*). A roar at a set interval on
   one login screen drew complaints and was made much quieter in the next (*doc*): a repeated loud event in a
   front end wears.
3. Hearthstone's tavern is a small band playing in the room, ambient and leaving space for play: guitar, fiddle,
   harp and contrabassoon; a Celtic triplet feel turned into a steady groove; "Warcraft, whimsy and warmth" was
   the brief (*McConnell*, *Dodds*). Its legendary stingers run about five seconds (*McConnell*).
4. StarCraft II's menu echoes the first game's menu music (*critic*): a front end's theme is the game's signature,
   kept.

## Groundhold's music

**The pieces and where they play** (front-end.md §4.6: an `AudioStreamInteractive` crossfaded by state):

| Piece | What it is | Length |
| --- | --- | --- |
| The Causeway (the hub) | The theme in Bush's three parts, grown from sketch E (A's theme with C's calm; the owner, 2 November 2026: "Grow E"): C's flats and the flute's call, A's tune, C's texture as the long ambient middle, A's strong close and the horn's echo into the flats; a seamless loop, its end running into its start (`pieces/causeway_theme.py`). WC3's 20 to 40 s of ambience alone between pieces is the player's to add if the owner wants it, never cut into the file | 2:12 (44 bars at 80), looping |
| The queue | The ambient middle's material as a loop that can run for minutes: the ostinato and the drone, the call in fragments, nothing that builds | a loop of 1:00 to 2:00 |
| Match Found | A sting over the queue's bar: the call on the horn over a rising harp and a bell (Hearthstone's stingers run about 5 s) | 4 to 6 s |
| Loading ("Walking out") | The call turned into a march out (a rope-tension field drum and timpani, the low strings in eighths; never the frame drum's folk lilt, sketch B), building toward the match and ending on the horn's A so the match's horn lands as its own; played once, then its last bars looped (`Score.loop_from`) until the match stands | 0:30 to 0:45, its last bars looping |
| The Ebb (results) | Later: a close of 35 to 55 s (Warcraft II's victory and defeat lengths), won and lost | 35 to 55 s |

**The call.** Every Causeway piece grows from one figure: a rising fourth and a step, long-short-long (A, D, E in
D; `pieces/causeway.py`). It is the Holdfast's horn made into a tune: the match's `wave_horn` sounds A (220 Hz),
the hub sits in D, the call starts on the horn's own note, and the countdown's horn on 0 lands as the theme's
fifth (front-end.md §5.3). Every map has a Holdfast, so the call runs on every map. *Ours.*

**The world in sound** (*ours*, from world.md):
- The Flats are wide: open fifths and a held D under the music (the horizon); nothing below C3 closer than a fifth.
- The Tide is one water, rising and falling: an ostinato that turns up and down over its chord (a harp, high, as
  in sketch C), slow, like water on sand.
- Builders come from every shore and every age, and their instruments are colours inside the orchestra (a bowed
  psaltery's or a rubbed glass's air, hand chimes, a recorder doubling the flute), never a band of their own and
  never a jig: sketch B's band in 12/8 was "not my jam. feels off" (owner, 2 November 2026). Which part of it felt
  off is not known (the jig's lilt, the recorder's weak low register, the strumstick's thin samples, or a tavern on
  the hub at all): ask before any of them leads again.
- The Holdfast is held: the horn, and timpani on the roots of a summation.
- It is daylight: the hub is never night (front-end.md §4.4). No lantern, gourd, autumn or night in anything that
  runs on every map (AGENTS.md): no harvest dance, no spooky celesta, no Hollowtide colour. A Builder's own land
  may colour her own page later (below), never the hub.

## Harmony (*ours*)

1. **Modal.** D Dorian for the hub's hope with weather in it (the raised sixth, B natural, is its brightest note),
   D Aeolian for the Tide's weight, D Mixolydian for daylight and the summation's warmth (its C natural, the bVII).
2. **No functional V7 cadence.** Close by bVII to I, IV to I (a hymn's plagal close), or bVI bVII i (the heroic
   rise); the minor v or a suspended v (Asus4) for a half close; a major V only once, as a surprise.
3. **Pedals and drones.** The tonic (or the fifth) held under changing chords: C over D, G over D. A drone enters
   at a section's head and stays.
4. **Slow harmonic rhythm.** One chord a bar in a theme's statement, two toward a close; 0.5 to 2 changes a bar
   (check.py), slower than a battle (Battle Network's 1.3 to 1.9).
5. **Colour by suspension and added tones**: sus2, sus4, add9, the Dorian's IV major; a borrowed bVI (Bb) at a
   summation; a Picardy major I at the very end of a strong close. A borrowed note is named (`Score.borrowed`) and
   kept under a fifth of the time; anything else outside the mode under 8%.
6. **Voicing.** Wide in the bass (fifths and octaves below C3), close in the middle; horns in fifths and thirds;
   strings open.

## Melody

1. **Grow from the call.** State it, answer it in the same rhythm, state it again higher or over a new chord, then
   a phrase that does not close (on the fifth or the second). Two plus two bars.
2. **Hand it on.** The tune passes between instruments at phrase heads (horn, then violins; flute, then horn, then
   violins), each statement in its instrument's singing register (*Bush*, *Hayes*). The check reads the hand-off as
   no leap.
3. **Singable.** Each statement within an octave and a third (16 semitones); at least 45% steps and repeats, at most
   12% leaps past a fifth; one long note a phrase (a beat and a half or more), after a rise.
4. **The rhythm comes back.** A quarter to three quarters of the tune's bars share a rhythm with another bar within
   eight (the call's long-short-long is the thread); the call itself returns at least once in eight bars.
5. **Folk colour sparingly**: a turn, a dotted figure, never a whole melody of runs and never a jig's lilt on
   the hub (sketch B, above).

## Arrangement and orchestration

1. **Few voices, each doing a job.** At most seven lines sounding at once in a sketch (a doubling an octave under is
   no new voice: `Part.doubles`). A part enters at a section's head, or as a pickup of up to two beats into one (a
   swell or a bell up to a bar). Cyberworld's discipline, kept: one idea at a time; only the tune moves freely.
2. **Roles.** One tune (`lead`); a counter that moves where the tune holds; harmony (violas, voices) under it,
   never exposed; the bass (celli, contrabass, bassoon, plucked celli); a drone; an ostinato (harp, strumstick);
   percussion (frame drum, timpani, a far bass drum; never a drum kit, hi-hat or clap); colour (bells, mark tree,
   a cymbal's swell) at phrase heads.
3. **Registers** (levels.json says how loud each third of an instrument's range is): the horn sings A3 to F5 and
   grows loud above E4 (its top third +8 dB); the flute and the recorders are weak in their lowest fifth (-9 to
   -15 dB): a tune in a flute's low octave stays under everything, which is a choice, not an accident; the harp's
   low octave is soft (-12 dB) and muddies the middle: keep its ostinato above C3 in a thin texture.
4. **Dynamics** build by adding parts, not by fading; a section holds its level; a summation is at most about 6 dB
   over the statement before it (Brower's no sudden loud sounds).
5. **The ambient middle** (a piece's second part, the queue) is sketch C's texture, which the owner liked "for its
   relaxing atmosphere": a harp turning high (above D4), the held low D, a rubbed glass's long note, a far bell at
   a section's head, and the call handed from flute to horn to violins, each statement in its own bar, left open on
   the second or the ninth. Nothing builds there; the ambience bed rises under it.

## Mix and master

1. **One hall, sized to the piece**: RT60 about 1.7 s for a near band, 2.6 s for the orchestra, 3.2 s for the
   flats at their widest (Bush's large reverbs for distance). Far things wetter (bells 0.6 to 0.85 sent), the tune
   drier (0.3 to 0.45).
2. **Seating**: violins left, violas left of centre, celli right of centre, contrabass right; horns left of centre;
   the harp right; the band spread a little in front; the tune in the middle or near it. No ping-pong.
3. **Balance by role** against the tune while each plays (check.py's stem lines, from `render.py --stems`):
   counter -1 to -9 dB, harmony -4 to -16, bass -1 to -12, drone -5 to -18, ostinato -3 to -14, percussion -3 to
   -16, colour -5 to -20; the tune's statements within 4 dB of each other. Nothing covers the tune.
4. **Loudness.** A music master at -20 LUFS integrated (+/- 1), its true peak at most -1 dBTP, its loudness range 3
   to 14 LU; the ambience bed at -28 LUFS; UI cues by peak, each at its own level (cues.json). Sony's ASWG asks a
   home console title for about -23 LUFS (+/- 2) and a handheld for -18, measured over the whole game
   (Garry Taylor, Designing Sound, 2012,
   <https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/>):
   a browser and desktop game's menu, music over ambience and cues, sits between them; the Music bus trims it.
5. **Bands and air.** No target yet: round 1's sketches measured about 5-20% below 120 Hz, 25-60% from 120 to
   500, 25-55% from 500 to 2000 and 1-4% from 2 to 6 kHz, dull. The air comes from the writing and the room before
   any filter: the violins (25-30% of their energy above 2 kHz) and the flute in its upper register, strings in
   their upper velocity layer at a lower gain, the hall's tail and early reflections less damped (`hall_air`,
   `early`), a glockenspiel's or hand chimes' glint at a phrase head; then a small shelf from 3 kHz (`Part.air`, a
   few dB) on strings and harp. VSCO's harp and horn keep almost nothing above 2 kHz: no shelf gives them air. The
   check prints the mix's air as 2-6 kHz against 500-2000 Hz, in dB. Set the targets from a reference the owner
   hands over (`check.py --ref FILE`), as Cyberworld's came from his recording of "Surge of Power!".
6. **Level the library first.** `levels.json` brings every instrument's median note to one level
   (`render.py --calibrate`), so a part's `gain_db` is a mix decision; VSCO's contrabass sits 10 dB under its horn
   and its glockenspiel 24 dB under, as recorded.

## Discipline (Cyberworld's, kept)

The owner on a Cyberworld sketch whose numbers matched and whose writing did not: "all over the place". So:

1. One idea at a time: an eight-bar sketch has an opening, one statement, its answer or its handing-on, and an end.
2. Only the tune moves freely; the ostinato keeps one figure a chord, the bass its roots on the strong beats, the
   drum one pattern a section and a fill only into the next.
3. Each part's motion stays near what its role does: the check's tune numbers and the balance by role.
4. The palette first (palette.py), and a new instrument only for a reason written beside it.
5. One kit: frame drum, timpani, bells, a swell. A sound one section has stays there.
6. Wide stereo for the hall, the strings' seating and the harp; no part thrown from side to side.

## What does not carry over from Cyberworld

The Game Boy Advance's sound (MP2K, 8-bit samples at 10512 Hz, squares and the wave channel), a source song read
from a ROM, Battle Network's busy battle themes (two chords a bar, syncopated kicks, 32nd-note arpeggios, 7 dB of
punch), chord samples recoloured by the bass and hard ping-pong pans. What carries over is the loop: rules read from
the references, sketches for the owner's ear, a check by numbers and pictures, his word before it ships.

## Builders' colours (after v1, *ours*)

Brower's distinct devices and colours for each faction become each Builder's instrument, for her own page and her
own stinger, never the hub's: Tamsin Wick (Wickhollow, a harvest valley) the fiddle; Edda Greyplume (Fogholm, cliff
isles over a fog-sea) the alto recorder and an ocarina; Ottilie Brass (Brackwater's dikes and storm bells) hand
chimes and tubular bells; Sefa Amberwell (Thousandwell, a red-rock city of cisterns) the psaltery and the frame
drum. Each colours the call; none changes it.

## Checks before the owner listens

- `render.py`: every note finds a sample (a note outside an instrument's range is silence, never an error).
- `check.py` (written beside each render): every rule met, or each `MISS` explained in the gate report; the stem
  lines (with `--stems`) say no part covers the tune.
- The spectrogram (`NAME.spectrum.png`): no seam, no click, no part missing where the score has it, the cymbal's or
  bell's crest on its downbeat; the roll (`NAME.roll.png`): the call's returns, the tune's contour, the bass in its
  octave.
- You cannot hear it: say so, and ask the owner to listen. A green check is the agent's own, never his approval.
