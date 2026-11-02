#!/usr/bin/env python3
"""A sketch round for the owner's ear (SKILL.md, steps 2 to 4): renders the sketches and checks them, then drafts the
gate report from what the pieces and the checks say, for the agent to finish before anything is sent.

    python3 .claude/skills/music/scripts/sketch_round.py SKETCH [SKETCH ...] [--ambience] [--cues]

Each SKETCH is a module of art_src/music/pieces/. Everything goes to .build/music-sketches/ (the cues to
.build/music-cues/): the renders, their stems, checks and pictures, and gate_report.txt, a draft with one block a
sketch (its length, what it tries from its docstring, its instruments and their libraries, every MISS of its check)
and the five gates with what the agent must still fill in. The draft never says a gate is met: that is the agent's
to show and the owner's to judge. Standard library only (the rendering runs in the music image).
"""

import importlib
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
MUSIC = os.path.join(ROOT, 'art_src', 'music')
OUT = os.path.join(ROOT, '.build', 'music-sketches')
sys.path.insert(0, MUSIC)

GATES = [
    "1. Groundhold's world, not Warcraft's notes, not Wickhollow's flavour: what of the Causeway each sketch carries, "
    "and that no lantern, gourd, autumn or night is in it.",
    "2. Grown from the references' habits: which habits (music_rules.md) and the measure's five points (a theme "
    "first, bronze not chrome, shape not loop, support never 'listen to me', a place you can name), one line each.",
    "3. The palette: the instruments below, all from palette.py's libraries.",
    "4. Sketches before the piece: these are sketches; none is grown until the owner picks one.",
    "5. The owner hears it before it ships: nothing here is in the game; not checked by ear (the agent cannot hear).",
]


def summary(name):
    import palette
    mod = importlib.import_module('pieces.' + name)
    s = mod.score()
    doc = (mod.__doc__ or '').strip().split('\n\n')
    tries = ' '.join(doc[1].split()) if len(doc) > 1 else ' '.join(doc[0].split())
    insts = sorted({p.inst for p in s.parts if p.notes})
    libs = ', '.join(f'{i} ({palette.INSTRUMENTS[i][0]})' for i in insts)
    check = os.path.join(OUT, f'{name}.check.txt')
    lines = open(check).read().splitlines() if os.path.exists(check) else ['(no check written)']
    misses = [l.strip() for l in lines if l.endswith('MISS')]
    verdict = lines[-1] if lines else ''
    return [f'== {s.title} ({name})',
            f'length {s.length_s + s.tail:.1f} s; {s.bpm:g} a minute, {s.meter[0]}/{s.meter[1]}, {s.tonic} {s.mode}',
            f'what it tries: {tries}',
            f'instruments: {libs}',
            f'check: {verdict}'] + [f'  {m}' for m in misses] + [
            f'files: .build/music-sketches/{name}.mp3 (for the ear), .wav, .spectrum.png, .roll.png']


def main(argv):
    names = [a for a in argv if not a.startswith('--')]
    if not names:
        print(__doc__)
        return 2
    run = lambda *cmd: subprocess.call([sys.executable, *cmd], cwd=ROOT)  # noqa: E731
    if run(os.path.join(MUSIC, 'render.py'), *names, '--out', OUT, '--stems'):
        return 1
    if '--ambience' in argv and run(os.path.join(MUSIC, 'ambience.py'), '--out', OUT):
        return 1
    if '--cues' in argv and run(os.path.join(MUSIC, 'cues.py')):
        return 1
    report = ['Gate report (a draft: finish every gate line before the owner is sent anything)', '']
    for name in names:
        report += summary(name) + ['']
    if '--ambience' in argv:
        amb = os.path.join(OUT, 'causeway_ambience.check.txt')
        report += ['== the ambience bed'] + (open(amb).read().splitlines() if os.path.exists(amb) else []) + ['']
    report += ['The gates (say how each is met, with its evidence):'] + GATES
    path = os.path.join(OUT, 'gate_report.txt')
    with open(path, 'w') as f:
        f.write('\n'.join(report) + '\n')
    print('\n'.join(report))
    print('wrote', os.path.relpath(path, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
