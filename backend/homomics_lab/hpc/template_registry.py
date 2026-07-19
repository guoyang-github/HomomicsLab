"""Production Nextflow template registry.

Maps analysis intents to validated DSL2 workflow templates. When a template
exists for the requested analysis type, the system uses it instead of
auto-generating a stub workflow from ``SimpleNFTranslator``.
"""

from pathlib import Path
from typing import Dict, Optional

# nf-core integration is always on (formerly HOMOMICS_NFCORE_ENABLED).
NFCORE_ENABLED = True


class NextflowTemplateRegistry:
    """Registry of curated Nextflow workflow templates."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or Path(__file__).parent / "templates"
        self._templates: Dict[str, Path] = {}
        self._discover_templates()

    def _discover_templates(self) -> None:
        if not self.templates_dir.exists():
            return
        for entry in self.templates_dir.iterdir():
            main_nf = entry / "main.nf"
            if entry.is_dir() and main_nf.exists():
                self._templates[entry.name] = main_nf

    def list_templates(self) -> Dict[str, str]:
        return {name: str(path) for name, path in self._templates.items()}

    def get_template(self, name: str) -> Optional[Path]:
        return self._templates.get(name)

    def resolve_for_intent(self, intent_type: str) -> Optional[Path]:
        """Map a domain intent to a template path.

        First check local curated templates; then fall back to nf-core
        suggestions if nf-core integration is enabled.
        """
        mapping = {
            "single_cell_analysis": "single_cell",
            "single_cell": "single_cell",
            "spatial_analysis": None,  # not yet curated locally
            "metagenomics_analysis": None,
            "rnaseq_analysis": "rnaseq",
            "rnaseq": "rnaseq",
            "rna_seq": "rnaseq",
            "differential_expression": "rnaseq",
        }
        template_name = mapping.get(intent_type)
        if template_name is not None:
            local_path = self._templates.get(template_name)
            if local_path is not None:
                return local_path

        # Fall back to nf-core pipeline suggestion.
        from homomics_lab.nfcore_integration import get_nfcore_manager

        if not NFCORE_ENABLED:
            return None

        nfcore_manager = get_nfcore_manager()
        suggested = nfcore_manager.suggest_pipeline(intent_type)
        if suggested is not None:
            try:
                return nfcore_manager.get_pipeline_path(suggested)
            except Exception:
                return None
        return None


# Singleton registry.
_registry: Optional[NextflowTemplateRegistry] = None


def get_template_registry() -> NextflowTemplateRegistry:
    global _registry
    if _registry is None:
        _registry = NextflowTemplateRegistry()
    return _registry
