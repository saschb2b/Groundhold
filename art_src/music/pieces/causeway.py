"""What the Causeway's pieces share (not a piece): the call, the theme the owner chose, and C's flats.

The call is the Causeway's signature, three notes every piece grows from: a rising fourth and a step,
long-short-long (A, D, E in D). It is the Holdfast's horn made into a tune: the match's `wave_horn` sounds A
(220 Hz), so the hub sits in D, the call starts on the horn's own note, and the countdown's horn on 0 lands as the
theme's fifth (front-end.md §5.3). Every map has a Holdfast; no lantern, gourd, night or autumn is in any of this
(AGENTS.md), and no note of Blizzard's (music_rules.md).

The owner chose sketch A's theme and sketch C's calm (2 November 2026, lessons.md), so both live here once, for
round 2's sketches and the piece they grow into:
- THEME: A's four bars of tune (the call, its answer falling by steps to C, the call a fourth higher, the fall to
  the half close on A suspended) with its chords, the horn's counter, the violas' two parts and the roots.
- FLATS: C's harp figures, high, turning up and down over each chord like water on sand. Under the tune's D minor
  bar the harp plays the D-and-E figure, not the F: high, its F would ring a semitone over the tune's held E.
"""

from __future__ import annotations

import score as sc

E = 1 / 3            # an eighth in 6/8 and 12/8, where a beat is a dotted quarter

CALL = (0, 5, 7)     # the call's steps over its first note: up a fourth, then a step


def call(first, lengths=(1.5, 0.5, 2.0)):
    """The call from `first` (a key or a name): [(length, key), ...] for Part.line."""
    k = sc.key(first)
    return [(length, k + step) for length, step in zip(lengths, CALL)]


def arp(part, at: float, keys, step: float, vel: int = 64, ring: float = 1.0, accent: int = 0):
    """Keys one after another from beat `at`, each `step` beats apart and ringing `ring` beats; the first one
    `accent` louder."""
    for i, k in enumerate(keys.split() if isinstance(keys, str) else keys):
        part.play(at + i * step, ring, k, vel + (accent if i == 0 else 0))
    return part


# ---- sketch A's theme (4/4, a bar of four beats) ------------------------------------------------------------------

THEME_CHORDS = (('Dm',), ('Bbmaj7', 'C'), ('F', 'G'), ('C', 'Asus4'))
THEME_TUNE = (
    call('A4'),
    [(1, 'F5'), (0.5, 'E5'), (0.5, 'D5'), (1, 'C5'), (1, 'D5')],
    call('D5'),
    [(1, 'G5'), (0.5, 'F5'), (0.5, 'E5'), (1, 'D5'), (1, 'E5')],
)
# the horn's counter, moving only where the tune holds: (beat in the four bars, length, key)
THEME_COUNTER = ((0, 2, 'D4'), (2, 1, 'A3'), (3, 1, 'D4'), (4, 2, 'D4'), (6, 2, 'E4'), (8, 2, 'C4'), (10, 1, 'D4'),
                 (11, 1, 'B3'), (12, 2, 'C4'), (14, 2, 'D4'))
THEME_VIOLAS = ((0, 4, ('D4', 'F4')), (4, 2, ('D4', 'F4')), (6, 2, ('E4', 'G4')), (8, 2, ('C4', 'A4')),
                (10, 2, ('D4', 'B4')), (12, 2, ('E4', 'G4')), (14, 2, ('D4', 'A4')))
THEME_ROOTS = ((0, 4, 'D3'), (4, 2, 'Bb2'), (6, 2, 'C3'), (8, 2, 'F2'), (10, 2, 'G2'), (12, 2, 'C3'), (14, 2, 'A2'))


def theme(at: float, tune, counter=None, violas=None, celli=None, basses=None, vel: int = 82, lift: int = 2):
    """Sketch A's four bars from beat `at` on the parts given: the tune (each bar `lift` louder than the last, so the
    phrase rises to its height in the third), the counter, the violas, the celli on the roots and the contrabass an
    octave under them."""
    for i, bar in enumerate(THEME_TUNE):
        tune.line(at + 4 * i, bar, vel=vel + lift * i + (4 if i == 2 else 0))
    for beat, length, k in THEME_COUNTER if counter else ():
        counter.play(at + beat, length, k, vel - 10 + (2 if beat >= 8 else 0))
    for beat, length, keys in THEME_VIOLAS if violas else ():
        violas.chord(at + beat, length, keys, vel - 8)
    for beat, length, k in THEME_ROOTS:
        if celli:
            celli.play(at + beat, length, k, vel - 6)
        if basses:
            basses.play(at + beat, length, sc.key(k) - 12, vel - 12)


# ---- sketch C's flats: the harp, high, a figure of eight eighths a bar (or four a chord) ---------------------------

FLATS = {
    'Dsus2': 'D4 A4 E5 A5 D6 A5 E5 A4', 'C/D': 'D4 G4 C5 E5 G5 E5 C5 G4', 'D': 'D4 A4 D5 F#5 A5 F#5 D5 A4',
    'C': 'C4 G4 C5 E5 G5 E5 C5 G4', 'G/D': 'D4 G4 B4 D5 G5 D5 B4 G4', 'Dm': 'D4 A4 D5 F5 A5 F5 D5 A4',
    'Em7': 'E4 B4 D5 G5', 'Asus4': 'A3 E4 A4 D5', 'G/B': 'B3 G4 B4 D5', 'Bbmaj7': 'D4 F4 A4 D5',
    'Bb': 'D4 F4 Bb4 D5', 'F': 'F4 A4 C5 F5', 'G': 'G4 B4 D5 G5', 'C4': 'E4 G4 C5 E5',
    # whole bars of a chord the sketches only held for half a bar (the hub's theme)
    'Bbmaj7 bar': 'D4 F4 A4 D5 F5 D5 A4 F4', 'Asus4 bar': 'A3 E4 A4 D5 E5 D5 A4 E4',
    'Cadd9/D': 'D4 G4 C5 D5 E5 D5 C5 G4',
}


def flats(harp, at: float, names, vel: int = 58, ring: float = 1.5, accent: int = 8):
    """The harp over one bar from beat `at`: one chord's figure of eight eighths, or two chords' of four each."""
    if len(names) == 1:
        name = 'Dsus2' if names[0] == 'Dm' else names[0]
        name = name + ' bar' if name + ' bar' in FLATS else name
        arp(harp, at, FLATS[name], 0.5, vel=vel, ring=ring, accent=accent)
    else:
        for i, name in enumerate(names):
            arp(harp, at + 2 * i, FLATS['C4' if name == 'C' else name], 0.5, vel=vel, ring=ring,
                accent=accent if i == 0 else accent // 2)
