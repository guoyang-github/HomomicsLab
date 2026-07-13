"""Flat scientific-search tools backed by the Connector registry.

Exposes two agent-callable tools:

* ``science_list_dbs`` — list the scientific databases the agent can query.
* ``science_search``  — query one or more databases and merge normalized hits.

Adding a new database is one ``Connector`` file + registration; these tools do
not change.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from homomics_lab.connectors import (
    get_connector_registry,
    register_default_connectors,
)

logger = logging.getLogger(__name__)


def science_list_dbs() -> Dict[str, Any]:
    """List registered scientific databases and their availability."""
    registry = get_connector_registry()
    databases = [
        {
            "name": c.name,
            "description": c.description,
            "available": c.is_available(),
        }
        for c in registry.list_all()
    ]
    return {"count": len(databases), "databases": databases}


async def science_search(
    query: str,
    databases: Optional[List[str]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Search scientific databases and return merged, deduplicated hits.

    Args:
        query: Free-text search query.
        databases: Optional subset of connector names (e.g. ["pubmed"]).
            Defaults to every available connector.
        limit: Maximum number of merged results to return.
    """
    registry = get_connector_registry()
    connectors = registry.resolve(databases)
    if not connectors:
        return {
            "query": query,
            "databases": [],
            "count": 0,
            "results": [],
            "errors": {"_": "No available scientific database connectors."},
        }

    per_connector = max(1, limit)
    tasks = [c.search(query, per_connector) for c in connectors]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    errors: Dict[str, str] = {}
    merged: List[Any] = []
    seen = set()
    for connector, outcome in zip(connectors, gathered):
        if isinstance(outcome, Exception):
            logger.warning("Connector %s failed for %r: %s", connector.name, query, outcome)
            errors[connector.name] = str(outcome)
            continue
        for hit in outcome:
            key = hit.dedupe_key()
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
            if len(merged) >= limit:
                break
        if len(merged) >= limit:
            break

    return {
        "query": query,
        "databases": [c.name for c in connectors],
        "count": len(merged),
        "results": [h.to_dict() for h in merged],
        "errors": errors,
    }


def register_science_tools(tool_registry: Any) -> None:
    """Populate connectors and register the two flat science tools."""
    register_default_connectors(get_connector_registry())

    tool_registry.register_builtin(
        name="science_list_dbs",
        description=(
            "List the scientific databases HomomicsLab can search "
            "(PubMed, Europe PMC, bioRxiv, web, ...) and whether each is available."
        ),
        handler=science_list_dbs,
        input_schema={"type": "object", "properties": {}},
    )
    tool_registry.register_builtin(
        name="science_search",
        description=(
            "Search one or more scientific databases (PubMed, Europe PMC, bioRxiv, web) "
            "and return merged, deduplicated results with titles, links, and sources. "
            "Use science_list_dbs first to see what is queryable."
        ),
        handler=science_search,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "databases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of connector names to query.",
                },
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
