"""Ingest nf-core pipeline outputs into the HomomicsLab workspace.

After an nf-core run completes, this module scans the output directory for
known result files (MultiQC reports, quantification outputs, tables, plots)
and registers them as tracked artifacts via WorkspaceManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.workspace.manager import WorkspaceManager


@dataclass
class ResultPattern:
    """Pattern for recognizing a result artifact."""

    artifact_type: str  # "report" | "data" | "plot" | "table" | "log"
    globs: List[str]
    description: str


# Common nf-core output patterns.
DEFAULT_PATTERNS: List[ResultPattern] = [
    ResultPattern(
        artifact_type="report",
        globs=["**/multiqc_report.html", "**/MultiQC/multiqc_report.html"],
        description="MultiQC quality control report",
    ),
    ResultPattern(
        artifact_type="data",
        globs=["**/quant.sf", "**/salmon/**/quant.sf", "**/star_salmon/**/quant.sf"],
        description="Salmon quantification output",
    ),
    ResultPattern(
        artifact_type="data",
        globs=["**/*.h5ad"],
        description="Single-cell AnnData object",
    ),
    ResultPattern(
        artifact_type="table",
        globs=["**/*.csv", "**/*.tsv"],
        description="Tabular result file",
    ),
    ResultPattern(
        artifact_type="plot",
        globs=["**/*.png", "**/*.pdf", "**/*.svg"],
        description="Plot or figure",
    ),
    ResultPattern(
        artifact_type="report",
        globs=["**/pipeline_info/execution_report_*.html", "**/pipeline_info/dag_*.html"],
        description="Nextflow execution report",
    ),
    ResultPattern(
        artifact_type="log",
        globs=["**/pipeline_info/execution_trace_*.txt"],
        description="Nextflow execution trace",
    ),
]

# WorkspaceManager only accepts a closed set of artifact types. Map semantic
# nf-core artifact labels to the workspace taxonomy.
WORKSPACE_TYPE_MAP: Dict[str, str] = {
    "report": "output",
    "data": "data",
    "table": "output",
    "plot": "output",
    "log": "intermediate",
}


class NFCoreResultIngester:
    """Scan nf-core output directories and register artifacts."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        patterns: Optional[List[ResultPattern]] = None,
    ):
        self.workspace = workspace_manager
        self.patterns = patterns or DEFAULT_PATTERNS

    def ingest(
        self,
        output_dir: Path,
        task_id: str,
        source_task: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Scan ``output_dir`` and register all matching files as artifacts.

        Returns:
            List of registered artifact metadata dicts.
        """
        output_dir = Path(output_dir)
        if not output_dir.exists():
            return []

        registered: List[Dict[str, Any]] = []
        seen: set[Path] = set()

        for pattern in self.patterns:
            workspace_type = WORKSPACE_TYPE_MAP.get(pattern.artifact_type, "output")
            for glob in pattern.globs:
                for file_path in output_dir.glob(glob):
                    if not file_path.is_file():
                        continue
                    resolved = file_path.resolve()
                    if resolved in seen:
                        continue
                    seen.add(resolved)

                    # Preserve sub-directory structure to avoid name collisions.
                    rel_path = file_path.relative_to(output_dir)
                    safe_name = str(rel_path).replace("../", "").replace("..", "")

                    artifact_path = self.workspace.register_artifact(
                        task_id=task_id,
                        artifact_type=workspace_type,
                        filename=safe_name,
                        source_task=source_task,
                        metadata={
                            "description": pattern.description,
                            "nfcore_artifact_type": pattern.artifact_type,
                            "relative_path": str(rel_path),
                        },
                    )
                    # Copy the file into the workspace artifact location.
                    artifact_path.write_bytes(file_path.read_bytes())
                    self.workspace.update_artifact_checksum(
                        f"{workspace_type}/{safe_name}"
                    )

                    registered.append({
                        "artifact_type": pattern.artifact_type,
                        "workspace_type": workspace_type,
                        "filename": safe_name,
                        "path": str(artifact_path),
                        "description": pattern.description,
                    })

        return registered

    def ingest_multiqc_summary(self, output_dir: Path) -> Optional[Dict[str, Any]]:
        """Extract a lightweight summary from MultiQC JSON if present."""
        multiqc_json_paths = list(output_dir.glob("**/multiqc_data/multiqc_data.json"))
        if not multiqc_json_paths:
            return None

        import json

        try:
            data = json.loads(multiqc_json_paths[0].read_text(encoding="utf-8"))
            summary = {
                "report_general_stats": list(data.get("report_general_stats_data", {}).keys()),
                "sample_count": len(data.get("report_general_stats_data", {})),
            }
            return summary
        except Exception:
            return None
