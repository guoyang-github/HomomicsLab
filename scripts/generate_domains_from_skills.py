"""Generate domain templates from external skill collections.

Usage:
    python scripts/generate_domains_from_skills.py \
        /path/to/NanoResearch-Skills/skills \
        /path/to/Genomics-Skills/skills \
        ... \
        --out-dir backend/homomics_lab/domains

The script parses SKILL.md frontmatter, groups skills by collection, infers
analysis phases from skill names/descriptions, and writes a domain.yaml per
collection.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def parse_frontmatter(skill_path: Path) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from a SKILL.md file."""
    text = skill_path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1])
    except Exception:
        return None


def collection_name_from_path(skill_dir: Path) -> str:
    """Derive a collection/domain name from the parent skill directory."""
    # /.../mRNAseq-Skills/skills -> mrna_seq
    repo_name = skill_dir.parent.name
    name = repo_name.replace("-Skills", "").replace("-", "_").lower()
    return name


def normalize_domain_id(collection: str) -> str:
    """Create a valid domain id from a collection name."""
    return re.sub(r"[^a-z0-9_]", "_", collection).strip("_")


def infer_phase(skill_id: str, description: str) -> str:
    """Infer a phase label from skill id and description."""
    desc = (description or "").lower()
    sid = skill_id.lower()
    # Explicit workflow/pipeline skills usually represent the whole domain.
    if "workflow" in sid or "pipeline" in sid or "orchestrator" in sid:
        return "pipeline"
    # Common phase keywords.
    phase_keywords = [
        ("qc", ["qc", "quality control", "preprocessing", "trim", "fastqc", "multiqc"]),
        ("alignment", ["alignment", "align", "mapping", "map", "star", "bwa", "hisat"]),
        ("quantification", ["quantification", "quantify", "count", "featurecounts", "salmon", "kallisto", "rsem"]),
        ("normalization", ["normalization", "normalize", "batch correction", "combat", "harmony"]),
        ("differential_expression", ["differential expression", "deseq", "edge", "limma", "de " ]),
        ("clustering", ["cluster", "louvain", "leiden", "umap", "tsne", "pca"]),
        ("annotation", ["annotate", "annotation", "celltypist", "sctype", "singler", "markers"]),
        ("pathway_enrichment", ["pathway", "enrichment", "gsea", "go", "kegg", "ora"]),
        ("visualization", ["visualization", "visualize", "plot", "figure", "illustration"]),
        ("variant_calling", ["variant", "snp", "indel", "germline", "somatic", "mutect", "gatk"]),
        ("interpretation", ["interpretation", "variant interpretation", "annotation"]),
        ("database_query", ["database", "query", "search", "fetch", "geo", "uniprot", "pubmed"]),
        ("literature", ["literature", "review", "manuscript", "grant", "peer review", "communication"]),
        ("translation", ["translation", "ribosome", "orf", "stalling", "occupancy", "riboseq"]),
    ]
    for phase, keywords in phase_keywords:
        if any(kw in sid or kw in desc for kw in keywords):
            return phase
    return "analysis"


def order_phase(phase: str) -> int:
    """Return a rough ordering index for phases."""
    order = [
        "qc",
        "preprocessing",
        "alignment",
        "quantification",
        "normalization",
        "clustering",
        "annotation",
        "differential_expression",
        "pathway_enrichment",
        "variant_calling",
        "interpretation",
        "visualization",
        "translation",
        "database_query",
        "literature",
        "pipeline",
        "analysis",
    ]
    try:
        return order.index(phase)
    except ValueError:
        return 99


