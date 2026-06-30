"""Abstract base class for document parsers."""

from abc import ABC, abstractmethod

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument


class DocumentParser(ABC):
    """Parse a raw document source into clean text and metadata."""

    @abstractmethod
    def supports(self, mime_type: str, extension: str) -> bool:
        """Return True if this parser can handle the given mime/extension."""

    @abstractmethod
    async def parse(self, source: DocumentSource) -> ParsedDocument:
        """Parse the source and return a ParsedDocument."""

    def _extension(self, source: DocumentSource) -> str:
        name = (source.filename or "").lower()
        if "." in name:
            return name.rsplit(".", 1)[-1]
        return ""
