"""Generic binary chain — the catch-all for anything that isn't a recognised
media type (documents, datasets, logs, raw binaries, ...).

Uses LZMA/xz from the Python standard library (always available, no external
tool needed) at maximum compression. Output is a `.xz` file — decompress with
`xz -d file.xz` or any archive tool. The router's never-bigger safety net
keeps the original for things that are already compressed (zip, jpg renamed,
etc.) where xz can't help.
"""
from __future__ import annotations

import lzma
from pathlib import Path

from ..result import Result

CHUNK = 1024 * 1024   # stream in 1 MB blocks so big files don't eat RAM


def compress(src: Path, out_dir: Path, target_ratio: float) -> Result:
    out = out_dir / f"{src.name}.xz"
    filt = lzma.FORMAT_XZ
    try:
        with open(src, "rb") as fin, \
                lzma.open(out, "wb", format=filt, preset=9 | lzma.PRESET_EXTREME) as fout:
            while True:
                chunk = fin.read(CHUNK)
                if not chunk:
                    break
                fout.write(chunk)
    except Exception as exc:
        return Result(False, None, "LZMA/xz", f"failed: {exc}")
    return Result(True, out, "LZMA/xz (lossless)",
                  "decompress with: xz -d", format_changed=True)
