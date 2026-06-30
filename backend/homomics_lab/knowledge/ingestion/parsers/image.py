"""Image parser placeholder.

Reads image metadata and produces a placeholder description.  OCR or vision-LLM
support can be plugged in here later without changing the pipeline interface.
"""

from pathlib import Path

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser


class ImageParser(DocumentParser):
    """Parser for image files."""

    SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}
    SUPPORTED_MIMES = {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/bmp",
        "image/tiff",
        "image/webp",
    }

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension in self.SUPPORTED_EXTENSIONS or mime_type in self.SUPPORTED_MIMES

    async def parse(self, source: DocumentSource) -> ParsedDocument:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Image parsing requires 'Pillow'. Install it with: uv pip install Pillow"
            ) from exc

        if source.source_type.value == "text":
            # Inline images are not supported via text source.
            description = "[Image data provided inline; visual parsing not implemented]"
            return ParsedDocument(
                source=source,
                title=source.filename,
                text=description,
                pages=[description],
                paragraphs=[description],
                metadata={"format": "unknown"},
            )

        path = Path(source.source)
        image = Image.open(path)
        description = (
            f"Image file: {source.filename or path.name}. "
            f"Format={image.format}, size={image.size}, mode={image.mode}. "
            "Visual content is not yet extracted (OCR/vision LLM placeholder)."
        )
        return ParsedDocument(
            source=source,
            title=source.filename or path.name,
            text=description,
            pages=[description],
            paragraphs=[description],
            metadata={
                "format": image.format,
                "size": image.size,
                "mode": image.mode,
                "ocr_enabled": False,
            },
        )
