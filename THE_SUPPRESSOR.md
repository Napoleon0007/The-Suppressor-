# THE SUPPRESSOR — Master Document

> A universal file compressor by **Rex Trueform**. Drop any file, in any format, and get a far smaller version back — or convert it to a format you choose. The user never has to understand compression; the tool decides the best route.

This is the single source of truth for the project. Everything — what it is, how it's built, every chain, every conversion, the rules it lives by, how to run it and ship it — lives here.

---

## 1. What it is

| | |
|---|---|
| **Name** | The Suppressor (Luke verbally calls it "the compressor") |
| **Owner / brand** | Rex Trueform — orange `#E46113` on black |
| **Repo** | [Napoleon0007/The-Suppressor-](https://github.com/Napoleon0007/The-Suppressor-) |
| **Local path** | `~/Desktop/The-Suppressor/` |
| **Stack** | Python 3 · Flask · vanilla JS · ffmpeg · Pillow |
| **Built** | 31 May 2026 |

The whole pitch: **one drop zone, zero required decisions.** You drop files, the router works out what each one is and sends it down the best compression chain for that type. No quality sliders, no "compress to X MB" menus.

---

## 2. The two modes

Every file in the queue gets a per-file mode picker:

1. **Auto · compress (keep format)** — the default. Shrinks the file and keeps it the same type. A smaller `.jpg` is still a `.jpg`. Aims for a big reduction without visibly hurting quality.
2. **Convert to…** — converts *and* compresses into a standard format you choose. The dropdown only ever shows valid targets for that file's type (drop a `.wav`, you see audio formats; drop an `.mp4`, you see video formats plus sensible cross-options like "rip to MP3" or "make a GIF"). No nonsense pairings.

---

## 3. Architecture

```
The-Suppressor/
├── app.py                  Flask server: upload, dispatch, download, cleanup
├── engine/
│   ├── router.py           sniffs file type, routes to a chain (the "brain")
│   ├── convert.py          Convert-to mode: Pillow + ffmpeg conversions
│   ├── result.py           shared Result dataclass
│   └── chains/             Auto-mode compressors, one per media kind
│       ├── image.py        JPEG/WebP quality-search · PNG/TIFF/GIF lossless
│       ├── video.py        H.265 (HEVC) re-encode via ffmpeg
│       ├── audio.py        lossless→Opus · lossy→re-encode in-family
│       ├── pdf.py          Ghostscript /ebook (pikepdf fallback)
│       └── binary.py       LZMA/xz, standard library, always available
├── templates/index.html    Rex Trueform branded UI
├── static/                 style.css · app.js · logo.png (Rex Trueform mark)
├── requirements.txt        Flask · Pillow · waitress
├── Procfile                waitress-serve … app:app   (Railway start command)
├── nixpacks.toml           installs ffmpeg on Railway
└── THE_SUPPRESSOR.md       this document
```

### How a file flows
1. **Upload** — `app.py /compress` saves each file into a temp batch dir.
2. **Sniff** — `router.sniff()` reads magic bytes (extension only as fallback) → `image | video | audio | pdf | other`.
3. **Route** — `router.route(src, out_dir, target)`:
   - `target=None` → Auto mode → the matching chain in `engine/chains/`.
   - `target="webp"` (etc.) → Convert mode → `engine/convert.py`.
4. **Report** — sizes compared, percentage saved computed, result returned as JSON.
5. **Download** — each output is held by an id and served via `/download/<id>`. Batches older than 1 hour are purged.

---

## 4. The compression chains (Auto mode)

| Input | Chain | Method |
|-------|-------|--------|
| Video — mp4/mov/mkv/avi… | `video.py` | H.265 (HEVC), CRF 30, AAC 128k audio; falls back to .mp4 if the container can't hold HEVC |
| Audio — lossless (wav/flac/aiff) | `audio.py` | → Opus 96 kbps (transparent, ~90% smaller) — format change, labelled |
| Audio — lossy (mp3/m4a/ogg) | `audio.py` | re-encode in-family at a lower bitrate |
| Image — JPEG/WebP | `image.py` | quality search: highest quality that still hits the target, floor at 45 |
| Image — PNG | `image.py` | lossless optimise, then optional 256-colour palette for stubborn photographic PNGs (labelled) |
| Image — TIFF/GIF | `image.py` | deflate / optimise (lossless) |
| Image — BMP | `image.py` | left untouched — uncompressible staying .bmp |
| PDF | `pdf.py` | Ghostscript `/ebook` downsample; pikepdf lossless fallback; else kept + install hint |
| Anything else | `binary.py` | LZMA/xz max compression → `.xz` (stdlib, no external tool) |

---

## 5. The conversion matrix (Convert-to mode)

Single source of truth: `engine/convert.py → TARGETS` (mirrored in `static/app.js`).

| Drop this | You can convert to |
|-----------|--------------------|
| **Image** | jpg · png · webp · tiff · gif · bmp · pdf |
| **Audio** | mp3 · wav · flac · m4a · opus · ogg |
| **Video** | mp4 · mov · mkv · webm · avi · gif · **mp3 / m4a** (rip audio) |
| **PDF / other** | — (Auto compress only) |

- Images use **Pillow**; audio/video use **ffmpeg**.
- Convert-to is intentionally **not** held to the never-bigger rule — if you ask JPG→PNG and PNG is genuinely bigger, you get it (shown as `+%`), because you chose it on purpose.
- Impossible-but-sensible requests fail cleanly with a human message (e.g. extracting audio from a silent video → *"this file has no audio track to extract"*, original returned).

---

## 6. The rules it lives by

1. **Auto output is never bigger than the input.** Enforced in `router.route()` — any chain result that isn't actually smaller is discarded and the original is kept.
2. **Honesty over fake numbers.** Already-compressed files (a maxed JPEG, a tiny H.264 clip) can't lose 75% without wrecking quality, so the tool keeps them and *says why* rather than producing a worse file.
3. **Every format change is labelled** in the UI (WAV → Opus, anything → .xz, etc.).
4. **Only valid targets are offered** for the file you dropped — the picker can't suggest nonsense.

---

## 7. Running it locally

```bash
cd ~/Desktop/The-Suppressor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py            # → http://127.0.0.1:7437 (auto-picks a free port)
```

**Dependencies**
- Python 3, Flask, Pillow — required (`pip install -r requirements.txt`).
- **ffmpeg** — required for video/audio (`brew install ffmpeg`).
- **Ghostscript** — optional, best PDF shrink (`brew install ghostscript`). Without it, PDFs fall back to lossless pikepdf or are left untouched.
- LZMA/xz ships with Python — nothing to install.

---

## 8. Deploying (Railway)

- `Procfile` starts the app with **waitress** on `$PORT`.
- `nixpacks.toml` installs **ffmpeg** into the build (without it, the media chains break in the cloud — this is the #1 deploy gotcha).
- **Known limit:** H.265 / VP9 video re-encodes are CPU-heavy and slow on small instances — large videos may take minutes or time out. Images, audio, PDFs and the generic chain are snappy in the cloud. Heavy video is best run locally.

---

## 9. Branding

- Logo: the Rex Trueform orange silhouette (`static/logo.png`), used as the header mark and favicon.
- Palette: orange `#E46113` (primary), lighter `#F4842E` (accents/hover), black/near-black surfaces, off-white text.
- Type: **Poppins** (headings) + **Inter** (body). Clean and professional — no neon.

---

## 10. Roadmap / ideas

- [ ] AVIF / HEIC image support (needs a Pillow plugin).
- [ ] PDF → image export (needs poppler).
- [ ] "Download all as .zip" for a batch.
- [ ] Optional target-size control for power users (kept opt-in so Auto stays zero-decision).
- [ ] Progress per file for long video encodes.

---

## 11. Changelog

- **31 May 2026** — Initial build: smart-routing compressor, 5 chains, never-bigger guarantee. Verified live end to end.
- **31 May 2026** — Added Convert-to mode (per-file Auto / convert picker) with the conversion matrix and clean human errors.
- **31 May 2026** — Rebranded the front end to the Rex Trueform identity (orange/black, logo, Poppins/Inter); added `nixpacks.toml` for Railway ffmpeg.
