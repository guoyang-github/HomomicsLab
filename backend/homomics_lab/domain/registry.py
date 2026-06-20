"""DomainRegistry: manages all loaded domains and provides unified access."""

from pathlib import Path
from typing import Dict, List, Optional

from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.models import DomainDefinition


class DomainRegistry:
    """Central registry for all loaded domains.

    Provides:
    - Domain lookup by ID
    - List all loaded domains
    - Get intent configuration for all domains
    - Hot-reload support
    """

    def __init__(self):
        self._domains: Dict[str, DomainDefinition] = {}
        self._loaders: Dict[str, DomainLoader] = {}
        self._source_paths: Dict[str, Path] = {}

    def register(self, domain: DomainDefinition, loader: Optional[DomainLoader] = None, source_path: Optional[Path] = None) -> None:
        """Register a loaded domain."""
        self._domains[domain.domain] = domain
        if loader:
            self._loaders[domain.domain] = loader
        if source_path:
            self._source_paths[domain.domain] = source_path

    def get(self, domain_id: str) -> Optional[DomainDefinition]:
        """Get a domain by ID."""
        return self._domains.get(domain_id)

    def list_all(self) -> List[DomainDefinition]:
        """List all registered domains."""
        return list(self._domains.values())

    def list_ids(self) -> List[str]:
        """List all registered domain IDs."""
        return list(self._domains.keys())

    def unregister(self, domain_id: str) -> bool:
        """Unregister a domain. Returns True if removed."""
        if domain_id in self._domains:
            del self._domains[domain_id]
            self._loaders.pop(domain_id, None)
            self._source_paths.pop(domain_id, None)
            return True
        return False

    def get_intent_config(self) -> Dict[str, Dict]:
        """Get merged intent configuration from all domains.

        Returns a map of analysis_type -> intent config for the IntentAnalyzer.
        """
        config = {}
        for domain in self._domains.values():
            for intent in domain.intents:
                config[intent.analysis_type] = {
                    "domain": domain.domain,
                    "keywords": intent.keywords,
                    "complexity_indicators": intent.complexity_indicators,
                    "data_scale_patterns": intent.data_scale_patterns,
                }
        return config

    def get_all_keywords(self) -> Dict[str, List[str]]:
        """Get all keywords grouped by analysis_type."""
        result = {}
        for domain in self._domains.values():
            for intent in domain.intents:
                result[intent.analysis_type] = intent.keywords
        return result

    def get_phase_types(self) -> Dict[str, List[str]]:
        """Get all phase types grouped by domain."""
        return {
            domain.domain: domain.get_phase_types()
            for domain in self._domains.values()
        }

    def get_roles(self) -> Dict[str, Dict]:
        """Get all roles from all domains."""
        result = {}
        for domain in self._domains.values():
            for role in domain.roles:
                result[role.role_id] = role.model_dump()
        return result

    def reload(self, domain_id: str) -> Optional[DomainDefinition]:
        """Hot-reload a domain from its source path.

        Returns the reloaded domain, or None if no source path is known.
        """
        source_path = self._source_paths.get(domain_id)
        if source_path is None:
            return None

        loader = self._loaders.get(domain_id)
        if loader is None:
            return None

        # Unregister old
        self.unregister(domain_id)

        # Reload
        domain = loader.load(source_path)
        self.register(domain, loader, source_path)
        return domain

    def __contains__(self, domain_id: str) -> bool:
        return domain_id in self._domains

    def __len__(self) -> int:
        return len(self._domains)


# Global singleton
_global_registry: Optional[DomainRegistry] = None


def get_domain_registry() -> DomainRegistry:
    """Get the global domain registry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = DomainRegistry()
    return _global_registry
