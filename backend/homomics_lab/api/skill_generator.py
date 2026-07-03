"""API endpoints for skill generation."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homomics_lab.skills.generator.generator import SkillGenerator

router = APIRouter()


class GenerateSkillRequest(BaseModel):
    name: str
    description: str
    category: str = "custom"
    tool_type: str = "python"
    primary_tool: str = ""
    supported_tools: List[str] = []
    keywords: List[str] = []
    inputs: List[Dict[str, Any]] = []
    outputs: List[str] = []
    dependencies: List[str] = []
    save_to_disk: bool = False


class SuggestSkillRequest(BaseModel):
    description: str


class GeneratedSkillResponse(BaseModel):
    skill_id: str
    files: Dict[str, str]
    saved_path: Optional[str] = None


class SuggestedSkillResponse(BaseModel):
    tool_type: str
    category: str
    keywords: str


class ScriptTemplateResponse(BaseModel):
    tool_type: str
    template: str


@router.post("/generate", response_model=GeneratedSkillResponse)
async def generate_skill(request: GenerateSkillRequest):
    """Generate a new skill from requirements."""
    try:
        generator = SkillGenerator()
        files = generator.generate(
            name=request.name,
            description=request.description,
            category=request.category,
            tool_type=request.tool_type,
            primary_tool=request.primary_tool,
            supported_tools=request.supported_tools,
            keywords=request.keywords,
            inputs=request.inputs,
            outputs=request.outputs,
            dependencies=request.dependencies,
        )

        saved_path = None
        if request.save_to_disk:
            base_dir = generator.save(files)
            saved_path = str(base_dir)

        skill_id = generator._normalize_name(request.name)
        return GeneratedSkillResponse(
            skill_id=skill_id,
            files=files,
            saved_path=saved_path,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill generation failed: {str(e)}")


@router.post("/suggest", response_model=SuggestedSkillResponse)
async def suggest_skill(request: SuggestSkillRequest):
    """Suggest skill parameters from a natural language description."""
    generator = SkillGenerator()
    suggestions = generator.suggest_from_description(request.description)
    return SuggestedSkillResponse(**suggestions)


@router.get("/templates/{tool_type}", response_model=ScriptTemplateResponse)
async def get_script_template(tool_type: str):
    """Get a script template for a given tool type."""
    from homomics_lab.skills.generator.templates import SkillTemplateBuilder

    builder = SkillTemplateBuilder()

    if tool_type == "python":
        template = builder.build_python_script(
            name="example-skill",
            description="Example skill description",
            inputs=[{"name": "input_file", "description": "Input data file"}],
            outputs=["output_file"],
        )
    elif tool_type == "r":
        template = builder.build_r_script(
            name="example-skill",
            description="Example skill description",
            inputs=[{"name": "input_file", "description": "Input data file"}],
            outputs=["output_file"],
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported tool type: {tool_type}")

    return {"tool_type": tool_type, "template": template}
