"""A piece as code: its parts, their notes in beats, and the MIDI each part is rendered from.

A piece module (art_src/music/pieces/NAME.py) gives `score()`, which returns a `Score`: the tempo, the meter, the
bars, the key and mode, the chords by half bar (what the check holds the lead against), the sections, and its
`Part`s. A part plays one instrument of the palette (palette.py) with its notes, its mix (gain, pan, width, filters,
how much of it goes to the hall) and its role (lead, counter, harmony, bass, drone, ostinato, perc, colour), which is
what the check reads it by. Times are in beats from the piece's start (a beat is the meter's unit: a quarter in 4/4,
a dotted quarter in 12/8), lengths in beats, keys as MIDI numbers or names ('D4' is 62, 'F#3' 54, 'Bb2' 46).

Standard library only, so a piece's notes and its MIDI can be read anywhere; the sound is made in the music image.
"""

from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field

NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
PITCH_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

MODES = {
    'ionian': (0, 2, 4, 5, 7, 9, 11), 'dorian': (0, 2, 3, 5, 7, 9, 10), 'phrygian': (0, 1, 3, 5, 7, 8, 10),
    'lydian': (0, 2, 4, 6, 7, 9, 11), 'mixolydian': (0, 2, 4, 5, 7, 9, 10), 'aeolian': (0, 2, 3, 5, 7, 8, 10),
}

# chord qualities as intervals over the root
QUALITIES = {
    '': (0, 4, 7), 'm': (0, 3, 7), '5': (0, 7), 'sus2': (0, 2, 7), 'sus4': (0, 5, 7), '7': (0, 4, 7, 10),
    'm7': (0, 3, 7, 10), 'maj7': (0, 4, 7, 11), 'add9': (0, 4, 7, 14), 'madd9': (0, 3, 7, 14), '6': (0, 4, 7, 9),
    'm6': (0, 3, 7, 9), 'm9': (0, 3, 7, 10, 14), 'maj9': (0, 4, 7, 11, 14), '7sus4': (0, 5, 7, 10),
    'dim': (0, 3, 6), 'm7b5': (0, 3, 6, 10),
}


def key(name) -> int:
    """'D4' -> 62 (C4 is 60); a number is returned as it is."""
    if isinstance(name, int):
        return name
    letter, rest = name[0].upper(), name[1:]
    pc = NAMES[letter]
    while rest and rest[0] in '#b':
        pc += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + pc


def name_of(k: int) -> str:
    return f'{PITCH_NAMES[k % 12]}{k // 12 - 1}'


def chord(name: str) -> tuple[int, tuple[int, ...]]:
    """'Dm7' -> (2, (0, 3, 7, 10)), 'G/B' -> (7, ...) with its bass in name_bass(); the root's pitch class and the
    quality's intervals."""
    head = name.split('/')[0]
    letter = head[0].upper()
    pc = NAMES[letter]
    i = 1
    while i < len(head) and head[i] in '#b':
        pc += 1 if head[i] == '#' else -1
        i += 1
    return pc % 12, QUALITIES[head[i:]]


def chord_pcs(name: str) -> set[int]:
    root, ivs = chord(name)
    pcs = {(root + iv) % 12 for iv in ivs}
    if '/' in name:
        pcs.add(chord(name.split('/')[1] + '')[0])
    return pcs


@dataclass
class Note:
    start: float          # beats from the piece's start
    length: float         # beats
    key: int
    vel: int = 80


