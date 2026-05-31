"""Audio chain.

Lossless sources (WAV/FLAC/AIFF/ALAC) are physically huge and CANNOT shrink
staying in their own format — so the best route is Opus, which is transparent
to the ear at a fraction of the size. That format change is labelled clearly.

Already-lossy sources (MP3/AAC/M4A/OGG) are re-encoded in their own family at
a lower bitrate; the router's never-bigger safety net keeps the original if
that doesn't actually help.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..result import Result

FFMPEG = shutil.which("ffmpeg")
LOSSLESS = {".wav", ".flac", ".aiff", ".aif", ".alac"}
TIMEOUT = 900


def _run(cmd) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)


def compress(src: Path, out_dir: Path, target_ratio: float) -> Result:
    if not FFMPEG:
        return Result(False, None, "audio", "ffmpeg not found on PATH")

    ext = src.suffix.lower()
    if ext in LOSSLESS:
        out = out_dir / f"{src.stem}.opus"
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:a", "libopus", "-b:a", "96k", str(out)]
        method, note, changed = "Opus encode", f"converted {ext} -> .opus (96 kbps, transparent)", True
    elif ext == ".mp3":
        out = out_dir / f"{src.stem}.mp3"
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:a", "libmp3lame", "-b:a", "96k", str(out)]
        method, note, changed = "MP3 re-encode", "96 kbps", False
    elif ext in (".m4a", ".aac"):
        out = out_dir / f"{src.stem}.m4a"
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:a", "aac", "-b:a", "96k", str(out)]
        method, note, changed = "AAC re-encode", "96 kbps", False
    else:  # ogg / opus / anything else lossy -> Opus
        out = out_dir / f"{src.stem}.opus"
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:a", "libopus", "-b:a", "96k", str(out)]
        method, note, changed = "Opus re-encode", "96 kbps", ext != ".opus"

    try:
        proc = _run(cmd)
    except subprocess.TimeoutExpired:
        return Result(False, None, method, "timed out")
    if proc.returncode != 0 or not out.exists():
        err = (proc.stderr or b"").decode("utf-8", "ignore")[-300:]
        return Result(False, None, method, f"ffmpeg failed: {err}")
    return Result(True, out, method, note, format_changed=changed)
