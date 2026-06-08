from homics_lab.skills.models import SkillDefinition, SkillInputSchema


DATA_LOADER_SKILL = SkillDefinition(
    id="data_loader",
    name="Load Omics Data",
    version="1.0.0",
    category="data_io",
    description="Load omics data from various formats",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "format": {"type": "string", "default": "auto"},
            "path": {"type": "string"},
        },
        required=["path"],
    ),
)


DATA_LOADER_CODE = '''
# Mock data loader for MVP
import os

result = {
    "format": format,
    "path": adata_path if "adata_path" in locals() else path,
    "status": "loaded (mock)",
    "shape": [1000, 2000] if format == "10x" else [500, 1000],
}
'''
