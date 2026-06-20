"""RO-Crate export for project provenance."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.provenance.models import ExecutionProvenance


class ROCrateExporter:
    """Export a project and its provenance records as an RO-Crate."""

    def __init__(self, crate_dir: Path):
        self.crate_dir = Path(crate_dir)
        self.data_dir = self.crate_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        project_id: str,
        provenance_records: List[ExecutionProvenance],
        project_files: Optional[List[Path]] = None,
    ) -> Path:
        """Create an RO-Crate directory and return its path."""
        self.crate_dir.mkdir(parents=True, exist_ok=True)

        # Copy project files into data/
        file_map: Dict[str, str] = {}
        for src in project_files or []:
            if src.is_file():
                dest = self.data_dir / src.name
                shutil.copy2(src, dest)
                file_map[str(src)] = f"data/{src.name}"

        # Build RO-Crate metadata
        graph: List[Dict[str, Any]] = [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "name": f"HomomicsLab project {project_id}",
                "datePublished": datetime.now(timezone.utc).isoformat(),
                "hasPart": [{"@id": file_map[path]} for path in file_map],
            },
        ]

        for record in provenance_records:
            action_id = f"#{record.execution_id}"
            action_node: Dict[str, Any] = {
                "@id": action_id,
                "@type": "CreateAction",
                "name": f"Execute {record.skill_id}",
                "startTime": record.started_at.isoformat() if record.started_at else None,
                "endTime": record.ended_at.isoformat() if record.ended_at else None,
                "instrument": {"@id": f"#software-{record.skill_id}"},
                "object": [{"@id": file_map.get(f.path, f.path)} for f in record.input_files],
                "result": [{"@id": file_map.get(f.path, f.path)} for f in record.output_files],
            }
            software_node = {
                "@id": f"#software-{record.skill_id}",
                "@type": "SoftwareApplication",
                "name": record.skill_id,
                "version": record.skill_version,
            }
            if record.container_image:
                software_node["containerImage"] = record.container_image
            if record.container_digest:
                software_node["containerDigest"] = record.container_digest
            graph.extend([action_node, software_node])

        metadata = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph}
        (self.crate_dir / "ro-crate-metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False)
        )
        return self.crate_dir
