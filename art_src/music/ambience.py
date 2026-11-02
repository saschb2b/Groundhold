#!/usr/bin/env python3
"""The Causeway's ambience bed: wind over the flats, water moving on sand, and a far bell, as a seamless loop.

    python3 art_src/music/ambience.py [--seconds 30] [--seed 1] [--out DIR] [--name causeway_ambience]

front-end.md §4.6 asks for it: "a seamless loop of wind over the flats, water moving on sand and a far bell". It
belongs to no map (the Flats and the Tide run on every map; AGENTS.md), so it carries no night, insects or lanterns.
Made here, in the music image, so the bell is a sampled one (palette.py's tubular bells) and the surf has a real
ocean drum's beads under the synthesized water:

- Wind: noise in eight bands from 140 Hz to 3.6 kHz, each made circular (shaped in the frequency domain over the
  loop's whole length, so its end runs into its start) and swelled by its own slow envelope, with gusts that lift
  the upper bands more than the lower; a faint whistle round 800 Hz in the strongest gusts.
- Water: laps every three to six seconds, each a swell of low-passed noise that falls back, with a fizz of bubbles
  after it; a low, far wash under everything; an ocean drum's surf twice in the loop, far off.
- The bell: a tubular bell's D (the Causeway theme's tonic) once and its A once more faintly, low-passed and wet,
  as heard across a mile of flats.

Every envelope's period divides the loop, every event that runs past the end wraps to the start, and the hall is a
circular convolution, so the loop has no seam. The bed is brought to -28 LUFS (under the music: music_rules.md,
Mix) and checked: its loudness, its bands, and the seam (the level either side of it and the step across it).
Seeded and deterministic. Writes NAME.wav (48 kHz, 24-bit), .ogg, .mp3 and .spectrum.png into DIR
(.build/music-sketches/ by default).
"""

from __future__ import annotations

import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render  # noqa: E402

RATE = render.RATE
TARGET_LUFS = -28.0


def periodic(n: int, rng, cycles=(1, 2, 3, 5), depth=0.5, floor=0.0):
    """A smooth envelope whose every component repeats a whole number of times over n samples (so it loops)."""
    import numpy as np
    t = np.arange(n) / n
    env = np.zeros(n)
    for c in cycles:
        env += rng.uniform(0.3, 1.0) / c * np.cos(2 * math.pi * c * t + rng.uniform(0, 2 * math.pi))
    env = (env - env.min()) / (env.max() - env.min() + 1e-12)
    return floor + (1 - floor) * (1 - depth + depth * env)


def circular_band(n: int, rng, lo: float, hi: float, tilt: float = 0.0):
    """White noise over the loop's length, kept between lo and hi Hz (soft edges) and tilted by `tilt` dB an octave:
    shaped in the frequency domain, so it is periodic in n."""
    import numpy as np
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / RATE)
    gain = 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4) / (1 + (f / hi) ** 4)
    if tilt:
        gain *= (np.maximum(f, 20) / 1000) ** (tilt / 6.02)
    x = np.fft.irfft(spec * gain, n)
    return x / (np.std(x) + 1e-12)


def wrap_add(out, x, at: int):
    """Adds x into out from sample `at`, wrapping past the end to the start."""
    n = len(out)
    i = 0
    while i < len(x):
        start = (at + i) % n
        take = min(len(x) - i, n - start)
        out[start:start + take] += x[i:i + take]
        i += take


def lowpass(x, cutoff, order=2):
    from scipy import signal
    return signal.sosfilt(signal.butter(order, cutoff, 'lowpass', fs=RATE, output='sos'), x, axis=0)


def highpass(x, cutoff, order=2):
    from scipy import signal
    return signal.sosfilt(signal.butter(order, cutoff, 'highpass', fs=RATE, output='sos'), x, axis=0)


