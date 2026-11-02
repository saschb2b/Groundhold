"""Sketch E for the Causeway's theme, round 2, "The flats, then the call": for the owner's ear, not a piece.

From the owner's ear on round 1 (2 November 2026, lessons.md): "A sounds the best. also really like C for its
relaxing atmosphere." This take is a calmer A: it opens in C's flats and builds to A's call and its strong close,
then lets the horn echo the call into the flats again, which is where a hub's loop would turn (music_rules.md: its
last bars left open so the seam is a breath). In D at 80, a bar 3 s (90 frames at 30 fps), eleven bars.

- Bars 1-2, the flats: C's opening, a harp turning high, a rubbed glass's D, the contrabass's D, a far bell.
- Bars 3-4, the call: the flute plays it (A, D, E) and turns down to C over C, as in C.
- Bars 5-8, the tune: the D major of the flats darkens to D minor as the violins take A's four bars, softer than A
  (they start at 74 against A's 82), the horn's counter under them, the violas, the celli and the contrabass
  entering on the roots; the harp stays high.
- Bars 9-10, the summation: A's close, held to about 4 dB over the tune before it (A's was about 5): the call a
  last time on the violins with the horns an octave under, over the heroic Bb C onto D major, its F sharp held on
  top, the timpani soft on the roots, a cymbal's swell into it, a glint of glockenspiel on each downbeat.
- Bar 11, the echo: the D chord dies away; the horn alone plays the call once more, quietly, and leaves its E
  hanging over the contrabass's D and the celli's A, the glass's D back above, the harp turning again: bar 1's
  texture, so the end runs into the start.

Air as in sketch D: the harp high throughout, the strings in their upper velocity layer with a 3 dB shelf from
3 kHz, the flute and the glass with 2, the glockenspiel's glint, the violins' tremolo very soft and high over the
flats, a brighter hall (its tail above 3.5 kHz at 0.8 of its reverb time, against 0.55; its early reflections
1.3).
"""

import score as sc
from pieces.causeway import call, flats, theme, THEME_CHORDS

BARS = 11


