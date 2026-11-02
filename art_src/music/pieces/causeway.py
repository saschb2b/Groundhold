"""What the Causeway's sketches share (not a piece): the call, and a few ways of playing a chord.

The call is the Causeway's signature, three notes any sketch grows from: a rising fourth and a step, long-short-long
(A, D, E in D). It is the Holdfast's horn made into a tune: the match's `wave_horn` sounds A (220 Hz), so the hub
sits in D, the call starts on the horn's own note, and the countdown's horn on 0 lands as the theme's fifth
(front-end.md §5.3: the match opens with the horn the menu just played). Every map has a Holdfast; no lantern,
gourd, night or autumn is in any of this (AGENTS.md), and no note of Blizzard's (music_rules.md).
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
