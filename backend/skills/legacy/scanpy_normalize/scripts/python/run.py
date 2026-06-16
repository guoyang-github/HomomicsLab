"""Legacy stub: normalize single-cell counts."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    adata_path = skill_inputs["adata_path"]
    target_sum = skill_inputs.get("target_sum", 10000)
    return {
        "output_path": adata_path.replace(".h5ad", "_normalized.h5ad"),
        "target_sum": target_sum,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