def wind(n, rng):
    import numpy as np
    gust = periodic(n, rng, cycles=(1, 2, 3, 4, 6), depth=0.85, floor=0.15) ** 1.6
    out = np.zeros((n, 2))
    edges = np.geomspace(140, 3600, 9)
    for k, (lo, hi) in enumerate(zip(edges, edges[1:])):
        lift = 0.6 + 1.4 * k / 7                       # a gust lifts the upper bands more
        env = periodic(n, rng, cycles=(1, 2, 3), depth=0.5) * gust ** lift
        common = circular_band(n, rng, lo, hi, tilt=-1.5)
        for ch in range(2):
            own = circular_band(n, rng, lo, hi, tilt=-1.5)
            out[:, ch] += (0.8 * common + 0.6 * own) * env * (1.0 - 0.07 * k)
    whistle = circular_band(n, rng, 760, 860) * np.clip(gust - 0.55, 0, None) ** 2 * 0.9
    out[:, 0] += whistle * 0.8
    out[:, 1] += whistle * 0.5
    return out


def water(n, rng):
    import numpy as np
    out = np.zeros((n, 2))
    # the far wash: low noise, slowly breathing
    wash = circular_band(n, rng, 90, 520, tilt=-3) * periodic(n, rng, cycles=(2, 3, 5), depth=0.4)
    out += np.stack([wash, np.roll(wash, int(0.37 * RATE))], axis=1) * 0.35
    t = rng.uniform(0.5, 2.0)
    while t < n / RATE:
        length = rng.uniform(2.0, 3.2)
        m = int(length * RATE)
        k = np.arange(m) / RATE
        rise = rng.uniform(0.35, 0.8)
        env = np.where(k < rise, (k / rise) ** 2, np.exp(-(k - rise) / rng.uniform(0.5, 0.9)))
        body = lowpass(rng.standard_normal(m), rng.uniform(700, 1300), 2) * env * rng.uniform(0.6, 1.0)
        # the fizz: sparse bubbles, high, after the lap's crest
        bubbles = (rng.random(m) < 0.004) * rng.standard_normal(m)
        fizz = highpass(lowpass(bubbles, 7000), 2500) * np.exp(-np.maximum(k - rise, 0) / 0.7) * (k > rise * 0.8)
        pan = rng.uniform(-0.6, 0.6)
        lap = body * 1.6 + fizz * 3.0
        stereo = np.stack([lap * math.cos((pan + 1) * math.pi / 4), lap * math.sin((pan + 1) * math.pi / 4)], axis=1)
        wrap_add(out, stereo * math.sqrt(2), int(t * RATE))
        t += rng.uniform(3.0, 6.0)
    return out


