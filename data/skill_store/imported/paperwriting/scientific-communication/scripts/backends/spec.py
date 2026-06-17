"""
Fallback spec backend: generates a structured task specification JSON
when no image generation backend (API or local) is available.
"""

import json
from pathlib import Path
from typing import Any, Dict

from . import Backend, _load_ai_config


class SpecBackend(Backend):
    """Generate a task specification JSON as fallback."""

    name = "spec"

    FULL_SLIDE_GUIDELINES = """
Presentation Slide Requirements:
- 16:9 aspect ratio, clean modern design
- Clear visual hierarchy: large bold title at top, content below
- Generous margins (at least 5% on all sides)
- Bullet points or key phrases, NOT paragraphs
- Maximum 5-6 lines of text content
- High contrast text for projection readability
- Consistent color scheme (2-3 main colors only)
- Professional, minimal aesthetic
- No cluttered or busy layouts
"""

    VISUAL_GUIDELINES = """
Visual/Figure Requirements:
- Clean, professional appearance
- Simple, clear composition with minimal elements
- High contrast for projection readability
- No text unless essential to the visual
- Transparent or white background preferred
- Colorblind-friendly colors
- Suitable for embedding in a slide
"""

    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self.config = _load_ai_config(script_dir)

    def generate(self, prompt: str, output_path: Path, visual_only: bool = False,
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        threshold = self.config.get("quality_threshold", 6.5)
        guidelines = self.VISUAL_GUIDELINES if visual_only else self.FULL_SLIDE_GUIDELINES
        mode_label = "visual/figure" if visual_only else "presentation slide"

        optimized_prompt = f"""{guidelines}

Create a high-quality {mode_label} for the following request:

{prompt}

Quality threshold: {threshold}/10
"""

        spec = {
            "task_type": "generate_slide" if not visual_only else "generate_visual",
            "original_prompt": prompt,
            "optimized_prompt": optimized_prompt.strip(),
            "mode": "visual_only" if visual_only else "full_slide",
            "quality_threshold": threshold,
            "guidelines": guidelines.strip(),
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
