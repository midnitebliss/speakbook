"""parsers/markdown_parser.py — Parse Markdown files into chapters."""

import re
from pathlib import Path

from models import BookMetadata, Chapter
from parsers.base import ParseResult, clean_text


def _extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter (--- delimited) if present. Returns (meta, body)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not m:
        return {}, content
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip("\"'")
    return meta, content[m.end():]


def _split_by_headings(content: str) -> list[tuple[str, str]]:
    """
    Split markdown by # or ## headings.
    Returns list of (heading_text, body_text).
    Falls back to treating the whole document as one chapter.
    """
    # Find all headings (# or ##)
    heading_pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(content))

    if not matches:
        return [("Chapter 1", content.strip())]

    # Use the shallowest heading level present
    levels = [len(m.group(1)) for m in matches]
    split_level = min(levels)
    filtered = [(m.start(), m.group(2).strip()) for m in matches if len(m.group(1)) == split_level]

    result = []
    for i, (pos, title) in enumerate(filtered):
        # Body starts after the heading line
        heading_line_end = content.index("\n", pos) + 1 if "\n" in content[pos:] else len(content)
        end = filtered[i + 1][0] if i + 1 < len(filtered) else len(content)
        body = content[heading_line_end:end].strip()
        result.append((title, body))

    return result


def parse_markdown(file_path: Path) -> ParseResult:
    """Parse a Markdown file into chapters, splitting on headings."""
    file_path = Path(file_path)
    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = _extract_frontmatter(content)

    title = frontmatter.get("title", file_path.stem.replace("_", " ").replace("-", " ").title())
    author = frontmatter.get("author", "Unknown")

    sections = _split_by_headings(body)

    chapters = []
    idx = 1
    for heading, text in sections:
        cleaned = clean_text(text)
        if not cleaned.strip():
            continue
        chapters.append(Chapter(
            index=idx,
            title=heading,
            tts_title=heading,
            text=cleaned,
        ))
        idx += 1

    metadata = BookMetadata(
        title=title,
        author=author,
        cover_path=None,
        source_format="markdown",
    )
    return ParseResult(chapters=chapters, metadata=metadata)
