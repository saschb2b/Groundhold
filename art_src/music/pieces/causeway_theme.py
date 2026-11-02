"""The Causeway, the hub's theme: sketch E grown into the piece (the owner, 2 November 2026: "Grow E").

A seamless loop of 44 bars in D at 80 (a bar 3 s, 90 frames at 30 fps; 2:12), in Bush's three parts as
music_rules.md gives them: a theme to build on, a long ambient middle, a strong summation; its end, the horn's
quiet echo and the flats, runs into its start. It keeps the owner's verdicts (lessons.md): A's orchestra and
A's tune are the theme, C's texture is the middle, no band and no jig; and round 2's air (the harp high, the
strings in their upper layer with a 3 dB shelf from 3 kHz, a soft high violin tremolo over the flats, a
glockenspiel's glint, a brighter hall). A's tune and C's harp figures are `pieces/causeway.py`'s, the same notes
the sketches played.

I, the theme (0:00-0:42)
- Bars 1-4, the flats: the harp turning high, the contrabass's D, a rubbed glass's D, the violins' tremolo very
  soft and high, a far bell: Dsus2 C/D G/D Dsus2.
- Bars 5-6, the call: the flute plays it (A, D, E) and turns down to C over C.
- Bars 7-10, the tune: the violins take A's four bars, calm (74), the horn's counter under them, the violas, the
  celli and the contrabass on the roots: Dm | Bbmaj7 C | F G | C Asus4.
- Bars 11-14, handed on: the horn takes the tune an octave down, its rhythm turned a little (the answer long-short,
  the last bar falling to E), the violins over it in long notes as a descant.
II, the ambient middle (0:42-1:42), C's texture over the held low D, nothing building, the call handed on and
left open each time
- Bars 15-18: the half close opens onto D major; a far bell and a glint; the flute's call, turned up to G and down
  to E over C on the D pedal; two bars of the harp and the glass alone.
- Bars 19-22: the horn's call a fourth up over G, falling to E over A suspended, voices humming under it, the celli
  beginning to move; C, D.
- Bars 23-26: the violins' call high over C and G/B, turned over (A, G, E) and left on E over C with D under it;
  two bars of breath.
- Bars 27-30: the flute's call over D minor with the horn's A under it, down to C over Bbmaj7, the far bell's A;
  two bars of breath.
- Bars 31-34, the gathering: the pedal lets go, the roots walk Bb C D A, the violins rise D, E, A and fall to E,
  a timpani roll on A in the last two beats.
III, the summation (1:42-2:12)
- Bars 35-38, the tune returns: A's four bars, the violins at full voice (82) with the horns an octave under.
- Bars 39-40, the close: the call a last time over the heroic Bb C onto D major, its F sharp held on top, the
  timpani on the roots, a cymbal's swell into it, a glint on each downbeat, the harp rolled.
- Bar 41, the echo: the horn alone plays the call quietly over the contrabass's D and the celli's A and leaves its
  E hanging; the glass and the tremolo come back.
- Bars 42-44, the flats again: C/D G/D C/D, which turn to bar 1's Dsus2 as the loop goes round.

Placed for the front end (F4) as SKILL.md, Placing the hub's music, says: the Music bus, the whole file looping.
"""

import score as sc
from pieces.causeway import call, flats, theme, THEME_CHORDS

BARS = 44
UNDER_TUNE = set(range(6, 14)) | set(range(34, 39))     # where the harp rings less, under a tune