@dataclass
class Part:
    name: str
    inst: str                         # an id of palette.INSTRUMENTS
    role: str = 'harmony'             # lead, distant, counter, harmony, bass, drone, ostinato, perc, colour
    notes: list[Note] = field(default_factory=list)
    gain_db: float = 0.0
    pan: float = 0.0                  # -1 left .. 1 right (constant power)
    width: float = 1.0                # 0 mono .. 1 as recorded .. 1.5 wider
    hp: float = 0.0                   # high-pass, Hz (0: none)
    lp: float = 0.0                   # low-pass, Hz (0: none)
    air: float = 0.0                  # a high shelf from about 3 kHz, dB: a string's upper partials, a harp's attack
    hall: float = 0.35                # share sent to the hall reverb, 0..1
    dyn: list[tuple[float, float]] = field(default_factory=list)   # (beat, dB) breakpoints, linear in dB between
    cc: list[tuple[float, int, int]] = field(default_factory=list)  # (beat, controller, value) sent to the renderer
    humanize: tuple[float, int] = (0.0, 0)  # (ms, velocity): a seeded, played feel; (0, 0) for none
    seed: int = 1
    early_ms: float = 0.0             # every note this much early: a bowed or blown sample speaks late
    doubles: str = ''                 # the part this one doubles (an octave, a unison): no voice of its own

    def play(self, start: float, length: float, k, vel: int = 80) -> 'Part':
        self.notes.append(Note(float(start), float(length), key(k), int(vel)))
        return self

    def line(self, at: float, notes, vel: int = 80) -> 'Part':
        """Notes one after another from beat `at`: each (length, key) or (length, key, vel); a key of None is a
        rest."""
        t = float(at)
        for n in notes:
            length, k = n[0], n[1]
            v = n[2] if len(n) > 2 else vel
            if k is not None:
                self.play(t, length, k, v)
            t += length
        return self

    def chord(self, start: float, length: float, keys, vel: int = 72, roll: float = 0.0) -> 'Part':
        """Several keys at once; `roll` beats between each, from the lowest (a harp's or a guitar's spread)."""
        for i, k in enumerate(sorted(key(x) for x in keys)):
            self.play(start + i * roll, length - i * roll, k, vel)
        return self

    def played(self, bpm: float) -> list[Note]:
        """The notes as they are played: the part's seeded feel applied (never moving a note before beat 0)."""
        ms, dv = self.humanize
        early = self.early_ms / 1000 * bpm / 60
        if not ms and not dv and not early:
            return list(self.notes)
        rng = random.Random(f'{self.name}:{self.seed}')
        out = []
        for n in self.notes:
            shift = (rng.uniform(-ms, ms) / 1000 * bpm / 60 if ms else 0.0) - early
            vel = max(1, min(127, n.vel + (rng.randint(-dv, dv) if dv else 0)))
            out.append(Note(max(0.0, n.start + shift), n.length, n.key, vel))
        return out


@dataclass
class Score:
    title: str
    bpm: float
    meter: tuple[int, int] = (4, 4)         # beats a bar, and the beat's unit as written (4 a quarter, 8 an eighth)
    beat_unit: str = 'quarter'              # what a beat is: 'quarter', or 'dotted quarter' in 6/8 and 12/8
    bars: int = 8
    tonic: str = 'D'
    mode: str = 'dorian'
    borrowed: tuple[str, ...] = ()           # notes taken from outside the mode on purpose ('Bb' for a bVI, 'F#' ...)
    chords: dict[int, tuple[str, ...]] = field(default_factory=dict)   # bar: one chord, or one for each half bar
    sections: list[tuple[int, str]] = field(default_factory=list)       # (bar, name): where each section starts
    parts: list[Part] = field(default_factory=list)
    tail: float = 3.0                        # seconds after the last bar that ring out
    kind: str = 'sketch'                     # sketch, theme, loop, sting, bed
    loop_from: int = 0                       # a loop's first looped bar: the bars before it play once (Loading's
                                             # build), and the player's loop_offset is this bar's time
    loudness: float = -20.0                  # the master's integrated loudness, LUFS
    hall_seconds: float = 2.4                # the hall's reverb time (RT60 at 500 Hz to 1 kHz)
    hall_air: float = 0.55                   # the hall's reverb time above 3.5 kHz, as a share of hall_seconds
    early: float = 0.9                       # the hall's early reflections, against its tail (the room's first answer)

    @property
    def beats_per_bar(self) -> int:
        return self.meter[0] // 3 if self.beat_unit == 'dotted quarter' else self.meter[0]

    def bar(self, b: float, beat: float = 0.0) -> float:
        """Beat number of bar `b` (0-based) plus `beat` beats."""
        return b * self.beats_per_bar + beat

    @property
    def seconds_per_beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def length_s(self) -> float:
        return self.bars * self.beats_per_bar * self.seconds_per_beat

    def part(self, name: str, inst: str, **kw) -> Part:
        p = Part(name, inst, **kw)
        self.parts.append(p)
        return p

    def chord_at(self, beat: float) -> str | None:
        """The chord sounding at `beat`, from `chords` (one per bar, or one per half bar)."""
        b = int(beat // self.beats_per_bar)
        names = self.chords.get(b)
        if not names:
            return None
        frac = (beat - b * self.beats_per_bar) / self.beats_per_bar
        return names[min(len(names) - 1, int(frac * len(names)))]

    def section_at(self, bar: int) -> str:
        name = ''
        for b, n in sorted(self.sections):
            if b <= bar:
                name = n
        return name


# ---- MIDI ---------------------------------------------------------------------------------------------------------

TPQ = 480   # ticks a beat


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, int, bytes]]) -> bytes:
    """events: (tick, order, data), sorted by tick then order (note-offs before note-ons on the same tick)."""
    data, last = b'', 0
    for tick, _, ev in sorted(events, key=lambda e: (e[0], e[1])):
        data += _vlq(tick - last) + ev
        last = tick
    data += _vlq(0) + b'\xff\x2f\x00'
    return b'MTrk' + struct.pack('>I', len(data)) + data


