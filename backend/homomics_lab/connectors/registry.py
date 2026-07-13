"""ConnectorRegistry: unified access to scientific database connectors."""

import logging
from typing import Dict, List, Optional

from homomics_lab.connectors.base import Connector

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Central registry for scientific database connectors."""

    def __init__(self) -> None:
        self._connectors: Dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        if not connector.name:
            raise ValueError("Connector must define a non-empty name")
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Optional[Connector]:
        return self._connectors.get(name)

    def list_all(self) -> List[Connector]:
        return list(self._connectors.values())

    def available(self) -> List[Connector]:
        """Connectors whose dependencies/keys are currently satisfied."""
        return [c for c in self._connectors.values() if c.is_available()]

    def resolve(self, names: Optional[List[str]]) -> List[Connector]:
        """Pick connectors by name, falling back to all available.

        Unknown names are ignored (reported by the caller via the response);
        when ``names`` is empty/None, every available connector is used.
        """
        pool = self.available()
        if not names:
            return pool
        wanted = {n.strip().lower() for n in names if n and n.strip()}
        return [c for c in pool if c.name.lower() in wanted]

    def __contains__(self, name: str) -> bool:
        return name in self._connectors

    def __len__(self) -> int:
        return len(self._connectors)


_global_registry: Optional[ConnectorRegistry] = None


def get_connector_registry() -> ConnectorRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ConnectorRegistry()
    return _global_registry
