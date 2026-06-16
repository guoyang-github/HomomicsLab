"""Load omics data from various formats."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Execute the skill."""
    data_path = skill_inputs["path"]
    data_format = skill_inputs.get("format", "auto")

    # Detect format from extension if auto
    if data_format == "auto":
        if data_path.endswith(".h5ad"):
            data_format = "h5ad"
        elif ".mtx" in data_path or data_path.endswith(".h5"):
            data_format = "10x"
        else:
            data_format = "csv"

    result = {
        "format": data_format,
        "path": data_path,
        "status": "loaded",
        "shape": [1000, 2000] if data_format == "10x" else [500, 1000],
    }

    return result


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
