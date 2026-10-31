"""Generates the TimeFlow sounds: four seamless ambient loops and the timer chime.

The loops are built as exactly periodic signals (FFT shaping, circular
reverb), so the loop point has no click or gap. The chime is a short, soft
two-note bell that plays once when a timer ends (only if turned on in settings).

All sounds are generated here from math, so there are no licensing questions.
Needs numpy and ffmpeg. Run from the project root:
    python tools/make_sounds.py            # everything
    python tools/make_sounds.py chime      # only the chime
The files are written to static/sounds/.
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 32000
SECONDS = 64
N = SR * SECONDS
rng = np.random.default_rng(7)
t = np.arange(N) / SR
freqs = np.fft.rfftfreq(N, 1 / SR)


def shaped_noise(power, low=20.0, high=None):
    """White noise shaped by 1/f**power (circular, so it loops perfectly)."""
    spec = np.fft.rfft(rng.standard_normal(N))
    f = np.maximum(freqs, 1.0)
    gain = 1 / f ** power
    gain[freqs < low] *= (freqs[freqs < low] / low) ** 2
    if high:
        gain *= 1 / (1 + (freqs / high) ** 4)
    out = np.fft.irfft(spec * gain, N)
    return out / np.max(np.abs(out))


def circular_reverb(x, seconds=2.6, mix=0.35):
    ir_len = int(SR * seconds)
    ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / (SR * seconds / 6))
    ir_full = np.zeros(N)
    ir_full[:ir_len] = ir
    wet = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir_full), N)
    wet /= np.max(np.abs(wet))
    return (1 - mix) * x / np.max(np.abs(x)) + mix * wet


def lowpass(x, cutoff):
    spec = np.fft.rfft(x)
    spec *= 1 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, N)


def deep_focus():
    # brown noise: deep, steady, no melody
    return lowpass(shaped_noise(1.0, low=25), 900)


def calm_waves():
    # slow waves: brown + pink noise breathing every 8 seconds
    wave_env = (0.5 - 0.5 * np.cos(2 * np.pi * t / 8)) ** 2
    swell = 0.5 - 0.5 * np.cos(2 * np.pi * t / 32)
    body = shaped_noise(1.0, low=30) * (0.25 + 0.75 * wave_env)
    foam = lowpass(shaped_noise(0.5, low=200), 5000) * wave_env ** 1.5 * (0.6 + 0.4 * swell)
    return body + 0.45 * foam


def soft_rain():
    # gentle rain: airy pink hiss plus sparse soft droplets
    hiss = lowpass(shaped_noise(0.5, low=400), 7000)
    drops = np.zeros(N)
    for start in rng.integers(0, N, size=SECONDS * 22):
        length = int(SR * 0.03)
        idx = (start + np.arange(length)) % N
        f = rng.uniform(1800, 4200)
        drops[idx] += rng.uniform(0.05, 0.25) * np.sin(2 * np.pi * f * np.arange(length) / SR) * np.exp(-np.arange(length) / (SR * 0.006))
    return 0.55 * hiss + drops


def note_freq(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    semis = names[name[0]] + (1 if "#" in name else 0) - (1 if name[1] == "b" else 0)
    octave = int(name[-1])
    return 440 * 2 ** ((semis + 12 * (octave - 4)) / 12)


def study_pads():
    # soft instrumental: warm chord pads with a slow, gentle arpeggio
    chords = [["C3", "E3", "G3", "B3"], ["A2", "C3", "E3", "G3"],
              ["F2", "A2", "C3", "E3"], ["G2", "B2", "D3", "E3"]]
    chord_len = SECONDS / 8
    out = np.zeros(N)
    for k in range(8):
        chord = chords[k % 4]
        start = k * chord_len
        # smooth envelope that overlaps the next chord (wraps around the loop)
        local = (t - start) % SECONDS
        env = np.clip(local / 2.0, 0, 1) * np.clip((chord_len + 2.0 - local) / 2.0, 0, 1)
        for name in chord:
            f0 = note_freq(name)
            for detune in (-0.12, 0.0, 0.12):
                f = f0 * 2 ** (detune / 12)
                for h in range(1, 6):
                    fh = round(f * h * SECONDS) / SECONDS   # whole cycles per loop: no click
                    out += env * np.sin(2 * np.pi * fh * t + h) / (h ** 1.6) * 0.05
        # arpeggio: chord tones one octave up, one every second
        for j in range(int(chord_len)):
            name = chord[j % 4]
            f = note_freq(name) * 4
            onset = int((start + j) * SR)
            length = int(SR * 1.8)
            idx = (onset + np.arange(length)) % N
            tt = np.arange(length) / SR
            out[idx] += 0.10 * np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.45) * np.clip(tt / 0.01, 0, 1)
    return circular_reverb(lowpass(out, 3200), seconds=3.0, mix=0.4)


def chime():
    # soft bell: two gentle notes (E5, then B5), each with a few decaying partials
    length = int(SR * 2.4)
    tt = np.arange(length) / SR
    out = np.zeros(length)
    for onset, name in ((0.0, "E5"), (0.35, "B5")):
        f0 = note_freq(name)
        local = np.clip(tt - onset, 0, None)
        attack = np.clip(local / 0.008, 0, 1) * (tt >= onset)
        for ratio, amp, decay in ((1.0, 1.0, 0.9), (2.0, 0.35, 0.5), (2.76, 0.18, 0.3), (5.4, 0.05, 0.15)):
            out += amp * attack * np.exp(-local / decay) * np.sin(2 * np.pi * f0 * ratio * local)
    fade = np.clip((length - np.arange(length)) / (SR * 0.3), 0, 1)
    return out * fade


OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "sounds"


def save(name, x, level):
    x = x - np.mean(x)
    x = x / np.max(np.abs(x)) * level
    pcm = (x * 32767).astype(np.int16)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        wav = str(Path(folder) / f"{name}.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libopus", "-b:a", "40k",
                        str(OUT_DIR / f"{name}.ogg")], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "64k",
                        str(OUT_DIR / f"{name}.mp3")], check=True)


if __name__ == "__main__":
    which = sys.argv[1:] or ["deep", "calm", "study", "reading", "chime"]
    makers = {"deep": deep_focus, "calm": calm_waves, "study": study_pads, "reading": soft_rain, "chime": chime}
    levels = {"deep": 0.6, "calm": 0.6, "study": 0.7, "reading": 0.5, "chime": 0.45}
    for key in which:
        save(key, makers[key](), levels[key])
        print("made", key)
