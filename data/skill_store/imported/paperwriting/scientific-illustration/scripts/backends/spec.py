"""
Fallback spec backend: generates a structured task specification JSON
when no image generation backend (API or local) is available.

The spec file can be read by the calling LLM/agent to generate the image
using its own capabilities, or by a human for manual processing.
"""

import json
from pathlib import Path
from typing import Any, Dict

from . import Backend, _load_ai_config


class SpecBackend(Backend):
    """Generate a task specification JSON as fallback."""

    name = "spec"

    # Scientific diagram guidelines included in spec for LLM reference
    GUIDELINES = """
Scientific Diagram Requirements:
- Clean white or light background, no textures
- High contrast, publication-ready quality
- Clear sans-serif fonts (Helvetica/Arial style), min 10pt
- Colorblind-friendly colors (Okabe-Ito palette)
- Logical flow (left-to-right or top-to-bottom)
- No figure numbers or captions inside the image
- Redundant encoding (shapes + colors)
- Adequate spacing, no overlapping elements
"""

    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self.config = _load_ai_config(script_dir)

    def generate(self, prompt: str, output_path: Path, doc_type: str = "default",
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        threshold = self.config.get("quality_thresholds", {}).get(doc_type.lower(), 7.5)

        optimized_prompt = f"""{self.GUIDELINES}

Create a publication-quality scientific diagram for the following request:

{prompt}

Document type: {doc_type} (quality threshold: {threshold}/10)
"""

        spec = {
            "task_type": "generate_schematic",
            "original_prompt": prompt,
            "optimized_prompt": optimized_prompt.strip(),
            "doc_type": doc_type,
            "quality_threshold": threshold,
            "guidelines": self.GUIDELINES.strip(),
            "suggested_backend": "llm_native",
            "output_path": str(output_path),
            "note": (
                "No image generation backend is available in this environment. "
                "Please use an LLM with image generation capabilities to create the image "
                "using the optimized_prompt above, then save it to output_path."
            )
        }

        spec_path = output_path.parent / f"{output_path.stem}_spec.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"[Spec] No image backend available. Generated spec: {spec_path}")

        return {
            "success": True,
            "mode": "spec",
            "spec_path": str(spec_path),
            "output_path": str(output_path),
            "message": (
                f"No image generation backend available. "
                f"Generated task specification at {spec_path}. "
                f"Please use an LLM with image generation capabilities to create the image, "
                f"then save it to {output_path}."
            )
        }
