# speakbook

Convert documents into audiobooks using ElevenLabs TTS, with support for voice cloning.

Supports **EPUB**, **Markdown**, and **PDF** input — outputs **M4B** (with chapter markers) or **MP3**.

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

## Supported Formats

| Input | How chapters are detected |
|---|---|
| **EPUB** (directory or ZIP) | Table of contents (`toc.ncx`) |
| **Markdown** (`.md`) | `#` / `##` headings; YAML frontmatter for title/author |
| **PDF** | PDF bookmarks → heading patterns → fixed page chunks |

---

## Usage

### 1. Dry run — inspect chapters, no API calls

```bash
python speakbook.py "The Inimitable Jeeves.epub/" --dry-run
python speakbook.py essay.md --dry-run
python speakbook.py book.pdf --dry-run
```

### 2. Get a voice sample (optional)

Find a YouTube clip of someone speaking clearly — no background music, no other voices.

```bash
python get_voice_sample.py \
  --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
  --start 30 \
  --duration 120 \
  --output voice_sample.mp3
```

> **Tip:** If ElevenLabs' public Voice Library already has the voice you want, speakbook will find and use it automatically — no sample needed.

### 3. Test with one chapter

```bash
python speakbook.py book.epub --voice-sample voice_sample.mp3 --chapters 1-1
```

### 4. Full conversion

```bash
# M4B with chapter markers (default)
python speakbook.py book.epub --voice-sample voice_sample.mp3

# MP3 output
python speakbook.py essay.md --format mp3

# Custom output path
python speakbook.py book.pdf --output ~/Desktop/audiobook.m4b
```

Progress is saved after every chunk — if interrupted, re-running the same command resumes where it left off.

---

## All CLI Options

```
python speakbook.py <input_path> [options]

Positional:
  input_path            Path to EPUB, Markdown (.md), or PDF file

Voice options:
  --voice-sample FILE   Audio sample for voice cloning (MP3/WAV, 30s-5min)
  --voice-id ID         Use a specific ElevenLabs voice ID directly
  --no-library-search   Skip searching the ElevenLabs Voice Library

Model options:
  --model MODEL         TTS model (default: eleven_turbo_v2_5)
                        Options: eleven_turbo_v2_5 (faster, cheaper)
                                 eleven_multilingual_v2 (quality)
                                 eleven_monolingual_v1 (older)

Output options:
  --format {m4b,mp3}    Output format (default: m4b)
  --output PATH         Output file path (default: output/<Title>.m4b/.mp3)
  --output-dir DIR      Working directory for intermediate files (default: ./output)
  --chapters RANGE      Process only specific chapters, e.g. '1-3' or '5'
  --max-chars N         Limit total characters sent to TTS (truncates at sentence boundary)
  --no-resume           Ignore previous progress and start fresh
  --dry-run             Parse input and list chapters without calling TTS API
```

---

## Voice Setup — How It Works

On first run, speakbook resolves the voice in this order:

1. **Cached** — if `VOICE_ID` is already saved in `.env`, use it immediately
2. **Voice Library** — searches ElevenLabs' public library for a matching voice
3. **Voice Cloning** — if `--voice-sample` is provided, uploads it via Instant Voice Cloning
4. **Default** — falls back to ElevenLabs' built-in Aria voice

The resolved voice ID is saved to `.env` automatically so future runs skip setup.

To force a different voice, clear `VOICE_ID=` in `.env` or pass `--voice-id` directly.

---

## ElevenLabs Pricing

Rates below are for the **Flash/Turbo** model (`eleven_turbo_v2_5`).

| Plan | Monthly fee | Chars included | Overage rate |
|---|---|---|---|
| Free | $0 | 20,000 | — |
| Starter | $5 | 60,000 | No overage |
| **Creator** | **$22** (first month **$11**) | **200,000** | **$0.15 / 1K** |
| Pro | $99 | 1,000,000 | $0.12 / 1K |

Voice cloning (Instant Voice Cloning) requires **Creator plan or above**.

---

## Output Format

**M4B** (default):
- AAC audio at 64 kbps
- Named chapter markers — navigate in Apple Books, Overcast, VLC, etc.
- Embedded cover art (from EPUB, if available)
- Title, author, genre metadata

**MP3**:
- Concatenated chapter audio, no chapter markers

---

## Resuming After Interruption

Progress is saved to `output/progress.json` after every API chunk.

```bash
# Re-run the same command — picks up where it left off
python speakbook.py book.epub

# Start fresh
python speakbook.py book.epub --no-resume
```

---

## Project Structure

```
speakbook/
├── speakbook.py          # CLI entry point
├── models.py             # Chapter + BookMetadata dataclasses
├── parsers/
│   ├── __init__.py       # Format dispatcher (epub/md/pdf)
│   ├── base.py           # ParseResult, clean_text()
│   ├── epub_parser.py    # EPUB → chapters (toc.ncx + content.opf)
│   ├── markdown_parser.py # Markdown → chapters (headings + frontmatter)
│   └── pdf_parser.py     # PDF → chapters (bookmarks/heuristics)
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
    └── *.m4b / *.mp3     # Final audiobook
```
