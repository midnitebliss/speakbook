#!/usr/bin/env python3
"""
speakbook — Convert documents to audiobooks using ElevenLabs TTS.

Supported input formats: EPUB, Markdown (.md), PDF
Output formats: M4B (with chapter markers) or MP3

Quick start:
  1. Add ELEVENLABS_API_KEY to .env
  2. python speakbook.py "The Inimitable Jeeves.epub/" --dry-run
  3. python speakbook.py "The Inimitable Jeeves.epub/" --chapters 1-1
  4. python speakbook.py "The Inimitable Jeeves.epub/"

Voice cloning:
  python get_voice_sample.py --url "https://youtube.com/..." --output fry.mp3
  python speakbook.py "The Inimitable Jeeves.epub/" --voice-sample fry.mp3
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ERROR: ffmpeg/ffprobe not found.")
        print("Install with: brew install ffmpeg")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert documents (EPUB, Markdown, PDF) to audiobooks using ElevenLabs TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run — list chapters, no API calls:
  python speakbook.py "The Inimitable Jeeves.epub/" --dry-run
  python speakbook.py essay.md --dry-run
  python speakbook.py book.pdf --dry-run

  # Convert to MP3 (simpler, no chapters):
  python speakbook.py essay.md --format mp3

  # Save output to a specific location:
  python speakbook.py book.epub --output ~/Desktop/audiobook.m4b

  # Test first 2 chapters:
  python speakbook.py book.epub --chapters 1-2

  # Voice cloning from a sample:
  python speakbook.py book.epub --voice-sample fry.mp3
        """,
    )
    parser.add_argument("input_path", type=Path, help="Path to EPUB, Markdown (.md), or PDF file")
    parser.add_argument(
        "--voice-sample", type=Path, default=None, metavar="FILE",
        help="Audio sample for voice cloning (MP3/WAV, 30s-5min)",
    )
    parser.add_argument(
        "--voice-id", type=str, default=None, metavar="ID",
        help="Use a specific ElevenLabs voice ID directly",
    )
    parser.add_argument(
        "--no-library-search", action="store_true", default=False,
        help="Skip searching ElevenLabs Voice Library",
    )
    parser.add_argument(
        "--model",
        choices=["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_monolingual_v1"],
        default="eleven_turbo_v2_5",
        help="ElevenLabs TTS model (default: eleven_turbo_v2_5)",
    )
    parser.add_argument(
        "--format", choices=["m4b", "mp3"], default="m4b", dest="output_format",
        help="Output format: m4b (with chapters) or mp3 (default: m4b)",
    )
    parser.add_argument(
        "--output", type=Path, default=None, metavar="PATH",
        help="Output file path (default: output/<Title>.m4b or .mp3)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"), metavar="DIR",
        help="Working directory for intermediate files (default: ./output)",
    )
    parser.add_argument(
        "--chapters", type=str, default=None, metavar="RANGE",
        help="Process only these chapters, e.g. '1-3' or '5'",
    )
    parser.add_argument(
        "--max-chars", type=int, default=None, metavar="N",
        help="Limit total characters sent to TTS (truncates at sentence boundary)",
    )
    parser.add_argument(
        "--no-resume", action="store_true", default=False,
        help="Ignore previous progress and start fresh",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse input and list chapters without calling TTS API",
    )
    return parser.parse_args()


