"""Registry that maps document types to parsers."""

from typing import List, Optional

from homomics_lab.knowledge.ingestion.models import DocumentSource
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser
from homomics_lab.knowledge.ingestion.parsers.docx import DOCXParser
from homomics_lab.knowledge.ingestion.parsers.html import HTMLParser
from homomics_lab.knowledge.ingestion.parsers.image import ImageParser
from homomics_lab.knowledge.ingestion.parsers.pdf import PDFParser
from homomics_lab.knowledge.ingestion.parsers.plaintext import PlainTextParser


class ParserRegistry:
    """Select the best parser for a DocumentSource."""

    def __init__(self, parsers: Optional[List[DocumentParser]] = None) -> None:
        self.parsers = parsers or self._default_parsers()

    @staticmethod
    def _default_parsers() -> List[DocumentParser]:
        return [
            PlainTextParser(),
            PDFParser(),
            DOCXParser(),
            HTMLParser(),
            ImageParser(),
        ]

    def select(self, source: DocumentSource) -> DocumentParser:
        if source.source_type.value == "url":
            from homomics_lab.knowledge.ingestion.parsers.composite import URLParser

            return URLParser()

        extension = ""
        if source.filename and "." in source.filename:
            extension = source.filename.rsplit(".", 1)[-1].lower()
        mime = (source.mime_type or "").lower()

        # Prefer parser that declares support by extension, then by mime.
        for parser in self.parsers:
            if parser.supports(mime, extension):
                return parser
        for parser in self.parsers:
            if parser.supports(mime, ""):
                return parser

        # Final fallback: try plain text.
        return PlainTextParser()
