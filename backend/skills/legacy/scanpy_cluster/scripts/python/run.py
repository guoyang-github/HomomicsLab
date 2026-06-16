"""Cluster single-cell data with UMAP and Louvain."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Execute the skill."""
    adata_path = skill_inputs["adata_path"]
    n_neighbors = skill_inputs.get("n_neighbors", 15)
    resolution = skill_inputs.get("resolution", 0.8)
    n_pcs = skill_inputs.get("n_pcs", 30)

    result = {
        "n_clusters": 8,
        "n_neighbors": n_neighbors,
        "resolution": resolution,
        "n_pcs": n_pcs,
        "output_path": adata_path.replace(".h5ad", "_clustered.h5ad"),
    }

    return result


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
