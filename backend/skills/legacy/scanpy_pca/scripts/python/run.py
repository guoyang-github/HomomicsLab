"""Legacy stub: run PCA on single-cell data."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    adata_path = skill_inputs["adata_path"]
    n_comps = skill_inputs.get("n_comps", 50)
    return {
        "output_path": adata_path.replace(".h5ad", "_pca.h5ad"),
        "n_comps": n_comps,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
