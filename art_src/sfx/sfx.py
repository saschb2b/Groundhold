#!/usr/bin/env python3
"""Paints the sounds the kit's one-oscillator synthesizer cannot make, as art_src/sfx/sfx.json lists them: bells
(inharmonic partials, each dying away at its own rate, with a strike) and a swarm of bees.

    python3 art_src/sfx/sfx.py              # from the project root; rewrites the listed sfx/*.wav

A bell is a sum of partials at fixed ratios to its prime (a church bell's hum 0.5, prime 1, minor-third tierce 1.2,
quint 1.5, nominal 2 and its upper partials; a chime tube's free-bar modes 1, 2.756, 5.404, 8.933), each a pair of
sines a few cents apart, so it beats and shimmers as a cast bell does, decaying exponentially with its own time
constant, over a short strike: a burst of low-passed noise and, for a heavy blow, a low thump. Notes may follow one
another (a peal). A swarm is a handful of buzzing voices (band-limited saws round 200 Hz, each with its own
vibrato and drift) under a soft low-pass. Every sound is mono, 16 bit, 44.1 kHz, its sample peak at the spec's
`peak_db` (below the style's -1 dBFS true peak), faded in over 2 ms and out over its last 60 ms.

Seeded and deterministic; only the standard library is needed. Outputs are recorded in asset_manifest.json; a file
whose bytes come out as they were is left alone, its manifest entry too.
"""

from __future__ import annotations

import array
import json
import math
import random
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))
from console import record  # noqa: E402

RATE = 44100

# Partials: (ratio to the prime, amplitude, decay time constant in seconds at the prime's own length)
CHURCH = [(0.5, 0.50, 1.30), (1.0, 0.70, 0.95), (1.2, 0.45, 0.75), (1.5, 0.25, 0.55), (2.0, 1.00, 0.70),
          (2.61, 0.18, 0.35), (3.0, 0.32, 0.40), (4.0, 0.22, 0.28), (5.43, 0.10, 0.16), (6.8, 0.06, 0.10)]
HANDBELL = [(1.0, 0.60, 0.50), (2.0, 1.00, 0.40), (2.42, 0.35, 0.30), (3.0, 0.40, 0.25), (4.2, 0.22, 0.16),
            (5.4, 0.12, 0.10), (6.9, 0.06, 0.07)]
CHIME_TUBE = [(1.0, 1.00, 0.90), (2.756, 0.55, 0.55), (5.404, 0.28, 0.28), (8.933, 0.12, 0.12)]
SPECTRA = {"church": CHURCH, "handbell": HANDBELL, "chime": CHIME_TUBE}


def _onepole(samples: list[float], cutoff: float) -> list[float]:
    a = 1 - math.exp(-2 * math.pi * cutoff / RATE)
    out, s = [], 0.0
    for x in samples:
        s += a * (x - s)
        out.append(s)
    return out


def bell_note(n: int, at: float, freq: float, spectrum: list, gain: float, decay: float, detune: float,
              strike: float, strike_cut: float, thump: float, rng: random.Random, out: list[float]) -> None:
    """Adds one struck bell into `out` from second `at`."""
    start = int(at * RATE)
    for ratio, amp, tau in spectrum:
        f = freq * ratio
        if f > RATE * 0.45:
            continue
        cents = detune * (0.5 + rng.random())
        f2 = f * 2 ** (cents / 1200)
        ph1, ph2 = rng.random() * 2 * math.pi, rng.random() * 2 * math.pi
        t_const = tau * decay
        for i in range(start, n):
            t = (i - start) / RATE
            env = math.exp(-t / t_const)
            if env < 1e-4:
                break
            pair = math.sin(2 * math.pi * f * t + ph1) + math.sin(2 * math.pi * f2 * t + ph2)
            out[i] += gain * amp * env * 0.5 * pair
    if strike:   # the hit: a short burst of noise, low-passed
        length = min(n - start, int(0.06 * RATE))
        burst = [rng.uniform(-1, 1) * math.exp(-(k / RATE) / 0.008) for k in range(length)]
        for k, v in enumerate(_onepole(burst, strike_cut)):
            out[start + k] += gain * strike * v * 2.2
    if thump:   # a heavy blow's low thud
        for k in range(min(n - start, int(0.25 * RATE))):
            t = k / RATE
            out[start + k] += gain * thump * math.sin(2 * math.pi * (95 - 40 * t / 0.25) * t) * math.exp(-t / 0.05)


