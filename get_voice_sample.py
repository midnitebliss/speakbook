#!/usr/bin/env python3
"""
get_voice_sample.py — Download and prepare a voice sample for ElevenLabs voice cloning.

This tool downloads audio from a YouTube URL using yt-dlp, trims it to the
desired segment, and normalizes the volume. The result is suitable for uploading
to ElevenLabs Instant Voice Cloning.

Usage:
  python get_voice_sample.py --url "https://youtube.com/watch?v=..." \\
                              --start 30 --duration 120 \\
                              --output stephen_fry.mp3

Tips for finding Stephen Fry audio:
  - Search YouTube for "Stephen Fry reading" or "Stephen Fry lecture"
  - The QI YouTube channel (official) has many Fry clips
  - Penguin Books has audiobook trailer clips
  - Look for clips with NO background music and clear speech

Ideal sample characteristics for best voice clone quality:
  - 1-5 minutes of clean, uninterrupted speech
  - No background music, sound effects, or other voices
  - Single speaker only (Stephen Fry)
  - Clear, high-quality audio (not phone recordings)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and trim a YouTube audio clip for voice cloning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python get_voice_sample.py \\
    --url "https://www.youtube.com/watch?v=XXXXXXXXXX" \\
    --start 30 \\
    --duration 120 \\
    --output stephen_fry.mp3
        """,
    )
    parser.add_argument(
        "--url", type=str, required=True,
        help="YouTube URL to download audio from",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("stephen_fry_sample.mp3"),
        help="Output file path (default: stephen_fry_sample.mp3)",
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start time in seconds, e.g. 30 to skip an intro (default: 0)",
    )
    parser.add_argument(
        "--duration", type=int, default=120,
        help="Duration in seconds to extract (default: 120 = 2 minutes)",
    )
    parser.add_argument(
        "--no-normalize", action="store_true",
        help="Skip loudness normalization",
    )
    return parser.parse_args()


def check_dependencies():
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp   →  pip install yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg   →  brew install ffmpeg")
    if missing:
        print("Missing required tools:")
        for dep in missing:
            print(f"  {dep}")
        sys.exit(1)


def download_audio(url: str, output_path: Path) -> Path:
    """Download best-quality audio from YouTube as MP3."""
    print(f"Downloading: {url}")
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",        # best quality
        "--output", str(output_path),
        "--no-playlist",
        url,
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("ERROR: yt-dlp download failed.")
        sys.exit(1)
    return output_path


def trim_audio(input_path: Path, output_path: Path, start_sec: int, duration_sec: int) -> Path:
    """Trim audio to the desired segment."""
    print(f"Trimming: {start_sec}s to {start_sec + duration_sec}s ({duration_sec}s total)")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-c", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {result.stderr}")
    return output_path


def normalize_audio(input_path: Path, output_path: Path) -> Path:
    """Normalize audio loudness using EBU R128 standard (good for voice)."""
    print("Normalizing loudness...")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", "44100",
        "-ac", "1",       # mono is fine for voice cloning
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg normalize failed: {result.stderr}")
    return output_path


def main():
    args = parse_args()
    check_dependencies()

    # Temp files in same directory as output
    out_dir = args.output.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"_raw_{args.output.name}"
    trimmed_path = out_dir / f"_trimmed_{args.output.name}"

    try:
        download_audio(args.url, raw_path)

        trim_audio(raw_path, trimmed_path, args.start, args.duration)

        if args.no_normalize:
            trimmed_path.rename(args.output)
        else:
            normalize_audio(trimmed_path, args.output)

    finally:
        raw_path.unlink(missing_ok=True)
        trimmed_path.unlink(missing_ok=True)

    size_kb = args.output.stat().st_size // 1024
    print(f"\nVoice sample ready: {args.output}  ({size_kb} KB, {args.duration}s)")
    print(f"\nNext step:")
    print(f'  python speakbook.py "The Inimitable Jeeves.epub/" --voice-sample {args.output} --dry-run')


if __name__ == "__main__":
    main()