def sampled(n, seconds):
    """The bell and the ocean drum's surf, rendered by the palette's instruments (render.mixdown, no hall: the bed's
    own circular hall comes after), wrapped into the loop."""
    import numpy as np
    import score as sc
    s = sc.Score(title='causeway ambience, sampled', bpm=60, bars=int(seconds // 4) + 1, tail=6.0)
    s.part('bell', 'tubular_bells', role='colour', hp=160, lp=2400, gain_db=-6).play(seconds * 0.23, 2, 'D4', 64) \
        .play(seconds * 0.73, 2, 'A4', 44)
    s.part('surf', 'ocean_drum', role='colour', lp=5000, gain_db=-14).play(seconds * 0.05, 4, 61, 70) \
        .play(seconds * 0.55, 4, 62, 60)
    work = os.path.join(render.CACHE, 'work', 'ambience')
    os.makedirs(work, exist_ok=True)
    x = render.mixdown(s, work, hall=False)
    out = np.zeros((n, 2))
    wrap_add(out, x, 0)
    return out


def circ(f, x):
    """An IIR filter run round the loop: over two passes, keeping the second, so the filter's state at the start
    is the one the end left (no seam where it would have started from silence)."""
    import numpy as np
    n = len(x)
    return f(np.concatenate([x, x]))[n:]


def circular_hall(x, rt60=2.2, wet=0.35):
    import numpy as np
    import mix
    ir = mix.hall_ir(RATE, rt60, seed=11)
    n = len(x)
    ir = ir[:n] if len(ir) > n else np.concatenate([ir, np.zeros((n - len(ir), 2))])
    y = np.stack([np.fft.irfft(np.fft.rfft(x[:, c]) * np.fft.rfft(ir[:, c]), n) for c in range(2)], axis=1)
    return x + wet * circ(lambda v: highpass(v, 120), y)


# each layer's level against the wind's (dB): the wind the floor, the water just under it; the sampled bell and
# surf keep the palette's calibrated level (render.py --calibrate), read off build()'s layer line
LAYERS = {'wind': 0.0, 'water': -2.0, 'bell and surf': -7.0}


def build(seconds: float, seed: int):
    """The bed, and its layers' loudness (LUFS, before the bed is brought to its target)."""
    import numpy as np
    import mix
    rng = np.random.default_rng(seed)
    n = int(round(seconds * RATE))
    layers = {'wind': wind(n, rng), 'water': water(n, rng), 'bell and surf': sampled(n, seconds)}
    ref = mix.integrated(layers['wind'], RATE)
    for k, rel in LAYERS.items():
        layers[k] = layers[k] * mix.undb(ref - mix.integrated(layers[k], RATE) + rel)
    loud = {k: mix.integrated(v, RATE) for k, v in layers.items()}
    bed = sum(layers.values())
    bed = circular_hall(bed)
    return circ(lambda v: highpass(v, 30.0), bed), loud


def seam_lines(x, sr):
    import numpy as np
    import mix
    w = int(0.1 * sr)
    head = mix.db(float(np.sqrt(np.mean(x[:w] ** 2))))
    tail = mix.db(float(np.sqrt(np.mean(x[-w:] ** 2))))
    step = float(np.max(np.abs(x[0] - x[-1])))
    typical = float(np.percentile(np.abs(np.diff(x, axis=0)), 99))
    ok = abs(head - tail) <= 3.0 and step <= 2 * typical
    return [f'the seam: last 100 ms {tail:.1f} dBFS, first 100 ms {head:.1f}; the step across it {step:.5f} '
            f'against a 99th-percentile step of {typical:.5f}' + ('' if ok else '  MISS')]


def main(argv: list[str]) -> int:
    if not render.inside():
        return render.in_image('ambience.py', argv)
    import mix
    import check
    seconds, seed = 30.0, 1
    out_dir = os.path.join(render.ROOT, '.build', 'music-sketches')
    name = 'causeway_ambience'
    for flag in ('--seconds', '--seed', '--out', '--name'):
        if flag in argv:
            v = argv[argv.index(flag) + 1]
            if flag == '--seconds':
                seconds = float(v)
            elif flag == '--seed':
                seed = int(v)
            elif flag == '--out':
                out_dir = os.path.abspath(v)
            else:
                name = v
    os.makedirs(out_dir, exist_ok=True)
    bed, loud = build(seconds, seed)
    gain = TARGET_LUFS - mix.integrated(bed, RATE)
    bed = bed * mix.undb(gain)
    peak = mix.true_peak(bed)
    if peak > -1.0:
        bed = bed * mix.undb(-1.0 - peak)
    wav = os.path.join(out_dir, f'{name}.wav')
    mix.write_wav(wav, bed, RATE, 24)
    for ext, codec in (('ogg', ['-c:a', 'libvorbis', '-q:a', '6']), ('mp3', ['-c:a', 'libmp3lame', '-q:a', '2'])):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav] + codec
                       + [os.path.join(out_dir, f'{name}.{ext}')], check=True)
    lines = [f'== the Causeway\'s ambience bed ({seconds:g} s loop, seed {seed}), target {TARGET_LUFS:g} LUFS']
    x, sr = check.decode(wav)
    lines += check.sound_lines(x, sr, 60, 4)
    lines += seam_lines(mix.read_wav(wav)[0], RATE)
    lines.append('layers (LUFS as made, before the bed\'s gain of %+.1f dB): ' % gain
                 + ', '.join(f'{k} {v:.1f}' for k, v in loud.items()))
    report = '\n'.join(lines)
    with open(os.path.join(out_dir, f'{name}.check.txt'), 'w') as f:
        f.write(report + '\n')
    print(report)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-lavfi', check.SPECTRUM,
                    os.path.join(out_dir, f'{name}.spectrum.png')], check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