def build_domain(collection: str, skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a domain YAML dict from a list of skill frontmatters."""
    domain_id = normalize_domain_id(collection)
    display_name = collection.replace("_", " ").title()

    # Group skills by inferred phase.
    phase_skills: Dict[str, List[str]] = defaultdict(list)
    phase_descriptions: Dict[str, List[str]] = defaultdict(list)
    workflow_skills: List[str] = []

    for skill in skills:
        sid = skill.get("name") or skill.get("id")
        if not sid:
            continue
        desc = skill.get("description", "")
        phase = infer_phase(sid, desc)
        if phase == "pipeline":
            workflow_skills.append(sid)
            continue
        phase_skills[phase].append(sid)
        phase_descriptions[phase].append(desc.split(".")[0])

    phases = []
    for phase in sorted(phase_skills.keys(), key=order_phase):
        skill_list = phase_skills[phase]
        if not skill_list:
            continue
        desc = phase_descriptions.get(phase, [""])[0] or f"{phase.replace('_', ' ').title()} step"
        phases.append(
            {
                "id": phase,
                "required": phase in ("qc", "alignment", "quantification", "pipeline"),
                "description": desc,
                "skills": skill_list[:5],  # avoid overly long phase lists
                "default_skill": skill_list[0],
            }
        )

    # If there is an explicit workflow/orchestrator skill, add it as final pipeline phase.
    for wf in workflow_skills:
        phases.append(
            {
                "id": "pipeline",
                "required": False,
                "description": f"End-to-end {display_name} workflow",
                "skills": [wf],
                "default_skill": wf,
            }
        )

    # Build simple DAG seeds: each phase -> next phase.
    dag_seeds = []
    for i in range(len(phases) - 1):
        for src_skill in phases[i]["skills"][:1]:
            for tgt_skill in phases[i + 1]["skills"][:1]:
                dag_seeds.append(
                    {"from": src_skill, "to": tgt_skill, "type": "followed_by", "context": "auto-generated"}
                )

    # Build intent from collection name.
    intent_type = f"{domain_id}_analysis"
    keywords = [display_name, domain_id.replace("_", " ")]
    if "mrna" in domain_id:
        keywords.extend(["mRNA-seq", "bulk RNA-seq", "transcriptome"])
    if "ribo" in domain_id:
        keywords.extend(["Ribo-seq", "ribosome profiling", "translation"])
    if "genomics" in domain_id:
        keywords.extend(["genomics", "WGS", "WES", "variant calling"])
    if "database" in domain_id:
        keywords.extend(["database", "query", "search", "annotation"])
    if "paper" in domain_id or "writing" in domain_id:
        keywords.extend(["paper writing", "manuscript", "grant", "literature review"])

    domain = {
        "domain": domain_id,
        "display_name": display_name,
        "description": f"Auto-generated {display_name} analysis domain from imported skills.",
        "version": "1.0.0",
        "phases": phases,
        "intents": [
            {
                "analysis_type": intent_type,
                "keywords": list(set(keywords)),
            }
        ],
        "roles": [
            {
                "role_id": f"{domain_id}_specialist",
                "name": f"{display_name} Specialist",
                "allowed_skills": [s.get("name") for s in skills if s.get("name")][:20],
                "allowed_tools": ["file_read", "file_write", "shell_exec"],
                "permissions": {
                    "can_execute": True,
                    "can_spawn_specialist": False,
                    "max_concurrent_tasks": 3,
                },
            }
        ],
        "dag_seeds": dag_seeds,
        "sops": [
            {
                "id": f"sop_{domain_id}_v1",
                "title": f"{display_name} Analysis SOP",
                "steps": [f"Run {p['id'].replace('_', ' ')} step" for p in phases],
            }
        ],
    }
    return domain


def main():
    parser = argparse.ArgumentParser(description="Generate domain templates from skill collections.")
    parser.add_argument("skill_dirs", nargs="+", type=Path, help="Directories containing skill subdirectories")
    parser.add_argument("--out-dir", type=Path, default=Path("backend/homomics_lab/domains"), help="Output directory for domain YAMLs")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Group skills by collection.
    collections: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for skill_dir in args.skill_dirs:
        if not skill_dir.exists():
            print(f"Skipping non-existent directory: {skill_dir}")
            continue
        collection = collection_name_from_path(skill_dir)
        for skill_path in skill_dir.iterdir():
            if not skill_path.is_dir():
                continue
            md_path = skill_path / "SKILL.md"
            if not md_path.exists():
                continue
            frontmatter = parse_frontmatter(md_path)
            if frontmatter:
                collections[collection].append(frontmatter)

    for collection, skills in sorted(collections.items()):
        if not skills:
            continue
        domain = build_domain(collection, skills)
        domain_dir = args.out_dir / domain["domain"]
        domain_dir.mkdir(parents=True, exist_ok=True)
        domain_path = domain_dir / "domain.yaml"
        domain_path.write_text(yaml.safe_dump(domain, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"Generated {domain_path} with {len(skills)} skills, {len(domain['phases'])} phases")


if __name__ == "__main__":
    main()
