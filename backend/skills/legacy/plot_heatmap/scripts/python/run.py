"""Legacy stub: plot heatmap."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    adata_path = skill_inputs["adata_path"]
    markers = skill_inputs.get("markers", [])
    return {
        "output_path": adata_path.replace(".h5ad", "_heatmap.png"),
        "markers": markers,
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
