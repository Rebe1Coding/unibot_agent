from pathlib import Path

from indexer.parsers import html_parser, pdf_parser, text_parser

PARSERS = {
    ".html": html_parser.parse,
    ".htm": html_parser.parse,
    ".pdf": pdf_parser.parse,
    ".md": text_parser.parse,
    ".txt": text_parser.parse,
}


def get_parser(filename: str):
    ext = Path(filename).suffix.lower()
    return PARSERS.get(ext)
