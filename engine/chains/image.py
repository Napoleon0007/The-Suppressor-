"""Image chain — shrinks images while keeping them the same kind of image.

JPEG / WebP : quality search, drops quality only as far as needed to hit the
              target, never below a floor that keeps it looking clean.
PNG         : lossless optimise, then an optional 256-colour palette pass for
              photographic PNGs that won't budge otherwise (clearly labelled).
TIFF        : deflate compression (lossless).
GIF         : optimise (lossless).
BMP         : can't be compressed in-format — reported honestly, original kept.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageOps

from ..result import Result

QUALITY_START = 85   # best-looking starting point
QUALITY_FLOOR = 45   # don't make it uglier than this chasing a number
QUALITY_STEP = 10


def compress(src: Path, out_dir: Path, target_ratio: float) -> Result:
    orig = src.stat().st_size
    ext = src.suffix.lower().lstrip(".")
    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)   # bake in rotation, strip bulky EXIF
    except Exception as exc:
        return Result(False, None, "image", f"couldn't open image: {exc}")

    fmt = (img.format or ext).lower()

    if fmt in ("jpeg", "jpg") or ext in ("jpg", "jpeg"):
        return _quality_search(img, src, out_dir, orig, target_ratio, "JPEG", ".jpg")
    if fmt == "webp" or ext == "webp":
        return _quality_search(img, src, out_dir, orig, target_ratio, "WEBP", ".webp")
    if fmt == "png" or ext == "png":
        return _png(img, src, out_dir, orig, target_ratio)
    if fmt == "tiff" or ext in ("tif", "tiff"):
        out = out_dir / f"{src.stem}.tiff"
        try:
            img.save(out, "TIFF", compression="tiff_deflate")
        except Exception as exc:
            return Result(False, None, "TIFF deflate", f"failed: {exc}")
        return Result(True, out, "TIFF deflate (lossless)")
    if fmt == "gif" or ext == "gif":
        out = out_dir / f"{src.stem}.gif"
        try:
            img.save(out, "GIF", optimize=True, save_all=getattr(img, "is_animated", False))
        except Exception as exc:
            return Result(False, None, "GIF optimize", f"failed: {exc}")
        return Result(True, out, "GIF optimize (lossless)")
    if fmt == "bmp" or ext == "bmp":
        return Result(False, None, "BMP",
                      "BMP is uncompressed by design — can't shrink it staying .bmp "
                      "(convert it to PNG/JPEG to save space)")
    return Result(False, None, "image", f"unsupported image format: {fmt}")


def _quality_search(img, src, out_dir, orig, target_ratio, pil_fmt, ext) -> Result:
    """Encode at the highest quality that still meets the size target."""
    if pil_fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    target = orig * target_ratio
    best = None
    q = QUALITY_START
    while q >= QUALITY_FLOOR:
        trial = out_dir / f"{src.stem}_q{q}{ext}"
        try:
            if pil_fmt == "JPEG":
                img.save(trial, "JPEG", quality=q, optimize=True, progressive=True)
            else:
                img.save(trial, "WEBP", quality=q, method=6)
        except Exception as exc:
            return Result(False, None, f"{pil_fmt} re-encode", f"failed: {exc}")
        best = (trial, q, trial.stat().st_size)
        if best[2] <= target:          # highest quality that hits the target — stop here
            break
        q -= QUALITY_STEP

    trial, q, size = best
    final = out_dir / f"{src.stem}{ext}"
    if trial != final:
        os.replace(trial, final)
    note = f"quality {q}"
    if size > target:
        note += " — hit the quality floor, this is as small as it goes without visible loss"
    return Result(True, final, f"{pil_fmt} re-encode", note)


def _png(img, src, out_dir, orig, target_ratio) -> Result:
    out = out_dir / f"{src.stem}.png"
    try:
        img.save(out, "PNG", optimize=True)
    except Exception as exc:
        return Result(False, None, "PNG optimize", f"failed: {exc}")
    note = "lossless optimise"

    # Photographic PNGs won't hit the target losslessly — try a 256-colour palette.
    if out.stat().st_size > orig * target_ratio:
        try:
            base = img.convert("RGB") if img.mode in ("RGB", "L") else img.convert("RGBA")
            palette = base.quantize(colors=256, method=Image.FASTOCTREE)
            trial = out_dir / f"{src.stem}_pal.png"
            palette.save(trial, "PNG", optimize=True)
            if trial.stat().st_size < out.stat().st_size:
                os.replace(trial, out)
                note = "palette-reduced to 256 colours (slight colour loss)"
            else:
                trial.unlink(missing_ok=True)
        except Exception:
            pass   # palette pass is best-effort; lossless result still stands
    return Result(True, out, "PNG", note)
