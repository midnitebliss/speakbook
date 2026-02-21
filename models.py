"""models.py — Shared data types for speakbook."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chapter:
    index: int       # 1-based
    title: str       # Display title, e.g. "Chapter I: Jeeves Exerts the Old Cerebellum"
    tts_title: str   # For TTS announcement, e.g. "Chapter One"
    text: str        # Cleaned plain text, ready for TTS


@dataclass
class BookMetadata:
    title: str
    author: str
    cover_path: Path | None = None
    source_format: str = ""         # "epub", "markdown", "pdf"
