"""Seed CLI: broadcast cold-start baseline records into CBKB and SkillDAG."""

import argparse
from pathlib import Path

from homomics_lab.config import settings
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.knowledge.seed import seed_baselines
from homomics_lab.skills.registry import get_default_registry
from homomics_lab.skills.skill_dag import SkillDAG


def register_seed_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "seed",
        help="Broadcast cold-start baseline records into CBKB and SkillDAG",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-broadcast even if seed records already exist",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Data directory holding cbkb/skill_dag stores (default: HOMOMICS_DATA_DIR)",
    )


def run_seed(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir) if args.data_dir else Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    cbkb = CBKB(base_dir=data_dir)
    skill_dag = SkillDAG(
        registry=get_default_registry(),
        db_path=data_dir / "skill_dag.db",
    )

    report = seed_baselines(cbkb, skill_dag, force=args.force)
    print(
        "Seed complete: "
        f"{report['experiments_added']} experiments added, "
        f"{report['experiment_edges_added']} experiment edges added, "
        f"{report['skill_edges_confirmed']} skill edges confirmed, "
        f"{report['skipped']} skipped"
    )
    return 0
