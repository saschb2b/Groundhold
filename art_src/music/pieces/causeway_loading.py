"""Sketch for Loading's music, "Walking out": for the owner's ear, not a piece yet.

Grown from the hub's theme, which the owner approved ("Yes, make the next", 2 November 2026): the call turned into a
march out, building toward the match (front-end.md §5.6: the camera sets off down the road past the crew while the
cards fill). In D at 80 like the hub, so it starts on the hub's next bar; the march's pulse is in eighths, so it
walks rather than strolls. A field drum and timpani, never sketch B's frame-drum lilt (the owner: "not my jam").

Twelve bars (36 s). The first eight play once; the last four loop (`loop_from`, the player's loop_offset at 24 s)
for as long as the match takes to load, and every pass ends on the horns' A, the match horn's own note, so whenever
the match starts, its horn lands as the march's arrival.
- Bars 1-2, setting out: the field drum alone in eighths, soft, the timpani on D, the celli and the contrabass
  stepping D in eighths beneath.
- Bars 3-6, the call marches: the horns play the call in a march's dotted rhythm (A, D, E), turn, and call again a
  fourth up, over Dm | Bb C | Dm | C Asus4.
- Bars 7-8, the tune: the violins take A's tune over the march (the call, its answer), the violas fill in.
- Bars 9-12, walking out (looped): A's tune goes on (the call a fourth up, the fall to A), then Bb and C rise to A
  suspended, the horns holding A and the field drum rolling into the bar the loop returns to.
"""

import score as sc
from pieces.causeway import THEME_TUNE

BARS = 12
LOOP_FROM = 8
CHORDS = {0: ('Dm',), 1: ('Dm',), 2: ('Dm',), 3: ('Bb', 'C'), 4: ('Dm',), 5: ('C', 'Asus4'),
          6: ('Dm',), 7: ('Bbmaj7', 'C'), 8: ('F', 'G'), 9: ('C', 'Asus4'), 10: ('Bb', 'C'), 11: ('Asus4',)}
ROOTS = {'Dm': 'D', 'Bb': 'Bb', 'C': 'C', 'Asus4': 'A', 'Bbmaj7': 'Bb', 'F': 'F', 'G': 'G'}


