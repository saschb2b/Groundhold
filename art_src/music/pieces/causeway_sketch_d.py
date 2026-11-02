"""Sketch D for the Causeway's theme, round 2, "The call, then the flats": for the owner's ear, not a piece.

From the owner's ear on round 1 (2 November 2026, lessons.md): "A sounds the best. also really like C for its
relaxing atmosphere." This take plays A's theme first and lets it flow into C's flats, which is the order of Bush's
three parts (a theme, then the ambient middle; music_rules.md): the first half of the hub's piece, cut short. In D
at 80, a bar 3 s (90 frames at 30 fps), eleven bars.

- Bars 1-2, the call: the horn alone, as in A, over the contrabass's D and the celli's A held, but with C's harp
  turning high over them and a rubbed glass's D above: the flats are there from the first bar. The horn's answer
  falls by steps (F, E, D) over C on the D pedal.
- Bars 3-6, the tune: A's four bars (`pieces/causeway.py`, THEME), the violins with the horn's counter under them,
  the violas, the celli and the contrabass on the roots; the harp stays high (C's register, not A's low one).
- Bars 7-11, the flats: the tune's half close on A suspended opens onto D major (the Mixolydian's daylight, its F
  sharp) and the orchestra thins to C's texture: the harp, the contrabass's D re-bowed each bar, the glass, a far
  bell and a glint of glockenspiel at the head. The flute takes the call (A, D, E) and turns down to C over C; the
  horn takes it a fourth up over G with voices humming under, the celli starting to move; the violins, high, turn
  it over (A, G, E) and leave the E hanging over C with D under it.

Air (round 1's mixes were dark, 1 to 4% of their energy from 2 to 6 kHz): the harp high throughout, the strings in
their upper velocity layer with a 3 dB shelf from 3 kHz, the flute and the glass with 2, a glockenspiel's glint,
the violins' tremolo very soft and high over the flats, and a brighter hall (its tail above 3.5 kHz at 0.8 of its
reverb time, against 0.55; its early reflections 1.3).
"""

import score as sc
from pieces.causeway import call, flats, theme, THEME_CHORDS

BARS = 11