def truncate_at_sentence_boundary(text: str, max_chars: int) -> str:
    """Truncate text to at most max_chars, cutting at the last sentence end."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    for end in [". ", "! ", "? "]:
        idx = truncated.rfind(end)
        if idx != -1:
            return truncated[:idx + 1]
    idx = truncated.rfind(" ")
    return truncated[:idx] if idx != -1 else truncated


def parse_chapter_range(range_str: str) -> range:
    """Parse '3-7' or '5' into a range (1-indexed, inclusive)."""
    if "-" in range_str:
        start, end = range_str.split("-", 1)
        return range(int(start), int(end) + 1)
    n = int(range_str)
    return range(n, n + 1)


def load_progress(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"completed_chapters": [], "completed_chunks": []}


def save_progress(progress: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progress, indent=2))


def print_chapter_list(chapters, metadata=None, show_chars: bool = True):
    if metadata:
        print(f"Title:  {metadata.title}")
        print(f"Author: {metadata.author}")
        print(f"Format: {metadata.source_format}")
    print(f"\nFound {len(chapters)} chapters:")
    print("-" * 70)
    total_chars = 0
    for ch in chapters:
        word_count = len(ch.text.split())
        char_count = len(ch.text)
        total_chars += char_count
        if show_chars:
            print(f"  {ch.index:2d}. {ch.title:<50} {word_count:>6} words  {char_count:>7} chars")
        else:
            print(f"  {ch.index:2d}. {ch.title}")
    print("-" * 70)
    if show_chars:
        estimated_chunks = total_chars // 4800 + 1
        included = 200_000
        overage = max(0, total_chars - included)
        est_cost = 22 + (overage / 1000 * 0.15)
        print(f"  Total: {total_chars:,} chars | ~{estimated_chunks} API chunks | ~${est_cost:.2f} on Creator plan (Flash/Turbo)")
    print()


def main():
    args = parse_args()
    load_dotenv()

    if not args.dry_run:
        check_ffmpeg()

    # Import parsers and tools (lazy to keep --help fast)
    from parsers import parse_file
    from m4b_builder import (
        build_chapter_marks,
        build_m4b,
        concatenate_audio_files,
        format_duration,
        write_ffmetadata,
    )
    from tts_engine import synthesize_chapter
    from voice_setup import setup_voice

    # Parse input file
    print(f"Parsing: {args.input_path}")
    result = parse_file(args.input_path)
    all_chapters = result.chapters
    metadata = result.metadata

    # Filter chapters if requested
    if args.chapters:
        chapter_range = parse_chapter_range(args.chapters)
        chapters = [ch for ch in all_chapters if ch.index in chapter_range]
        if not chapters:
            print(f"ERROR: No chapters matched range '{args.chapters}' (book has {len(all_chapters)} chapters)")
            sys.exit(1)
    else:
        chapters = all_chapters

    # Truncate text if character budget is set
    if args.max_chars:
        for ch in chapters:
            ch.text = truncate_at_sentence_boundary(ch.text, args.max_chars)

    print_chapter_list(chapters, metadata)

    if args.dry_run:
        print("Dry run complete. No API calls made.")
        return

    # Validate API key
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not set.")
        print("Add it to .env:  ELEVENLABS_API_KEY=your_key_here")
        sys.exit(1)

    from elevenlabs import ElevenLabs
    client = ElevenLabs(api_key=api_key)

    # Resolve voice
    if args.voice_id:
        voice_id = args.voice_id
        print(f"Using voice ID from CLI: {voice_id}")
    else:
        voice_id = setup_voice(
            client,
            sample_path=args.voice_sample,
            use_library=not args.no_library_search,
        )

    print(f"Voice ID: {voice_id}")
    print(f"Model: {args.model}")
    print(f"Output format: {args.output_format}")
    print()

    # Set up output directories
    output_dir = args.output_dir
    chunks_dir = output_dir / "audio_chunks"
    chapters_dir = output_dir / "chapters"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "progress.json"
    progress = {} if args.no_resume else load_progress(progress_file)
    progress.setdefault("completed_chapters", [])
    progress.setdefault("completed_chunks", [])

    def _save(p):
        save_progress(p, progress_file)

    # Phase 1: TTS synthesis
    print("=== Phase 1: Synthesizing audio ===\n")
    chapter_audio_pairs = []

    for chapter in chapters:
        safe_title = chapter.title[:40].replace(" ", "_").replace(":", "").replace("/", "_")
        chapter_mp3 = chapters_dir / f"ch{chapter.index:02d}_{safe_title}.mp3"

        if chapter.index in progress["completed_chapters"] and chapter_mp3.exists():
            print(f"  Skipping Chapter {chapter.index} (already complete)")
            chapter_audio_pairs.append((chapter.title, chapter_mp3))
            continue

        print(f"Chapter {chapter.index}: {chapter.title}")
        chunk_paths = synthesize_chapter(
            client=client,
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            tts_title=chapter.tts_title,
            chapter_text=chapter.text,
            voice_id=voice_id,
            model_id=args.model,
            chunks_dir=chunks_dir,
            progress=progress,
            save_progress_fn=_save,
        )

        print(f"  Concatenating {len(chunk_paths)} chunks...")
        concatenate_audio_files(chunk_paths, chapter_mp3)

        progress["completed_chapters"].append(chapter.index)
        _save(progress)

        chapter_audio_pairs.append((chapter.title, chapter_mp3))
        print()

    # Phase 2: Assemble output
    safe_book_title = metadata.title.replace(" ", "_").replace("/", "_")

    if args.output_format == "mp3":
        # MP3: just concatenate all chapter MP3s
        print("=== Phase 2: Building MP3 ===\n")
        default_output = output_dir / f"{safe_book_title}.mp3"
        output_file = args.output or default_output
        output_file.parent.mkdir(parents=True, exist_ok=True)

        print("  Concatenating all chapters...")
        concatenate_audio_files([p for _, p in chapter_audio_pairs], output_file)

    else:
        # M4B: full chapter-marked audiobook
        print("=== Phase 2: Building M4B ===\n")

        print("  Measuring chapter durations...")
        chapter_marks = build_chapter_marks(chapter_audio_pairs)

        metadata_path = output_dir / "ffmetadata.txt"
        write_ffmetadata(chapter_marks, metadata_path, metadata.title, metadata.author)
        print(f"  Chapter metadata written: {len(chapter_marks)} chapters")

        full_audio = output_dir / "full_audio.mp3"
        print("  Concatenating all chapters...")
        concatenate_audio_files([p for _, p in chapter_audio_pairs], full_audio)

        cover_path = metadata.cover_path
        if cover_path:
            print(f"  Cover image: {cover_path.name}")

        default_output = output_dir / f"{safe_book_title}.m4b"
        output_file = args.output or default_output
        output_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"  Encoding M4B: {output_file}")
        build_m4b(full_audio, metadata_path, cover_path, output_file)

    # Summary
    print(f"\nDone! Audiobook saved to: {output_file}")
    if args.output_format == "m4b":
        total_ms = chapter_marks[-1].end_ms if chapter_marks else 0
        print(f"Total duration: {format_duration(total_ms)}")
        print("Chapters:")
        for mark in chapter_marks:
            start = format_duration(mark.start_ms)
            print(f"  [{start}] {mark.title}")


if __name__ == "__main__":
    main()
