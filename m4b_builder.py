"""m4b_builder.py — Assemble per-chapter MP3s into a final M4B with chapter markers."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChapterMark:
    title: str
    start_ms: int
    end_ms: int


def _run(cmd: list[str], desc: str = "") -> None:
    """Run a subprocess command, raising on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({desc}): {' '.join(cmd)}\n"
            f"stderr: {result.stderr[-2000:]}"
        )


def get_audio_duration_ms(audio_path: Path) -> int:
    """Return duration of an audio file in milliseconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {audio_path}: {result.stderr}")
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if duration:
            return int(float(duration) * 1000)
    raise ValueError(f"Could not determine duration of {audio_path}")


def concatenate_audio_files(input_paths: list[Path], output_path: Path) -> Path:
    """Concatenate multiple MP3 files into one using ffmpeg concat demuxer."""
    if len(input_paths) == 1:
        # Single file: just copy it
        _run(
            ["ffmpeg", "-y", "-i", str(input_paths[0]), "-c", "copy", str(output_path)],
            desc="copy single chunk",
        )
        return output_path

    # Write concat list to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, dir=output_path.parent
    ) as tmp:
        for p in input_paths:
            # ffmpeg concat list uses single-quoted paths
            tmp.write(f"file '{p.resolve()}'\n")
        concat_list = Path(tmp.name)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ],
            desc="concatenate audio",
        )
    finally:
        concat_list.unlink(missing_ok=True)

    return output_path


def build_chapter_marks(chapter_audio_pairs: list[tuple[str, Path]]) -> list[ChapterMark]:
    """
    Given list of (title, mp3_path), compute cumulative chapter start/end times.
    Returns list of ChapterMark objects.
    """
    marks = []
    cursor_ms = 0
    for title, path in chapter_audio_pairs:
        duration_ms = get_audio_duration_ms(path)
        marks.append(ChapterMark(
            title=title,
            start_ms=cursor_ms,
            end_ms=cursor_ms + duration_ms,
        ))
        cursor_ms += duration_ms
    return marks


def write_ffmetadata(
    chapter_marks: list[ChapterMark],
    metadata_path: Path,
    book_title: str,
    author: str,
    comment: str = "Narrated by AI voice",
) -> Path:
    """Write an ffmetadata file encoding chapter markers for M4B creation."""
    lines = [
        ";FFMETADATA1",
        f"title={book_title}",
        f"artist={author}",
        f"album={book_title}",
        "genre=Audiobook",
        f"comment={comment}",
        "",
    ]
    for mark in chapter_marks:
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={mark.start_ms}",
            f"END={mark.end_ms}",
            f"title={mark.title}",
            "",
        ]
    metadata_path.write_text("\n".join(lines), encoding="utf-8")
    return metadata_path


def build_m4b(
    full_audio_path: Path,
    metadata_path: Path,
    cover_image_path: Path | None,
    output_m4b_path: Path,
) -> Path:
    """
    Convert concatenated MP3 + ffmetadata into final M4B with chapters and cover art.
    Encodes audio as AAC 64kbps (standard audiobook quality).
    """
    output_m4b_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(full_audio_path),
        "-i", str(metadata_path),
    ]

    if cover_image_path and cover_image_path.exists():
        cmd += ["-i", str(cover_image_path)]
        cmd += [
            "-map", "0:a",
            "-map", "2:v",
            "-disposition:v", "attached_pic",
        ]
    else:
        cmd += ["-map", "0:a"]

    cmd += [
        "-map_metadata", "1",
        "-c:a", "aac",
        "-b:a", "64k",
        "-c:v", "copy",       # keep cover JPEG as-is (don't transcode to h264)
        "-movflags", "+faststart",
        str(output_m4b_path),
    ]

    _run(cmd, desc="build M4B")
    return output_m4b_path


def format_duration(total_ms: int) -> str:
    """Format milliseconds as H:MM:SS."""
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"
