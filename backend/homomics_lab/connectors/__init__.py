"""Scientific database connectors.

Unified connector interface + registry. New databases are added by implementing
``Connector`` in one file and registering it via ``register_default_connectors``
(or ``ConnectorRegistry.register``).
"""

from homomics_lab.connectors.base import Connector, ConnectorHit
from homomics_lab.connectors.registry import (
    ConnectorRegistry,
    get_connector_registry,
)


def register_default_connectors(registry: ConnectorRegistry) -> None:
    """Register the built-in literature + web connectors.

    Each registration is isolated so a missing optional dependency in one
    connector never prevents the others from loading.
    """
    try:
        from homomics_lab.connectors.literature import default_literature_connectors

        for connector in default_literature_connectors():
            registry.register(connector)
    except Exception as exc:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).warning("Literature connectors unavailable: %s", exc)

    try:
        from homomics_lab.connectors.web import WebConnector

        registry.register(WebConnector())
    except Exception as exc:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).warning("Web connector unavailable: %s", exc)


__all__ = [
    "Connector",
    "ConnectorHit",
    "ConnectorRegistry",
    "get_connector_registry",
    "register_default_connectors",
]
