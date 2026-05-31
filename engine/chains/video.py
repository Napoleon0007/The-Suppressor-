"""Video chain — re-encodes to H.265 (HEVC), which is dramatically smaller
than H.264 at the same visible quality. CRF 30 is aggressive-but-clean, and
audio is brought down to a sane 128 kbps AAC.

Keeps the source container when it can carry HEVC; falls back to .mp4 for
containers that won't (AVI/WMV/FLV).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..result import Result

FFMPEG = shutil.which("ffmpeg")
HEVC_OK = {".mp4", ".mov", ".m4v", ".mkv"}   # containers happy to hold H.265
TIMEOUT = 3600                                # 1h ceiling per file


def _encode(src: Path, out: Path) -> subprocess.CompletedProcess:
    cmd = [
        FFMPEG, "-y", "-i", str(src),
        "-c:v", "libx265", "-preset", "medium", "-crf", "30",
        "-tag:v", "hvc1",                     # QuickTime-friendly HEVC tag
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]
    return subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)


def compress(src: Path, out_dir: Path, target_ratio: float) -> Result:
    if not FFMPEG:
        return Result(False, None, "video", "ffmpeg not found on PATH")

    ext = src.suffix.lower() or ".mp4"
    if ext in HEVC_OK:
        out = out_dir / f"{src.stem}{ext}"
        try:
            proc = _encode(src, out)
        except subprocess.TimeoutExpired:
            return Result(False, None, "H.265", "timed out (file too large/long)")
        if proc.returncode == 0 and out.exists():
            return Result(True, out, "H.265 (HEVC) re-encode", "CRF 30, AAC 128k")
        err = (proc.stderr or b"").decode("utf-8", "ignore")[-300:]
        return Result(False, None, "H.265", f"ffmpeg failed: {err}")

    # Container can't hold HEVC — re-mux into .mp4.
    out = out_dir / f"{src.stem}.mp4"
    try:
        proc = _encode(src, out)
    except subprocess.TimeoutExpired:
        return Result(False, None, "H.265", "timed out (file too large/long)")
    if proc.returncode == 0 and out.exists():
        return Result(True, out, "H.265 (HEVC) re-encode",
                      f"container changed {ext} -> .mp4 to carry H.265",
                      format_changed=True)
    err = (proc.stderr or b"").decode("utf-8", "ignore")[-300:]
    return Result(False, None, "H.265", f"ffmpeg failed: {err}")
