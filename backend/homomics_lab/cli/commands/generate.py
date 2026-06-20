"""homomics generate - Generate a domain from natural language (LLM-assisted)."""

import os
import sys
from pathlib import Path


def generate_domain(args):
    """Generate a domain configuration from natural language using LLM."""
    description = args.description
    output_dir = Path(args.output)

    # Check for OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        print("Set it with: export OPENAI_API_KEY=sk-...", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed.", file=sys.stderr)
        print("Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    system_prompt = """You are a bioinformatics workflow expert. Given a natural language description of an analysis workflow, generate a complete HomomicsLab domain.yaml configuration.

The output must be valid YAML following this schema:

```yaml
domain: <domain_id>
description: <description>
version: "1.0.0"
phases:
  - id: <phase_id>
    required: true|false
    description: <description>
    skills: [<skill_id>]
state_checks:
  - condition: <python expression using ds.field_name>
    action: insert|skip|modify_param
    target: <phase_id>
    value: <optional>
    after: <phase_id for insert>
intents:
  - analysis_type: <type>
    keywords: [<keyword>]
    complexity_indicators: [<keyword>]
dag_seeds:
  - from: <skill_id>
    to: <skill_id>
    type: followed_by|conflicts_with|alternative_to|depends_on
    context: <description>
roles:
  - role_id: <role_id>
    name: <name>
    allowed_skills: [<skill_id>]
    allowed_tools: [file_read, file_write, shell_exec]
    permissions:
      can_execute: true
    priority: 2
data_state_schema:
  <field_name>:
    type: boolean|integer|string|number
    description: <description>
```

Rules:
1. Use snake_case for all IDs
2. Conditions in state_checks should use simple field comparisons (e.g. 'host_contamination > 0.1', 'n_samples < 3')
3. Each phase should have at least one skill
4. Include both English and Chinese keywords if relevant
5. Make the domain as complete and realistic as possible

Output ONLY the YAML content, no markdown fences, no explanations.
"""

    print(f"Generating domain from description using {args.model}...")

    try:
        response = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate a domain.yaml for: {description}"},
            ],
            temperature=0.3,
        )
        yaml_content = response.choices[0].message.content.strip()

        # Remove markdown fences if present
        if yaml_content.startswith("```yaml"):
            yaml_content = yaml_content[7:]
        if yaml_content.startswith("```"):
            yaml_content = yaml_content[3:]
        if yaml_content.endswith("```"):
            yaml_content = yaml_content[:-3]
        yaml_content = yaml_content.strip()

        # Validate
        import yaml
        data = yaml.safe_load(yaml_content)
        from homomics_lab.domain.models import DomainDefinition
        domain = DomainDefinition(**data)

        # Write output
        domain_dir = output_dir / domain.domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        domain_yaml_path = domain_dir / "domain.yaml"

        with open(domain_yaml_path, "w") as f:
            f.write(yaml_content)

        # Create skills directory
        (domain_dir / "skills").mkdir(exist_ok=True)

        print(f"Generated domain: {domain.domain}")
        print(f"  Saved to: {domain_yaml_path}")
        print(f"  Phases: {len(domain.phases)}")
        print(f"  Next: homomics validate {domain_yaml_path}")

    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        sys.exit(1)
