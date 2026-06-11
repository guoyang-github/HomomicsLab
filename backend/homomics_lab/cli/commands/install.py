"""homomics install - Install a domain from a directory or git repo."""

import shutil
import subprocess
import sys
from pathlib import Path


def install_domain(args):
    """Install a domain from a local directory or git repository."""
    source = args.source
    domains_dir = Path(args.domains_dir)
    domains_dir.mkdir(parents=True, exist_ok=True)

    if source.startswith("http") or source.endswith(".git"):
        # Clone from git
        repo_name = source.split("/")[-1].replace(".git", "")
        temp_dir = Path(f"/tmp/homomics_install_{repo_name}")

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print(f"Cloning {source}...")
        result = subprocess.run(
            ["git", "clone", source, str(temp_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Git clone failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        source_path = temp_dir
    else:
        source_path = Path(source)

    if not source_path.exists():
        print(f"Error: Source not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    # Find domain.yaml
    domain_yaml = source_path / "domain.yaml"
    if not domain_yaml.exists():
        # Search recursively
        candidates = list(source_path.rglob("domain.yaml"))
        if not candidates:
            print(f"Error: No domain.yaml found in {source_path}", file=sys.stderr)
            sys.exit(1)
        domain_yaml = candidates[0]
        source_path = domain_yaml.parent

    # Validate before installing
    from homomics_lab.domain.models import DomainDefinition
    import yaml
    with open(domain_yaml) as f:
        data = yaml.safe_load(f)
    domain = DomainDefinition(**data)

    # Install
    target_dir = domains_dir / domain.domain
    if target_dir.exists():
        print(f"Domain '{domain.domain}' already exists. Overwrite? [y/N]", end=" ")
        response = input().strip().lower()
        if response != "y":
            print("Installation cancelled.")
            return
        shutil.rmtree(target_dir)

    shutil.copytree(source_path, target_dir)
    print(f"Installed domain '{domain.domain}' to {target_dir}")
    print(f"  Phases: {len(domain.phases)}")
    print(f"  Skills dir: {domain.skills_dir or 'N/A'}")
