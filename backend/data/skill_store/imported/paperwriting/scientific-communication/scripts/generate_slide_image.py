#!/usr/bin/env python3
"""
Generate presentation slides or visuals with auto-detected backend.

Three backends are tried in order:
1. API    - External image generation API (if config + key available)
2. PPTX   - Local PowerPoint generation (if python-pptx installed)
3. Spec   - Fallback: generate task specification JSON for LLM/agent

Usage:
    # Full slide (default)
    python generate_slide_image.py "Title: Introduction\nKey points: AI, ML" -o slides/01.pptx

    # Visual only
    python generate_slide_image.py "Neural network diagram" -o figure.png --visual-only
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate presentation slides or visuals (auto-detects best backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backends (auto-selected):
  api   - External AI API (requires config/ai_models.json + API key env var)
  pptx  - Local PowerPoint slides (requires python-pptx)
  spec  - Generate task spec JSON (fallback, no dependencies)

Examples:
  # Full slide
  python generate_slide_image.py "Title: Introduction to ML" -o slides/01.pptx

  # Visual only (for PPT workflow)
  python generate_slide_image.py "Neural network diagram" -o figure.png --visual-only

  # Force specific backend
  python generate_slide_image.py "Title slide" -o title.pptx --mode pptx
        """
    )

    parser.add_argument("prompt", help="Description of the slide or visual to generate")
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    parser.add_argument("--visual-only", action="store_true",
                        help="Generate just the visual/figure (for PPT workflow)")
    parser.add_argument("--iterations", type=int, default=1,
                        help="Max generation attempts (default: 1, max: 2)")
    parser.add_argument("--mode", choices=["auto", "api", "pptx", "spec"],
                        default="auto", help="Force specific backend (default: auto-detect)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_path = Path(args.output)

    from backends import detect_backend
    from backends.api import APIBackend
    from backends.pptx import PPTXBackend
    from backends.spec import SpecBackend

    # Select backend
    if args.mode == "auto":
        backend = detect_backend(script_dir)
    elif args.mode == "api":
        backend = APIBackend(script_dir)
    elif args.mode == "pptx":
        backend = PPTXBackend(script_dir)
    else:
        backend = SpecBackend(script_dir)

    # Notify user of backend selection (even without -v for transparency)
    if not args.verbose and backend.name != "api":
        print(f"[INFO] Using '{backend.name}' backend")
    if args.verbose:
        print(f"Using backend: {backend.name}")

    iterations = min(max(args.iterations, 1), 2)
    result = backend.generate(
        prompt=args.prompt,
        output_path=output_path,
        visual_only=args.visual_only,
        iterations=iterations,
        verbose=args.verbose
    )

    # Auto-fallback: if a non-spec backend fails with fallback_to_spec flag,
    # automatically try the spec backend
    if not result.get("success") and args.mode == "auto" and backend.name != "spec" and result.get("fallback_to_spec"):
        print(f"[INFO] {backend.name} backend could not handle this request, falling back to spec")
        backend = SpecBackend(script_dir)
        result = backend.generate(
            prompt=args.prompt,
            output_path=output_path,
            visual_only=args.visual_only,
            iterations=iterations,
            verbose=args.verbose
        )

    if result.get("success"):
        if backend.name == "spec":
            print(f"\n[INFO] {result['message']}")
            print(f"Spec file: {result['spec_path']}")
            sys.exit(0)
        else:
            print(f"\nSuccess! Output saved to: {result['final_image']}")
            if args.verbose:
                print(f"Backend: {result.get('mode')}")
            sys.exit(0)
    else:
        print(f"\nGeneration failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