def part_events(score: Score, part: Part, channel: int, program: tuple[int, int] | None,
                tail_beats: float = 0.0) -> list[tuple[int, int, bytes]]:
    ev = []
    # MIDI counts quarters: a dotted-quarter beat (6/8, 12/8) is a quarter and a half, so the file's bars and
    # meter read as written in any sequencer
    qpb = 1.5 if score.beat_unit == 'dotted quarter' else 1.0
    tpb = TPQ * qpb
    tempo = int(round(60_000_000 / (score.bpm * qpb)))
    ev.append((0, 0, b'\xff\x51\x03' + tempo.to_bytes(3, 'big')))
    num, den = score.meter
    ev.append((0, 0, b'\xff\x58\x04' + bytes([num, {2: 1, 4: 2, 8: 3, 16: 4}[den], 24, 8])))
    ch = channel & 0x0F
    if program is not None:
        bank, prog = program
        ev.append((0, 1, bytes([0xB0 | ch, 0, bank & 0x7F])))
        ev.append((0, 1, bytes([0xC0 | ch, prog & 0x7F])))
    ev.append((0, 1, bytes([0xB0 | ch, 7, 100])))
    ev.append((0, 1, bytes([0xB0 | ch, 10, 64])))
    ev.append((0, 1, bytes([0xB0 | ch, 11, 127])))
    for beat, ctl, val in part.cc:
        ev.append((int(round(beat * tpb)), 2, bytes([0xB0 | ch, ctl & 0x7F, val & 0x7F])))
    end = 0
    notes = sorted(part.played(score.bpm), key=lambda n: (n.start, n.key))
    spans = []
    for i, n in enumerate(notes):
        on = int(round(n.start * tpb))
        off = max(on + 1, int(round((n.start + n.length) * tpb)))
        # a key struck again while it still sounds: MIDI cannot tell the two apart, and the first one's note-off
        # would cut the second short (sfizz releases the key), so the first ends where the second begins
        later = [int(round(m.start * tpb)) for m in notes[i + 1:] if m.key == n.key]
        if later and later[0] < off:
            off = max(on + 1, later[0])
        spans.append((on, off, n))
    for on, off, n in spans:
        ev.append((on, 4, bytes([0x90 | ch, n.key & 0x7F, n.vel & 0x7F])))
        ev.append((off, 3, bytes([0x80 | ch, n.key & 0x7F, 0])))
        end = max(end, off)
    if tail_beats:
        # a controller at the end of the tail, so a renderer that stops at the last event lets the notes ring
        ev.append((end + int(tail_beats * tpb), 5, bytes([0xB0 | ch, 11, 127])))
    return ev


def midi_bytes(tracks: list[list[tuple[int, int, bytes]]]) -> bytes:
    head = b'MThd' + struct.pack('>IHHH', 6, 1 if len(tracks) > 1 else 0, len(tracks), TPQ)
    return head + b''.join(_track(t) for t in tracks)
