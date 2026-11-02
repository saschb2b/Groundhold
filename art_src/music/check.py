#!/usr/bin/env python3
"""A piece checked without ears: its sound by numbers, its score against the rules, and two pictures to look at.

    python3 art_src/music/check.py PIECE [--out DIR]     # render.py's output for PIECE, checked again
    python3 art_src/music/check.py --ref FILE            # a reference recording's habits by the same numbers

The sound (the rendered master): its length; integrated loudness against the piece's target, loudness range and
true peak (mix.py's BS.1770-4 and EBU Tech 3342); each bar's loudness and peak; the energy in five bands (below
120 Hz, to 500, to 2000, to 6000, above); the spectrum's centre and flatness; the stereo image (side against
middle, correlation); the punch (Cyberworld's swing inside a beat); and the tempo the onsets beat at, against the
piece's own.

The score (what the piece wrote down): the tempo for its kind; the notes outside its mode; the lead's range, its
intervals, its longest note, its notes a bar and how often a bar's rhythm comes back; the hook's return; how many
parts sound at once; whether every part enters at a section's head; low intervals packed too close; the lead's
notes rubbing a semitone against the harmony; the chord changes a bar; and the ending. Each line that misses its
rule says so with `MISS`; `music_rules.md` (.claude/skills/music/) says where each number comes from.

The pictures: NAME.spectrum.png (ffmpeg's showspectrumpic, log frequency) and NAME.roll.png (the score drawn, a
row a semitone, each part in its role's colour, bar lines and sections, the chords above). Runs in the music image
(render.py starts it there).
"""

from __future__ import annotations

import collections
import importlib
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)

# The rules' numbers (music_rules.md names each one's source). A kind is what a piece is for.
TEMPO = {   # beats a minute, by kind and beat unit
    ('sketch', 'quarter'): (66, 104), ('theme', 'quarter'): (66, 104), ('loop', 'quarter'): (60, 104),
    ('sketch', 'dotted quarter'): (50, 76), ('theme', 'dotted quarter'): (50, 76), ('loop', 'dotted quarter'): (50, 76),
    ('sting', 'quarter'): (60, 140), ('bed', 'quarter'): (40, 140),
}
LOUDNESS_TOLERANCE = 1.0          # LU around the piece's target
TRUE_PEAK_MAX = -1.0              # dBTP
LRA = (3.0, 14.0)                 # LU: a theme breathes but never jumps the player's volume
OUT_OF_MODE_MAX = 0.08            # share of the pitched notes' time outside the mode
LEAD_RANGE_MAX = 16               # semitones: about an octave and a third, what a voice or a whistle carries
LEAD_STEPS_MIN = 0.45             # share of the lead's intervals that are steps (1-2 semitones) or repeats
LEAD_BIG_LEAPS_MAX = 0.12         # share of leaps wider than a fifth
LEAD_NOTES_A_BAR = (1.5, 9.0)
LEAD_LONGEST_MIN = 1.5            # beats: a line breathes on at least one held note
RHYTHM_RETURN = (0.25, 0.75)      # share of the lead's bars whose rhythm comes back within 8 bars
VOICES_AT_ONCE_MAX = 7            # parts sounding together (a sketch); the rules' "few voices, each doing a lot"
LOW_LIMIT = 48                    # below C3 two notes of one chord sit a fifth or more apart
CHANGES_A_BAR = (0.5, 2.0)        # chords a bar: a theme moves slower than a battle (BN's 1.3-1.9)
BORROWED_MAX = 0.20               # share of the notes' time on notes borrowed from outside the mode, named
# each role's loudness while it plays against the tune's (dB): the tune on top, every other part under it
ROLE_BALANCE = {'counter': (-9, -1), 'harmony': (-16, -4), 'bass': (-12, -1), 'drone': (-18, -5),
                'ostinato': (-14, -3), 'perc': (-16, -3), 'colour': (-20, -5)}
LEADS_APART = 4.0                 # dB: the tune handed from one instrument to the next keeps its level

