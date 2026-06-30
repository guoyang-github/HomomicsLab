"""Knowledge ingestion: Extract-Cognify-Load style pipeline.

This package turns unstructured documents (text, PDF, DOCX, HTML, Markdown,
images) into a searchable knowledge graph using the existing pluggable
GraphBackend, VectorStoreBackend and LLMClient.
"""

from .index import KnowledgeIndex
from .models import IngestionResult, DocumentSource, SourceType
from .pipeline import CognifyPipeline, CognifyOptions

__all__ = [
    "KnowledgeIndex",
    "CognifyPipeline",
    "CognifyOptions",
    "DocumentSource",
    "IngestionResult",
    "SourceType",
]
