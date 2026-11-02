"""Sketch B for the Causeway's theme, "The crossroads band": eight bars for the owner's ear, not a piece.

The folk take: Builders from every shore meet on the road, so the band is from everywhere (a strumstick, a bowed
psaltery, an alto recorder for the whistle's colour, a bassoon in the bass, a frame drum where a bodhran would be, a
fiddle and a folk harp joining at the end), in the manner of Hearthstone's tavern as McConnell describes it (a small
band, ambient, leaving room; music_rules.md) and of Warcraft's flutes over nature for its night elves (critics'
words), never in their notes. A jig's lilt in 12/8, the dotted quarter at 63, D Dorian, a near room.

- Bars 1-2, the band: the psaltery's bowed A and D in the air, the strumstick striking each beat with its drone
  string after, the bassoon on root and fifth, the frame drum's three strokes a beat (struck, then two light).
- Bars 3-6, the tune: the recorder plays the call in the jig's long-short (A, D, E), turns down (F, E, D), runs
  over C, the call again turning to the Dorian's bright IV (G, its B natural), and comes to rest on A over A minor,
  the horn's note.
- Bars 7-8, all together: the fiddle joins a third under the tune, the folk harp runs up Bb and C, the drum
  fills, and the tune comes home on D over an open fifth, the fiddle on A, the harp rolled.
"""

import score as sc
from pieces.causeway import E, arp, call

BARS = 8


