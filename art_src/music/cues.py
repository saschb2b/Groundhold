#!/usr/bin/env python3
"""The front end's UI cues from real instruments: each cue in cues.json played by the palette's samples (plucks,
bells, a horn, wood and skin), in a small room, as a mono sound in the style sfx/ holds (asset_style.json: 44.1 kHz,
mono, its peak under -1 dBFS, no more than 20 ms of silence before it, at most 1.6 s).

    python3 art_src/music/cues.py [NAME ...]                # into .build/music-cues/, to be heard
    python3 art_src/music/cues.py --dest sfx [NAME ...]     # into sfx/, recorded in asset_manifest.json

Beside art_src/sfx/sfx.py, whose synthesized bells and swarm stay where they are: this is the path for a cue that
should sound like an instrument. A cue goes into sfx/ only after the owner has heard it (the music skill's gate 5);
until then it is rendered to .build/ for his ear. Runs in the music image (render.py starts it there).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render  # noqa: E402

SPEC = 'art_src/music/cues.json'


def render_cue(name: str, cue: dict, room_seconds: float, rate: int):
    import numpy as np
    from scipy import signal
    import mix
    import score as sc
    s = sc.Score(title=name, bpm=60, bars=1 + int(cue['duration'] // 4), tail=1.0, hall_seconds=room_seconds)
    for i, ev in enumerate(cue['events']):
        key = ev['key']
        s.part(f'{i}-{ev["inst"]}', ev['inst'], role='colour', hall=cue.get('room', 0.2)) \
            .play(ev['at'], ev['length'], key, ev['vel'])
    lost = render.coverage(s)
    if lost:
        raise SystemExit(f'{name}: notes that find no sample (a cue normalised from silence would be noise): {lost}')
    work = os.path.join(render.CACHE, 'work', 'cues')
    os.makedirs(work, exist_ok=True)
    x = render.mixdown(s, work)
    mono = x.mean(axis=1)
    # no more than a few ms of silence before the sound
    above = np.nonzero(np.abs(mono) > 10 ** (-50 / 20) * np.max(np.abs(mono)))[0]
    start = max(0, int(above[0]) - int(0.002 * render.RATE)) if len(above) else 0
    mono = mono[start:start + int(cue['duration'] * render.RATE)]
    mono = signal.resample_poly(mono, rate, render.RATE) if rate != render.RATE else mono
    n = len(mono)
    fade_in, fade_out = int(0.002 * rate), min(n, int(0.06 * rate))
    mono[:fade_in] *= np.linspace(0, 1, fade_in)
    mono[n - fade_out:] *= np.linspace(1, 0, fade_out)
    mono *= mix.undb(cue['peak_db']) / (np.max(np.abs(mono)) + 1e-12)
    return mono


def main(argv: list[str]) -> int:
    if not render.inside():
        return render.in_image('cues.py', argv)
    import mix
    dest = None
    if '--dest' in argv:
        i = argv.index('--dest')
        dest = argv[i + 1]
        del argv[i:i + 2]
    spec = json.load(open(os.path.join(render.ROOT, SPEC)))
    names = argv or list(spec['cues'])
    out_dir = os.path.join(render.ROOT, dest) if dest else os.path.join(render.ROOT, '.build', 'music-cues')
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name in names:
        cue = spec['cues'][name]
        mono = render_cue(name, cue, spec.get('room_seconds', 0.9), spec.get('rate', 44100))
        path = os.path.join(out_dir, f'{name}.wav')
        before = open(path, 'rb').read() if os.path.exists(path) else None
        mix.write_wav(path, mono[:, None], spec.get('rate', 44100), 16)
        written.append((path, before is not None and open(path, 'rb').read() == before))
        print(f'wrote {os.path.relpath(path, render.ROOT)}: {len(mono) / spec.get("rate", 44100):.2f} s, '
              f'peak {cue["peak_db"]} dBFS, {cue["note"]}')
    if dest:
        from pathlib import Path
        sys.path.insert(0, os.path.join(render.ROOT, 'art_src', 'ui'))
        from console import record
        project = Path(render.ROOT)
        script = 'art_src/music/cues.py'
        for path, same in written:
            p = Path(path)
            record(project, [p], {'tool': 'script', 'script': script, 'spec': SPEC, 'sound': p.stem,
                                  'regen': f'python3 {script} --dest {dest} {p.stem}'}, keep={p} if same else set())
    else:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + sum((['-i', p] for p, _ in written), [])
                       + ['-filter_complex', ''.join(f'[{i}:a]apad=pad_dur=0.6[a{i}];' for i in range(len(written)))
                          + ''.join(f'[a{i}]' for i in range(len(written))) + f'concat=n={len(written)}:v=0:a=1',
                          os.path.join(out_dir, 'all_cues.mp3')], check=True)
        print('and', os.path.relpath(os.path.join(out_dir, 'all_cues.mp3'), render.ROOT), '(every cue in turn)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
