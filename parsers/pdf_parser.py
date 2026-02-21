"""parsers/pdf_parser.py — Parse PDF files into chapters using pymupdf."""

import re
from pathlib import Path

from models import BookMetadata, Chapter
from parsers.base import ParseResult, clean_text


def _chapters_from_outline(doc) -> list[tuple[str, int, int]] | None:
    """Try to extract chapters from PDF bookmarks/outline."""
    toc = doc.get_toc()  # list of [level, title, page_number]
    if not toc:
        return None

    # Use the shallowest level present
    min_level = min(level for level, _, _ in toc)
    top_level = [(title, page) for level, title, page in toc if level == min_level]

    if len(top_level) < 2:
        return None

    result = []
    for i, (title, start_page) in enumerate(top_level):
        start_0 = max(0, start_page - 1)
        if i + 1 < len(top_level):
            end_0 = top_level[i + 1][1] - 2  # page before next chapter, 0-indexed
        else:
            end_0 = doc.page_count - 1  # last page, already 0-indexed
        if end_0 < start_0:
            end_0 = start_0  # at minimum, single-page chapter
        result.append((title, start_0, end_0))
    return result


def _chapters_from_heuristics(doc) -> list[tuple[str, int, int]]:
    """Fallback: detect chapter headings or split into fixed-size chunks."""
    chapter_pattern = re.compile(
        r"^(chapter\s+[\divxlcdm]+[.:]*\s*.*)",
        re.IGNORECASE | re.MULTILINE,
    )
    chapter_starts = []
    for page_num in range(doc.page_count):
        text = doc[page_num].get_text("text")
        m = chapter_pattern.search(text[:500])
        if m:
            chapter_starts.append((m.group(1).strip(), page_num))

    if len(chapter_starts) >= 2:
        result = []
        for i, (title, start) in enumerate(chapter_starts):
            end = chapter_starts[i + 1][1] - 1 if i + 1 < len(chapter_starts) else doc.page_count - 1
            result.append((title, start, end))
        return result

    # Ultimate fallback: one chapter per ~20 pages
    chunk_size = 20
    result = []
    for i in range(0, doc.page_count, chunk_size):
        end = min(i + chunk_size - 1, doc.page_count - 1)
        result.append((f"Section {len(result) + 1}", i, end))
    return result


def parse_pdf(file_path: Path) -> ParseResult:
    """
    Parse a PDF into chapters.
    Strategy: (1) PDF bookmarks, (2) heading patterns, (3) fixed page chunks.
    """
    import fitz  # pymupdf

    file_path = Path(file_path)
    doc = fitz.open(str(file_path))

    pdf_meta = doc.metadata or {}
    title = pdf_meta.get("title", "").strip() or file_path.stem.replace("_", " ").title()
    author = pdf_meta.get("author", "").strip() or "Unknown"

    outline_chapters = _chapters_from_outline(doc)
    chapter_ranges = outline_chapters if outline_chapters else _chapters_from_heuristics(doc)

    chapters = []
    idx = 1
    for ch_title, start_page, end_page in chapter_ranges:
        text_parts = []
        for page_num in range(start_page, min(end_page + 1, doc.page_count)):
            text_parts.append(doc[page_num].get_text("text"))
        raw_text = "\n\n".join(text_parts)
        cleaned = clean_text(raw_text)
        if not cleaned.strip():
            continue
        chapters.append(Chapter(
            index=idx,
            title=ch_title.strip(),
            tts_title=ch_title.strip(),
            text=cleaned,
        ))
        idx += 1

    doc.close()

    metadata = BookMetadata(
        title=title,
        author=author,
        cover_path=None,
        source_format="pdf",
    )
    return ParseResult(chapters=chapters, metadata=metadata)
