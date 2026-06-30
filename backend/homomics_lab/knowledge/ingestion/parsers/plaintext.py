"""Plain-text parsers: txt, md, json, yaml, csv."""

import csv
import json
from pathlib import Path

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser


class PlainTextParser(DocumentParser):
    """Parser for text-based formats using the standard library."""

    SUPPORTED_EXTENSIONS = {
        "txt",
        "md",
        "markdown",
        "json",
        "yaml",
        "yml",
        "csv",
        "tsv",
        "log",
        "py",
        "r",
        "sh",
    }
    SUPPORTED_MIMES = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/json",
        "application/yaml",
        "application/x-yaml",
        "text/csv",
        "text/x-python",
        "text/x-r",
    }

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension in self.SUPPORTED_EXTENSIONS or mime_type in self.SUPPORTED_MIMES

    async def parse(self, source: DocumentSource) -> ParsedDocument:
        if source.source_type.value == "text":
            text = source.source
        else:
            path = Path(source.source)
            text = path.read_text(encoding="utf-8", errors="replace")

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        metadata: dict = {"paragraph_count": len(paragraphs)}

        extension = (source.filename or "").lower().rsplit(".", 1)[-1] if "." in (source.filename or "") else ""
        if extension == "json":
            try:
                metadata["json_keys"] = list(json.loads(text).keys())
            except Exception:
                pass
        elif extension == "csv":
            try:
                reader = csv.reader(text.splitlines())
                rows = list(reader)
                metadata["csv_rows"] = len(rows)
                metadata["csv_columns"] = len(rows[0]) if rows else 0
            except Exception:
                pass

        title = paragraphs[0][:200] if paragraphs else None
        return ParsedDocument(
            source=source,
            title=title,
            text=text,
            pages=[text],
            paragraphs=paragraphs,
            metadata=metadata,
        )