# the spectrogram: log frequency to 16 kHz, 1024 rows (its FFT follows the rows: fewer smear the bass)
SPECTRUM = 'showspectrumpic=s=1200x1024:mode=combined:color=intensity:scale=log:fscale=log:legend=1:stop=16000'

ROLE_COLOURS = {'lead': (255, 214, 102), 'counter': (130, 200, 255), 'harmony': (150, 130, 210),
                'bass': (110, 220, 140), 'drone': (90, 110, 150), 'ostinato': (240, 140, 200),
                'perc': (230, 230, 230), 'colour': (120, 230, 230)}


def mark(ok: bool) -> str:
    return '' if ok else '  MISS'


# ---- the sound ----------------------------------------------------------------------------------------------------

def decode(path: str):
    """Any file ffmpeg reads, as 48 kHz stereo float frames."""
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-ac', '2', '-ar', '48000', '-f', 'f32le', '-'],
                         check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype='<f4').astype(np.float64).reshape(-1, 2), 48000


def bands(x, sr, edges=(120, 500, 2000, 6000)):
    import numpy as np
    mono = x.mean(axis=1)
    n = 1 << 15
    hop = n // 2
    win = np.hanning(n)
    power = np.zeros(n // 2 + 1)
    for i in range(0, max(1, len(mono) - n), hop):
        seg = mono[i:i + n]
        if len(seg) < n:
            break
        power += np.abs(np.fft.rfft(seg * win)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    total = power[f > 20].sum() or 1.0
    lims = [20, *edges, sr / 2]
    return [100 * power[(f >= lo) & (f < hi)].sum() / total for lo, hi in zip(lims, lims[1:])]


def timbre(x, sr):
    """The median spectral centroid (Hz) and the median flatness between 100 and 6000 Hz over 85 ms frames."""
    import numpy as np
    mono = x.mean(axis=1)
    n = 4096
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f >= 100) & (f <= 6000)
    cents, flats = [], []
    for i in range(0, len(mono) - n, n):
        p = np.abs(np.fft.rfft(mono[i:i + n] * win)) ** 2
        if p[band].sum() < 1e-10:
            continue
        cents.append((f * p).sum() / p.sum())
        pb = p[band] + 1e-20
        flats.append(math.exp(np.mean(np.log(pb))) / np.mean(pb))
    return (float(np.median(cents)) if cents else 0.0), (float(np.median(flats)) if flats else 0.0)


def stereo(x):
    import numpy as np
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    width = 10 * math.log10((np.sum(side ** 2) + 1e-20) / (np.sum(mid ** 2) + 1e-20))
    corr = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) if np.std(x[:, 0]) > 0 and np.std(x[:, 1]) > 0 else 1.0
    return width, corr


