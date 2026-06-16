"""
External API backend for slide/visual generation.

Uses configured image generation model to generate slide images from text prompts.
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import Backend, _load_ai_config


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
    """Generate slide images using an external image generation API."""

    name = "api"

    FULL_SLIDE_GUIDELINES = """
Create a professional presentation slide image with these requirements:

SLIDE LAYOUT (16:9 aspect ratio):
- Clean, modern slide design
- Clear visual hierarchy: title at top, content below
- Generous margins (at least 5% on all sides)
- Balanced composition with intentional white space

TYPOGRAPHY:
- LARGE, bold title text (easily readable from distance)
- Clear, sans-serif fonts throughout
- High contrast text (dark on light or light on dark)
- Bullet points or key phrases, NOT paragraphs
- Maximum 5-6 lines of text content

VISUAL ELEMENTS:
- Use GENERIC, simple images and icons
- MINIMAL extra elements - no decorative borders or shadows
- Visuals should support the message, not distract
- Professional, clean aesthetic
- Consistent color scheme (2-3 main colors only)

PROFESSIONAL MINIMALISM:
- Less is more: favor empty space over additional elements
- No unnecessary decorations, gradients, or visual noise
- Clean lines and simple shapes
- Corporate/academic level of professionalism

PRESENTATION QUALITY:
- Designed for projection (high contrast)
- Bold, impactful design
- Professional and polished appearance
- No cluttered or busy layouts
"""

    VISUAL_ONLY_GUIDELINES = """
Create a high-quality visual/figure for a presentation slide:

IMAGE QUALITY:
- Clean, professional appearance
- High resolution and sharp details
- Suitable for embedding in a slide

DESIGN:
- Simple, clear composition with MINIMAL elements
- High contrast for projection readability
- No text unless essential to the visual
- Transparent or white background preferred

PROFESSIONAL MINIMALISM:
- Favor simplicity over complexity
- No decorative elements, shadows, or flourishes
- Clean lines and simple shapes only
- Abstract/conceptual rather than literal representations

STYLE:
- Modern, professional aesthetic
- Colorblind-friendly colors
- Bold but restrained imagery
- Suitable for scientific/professional presentations
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
        headers.setdefault("X-Title", "Scientific Slide Generator")

        payload = {"model": model, "messages": messages}
        if modalities:
            payload["modalities"] = modalities

        response = self._requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers, json=payload, timeout=self.request_timeout
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
                return None
            message = choices[0].get("message", {})
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

    def generate(self, prompt: str, output_path: Path, visual_only: bool = False,
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        iterations = min(max(iterations, 1), 2)

        guidelines = self.VISUAL_ONLY_GUIDELINES if visual_only else self.FULL_SLIDE_GUIDELINES
        full_prompt = f"""{guidelines}

USER REQUEST: {prompt}

Generate a high-quality {'visual/figure' if visual_only else 'presentation slide'} that meets all the guidelines above."""

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
                    return {"success": False, "error": f"API Error: {error_msg}", "mode": "api"}

                image_data = self._extract_image(response, verbose)
                if not image_data:
                    return {"success": False, "error": "No image data in API response", "mode": "api"}

                with open(output_path, "wb") as f:
                    f.write(image_data)

                return {"success": True, "final_image": str(output_path), "mode": "api", "iterations_used": i}
            except Exception as e:
                self._log(f"Generation failed: {e}", verbose)
                if i == iterations:
                    return {"success": False, "error": str(e), "mode": "api"}

        return {"success": False, "error": "Max iterations reached without success", "mode": "api"}
