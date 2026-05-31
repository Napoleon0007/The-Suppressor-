# The Suppressor

A universal file compressor. Drop in **any** file, in **any** format, and get a much smaller version back — no quality sliders, no "compress down to X" menu. You give it files, it picks the best route, and hands back the smallest sensible result.

## How it works — cross-pollination = smart format routing

One drop zone for you. Under the hood, the **router** (`engine/router.py`) sniffs each file's real type (magic bytes first, extension as fallback) and sends it down the best compression chain for that kind of file. You never choose a method or a target size — the router decides.

| Input | Chain | What it does |
|-------|-------|--------------|
| Video (.mp4/.mov/.mkv/.avi…) | `chains/video.py` | H.265 (HEVC) re-encode, CRF 30, AAC audio |
| Audio — lossless (.wav/.flac/.aiff) | `chains/audio.py` | → Opus 96 kbps (transparent, ~90% smaller) |
| Audio — lossy (.mp3/.m4a/.ogg) | `chains/audio.py` | re-encode in-family at a lower bitrate |
| Images (.jpg/.png/.webp/.tiff/.gif) | `chains/image.py` | quality search / lossless optimise |
| PDF | `chains/pdf.py` | Ghostscript /ebook downsample (pikepdf fallback) |
| Anything else | `chains/binary.py` | LZMA/xz max compression (stdlib) |

## The 75% target — and the honesty rule

The router pushes hard for **at least 75% smaller while keeping quality**. That's very achievable for video, lossless audio, high-quality JPEGs and raw binaries.

For files that are *already* compressed (a maxed-out JPEG, a small H.264 clip), nothing can take 75% off without wrecking quality — so The Suppressor **keeps the original untouched and tells you why**. Two hard guarantees:

1. **The output is never bigger than the input.** Ever. (Enforced in `router.route()`.)
2. **Format changes are always labelled** (e.g. WAV → Opus, or any file → .xz).

## Run it locally

```bash
cd The-Suppressor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Opens on <http://127.0.0.1:7437> (auto-picks a free port if 7437 is taken).

## Dependencies

- **Python 3**, **Flask**, **Pillow** — required.
- **ffmpeg** — required for the video/audio chains (`brew install ffmpeg`).
- **Ghostscript** — optional, best PDF shrink (`brew install ghostscript`). Without it, PDFs fall back to lossless pikepdf or are left untouched.
- LZMA/xz for the generic chain ships with Python — nothing to install.

## Deploy (Railway)

**Live:** https://the-suppressor-production.up.railway.app

Built from the `Dockerfile` (`python:3.12-slim` + `apt install ffmpeg`, served by waitress on `$PORT`). The Dockerfile is deliberate — it guarantees ffmpeg is present, which nixpacks did not. Redeploy with `railway up --service the-suppressor --ci`.

Note: heavy video re-encodes are CPU-bound and slow on small instances — best run locally for large media.
