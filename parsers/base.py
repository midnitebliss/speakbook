"""parsers/base.py — Shared parser utilities and types."""

import html
import re
from dataclasses import dataclass

from models import BookMetadata, Chapter


@dataclass
class ParseResult:
    """Standard return type for all parsers."""
    chapters: list[Chapter]
    metadata: BookMetadata


def clean_text(text: str) -> str:
    """Normalize text for TTS synthesis."""
    text = html.unescape(text)
    text = text.replace("\u2014", " - ").replace("\u2013", " - ")
    text = text.replace("\u00ad", "")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    lines = text.split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    cleaned_lines = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned_lines.append("")
            prev_blank = True
        else:
            cleaned_lines.append(line)
            prev_blank = False
    return "\n".join(cleaned_lines).strip()
