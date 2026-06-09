from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homomics_lab.viz.generator import PlotGenerator, PlotType

router = APIRouter()


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
        raise HTTPException(status_code=500, detail=f"Plot generation failed: {str(e)}")


@router.get("/plot/types")
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
