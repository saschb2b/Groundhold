"""Sketch C for the Causeway's theme, "Low water": eight bars for the owner's ear, not a piece.

The sparse take, in the manner of the zone music Hayes and Bush describe for World of Warcraft (music_rules.md): a
few instruments state a theme, it builds a little, the melody passes to another instrument, and it is left
unresolved; large reverbs for distance. The Causeway at low water in daylight: D Mixolydian (major, its C natural
for the open road), 66 a minute, a long hall, the contrabass holding D under everything like the horizon.

- Bars 1-2, the flats: a harp turning slowly, a rubbed glass's D high above, a far bell once.
- Bars 3-4, the call: a flute plays the call (A, D, E), then F sharp falling to C over C: the Mixolydian's bVII.
- Bars 5-6, handed on: the horn takes the call a fourth up over G (and the bell again, further), the celli begin
  to move, voices hum under it, and the line comes down to E over A suspended.
- Bars 7-8, the ebb: the violins take the call high over C and G/B, and turn it over, down to E over C with D
  under it: the ninth left hanging, the flats going on.
"""

import score as sc
from pieces.causeway import arp, call

BARS = 8


def score():
    s = sc.Score(title='Causeway sketch C, "Low water"', bpm=66, meter=(4, 4), bars=BARS, tonic='D',
                 mode='mixolydian', tail=5.5, kind='sketch', loudness=-20.0, hall_seconds=3.2,
                 chords={0: ('Dsus2',), 1: ('C/D',), 2: ('D',), 3: ('C',), 4: ('G/D',), 5: ('Em7', 'Asus4'),
                         6: ('C', 'G/B'), 7: ('Cadd9/D',)},
                 sections=[(0, 'the flats'), (2, 'the call'), (4, 'handed on'), (6, 'the ebb')])
    b = s.bar

    # the horizon: the contrabass's D under everything, bowed again each bar
    basses = s.part('basses', 'basses', role='drone', pan=0.4, hall=0.45, gain_db=-5, hp=30, early_ms=50,
                    dyn=[(b(0), -12), (b(1), -2), (b(6), 0), (b(7, 2), -3)])
    for bar in range(BARS):
        basses.play(b(bar), 4.05 if bar < BARS - 1 else 5, 'D2', 70)

    # the harp, slowly, wet
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.55, gain_db=-10, humanize=(5, 5))
    figures = {
        # (high, above the strings, where the flats' light is: the harp's low octave only muds the middle)
        0: 'D4 A4 E5 A5 D6 A5 E5 A4', 1: 'D4 G4 C5 E5 G5 E5 C5 G4', 2: 'D4 A4 D5 F#5 A5 F#5 D5 A4',
        3: 'C4 G4 C5 E5 G5 E5 C5 G4', 4: 'D4 G4 B4 D5 G5 D5 B4 G4', 5: 'E4 B4 D5 G5 A3 E4 A4 D5',
        6: 'C4 G4 C5 E5 B3 G4 B4 D5',
    }
    for bar, keys in figures.items():
        arp(harp, b(bar), keys, 0.5, vel=56, ring=1.5, accent=8)
    harp.chord(b(7), 5, ['D3', 'G3', 'C4', 'D4', 'E4', 'G4', 'C5', 'E5'], 60, roll=0.09)

    # a rubbed glass: D, then A, far above, swelling and falling away
    glass = s.part('glass', 'wine_glass', role='drone', pan=-0.3, hall=0.6, gain_db=-12,
                   dyn=[(b(0), -12), (b(1), 0), (b(3, 2), -4), (b(4), -2), (b(5), 0), (b(7), -6)])
    glass.play(b(0), 16, 'D5', 70).play(b(4), 16.5, 'A5', 70)

    # a far bell: once at the start, once when the horn takes the call; far, so without its strike's thud
    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-9, hp=160, lp=3200)
    bell.play(b(0), 2, 'D4', 70).play(b(4), 2, 'A4', 58)

    # the call: the flute, then the horn, then the violins
    flute = s.part('flute', 'flute', role='lead', pan=-0.15, hall=0.45, gain_db=0, early_ms=30, humanize=(6, 3),
                   dyn=[(b(2), -2), (b(2, 3), 0), (b(3, 2), -1)])
    flute.line(b(2), call('A4'), vel=78)
    flute.line(b(3), [(1.5, 'F#5', 84), (0.5, 'E5', 76), (1, 'D5', 74), (1, 'C5', 72)])
    horn = s.part('horn', 'horn', role='lead', pan=-0.25, hall=0.5, gain_db=-6, early_ms=30, humanize=(6, 3),
                  dyn=[(b(4), -2), (b(4, 2), 0), (b(5, 2), -2)])
    horn.line(b(4), call('D4'), vel=58)
    horn.line(b(5), [(1, 'B4', 60), (0.5, 'A4', 56), (0.5, 'G4', 54), (2, 'E4', 54)])
    violins = s.part('violins', 'violins', role='lead', pan=-0.45, hall=0.45, gain_db=0, early_ms=50,
                     humanize=(6, 3), dyn=[(b(6), -3), (b(6, 2), 0), (b(7), 0), (b(7, 2), -3), (b(8), -9)])
    violins.line(b(6), call('E5'), vel=80)
    violins.line(b(7), [(1.5, 'A5', 80), (0.5, 'G5', 74), (3.5, 'E5', 70)])

    # the middle: violas in two parts under the flute and the violins; voices under the horn
    violas = s.part('violas', 'violas', role='harmony', pan=-0.05, hall=0.45, gain_db=-9, early_ms=40,
                    dyn=[(b(2), -4), (b(2, 2), 0)])
    for at, length, keys in [(b(2), 4, ('F#4', 'A4')), (b(3), 4, ('E4', 'G4')),
                             (b(6), 2, ('E4', 'G4')), (b(6, 2), 2, ('D4', 'G4')), (b(7), 5, ('E4', 'G4'))]:
        violas.chord(at, length, keys, 60)
    voices = s.part('voices', 'voices', role='harmony', pan=0.1, hall=0.55, gain_db=-10,
                    dyn=[(b(4), -8), (b(4, 2), 0), (b(5, 3), -3), (b(6), -12)])
    for at, length, keys in [(b(4), 4, ('B3', 'D4', 'G4')), (b(5), 2, ('B3', 'D4', 'G4')),
                             (b(5, 2), 2, ('A3', 'D4', 'E4'))]:
        voices.chord(at, length, keys, 56)

    # the celli begin to move when the horn takes the call
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.45, gain_db=-5, hp=45, early_ms=40, humanize=(5, 3))
    celli.line(b(4), [(2, 'B2', 62), (2, 'D3', 62), (2, 'E3', 64), (2, 'A2', 62), (2, 'C3', 64), (2, 'B2', 62),
                      (5, 'C3', 60)])
    return s
