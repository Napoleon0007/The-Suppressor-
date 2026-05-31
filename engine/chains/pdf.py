"""PDF chain.

Best results come from Ghostscript's /ebook downsample (shrinks embedded
images, the usual bloat). If Ghostscript isn't installed we fall back to
pikepdf's lossless stream compression, and if neither is available we keep
the original and tell the user the one-line install for real shrinkage.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..result import Result

GS = shutil.which("gs")
TIMEOUT = 600


def compress(src: Path, out_dir: Path, target_ratio: float) -> Result:
    out = out_dir / f"{src.stem}.pdf"

    if GS:
        cmd = [
            GS, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
            "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={out}", str(src),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return Result(False, None, "PDF", "timed out")
        if proc.returncode == 0 and out.exists():
            return Result(True, out, "Ghostscript /ebook downsample")
        err = (proc.stderr or b"").decode("utf-8", "ignore")[-300:]
        return Result(False, None, "PDF", f"ghostscript failed: {err}")

    # Fallback: lossless object-stream compression via pikepdf (if installed).
    try:
        import pikepdf
        with pikepdf.open(src) as doc:
            doc.save(out, compress_streams=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate)
        return Result(True, out, "pikepdf stream compression (lossless)")
    except ImportError:
        return Result(False, None, "PDF",
                      "needs Ghostscript for real shrinkage — install: brew install ghostscript")
    except Exception as exc:
        return Result(False, None, "PDF", f"failed: {exc}")
