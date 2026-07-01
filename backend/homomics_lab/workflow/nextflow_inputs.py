"""Build Nextflow inputs from a Plan and project workspace."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.workspace.manager import WorkspaceManager


class NextflowInputBuilder:
    """Convert a PlanResult + workspace into Nextflow params and samplesheets."""

    def __init__(self, base_dir: Path, project_id: str):
        self.workspace = WorkspaceManager(base_dir, project_id)

    def build(self, plan_result: PlanResult, template_name: Optional[str] = None) -> Dict[str, Any]:
        """Build a flat params dict plus any sidecar samplesheet files."""
        inputs: Dict[str, Any] = {
            "outdir": str(self.workspace.get_path("outputs/nf_results")),
            "project_id": self.workspace.project_id,
        }

        # Flatten phase parameters into params. Phase-specific keys win over globals.
        for phase in plan_result.phases:
            for key, value in (phase.parameters or {}).items():
                inputs[key] = value

        # Derive input files from the workspace data directory.
        data_files = self._discover_data_files()

        # Curated templates may need a samplesheet.
        if template_name == "single_cell":
            samplesheet = self._build_single_cell_samplesheet(data_files)
            if samplesheet is not None:
                inputs["samplesheet"] = str(samplesheet)
        elif template_name == "rnaseq":
            samplesheet = self._build_rnaseq_samplesheet(data_files)
            if samplesheet is not None:
                inputs["samplesheet"] = str(samplesheet)
        else:
            # Auto mode: expose the first usable data file as input_path.
            if data_files:
                inputs["input_path"] = str(data_files[0])

        return inputs

    def _discover_data_files(self) -> List[Path]:
        """Return sorted list of data files in the workspace data directory."""
        data_dir = self.workspace.get_path("data")
        if not data_dir.exists():
            return []
        files = [
            p
            for p in data_dir.iterdir()
            if p.is_file() and not p.name.startswith(".")
        ]
        return sorted(files, key=lambda p: p.name.lower())

    def _build_single_cell_samplesheet(self, data_files: List[Path]) -> Optional[Path]:
        """Create a two-column samplesheet: sample,input_path."""
        if not data_files:
            return None
        samplesheet_path = self.workspace.get_path("intermediate/samplesheet.csv")
        samplesheet_path.parent.mkdir(parents=True, exist_ok=True)
        with samplesheet_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample", "input_path"])
            for p in data_files:
                sample_name = p.stem
                writer.writerow([sample_name, str(p)])
        return samplesheet_path

    def _build_rnaseq_samplesheet(self, data_files: List[Path]) -> Optional[Path]:
        """Create a simple RNA-seq samplesheet: sample,fastq_1[,fastq_2]."""
        if not data_files:
            return None
        samplesheet_path = self.workspace.get_path("intermediate/samplesheet.csv")
        samplesheet_path.parent.mkdir(parents=True, exist_ok=True)
        with samplesheet_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sample", "fastq_1", "fastq_2", "strandedness"])
            # Pair files heuristically by sample stem.
            by_sample: Dict[str, List[Path]] = {}
            for p in data_files:
                name = p.stem
                # Strip common suffixes like _1, _2, _R1, _R2 before grouping.
                base = name
                for suffix in ("_R2", "_R1", "_2", "_1"):
                    if base.endswith(suffix):
                        base = base[: -len(suffix)]
                        break
                by_sample.setdefault(base, []).append(p)
            for sample, paths in sorted(by_sample.items()):
                paths = sorted(paths, key=lambda p: p.name.lower())
                fastq_1 = str(paths[0]) if paths else ""
                fastq_2 = str(paths[1]) if len(paths) > 1 else ""
                writer.writerow([sample, fastq_1, fastq_2, "auto"])
        return samplesheet_path