def score():
    s = sc.Score(title='Causeway sketch B, "The crossroads band"', bpm=63, meter=(12, 8), beat_unit='dotted quarter',
                 bars=BARS, tonic='D', mode='dorian', tail=3.5, kind='sketch', loudness=-20.0, hall_seconds=1.7,
                 chords={0: ('D5',), 1: ('C',), 2: ('Dm',), 3: ('C',), 4: ('Dm', 'G'), 5: ('Am',), 6: ('Bb', 'C'),
                         7: ('D5',)},
                 sections=[(0, 'the band'), (2, 'the tune'), (6, 'all together')])
    b = s.bar

    # the psaltery bowed: the air over the band's first two bars
    psaltery = s.part('psaltery', 'psaltery_bowed', role='drone', pan=0.4, hall=0.35, gain_db=-9,
                      dyn=[(b(0), -10), (b(1), 0), (b(1, 3), -2), (b(2), -12)])
    psaltery.chord(b(0), 8, ['A4', 'D5'], 70)

    # the strumstick: a chord struck on each beat, its drone string between
    strum = s.part('strumstick', 'strumstick', role='ostinato', pan=-0.35, hall=0.2, gain_db=-9, humanize=(5, 6))
    voicing = {'D5': ('D4', 'A4', 'D5'), 'C': ('C4', 'G4', 'C5'), 'Dm': ('D4', 'F4', 'A4'), 'G': ('D4', 'G4', 'B4'),
               'Am': ('E4', 'A4', 'C5'), 'Bb': ('D4', 'F4', 'Bb4')}
    for bar in range(BARS - 1):
        names = s.chords[bar]
        for beat in range(4):
            name = names[min(len(names) - 1, beat * len(names) // 4)]
            strong = beat in (0, 2)
            strum.chord(b(bar, beat), 2 * E, voicing[name], 78 if strong else 62, roll=0.03)
            strum.play(b(bar, beat + 2 * E), E, 'A4', 44 if strong else 40)
    strum.chord(b(7), 4, voicing['D5'], 84, roll=0.05)

    # the bassoon: root and fifth on the beats, detached
    bassoon = s.part('bassoon', 'bassoon', role='bass', pan=0.15, hall=0.22, gain_db=-4, humanize=(6, 4))
    roots = {0: ('D3', 'A2'), 1: ('C3', 'G2'), 2: ('D3', 'A2'), 3: ('C3', 'G2'), 5: ('A2', 'E3')}
    for bar, (root, fifth) in roots.items():
        bassoon.line(b(bar), [(0.8, root, 80), (0.2, None), (0.8, fifth, 70), (0.2, None),
                              (0.8, root, 76), (0.2, None), (0.8, fifth, 70), (0.2, None)])
    bassoon.line(b(4), [(0.8, 'D3', 80), (0.2, None), (0.8, 'A2', 70), (0.2, None),
                        (0.8, 'G2', 78), (0.2, None), (0.8, 'D3', 70), (0.2, None)])
    bassoon.line(b(6), [(0.8, 'Bb2', 84), (0.2, None), (0.8, 'F2', 74), (0.2, None),
                        (0.8, 'C3', 84), (0.2, None), (0.8, 'G2', 76), (0.2, None)])
    bassoon.play(b(7), 4, 'D2', 84)

    # the frame drum: struck, then two light strokes, every beat; a fill into bar 7
    drum = s.part('frame drum', 'frame_drum', role='perc', pan=-0.1, hall=0.2, gain_db=-6, humanize=(4, 5))
    for bar in range(BARS - 1):
        lift = 10 if bar >= 6 else 0
        for beat in range(4):
            if bar == 5 and beat == 3:
                drum.line(b(bar, beat), [(E, 64, 62), (E, 64, 72), (E, 64, 86)])
                continue
            low = 61 if beat in (0, 2) else 62
            drum.line(b(bar, beat), [(E, low, 84 + lift if beat in (0, 2) else 70 + lift), (E, 65, 40 + lift),
                                      (E, 64, 52 + lift)])
    drum.play(b(7), 2, 61, 96)

    # the tune on the alto recorder
    tune = s.part('tune', 'alto_recorder', role='lead', pan=0.0, hall=0.28, gain_db=0, early_ms=20, humanize=(5, 3))
    tune.line(b(2), call('A4', (2 * E, E, 3 * E)) + [(2 * E, 'F5'), (E, 'E5'), (3 * E, 'D5')], vel=88)
    tune.line(b(3), [(E, 'E5'), (E, 'D5'), (E, 'C5'), (3 * E, 'G4'), (E, 'A4'), (E, 'B4'), (E, 'C5'), (3 * E, 'D5')],
              vel=84)
    tune.line(b(4), call('A4', (2 * E, E, 3 * E)) + [(2 * E, 'D5'), (E, 'B4'), (3 * E, 'G4')], vel=90)
    tune.line(b(5), [(2 * E, 'A4'), (E, 'C5'), (2 * E, 'E5'), (E, 'D5'), (2 * E, 'C5'), (E, 'B4'), (3 * E, 'A4')],
              vel=86)
    tune.line(b(6), [(2 * E, 'D5'), (E, 'F5'), (3 * E, 'A5'), (2 * E, 'G5'), (E, 'E5'), (3 * E, 'C5')], vel=96)
    tune.line(b(7), [(2 * E, 'D5'), (E, 'E5'), (9 * E + 0.3, 'D5')], vel=96)

    # the fiddle: a third under the tune, then the open fifth's A
    fiddle = s.part('fiddle', 'fiddle', role='counter', pan=0.25, hall=0.28, gain_db=-5, early_ms=40, humanize=(5, 3))
    fiddle.line(b(6), [(2 * E, 'Bb4'), (E, 'D5'), (3 * E, 'F5'), (2 * E, 'E5'), (E, 'C5'), (3 * E, 'G4')], vel=84)
    fiddle.line(b(7), [(2 * E, 'A4'), (E, 'C5'), (9 * E + 0.3, 'A4')], vel=86)

    # the folk harp: a run up each chord of bar 7, then the last chord rolled
    harp = s.part('folk harp', 'folk_harp', role='colour', pan=0.45, hall=0.35, gain_db=-15, humanize=(3, 4))
    arp(harp, b(6), 'Bb3 D4 F4 Bb4 D5 F5', E, vel=62, ring=1.0)
    arp(harp, b(6, 2), 'C4 E4 G4 C5 E5 G5', E, vel=64, ring=1.0)
    harp.chord(b(7), 4, ['D3', 'A3', 'D4', 'E4', 'A4', 'D5'], 70, roll=0.05)
    return s
