"""Sketch for the queue's music, "Waiting on the tide": for the owner's ear, not a piece yet.

Grown from the hub's theme, which the owner approved ("Yes, make the next", 2 November 2026): its flats, its call and
its D at 80, so the hub hands over to it on the next bar (SKILL.md, Placing the hub's music) and nothing in the key,
the tempo or the hall changes under the player. music_rules.md asks the queue for the ambient middle's material as a
loop that can run for minutes, nothing that builds; the coordinator's brief, a patient pulse under the flats with a
soft ticking figure.

A seamless loop of 12 bars (36 s), quieter than the hub (-23 LUFS against -20): the player is waiting, not arriving.
- The pulse: the celli plucked, D on the first beat and A on the third of every bar, under the contrabass's held D;
  a heartbeat, slow and even.
- The tick: the violins plucked very softly on every beat, A and E in turn: a clock, never louder than the water.
- The flats, slowed: the harp turning up a chord in quarters, high; the rubbed glass; the violins' tremolo very
  soft and high; the far bell once a loop. Dsus2 C/D D C/D G/D Dsus2 D C/D G/D C/D Dsus2 C/D, over the D pedal.
- The call, far off and left open, once every four bars: the flute (bars 3-4), the horn on the match horn's own A
  (bars 7-8), the violins high (bars 11-12), each holding its last note into the next bar.
"""

import score as sc
from pieces.causeway import FLATS, call

BARS = 12
CHORDS = ('Dsus2', 'C/D', 'D', 'C/D', 'G/D', 'Dsus2', 'D', 'C/D', 'G/D', 'C/D', 'Dsus2', 'C/D')


def score():
    s = sc.Score(title='The queue, "Waiting on the tide"', bpm=80, meter=(4, 4), bars=BARS, tonic='D',
                 mode='mixolydian', tail=6.0, kind='loop', loudness=-23.0, hall_seconds=2.8, hall_air=0.8, early=1.3,
                 chords={i: (c,) for i, c in enumerate(CHORDS)},
                 sections=[(0, 'the wait'), (2, 'the flute far off'), (6, 'the horn far off'),
                           (10, 'the violins far off')])
    b = s.bar

    # the floor and the pulse
    basses = s.part('basses', 'basses', role='drone', pan=0.45, hall=0.4, gain_db=-8, hp=30, early_ms=50)
    for bar in range(0, BARS, 2):
        basses.play(b(bar), 8, 'D2', 62)
    pulse = s.part('pulse', 'celli_pizz', role='bass', pan=0.3, hall=0.45, gain_db=-4, hp=40)
    for bar in range(BARS):
        pulse.play(b(bar), 1.5, 'D2', 66).play(b(bar, 2), 1.5, 'A2', 58)

    # the tick: the violins plucked, A and E in turn, very soft
    tick = s.part('tick', 'violins_pizz', role='ostinato', pan=-0.4, hall=0.5, gain_db=-8, air=2, humanize=(4, 3))
    for bar in range(BARS):
        for beat in range(4):
            tick.play(b(bar, beat), 0.6, 'A5' if beat % 2 == 0 else 'E5', 52 if beat == 0 else 46)

    # the flats, slowed: a chord rising in quarters, high
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.55, gain_db=-8, air=3, humanize=(5, 4))
    for bar, name in enumerate(CHORDS):
        for i, k in enumerate(FLATS[name].split()[:4]):
            harp.play(b(bar, i), 2.0, k, 58 + (6 if i == 0 else 0))
    glass = s.part('glass', 'wine_glass', role='drone', pan=-0.3, hall=0.6, gain_db=-10, air=2)
    shimmer = s.part('shimmer', 'violins_trem', role='drone', pan=-0.55, hall=0.6, gain_db=-15, air=3, early_ms=50)
    for bar in range(0, BARS, 2):
        glass.play(b(bar), 8, 'A5' if bar in (4, 6) else 'D5', 66)
        shimmer.chord(b(bar), 8, ['A5', 'D6'], 54)
    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-10, hp=160, lp=3200)
    bell.play(b(0), 2, 'D4', 60)

    # the call far off, once every four bars, its last note held into the next bar and left there
    flute = s.part('flute far', 'flute', role='distant', pan=-0.2, hall=0.55, gain_db=2, air=2, early_ms=30,
                   humanize=(6, 3))
    flute.line(b(2), call('A4', (1.5, 0.5, 5.0)), vel=72)
    horn = s.part('horn far', 'horn', role='distant', pan=-0.3, hall=0.6, gain_db=-3, early_ms=30, humanize=(6, 3))
    horn.line(b(6), call('A3', (2.0, 1.0, 4.0)), vel=56)        # (its own rhythm, slower)
    violins = s.part('violins far', 'violins', role='distant', pan=-0.5, hall=0.55, gain_db=-4, air=3, early_ms=50,
                     humanize=(6, 3))
    violins.line(b(10), call('E5', (1.5, 0.5, 5.0)), vel=66)
    return s
