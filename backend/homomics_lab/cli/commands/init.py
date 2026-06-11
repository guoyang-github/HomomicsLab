"""homomics init - Initialize a new domain scaffold."""

from pathlib import Path

import yaml


DOMAIN_TEMPLATE_BLANK = """domain: {domain_name}
description: "{description}"
version: "1.0.0"

phases:
{phases_yaml}

state_checks: []

intents:
  - analysis_type: {domain_name}_analysis
    keywords:
      - "{domain_name}"
    complexity_indicators: []
    data_scale_patterns: []

dag_seeds: []

roles: []

sops: []

data_state_schema: {{}}

skills_dir: null
"""

PHASE_TEMPLATE = """  - id: {phase_id}
    required: true
    description: "{phase_id} analysis step"
    skills: []
"""


def init_domain(args):
    """Initialize a new domain scaffold."""
    domain_name = args.name
    output_dir = Path(args.output)
    domain_dir = output_dir / domain_name
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Parse phases
    phases = []
    if args.phases:
        phase_ids = [p.strip() for p in args.phases.split(",")]
        phases = [PHASE_TEMPLATE.format(phase_id=p) for p in phase_ids]

    phases_yaml = "\n".join(phases) if phases else "  # Add phases here"

    # Generate domain.yaml
    domain_yaml = DOMAIN_TEMPLATE_BLANK.format(
        domain_name=domain_name,
        description=f"{domain_name} analysis pipeline",
        phases_yaml=phases_yaml,
    )

    domain_yaml_path = domain_dir / "domain.yaml"
    with open(domain_yaml_path, "w") as f:
        f.write(domain_yaml)

    # Create skills directory
    skills_dir = domain_dir / "skills"
    skills_dir.mkdir(exist_ok=True)

    # Create __init__.py for skills package
    (skills_dir / "__init__.py").write_text("")

    print(f"Domain scaffold created: {domain_dir}")
    print(f"  domain.yaml: {domain_yaml_path}")
    print(f"  skills/: {skills_dir}")
    print()
    print("Next steps:")
    print(f"  1. Edit {domain_yaml_path} to define your phases, state_checks, intents")
    print(f"  2. Add skills to {skills_dir}/")
    print(f"  3. Run: homomics validate {domain_yaml_path}")
