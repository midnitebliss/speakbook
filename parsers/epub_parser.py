"""parsers/epub_parser.py — Parse EPUB (packed or directory) into chapters."""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from models import BookMetadata, Chapter
from parsers.base import ParseResult, clean_text

NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"

ROMAN_MAP = {
    "I": "One", "II": "Two", "III": "Three", "IV": "Four", "V": "Five",
    "VI": "Six", "VII": "Seven", "VIII": "Eight", "IX": "Nine", "X": "Ten",
    "XI": "Eleven", "XII": "Twelve", "XIII": "Thirteen", "XIV": "Fourteen",
    "XV": "Fifteen", "XVI": "Sixteen", "XVII": "Seventeen", "XVIII": "Eighteen",
    "XIX": "Nineteen", "XX": "Twenty",
}


def _find_oebps(epub_path: Path) -> tuple[Path, bool]:
    """Return (oebps_dir, is_zip)."""
    if epub_path.is_dir():
        oebps = epub_path / "OEBPS"
        if not oebps.exists():
            raise FileNotFoundError(f"No OEBPS directory found in {epub_path}")
        return oebps, False
    elif epub_path.suffix.lower() == ".epub" and zipfile.is_zipfile(epub_path):
        return epub_path, True
    else:
        raise ValueError(f"Cannot determine EPUB format for {epub_path}")


def _parse_toc_ncx(ncx_path: Path) -> list[dict]:
    """Parse toc.ncx, skipping first 2 and last 1 nav points (Gutenberg boilerplate)."""
    tree = ET.parse(ncx_path)
    root = tree.getroot()
    nav_map = root.find(f"{{{NCX_NS}}}navMap")
    if nav_map is None:
        raise ValueError("No navMap found in toc.ncx")

    nav_points = nav_map.findall(f"{{{NCX_NS}}}navPoint")
    content_points = nav_points[2:-1]

    chapters = []
    for np in content_points:
        label = np.find(f"{{{NCX_NS}}}navLabel/{{{NCX_NS}}}text")
        content = np.find(f"{{{NCX_NS}}}content")
        play_order = int(np.get("playOrder", 0))
        title_raw = label.text.strip() if label is not None and label.text else ""
        src = content.get("src", "") if content is not None else ""
        src_file = src.split("#")[0]
        chapters.append({"title_raw": title_raw, "src_file": src_file, "play_order": play_order})
    return chapters


def _clean_title(raw: str) -> tuple[str, str]:
    """Convert 'CHAPTER I TITLE' → ('Chapter I: Title', 'Chapter One')."""
    m = re.match(r"^CHAPTER\s+([IVXLCDM]+)\s+(.+)$", raw, re.IGNORECASE)
    if m:
        roman = m.group(1).upper()
        subtitle = _title_case(m.group(2).strip())
        number_word = ROMAN_MAP.get(roman, roman)
        return f"Chapter {roman}: {subtitle}", f"Chapter {number_word}"
    return _title_case(raw), _title_case(raw)


def _title_case(text: str) -> str:
    """Title-case that handles apostrophes correctly."""
    return " ".join(
        word[0].upper() + word[1:].lower() if word else ""
        for word in text.split()
    )


def _extract_chapter_text(xhtml_path: Path) -> str:
    """Parse a single chapter XHTML file, return cleaned text."""
    content = xhtml_path.read_bytes()
    soup = BeautifulSoup(content, features="lxml-xml")

    chapter_div = None
    for div in soup.find_all("div", class_="chapter"):
        if div.get("id") and div["id"].startswith("pgepubid"):
            chapter_div = div
            break
    if chapter_div is None:
        divs = soup.find_all("div", class_="chapter")
        chapter_div = divs[-1] if divs else soup.body

    paragraphs = []
    for tag in chapter_div.find_all(["p"]):
        if tag.find_parent("h2"):
            continue
        text = tag.get_text(separator=" ", strip=True)
        if text:
            paragraphs.append(text)

    return clean_text("\n\n".join(paragraphs))


def _extract_metadata(oebps: Path) -> BookMetadata:
    """Read title, author, cover from content.opf."""
    opf = oebps / "content.opf"
    title, author, cover_path = "Untitled", "Unknown", None

    if opf.exists():
        tree = ET.parse(opf)
        root = tree.getroot()
        t = root.find(f".//{{{DC_NS}}}title")
        if t is not None and t.text:
            title = t.text.strip()
        a = root.find(f".//{{{DC_NS}}}creator")
        if a is not None and a.text:
            author = a.text.strip()
        for item in root.findall(f".//{{{OPF_NS}}}item"):
            if "cover-image" in (item.get("properties") or ""):
                href = item.get("href", "")
                candidate = oebps / href
                if candidate.exists():
                    cover_path = candidate
                    break

    return BookMetadata(title=title, author=author, cover_path=cover_path, source_format="epub")


def parse_epub(epub_path: Path) -> ParseResult:
    """Main entry point. Returns ParseResult with chapters and metadata."""
    epub_path = Path(epub_path)
    oebps, is_zip = _find_oebps(epub_path)

    if is_zip:
        raise NotImplementedError(
            "Packed EPUB not yet supported. "
            "Please unzip first: unzip book.epub -d book.epub.dir"
        )

    toc_entries = _parse_toc_ncx(oebps / "toc.ncx")
    metadata = _extract_metadata(oebps)

    chapters = []
    for i, entry in enumerate(toc_entries, start=1):
        xhtml_path = oebps / entry["src_file"]
        if not xhtml_path.exists():
            raise FileNotFoundError(f"Chapter file not found: {xhtml_path}")
        display_title, tts_title = _clean_title(entry["title_raw"])
        text = _extract_chapter_text(xhtml_path)
        chapters.append(Chapter(index=i, title=display_title, tts_title=tts_title, text=text))

    return ParseResult(chapters=chapters, metadata=metadata)