def score():
    chords = {0: ('Dsus2',), 1: ('C/D',)}
    chords.update({2 + i: c for i, c in enumerate(THEME_CHORDS)})
    chords.update({6: ('D',), 7: ('C/D',), 8: ('G/D',), 9: ('Em7', 'Asus4'), 10: ('Cadd9/D',)})
    s = sc.Score(title='Causeway sketch D, "The call, then the flats"', bpm=80, meter=(4, 4), bars=BARS, tonic='D',
                 mode='dorian', borrowed=('Bb', 'F#'), tail=5.5, kind='sketch', loudness=-20.0, hall_seconds=2.8,
                 hall_air=0.8, early=1.3, chords=chords,
                 sections=[(0, 'the call'), (2, 'the tune'), (6, 'the flats'), (8, 'handed on')])
    b = s.bar

    # the horn: the call alone, its answer; later the call again in the flats
    horn = s.part('horn', 'horn', role='lead', pan=-0.2, hall=0.45, gain_db=-3, early_ms=30, humanize=(6, 3),
                  dyn=[(b(0), -3), (b(0, 2), 0)])
    horn.line(b(0), call('A3'), vel=82)
    horn.line(b(1), [(1, 'F4', 78), (1, 'E4', 74), (2, 'D4', 70)])
    horn.line(b(8), call('D4'), vel=54)
    horn.line(b(9), [(1, 'B4', 56), (0.5, 'A4', 52), (0.5, 'G4', 50), (2, 'E4', 50)])

    # the floor: the contrabass's D and the celli's A held under the call; the roots under the tune; the D re-bowed
    # each bar on the flats
    basses = s.part('basses', 'basses', role='bass', pan=0.45, hall=0.4, gain_db=-6, hp=30, early_ms=50,
                    dyn=[(b(0), -9), (b(1), 0)])
    basses.play(b(0), 8, 'D2', 66)
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.4, gain_db=-3, hp=45, air=2, early_ms=40,
                   humanize=(5, 3), dyn=[(b(0), -9), (b(1), -2), (b(2), 0)])
    celli.play(b(0), 8, 'A2', 70)
    for bar in range(6, BARS):
        basses.play(b(bar), 4, 'D2', 68)
    celli.line(b(8), [(2, 'B2', 64), (2, 'D3', 64), (2, 'E3', 66), (2, 'A2', 64), (5, 'C3', 62)])

    # the harp, high, the whole sketch: C's figures over every chord
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.5, gain_db=-9, air=3, humanize=(5, 5))
    for bar in range(BARS - 1):
        # (drier under the tune, so a ringing string never rubs its next downbeat; wetter on the flats)
        flats(harp, b(bar), chords[bar], vel=60 if 2 <= bar < 6 else 56, ring=1.0 if 2 <= bar < 6 else 1.5)
    harp.chord(b(10), 5, ['D3', 'G3', 'C4', 'D4', 'E4', 'G4', 'C5', 'E5'], 60, roll=0.09)

    # the glass: D over the call, then over the flats, A when the horn takes it
    glass = s.part('glass', 'wine_glass', role='drone', pan=-0.3, hall=0.6, gain_db=-10, air=2,
                   dyn=[(b(0), -12), (b(1), 0), (b(1, 3), -6), (b(6), -10), (b(7), 0), (b(10, 2), -6)])
    glass.play(b(0), 8, 'D5', 70).play(b(6), 8, 'D5', 70).play(b(8), 12.5, 'A5', 70)

    # bars 3-6: A's theme
    tune = s.part('tune', 'violins', role='lead', pan=-0.45, hall=0.4, air=3, early_ms=50, humanize=(6, 3),
                  dyn=[(b(2), -1), (b(4), 0), (b(6), 0), (b(10), -3), (b(10, 3), -6)])
    counter = s.part('counter', 'horn', role='counter', pan=-0.15, hall=0.45, gain_db=-2, early_ms=30,
                     humanize=(6, 3))
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.4, gain_db=-9, air=3, early_ms=40,
                    humanize=(5, 3))
    theme(b(2), tune, counter, violas, celli, basses, vel=80)
    tune.line(b(10), [(1.5, 'A5', 76), (0.5, 'G5', 70), (3.5, 'E5', 66)])

    # bars 7-11: the flats; the flute takes the call, a far bell and a glint mark the arrival, voices hum under the
    # horn's turn
    flute = s.part('flute', 'flute', role='lead', pan=-0.15, hall=0.45, gain_db=2, air=2, early_ms=30,
                   humanize=(6, 3),
                   dyn=[(b(6), -2), (b(6, 3), 0), (b(7, 2), -1)])
    flute.line(b(6), call('A4'), vel=80)
    flute.line(b(7), [(1.5, 'F#5', 84), (0.5, 'E5', 76), (1, 'D5', 74), (1, 'C5', 72)])
    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-9, hp=160, lp=3200)
    bell.play(b(6), 2, 'D4', 66)
    glint = s.part('glint', 'glockenspiel', role='colour', pan=0.35, hall=0.6, gain_db=-14)
    glint.play(b(6), 1, 'D6', 56).play(b(10), 1, 'E6', 50)
    voices = s.part('voices', 'voices', role='harmony', pan=0.1, hall=0.55, gain_db=-9,
                    dyn=[(b(8), -8), (b(8, 2), 0), (b(9, 3), -3), (b(10), -12)])
    for at, length, keys in [(b(8), 4, ('B3', 'D4', 'G4')), (b(9), 2, ('B3', 'D4', 'G4')),
                             (b(9, 2), 2, ('A3', 'D4', 'E4'))]:
        voices.chord(at, length, keys, 56)

    # air over the flats: the violins' tremolo, very soft and high, the light on the water
    shimmer = s.part('shimmer', 'violins_trem', role='drone', pan=-0.55, hall=0.6, gain_db=-13, air=3, early_ms=50,
                     dyn=[(b(6), -12), (b(7), 0), (b(10, 2), -6)])
    shimmer.chord(b(6), 20, ['A5', 'D6'], 60)
    return s