def punch(x, sr, bpm):
    """The median over the beats of the 95th against the 10th percentile of a 10 ms loudness, dB (Cyberworld's)."""
    import numpy as np
    mono = x.mean(axis=1)
    h = int(0.01 * sr)
    env = np.sqrt(np.mean(mono[: len(mono) // h * h].reshape(-1, h) ** 2, axis=1))
    beat = max(1, int(60 / bpm / 0.01))
    swings = []
    for i in range(0, len(env) - beat, beat):
        seg = np.sort(env[i:i + beat])
        top, floor = seg[int(0.95 * (len(seg) - 1))], seg[int(0.1 * (len(seg) - 1))]
        if top > 1e-5:
            swings.append(20 * math.log10((top + 1e-9) / (floor + 1e-9)))
    return float(np.median(swings)) if swings else 0.0


def tempo(x, sr, lo=40, hi=200):
    """The beat the onsets keep: spectral flux on 10 ms hops, its autocorrelation's best lag in [lo, hi] bpm."""
    import numpy as np
    mono = x.mean(axis=1)
    n, hop = 2048, 480
    win = np.hanning(n)
    frames = np.lib.stride_tricks.sliding_window_view(mono, n)[::hop] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(0, np.diff(np.log1p(100 * mag), axis=0)).sum(axis=1)
    flux -= flux.mean()
    ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
    fps = sr / hop
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= lo) & (bpm <= hi)
    if not ok.any():
        return 0.0, 0.0
    best = lags[ok][np.argmax(ac[ok])]
    strength = float(ac[best] / (ac[0] + 1e-12))
    return float(60 * fps / best), strength


def beat_strength(x, sr, bpm):
    """The onsets' autocorrelation at the piece's own beat (or its half or double), against its best lag in
    40-200 a minute: near 1 when the beat the piece is written in is the one a listener feels."""
    import numpy as np
    mono = x.mean(axis=1)
    n, hop = 2048, 480
    frames = np.lib.stride_tricks.sliding_window_view(mono, n)[::hop] * np.hanning(n)
    flux = np.maximum(0, np.diff(np.log1p(100 * np.abs(np.fft.rfft(frames, axis=1))), axis=0)).sum(axis=1)
    flux -= flux.mean()
    ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
    fps = sr / hop
    best = max(ac[int(60 * fps / 200):int(60 * fps / 40) + 1])
    own = max(ac[int(round(60 * fps / (bpm * m)))] for m in (0.5, 1, 2) if int(round(60 * fps / (bpm * m))) < len(ac))
    return float(own / best) if best > 0 else 0.0


def sound_lines(x, sr, bpm, beats_per_bar, target=None, music_s=None):
    import numpy as np
    import mix
    lines = []
    il = mix.integrated(x, sr)
    lra = mix.loudness_range(x, sr)
    tp = mix.true_peak(x)
    st = mix.short_term(x, sr)
    lines.append(f'length {len(x) / sr:.1f} s')
    if target is not None:
        lines.append(f'loudness {il:.1f} LUFS (target {target:.0f} +/- {LOUDNESS_TOLERANCE:.0f})'
                     + mark(abs(il - target) <= LOUDNESS_TOLERANCE + 0.05))
    else:
        lines.append(f'loudness {il:.1f} LUFS')
    lines.append(f'loudness range {lra:.1f} LU (rules {LRA[0]:.0f}-{LRA[1]:.0f})'
                 + mark(LRA[0] <= lra <= LRA[1] or target is None))
    lines.append(f'true peak {tp:.1f} dBTP (at most {TRUE_PEAK_MAX:.0f})'
                 + mark(tp <= TRUE_PEAK_MAX + 0.05 or target is None))
    lines.append(f'short-term loudness at most {st.max():.1f} LUFS; PLR {tp - il:.1f} dB')
    span = x[: int((music_s or len(x) / sr) * sr)]
    b = bands(span, sr)
    lines.append('bands % (<120, 120-500, 500-2k, 2k-6k, >6k Hz): ' + ' / '.join(f'{v:.0f}' for v in b))
    c, fl = timbre(span, sr)
    lines.append(f'spectral centre {c:.0f} Hz, flatness {fl:.3f}; air: 2-6 kHz '
                 f'{10 * math.log10((b[3] + 1e-9) / (b[2] + 1e-9)):+.1f} dB against 500-2000 Hz')
    w, corr = stereo(span)
    lines.append(f'stereo: side {w:.1f} dB under middle, correlation {corr:.2f}' + mark(corr > 0.2))
    lines.append(f'punch (the swing inside a beat) {punch(span, sr, bpm):.1f} dB')
    found, strength = tempo(span, sr)
    if found:
        own = beat_strength(span, sr, bpm)
        lines.append(f'onsets: strongest pulse {found:.0f} a minute; at the piece\'s beat ({bpm:g}) '
                     f'{own:.2f} of the strongest')
    if music_s:
        bar_s = beats_per_bar * 60 / bpm
        rows = []
        for i in range(int(math.ceil(music_s / bar_s))):
            seg = x[int(i * bar_s * sr): int((i + 1) * bar_s * sr)]
            if not len(seg):
                break
            rms = math.sqrt(float(np.mean(seg ** 2)))
            pk = float(np.max(np.abs(seg)))
            rows.append(f'{i + 1}:{mix.db(rms):.0f}/{mix.db(pk):.0f}')
        lines.append('bars (loudness/peak dBFS): ' + '  '.join(rows))
    return lines


# ---- the score ----------------------------------------------------------------------------------------------------

def melody(score):
    """The tune: every lead part's notes as one line (a tune handed from one instrument to the next), leaving out
    a part that doubles another."""
    parts = [p for p in score.parts if p.role == 'lead' and p.notes and not p.doubles]
    notes = sorted(((n, p.name) for p in parts for n in p.notes), key=lambda e: (e[0].start, -e[0].key))
    line, owner = [], []
    for n, name in notes:   # where two leads overlap, the higher one carries the tune
        if line and n.start < line[-1].start + 1e-6:
            continue
        line.append(n)
        owner.append(name)
    melody.owner = owner
    return parts, line


def bar_rhythm(notes, score, bar):
    """A bar's onsets on a grid of twelfths of a beat (sixteenths and triplets alike)."""
    bpb = score.beats_per_bar
    return tuple(round((n.start - bar * bpb) * 12) for n in notes if bar * bpb <= n.start < (bar + 1) * bpb)


def score_lines(score):
    import score as sc
    lines = []
    lo, hi = TEMPO.get((score.kind, score.beat_unit), (40, 200))
    lines.append(f'tempo {score.bpm:g} a minute ({score.beat_unit}, {score.meter[0]}/{score.meter[1]}; rules for a '
                 f'{score.kind} {lo}-{hi})' + mark(lo <= score.bpm <= hi))
    pitched = [p for p in score.parts if p.role != 'perc']
    scale = {(sc.key(score.tonic + '4') + iv) % 12 for iv in sc.MODES[score.mode]}
    borrowed = {sc.key(n + '4') % 12 for n in score.borrowed}
    total = sum(n.length for p in pitched for n in p.notes) or 1
    outside, lent = collections.Counter(), collections.Counter()
    for p in pitched:
        for n in p.notes:
            if n.key % 12 in borrowed:
                lent[sc.PITCH_NAMES[n.key % 12]] += n.length
            elif n.key % 12 not in scale:
                outside[sc.PITCH_NAMES[n.key % 12]] += n.length
    share = sum(outside.values()) / total
    lines.append(f'{score.tonic} {score.mode}: {100 * share:.0f}% of the notes\' time outside the mode'
                 + (f' ({", ".join(f"{k} {v:g} beats" for k, v in outside.most_common(4))})' if outside else '')
                 + mark(share <= OUT_OF_MODE_MAX))
    if borrowed:
        lshare = sum(lent.values()) / total
        lines.append(f'  borrowed on purpose ({", ".join(score.borrowed)}): {100 * lshare:.0f}% of the time'
                     + mark(lshare <= BORROWED_MAX))
    parts, ns = melody(score)
    if ns:
        keys = [n.key for n in ns]
        owner = melody.owner
        # intervals inside one instrument's statement: a hand-off to another is no leap a voice sings
        ivs = [b - a for a, b, oa, ob in zip(keys, keys[1:], owner, owner[1:]) if oa == ob]
        steps = sum(1 for i in ivs if abs(i) <= 2) / (len(ivs) or 1)
        big = sum(1 for i in ivs if abs(i) > 7) / (len(ivs) or 1)
        span = max(max(n.key for n in p.notes) - min(n.key for n in p.notes) for p in parts)
        bars_played = sorted({int(n.start // score.beats_per_bar) for n in ns})
        per_bar = len(ns) / (len(bars_played) or 1)
        longest = max(n.length for n in ns)
        names = ', '.join(f'{p.name} ({p.inst})' for p in parts)
        lines.append(f'the tune ({names}): {sc.name_of(min(keys))}-{sc.name_of(max(keys))}; the widest statement '
                     f'{span} semitones' + mark(span <= LEAD_RANGE_MAX))
        lines.append(f'  steps and repeats {100 * steps:.0f}% (at least {100 * LEAD_STEPS_MIN:.0f}), leaps past a '
                     f'fifth {100 * big:.0f}% (at most {100 * LEAD_BIG_LEAPS_MAX:.0f})'
                     + mark(steps >= LEAD_STEPS_MIN and big <= LEAD_BIG_LEAPS_MAX))
        lines.append(f'  {per_bar:.1f} notes a bar over {len(bars_played)} bars, the longest {longest:g} beats'
                     + mark(LEAD_NOTES_A_BAR[0] <= per_bar <= LEAD_NOTES_A_BAR[1] and longest >= LEAD_LONGEST_MIN))
        rhythms = {b: bar_rhythm(ns, score, b) for b in bars_played}
        back = sum(1 for b in bars_played if any(rhythms.get(o) == rhythms[b] for o in range(b - 8, b + 9) if o != b))
        share_back = back / (len(bars_played) or 1)
        same_next = sum(1 for b in bars_played if rhythms.get(b + 1) == rhythms[b] and rhythms[b])
        lines.append(f'  a bar\'s rhythm back within 8 bars: {100 * share_back:.0f}% '
                     f'(rules {100 * RHYTHM_RETURN[0]:.0f}-{100 * RHYTHM_RETURN[1]:.0f}); the same rhythm in the next '
                     f'bar {same_next} times' + mark(RHYTHM_RETURN[0] <= share_back <= RHYTHM_RETURN[1]))
        # the call: the tune's first three notes (their intervals and lengths), found again later in any key
        def shape(i):
            seg = ns[i:i + 3]
            return tuple(b.key - a.key for a, b in zip(seg, seg[1:])), tuple(round(n.length * 12) for n in seg[:2])
        call = shape(0)
        again = [i for i in range(1, len(ns) - 2) if shape(i) == call]
        where = [f'bar {int(ns[i].start // score.beats_per_bar) + 1}' for i in again]
        lines.append(f'  the call ({" ".join(sc.name_of(n.key) for n in ns[:3])}) comes back: '
                     + (', '.join(where) if where else 'never') + mark(bool(again)))
    # voices at once, on a half-beat grid
    end = score.bars * score.beats_per_bar
    counts = []
    t = 0.0
    while t < end:
        counts.append(sum(1 for p in score.parts if not p.doubles
                          and any(n.start <= t + 0.01 < n.start + n.length for n in p.notes)))
        t += 0.5
    lines.append(f'voices at once (a doubling is none): at most {max(counts)}, '
                 f'on average {sum(counts) / len(counts):.1f} '
                 f'(at most {VOICES_AT_ONCE_MAX})' + mark(max(counts) <= VOICES_AT_ONCE_MAX))
    heads = sorted(b for b, _ in score.sections) or [0]
    late = []
    for p in score.parts:
        if not p.notes:
            continue
        first = min(n.start for n in p.notes)
        b = first / score.beats_per_bar
        # at a head, or a pickup of up to two beats into one (a swell, a colour, up to a bar)
        early = 1.0 if p.role == 'colour' else 2.0 / score.beats_per_bar
        if not any(-1e-6 <= h - b <= early + 1e-6 for h in heads):
            late.append(f'{p.name} (bar {int(b) + 1})')
    lines.append('every part enters at a section\'s head' + ('' if not late else f': not {", ".join(late)}')
                 + mark(not late))
    # low intervals: notes sounding together below LOW_LIMIT closer than a fifth
    mud = set()
    t = 0.0
    while t < end:
        low = sorted({n.key for p in pitched for n in p.notes if n.start <= t + 0.01 < n.start + n.length
                      and n.key < LOW_LIMIT})
        for a, b in zip(low, low[1:]):
            if 0 < b - a < 7:
                mud.add(f'bar {int(t // score.beats_per_bar) + 1} {sc.name_of(a)}-{sc.name_of(b)}')
        t += 0.5
    lines.append(f'low intervals closer than a fifth under C3: {len(mud)}'
                 + (f' ({", ".join(sorted(mud)[:6])})' if mud else '')
                 + mark(not mud))
    if score.chords:
        rubs, strong = [], 0
        harmony = [p for p in pitched if p.role != 'lead']
        for lead in [melody(score)[1]]:
            for n in lead:
                on_beat = abs(n.start - round(n.start)) < 1e-6
                if not on_beat and n.length < 1:
                    continue
                strong += 1
                name = score.chord_at(n.start + 0.01)
                under = {m.key for p in harmony for m in p.notes if m.start <= n.start + 0.01 < m.start + m.length}
                # a minor second or a minor ninth against a note that sounds (a major seventh over a root is a
                # colour, and a ninth over a minor chord's root is too); with nothing sounding, the chord's name
                if under:
                    rub = any(abs(n.key - k) in (1, 13) for k in under)
                else:
                    pcs = sc.chord_pcs(name) if name else set()
                    rub = n.key % 12 not in pcs and any((n.key - pc) % 12 == 1 for pc in pcs)
                if rub:
                    rubs.append(f'bar {int(n.start // score.beats_per_bar) + 1} {sc.name_of(n.key)} over {name}')
        lines.append(f'lead notes a minor second or ninth from a sounding note, on the beat or held: '
                     f'{len(rubs)} of {strong}'
                     + (f': {", ".join(rubs[:8])}' if rubs else '') + ' (keep a rub only as a colour on purpose)')
        names = [c for b in range(score.bars) for c in score.chords.get(b, ())]
        changes = sum(1 for a, b in zip(names, names[1:]) if a != b)
        cab = changes / max(1, score.bars - 1)
        lines.append(f'chord changes a bar {cab:.2f} (rules {CHANGES_A_BAR[0]}-{CHANGES_A_BAR[1]})'
                     + mark(CHANGES_A_BAR[0] <= cab <= CHANGES_A_BAR[1]))
    last_bar = score.bars - 1
    rings = [p.name for p in pitched for n in p.notes
             if n.start >= last_bar * score.beats_per_bar - 1e-6 and n.length >= 2]
    lines.append('the ending rings (a note held two beats or more in the last bar)'
                 + ('' if rings else ': nothing held')
                 + mark(bool(rings)))
    return lines


def stem_lines(stems_dir: str, score) -> list[str]:
    """Each part as placed in the mix (render.py --stems): its loudness over the bars it plays, its peak, and the
    band its energy is in, so a part that covers the others, or that nobody would hear, shows by number."""
    import numpy as np
    import mix
    rows = []
    for p in score.parts:
        path = os.path.join(stems_dir, f'{p.name}.wav')
        if not p.notes or not os.path.exists(path):
            continue
        x, sr = mix.read_wav(path)
        t0 = min(n.start for n in p.notes) * 60 / score.bpm
        t1 = max(n.start + n.length for n in p.notes) * 60 / score.bpm
        seg = x[int(t0 * sr): int(t1 * sr) + 1]
        loud = mix.integrated(seg, sr) if len(seg) > sr // 2 else -120.0
        b = bands(seg, sr) if len(seg) > 1 << 15 else [0] * 5
        main = ['<120', '120-500', '500-2k', '2k-6k', '>6k'][int(np.argmax(b))]
        main += f' Hz, {b[3] + b[4]:.0f}% above 2k'
        rows.append((loud, p, main, mix.db(float(np.max(np.abs(x))))))
    leads = [(loud, p) for loud, p, _, _ in rows if p.role == 'lead' and not p.doubles]
    tune = max((loud for loud, _ in leads), default=None)
    out = ['parts as placed (render.py --stems), each while it plays, against the tune\'s loudest statement:']
    for loud, p, main, peak in sorted(rows, key=lambda r: -r[0]):
        rel = loud - tune if tune is not None else 0.0
        rule = ROLE_BALANCE.get(p.role)
        ok = True
        if p.role == 'lead' and not p.doubles:
            ok = rel >= -LEADS_APART
            want = f'within {LEADS_APART:g} of the loudest lead'
        elif rule and not p.doubles:
            ok = rule[0] <= rel <= rule[1]
            want = f'{rule[0]} to {rule[1]}'
        else:
            want = 'a doubling' if p.doubles else ''
        out.append(f'  {p.name:12s} {loud:6.1f} LUFS ({rel:+5.1f}; {p.role}: {want}), peak {peak:5.1f} dBFS, '
                   f'most in {main}' + mark(ok))
    return out


def report(wav: str, score, mod=None) -> str:
    x, sr = decode(wav)
    out = [f'== {score.title}', '-- the sound']
    out += sound_lines(x, sr, score.bpm, score.beats_per_bar, score.loudness, score.length_s)
    stems_dir = wav[:-4] + '.stems'
    if os.path.isdir(stems_dir):
        out += stem_lines(stems_dir, score)
    out.append('-- the score')
    out += score_lines(score)
    misses = sum(1 for line in out if line.endswith('MISS'))
    out.append(f'-- {misses} rule{"s" if misses != 1 else ""} missed' if misses else '-- every rule met')
    return '\n'.join(out)


# ---- pictures -----------------------------------------------------------------------------------------------------

def pictures(wav: str, score, base: str) -> None:
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-lavfi', SPECTRUM, base + '.spectrum.png'],
                   check=True)
    roll(score, base + '.roll.png')


def roll(score, path: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    import score as sc
    keys = [n.key for p in score.parts if p.role != 'perc' for n in p.notes] or [60]
    lo, hi = min(keys) - 2, max(keys) + 2
    px, row, top, left = 36, 6, 40, 70
    beats = score.bars * score.beats_per_bar
    w, h = left + int(beats * px) + 20, top + (hi - lo + 1) * row + 60
    im = Image.new('RGB', (w, h), (14, 16, 24))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    except OSError:
        font = ImageFont.load_default()
    for k in range(lo, hi + 1):
        y = top + (hi - k) * row
        if k % 12 == 0:
            d.line([(left, y + row), (w, y + row)], fill=(40, 44, 60))
            d.text((6, y - 2), sc.name_of(k), fill=(150, 150, 170), font=font)
    for b in range(score.bars + 1):
        x = left + int(b * score.beats_per_bar * px)
        d.line([(x, top), (x, h - 50)], fill=(70, 74, 96))
        if b < score.bars:
            names = score.chords.get(b, ())
            for i, name in enumerate(names):
                d.text((x + 4 + i * score.beats_per_bar * px / len(names), 4), name, fill=(220, 220, 230), font=font)
    for b, name in score.sections:
        d.text((left + int(b * score.beats_per_bar * px) + 4, 20), name, fill=(255, 200, 120), font=font)
    order = ['drone', 'harmony', 'bass', 'perc', 'colour', 'ostinato', 'counter', 'lead']
    for p in sorted(score.parts, key=lambda p: order.index(p.role) if p.role in order else 0):
        colour = ROLE_COLOURS.get(p.role, (200, 200, 200))
        for n in p.notes:
            x0 = left + int(n.start * px)
            x1 = max(x0 + 2, left + int((n.start + n.length) * px) - 1)
            if p.role == 'perc':
                y = h - 46 + (n.key % 6) * 6
            else:
                y = top + (hi - n.key) * row
            d.rectangle([x0, y, x1, y + row - 2], fill=colour)
    legend = '  '.join(f'{r}' for r in ROLE_COLOURS)
    x = left
    for r, c in ROLE_COLOURS.items():
        d.rectangle([x, h - 12, x + 10, h - 4], fill=c)
        d.text((x + 14, h - 16), r, fill=(200, 200, 210), font=font)
        x += 90
    im.save(path)


def main(argv: list[str]) -> int:
    import render
    if not render.inside():
        return render.in_image('check.py', argv)
    if argv[:1] == ['--ref']:
        x, sr = decode(argv[1])
        bpm = float(argv[argv.index('--bpm') + 1]) if '--bpm' in argv else (tempo(x, sr)[0] or 90.0)
        print(f'== {os.path.basename(argv[1])} (a reference, never committed)')
        for line in sound_lines(x, sr, bpm, 4):
            print(line)
        import mix
        st = mix.short_term(x, sr)
        print('short-term loudness every 10 s: ' + ' '.join(f'{v:.0f}' for v in st[::100]))
        return 0
    out = render.DEFAULT_OUT
    if '--out' in argv:
        i = argv.index('--out')
        out = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    for name in argv:
        mod, s = render.load_piece(name)
        wav = os.path.join(out, f'{name}.wav')
        print(report(wav, s, mod))
        pictures(wav, s, os.path.join(out, name))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
