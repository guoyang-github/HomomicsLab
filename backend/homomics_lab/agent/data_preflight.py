"""DataPreflight — lightweight data-aware planning before decomposition.

Reads the metadata of files referenced by the user and decides which phases
are actually necessary. This prevents rigid domain strategies from forcing
unneeded qc / normalization / clustering steps when the user only wants a
single-shot analysis (e.g. "run CellTypist and compare labels").
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """Decision produced by DataPreflight."""

    file_paths: List[str] = field(default_factory=list)
    data_notes: str = ""
    skip_phases: List[str] = field(default_factory=list)
    required_steps: List[str] = field(default_factory=list)
    target_column: Optional[str] = None
    target_column_exists: bool = False
    available_layers: List[str] = field(default_factory=list)
    suggested_input_layer: Optional[str] = None
    needs_qc: bool = False
    needs_normalization: bool = False
    needs_clustering: bool = False
    needs_annotation: bool = False
    raw_counts_layer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_paths": self.file_paths,
            "data_notes": self.data_notes,
            "skip_phases": self.skip_phases,
            "required_steps": self.required_steps,
            "target_column": self.target_column,
            "target_column_exists": self.target_column_exists,
            "available_layers": self.available_layers,
            "suggested_input_layer": self.suggested_input_layer,
            "needs_qc": self.needs_qc,
            "needs_normalization": self.needs_normalization,
            "needs_clustering": self.needs_clustering,
            "needs_annotation": self.needs_annotation,
            "raw_counts_layer": self.raw_counts_layer,
            "metadata": self.metadata,
        }


class DataPreflight:
    """Inspect referenced files and decide the minimal required workflow."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    async def run(
        self,
        user_request: str,
        file_paths: List[str],
        intent_type: str = "",
    ) -> PreflightResult:
        """Run preflight on the referenced files."""
        if not file_paths:
            return PreflightResult()

        metadatas = []
        for p in file_paths:
            try:
                # _read_metadata does blocking file I/O (h5ad reads, matrix
                # sampling); keep it off the event loop.
                meta = await asyncio.to_thread(self._read_metadata, Path(p))
                metadatas.append({"path": p, **meta})
            except Exception as exc:
                logger.warning("Preflight failed to read %s: %s", p, exc)
                metadatas.append({"path": p, "error": str(exc)})

        if not metadatas:
            return PreflightResult(file_paths=file_paths)

        target_column = self._extract_target_column(user_request)
        target_exists = self._check_target_column(metadatas, target_column)

        # Try LLM-driven decision when configured.
        if self.llm_client is not None and self.llm_client.is_configured():
            try:
                decision = await self._llm_decide(
                    user_request, intent_type, metadatas, target_column, target_exists
                )
                decision.file_paths = file_paths
                decision.target_column = target_column
                decision.target_column_exists = target_exists
                decision.metadata = {"files": metadatas}
                return decision
            except Exception as exc:
                logger.warning("LLM preflight decision failed: %s", exc, exc_info=True)

        # Lightweight heuristic fallback.
        decision = self._heuristic_decide(
            user_request, intent_type, metadatas, target_column, target_exists
        )
        decision.file_paths = file_paths
        decision.target_column = target_column
        decision.target_column_exists = target_exists
        decision.metadata = {"files": metadatas}
        return decision

    @staticmethod
    def _parse_json_response(response: str) -> Dict[str, Any]:
        """Parse an LLM response that may be wrapped in markdown fences.

        Tries strict JSON first, then YAML as a more forgiving fallback for
        common LLM formatting mistakes (unquoted keys, trailing commas,
        single-quoted strings).
        """
        import yaml

        text = (response or "").strip()
        if text.startswith("```"):
            # Drop the opening fence and optional language tag.
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
        if not text:
            raise ValueError("Empty LLM response")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        raise ValueError(f"Could not parse LLM response as JSON or YAML: {text[:200]}")

    @staticmethod
    def _extract_target_column(user_request: str) -> Optional[str]:
        """Extract a column name the user wants to compare against."""
        lowered = (user_request or "").lower()
        if "all_celltype" in lowered:
            return "all_celltype"
        return None

    @staticmethod
    def _check_target_column(metadatas: List[Dict[str, Any]], column: Optional[str]) -> bool:
        if not column:
            return False
        for meta in metadatas:
            obs_columns = meta.get("obs_columns", [])
            if column in obs_columns:
                return True
        return False

    def _read_metadata(self, path: Path) -> Dict[str, Any]:
        """Read lightweight metadata without loading heavy matrix data."""
        suffix = path.suffix.lower()
        if suffix == ".h5ad":
            return self._read_h5ad_metadata(path)
        return {
            "format": suffix.lstrip(".") or "unknown",
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }

    @staticmethod
    def _read_h5ad_metadata(path: Path) -> Dict[str, Any]:
        """Read AnnData metadata in backed mode."""
        import anndata as ad

        adata = ad.read_h5ad(str(path), backed="r")
        try:
            obs_cols = list(adata.obs.columns)
            var_cols = list(adata.var.columns)
            layers = list(adata.layers.keys())
            obsm_keys = list(adata.obsm.keys())
            uns_keys = list(adata.uns.keys())
            shape = (int(adata.n_obs), int(adata.n_vars))

            result: Dict[str, Any] = {
                "format": "h5ad",
                "shape": shape,
                "obs_columns": obs_cols,
                "var_columns": var_cols,
                "layers": layers,
                "obsm_keys": obsm_keys,
                "uns_keys": uns_keys,
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }

            # Sample of categorical/string obs columns for context.
            sample_cols: Dict[str, Any] = {}
            for col in obs_cols[:20]:
                try:
                    sample_cols[col] = {
                        "dtype": str(adata.obs[col].dtype),
                        "unique_count": int(adata.obs[col].nunique()),
                    }
                except Exception:
                    pass
            result["obs_summary"] = sample_cols

            # If the target all_celltype column exists, give a preview.
            if "all_celltype" in obs_cols:
                try:
                    result["all_celltype_counts"] = (
                        adata.obs["all_celltype"].value_counts().head(10).to_dict()
                    )
                except Exception:
                    pass

            # Guess whether X is raw counts or normalized.
            try:
                x_max = float(adata.X[:1000].max()) if adata.n_obs > 0 else 0.0
                result["x_approx_max"] = x_max
            except Exception:
                result["x_approx_max"] = None

            return result
        finally:
            try:
                adata.file.close()
            except Exception:
                pass

    async def _llm_decide(
        self,
        user_request: str,
        intent_type: str,
        metadatas: List[Dict[str, Any]],
        target_column: Optional[str],
        target_exists: bool,
    ) -> PreflightResult:
        """Ask the LLM to decide the minimal workflow."""
        prompt = f"""You are a bioinformatics workflow planner. Given the user request and the metadata of the referenced file(s), decide the minimal steps actually required.

User request: {user_request}
Intent type: {intent_type}
Target comparison column: {target_column or 'none'}
Target column exists in .obs: {target_exists}

File metadata:
{json.dumps(metadatas, ensure_ascii=False, indent=2, default=str)}

Return ONLY a JSON object with this schema:
{{
  "data_notes": "short description of the data and what it already contains",
  "skip_phases": ["qc", "normalization", "dim_reduction", "clustering", ...],
  "required_steps": ["load data", "run celltypist", "compare labels", "summarize"],
  "suggested_input_layer": "counts" or "X" or null,
  "raw_counts_layer": "counts" or null,
  "needs_qc": bool,
  "needs_normalization": bool,
  "needs_clustering": bool,
  "needs_annotation": bool
}}

Rules:
- If the user explicitly asks for annotation only (e.g. CellTypist), skip qc/normalization/dim_reduction/clustering. CellTypist can normalize internally or accept log1p-normalized data.
- If the user asks for descriptive statistics, skip all analysis phases.
- If the user asks for clustering, normalization and dim_reduction are needed only if not already present.
- If the data already has a normalized layer (e.g. "log1p", "normalized") or .X looks normalized, do not force re-normalization.
- If the target comparison column exists, include a comparison step.
"""
        response = await self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You output only valid JSON. Do not include explanations outside the JSON object."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        data = self._parse_json_response(response)
        return PreflightResult(
            data_notes=data.get("data_notes", ""),
            skip_phases=data.get("skip_phases", []),
            required_steps=data.get("required_steps", []),
            suggested_input_layer=data.get("suggested_input_layer"),
            raw_counts_layer=data.get("raw_counts_layer"),
            needs_qc=bool(data.get("needs_qc", False)),
            needs_normalization=bool(data.get("needs_normalization", False)),
            needs_clustering=bool(data.get("needs_clustering", False)),
            needs_annotation=bool(data.get("needs_annotation", False)),
        )

    def _heuristic_decide(
        self,
        user_request: str,
        intent_type: str,
        metadatas: List[Dict[str, Any]],
        target_column: Optional[str],
        target_exists: bool,
    ) -> PreflightResult:
        """Rule-based fallback when no LLM is available."""
        lowered = (user_request or "").lower()
        first = metadatas[0] if metadatas else {}
        layers = first.get("layers", [])
        x_max = first.get("x_approx_max")

        has_normalized_layer = any(
            name in layers
            for name in ("log1p", "normalized", "norm", "data", "scvi_normalized")
        )
        looks_normalized = x_max is not None and x_max < 100

        skip: List[str] = []
        required: List[str] = ["inspect input data"]

        # Descriptive stats / overview.
        if "describe" in lowered or "描述性统计" in lowered or "统计" in lowered:
            return PreflightResult(
                data_notes="User asked for descriptive statistics; no analysis pipeline needed.",
                skip_phases=[
                    "qc",
                    "doublet_removal",
                    "normalization",
                    "batch_integration",
                    "dim_reduction",
                    "clustering",
                    "annotation",
                ],
                required_steps=["load data", "compute descriptive statistics", "summarize"],
                suggested_input_layer="X",
            )

        # Annotation-only tasks (CellTypist, SingleR, etc.).
        if any(k in lowered for k in ("annotat", "celltypist", "singler", "sctype", "注释")):
            skip = ["qc", "doublet_removal", "dim_reduction", "clustering"]
            required.extend(["prepare input", "run annotation"])
            if not has_normalized_layer and not looks_normalized:
                required.insert(1, "normalize counts")
            else:
                skip.append("normalization")
            if target_exists:
                required.append("compare predictions with existing labels")
            required.append("summarize results")
            return PreflightResult(
                data_notes="Annotation-only request; use the selected method on available data.",
                skip_phases=skip,
                required_steps=required,
                suggested_input_layer="X" if has_normalized_layer or looks_normalized else "counts",
                raw_counts_layer="counts" if "counts" in layers else None,
                needs_annotation=True,
            )

        # Clustering tasks.
        if any(k in lowered for k in ("cluster", "聚类", "louvain", "leiden", "umap")):
            required.extend(["normalize", "dimensionality reduction", "cluster"])
            if has_normalized_layer or looks_normalized:
                skip.append("normalization")
            skip.extend(["qc", "doublet_removal"])
            return PreflightResult(
                data_notes="Clustering request; needs normalization+PCA+clustering unless already present.",
                skip_phases=skip,
                required_steps=required,
                suggested_input_layer="X" if has_normalized_layer or looks_normalized else "counts",
                needs_normalization=not (has_normalized_layer or looks_normalized),
                needs_clustering=True,
            )

        # Generic default: assume a minimal pipeline.
        required.extend(["run requested analysis"])
        return PreflightResult(
            data_notes="Generic request; keep minimal analysis steps.",
            skip_phases=["qc", "doublet_removal", "batch_integration"],
            required_steps=required,
            suggested_input_layer="X",
        )


def resolve_preflight_file_paths(project_id: str, user_request: str) -> List[str]:
    """Find file paths referenced in the user request for a project."""
    import re

    candidates = re.findall(r"[\w\-\.]+\.\w{2,8}", user_request or "")
    seen: set = set()
    resolved: List[str] = []
    for candidate in candidates:
        filename = Path(candidate).name
        if not filename or filename in seen:
            continue
        seen.add(filename)
        for base in (
            settings.data_dir / "raw" / project_id,
            settings.data_dir / "workspaces" / project_id / "data",
        ):
            p = base / filename
            if p.is_file():
                resolved.append(str(p.resolve()))
                break
    return resolved
