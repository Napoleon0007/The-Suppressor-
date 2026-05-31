"""Conversion engine — the 'Convert to…' mode.

When the user explicitly picks a target format, we convert AND compress into
that format. Only sensible, standard conversions are offered (the router and
the UI both restrict targets to ones that make sense for the input type).

Note: unlike Auto mode, conversions are NOT held to the never-bigger rule —
the user asked for this format on purpose (e.g. JPG→PNG is legitimately
bigger). We just report the real size change honestly.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from .result import Result

FFMPEG = shutil.which("ffmpeg")
TIMEOUT = 3600

# Valid targets per input category — the single source of truth the UI mirrors.
TARGETS = {
    "image": ["jpg", "png", "webp", "tiff", "gif", "bmp", "pdf"],
    "audio": ["mp3", "wav", "flac", "m4a", "opus", "ogg"],
    "video": ["mp4", "mov", "mkv", "webm", "avi", "gif", "mp3", "m4a"],
    "pdf":   [],     # PDF stays PDF (Auto compress only)
    "other": [],     # generic files: Auto (xz) only
}


# ----------------------------------------------------------------------------- images
def image_to(src: Path, out_dir: Path, target: str) -> Result:
    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        return Result(False, None, "convert", f"couldn't open image: {exc}")

    t = target.lower()
    stem = src.stem
    try:
        if t in ("jpg", "jpeg"):
            out = out_dir / f"{stem}.jpg"
            img.convert("RGB").save(out, "JPEG", quality=82, optimize=True, progressive=True)
            return Result(True, out, "→ JPG", "quality 82", True)
        if t == "png":
            out = out_dir / f"{stem}.png"
            img.save(out, "PNG", optimize=True)
            return Result(True, out, "→ PNG", "lossless", True)
        if t == "webp":
            out = out_dir / f"{stem}.webp"
            src_img = img if img.mode in ("RGB", "RGBA") else img.convert("RGBA")
            src_img.save(out, "WEBP", quality=82, method=6)
            return Result(True, out, "→ WebP", "quality 82", True)
        if t in ("tif", "tiff"):
            out = out_dir / f"{stem}.tiff"
            img.save(out, "TIFF", compression="tiff_deflate")
            return Result(True, out, "→ TIFF", "deflate (lossless)", True)
        if t == "gif":
            out = out_dir / f"{stem}.gif"
            img.convert("P", palette=Image.ADAPTIVE, colors=256).save(out, "GIF", optimize=True)
            return Result(True, out, "→ GIF", "256 colours", True)
        if t == "bmp":
            out = out_dir / f"{stem}.bmp"
            img.convert("RGB").save(out, "BMP")
            return Result(True, out, "→ BMP", "uncompressed format", True)
        if t == "pdf":
            out = out_dir / f"{stem}.pdf"
            img.convert("RGB").save(out, "PDF", resolution=150)
            return Result(True, out, "→ PDF", "", True)
    except Exception as exc:
        return Result(False, None, "convert", f"failed: {exc}")
    return Result(False, None, "convert", f"can't convert image to {target}")


# ----------------------------------------------------------------------------- audio
_AUDIO = {
    "mp3":  ("libmp3lame", ["-b:a", "128k"], ".mp3", "128 kbps"),
    "m4a":  ("aac", ["-b:a", "128k"], ".m4a", "128 kbps"),
    "aac":  ("aac", ["-b:a", "128k"], ".m4a", "128 kbps"),
    "opus": ("libopus", ["-b:a", "128k"], ".opus", "128 kbps"),
    "ogg":  ("libvorbis", ["-q:a", "5"], ".ogg", "VBR q5"),
    "wav":  ("pcm_s16le", [], ".wav", "lossless PCM"),
    "flac": ("flac", [], ".flac", "lossless"),
}


def audio_to(src: Path, out_dir: Path, target: str) -> Result:
    if not FFMPEG:
        return Result(False, None, "audio", "ffmpeg not found on PATH")
    enc = _AUDIO.get(target.lower())
    if not enc:
        return Result(False, None, "convert", f"can't convert audio to {target}")
    codec, opts, ext, note = enc
    out = out_dir / f"{src.stem}{ext}"
    cmd = [FFMPEG, "-y", "-i", str(src), "-vn", "-c:a", codec, *opts, str(out)]
    return _run_ffmpeg(cmd, out, f"→ {target.upper()}", note)


# ----------------------------------------------------------------------------- video
_VIDEO = {
    "mp4":  (["-c:v", "libx265", "-preset", "medium", "-crf", "28", "-tag:v", "hvc1",
              "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"], ".mp4", "H.265 CRF 28"),
    "mov":  (["-c:v", "libx265", "-preset", "medium", "-crf", "28", "-tag:v", "hvc1",
              "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"], ".mov", "H.265 CRF 28"),
    "mkv":  (["-c:v", "libx265", "-preset", "medium", "-crf", "28",
              "-c:a", "aac", "-b:a", "128k"], ".mkv", "H.265 CRF 28"),
    "webm": (["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
              "-c:a", "libopus", "-b:a", "128k"], ".webm", "VP9 CRF 32"),
    "avi":  (["-c:v", "mpeg4", "-qscale:v", "5",
              "-c:a", "libmp3lame", "-b:a", "128k"], ".avi", "MPEG-4 ASP"),
}


def video_to(src: Path, out_dir: Path, target: str) -> Result:
    if not FFMPEG:
        return Result(False, None, "video", "ffmpeg not found on PATH")
    t = target.lower()

    if t == "gif":
        out = out_dir / f"{src.stem}.gif"
        vf = ("fps=12,scale=480:-1:flags=lanczos,split[s0][s1];"
              "[s0]palettegen[p];[s1][p]paletteuse")
        cmd = [FFMPEG, "-y", "-i", str(src), "-vf", vf, "-loop", "0", str(out)]
        return _run_ffmpeg(cmd, out, "→ GIF", "480px, 12fps")

    if t in ("mp3", "m4a"):  # rip the audio track out of the video
        codec = "libmp3lame" if t == "mp3" else "aac"
        out = out_dir / f"{src.stem}.{t}"
        cmd = [FFMPEG, "-y", "-i", str(src), "-vn", "-c:a", codec, "-b:a", "128k", str(out)]
        return _run_ffmpeg(cmd, out, f"→ {t.upper()} (audio extracted)", "128 kbps")

    enc = _VIDEO.get(t)
    if not enc:
        return Result(False, None, "convert", f"can't convert video to {target}")
    opts, ext, note = enc
    out = out_dir / f"{src.stem}{ext}"
    cmd = [FFMPEG, "-y", "-i", str(src), *opts, str(out)]
    return _run_ffmpeg(cmd, out, f"→ {target.upper()}", note)


# ----------------------------------------------------------------------------- helper
def _run_ffmpeg(cmd, out: Path, method: str, note: str) -> Result:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return Result(False, None, method, "timed out (file too large/long)")
    if proc.returncode != 0 or not out.exists():
        err = (proc.stderr or b"").decode("utf-8", "ignore")
        if "does not contain any stream" in err or "Output file #0 does not" in err:
            friendly = "this file has no audio track to extract"
        else:
            # last non-empty line of ffmpeg's output is usually the real reason
            lines = [ln.strip() for ln in err.splitlines() if ln.strip()]
            friendly = lines[-1] if lines else "conversion failed"
        return Result(False, None, method, friendly)
    return Result(True, out, method, note, format_changed=True)
