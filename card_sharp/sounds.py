"""Sound effects — macOS `afplay` fire-and-forget.

- correct / wrong / lose / push: built-in system sounds (safe fallback if missing).
- win / bj: synthesized cha-ching WAV written to Application Support on first use.

Toggle at runtime by setting sounds.ENABLED = False (or via prefs).
"""
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path

from .prefs import app_support_dir


ENABLED = True   # runtime toggle

SYSTEM_SFX = {
    "correct": "/System/Library/Sounds/Pop.aiff",
    "wrong":   "/System/Library/Sounds/Basso.aiff",
    "push":    "/System/Library/Sounds/Tink.aiff",
    "lose":    "/System/Library/Sounds/Funk.aiff",
    "click":   "/System/Library/Sounds/Tink.aiff",
}


def _sounds_dir() -> Path:
    p = app_support_dir() / "sounds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_wav(path: Path, samples: list[int], framerate: int = 44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)     # 16-bit
        w.setframerate(framerate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def _bell(freqs: list[float], duration_s: float, framerate: int,
          amp: float = 0.55, decay: float = 6.0) -> list[int]:
    """Additive-synth bell: sum of decaying sinusoids."""
    n = int(framerate * duration_s)
    out = []
    for i in range(n):
        t = i / framerate
        env = math.exp(-decay * t)
        v = 0.0
        for f in freqs:
            v += math.sin(2 * math.pi * f * t)
        v = env * amp * v / max(1, len(freqs))
        # Soft attack (first 5 ms)
        if t < 0.005:
            v *= t / 0.005
        s = int(max(-1.0, min(1.0, v)) * 32767)
        out.append(s)
    return out


def _generate_win_wav(path: Path):
    """Two-note ascending 'cha-ching' bell — approx cash-register feel."""
    fr = 44100
    # Bell tone 1 (root)
    n1 = _bell([880, 1320, 1760, 2640], duration_s=0.28, framerate=fr, decay=7.0)
    # Small gap
    gap = [0] * int(fr * 0.04)
    # Bell tone 2 (fifth up)
    n2 = _bell([1320, 1980, 2640, 3960], duration_s=0.55, framerate=fr, decay=4.5)
    _write_wav(path, n1 + gap + n2, framerate=fr)


def _generate_bj_wav(path: Path):
    """Blackjack fanfare: three bells ascending."""
    fr = 44100
    a = _bell([880, 1760, 2640], 0.20, fr, decay=8.0)
    g = [0] * int(fr * 0.03)
    b = _bell([1108, 2217, 3325], 0.20, fr, decay=8.0)
    c = _bell([1320, 2640, 3960, 5280], 0.65, fr, decay=4.5)
    _write_wav(path, a + g + b + g + c, framerate=fr)


def ensure_synth():
    """Create the synth WAVs on disk if missing. Idempotent."""
    d = _sounds_dir()
    win = d / "win.wav"
    bj = d / "blackjack.wav"
    try:
        if not win.exists():
            _generate_win_wav(win)
        if not bj.exists():
            _generate_bj_wav(bj)
    except Exception:
        pass


def _synth_path(name: str) -> str | None:
    d = _sounds_dir()
    p = {"win": d / "win.wav", "bj": d / "blackjack.wav"}.get(name)
    return str(p) if (p and p.exists()) else None


def play(name: str):
    """Non-blocking play. Best-effort; failures are swallowed."""
    if not ENABLED:
        return
    if sys.platform != "darwin":
        return
    # Ensure synth exists lazily
    if name in ("win", "bj"):
        ensure_synth()
        path = _synth_path(name)
    else:
        path = SYSTEM_SFX.get(name)
    if not path or not os.path.exists(path):
        return
    try:
        subprocess.Popen(
            ["/usr/bin/afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
