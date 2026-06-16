"""Legacy stub: differential expression analysis."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    adata_path = skill_inputs["adata_path"]
    groupby = skill_inputs.get("groupby", "leiden")
    return {
        "output_path": adata_path.replace(".h5ad", "_de.csv"),
        "groupby": groupby,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
