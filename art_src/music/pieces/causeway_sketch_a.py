"""Sketch A for the Causeway's theme, "The Holdfast's call": eight bars for the owner's ear, not a piece.

The orchestral take, nearest the Warcraft III in-game pieces as their composers describe them (music_rules.md):
fully orchestrated and in Bush's shape in miniature, a theme stated, handed on, and a strong summation, sampled
strings and a horn in a hall. In D at 84, a bar 2.86 s (a bar of whole frames at 30 fps needs 72, 80 or 90 a
minute: a sketch has no cut to meet, a piece will).

- Bars 1-2, the call: a horn alone over the flats' open fifth (the contrabass's D, the celli's A, held) and a harp
  turning over D and A in eighths like water. The call (A, D, E: up a fourth and a step) and its answer falling by
  steps (F, E, D), softer, over C on the D pedal, the Dorian's bVII.
- Bars 3-6, the tune: the violins take the call an octave up, the horn drops to a counter that moves only where the
  tune holds, the violas fill the middle, the celli and basses walk the roots. Dm | Bbmaj7 C | F G | C Asus4: the
  call answered (falling by steps to C), the call again a fourth higher over F and the Dorian's bright IV (G, its B
  natural), then a fall onto the half close, Asus4 (the minor v suspended, never a major V).
- Bars 7-8, the summation: the call a third time, the horns under the violins in octaves, the timpani on the roots,
  a cymbal swelling into it, over the heroic bVI bVII (Bb C) onto D major: the Mixolydian's major I, its F sharp
  held on top, ringing in the hall.

Its numbers are check.py's (.build/music-sketches/causeway_sketch_a.check.txt).
"""

import score as sc
from pieces.causeway import arp, call

BARS = 8


