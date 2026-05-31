"""The router — the 'cross-pollination' brain of The Suppressor.

One drop zone for the user. Under the hood the router sniffs each file's
real type (magic bytes first, extension as fallback) and sends it down the
best compression chain for that kind of file. The user never picks a method
or a target size — the router decides.

Hard rule enforced here: the output is NEVER bigger than the input. If a
chain can't actually shrink a file (already-compressed JPEG, tiny MP4, etc.)
the original is kept untouched and we say why.
"""
from __future__ import annotations

from pathlib import Path

from .result import Result
from .chains import image, video, audio, pdf, binary

# Goal: output should be <= 25% of the original size (i.e. >= 75% smaller).
# This is the target the chains push toward, not a guarantee — already-compressed
# files physically can't hit it without wrecking quality, and we're honest about that.
TARGET_RATIO = 0.25


def sniff(path: Path) -> str:
    """Classify a file as: image | video | audio | pdf | other.

    Magic bytes win over the extension (a .txt that's really a JPEG is an image).
    """
    try:
        with open(path, "rb") as f:
            head = f.read(32)
    except OSError:
        head = b""
    ext = path.suffix.lower().lstrip(".")

    # ---- magic-byte detection ----
    if head[:3] == b"\xff\xd8\xff":
        return "image"                                    # JPEG
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"                                    # PNG
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image"                                    # GIF
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"                                    # WebP
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio"                                    # WAV
    if head[:4] == b"RIFF" and head[8:11] == b"AVI":
        return "video"                                    # AVI
    if head[:2] in (b"II", b"MM") and ext in ("tif", "tiff"):
        return "image"                                    # TIFF
    if head[:2] == b"BM":
        return "image"                                    # BMP
    if head[:4] == b"%PDF":
        return "pdf"
    if head[:4] == b"fLaC":
        return "audio"                                    # FLAC
    if head[:4] == b"OggS":
        return "audio"                                    # Ogg / Opus
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio"                                    # MP3
    if head[:4] == b"\x1aE\xdf\xa3":
        return "video"                                    # Matroska / WebM
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B ", b"M4P "):
            return "audio"
        return "video"                                    # mp4, mov, m4v, ...
    if head[:4] == b"FORM" and head[8:12] == b"AIFF":
        return "audio"                                    # AIFF

    # ---- extension fallback ----
    images = {"jpg", "jpeg", "png", "gif", "webp", "tif", "tiff", "bmp"}
    videos = {"mp4", "mov", "m4v", "mkv", "webm", "avi", "wmv", "flv"}
    audios = {"wav", "flac", "ogg", "mp3", "m4a", "aac", "aiff", "aif", "opus"}
    if ext in images:
        return "image"
    if ext in videos:
        return "video"
    if ext in audios:
        return "audio"
    if ext == "pdf":
        return "pdf"
    return "other"


CHAINS = {
    "image": image.compress,
    "video": video.compress,
    "audio": audio.compress,
    "pdf": pdf.compress,
    "other": binary.compress,
}


def route(src: Path, out_dir: Path) -> Result:
    """Pick a chain for `src`, run it, and guarantee we never return a bigger file."""
    kind = sniff(src)
    chain = CHAINS.get(kind, binary.compress)

    try:
        result = chain(src, out_dir, TARGET_RATIO)
    except Exception as exc:  # a broken file shouldn't take down the whole batch
        return Result(False, None, f"{kind} chain", note=f"error: {exc}")

    # Safety net: discard any output that isn't actually smaller than the source.
    if result.out_path and result.out_path.exists():
        orig = src.stat().st_size
        if result.out_path.stat().st_size >= orig:
            try:
                result.out_path.unlink()
            except OSError:
                pass
            result.ok = False
            result.out_path = None
            if not result.note:
                result.note = "already optimally compressed — can't shrink further in-format"
    return result
