from typing import Any, Dict, List, Optional

import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from homomics_lab.config import settings
from homomics_lab.viz.generator import PlotGenerator, PlotType
from homomics_lab.viz.plotly_adapter import to_plotly_json
from homomics_lab.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

router = APIRouter()

SKILL_ID = "bio-statistics-visualization"


class PlotRequest(BaseModel):
    plot_type: PlotType
    data: Dict[str, Any]
    title: str = ""
    width: int = 8
    height: int = 6
    dpi: int = 100


class PlotResponse(BaseModel):
    image_base64: str
    plot_type: str
    title: str


class PlotDataRequest(BaseModel):
    plot_type: PlotType
    data: Dict[str, Any]
    title: str = ""
    width: int = 800
    height: int = 600


class PlotDataResponse(BaseModel):
    data: list
    layout: dict
    plot_type: str


class CreateVizSessionRequest(BaseModel):
    project_id: str
    source_filename: str
    table_type_hint: str | None = None


class RenderRequest(BaseModel):
    project_id: str
    action: str
    params: Dict[str, Any]


class PlotTypeInfo(BaseModel):
    type: str
    description: str


@router.post("/plot", response_model=PlotResponse)
async def generate_plot(request: PlotRequest):
    """Generate a bioinformatics plot and return as base64 PNG."""
    try:
        generator = PlotGenerator()
        image_base64 = generator.generate(
            plot_type=request.plot_type,
            data=request.data,
            title=request.title,
            width=request.width,
            height=request.height,
            dpi=request.dpi,
        )
        return PlotResponse(
            image_base64=image_base64,
            plot_type=request.plot_type.value,
            title=request.title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Plot generation failed (plot_type=%s)", request.plot_type)
        raise HTTPException(status_code=500, detail="Internal error") from e


@router.post("/plot-data", response_model=PlotDataResponse)
async def generate_plot_data(request: PlotDataRequest):
    """Generate Plotly-compatible JSON data for interactive frontend rendering.

    Returns structured data that react-plotly.js can render directly.
    """
    try:
        figure = to_plotly_json(
            plot_type=request.plot_type,
            data=request.data,
            title=request.title,
            width=request.width,
            height=request.height,
        )
        return PlotDataResponse(
            data=figure["data"],
            layout=figure["layout"],
            plot_type=request.plot_type.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Plot data generation failed (plot_type=%s)", request.plot_type)
        raise HTTPException(status_code=500, detail="Internal error") from e


@router.get("/plot/types", response_model=List[PlotTypeInfo])
async def list_plot_types():
    """List available plot types."""
    return [
        {"type": pt.value, "description": _get_plot_description(pt)}
        for pt in PlotType
    ]


def _get_plot_description(plot_type: PlotType) -> str:
    descriptions = {
        PlotType.UMAP: "UMAP dimensionality reduction scatter plot with cluster coloring",
        PlotType.HEATMAP: "Matrix heatmap with color scale",
        PlotType.VIOLIN: "Violin plot for distribution comparison across groups",
        PlotType.BAR: "Bar chart for categorical data",
        PlotType.SCATTER: "Scatter plot for x-y relationships",
        PlotType.HISTOGRAM: "Histogram for value distribution",
    }
    return descriptions.get(plot_type, "")


async def _execute_skill(
    skill_executor,
    action: str,
    project_id: str,
    session_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the bio-statistics-visualization skill with the given action."""
    skill = skill_executor.registry.get(SKILL_ID)
    if skill is None:
        raise HTTPException(
            status_code=500,
            detail=f"Skill '{SKILL_ID}' is not registered",
        )

    inputs = {
        "action": action,
        "project_id": project_id,
        "session_id": session_id,
        "params": params,
        "source_dir": str(skill.source_dir),
        "workspace_base": str(settings.data_dir),
    }
    return await skill_executor.execute(SKILL_ID, inputs)


def _register_artifacts(
    project_id: str,
    artifacts: list[dict],
    task_id: str,
    figure_id: str | None = None,
    formats: dict[str, str] | None = None,
):
    """Register skill artifacts with the project's WorkspaceManager."""
    ws = WorkspaceManager(settings.data_dir, project_id)
    for artifact in artifacts:
        path = artifact.get("path")
        if not path:
            continue
        artifact_type = artifact.get("type", "output")
        filename = artifact.get("relative_path") or Path(path).name
        metadata = {"mime": artifact.get("mime", "")}
        if figure_id and artifact_type == "output":
            metadata["kind"] = "figure"
            metadata["figure_id"] = figure_id
            if formats:
                metadata["formats"] = formats
        abs_path = ws.register_artifact(
            task_id=task_id,
            artifact_type=artifact_type,
            filename=filename,
            metadata=metadata,
        )
        # Copy artifact into the tracked workspace location if it isn't already there.
        if Path(path).resolve() != abs_path.resolve():
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(Path(path).read_bytes())
        ws.update_artifact_checksum(str(abs_path.relative_to(ws.workspace_dir)))


def _extract_vision_instruction(params: Dict[str, Any]) -> str:
    """Extract a plain-text instruction from vision edit params."""
    instruction = params.get("instruction", "")
    if not instruction:
        commands = params.get("commands", [])
        if isinstance(commands, list):
            instruction = " ".join(str(c) for c in commands)
    return str(instruction).strip()


async def _apply_vision_edit(
    llm_client: Optional[Any],
    instruction: str,
    current_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Use an LLM to turn a natural-language edit into structured overrides."""
    if not instruction:
        raise HTTPException(status_code=400, detail="Vision edit instruction is empty")

    params = dict(current_params)
    params.setdefault("overrides", {})
    params.setdefault("annotations", [])

    if llm_client is None or not getattr(llm_client, "is_configured", lambda: False)():
        # Fallback: keep the original params and let the skill apply rule-based edits.
        params["instruction"] = instruction
        return params

    system_prompt = (
        "You are a biomedical figure editing assistant. "
        "Convert the user's natural-language request into a JSON object with two keys: "
        "'overrides' (colors, labels, title, error_bar_style, legend_position) and "
        "'annotations' (list of {text, x1, x2, y?}). "
        "Only return valid JSON."
    )
    user_prompt = (
        f"Current plot: {current_params.get('plot_type', 'bar')} "
        f"theme={current_params.get('theme', 'generic')}, "
        f"groups={current_params.get('group_columns', [])}.\n"
        f"User request: {instruction}\n\n"
        "Return JSON:"
    )

    try:
        content = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = str(content)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            overrides = parsed.get("overrides") or {}
            annotations = parsed.get("annotations") or []
            if overrides:
                existing = params.get("overrides") or {}
                if isinstance(existing, dict):
                    params["overrides"] = {**existing, **overrides}
                else:
                    params["overrides"] = overrides
            if annotations:
                params["annotations"] = list(params.get("annotations", [])) + list(annotations)
        params["instruction"] = instruction
    except Exception as exc:
        # If LLM parsing fails, fall back to rule-based edit.
        params["instruction"] = instruction
        params.setdefault("_vision_edit_error", str(exc))

    return params


@router.post("/sessions", response_model=Dict[str, Any])
async def create_session(
    request: CreateVizSessionRequest,
    http_request: Request,
):
    """Create a visualization session: import and validate data."""
    skill_executor = getattr(http_request.app.state, "skill_executor", None)
    if skill_executor is None:
        raise HTTPException(status_code=500, detail="Skill executor not initialized")

    session_id = uuid.uuid4().hex[:12]
    result = await _execute_skill(
        skill_executor,
        action="import_data",
        project_id=request.project_id,
        session_id=session_id,
        params={
            "source": request.source_filename,
            "table_type": request.table_type_hint,
        },
    )

    if isinstance(result, dict) and result.get("success"):
        _register_artifacts(
            project_id=request.project_id,
            artifacts=result.get("artifacts", []),
            task_id=f"viz_{session_id}_import",
        )

    return {"session_id": session_id, **result}


@router.post("/sessions/{session_id}/render", response_model=Dict[str, Any])
async def render(
    session_id: str,
    request: RenderRequest,
    http_request: Request,
):
    """Execute statistical tests, render figures, or apply vision edits."""
    skill_executor = getattr(http_request.app.state, "skill_executor", None)
    if skill_executor is None:
        raise HTTPException(status_code=500, detail="Skill executor not initialized")

    if request.action not in {"stat_test", "render", "render_plotly", "render_multipanel", "vision_edit", "full_pipeline"}:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {request.action}")

    params = dict(request.params)
    action = request.action

    # LLM-driven vision edit: translate natural-language instruction into
    # structured overrides, then re-render the figure.
    if action == "vision_edit":
        llm_client = getattr(http_request.app.state, "llm_client", None)
        params = await _apply_vision_edit(
            llm_client=llm_client,
            instruction=_extract_vision_instruction(params),
            current_params=params,
        )
        action = "render"

    result = await _execute_skill(
        skill_executor,
        action=action,
        project_id=request.project_id,
        session_id=session_id,
        params=params,
    )

    if isinstance(result, dict) and result.get("success"):
        figure_id = result.get("outputs", {}).get("figure_id")
        format_paths = result.get("outputs", {}).get("formats", {})
        ws = WorkspaceManager(settings.data_dir, request.project_id)

        def _relative_to_workspace(path: str) -> str:
            p = Path(path)
            if not p.is_absolute():
                p = ws.workspace_dir / p
            return str(p.relative_to(ws.workspace_dir))

        formats = {
            fmt: _relative_to_workspace(path)
            for fmt, path in format_paths.items()
        }
        _register_artifacts(
            project_id=request.project_id,
            artifacts=result.get("artifacts", []),
            task_id=f"viz_{session_id}_{request.action}",
            figure_id=figure_id,
            formats=formats,
        )

    return result
