from homics_lab.skills.models import SkillDefinition, SkillInputSchema


SCANPY_QC_SKILL = SkillDefinition(
    id="scanpy_qc",
    name="Scanpy Quality Control",
    version="1.0.0",
    category="single_cell_analysis",
    description="Perform QC filtering on single-cell data",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "adata_path": {"type": "string"},
            "min_genes": {"type": "integer", "default": 200},
            "min_cells": {"type": "integer", "default": 3},
            "mt_threshold": {"type": "number", "default": 0.05},
        },
        required=["adata_path"],
    ),
)


SCANPY_QC_CODE = '''
# Mock QC for MVP
result = {
    "input_cells": 2700,
    "output_cells": 2531,
    "input_genes": 32738,
    "output_genes": 13714,
    "min_genes": min_genes,
    "min_cells": min_cells,
    "mt_threshold": mt_threshold,
    "output_path": adata_path.replace(".h5ad", "_qc.h5ad"),
}
'''
