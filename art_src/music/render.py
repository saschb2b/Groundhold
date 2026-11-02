#!/usr/bin/env python3
"""Renders a piece of Groundhold's music from its code to sound, in the music image (art_src/music/Dockerfile).

    python3 art_src/music/render.py PIECE [PIECE ...] [--out DIR] [--stems] [--no-check]
    python3 art_src/music/render.py --verify                  # every palette instrument: its samples and range
    python3 art_src/music/render.py --calibrate               # levels.json: each instrument's trim to one level
    python3 art_src/music/render.py --keys INSTRUMENT         # an unpitched set's keys and the samples they play
    python3 art_src/music/render.py --note INSTRUMENT KEY [VELOCITY] [SECONDS] [--out DIR]

PIECE is a module of art_src/music/pieces/ (causeway_sketch_a). Each of its parts is written as MIDI and rendered
alone, dry, at 48 kHz: an SFZ instrument by sfizz, a soundfont preset by FluidSynth. The parts are mixed (mix.py:
gain, a dynamics curve, filters, pan and width, a seeded hall), the master brought to the piece's loudness under a
-1 dBTP ceiling, and written to DIR (.build/music/ by default) as NAME.wav (48 kHz, 24-bit stereo), NAME.ogg (what
the game would import), NAME.mp3 (for the owner's ear) and NAME.mid (every part, for a look in any sequencer), with
the check by numbers (check.py: NAME.check.txt, NAME.spectrum.png, NAME.roll.png). `--stems` also writes each part
as placed (DIR/NAME.stems/). A stem is cached in .build/music-cache/ by its MIDI, instrument and renderer, so a
change to one part renders that part again.

Run from the host, it builds the image if it is missing (a few minutes; it fetches the libraries) and runs itself
inside it with the checkout mounted, as the user, so what it writes is the user's.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
IMAGE = 'groundhold-music'
RATE = 48000
DEFAULT_OUT = os.path.join(ROOT, '.build', 'music')
CACHE = os.path.join(ROOT, '.build', 'music-cache')
RENDERERS = 'sfizz 1.2.3 (float) / fluidsynth 2.4.4'   # part of a stem's cache key

sys.path.insert(0, HERE)


def inside() -> bool:
    return bool(os.environ.get('GROUNDHOLD_SOUNDS')) and os.path.exists('/usr/local/bin/sfizz_render')


def ensure_image() -> None:
    if subprocess.call(['docker', 'image', 'inspect', IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        print(f'building {IMAGE} (the libraries are fetched once, about 1.5 GB)', file=sys.stderr)
        subprocess.check_call(['docker', 'build', '-t', IMAGE, HERE])


def in_image(script: str, args: list[str]) -> int:
    """Runs art_src/music/<script> in the image with the checkout at /src (paths under it map across)."""
    ensure_image()
    mapped = []
    for a in args:
        if os.path.isabs(a) and os.path.abspath(a).startswith(ROOT + os.sep):
            a = '/src/' + os.path.relpath(a, ROOT)
        elif os.path.isabs(a):
            raise SystemExit(f'{a}: outside the checkout, which the image mounts')
        mapped.append(a)
    cmd = ['docker', 'run', '--rm', '--name', f'groundhold-music-{os.getpid()}', '-u', f'{os.getuid()}:{os.getgid()}',
           '-e', 'HOME=/tmp', '-v', f'{ROOT}:/src', '-w', '/src', IMAGE,
           'python3', f'art_src/music/{script}'] + mapped
    return subprocess.call(cmd)


# ---- inside the image ---------------------------------------------------------------------------------------------

def load_piece(name: str):
    mod = importlib.import_module('pieces.' + name)
    return mod, mod.score()


def stem(score, part, work: str) -> str:
    """Renders one part dry to a float WAV (cached), and returns its path."""
    import palette
    import score as sc
    kind = palette.kind_of(part.inst)
    program = palette.INSTRUMENTS[part.inst][1] if kind == 'sf2' else None
    tail_beats = score.tail * score.bpm / 60 + 1
    midi = sc.midi_bytes([sc.part_events(score, part, 0, program, tail_beats)])
    path = palette.path_of(part.inst)
    h = hashlib.sha256(midi + path.encode() + RENDERERS.encode() + str(RATE).encode()).hexdigest()[:20]
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f'{part.inst}-{h}.wav')
    if os.path.exists(out):
        return out
    mid = os.path.join(work, f'{part.name}.mid')
    with open(mid, 'wb') as f:
        f.write(midi)
    tmp = out + '.tmp.wav'
    if kind == 'sfz':
        cmd = ['sfizz_render', '--sfz', path, '--midi', mid, '--wav', tmp, '-s', str(RATE), '-q', '3', '-p', '256',
               '-b', '512']
    else:
        cmd = ['fluidsynth', '-ni', '-q', '-F', tmp, '-r', str(RATE), '-O', 'float', '-T', 'wav',
               '-o', 'synth.reverb.active=0', '-o', 'synth.chorus.active=0', '-g', '1.0', path, mid]
    # (sfizz says on every block that a container may not raise its threads' priority: kept quiet unless it fails)
    run = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if run.returncode:
        raise SystemExit(f'{part.name}: {" ".join(cmd[:1])} failed:\n{run.stderr[-2000:]}')
    os.replace(tmp, out)
    return out


def coverage(score) -> list[str]:
    """Notes no sample answers (a note outside its instrument's range or velocity layers plays silence)."""
    import palette
    import sfz
    lost = []
    for part in score.parts:
        if palette.kind_of(part.inst) != 'sfz':
            continue
        regs = sfz.regions(palette.path_of(part.inst))
        for n in part.notes:
            if not sfz.covers(regs, n.key, n.vel):
                lost.append(f'{part.name} ({part.inst}) key {n.key} vel {n.vel} at beat {n.start:g}')
    return lost


LEVELS = os.path.join(HERE, 'levels.json')
REFERENCE_LUFS = -30.0     # every instrument's calibration phrase, at velocity 80, is brought here


def levels() -> dict:
    import json
    if not os.path.exists(LEVELS):
        return {}
    return json.load(open(LEVELS))['trim_db']


def calibration_notes(inst: str) -> list[int]:
    """The keys an instrument's level is read at: every fourth semitone across its sampled range (a pitched one),
    or its main stroke (an unpitched set)."""
    import palette
    import sfz
    if palette.kind_of(inst) == 'sf2':
        return list(range(48, 85, 4))
    regs = sfz.regions(palette.path_of(inst))
    lo, hi = sfz.key_range(regs)
    if hi - lo < 8:
        return [UNPITCHED_MAIN.get(inst, lo)]
    return [k for k in range(lo, hi + 1, 4) if sfz.covers(regs, k, 80)]


UNPITCHED_MAIN = {'frame_drum': 61, 'tom': 62, 'bass_drum': 60, 'snare_rope': 62, 'sus_cymbal': 68, 'triangle': 60,
                  'woodblock': 60, 'hand_bells': 60, 'mark_tree': 63, 'ocean_drum': 60}


def calibrate() -> int:
    """Writes levels.json: for each instrument, the trim (dB) that brings the median of its notes at velocity 80 to
    REFERENCE_LUFS, so a piece's gain_db says what the mix means (the lead at 0, a pad under it) and not how loud a
    library recorded its samples (VSCO's contrabass sits 10 dB under its horn, its glockenspiel 24); and how loud its
    low, middle and high thirds are against that median (a flute's low octave is weak, as it is in an orchestra)."""
    import json
    import mix
    import score as sc
    import palette
    work = os.path.join(CACHE, 'work', 'calibrate')
    os.makedirs(work, exist_ok=True)
    trims, registers = {}, {}
    for inst in palette.INSTRUMENTS:
        keys = calibration_notes(inst)
        s = sc.Score(title=f'calibrate {inst}', bpm=60, bars=len(keys), tail=1.0)
        p = s.part('note', inst, hall=0.0)
        for i, k in enumerate(keys):
            p.play(i * 4, 2.5, k, 80)
        x = mixdown(s, work, trim=False, hall=False)
        each = [mix.integrated(x[int(i * 4 * RATE): int((i * 4 + 3.5) * RATE)], RATE) for i in range(len(keys))]
        each = [v for v in each if v > -100] or [-100.0]
        med = sorted(each)[len(each) // 2]
        trims[inst] = round(REFERENCE_LUFS - med, 1)
        third = max(1, len(each) // 3)
        registers[inst] = [round(sum(part) / len(part) - med, 1) for part in
                           (each[:third], each[third:len(each) - third] or each, each[len(each) - third:])]
        print(f'{inst:15s} median {med:6.1f} LUFS -> trim {trims[inst]:+5.1f} dB; low/middle/high '
              + ' / '.join(f'{v:+.0f}' for v in registers[inst]))
    with open(LEVELS, 'w') as f:
        json.dump({'note': 'Written by `python3 art_src/music/render.py --calibrate`: each instrument\'s trim to '
                           f'{REFERENCE_LUFS:g} LUFS for the median of its notes at velocity 80 (every fourth '
                           'semitone across its range), and its low, middle and high thirds against that median, dB. '
                           'Never edited by hand.',
                   'reference_lufs': REFERENCE_LUFS, 'trim_db': trims, 'register_db': registers}, f, indent=1,
                  sort_keys=True)
        f.write('\n')
    print('wrote', os.path.relpath(LEVELS, ROOT))
    return 0


def mixdown(score, work: str, stems_dir: str | None = None, trim: bool = True, hall: bool = True):
    import numpy as np
    import mix
    n = int(round((score.length_s + score.tail) * RATE))
    trims = levels() if trim else {}
    dry = np.zeros((n, 2))
    send = np.zeros((n, 2))
    for part in score.parts:
        if not part.notes:
            continue
        x, sr = mix.read_wav(stem(score, part, work))
        if sr != RATE:
            raise SystemExit(f'{part.name}: rendered at {sr} Hz')
        if len(x) < n:
            x = np.concatenate([x, np.zeros((n - len(x), 2))])
        x = x[:n]
        x = x * mix.curve(n, RATE, score.bpm, part.dyn)[:, None]
        x = mix.filtered(x, RATE, part.hp, part.lp)
        x = mix.shelf(x, RATE, part.air, 3000.0)
        x = mix.place(x, part.pan, part.width) * mix.undb(part.gain_db + trims.get(part.inst, 0.0))
        dry += x
        send += x * part.hall
        if stems_dir:
            mix.write_wav(os.path.join(stems_dir, f'{part.name}.wav'), x, RATE)
    if not hall:
        return dry
    ir = mix.hall_ir(RATE, score.hall_seconds, air=score.hall_air, early=score.early)
    wet = mix.filtered(mix.convolve(send, ir), RATE, hp=140.0)
    # a gentle high-pass on the whole: nothing under 25 Hz is music (a drum skin's or a room's rumble)
    out = mix.filtered(dry + wet, RATE, hp=25.0)
    fade = int(0.6 * RATE)
    out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
    return out


def render_piece(name: str, out_dir: str, stems: bool, check: bool) -> None:
    import mix
    import score as sc
    import palette
    mod, s = load_piece(name)
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(CACHE, 'work', name)
    os.makedirs(work, exist_ok=True)
    lost = coverage(s)
    if lost:
        print(f'{name}: {len(lost)} notes find no sample:\n  ' + '\n  '.join(lost[:20]), file=sys.stderr)
        raise SystemExit(1)
    stems_dir = os.path.join(out_dir, f'{name}.stems') if stems else None
    if stems_dir:
        os.makedirs(stems_dir, exist_ok=True)
    x = mixdown(s, work, stems_dir)
    y, gain = mix.mastered(x, RATE, s.loudness)
    wav = os.path.join(out_dir, f'{name}.wav')
    mix.write_wav(wav, y, RATE, 24)
    tracks = []
    for i, part in enumerate(s.parts):
        program = palette.INSTRUMENTS[part.inst][1] if palette.kind_of(part.inst) == 'sf2' else None
        ch = i if i < 9 else i + 1
        tracks.append(sc.part_events(s, part, ch % 16, program))
    with open(os.path.join(out_dir, f'{name}.mid'), 'wb') as f:
        f.write(sc.midi_bytes(tracks))
    for ext, codec in (('ogg', ['-c:a', 'libvorbis', '-q:a', '6']), ('mp3', ['-c:a', 'libmp3lame', '-q:a', '2'])):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav] + codec
                       + [os.path.join(out_dir, f'{name}.{ext}')], check=True)
    print(f'{name}: {s.length_s + s.tail:.1f} s, master gain {gain:+.1f} dB -> {os.path.relpath(wav, ROOT)}')
    if check:
        import check as ck
        report = ck.report(wav, s, mod)
        with open(os.path.join(out_dir, f'{name}.check.txt'), 'w') as f:
            f.write(report + '\n')
        print(report)
        ck.pictures(wav, s, os.path.join(out_dir, name))


def verify() -> int:
    import palette
    import sfz
    bad = 0
    for inst, (lib, where, why) in palette.INSTRUMENTS.items():
        path = palette.path_of(inst)
        if not os.path.exists(path):
            print(f'{inst:15s} MISSING {path}')
            bad += 1
            continue
        if palette.kind_of(inst) == 'sf2':
            print(f'{inst:15s} sf2 preset {where}')
            continue
        regs = sfz.regions(path)
        miss = sfz.missing_samples(regs)
        lo, hi = sfz.key_range(regs) if regs else (0, 0)
        vels = sorted({(r.lovel, r.hivel) for r in regs})
        print(f'{inst:15s} {len(regs):4d} regions, keys {lo}-{hi}, {len(vels)} velocity layers'
              + (f', {len(miss)} samples MISSING: {miss[:3]}' if miss else ''))
        bad += bool(miss) or not regs
    return 1 if bad else 0


def keys(inst: str) -> int:
    import palette
    import sfz
    for k, names in sfz.keymap(sfz.regions(palette.path_of(inst))).items():
        print(f'{k:3d}  {", ".join(names[:4])}' + (' ...' if len(names) > 4 else ''))
    return 0


def note(inst: str, k: str, vel: int, seconds: float, out_dir: str) -> int:
    """One note of an instrument, dry and then in the hall, to hear what it is."""
    import score as sc
    s = sc.Score(title=f'{inst} {k}', bpm=60, bars=max(1, int(seconds // 4) + 1), tail=2.0, loudness=-20)
    s.part('note', inst, hall=0.3).play(0, seconds, int(k) if k.strip('0123456789') == '' else k, vel)
    work = os.path.join(CACHE, 'work', 'note')
    os.makedirs(work, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    import mix
    y, _ = mix.mastered(mixdown(s, work), RATE, -20)
    path = os.path.join(out_dir, f'note_{inst}_{k}_{vel}.wav')
    mix.write_wav(path, y, RATE)
    print('wrote', os.path.relpath(path, ROOT))
    return 0


def main(argv: list[str]) -> int:
    if not inside():
        return in_image('render.py', argv)
    out = DEFAULT_OUT
    if '--out' in argv:
        i = argv.index('--out')
        out = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    if argv[:1] == ['--verify']:
        return verify()
    if argv[:1] == ['--calibrate']:
        return calibrate()
    if argv[:1] == ['--keys']:
        return keys(argv[1])
    if argv[:1] == ['--note']:
        vel = int(argv[3]) if len(argv) > 3 else 90
        secs = float(argv[4]) if len(argv) > 4 else 3.0
        return note(argv[1], argv[2], vel, secs, out)
    stems = '--stems' in argv
    check = '--no-check' not in argv
    names = [a for a in argv if not a.startswith('--')]
    if not names:
        print(__doc__)
        return 2
    for name in names:
        render_piece(name, out, stems, check)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
