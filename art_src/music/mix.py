"""The mix and the master, and the loudness they are measured by (NumPy and SciPy, in the music image).

- Each part's stem is placed (gain, a dynamics curve in beats, high- and low-pass, constant-power pan and stereo
  width) and sent to a hall: one stereo impulse response made here from seeded noise, its reverb time longer in the
  lows than the highs, after a predelay and a few early reflections, so every render of a piece is the same.
- The master is brought to its integrated loudness (ITU-R BS.1770-4: K-weighting, 400 ms blocks, the -70 LUFS and
  -10 LU gates) and held under its true-peak ceiling (4x oversampled) by a look-ahead limiter that only acts when a
  peak would pass it.
- `loudness_range` is EBU Tech 3342's (3 s windows, the 10th to 95th percentile after its gates).
"""

from __future__ import annotations

import math
import wave

import numpy as np
from scipy import signal

RATE = 48000


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """A WAV as float64 frames (n, 2), whatever its sample format (16, 24 or 32-bit PCM, 32-bit float)."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError(f'{path}: not a WAV')
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], 'little')
        body = data[pos + 8:pos + 8 + size]
        if cid == b'fmt ':
            fmt = body
        elif cid == b'data':
            raw = body
        pos += 8 + size + (size & 1)
    tag, ch = int.from_bytes(fmt[0:2], 'little'), int.from_bytes(fmt[2:4], 'little')
    sr = int.from_bytes(fmt[4:8], 'little')
    bits = int.from_bytes(fmt[14:16], 'little')
    if tag == 0xFFFE:   # WAVE_FORMAT_EXTENSIBLE: the sub-format's first two bytes
        tag = int.from_bytes(fmt[24:26], 'little')
    if tag == 3 and bits == 32:
        x = np.frombuffer(raw, dtype='<f4').astype(np.float64)
    elif tag == 1 and bits == 16:
        x = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768.0
    elif tag == 1 and bits == 24:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float64) / float(1 << 23)
    elif tag == 1 and bits == 32:
        x = np.frombuffer(raw, dtype='<i4').astype(np.float64) / float(1 << 31)
    else:
        raise ValueError(f'{path}: format {tag} at {bits} bits')
    x = x[: len(x) // ch * ch].reshape(-1, ch)
    if ch == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr


def write_wav(path: str, x: np.ndarray, sr: int = RATE, bits: int = 24) -> None:
    """Frames (n, channels) as PCM; TPDF dither at 16 bits."""
    x = np.atleast_2d(x)
    if x.shape[0] < x.shape[1]:
        x = x.T
    ch = x.shape[1]
    if bits == 24:
        v = np.clip(np.round(x * (1 << 23)), -(1 << 23), (1 << 23) - 1).astype(np.int32).reshape(-1)
        raw = np.stack([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF], axis=1).astype(np.uint8).tobytes()
    else:
        rng = np.random.default_rng(16)
        d = (rng.random(x.shape) - rng.random(x.shape)) / 32768.0
        raw = np.clip(np.round((x + d) * 32767), -32768, 32767).astype('<i2').tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(bits // 8)
        w.setframerate(sr)
        w.writeframes(raw)


def db(v: float) -> float:
    return 20 * math.log10(max(v, 1e-12))


def undb(d: float) -> float:
    return 10 ** (d / 20)


# ---- placing a part -----------------------------------------------------------------------------------------------

def filtered(x: np.ndarray, sr: int, hp: float = 0.0, lp: float = 0.0) -> np.ndarray:
    if hp:
        x = signal.sosfilt(signal.butter(2, hp, 'highpass', fs=sr, output='sos'), x, axis=0)
    if lp:
        x = signal.sosfilt(signal.butter(2, lp, 'lowpass', fs=sr, output='sos'), x, axis=0)
    return x


def shelf(x: np.ndarray, sr: int, gain_db: float, f0: float = 5000.0, slope: float = 0.8) -> np.ndarray:
    """A high shelf (RBJ's cookbook biquad): `gain_db` above about f0, nothing below. Air for a part whose upper
    partials the samples keep quiet, never a cure for a dull writing."""
    if not gain_db:
        return x
    a = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / sr
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / 2 * math.sqrt((a + 1 / a) * (1 / slope - 1) + 2)
    sa = 2 * math.sqrt(a) * alpha
    b = [a * ((a + 1) + (a - 1) * cw + sa), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - sa)]
    den = [(a + 1) - (a - 1) * cw + sa, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - sa]
    return signal.lfilter(b, den, x, axis=0)


def pan_gains(pan: float) -> tuple[float, float]:
    """Constant power, normalised so the middle keeps the stem's level on both sides."""
    angle = (max(-1.0, min(1.0, pan)) + 1) * math.pi / 4
    return math.cos(angle) * math.sqrt(2), math.sin(angle) * math.sqrt(2)


def place(x: np.ndarray, pan: float, width: float) -> np.ndarray:
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2 * width
    gl, gr = pan_gains(pan)
    return np.stack([(mid + side) * gl, (mid - side) * gr], axis=1)


def curve(n: int, sr: int, bpm: float, points: list[tuple[float, float]]) -> np.ndarray:
    """A gain over n frames from (beat, dB) breakpoints, linear in dB between them, held outside them."""
    if not points:
        return np.ones(n)
    pts = sorted(points)
    t = np.arange(n) / sr * bpm / 60.0
    beats = np.array([p[0] for p in pts])
    dbs = np.array([p[1] for p in pts])
    return 10 ** (np.interp(t, beats, dbs) / 20)


# ---- the hall -----------------------------------------------------------------------------------------------------

def hall_ir(sr: int, rt60: float, seed: int = 7, predelay: float = 0.024, air: float = 0.55,
            early: float = 0.9) -> np.ndarray:
    """A stereo hall: early reflections over the first 80 ms (`early` loud), then decorrelated noise decaying in
    three bands (the lows at 1.25 of `rt60`, the highs above 3.5 kHz at `air` of it), its onset swelling over 60 ms.
    Unit energy."""
    rng = np.random.default_rng(seed)
    n = int((predelay + rt60 * 1.6) * sr)
    t = np.arange(n) / sr
    ir = np.zeros((n, 2))
    tail = np.clip((t - predelay) / 0.06, 0, 1) ** 2
    for lo, hi, scale in ((0, 350, 1.25), (350, 3500, 1.0), (3500, 0, air)):
        noise = rng.standard_normal((n, 2))
        if lo and hi:
            sos = signal.butter(2, [lo, hi], 'bandpass', fs=sr, output='sos')
        elif hi:
            sos = signal.butter(2, hi, 'lowpass', fs=sr, output='sos')
        else:
            sos = signal.butter(2, lo, 'highpass', fs=sr, output='sos')
        band = signal.sosfilt(sos, noise, axis=0)
        env = np.exp(-6.9078 * np.maximum(t - predelay, 0) / (rt60 * scale)) * tail
        ir += band * env[:, None]
    for k in range(10):   # early reflections, alternating sides
        at = predelay + 0.008 + 0.072 * rng.random()
        side = k % 2
        ir[int(at * sr), side] += early * (1 - (at - predelay) / 0.1) * rng.choice((-1, 1))
    ir /= math.sqrt(np.sum(ir ** 2) / 2)
    return ir


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    out = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)
    return out[: len(x)]


