#!/usr/bin/env python3
"""A handover from one rendered piece to another as the front end's AudioStreamInteractive would play it, to hear.

    python3 art_src/music/handover.py FROM TO --after-bar N [--lead 3] [--fade-beats 1] [--out DIR] [--from-dir DIR]

FROM and TO are pieces already rendered into DIR (render.py's; .build/music/ by default; FROM may be in
--from-dir). The state changes while FROM plays its bar N (1-based); the transition waits for the next bar line (TRANSITION_FROM_TIME_NEXT_BAR), where FROM
fades out over `--fade-beats` of its beats (FADE_OUT) and TO starts from its beginning at full level. Written as
DIR/FROM_to_TO.wav and .mp3: FROM's `--lead` bars before the bar line, then TO through its end (a loop once round, a
sting with its ring), with a check of its loudness, true peak and the bars either side of the bar line, and a
spectrogram. The settings are the ones SKILL.md's Placing the hub's music asks F4 to give the transitions.
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render  # noqa: E402


def main(argv: list[str]) -> int:
    if not render.inside():
        return render.in_image('handover.py', argv)
    import numpy as np
    import mix
    import check

    def opt(flag, default, cast):
        return cast(argv[argv.index(flag) + 1]) if flag in argv else default
    names = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or not argv[i - 1].startswith('--'))]
    if len(names) != 2 or '--after-bar' not in argv:
        print(__doc__)
        return 2
    src, dst = names
    after = opt('--after-bar', 0, int)
    lead = opt('--lead', 3, int)
    fade_beats = opt('--fade-beats', 1.0, float)
    out_dir = os.path.abspath(opt('--out', render.DEFAULT_OUT, str))
    from_dir = os.path.abspath(opt('--from-dir', out_dir, str))       # (the hub's theme lives in .build/music/)
    _, s_from = render.load_piece(src)
    _, s_to = render.load_piece(dst)
    a, sr = mix.read_wav(os.path.join(from_dir, f'{src}.wav'))
    b, _ = mix.read_wav(os.path.join(out_dir, f'{dst}.wav'))
    bar = s_from.beats_per_bar * s_from.seconds_per_beat
    cut = int(round(after * bar * sr))
    start = max(0, cut - int(round(lead * bar * sr)))
    fade = int(round(fade_beats * s_from.seconds_per_beat * sr))
    head = a[start:cut + fade].copy()
    ramp = np.cos(np.linspace(0, np.pi / 2, fade)) ** 2 if fade else np.ones(0)
    head[len(head) - fade:] *= ramp[:, None]
    n = (cut - start) + len(b)
    out = np.zeros((max(n, len(head)), 2))
    out[:len(head)] += head
    out[cut - start:cut - start + len(b)] += b
    base = os.path.join(out_dir, f'{src}_to_{dst}')
    mix.write_wav(base + '.wav', out, sr, 24)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', base + '.wav', '-c:a', 'libmp3lame', '-q:a', '2',
                    base + '.mp3'], check=True)

    def level(x):
        return mix.db(float(np.sqrt(np.mean(x ** 2)))) if len(x) else -120.0
    bar_n = int(round(bar * sr))
    lines = [f'== {src} to {dst}: {src} bars {after - lead + 1}-{after}, then {dst} on the bar line at '
             f'{(cut - start) / sr:.1f} s (FROM_TIME_NEXT_BAR; {src} fading out over {fade_beats:g} beat(s))',
             f'length {len(out) / sr:.1f} s; loudness {mix.integrated(out, sr):.1f} LUFS; true peak '
             f'{mix.true_peak(out):.1f} dBTP' + check.mark(mix.true_peak(out) <= -1.0),
             f'the bar before the bar line {level(out[cut - start - bar_n:cut - start]):.1f} dBFS, the bar after '
             f'{level(out[cut - start:cut - start + bar_n]):.1f} dBFS (rms)']
    report = '\n'.join(lines)
    with open(base + '.check.txt', 'w') as f:
        f.write(report + '\n')
    print(report)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', base + '.wav', '-lavfi', check.SPECTRUM,
                    base + '.spectrum.png'], check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
