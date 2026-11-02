"""Just enough of an SFZ reader to know what an instrument can play: its regions' keys and velocities and the
samples they name (headers <control>, <global>, <master>, <group>, <region>; `default_path`, `#define`, `key=`,
note names). sfizz plays the instrument; this tells the renderer which notes would find no sample (a note outside
the instrument's range is silence, never an error from sfizz) and names an unpitched set's keys. Standard library.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

NOTE = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def _key(v: str) -> int:
    v = v.strip()
    if re.fullmatch(r'-?\d+', v):
        return int(v)
    m = re.fullmatch(r'([a-gA-G])([#b]?)(-?\d+)', v)
    if not m:
        raise ValueError(f'not a key: {v}')
    pc = NOTE[m.group(1).lower()] + (1 if m.group(2) == '#' else -1 if m.group(2) == 'b' else 0)
    return 12 * (int(m.group(3)) + 1) + pc


@dataclass
class Region:
    lokey: int
    hikey: int
    lovel: int
    hivel: int
    sample: str
    trigger: str
    opcodes: dict


def regions(path: str) -> list[Region]:
    text = open(path, encoding='utf-8', errors='replace').read()
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    defines = dict(re.findall(r'#define\s+(\$\w+)\s+(\S+)', text))
    text = re.sub(r'#define\s+\$\w+\s+\S+', ' ', text)
    for k in sorted(defines, key=len, reverse=True):
        text = text.replace(k, defines[k])
    base = os.path.dirname(path)
    order = ['control', 'global', 'master', 'group']
    levels = {name: {} for name in order}
    out, target = [], {}
    # split into headers and opcode runs; a sample's name may hold spaces, so an opcode's value runs to the next
    # opcode or header
    for tok in re.split(r'(<\w+>)', text):
        h = re.fullmatch(r'<(\w+)>', tok)
        if h:
            name = h.group(1)
            if name in levels:
                # a header clears itself and every level under it (a <group> keeps the <global> above it)
                for lower in order[order.index(name):] if name != 'control' else ['control']:
                    levels[lower] = {}
                target = levels[name]
            elif name == 'region':
                region = {}
                for lvl in order:
                    region.update(levels[lvl])
                out.append(region)
                target = region
            else:
                target = {}
            continue
        for m in re.finditer(r'(\w+)=(.*?)(?=\s+\w+=|\s*$)', tok.strip(), flags=re.S):
            target[m.group(1)] = m.group(2).strip()
    result = []
    for op in out:
        if 'sample' not in op:
            continue
        if 'key' in op:
            lo = hi = _key(op['key'])
        else:
            lo, hi = _key(op.get('lokey', '0')), _key(op.get('hikey', '127'))
        lovel, hivel = int(op.get('lovel', 1)), int(op.get('hivel', 127))
        sample = op['sample'].replace('\\', '/')
        if not sample.startswith('*'):
            dp = op.get('default_path', '').replace('\\', '/')
            sample = os.path.normpath(os.path.join(base, dp, sample))
        result.append(Region(lo, hi, lovel, hivel, sample, op.get('trigger', 'attack'), op))
    return result


def covers(regs: list[Region], key: int, vel: int) -> bool:
    return any(r.trigger in ('attack', 'first', 'legato') and r.lokey <= key <= r.hikey and r.lovel <= vel <= r.hivel
               for r in regs)


def key_range(regs: list[Region]) -> tuple[int, int]:
    att = [r for r in regs if r.trigger in ('attack', 'first', 'legato')] or regs
    return min(r.lokey for r in att), max(r.hikey for r in att)


def missing_samples(regs: list[Region]) -> list[str]:
    return sorted({r.sample for r in regs if not r.sample.startswith('*') and not os.path.exists(r.sample)})


def keymap(regs: list[Region]) -> dict[int, list[str]]:
    """For an unpitched set: each key and the samples it plays (their file names)."""
    out: dict[int, list[str]] = {}
    for r in regs:
        for k in range(r.lokey, r.hikey + 1):
            out.setdefault(k, [])
            name = os.path.basename(r.sample)
            if name not in out[k]:
                out[k].append(name)
    return dict(sorted(out.items()))
