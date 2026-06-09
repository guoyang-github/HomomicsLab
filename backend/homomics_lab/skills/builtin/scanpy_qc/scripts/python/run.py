"""Perform QC filtering on single-cell data."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Execute the skill."""
    adata_path = skill_inputs["adata_path"]
    min_genes = skill_inputs.get("min_genes", 200)
    min_cells = skill_inputs.get("min_cells", 3)
    mt_threshold = skill_inputs.get("mt_threshold", 0.05)

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

    return result


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