# ---- loudness -----------------------------------------------------------------------------------------------------

def k_weighted(x: np.ndarray, sr: int) -> np.ndarray:
    """BS.1770's K-weighting: the high shelf (+4 dB above about 1.5 kHz) and the RLB high-pass, for any rate."""
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / sr)
    vh, vb = 10 ** (g / 20), 10 ** (g / 20) ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b1 = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a1 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / sr)
    a0 = 1 + k / q + k * k
    b2 = [1, -2, 1]
    a2 = [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    y = signal.lfilter(b1, a1, x, axis=0)
    return signal.lfilter(b2, a2, y, axis=0)


def _blocks(y: np.ndarray, sr: int, length: float, step: float) -> np.ndarray:
    """Mean square of each block, summed over the channels (both weighted 1.0)."""
    n, h = int(length * sr), int(step * sr)
    sq = np.sum(y ** 2, axis=1)
    c = np.concatenate([[0.0], np.cumsum(sq)])
    starts = np.arange(0, max(1, len(sq) - n + 1), h)
    return (c[np.minimum(starts + n, len(sq))] - c[starts]) / n


def lufs(z: np.ndarray) -> np.ndarray:
    return -0.691 + 10 * np.log10(np.maximum(z, 1e-20))


def integrated(x: np.ndarray, sr: int = RATE) -> float:
    z = _blocks(k_weighted(x, sr), sr, 0.4, 0.1)
    l = lufs(z)
    z = z[l > -70]
    if not len(z):
        return -120.0
    rel = lufs(np.array([z.mean()]))[0] - 10
    z = z[lufs(z) > rel]
    return float(lufs(np.array([z.mean()]))[0]) if len(z) else -120.0


def short_term(x: np.ndarray, sr: int = RATE) -> np.ndarray:
    """Short-term loudness (3 s windows) every 100 ms, LUFS."""
    return lufs(_blocks(k_weighted(x, sr), sr, 3.0, 0.1))


def loudness_range(x: np.ndarray, sr: int = RATE) -> float:
    st = short_term(x, sr)
    st = st[st > -70]
    if len(st) < 2:
        return 0.0
    z = 10 ** ((st + 0.691) / 10)
    rel = lufs(np.array([z.mean()]))[0] - 20
    st = np.sort(st[st > rel])
    if len(st) < 2:
        return 0.0
    return float(np.percentile(st, 95) - np.percentile(st, 10))


def true_peak(x: np.ndarray) -> float:
    """dBTP: the sample peak after 4x oversampling (BS.1770's method)."""
    up = signal.resample_poly(x, 4, 1, axis=0)
    return db(float(np.max(np.abs(up))))


def limited(x: np.ndarray, sr: int, ceiling_db: float = -1.0, lookahead: float = 0.005,
            release: float = 0.15) -> np.ndarray:
    """A look-ahead peak limiter on the 4x oversampled peak: gain only where a peak would pass the ceiling."""
    ceiling = undb(ceiling_db - 0.1)
    up = np.max(np.abs(signal.resample_poly(x, 4, 1, axis=0)), axis=1)
    peak = up[: len(up) // 4 * 4].reshape(-1, 4).max(axis=1)
    peak = np.concatenate([peak, np.zeros(len(x) - len(peak))])
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-12))
    if need.min() >= 1.0:
        return x
    la = max(1, int(lookahead * sr))
    # the gain must be down by the time the peak arrives: the minimum over the look-ahead window ahead
    padded = np.concatenate([need, np.ones(la)])
    ahead = np.lib.stride_tricks.sliding_window_view(padded, la + 1).min(axis=1)[: len(need)]
    g = np.empty_like(ahead)
    a_rel = math.exp(-1.0 / (release * sr))
    cur = 1.0
    for i, v in enumerate(ahead):
        cur = v if v < cur else v + (cur - v) * a_rel
        g[i] = cur
    return x * g[:, None]


def mastered(x: np.ndarray, sr: int, target_lufs: float, ceiling_db: float = -1.0) -> tuple[np.ndarray, float]:
    """The mix brought to its loudness and held under its true-peak ceiling; returns it and the gain it took."""
    now = integrated(x, sr)
    gain = target_lufs - now
    y = x * undb(gain)
    y = limited(y, sr, ceiling_db)
    # the limiter takes a little loudness on a peak; one more pass of gain, limited again, lands on the target
    again = target_lufs - integrated(y, sr)
    if abs(again) > 0.05:
        y = limited(y * undb(again), sr, ceiling_db)
        gain += again
    return y, gain
