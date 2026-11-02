"""Sketch for Match Found's music, "The tide turns": for the owner's ear, not a piece yet.

Grown from the hub's theme, which the owner approved ("Yes, make the next", 2 November 2026): a sting that rises to
the call, the theme's close made into one gesture. music_rules.md asks for a sting of four to six seconds (Hearthstone's
stingers run about five, McConnell), loud only after the quiet before it (Brower). It starts on the bar line after
Match Found appears (FROM_TIME_NEXT_BAR from the hub or the queue), in D at 80 like them, so it lands in their key.

Two bars and their ring (about 9 s in all, the gesture itself 6 s):
- Bar 1, the rise: the harp runs up Bb, then C, two octaves in sixteenths; the violins' tremolo swells under it; a
  timpani roll on Bb grows; the celli and contrabass hold Bb, then C: the theme's heroic bVI bVII.
- Bar 2, the call: on the downbeat D major, the far bell and the timpani; the violins play the call (A, D, E) with the
  horns an octave under, and the E is left ringing over the D major chord, the ninth: open, as the tide turning.
"""

import score as sc
from pieces.causeway import arp, call

BARS = 2


def score():
    s = sc.Score(title='Match Found, "The tide turns"', bpm=80, meter=(4, 4), bars=BARS, tonic='D', mode='mixolydian',
                 borrowed=('Bb', 'F'), tail=4.0, kind='sting', loudness=-19.0, hall_seconds=2.8, hall_air=0.8,
                 early=1.3, chords={0: ('Bb', 'C'), 1: ('D',)}, sections=[(0, 'the rise'), (1, 'the call')])
    b = s.bar

    # bar 1: the rise
    harp = s.part('harp', 'harp', role='ostinato', pan=0.5, hall=0.5, gain_db=-10, air=3,
                  dyn=[(b(0), -6), (b(0, 3.75), 0)])
    arp(harp, b(0), 'Bb2 D3 F3 Bb3 D4 F4 Bb4 D5', 0.25, vel=70, ring=1.0)
    arp(harp, b(0, 2), 'C3 E3 G3 C4 E4 G4 C5 E5', 0.25, vel=78, ring=1.0)
    harp.chord(b(1), 4, ['D3', 'A3', 'D4', 'F#4', 'A4', 'D5', 'F#5', 'A5'], 72, roll=0.05)
    trem = s.part('tremolo', 'violins_trem', role='harmony', pan=-0.45, hall=0.45, gain_db=-8, air=3, early_ms=50,
                  dyn=[(b(0), -15), (b(1), 0)])
    trem.chord(b(0), 2, ['D5', 'F5'], 80).chord(b(0, 2), 2, ['E5', 'G5'], 86)
    roll = s.part('roll', 'timpani_roll', role='perc', pan=0.15, hall=0.45, gain_db=-4, dyn=[(b(0), -14), (b(1), 0)])
    roll.play(b(0), 4, 'Bb2', 84)
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.4, gain_db=-3, hp=45, air=2, early_ms=40)
    basses = s.part('basses', 'basses', role='bass', doubles='celli', pan=0.45, hall=0.4, gain_db=-6, hp=30,
                    early_ms=50)
    for at, length, k, vel in ((b(0), 2, 'Bb2', 72), (b(0, 2), 2, 'C3', 80), (b(1), 4, 'D3', 88)):
        celli.play(at, length, k, vel)
        basses.play(at, length, sc.key(k) - 12, vel - 6)

    # bar 2: the call over D major
    tune = s.part('violins', 'violins', role='lead', pan=-0.45, hall=0.4, air=3, early_ms=50)
    tune.line(b(1), call('A4', (1.5, 0.5, 2.0)), vel=96)
    horns = s.part('horns', 'horn', role='lead', doubles='violins', pan=-0.25, hall=0.45, gain_db=-7, early_ms=30)
    horns.line(b(1), call('A3', (1.5, 0.5, 2.0)), vel=92)
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.4, gain_db=-8, air=3, early_ms=40)
    violas.chord(b(1), 4, ['D4', 'F#4', 'A4'], 80)
    bell = s.part('bell', 'tubular_bells', role='colour', pan=-0.5, hall=0.85, gain_db=-8, hp=160, lp=3600)
    bell.play(b(1), 2, 'D4', 80)
    timp = s.part('timpani', 'timpani', role='perc', pan=0.15, hall=0.45, gain_db=-5)
    timp.play(b(1), 2, 'D3', 96)
    return s
