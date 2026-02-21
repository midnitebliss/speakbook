"""parsers/ — Multi-format document parser package."""

from pathlib import Path

from parsers.base import ParseResult

SUPPORTED_EXTENSIONS = {".epub", ".md", ".markdown", ".pdf"}


def parse_file(file_path: Path) -> ParseResult:
    """Dispatch to the appropriate parser based on file extension."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".epub" or file_path.is_dir():
        from parsers.epub_parser import parse_epub
        return parse_epub(file_path)
    elif suffix in (".md", ".markdown"):
        from parsers.markdown_parser import parse_markdown
        return parse_markdown(file_path)
    elif suffix == ".pdf":
        from parsers.pdf_parser import parse_pdf
        return parse_pdf(file_path)
    else:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
