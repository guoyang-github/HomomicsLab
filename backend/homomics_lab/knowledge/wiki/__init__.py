"""LLM Wiki: a living, LLM-assisted document knowledge base.

The wiki layer sits on top of the knowledge ingestion pipeline.  It turns
ingested documents into editable concept pages, auto-links related pages, and
answers questions with retrieved chunks + generated summaries.
"""

from homomics_lab.knowledge.wiki.engine import WikiEngine
from homomics_lab.knowledge.wiki.models import WikiLink, WikiPage, WikiQueryResult
from homomics_lab.knowledge.wiki.store import WikiStore

__all__ = ["WikiEngine", "WikiLink", "WikiPage", "WikiQueryResult", "WikiStore"]
