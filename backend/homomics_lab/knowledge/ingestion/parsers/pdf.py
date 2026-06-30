"""PDF parser using pypdf (optional dependency)."""

from pathlib import Path

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser


class PDFParser(DocumentParser):
    """Extract text from PDF files."""

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension == "pdf" or mime_type == "application/pdf"

    async def parse(self, source: DocumentSource) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDF parsing requires 'pypdf'. Install with: uv pip install pypdf "
                "or add the 'knowledge' optional dependency group."
            ) from exc

        path = Path(source.source)
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append(text)

        full_text = "\n\n".join(pages)
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        title = None
        if reader.metadata:
            title = reader.metadata.get("/Title") or reader.metadata.get("title")

        return ParsedDocument(
            source=source,
            title=str(title) if title else None,
            text=full_text,
            pages=pages,
            paragraphs=paragraphs,
            metadata={
                "page_count": len(reader.pages),
                "paragraph_count": len(paragraphs),
            },
        )
