"""Integration tests for domain loading and hot-reload at startup."""

import asyncio

import pytest

from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.domain.hot_reload import DomainHotReloader, FileWatcher
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import DomainRegistry
from homomics_lab.skills.registry import get_default_registry


@pytest.fixture
def domain_registry():
    registry = DomainRegistry()
    registry._domains.clear()
    return registry


@pytest.fixture
def minimal_domain(tmp_path):
    """Create a minimal domain.yaml on disk."""
    domain_yaml = tmp_path / "domain.yaml"
    domain_yaml.write_text(
        """
domain: test_minimal
description: Minimal domain for hot-reload testing
version: "1.0.0"
phases: []
state_checks: []
intents:
  - analysis_type: test_analysis
    keywords:
      - "test"
      - "minimal"
dag_seeds: []
roles: []
sops: []
""",
        encoding="utf-8",
    )
    return domain_yaml


class TestDomainHotReload:
    def test_load_minimal_domain(self, domain_registry, minimal_domain):
        strategy_lib = StrategyLibrary()
        loader = DomainLoader(
            skill_registry=get_default_registry(),
            strategy_lib=strategy_lib,
        )
        domain = loader.load(minimal_domain)
        domain_registry.register(domain, loader, minimal_domain)

        assert domain.domain == "test_minimal"
        assert "test_minimal" in domain_registry
        assert domain_registry.get("test_minimal") is not None

    @pytest.mark.asyncio
    async def test_hot_reload_watches_domain_file(self, domain_registry, minimal_domain, tmp_path):
        strategy_lib = StrategyLibrary()
        loader = DomainLoader(
            skill_registry=get_default_registry(),
            strategy_lib=strategy_lib,
        )
        domain = loader.load(minimal_domain)
        domain_registry.register(domain, loader, minimal_domain)

        watcher = FileWatcher(check_interval=0.05)
        reloader = DomainHotReloader(
            domain_registry=domain_registry,
            domain_loader=loader,
            watcher=watcher,
        )
        reloader.watch_domain(minimal_domain)
        await reloader.start()

        try:
            # Modify the domain file
            await asyncio.sleep(0.05)
            content = minimal_domain.read_text(encoding="utf-8")
            content = content.replace(
                "domain: test_minimal",
                "domain: test_minimal_renamed",
            )
            minimal_domain.write_text(content, encoding="utf-8")

            # Wait for the watcher to detect the change
            for _ in range(50):
                await asyncio.sleep(0.05)
                if "test_minimal_renamed" in domain_registry:
                    break

            assert "test_minimal_renamed" in domain_registry
            assert "test_minimal" not in domain_registry
        finally:
            await reloader.stop()

    @pytest.mark.asyncio
    async def test_domain_reloader_stop(self, domain_registry, minimal_domain):
        strategy_lib = object()
        loader = DomainLoader(
            skill_registry=None,
            strategy_lib=strategy_lib,
        )
        reloader = DomainHotReloader(
            domain_registry=domain_registry,
            domain_loader=loader,
        )
        reloader.watch_domain(minimal_domain)
        await reloader.start()
        assert reloader.watcher._running is True
        await reloader.stop()
        assert reloader.watcher._running is False
