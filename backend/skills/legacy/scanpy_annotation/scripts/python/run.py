"""Legacy stub: annotate single-cell clusters."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    adata_path = skill_inputs["adata_path"]
    method = skill_inputs.get("method", "markers")
    return {
        "output_path": adata_path.replace(".h5ad", "_annotated.h5ad"),
        "method": method,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
