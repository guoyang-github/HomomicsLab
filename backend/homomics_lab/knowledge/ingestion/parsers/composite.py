"""URL fetcher that delegates to the appropriate parser by content type."""

import tempfile
from pathlib import Path
from urllib.parse import urlparse

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser
from homomics_lab.knowledge.ingestion.parser_registry import ParserRegistry


class URLParser(DocumentParser):
    """Fetch a URL and parse the returned document."""

    def supports(self, mime_type: str, extension: str) -> bool:
        # This parser is selected explicitly by source type, not by mime.
        return False

    async def parse(self, source: DocumentSource) -> ParsedDocument:
        url = source.source
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "URL ingestion requires 'httpx'. Install with: uv pip install httpx "
                "or add the 'knowledge' optional dependency group."
            ) from exc

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            mime = response.headers.get("content-type", "").split(";")[0].strip() or None

        extension = ""
        if source.filename and "." in source.filename:
            extension = source.filename.rsplit(".", 1)[-1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension or 'download'}") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            file_source = DocumentSource.from_file(tmp_path)
            if mime:
                file_source.mime_type = mime
            if source.filename:
                file_source.filename = source.filename
            registry = ParserRegistry()
            parser = registry.select(file_source)
            parsed = await parser.parse(file_source)
            parsed.source = source
            return parsed
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
