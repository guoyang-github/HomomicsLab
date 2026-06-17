"""
External API backend for scientific schematic generation.

Uses configured image generation model (default: Gemini 2.0 Flash via OpenRouter)
to generate images from text prompts.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import Backend, _load_ai_config, _get_env_key_name


def _load_env_file():
    """Load .env file from current directory or parent directories."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        return True
    cwd = Path.cwd()
    for _ in range(5):
        env_path = cwd / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            return True
        cwd = cwd.parent
        if cwd == cwd.parent:
            break
    script_dir = Path(__file__).resolve().parent.parent
    for _ in range(5):
        env_path = script_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            return True
        script_dir = script_dir.parent
        if script_dir == script_dir.parent:
            break
    return False


class APIBackend(Backend):
    """Generate images using an external image generation API."""

    name = "api"

    # Scientific diagram best practices prompt template
    SCIENTIFIC_DIAGRAM_GUIDELINES = """
Create a high-quality scientific diagram with these requirements:

VISUAL QUALITY:
- Clean white or light background (no textures or gradients)
- High contrast for readability and printing
- Professional, publication-ready appearance
- Sharp, clear lines and text
- Adequate spacing between elements to prevent crowding

TYPOGRAPHY:
- Clear, readable sans-serif fonts (Arial, Helvetica style)
- Minimum 10pt font size for all labels
- Consistent font sizes throughout
- All text horizontal or clearly readable
- No overlapping text

SCIENTIFIC STANDARDS:
- Accurate representation of concepts
- Clear labels for all components
- Include scale bars, legends, or axes where appropriate
- Use standard scientific notation and symbols
- Include units where applicable

ACCESSIBILITY:
- Colorblind-friendly color palette (use Okabe-Ito colors if using color)
- High contrast between elements
- Redundant encoding (shapes + colors, not just colors)
- Works well in grayscale

LAYOUT:
- Logical flow (left-to-right or top-to-bottom)
- Clear visual hierarchy
- Balanced composition
- Appropriate use of whitespace
- No clutter or unnecessary decorative elements

IMPORTANT - NO FIGURE NUMBERS:
- Do NOT include "Figure 1:", "Fig. 1", or any figure numbering in the image
- Do NOT add captions or titles like "Figure: ..." at the top or bottom
- Figure numbers and captions are added separately in the document/LaTeX
- The diagram should contain only the visual content itself
"""

    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self.config = _load_ai_config(script_dir)
        self.base_url = self.config.get("base_url", "https://openrouter.ai/api/v1")
        self.image_model = self.config.get("image_generation_model", "google/gemini-2.0-flash-exp:free")
        self.auth_type = self.config.get("auth_type", "bearer")
        self.request_timeout = self.config.get("request_timeout", 120)
        env_key_name = self.config.get("env_key_name", "OPENROUTER_API_KEY")

        self.api_key = os.getenv(env_key_name)
        if not self.api_key:
            _load_env_file()
            self.api_key = os.getenv(env_key_name)

        if not self.api_key:
            raise ValueError(f"{env_key_name} not found.")

        try:
            import requests
            self._requests = requests
        except ImportError:
            raise ImportError("requests library required for API backend. Install: pip install requests")

    def _log(self, message: str, verbose: bool):
        if verbose:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _make_request(self, model: str, messages: List[Dict[str, Any]],
                     modalities: Optional[List[str]] = None) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.auth_type == "api_key":
            headers["api-key"] = self.api_key

        headers.setdefault("HTTP-Referer", "https://localhost")
        headers.setdefault("X-Title", "Scientific Schematic Generator")

        payload = {"model": model, "messages": messages}
        if modalities:
            payload["modalities"] = modalities

        response = self._requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.request_timeout
        )

        try:
            response_json = response.json()
        except json.JSONDecodeError:
            response_json = {"raw_text": response.text[:500]}

        if response.status_code != 200:
            error_detail = response_json.get("error", response_json)
            raise RuntimeError(f"API request failed (HTTP {response.status_code}): {error_detail}")

        return response_json

    def _extract_image(self, response: Dict[str, Any], verbose: bool) -> Optional[bytes]:
        try:
            choices = response.get("choices", [])
            if not choices:
                self._log("No choices in response", verbose)
                return None

            message = choices[0].get("message", {})

            # Some models return images in 'images' field
            images = message.get("images", [])
            if images:
                first = images[0]
                if isinstance(first, dict) and first.get("type") == "image_url":
                    url = first.get("image_url", {})
                    if isinstance(url, dict):
                        url = url.get("url", "")
                    if url and url.startswith("data:image") and "," in url:
                        b64 = url.split(",", 1)[1].replace("\n", "").replace("\r", "").replace(" ", "")
                        return base64.b64decode(b64)

            # Fallback: check content field
            content = message.get("content", "")
            if isinstance(content, str) and "data:image" in content:
                import re
                match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=\n\r]+)', content, re.DOTALL)
                if match:
                    b64 = match.group(1).replace("\n", "").replace("\r", "").replace(" ", "")
                    return base64.b64decode(b64)

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        url = block.get("image_url", {})
                        if isinstance(url, dict):
                            url = url.get("url", "")
                        if url and url.startswith("data:image") and "," in url:
                            b64 = url.split(",", 1)[1].replace("\n", "").replace("\r", "").replace(" ", "")
                            return base64.b64decode(b64)

            return None
        except Exception as e:
            self._log(f"Error extracting image: {e}", verbose)
            return None

    def generate(self, prompt: str, output_path: Path, doc_type: str = "default",
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        iterations = min(max(iterations, 1), 2)

        full_prompt = f"""{self.SCIENTIFIC_DIAGRAM_GUIDELINES}

USER REQUEST: {prompt}

Generate a publication-quality scientific diagram that meets all the guidelines above."""

        self._log(f"Using API backend (model: {self.image_model})", verbose)

        for i in range(1, iterations + 1):
            self._log(f"Generation attempt {i}/{iterations}", verbose)
            try:
                response = self._make_request(
                    model=self.image_model,
                    messages=[{"role": "user", "content": full_prompt}],
                    modalities=["image", "text"]
                )

                if "error" in response:
                    error_msg = response["error"]
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(error_msg))
                    return {
                        "success": False,
                        "error": f"API Error: {error_msg}",
                        "mode": "api"
                    }

                image_data = self._extract_image(response, verbose)
                if not image_data:
                    return {
                        "success": False,
                        "error": "No image data in API response",
                        "mode": "api"
                    }

                with open(output_path, "wb") as f:
                    f.write(image_data)

                return {
                    "success": True,
                    "final_image": str(output_path),
                    "mode": "api",
                    "iterations_used": i
                }

            except Exception as e:
                self._log(f"Generation failed: {e}", verbose)
                if i == iterations:
                    return {
                        "success": False,
                        "error": str(e),
                        "mode": "api"
                    }

        return {"success": False, "error": "Max iterations reached without success", "mode": "api"}