def score():
    s = sc.Score(title='Loading, "Walking out"', bpm=80, meter=(4, 4), bars=BARS, tonic='D', mode='dorian',
                 borrowed=('Bb',), tail=5.0, kind='loop', loop_from=LOOP_FROM, loudness=-20.0, hall_seconds=2.6,
                 hall_air=0.8, early=1.3, chords=CHORDS,
                 sections=[(0, 'setting out'), (2, 'the call marches'), (6, 'the tune'), (8, 'walking out')])
    b = s.bar

    # the march: the field drum in eighths (snares on for the strokes, off for the ghosts), louder as it goes
    drum = s.part('field drum', 'snare_rope', role='perc', pan=0.1, hall=0.35, gain_db=-8, hp=70, humanize=(3, 4))
    for bar in range(BARS):
        lift = 0 if bar < 2 else 8 if bar < 6 else 14
        if bar == 11:     # a roll into the bar the loop returns to, its last stroke an eighth before the bar line
            drum.line(b(bar), [(1, 64, 70 + lift), (1, 63, 50 + lift)] + [(0.25, 64, 52 + lift + 4 * i)
                                                                            for i in range(6)] + [(0.5, 64, 86 + lift)])
            continue
        for beat in range(4):
            accent = beat in (0, 2)
            drum.line(b(bar, beat), [(0.5, 64 if accent else 63, (66 if accent else 46) + lift),
                                     (0.25, 63, 40 + lift), (0.25, 63, 44 + lift)])
    timp = s.part('timpani', 'timpani', role='perc', pan=0.15, hall=0.45, gain_db=-8)
    for bar in range(BARS):
        names = CHORDS[bar]
        for half, name in enumerate(names if len(names) == 2 else names * 2):
            root = ROOTS[name]
            k = {'D': 'D3', 'A': 'A2', 'Bb': 'Bb2', 'C': 'C3', 'F': 'F2', 'G': 'G2'}[root]
            timp.play(b(bar, 2 * half), 1, k, 70 if bar < 6 else 82)

    # the low strings stepping in eighths, the contrabass under the celli
    celli = s.part('celli', 'celli', role='bass', pan=0.3, hall=0.35, gain_db=-4, hp=45, air=2, early_ms=40,
                   humanize=(4, 3))
    basses = s.part('basses', 'basses', role='bass', doubles='celli', pan=0.45, hall=0.35, gain_db=-7, hp=30,
                    early_ms=50)
    lows = {'D': ('D3', 'A2'), 'Bb': ('Bb2', 'F2'), 'C': ('C3', 'G2'), 'A': ('A2', 'E2'), 'F': ('F2', 'C3'),
            'G': ('G2', 'D3')}
    for bar in range(BARS):
        names = CHORDS[bar]
        for half, name in enumerate(names if len(names) == 2 else names * 2):
            root, fifth = lows[ROOTS[name]]
            for i, k in enumerate((root, root, fifth, root)):
                vel = (72 if i == 0 else 60) + (0 if bar < 6 else 8)
                celli.play(b(bar, 2 * half + 0.5 * i), 0.4, k, vel)
                basses.play(b(bar, 2 * half + 0.5 * i), 0.4, sc.key(k) - 12, vel - 6)

    # bars 3-6: the call marches on the horns
    horns = s.part('horns', 'horn', role='lead', pan=-0.2, hall=0.45, gain_db=-3, early_ms=30, humanize=(5, 3))
    horns.line(b(2), [(0.75, 'A3'), (0.25, 'D4'), (1.5, 'E4'), (0.5, 'D4'), (1, 'C4')], vel=74)
    horns.line(b(3), [(0.75, 'D4'), (0.25, 'F4'), (1, 'D4'), (1, 'E4'), (1, 'G4')], vel=76)
    horns.line(b(4), [(0.75, 'D4'), (0.25, 'G4'), (1.5, 'A4'), (0.5, 'G4'), (1, 'F4')], vel=78)
    horns.line(b(5), [(1, 'G4'), (1, 'F4'), (2, 'E4')], vel=78)

    # bars 7-12: A's tune over the march; the horns under it, then holding A
    tune = s.part('violins', 'violins', role='lead', pan=-0.45, hall=0.4, air=3, early_ms=50, humanize=(5, 3))
    for i, bar_notes in enumerate(THEME_TUNE):
        tune.line(b(6 + i), bar_notes, vel=84 + 2 * i)
    tune.line(b(10), [(1.5, 'D5', 88), (0.5, 'F5', 88), (1, 'E5', 90), (1, 'G5', 90)])
    tune.play(b(11), 3.5, 'A5', 92)                       # (a breath before the loop's return)
    counter = s.part('horn line', 'horn', role='counter', pan=-0.15, hall=0.45, gain_db=-5, early_ms=30)
    for at, length, k in ((b(6), 2, 'D4'), (b(6, 2), 1, 'A3'), (b(6, 3), 1, 'D4'), (b(7), 2, 'D4'), (b(7, 2), 2, 'E4'),
                          (b(8), 2, 'C4'), (b(8, 2), 2, 'D4'), (b(9), 2, 'C4'), (b(9, 2), 2, 'D4'),
                          (b(10), 2, 'D4'), (b(10, 2), 2, 'E4'), (b(11), 3.5, 'A3')):
        counter.play(at, length, k, 76)
    violas = s.part('violas', 'violas', role='harmony', pan=-0.1, hall=0.4, gain_db=-8, air=3, early_ms=40)
    for at, length, keys in ((b(6), 4, ('D4', 'F4')), (b(7), 2, ('D4', 'F4')), (b(7, 2), 2, ('E4', 'G4')),
                             (b(8), 2, ('C4', 'A4')), (b(8, 2), 2, ('D4', 'B4')), (b(9), 2, ('E4', 'G4')),
                             (b(9, 2), 2, ('D4', 'A4')), (b(10), 2, ('D4', 'F4')), (b(10, 2), 2, ('E4', 'G4')),
                             (b(11), 3.5, ('D4', 'E4'))):
        violas.chord(at, length, keys, 74)
    return s
