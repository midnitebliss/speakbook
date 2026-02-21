# speakbook

Convert EPUB files into M4B audiobooks using ElevenLabs TTS, with support for voice cloning.

Built to narrate *The Inimitable Jeeves* in the voice of Sir Stephen Fry.

---

## Requirements

- Python 3.10+
- ffmpeg (for audio assembly)
- An [ElevenLabs](https://elevenlabs.io) account and API key

---

## Installation

```bash
# Install system dependency
brew install ffmpeg

# Install Python dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and add your key:
#   ELEVENLABS_API_KEY=your_key_here
```

---

## Usage

### 1. Dry run — inspect chapters, no API calls

```bash
python speakbook.py "The Inimitable Jeeves.epub/" --dry-run
```

Output:
```
Found 18 chapters:
   1. Chapter I: Jeeves Exerts The Old Cerebellum     3024 words   16372 chars
   2. Chapter II: No Wedding Bells For Bingo          2802 words   14739 chars
   ...
  Total: 370,446 chars | ~78 API chunks | ~$111.13 at pay-as-you-go
```

### 2. Get a Stephen Fry voice sample

Find a YouTube clip of Stephen Fry speaking clearly — no background music, no other voices. Good sources:

- The official **QI YouTube channel**
- **Penguin Books** audiobook trailers
- Any interview or lecture with clear audio

Then download and prepare the sample:

```bash
python get_voice_sample.py \
  --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
  --start 30 \
  --duration 120 \
  --output stephen_fry_sample.mp3
```

Options:
- `--start` — skip N seconds at the beginning (e.g. to skip an intro)
- `--duration` — how many seconds to extract (120 = 2 minutes; 1–5 minutes is ideal)

> **Tip:** If ElevenLabs' public Voice Library already has a Stephen Fry voice, speakbook will find and use it automatically — no sample needed.

### 3. Test with one chapter

Before committing to the full book, test with a single chapter to validate the voice quality:

```bash
python speakbook.py "The Inimitable Jeeves.epub/" \
  --voice-sample stephen_fry_sample.mp3 \
  --chapters 1-1 \
  --model eleven_turbo_v2_5
```

This produces `output/The_Inimitable_Jeeves.m4b` with just Chapter One. Open it in Apple Books or VLC to check how it sounds.

### 4. Full book

Once you're happy with the voice, run the full conversion:

```bash
python speakbook.py "The Inimitable Jeeves.epub/" \
  --voice-sample stephen_fry_sample.mp3
```

Output: `output/The_Inimitable_Jeeves.m4b`

This takes a while (the book is ~370k characters across ~78 API calls). Progress is saved after every chunk — if it fails or you stop it, re-running will resume from where it left off.

---

## All CLI Options

```
python speakbook.py <epub_path> [options]

Positional:
  epub_path             Path to EPUB file or expanded EPUB directory

Voice options:
  --voice-sample FILE   Audio sample for voice cloning (MP3/WAV, 30s–5min)
  --voice-id ID         Use a specific ElevenLabs voice ID directly
  --no-library-search   Skip searching the ElevenLabs Voice Library

Model options:
  --model MODEL         TTS model to use (default: eleven_multilingual_v2)
                        Options: eleven_multilingual_v2 (quality)
                                 eleven_turbo_v2_5 (faster, same price)
                                 eleven_monolingual_v1 (older)

Output options:
  --output-dir DIR      Output directory (default: ./output)
  --chapters RANGE      Process only specific chapters, e.g. '1-3' or '5'
  --no-resume           Ignore previous progress and start fresh
  --dry-run             Parse EPUB and list chapters without calling the API
```

---

## Voice Setup — How It Works

On first run, speakbook resolves the voice in this order:

1. **Cached** — if `VOICE_ID` is already saved in `.env`, use it immediately
2. **Voice Library** — searches ElevenLabs' public library for "Stephen Fry"; uses the first match
3. **Voice Cloning** — if `--voice-sample` is provided, uploads it via Instant Voice Cloning
4. **Default** — falls back to ElevenLabs' built-in Aria voice

The resolved voice ID is saved to `.env` automatically so future runs skip setup.

To force a different voice, clear `VOICE_ID=` in `.env` or pass `--voice-id` directly.

---

## ElevenLabs Pricing

The Inimitable Jeeves is ~370,000 characters. Rates below are for the **Flash/Turbo** model (`eleven_turbo_v2_5`).

| Plan | Monthly fee | Chars included | Overage rate | **Total for this book** |
|---|---|---|---|---|
| Free | $0 | 20,000 | — | Not enough |
| Starter | $5 | 60,000 | No overage | Not enough |
| **Creator** | **$22** (first month **$11**) | **200,000** | **$0.15 / 1K** | **~$47.60** (~$36.60 first month) |
| Pro | $99 | 1,000,000 | $0.12 / 1K | $99 (full quota, nothing extra) |

**Recommended:** Sign up for **Creator** ($22/mo, half-price first month), run the full book, then cancel. Total cost: ~$37–$48.

> The `eleven_multilingual_v2` model (default) has slightly higher per-character rates than Turbo. Use `--model eleven_turbo_v2_5` to stay on the cheaper Flash/Turbo pricing with near-identical quality.

Voice cloning (Instant Voice Cloning) requires **Creator plan or above**.

---

## Output Format

The final `.m4b` file contains:

- **AAC audio** at 64 kbps (standard audiobook quality, small file size)
- **18 named chapter markers** — navigate by chapter in Apple Books, Overcast, VLC, etc.
- **Embedded cover art** (taken from the EPUB)
- **Metadata**: title, author, genre

---

## Resuming After Interruption

Progress is saved to `output/progress.json` after every API chunk. If the process is interrupted:

```bash
# Just re-run the same command — it picks up where it left off
python speakbook.py "The Inimitable Jeeves.epub/"
```

To start fresh instead:

```bash
python speakbook.py "The Inimitable Jeeves.epub/" --no-resume
```

---

## Project Structure

```
speakbook/
├── speakbook.py          # CLI entry point
├── epub_parser.py        # EPUB → Chapter objects
├── tts_engine.py         # Text chunking + ElevenLabs API calls
├── voice_setup.py        # Voice library / cloning / .env persistence
├── m4b_builder.py        # ffmpeg → M4B with chapter markers
├── get_voice_sample.py   # yt-dlp helper for voice sample acquisition
├── requirements.txt
├── .env.example
└── output/               # Created at runtime
    ├── audio_chunks/     # Per-chunk MP3 files
    ├── chapters/         # Per-chapter MP3 files
    ├── progress.json     # Resumability state
    └── *.m4b             # Final audiobook
```
