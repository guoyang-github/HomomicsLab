"""Source attribution helpers for anti-hallucination.

Tool-driven answers must cite the sources they rely on. When no source can be
extracted from tool output, the response is left as-is so the LLM can state that
no source was available.
"""

import re
from typing import Any, Dict, List, Optional


_SOURCE_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,6}\s+)?(?:来源|Sources|References)\s*[:：]", re.IGNORECASE
)


def source_section_present(response_text: str) -> bool:
    """Return True when ``response_text`` already contains a sources section."""
    return bool(_SOURCE_SECTION_RE.search(response_text or ""))


def _extract_url(source: Dict[str, Any]) -> Optional[str]:
    """Pick the best URL-like value from a source dict."""
    for key in ("url", "source_url", "link"):
        value = source.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    for key in ("url", "source_url", "link"):
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_title(source: Dict[str, Any]) -> str:
    """Pick a human-readable title from a source dict."""
    for key in ("title", "name", "source", "id"):
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_id(source: Dict[str, Any]) -> str:
    """Pick the best identifier string from a source dict."""
    for key in ("pmid", "doi", "id", "source", "title", "name"):
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _source_type(source: Dict[str, Any]) -> str:
    """Classify a source dict into url/pmid/doi/other."""
    if _extract_url(source):
        return "url"
    if isinstance(source.get("pmid"), (str, int)):
        return "pmid"
    if isinstance(source.get("doi"), str):
        return "doi"
    return "other"


def _collect_source_dicts(value: Any) -> List[Dict[str, Any]]:
    """Recursively collect dicts that look like source records."""
    results: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        recognized_keys = {"url", "link", "source", "source_url", "pmid", "doi", "id", "title"}
        if recognized_keys.intersection(value.keys()):
            results.append(value)
        for v in value.values():
            results.extend(_collect_source_dicts(v))
    elif isinstance(value, (list, tuple)):
        for item in value:
            results.extend(_collect_source_dicts(item))
    return results


def extract_sources(tool_outputs: List[Any]) -> List[Dict[str, str]]:
    """Walk tool results and extract source identifiers.

    Recognized keys: ``url``, ``link``, ``source``, ``source_url``, ``pmid``,
    ``doi``, ``id``, ``title``. Nested lists and dicts are flattened.

    Returns a list of normalized source dicts with keys ``type``, ``id``,
    ``url`` and ``title``. Duplicate URLs/IDs are deduplicated.
    """
    seen: set = set()
    sources: List[Dict[str, str]] = []

    for output in tool_outputs:
        for raw in _collect_source_dicts(output):
            source_type = _source_type(raw)
            url = _extract_url(raw) or ""
            source_id = _extract_id(raw)
            title = _extract_title(raw)

            if not source_id and not url:
                continue

            dedup_key = url or source_id
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            sources.append(
                {
                    "type": source_type,
                    "id": source_id,
                    "url": url,
                    "title": title,
                }
            )

    return sources


def format_source_list(sources: List[Dict[str, str]]) -> str:
    """Return a Markdown "Sources" block in Chinese/English."""
    if not sources:
        return ""

    lines = ["", "### 来源 / Sources"]
    for idx, source in enumerate(sources, start=1):
        title = source.get("title") or source.get("id") or "来源"
        url = source.get("url") or ""
        source_id = source.get("id") or ""
        source_type = source.get("type") or "other"

        if url:
            lines.append(f"{idx}. [{title}]({url})")
        elif source_id:
            lines.append(f"{idx}. {title} ({source_type.upper()}: {source_id})")
        else:
            lines.append(f"{idx}. {title}")
    return "\n".join(lines)


def ensure_source_section(response_text: str, sources: List[Dict[str, str]]) -> str:
    """Append a formatted source block if sources exist and none is present."""
    if not sources or source_section_present(response_text):
        return response_text
    source_block = format_source_list(sources)
    separator = "" if response_text.rstrip().endswith("\n") else "\n"
    return f"{response_text}{separator}{source_block}"
