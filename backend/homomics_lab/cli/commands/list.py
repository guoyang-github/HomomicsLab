"""homomics list - List all installed domains."""

from pathlib import Path

import yaml

from homomics_lab.domain.models import DomainDefinition


def list_domains(args):
    """List all installed domains."""
    domains_dir = Path(args.domains_dir)

    if not domains_dir.exists():
        print(f"Domains directory not found: {domains_dir}")
        print("No domains installed.")
        return

    domains = []
    for domain_yaml in domains_dir.rglob("domain.yaml"):
        try:
            with open(domain_yaml) as f:
                data = yaml.safe_load(f)
            domain = DomainDefinition(**data)
            domains.append((domain, domain_yaml.parent))
        except Exception as e:
            if args.verbose:
                print(f"Warning: Failed to parse {domain_yaml}: {e}")

    if not domains:
        print("No domains installed.")
        return

    print(f"Installed domains ({len(domains)}):")
    print()

    for domain, path in sorted(domains, key=lambda x: x[0].domain):
        print(f"  {domain.domain} (v{domain.version})")
        print(f"    Path: {path}")
        print(f"    Description: {domain.description}")
        if args.verbose:
            print(f"    Phases: {len(domain.phases)}")
            print(f"    State checks: {len(domain.state_checks)}")
            print(f"    Intents: {len(domain.intents)}")
            print(f"    DAG seeds: {len(domain.dag_seeds)}")
            print(f"    Roles: {len(domain.roles)}")
            print(f"    SOPs: {len(domain.sops)}")
        print()
