"""Central registry for prompt templates.

Templates are keyed by ``name`` and optionally by ``domain``. The registry
supports layered overrides: a domain-specific template replaces or extends the
base template of the same name.
"""

from typing import Any, Dict, Optional

from jinja2 import BaseLoader, Environment


class PromptRegistry:
    """In-memory store for prompt templates with Jinja2 rendering.

    Templates are stored as ``{name: {domain: template}}``. ``None`` domain
    represents the global/base template. Domain-specific templates override the
    base template when requested with that domain.
    """

    def __init__(self) -> None:
        self._templates: Dict[str, Dict[Optional[str], str]] = {}
        self._jinja = Environment(loader=BaseLoader())

    def register(
        self,
        name: str,
        template: str,
        domain: Optional[str] = None,
    ) -> None:
        """Register or overwrite a prompt template."""
        self._templates.setdefault(name, {})[domain] = template

    def unregister(self, name: str, domain: Optional[str] = None) -> None:
        """Remove a template. If domain is None, remove the base template only."""
        domains = self._templates.get(name)
        if domains is None:
            return
        domains.pop(domain, None)
        if not domains:
            del self._templates[name]

    def get(self, name: str, domain: Optional[str] = None) -> Optional[str]:
        """Return the most specific template available.

        Priority: domain-specific > base > None.
        """
        domains = self._templates.get(name)
        if domains is None:
            return None
        if domain is not None and domain in domains:
            return domains[domain]
        return domains.get(None)

    def get_combined(self, name: str, domain: Optional[str] = None) -> Optional[str]:
        """Return base + domain-specific templates concatenated.

        Useful for system prompts where domain context should augment the global
        identity rather than replace it.
        """
        domains = self._templates.get(name)
        if domains is None:
            return None
        base = domains.get(None, "").strip()
        override = domains.get(domain, "").strip() if domain else ""
        if base and override:
            return f"{base}\n\n{override}"
        return override or base or None

    def render(
        self,
        name: str,
        domain: Optional[str] = None,
        combine: bool = False,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """Render a template with the supplied variables.

        Variables can be passed either as a ``context`` dict or as keyword
        arguments (or both). Keyword arguments take precedence over ``context``
        keys. Passing ``context`` avoids collisions with the ``name`` argument.
        """
        source = self.get_combined(name, domain) if combine else self.get(name, domain)
        if source is None:
            return None
        variables: Dict[str, Any] = {}
        if context:
            variables.update(context)
        variables.update(kwargs)
        template = self._jinja.from_string(source)
        return template.render(**variables)

    def list_names(self) -> list:
        """Return all registered template names."""
        return list(self._templates.keys())

    def clear_domain(self, domain: str) -> None:
        """Remove all templates registered for a specific domain."""
        for name in list(self._templates.keys()):
            self._templates[name].pop(domain, None)
            if not self._templates[name]:
                del self._templates[name]


# Global singleton used across the application.
_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Return the global prompt registry."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def render_prompt(
    name: str,
    domain: Optional[str] = None,
    combine: bool = False,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Optional[str]:
    """Convenience shortcut: render from the global registry."""
    return get_prompt_registry().render(
        name, domain=domain, combine=combine, context=context, **kwargs
    )