def swarm(n: int, voices: int, base: float, spread: float, rng: random.Random, out: list[float]) -> None:
    """Adds a swarm of buzzing voices into `out`."""
    for _ in range(voices):
        f0 = base * (1 + spread * rng.uniform(-1, 1))
        vib_rate, vib_depth = rng.uniform(6, 13), rng.uniform(0.015, 0.035)
        drift_rate, drift = rng.uniform(0.6, 1.8), rng.uniform(0.02, 0.06)
        amp = rng.uniform(0.6, 1.0) / voices
        pan_phase = rng.random() * 2 * math.pi
        swell = rng.uniform(1.2, 3.2)
        phase, vp, dp = rng.random(), rng.random() * 2 * math.pi, rng.random() * 2 * math.pi
        for i in range(n):
            t = i / RATE
            f = f0 * (1 + vib_depth * math.sin(2 * math.pi * vib_rate * t + vp)
                      + drift * math.sin(2 * math.pi * drift_rate * t + dp))
            phase = (phase + f / RATE) % 1.0
            # a band-limited saw: eight harmonics, 1/k
            s = sum(math.sin(2 * math.pi * k * phase) / k for k in range(1, 9))
            loud = 0.75 + 0.25 * math.sin(2 * math.pi * swell * t + pan_phase)
            out[i] += amp * loud * s


def render(spec: dict, seed: int) -> list[float]:
    rng = random.Random(f"sfx:{seed}")
    n = int(spec["duration"] * RATE)
    out = [0.0] * n
    for note in spec.get("notes", []):
        bell_note(n, note.get("at", 0.0), note["freq"], SPECTRA[note.get("spectrum", "church")], note.get("gain", 1.0),
                  note.get("decay", 1.0), note.get("detune", 4.0), note.get("strike", 0.3),
                  note.get("strike_cut", 3000), note.get("thump", 0.0), rng, out)
    if "swarm" in spec:
        s = spec["swarm"]
        swarm(n, s["voices"], s["base"], s["spread"], rng, out)
        out = _onepole(out, s.get("lowpass", 2600))
        out = _onepole(out, s.get("lowpass", 2600))
        attack, release = s.get("attack", 0.04), s.get("release", 0.3)
        for i in range(n):
            t = i / RATE
            out[i] *= min(1.0, t / attack) * min(1.0, (spec["duration"] - t) / release)
    return out


def write(samples: list[float], path: Path, peak_db: float) -> None:
    peak = max(abs(v) for v in samples) or 1.0
    gain = 10 ** (peak_db / 20) / peak
    n = len(samples)
    fade_in, fade_out = int(0.002 * RATE), int(0.06 * RATE)
    data = array.array("h")
    for i, v in enumerate(samples):
        edge = min(1.0, (i + 1) / fade_in, (n - i) / fade_out)
        data.append(int(max(-1.0, min(1.0, v * gain * edge)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def main(argv: list[str]) -> int:
    project = Path(__file__).resolve().parents[2]
    spec_rel = argv[0] if argv else "art_src/sfx/sfx.json"
    spec = json.loads((project / spec_rel).read_text())
    script = Path(__file__).resolve().relative_to(project).as_posix()
    for name, sound in spec["sounds"].items():
        path = project / spec["dest"] / f"{name}.wav"
        before = path.read_bytes() if path.exists() else None
        write(render(sound, sound.get("seed", 1)), path, sound.get("peak_db", spec.get("peak_db", -1.5)))
        keep = {path} if before is not None and path.read_bytes() == before else set()
        record(project, [path], {"tool": "script", "script": script, "spec": spec_rel, "sound": name,
                                 "regen": f"python3 {script} {spec_rel}"}, keep=keep)
        print(f"wrote {path.relative_to(project).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
