from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


SCANPY_CLUSTER_SKILL = SkillDefinition(
    id="scanpy_cluster",
    name="Scanpy Clustering",
    version="1.0.0",
    category="single_cell_analysis",
    description="Cluster single-cell data with UMAP",
    input_schema=SkillInputSchema(
        type="object",
        properties={
            "adata_path": {"type": "string"},
            "n_neighbors": {"type": "integer", "default": 15},
            "resolution": {"type": "number", "default": 0.8},
            "n_pcs": {"type": "integer", "default": 30},
        },
        required=["adata_path"],
    ),
)


SCANPY_CLUSTER_CODE = '''
# Mock clustering for MVP
result = {
    "n_clusters": 8,
    "n_neighbors": n_neighbors,
    "resolution": resolution,
    "n_pcs": n_pcs,
    "output_path": adata_path.replace(".h5ad", "_clustered.h5ad"),
}
'''
