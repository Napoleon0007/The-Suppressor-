#!/usr/bin/env python3
"""The Suppressor — a universal drag-and-drop file compressor.

Drop in any file, in any format. The router detects what it is and sends it
down the best compression chain for that kind of file, aiming for at least a
75% size reduction without trashing quality. The user never picks a method or
a target — and the output is never bigger than the input.
"""
from __future__ import annotations

import atexit
import os
import shutil
import socket
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock

from flask import (Flask, abort, jsonify, render_template, request, send_file)

from engine.router import route

APP_ROOT = Path(__file__).resolve().parent
WORK_ROOT = Path(tempfile.gettempdir()) / "suppressor_work"
WORK_ROOT.mkdir(exist_ok=True)

MAX_UPLOAD = 4 * 1024 ** 3   # 4 GB per request
MAX_AGE = 3600               # purge finished results after 1 hour
DEFAULT_PORT = 7437

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD

# id -> {"path": Path, "name": str, "ts": float}
RESULTS: dict[str, dict] = {}
LOCK = Lock()


def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def purge_old() -> None:
    now = time.time()
    with LOCK:
        for rid in [r for r, v in RESULTS.items() if now - v["ts"] > MAX_AGE]:
            RESULTS.pop(rid, None)
    for batch in WORK_ROOT.glob("batch_*"):
        try:
            if now - batch.stat().st_mtime > MAX_AGE:
                shutil.rmtree(batch, ignore_errors=True)
        except OSError:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/compress", methods=["POST"])
def compress():
    purge_old()
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400

    batch = WORK_ROOT / f"batch_{uuid.uuid4().hex}"
    out_dir = batch / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for f in files:
        name = Path(f.filename or "").name
        if not name:
            continue
        src = batch / name
        f.save(src)
        orig = src.stat().st_size

        res = route(src, out_dir)

        if res.ok and res.out_path and res.out_path.exists():
            new_size = res.out_path.stat().st_size
            saved = (1 - new_size / orig) * 100 if orig else 0.0
            rid = uuid.uuid4().hex
            with LOCK:
                RESULTS[rid] = {"path": res.out_path, "name": res.out_path.name, "ts": time.time()}
            results.append({
                "id": rid,
                "status": "ok",
                "name": name,
                "out_name": res.out_path.name,
                "original_h": human(orig),
                "output_h": human(new_size),
                "saved_pct": round(saved, 1),
                "met_target": saved >= 75,
                "method": res.method,
                "note": res.note,
                "format_changed": res.format_changed,
            })
        else:
            # Nothing helped — let the user pull the original back unchanged.
            rid = uuid.uuid4().hex
            with LOCK:
                RESULTS[rid] = {"path": src, "name": name, "ts": time.time()}
            results.append({
                "id": rid,
                "status": "skip",
                "name": name,
                "out_name": name,
                "original_h": human(orig),
                "output_h": human(orig),
                "saved_pct": 0.0,
                "met_target": False,
                "method": res.method,
                "note": res.note or "couldn't shrink this one further",
                "format_changed": False,
            })
    return jsonify({"results": results})


@app.route("/download/<rid>")
def download(rid):
    with LOCK:
        info = RESULTS.get(rid)
    if not info or not Path(info["path"]).exists():
        abort(404)
    return send_file(info["path"], as_attachment=True, download_name=info["name"])


def pick_port(preferred: int) -> int:
    """Return `preferred` if free, otherwise an OS-assigned open port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@atexit.register
def _cleanup():
    shutil.rmtree(WORK_ROOT, ignore_errors=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 0)) or pick_port(DEFAULT_PORT)
    print(f"\n  The Suppressor  →  http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
