"""DomainLoader: reads a domain.yaml and registers everything into HomomicsLab."""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from homomics_lab.domain.models import (
    DomainDefinition,
    DomainStateCheck,
)
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StateCheck, StrategyLibrary
from homomics_lab.knowledge.cbkb import CBKB, LabSOP
from homomics_lab.prompts import get_prompt_registry, load_domain_prompts
from homomics_lab.prompts.registry import PromptRegistry
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry


logger = logging.getLogger(__name__)

# If False, missing skills become warnings instead of failing the whole domain
# (formerly HOMOMICS_DOMAIN_STRICT_VALIDATION; default kept).
DOMAIN_STRICT_VALIDATION = False


class DomainLoaderError(Exception):
    """Raised when domain.yaml is invalid or registration fails."""

    pass


# ---------------------------------------------------------------------------
# Safe expression evaluation for domain state-check conditions
# ---------------------------------------------------------------------------


def _safe_eval(node: ast.AST, namespace: Dict[str, Any]) -> Any:
    """Evaluate an AST node using only a supplied namespace.

    Supports comparisons, boolean/arithmetic operators, constants, names,
    and ``ds.<attr>`` attribute access. All other nodes are rejected so that
    domain condition expressions cannot execute arbitrary code.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body, namespace)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in namespace:
            raise NameError(f"Unknown variable in condition: {node.id}")
        return namespace[node.id]

    if isinstance(node, ast.Attribute):
        # Build the attribute chain and ensure it starts with ``ds``.
        attr_chain: List[str] = [node.attr]
        root = node.value
        while isinstance(root, ast.Attribute):
            attr_chain.append(root.attr)
            root = root.value
        if not isinstance(root, ast.Name) or root.id != "ds":
            raise ValueError(
                "Only 'ds.<attr>' attribute access is allowed in conditions"
            )
        obj = namespace.get("ds")
        for attr in reversed(attr_chain):
            obj = getattr(obj, attr)
        return obj

    if isinstance(node, ast.Compare):
        left = _safe_eval(node.left, namespace)
        for op, comparator in zip(node.ops, node.comparators):
            right = _safe_eval(comparator, namespace)
            if isinstance(op, ast.Eq):
                result = left == right
            elif isinstance(op, ast.NotEq):
                result = left != right
            elif isinstance(op, ast.Lt):
                result = left < right
            elif isinstance(op, ast.LtE):
                result = left <= right
            elif isinstance(op, ast.Gt):
                result = left > right
            elif isinstance(op, ast.GtE):
                result = left >= right
            elif isinstance(op, ast.Is):
                result = left is right
            elif isinstance(op, ast.IsNot):
                result = left is not right
            elif isinstance(op, ast.In):
                result = left in right
            elif isinstance(op, ast.NotIn):
                result = left not in right
            else:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
            if not result:
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        # Short-circuit evaluation so guards like
        # ``n_batches is not None and n_batches > 1`` do not raise.
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _safe_eval(value, namespace):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value in node.values:
                if _safe_eval(value, namespace):
                    return True
            return False
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand, namespace)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left, namespace)
        right = _safe_eval(node.right, namespace)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


_ALLOWED_CONDITION_NODES = {
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Attribute,
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
}


def _attribute_root_name(node: ast.Attribute) -> Optional[str]:
    """Return the root Name id for an attribute chain, or None."""
    root = node.value
    while isinstance(root, ast.Attribute):
        root = root.value
    if isinstance(root, ast.Name):
        return root.id
    return None


def _validate_condition_expression(condition_str: str) -> None:
    """Validate that a state-check condition is syntactically safe.

    Unlike evaluation-time checks, this does not require names to be present
    in the DataState namespace; it only ensures the AST contains allowed nodes
    and that attribute access is restricted to ``ds.<attr>``.
    """
    tree = ast.parse(condition_str, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_CONDITION_NODES:
            raise ValueError(
                f"Unsupported expression node: {type(node).__name__}"
            )
        if isinstance(node, ast.Attribute):
            root = _attribute_root_name(node)
            if root != "ds":
                raise ValueError(
                    "Only 'ds.<attr>' attribute access is allowed in conditions"
                )


@dataclass
class DomainValidationIssue:
    """A single validation issue with an associated severity."""

    severity: str  # "error" or "warning"
    message: str


class DomainValidator:
    """Validate a domain definition before registration."""

    def __init__(self, skill_registry: SkillRegistry, strategy_lib: StrategyLibrary):
        self.skill_registry = skill_registry
        self.strategy_lib = strategy_lib

    def validate(self, domain: DomainDefinition) -> List[DomainValidationIssue]:
        """Return a list of validation issues with severities."""
        issues: List[DomainValidationIssue] = []
        phase_ids = {p.id for p in domain.phases}
        all_skill_ids = {s.id for s in self.skill_registry.list_all()}

        # 1. Check that phases reference valid skills (soft in lenient mode)
        for phase in domain.phases:
            for skill_id in phase.skills:
                if skill_id not in all_skill_ids:
                    issues.append(
                        DomainValidationIssue(
                            "warning",
                            f"Phase '{phase.id}' references unknown skill '{skill_id}'",
                        )
                    )
            if phase.default_skill is not None and phase.default_skill not in all_skill_ids:
                issues.append(
                    DomainValidationIssue(
                        "warning",
                        f"Phase '{phase.id}' default_skill '{phase.default_skill}' not found",
                    )
                )

        # 2. Check that state_check targets exist in phases
        for check in domain.state_checks:
            # insert actions create a new phase dynamically, so the target does
            # not need to exist in the static skeleton. skip/modify_param still
            # require the target phase to be present.
            if (
                check.target not in phase_ids
                and check.action != "insert"
                and check.action != "modify_param"
            ):
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"StateCheck targets unknown phase '{check.target}'",
                    )
                )
            if check.after is not None and check.after not in phase_ids:
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"StateCheck references unknown 'after' phase '{check.after}'",
                    )
                )

        # 3. Check that phase transitions reference known phases
        for transition in domain.phase_transitions:
            if transition.from_phase not in phase_ids:
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"Phase transition from unknown phase '{transition.from_phase}'",
                    )
                )
            if transition.to_phase not in phase_ids:
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"Phase transition to unknown phase '{transition.to_phase}'",
                    )
                )

        # 4. Check that DAG seeds reference known skills (soft)
        for seed in domain.dag_seeds:
            if seed.from_skill not in all_skill_ids:
                issues.append(
                    DomainValidationIssue(
                        "warning",
                        f"DAG seed references unknown skill '{seed.from_skill}'",
                    )
                )
            if seed.to_skill not in all_skill_ids:
                issues.append(
                    DomainValidationIssue(
                        "warning",
                        f"DAG seed references unknown skill '{seed.to_skill}'",
                    )
                )

        # 5. Check that orchestrator skills exist (soft) and are not also phase skills (hard)
        phase_skill_ids: set[str] = set()
        for phase in domain.phases:
            phase_skill_ids.update(phase.skills)
        for orch_id in domain.orchestrator_skills:
            if orch_id not in all_skill_ids:
                issues.append(
                    DomainValidationIssue(
                        "warning",
                        f"Orchestrator skill '{orch_id}' not found in registry",
                    )
                )
            if orch_id in phase_skill_ids:
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"Orchestrator skill '{orch_id}' should not also be listed in a phase",
                    )
                )

        # 6. Check that intent analysis_types are unique
        intent_types = [i.analysis_type for i in domain.intents]
        if len(intent_types) != len(set(intent_types)):
            issues.append(
                DomainValidationIssue("error", "Duplicate analysis_type in intents")
            )

        # 7. Check that condition expressions are syntactically valid and safe
        for check in domain.state_checks:
            try:
                _validate_condition_expression(check.condition)
            except (SyntaxError, ValueError) as e:
                issues.append(
                    DomainValidationIssue(
                        "error",
                        f"Invalid condition expression '{check.condition}': {e}",
                    )
                )

        return issues


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
        cbkb: Optional[CBKB] = None,
        strict: Optional[bool] = None,
        prompt_registry: Optional[PromptRegistry] = None,
    ):
        self.skill_registry = skill_registry
        self.strategy_lib = strategy_lib
        self.skill_dag = skill_dag
        self.cbkb = cbkb
        self.validator = DomainValidator(skill_registry, strategy_lib)
        self.strict = (
            strict if strict is not None else DOMAIN_STRICT_VALIDATION
        )
        self.prompt_registry = prompt_registry or get_prompt_registry()

    def load(self, domain_yaml_path: Path) -> DomainDefinition:
        """Load a domain.yaml and register all components.

        Returns the parsed DomainDefinition.
        Raises DomainLoaderError on hard validation failure.
        """
        # 1. Parse YAML
        domain = self._parse_yaml(domain_yaml_path)

        # 2. Load skills (if skills_dir specified)
        if domain.skills_dir:
            skills_path = domain_yaml_path.parent / domain.skills_dir
            self._load_skills(skills_path)

        # 3. Validate and repair in lenient mode
        issues = self.validator.validate(domain)
        domain = self._apply_repair(domain, issues)

        hard_errors = [i for i in issues if i.severity == "error"]
        if hard_errors or (self.strict and domain.warnings):
            messages = [i.message for i in (hard_errors or issues)]
            raise DomainLoaderError(
                f"Domain '{domain.domain}' validation failed:\n"
                + "\n".join(f"  - {m}" for m in messages)
            )

        if domain.warnings:
            logger.warning(
                "Domain '%s' loaded with warnings:\n%s",
                domain.domain,
                "\n".join(f"  - {w}" for w in domain.warnings),
            )

        # 4. Register strategy
        self._register_strategy(domain)

        # 5. Register DAG seeds
        if self.skill_dag:
            self._register_dag_seeds(domain)

        # 6. Register SOPs
        self._register_sops(domain)

        # 7. Register prompt templates declared by the domain
        if domain.prompts:
            self.prompt_registry.clear_domain(domain.domain)
            load_domain_prompts(domain.domain, domain.prompts, registry=self.prompt_registry)

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

    def _apply_repair(
        self,
        domain: DomainDefinition,
        issues: List[DomainValidationIssue],
    ) -> DomainDefinition:
        """Remove unknown skill references and record warnings for a lenient load."""
        if not issues:
            return domain

        warnings: List[str] = []
        all_skill_ids = {s.id for s in self.skill_registry.list_all()}

        # Repair phases
        for phase in domain.phases:
            missing = [s for s in phase.skills if s not in all_skill_ids]
            if missing:
                warnings.extend(
                    f"Phase '{phase.id}': removed unknown skill '{s}'" for s in missing
                )
                phase.skills = [s for s in phase.skills if s in all_skill_ids]

            if phase.default_skill is not None and phase.default_skill not in all_skill_ids:
                warnings.append(
                    f"Phase '{phase.id}': removed unknown default_skill '{phase.default_skill}'"
                )
                phase.default_skill = None

            if not phase.skills:
                phase.unresolvable = True
                warnings.append(
                    f"Phase '{phase.id}': no resolvable skills; marked unresolvable"
                )

        # Repair orchestrator skills
        missing_orch = [s for s in domain.orchestrator_skills if s not in all_skill_ids]
        if missing_orch:
            warnings.extend(f"Removed unknown orchestrator skill '{s}'" for s in missing_orch)
            domain.orchestrator_skills = [
                s for s in domain.orchestrator_skills if s in all_skill_ids
            ]

        # Repair DAG seeds
        bad_seeds = [
            seed
            for seed in domain.dag_seeds
            if seed.from_skill not in all_skill_ids or seed.to_skill not in all_skill_ids
        ]
        if bad_seeds:
            for seed in bad_seeds:
                warnings.append(
                    f"Removed DAG seed {seed.from_skill} -> {seed.to_skill} (unknown skill)"
                )
            domain.dag_seeds = [
                seed
                for seed in domain.dag_seeds
                if seed.from_skill in all_skill_ids and seed.to_skill in all_skill_ids
            ]

        domain.warnings = warnings
        return domain

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
                candidate_skills=list(phase.skills),
                default_skill=phase.default_skill,
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
            preferred_libraries=domain.preferred_libraries,
            code_templates=domain.code_templates,
            data_sources=domain.data_sources,
            fallback_rules=domain.fallback_rules,
            phase_transitions=[
                {"from": t.from_phase, "to": t.to_phase, "type": t.type, "context": t.context}
                for t in domain.phase_transitions
            ],
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
        Expressions are parsed into an AST and evaluated against a restricted
        namespace; no Python builtins are available.
        """
        try:
            tree = ast.parse(condition_str, mode="eval")
        except SyntaxError as exc:
            raise DomainLoaderError(
                f"Invalid condition expression: {condition_str}"
            ) from exc

        def evaluator(ds: DataState) -> bool:
            # Build namespace with DataState fields accessible by name
            namespace: Dict[str, Any] = {"ds": ds}
            # Add DataState attributes directly accessible
            for attr in dir(ds):
                if not attr.startswith("_"):
                    namespace[attr] = getattr(ds, attr)
            # Add domain_state dict contents
            if hasattr(ds, "domain_state"):
                for domain_key, domain_values in ds.domain_state.items():
                    if isinstance(domain_values, dict):
                        namespace.update(domain_values)
            try:
                return bool(_safe_eval(tree, namespace))
            except Exception as exc:
                logger.warning(
                    "Failed to evaluate state condition '%s': %s", condition_str, exc
                )
                return False

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
        if self.cbkb is None or not domain.sops:
            return

        import sqlite3

        for sop_def in domain.sops:
            sop = LabSOP(
                id=sop_def.id,
                name=sop_def.title,
                category=domain.domain,
                template={
                    "steps": sop_def.steps,
                    "content": sop_def.content,
                },
                derived_from_bundle_ids=[],
                version=sop_def.version,
                locked=sop_def.locked,
            )
            try:
                self.cbkb.create_sop(sop)
            except sqlite3.IntegrityError:
                # SOP already exists; leave the existing record untouched.
                pass
            except Exception as exc:
                print(
                    f"Warning: Failed to register SOP '{sop_def.id}' for domain "
                    f"'{domain.domain}': {exc}"
                )

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