def score():
    chords = {0: ('Dsus2',), 1: ('C/D',), 2: ('D',), 3: ('C',)}
    chords.update({4 + i: c for i, c in enumerate(THEME_CHORDS)})
    chords.update({8: ('Bb', 'C'), 9: ('D',), 10: ('Dsus2',)})
    s = sc.Score(title='Causeway sketch E, "The flats, then the call"', bpm=80, meter=(4, 4), bars=BARS, tonic='D',
                 mode='dorian', borrowed=('Bb', 'F#'), tail=5.0, kind='sketch', loudness=-20.0, hall_seconds=2.8,
                 hall_air=0.8, early=1.3, chords=chords,
                 sections=[(0, 'the flats'), (2, 'the call'), (4, 'the tune'), (8, 'summation'), (10, 'the echo')])
    b = s.bar

    # the flats: the harp high, the glass, the contrabass's D, a far bell
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.5, gain_db=-9, air=3, humanize=(5, 5),
                  dyn=[(b(0), 3), (b(3, 3), 3), (b(4), 0), (b(10), 0), (b(10, 1), 3)])
    for bar in range(BARS):
        if bar != 9:
            # (drier under the tune, so a ringing string never rubs its next downbeat; wetter on the flats)
            flats(harp, b(bar), chords[bar], vel=56 if bar in (0, 1, 10) else 60, ring=1.0 if 4 <= bar < 9 else 1.5)
    harp.chord(b(9), 4, ['D3', 'A3', 'D4', 'F#4', 'A4', 'D5', 'F#5', 'A5'], 74, roll=0.06)
    glass = s.part('glass', 'wine_glass', role='drone', pan=-0.3, hall=0.6, gain_db=-10, air=2,
                   dyn=[(b(0), -12), (b(1), 0), (b(3, 2), -6), (b(10), -10), (b(10, 2), 0)])
    glass.play(b(0), 16, 'D5', 70).play(b(10), 5, 'D5', 70)
    basses = s.part('basses', 'basses', role='bass', pan=0.45, hall=0.4, gain_db=-6, hp=30, early_ms=50,
                    dyn=[(b(0), -12), (b(1), -2), (b(4), 0)])
    for bar in range(4):
        basses.play(b(bar), 4, 'D2', 66)
    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-9, hp=160, lp=3200)
    bell.play(b(0), 2, 'D4', 66)
    # air over the flats: the violins' tremolo, very soft and high, the light on the water
    shimmer = s.part('shimmer', 'violins_trem', role='drone', pan=-0.55, hall=0.6, gain_db=-13, air=3, early_ms=50,
                     dyn=[(b(0), -12), (b(1), 0), (b(3, 2), -4), (b(4), -12), (b(10), -12), (b(10, 3), -2)])
    shimmer.chord(b(0), 16, ['A5', 'D6'], 60)
    shimmer.chord(b(10), 5, ['A5', 'D6'], 60)

    # bars 3-4: the flute's call
    flute = s.part('flute', 'flute', role='lead', pan=-0.15, hall=0.45, gain_db=5, air=2, early_ms=30,
                   humanize=(6, 3),
                   dyn=[(b(2), -2), (b(2, 3), 0), (b(3, 2), -1)])
    flute.line(b(2), call('A4'), vel=80)
    flute.line(b(3), [(1, 'F#5', 84), (1, 'E5', 76), (1, 'D5', 74), (1, 'C5', 72)])

    # bars 5-8: A's theme, calmer
    tune = s.part('tune', 'violins', role='lead', pan=-0.45, hall=0.4, air=3, early_ms=50, humanize=(6, 3),
                  dyn=[(b(4), -2), (b(6), 0), (b(8), 1)])
    counter = s.part('counter', 'horn', role='counter', pan=-0.15, hall=0.45, gain_db=-3, early_ms=30,
                     humanize=(6, 3))
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.4, gain_db=-9, air=3, early_ms=40,
                    humanize=(5, 3))
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.4, gain_db=-4, hp=45, air=2, early_ms=40,
                   humanize=(5, 3))
    theme(b(4), tune, counter, violas, celli, basses, vel=74)

    # bars 9-10: the summation
    tune.line(b(8), [(1.5, 'A4', 86), (0.5, 'D5', 86), (1, 'E5', 88), (1, 'G5', 90)])
    tune.play(b(9), 4.0, 'F#5', 92)
    horns = s.part('horns', 'horn', role='lead', doubles='tune', pan=-0.25, hall=0.45, gain_db=-9, early_ms=30,
                   humanize=(6, 3))
    horns.line(b(8), [(1.5, 'A3', 86), (0.5, 'D4', 86), (1, 'E4', 88), (1, 'G4', 90)])
    horns.play(b(9), 4.0, 'F#4', 92)
    for at, length, keys, vel in [(b(8), 2, ('D4', 'F4'), 76), (b(8, 2), 2, ('E4', 'G4'), 78),
                                  (b(9), 4.0, ('D4', 'A4'), 80)]:
        violas.chord(at, length, keys, vel)
    for at, length, k in [(b(8), 2, 'Bb2'), (b(8, 2), 2, 'C3'), (b(9), 4.0, 'D3')]:
        celli.play(at, length, k, 80)
        basses.play(at, length, sc.key(k) - 12, 74)
    timp = s.part('timpani', 'timpani', role='perc', pan=0.15, hall=0.45, gain_db=-7)
    timp.play(b(8), 1, 'Bb2', 70).play(b(8, 2), 1, 'C3', 74).play(b(9), 2, 'D3', 86)
    cymbal = s.part('cymbal', 'sus_cymbal', role='colour', hall=0.5, gain_db=-17)
    cymbal.play(b(8) - 1.5, 1.5, 64, 86)
    glint = s.part('glint', 'glockenspiel', role='colour', pan=0.35, hall=0.6, gain_db=-14)
    glint.play(b(8), 1, 'D6', 56).play(b(9), 1, 'F#6', 60)

    # bar 11: the echo, the horn alone over bar 1's floor
    echo = s.part('echo', 'horn', role='lead', pan=-0.2, hall=0.5, gain_db=1, early_ms=30, humanize=(6, 3))
    echo.line(b(10), call('A3', (1.5, 0.5, 3.0)), vel=64)
    basses.play(b(10), 5, 'D2', 64)
    celli.play(b(10), 5, 'A2', 62)
    return s
