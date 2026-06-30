"""HTML parser using BeautifulSoup (optional dependency)."""

from pathlib import Path

from homomics_lab.knowledge.ingestion.models import DocumentSource, ParsedDocument
from homomics_lab.knowledge.ingestion.parsers.base import DocumentParser


class HTMLParser(DocumentParser):
    """Extract readable text from HTML files or URL responses."""

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension in {"html", "htm", "xhtml"} or mime_type in {
            "text/html",
            "application/xhtml+xml",
        }

    async def parse(self, source: DocumentSource) -> ParsedDocument:
        if source.source_type.value == "text":
            html = source.source
        else:
            path = Path(source.source)
            html = path.read_text(encoding="utf-8", errors="replace")

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except ImportError:
            # Minimal fallback: strip common tags with regex.
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            return ParsedDocument(
                source=source,
                title=None,
                text=text,
                pages=[text],
                paragraphs=paragraphs,
                metadata={"fallback": True},
            )

        # Remove script/style/nav/footer/header tags.
        for tag_name in ("script", "style", "nav", "footer", "header"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        body = soup.find("body") or soup
        # Prefer paragraph-level text.
        paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p") if p.get_text(strip=True)]
        if not paragraphs:
            text = body.get_text(" ", strip=True)
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        else:
            text = "\n\n".join(paragraphs)

        return ParsedDocument(
            source=source,
            title=title,
            text=text,
            pages=[text],
            paragraphs=paragraphs,
            metadata={
                "paragraph_count": len(paragraphs),
                "has_bs4": True,
            },
        )
