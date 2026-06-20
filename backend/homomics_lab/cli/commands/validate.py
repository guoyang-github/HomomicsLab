"""homomics validate - Validate a domain.yaml file."""

import sys
from pathlib import Path

from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.models import DomainDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.agent.plan.strategies import StrategyLibrary


def validate_domain(args):
    """Validate a domain.yaml file."""
    domain_path = Path(args.path)

    if not domain_path.exists():
        print(f"Error: File not found: {domain_path}", file=sys.stderr)
        sys.exit(1)

    # Try to parse as valid YAML and Pydantic model first
    try:
        import yaml
        with open(domain_path) as f:
            data = yaml.safe_load(f)
        domain = DomainDefinition(**data)
        print(f"Syntax: OK ({domain.domain} v{domain.version})")
    except Exception as e:
        print("Syntax: FAILED")
        print(f"  {e}")
        sys.exit(1)

    # Try to validate against existing skills/strategies
    try:
        skill_registry = SkillRegistry()
        # Try to load any skills referenced in the domain
        if domain.skills_dir:
            skills_path = domain_path.parent / domain.skills_dir
            if skills_path.exists():
                from homomics_lab.skills.loader import SkillLoader
                loader = SkillLoader(registry=skill_registry)
                loader.load_all(skills_path)

        strategy_lib = StrategyLibrary()
        domain_loader = DomainLoader(skill_registry, strategy_lib)

        # Validate
        errors = domain_loader.validator.validate(domain)

        if errors:
            print(f"Validation: FAILED ({len(errors)} error(s))")
            for error in errors:
                print(f"  - {error}")
            if args.strict:
                sys.exit(1)
        else:
            print("Validation: OK")

    except Exception as e:
        print("Validation: ERROR")
        print(f"  {e}")
        if args.strict:
            sys.exit(1)

    # Print summary
    print()
    print(f"Summary for '{domain.domain}':")
    print(f"  Phases: {len(domain.phases)}")
    print(f"  State checks: {len(domain.state_checks)}")
    print(f"  Intents: {len(domain.intents)}")
    print(f"  DAG seeds: {len(domain.dag_seeds)}")
    print(f"  Roles: {len(domain.roles)}")
    print(f"  SOPs: {len(domain.sops)}")
