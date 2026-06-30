"""Semantic memory public API.

This module re-exports the new modular ``MemoryBackend`` under the legacy
``SemanticMemory`` name so existing callers continue to work without modification.
"""

from homomics_lab.context.memory_backend import (
    MemoryBackend,
    MemoryType,
    create_semantic_memory,
)

SemanticMemory = MemoryBackend
SQLiteSemanticMemory = MemoryBackend
PostgresSemanticMemory = MemoryBackend

__all__ = [
    "MemoryBackend",
    "MemoryType",
    "SemanticMemory",
    "SQLiteSemanticMemory",
    "PostgresSemanticMemory",
    "create_semantic_memory",
]