def score():
    chords = {0: ('Dsus2',), 1: ('C/D',), 2: ('G/D',), 3: ('Dsus2',), 4: ('D',), 5: ('C',)}
    for start in (6, 10, 34):
        chords.update({start + i: c for i, c in enumerate(THEME_CHORDS)})
    chords.update({14: ('D',), 15: ('C/D',), 16: ('G/D',), 17: ('D',),
                   18: ('G/D',), 19: ('Em7', 'Asus4'), 20: ('C',), 21: ('D',),
                   22: ('C', 'G/B'), 23: ('Cadd9/D',), 24: ('D',), 25: ('C/D',),
                   26: ('Dm',), 27: ('Bbmaj7',), 28: ('C/D',), 29: ('Dsus2',),
                   30: ('Bbmaj7',), 31: ('C',), 32: ('Dsus2',), 33: ('Asus4',),
                   38: ('Bb', 'C'), 39: ('D',), 40: ('Dsus2',), 41: ('C/D',), 42: ('G/D',), 43: ('C/D',)})
    s = sc.Score(title='The Causeway, the hub\'s theme', bpm=80, meter=(4, 4), bars=BARS, tonic='D', mode='dorian',
                 borrowed=('Bb', 'F#'), tail=6.0, kind='loop', loudness=-20.0, hall_seconds=2.8, hall_air=0.8,
                 early=1.3, chords=chords,
                 sections=[(0, 'the flats'), (4, 'the call'), (6, 'the tune'), (10, 'handed on'),
                           (14, 'middle: flute'), (18, 'middle: horn'), (22, 'middle: violins'),
                           (26, 'middle: together'), (30, 'the gathering'), (34, 'the tune returns'),
                           (38, 'summation'), (40, 'the echo'), (41, 'the flats again')])
    b = s.bar

    # ---- the floor and the water: the whole loop ------------------------------------------------------------
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.5, gain_db=-9, air=3, humanize=(5, 5))
    for bar in range(BARS):
        if bar == 39:
            continue
        under = bar in UNDER_TUNE
        flats(harp, b(bar), chords[bar], vel=60 if under else 56 if bar < 14 or bar > 39 else 58,
              ring=1.0 if under else 1.5)
    harp.chord(b(39), 4, ['D3', 'A3', 'D4', 'F#4', 'A4', 'D5', 'F#5', 'A5'], 74, roll=0.06)

    basses = s.part('basses', 'basses', role='bass', pan=0.45, hall=0.4, gain_db=-6, hp=30, early_ms=50)
    for bar in list(range(0, 6)) + list(range(14, 30)) + list(range(40, BARS)):
        basses.play(b(bar), 4, 'D2', 66)                 # the held low D, bowed again each bar
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.4, gain_db=-4, hp=45, air=2, early_ms=40,
                   humanize=(5, 3))

    glass = s.part('glass', 'wine_glass', role='drone', pan=-0.3, hall=0.6, gain_db=-10, air=2)
    shimmer = s.part('shimmer', 'violins_trem', role='drone', pan=-0.55, hall=0.6, gain_db=-13, air=3, early_ms=50)
    for start, end, high in ((0, 6, ()), (14, 30, (18, 19, 20, 21, 26, 27, 28, 29)), (40, BARS, ())):
        for bar in range(start, end, 2):
            glass.play(b(bar), 8, 'A5' if bar in high else 'D5', 70)
            shimmer.chord(b(bar), 8, ['A5', 'D6'], 58)

    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-9, hp=160, lp=3200)
    bell.play(b(0), 2, 'D4', 66).play(b(14), 2, 'D4', 62).play(b(26), 2, 'A4', 54)
    glint = s.part('glint', 'glockenspiel', role='colour', pan=0.35, hall=0.6, gain_db=-14)
    glint.play(b(14), 1, 'D6', 54).play(b(22), 1, 'E6', 50).play(b(38), 1, 'D6', 58).play(b(39), 1, 'F#6', 62)

    # ---- I: the theme ---------------------------------------------------------------------------------------
    flute = s.part('flute', 'flute', role='lead', pan=-0.15, hall=0.45, gain_db=5, air=2, early_ms=30,
                   humanize=(6, 3))
    flute.line(b(4), call('A4'), vel=80)
    flute.line(b(5), [(1, 'F#5', 84), (1, 'E5', 76), (1, 'D5', 74), (1, 'C5', 72)])

    tune = s.part('tune', 'violins', role='lead', pan=-0.45, hall=0.4, air=3, early_ms=50, humanize=(6, 3),
                  dyn=[(b(6), -2), (b(8), 0), (b(14), 0), (b(30), -8), (b(32), -3), (b(34), 0), (b(38), 1)])
    counter = s.part('counter', 'horn', role='counter', pan=-0.15, hall=0.45, gain_db=-3, early_ms=30,
                     humanize=(6, 3))
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.4, gain_db=-9, air=3, early_ms=40,
                    humanize=(5, 3))
    theme(b(6), tune, counter, violas, celli, basses, vel=74)

    # handed on: the horn takes the tune an octave down, its rhythm turned; the violins' descant over it
    horn = s.part('horn', 'horn', role='lead', pan=-0.2, hall=0.45, gain_db=-3, early_ms=30, humanize=(6, 3),
                  dyn=[(b(10), 0), (b(12), -3)])
    horn.line(b(10), call('A3'), vel=68)
    horn.line(b(11), [(1.5, 'F4', 70), (0.5, 'E4', 66), (1, 'D4', 66), (1, 'C4', 66)])
    horn.line(b(12), [(1, 'D4', 70), (1, 'G4', 70), (2, 'A4', 70)])          # the call, its rhythm turned
    horn.line(b(13), [(1.5, 'G4', 68), (0.5, 'F4', 64), (2, 'E4', 62)])
    descant = s.part('descant', 'violins', role='counter', pan=-0.5, hall=0.45, gain_db=-5, air=3, early_ms=50,
                     humanize=(6, 3))
    descant.line(b(10), [(4, 'A5', 70), (2, 'D5', 68), (2, 'E5', 70), (2, 'C5', 70), (2, 'D5', 72),
                         (2, 'E5', 72), (2, 'D5', 70)])
    # (open under the horn's E: the third stays in the harp's and the descant's hands, not a semitone over it)
    for beat, length, keys in ((0, 4, ('D4', 'A4')), (4, 2, ('D4', 'F4')), (6, 2, ('E4', 'G4')),
                               (8, 2, ('C4', 'A4')), (10, 2, ('D4', 'B4')), (12, 2, ('E4', 'G4')),
                               (14, 2, ('D4', 'A4'))):
        violas.chord(b(10) + beat, length, keys, 64)
    theme_roots = ((0, 4, 'D3'), (4, 2, 'Bb2'), (6, 2, 'C3'), (8, 2, 'F2'), (10, 2, 'G2'), (12, 2, 'C3'),
                   (14, 2, 'A2'))
    for beat, length, k in theme_roots:
        celli.play(b(10) + beat, length, k, 68)
        basses.play(b(10) + beat, length, sc.key(k) - 12, 62)

    # ---- II: the ambient middle -----------------------------------------------------------------------------
    # the call handed on at a distance (role 'distant': the tune, placed further back and wetter than the theme's
    # statements), each time in a rhythm of its own
    flute_far = s.part('flute far', 'flute', role='distant', pan=-0.2, hall=0.55, gain_db=2, air=2, early_ms=30,
                       humanize=(6, 3))
    horn_far = s.part('horn far', 'horn', role='distant', pan=-0.3, hall=0.6, gain_db=-10, early_ms=30,
                      humanize=(6, 3))
    violins_far = s.part('violins far', 'violins', role='distant', pan=-0.5, hall=0.55, gain_db=-3, air=3,
                         early_ms=50, humanize=(6, 3))
    flute_far.line(b(14), call('A4', (2, 1, 1)), vel=78)
    flute_far.line(b(15), [(1, 'F#5', 82), (0.5, 'G5', 76), (0.5, 'F#5', 74), (2, 'E5', 72)])
    horn_far.line(b(18), call('D4', (1, 1, 2)), vel=56)
    horn_far.line(b(19), [(1, 'B4', 58), (0.5, 'A4', 54), (0.5, 'G4', 52), (2, 'E4', 52)])
    celli.line(b(18), [(2, 'B2', 62), (2, 'D3', 62), (2, 'E3', 64), (2, 'A2', 62), (4, 'C3', 60), (4, 'D3', 58),
                       (2, 'C3', 60), (2, 'B2', 60), (4, 'C3', 58)])
    voices = s.part('voices', 'voices', role='harmony', pan=0.1, hall=0.55, gain_db=-9,
                    dyn=[(b(18), -8), (b(18, 2), 0), (b(20, 2), 0), (b(21), -12)])
    for at, length, keys in ((b(18), 4, ('B3', 'D4', 'G4')), (b(19), 2, ('B3', 'D4', 'G4')),
                             (b(19, 2), 2, ('A3', 'D4', 'E4')), (b(20), 4, ('G3', 'C4', 'E4'))):
        voices.chord(at, length, keys, 54)
    violins_far.line(b(22), call('E5', (2.5, 0.5, 1)), vel=74)
    violins_far.line(b(23), [(2, 'A5', 74), (1, 'G5', 68), (5, 'E5', 64)])  # the E held over the breath
    flute_far.line(b(26), call('A4', (2, 1, 1)), vel=74)
    flute_far.line(b(27), [(2, 'D5', 74), (2, 'C5', 70)])
    counter.play(b(26), 8, 'A3', 56)

    # the gathering: the pedal lets go, the roots walk, the violins rise, a roll into the return
    tune.line(b(30), [(4, 'D5', 70), (3, 'E5', 74), (1, 'G5', 74), (4, 'A5', 78), (2, 'G5', 76), (2, 'E5', 74)])
    for i, (keys, root) in enumerate(((('D4', 'F4'), 'Bb2'), (('E4', 'G4'), 'C3'), (('D4', 'A4'), 'D3'),
                                      (('D4', 'E4'), 'A2'))):
        violas.chord(b(30 + i), 4, keys, 66 + 2 * i)
        celli.play(b(30 + i), 4, root, 66 + 2 * i)
        basses.play(b(30 + i), 4, sc.key(root) - 12, 62 + 2 * i)
    roll = s.part('roll', 'timpani_roll', role='perc', pan=0.15, hall=0.45, gain_db=0,
                  dyn=[(b(33, 2), -12), (b(34), 0)])
    roll.play(b(33, 2), 2, 'A2', 84)

    # ---- III: the summation ---------------------------------------------------------------------------------
    horns = s.part('horns', 'horn', role='lead', doubles='tune', pan=-0.25, hall=0.45, gain_db=-9, early_ms=30,
                   humanize=(6, 3))
    theme(b(34), tune, None, violas, celli, basses, vel=82)
    horns.line(b(34), call('A3'), vel=80)
    horns.line(b(35), [(1, 'F4'), (0.5, 'E4'), (0.5, 'D4'), (1, 'C4'), (1, 'D4')], vel=82)
    horns.line(b(36), call('D4'), vel=86)
    horns.line(b(37), [(1, 'G4'), (0.5, 'F4'), (0.5, 'E4'), (1, 'D4'), (1, 'E4')], vel=86)

    tune.line(b(38), [(1.5, 'A4', 88), (0.5, 'D5', 88), (1, 'E5', 90), (1, 'G5', 92)])
    tune.play(b(39), 4, 'F#5', 94)
    horns.line(b(38), [(1.5, 'A3', 88), (0.5, 'D4', 88), (1, 'E4', 90), (1, 'G4', 92)])
    horns.play(b(39), 4, 'F#4', 94)
    for at, length, keys, vel in ((b(38), 2, ('D4', 'F4'), 78), (b(38, 2), 2, ('E4', 'G4'), 80),
                                  (b(39), 4, ('D4', 'A4'), 82)):
        violas.chord(at, length, keys, vel)
    for at, length, k in ((b(38), 2, 'Bb2'), (b(38, 2), 2, 'C3'), (b(39), 4, 'D3')):
        celli.play(at, length, k, 82)
        basses.play(at, length, sc.key(k) - 12, 76)
    timp = s.part('timpani', 'timpani', role='perc', pan=0.15, hall=0.45, gain_db=-7)
    timp.play(b(38), 1, 'Bb2', 72).play(b(38, 2), 1, 'C3', 76).play(b(39), 2, 'D3', 88)
    cymbal = s.part('cymbal', 'sus_cymbal', role='colour', hall=0.5, gain_db=-17)
    cymbal.play(b(38) - 1.5, 1.5, 64, 86)

    # the echo, then the flats again into bar 1
    echo = s.part('echo', 'horn', role='lead', pan=-0.2, hall=0.5, gain_db=2, early_ms=30, humanize=(6, 3))
    echo.line(b(40), call('A3', (1.5, 0.5, 3.0)), vel=64)
    celli.play(b(40), 5, 'A2', 62)
    return s
