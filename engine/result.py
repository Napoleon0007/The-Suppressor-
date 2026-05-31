"""Shared result type returned by every compression chain.

Kept in its own module so chains and the router can both import it
without a circular dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Result:
    ok: bool                       # True if a genuinely smaller file was produced
    out_path: Optional[Path]       # path to the compressed file (None = keep original)
    method: str                    # short human description of what the chain did
    note: str = ""                 # honest extra detail (quality floor hit, format change, why it failed)
    format_changed: bool = False   # True if the output is a different file type than the input