def score():
    s = sc.Score(title='Causeway sketch A, "The Holdfast\'s call"', bpm=84, meter=(4, 4), bars=BARS, tonic='D',
                 mode='dorian', borrowed=('Bb', 'F#'), tail=4.5, kind='sketch', loudness=-20.0, hall_seconds=2.6,
                 chords={0: ('Dsus2',), 1: ('C/D',), 2: ('Dm',), 3: ('Bbmaj7', 'C'), 4: ('F', 'G'),
                         5: ('C', 'Asus4'), 6: ('Bb', 'C'), 7: ('D',)},
                 sections=[(0, 'the call'), (2, 'the tune'), (6, 'summation')])
    b = s.bar

    # bars 1-2: the call, a horn alone; its answer falling by steps, softer
    horn = s.part('call', 'horn', role='lead', pan=-0.2, hall=0.45, early_ms=30, humanize=(6, 3),
                  dyn=[(b(0), -3), (b(0, 2), 0), (b(2), 0)])
    horn.line(b(0), call('A3'), vel=84)
    horn.line(b(1), [(1.0, 'F4', 80), (1.0, 'E4', 76), (2.0, 'D4', 72)])

    # the flats: the contrabass's D and the celli's A held, swelling in
    basses = s.part('basses', 'basses', role='bass', pan=0.45, hall=0.3, gain_db=-6, hp=30, early_ms=50,
                    dyn=[(b(0), -9), (b(1), 0)])
    basses.play(b(0), 8, 'D2', 62)
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.3, gain_db=-3, hp=45, early_ms=40, humanize=(5, 3),
                   dyn=[(b(0), -9), (b(1), -2), (b(2), 0)])
    celli.play(b(0), 8, 'A2', 64)

    # the harp: eighths up and down over the chord, the whole sketch long
    harp = s.part('harp', 'harp', role='ostinato', pan=0.55, hall=0.4, gain_db=-6, humanize=(4, 5))
    figures = {
        0: 'D3 A3 D4 E4 A4 E4 D4 A3', 1: 'D3 G3 C4 E4 G4 E4 C4 G3', 2: 'D3 A3 D4 F4 A4 F4 D4 A3',
        3: 'Bb2 F3 A3 D4 C3 G3 C4 E4', 4: 'F2 C3 F3 A3 G2 D3 G3 B3', 5: 'C3 G3 C4 E4 A2 E3 A3 D4',
        6: 'Bb2 F3 Bb3 D4 C3 G3 C4 E4',
    }
    for bar, keys in figures.items():
        arp(harp, b(bar), keys, 0.5, vel=58 if bar < 2 else 64, ring=1.0, accent=10)
    harp.chord(b(7), 4, ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4', 'F#4', 'A4'], 72, roll=0.06)

    # bars 3-8: the tune on the violins
    tune = s.part('tune', 'violins', role='lead', pan=-0.45, hall=0.35, early_ms=50, humanize=(6, 3),
                  dyn=[(b(2), -2), (b(4), 0), (b(5, 2), 0.5), (b(6), 2)])
    tune.line(b(2), call('A4'), vel=82)
    tune.line(b(3), [(1, 'F5', 86), (0.5, 'E5', 80), (0.5, 'D5', 80), (1, 'C5', 82), (1, 'D5', 84)])
    tune.line(b(4), call('D5'), vel=90)
    tune.line(b(5), [(1, 'G5', 92), (0.5, 'F5', 86), (0.5, 'E5', 84), (1, 'D5', 84), (1, 'E5', 88)])
    tune.line(b(6), [(1.5, 'A4', 92), (0.5, 'D5', 92), (1, 'E5', 94), (1, 'G5', 96)])
    tune.play(b(7), 4.2, 'F#5', 100)

    # the horn's counter: moving only where the tune holds
    counter = s.part('counter', 'horn', role='counter', pan=-0.15, hall=0.45, gain_db=-1, early_ms=30, humanize=(6, 3))
    counter.line(b(2), [(2, 'D4', 62), (1, 'A3', 70), (1, 'D4', 72)])     # the call's D held under the tune's
    counter.line(b(3), [(2, 'D4', 74), (2, 'E4', 74)])
    counter.line(b(4), [(2, 'C4', 76), (1, 'D4', 74), (1, 'B3', 74)])
    counter.line(b(5), [(2, 'C4', 76), (2, 'D4', 78)])

    # the summation: the horns double the tune an octave down
    horns = s.part('horns', 'horn', role='lead', doubles='tune', pan=-0.25, hall=0.45, gain_db=-8, early_ms=30,
                   humanize=(6, 3))
    horns.line(b(6), [(1.5, 'A3', 92), (0.5, 'D4', 92), (1, 'E4', 94), (1, 'G4', 96)])
    horns.play(b(7), 4.2, 'F#4', 100)

    # the violas: the middle, two notes at a time
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.35, gain_db=-8, early_ms=40, humanize=(5, 3))
    for at, length, keys, vel in [(b(2), 4, ('D4', 'F4'), 66),
                                  (b(3), 2, ('D4', 'F4'), 68), (b(3, 2), 2, ('E4', 'G4'), 68),
                                  (b(4), 2, ('C4', 'A4'), 70), (b(4, 2), 2, ('D4', 'B4'), 72),
                                  (b(5), 2, ('E4', 'G4'), 72), (b(5, 2), 2, ('D4', 'A4'), 74),
                                  (b(6), 2, ('D4', 'F4'), 78), (b(6, 2), 2, ('E4', 'G4'), 80),
                                  (b(7), 4.2, ('D4', 'A4'), 82)]:
        violas.chord(at, length, keys, vel)

    # the roots: the celli, the basses an octave under
    for at, length, k in [(b(2), 4, 'D3'), (b(3), 2, 'Bb2'), (b(3, 2), 2, 'C3'), (b(4), 2, 'F2'), (b(4, 2), 2, 'G2'),
                          (b(5), 2, 'C3'), (b(5, 2), 2, 'A2'), (b(6), 2, 'Bb2'), (b(6, 2), 2, 'C3'), (b(7), 4.2, 'D3')]:
        vel = 76 if at < b(6) else 84
        celli.play(at, length, k, vel)
        basses.play(at, length, sc.key(k) - 12, vel - 6)

    # the timpani on the summation's roots, a cymbal swelling into it
    timp = s.part('timpani', 'timpani', role='perc', pan=0.15, hall=0.4, gain_db=-5)
    timp.play(b(6), 1, 'Bb2', 76).play(b(6, 2), 1, 'C3', 80).play(b(6, 3.5), 0.5, 'C3', 62).play(b(7), 2, 'D3', 94)
    cymbal = s.part('cymbal', 'sus_cymbal', role='colour', hall=0.5, gain_db=-16)
    cymbal.play(b(6) - 1.5, 1.5, 64, 90)  # the 1.5 s crescendo: its highs crest about a second in, on the downbeat
    return s
