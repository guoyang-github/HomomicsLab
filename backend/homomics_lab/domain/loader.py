"""DomainLoader: reads a domain.yaml and registers everything into HomomicsLab."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from homomics_lab.domain.models import (
    DomainDAGSeed,
    DomainDefinition,
    DomainIntent,
    DomainPhase,
    DomainRole,
    DomainSOP,
    DomainStateCheck,
)
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StateCheck, StrategyLibrary
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG


class DomainLoaderError(Exception):
    """Raised when domain.yaml is invalid or registration fails."""

    pass


class DomainValidator:
    """Validate a domain definition before registration."""

    def __init__(self, skill_registry: SkillRegistry, strategy_lib: StrategyLibrary):
        self.skill_registry = skill_registry
        self.strategy_lib = strategy_lib

    def validate(self, domain: DomainDefinition) -> List[str]:
        """Return a list of validation errors (empty if valid)."""
        errors = []

        # 1. Check that phases reference valid skills
        for phase in domain.phases:
            for skill_id in phase.skills:
                if self.skill_registry.get(skill_id) is None:
                    errors.append(
                        f"Phase '{phase.id}' references unknown skill '{skill_id}'"
                    )

        # 2. Check that state_check targets exist in phases
        phase_ids = {p.id for p in domain.phases}
        for check in domain.state_checks:
            if check.target not in phase_ids and check.action != "modify_param":
                errors.append(
                    f"StateCheck targets unknown phase '{check.target}'"
                )
            if check.after is not None and check.after not in phase_ids:
                errors.append(
                    f"StateCheck references unknown 'after' phase '{check.after}'"
                )

        # 3. Check that DAG seeds reference known skills
        all_skill_ids = {s.id for s in self.skill_registry.list_all()}
        for seed in domain.dag_seeds:
            if seed.from_skill not in all_skill_ids:
                errors.append(f"DAG seed references unknown skill '{seed.from_skill}'")
            if seed.to_skill not in all_skill_ids:
                errors.append(f"DAG seed references unknown skill '{seed.to_skill}'")

        # 4. Check that intent analysis_types are unique
        intent_types = [i.analysis_type for i in domain.intents]
        if len(intent_types) != len(set(intent_types)):
            errors.append("Duplicate analysis_type in intents")

        # 5. Check that condition expressions are syntactically valid
        for check in domain.state_checks:
            try:
                compile(check.condition, "<string>", "eval")
            except SyntaxError as e:
                errors.append(f"Invalid condition expression '{check.condition}': {e}")

        return errors


class DomainLoader:
    """Load a domain from domain.yaml and register all components.

    Usage:
        loader = DomainLoader(skill_registry, strategy_lib, skill_dag)
        loader.load(Path("domains/metagenomics/domain.yaml"))
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        strategy_lib: StrategyLibrary,
        skill_dag: Optional[Any] = None,
    ):
        self.skill_registry = skill_registry
        self.strategy_lib = strategy_lib
        self.skill_dag = skill_dag
        self.validator = DomainValidator(skill_registry, strategy_lib)

    def load(self, domain_yaml_path: Path) -> DomainDefinition:
        """Load a domain.yaml and register all components.

        Returns the parsed DomainDefinition.
        Raises DomainLoaderError on validation failure.
        """
        # 1. Parse YAML
        domain = self._parse_yaml(domain_yaml_path)

        # 2. Load skills (if skills_dir specified)
        if domain.skills_dir:
            skills_path = domain_yaml_path.parent / domain.skills_dir
            self._load_skills(skills_path)

        # 3. Validate
        errors = self.validator.validate(domain)
        if errors:
            raise DomainLoaderError(
                f"Domain '{domain.domain}' validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        # 4. Register strategy
        self._register_strategy(domain)

        # 5. Register DAG seeds
        if self.skill_dag:
            self._register_dag_seeds(domain)

        # 6. Register SOPs
        self._register_sops(domain)

        return domain

    def load_directory(self, domains_dir: Path) -> List[DomainDefinition]:
        """Load all domain.yaml files in a directory tree."""
        domains = []
        for domain_yaml in domains_dir.rglob("domain.yaml"):
            try:
                domain = self.load(domain_yaml)
                domains.append(domain)
            except DomainLoaderError as e:
                # Log but continue loading other domains
                print(f"Warning: Failed to load domain from {domain_yaml}: {e}")
        return domains

    def _parse_yaml(self, path: Path) -> DomainDefinition:
        """Parse a domain.yaml file into DomainDefinition."""
        if not path.exists():
            raise DomainLoaderError(f"Domain file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise DomainLoaderError(f"Invalid YAML syntax in {path}: {e}") from e

        if data is None:
            raise DomainLoaderError(f"Empty domain.yaml: {path}")

        try:
            return DomainDefinition(**data)
        except Exception as e:
            raise DomainLoaderError(f"Invalid domain.yaml schema at {path}: {e}") from e

    def _load_skills(self, skills_path: Path) -> None:
        """Load skills from a directory into the registry."""
        if not skills_path.exists():
            return

        skill_loader = SkillLoader(registry=self.skill_registry)
        skill_loader.load_all(skills_path)

    def _register_strategy(self, domain: DomainDefinition) -> None:
        """Convert DomainDefinition to AnalysisStrategy and register."""
        strategy = self._build_strategy(domain)
        self.strategy_lib.register(strategy)

    def _build_strategy(self, domain: DomainDefinition) -> AnalysisStrategy:
        """Build an AnalysisStrategy from a DomainDefinition."""
        skeleton = [
            Phase(
                phase_type=phase.id,
                required=phase.required,
                description=phase.description or f"{phase.id} analysis step",
            )
            for phase in domain.phases
        ]

        state_checks = [
            self._build_state_check(check)
            for check in domain.state_checks
        ]

        # Collect all applicable intents from domain intents
        applicable_intents = []
        for intent in domain.intents:
            applicable_intents.append(intent.analysis_type)
            # Also add keywords as fallback intent patterns
            applicable_intents.extend(intent.keywords)

        # Deduplicate while preserving order
        seen = set()
        unique_intents = []
        for i in applicable_intents:
            if i not in seen:
                seen.add(i)
                unique_intents.append(i)

        return AnalysisStrategy(
            name=domain.domain,
            description=domain.description,
            applicable_intents=unique_intents,
            skeleton=skeleton,
            state_checks=state_checks,
        )

    def _build_state_check(self, check: DomainStateCheck) -> StateCheck:
        """Build a StateCheck from a DomainStateCheck.

        The condition string is compiled into a callable that evaluates
        the expression against a DataState instance.
        """
        return StateCheck(
            condition=self._compile_state_condition(check.condition),
            action=check.action,
            target=check.target,
            value=check.value,
            after=check.after,
        )

    def _compile_state_condition(self, condition_str: str) -> Any:
        """Compile a condition string into a callable.

        Supports expressions like:
        - 'host_contamination > 0.1'
        - 'n_samples < 3'
        - 'low_quality == True'
        - 'batch_detected and n_batches > 2'

        The compiled function takes a DataState instance as argument.
        """
        # Replace shorthand field names with ds.<field> access
        # This is a simplified compilation - in production, use a proper
        # expression parser or AST transformer
        code = compile(condition_str, "<string>", "eval")

        def evaluator(ds: DataState) -> bool:
            # Build namespace with DataState fields accessible by name
            namespace = {"ds": ds}
            # Add DataState attributes directly accessible
            for attr in dir(ds):
                if not attr.startswith("_"):
                    namespace[attr] = getattr(ds, attr)
            # Add domain_state dict contents
            if hasattr(ds, "domain_state"):
                for domain_key, domain_values in ds.domain_state.items():
                    if isinstance(domain_values, dict):
                        namespace.update(domain_values)
            return eval(code, {"__builtins__": {}}, namespace)

        return evaluator

    def _register_dag_seeds(self, domain: DomainDefinition) -> None:
        """Register DAG seeds from domain definition."""
        if self.skill_dag is None:
            return

        for seed in domain.dag_seeds:
            self.skill_dag.add_edge(
                from_skill=seed.from_skill,
                to_skill=seed.to_skill,
                edge_type=seed.type,
                metadata={"context": seed.context, "source": f"domain:{domain.domain}"},
            )

    def _register_sops(self, domain: DomainDefinition) -> None:
        """Register SOPs into CBKB."""
        # Lazy import to avoid circular dependency
        try:
            from homomics_lab.knowledge.cbkb import CBKB, LabSOP

            cbkb = CBKB(base_dir=".")
            for sop_def in domain.sops:
                sop = LabSOP(
                    id=sop_def.id,
                    title=sop_def.title,
                    version=sop_def.version,
                    category=domain.domain,
                    locked=sop_def.locked,
                    content=sop_def.content,
                )
                cbkb.create_sop(sop)
        except (ImportError, TypeError, Exception):
            # CBKB not available or not properly initialized, skip SOP registration
            pass

    def generate_intent_config(self, domain: DomainDefinition) -> Dict[str, Any]:
        """Generate intent analyzer configuration from domain definition."""
        return {
            "domain": domain.domain,
            "analysis_types": {
                intent.analysis_type: {
                    "keywords": intent.keywords,
                    "complexity_indicators": intent.complexity_indicators,
                    "data_scale_patterns": intent.data_scale_patterns,
                }
                for intent in domain.intents
            },
        }
