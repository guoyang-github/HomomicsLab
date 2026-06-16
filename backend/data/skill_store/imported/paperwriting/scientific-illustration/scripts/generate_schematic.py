#!/usr/bin/env python3
"""
Generate scientific schematics with auto-detected backend.

NOTE: This script is ONE of four paths in the scientific-illustration skill.
For zero-configuration publication-quality diagrams, consider Code-Based paths
(NetworkX/Matplotlib/Schemdraw) documented in SKILL.md Part 3.

Three backends are tried in order:
1. API      - External image generation API (if config + key available)
2. Graphviz - Local structured diagram generation (if graphviz installed).
              LIMITATION: only linear chain diagrams. No branching.
3. Spec     - Fallback: generate task specification JSON for LLM/agent

Usage:
    python generate_schematic.py "diagram description" -o output.png
    python generate_schematic.py "CONSORT flowchart" -o figures/consort.png --doc-type journal
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate scientific schematics (auto-detects best backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backends (auto-selected):
  api      - External AI API (requires config/ai_models.json + API key env var)
  graphviz - Local structured diagrams (requires graphviz installed).
             LIMITATION: only simple linear chains. Use NetworkX/Matplotlib for branching diagrams.
  spec     - Generate task spec JSON (fallback, no dependencies)

For zero-configuration publication-quality diagrams, see SKILL.md Part 3:
  Code-Based paths: NetworkX, Matplotlib, Schemdraw (no API keys needed)

Document Types (quality thresholds):
  journal      8.5/10  - Nature, Science, peer-reviewed journals
  conference   8.0/10  - Conference papers
  thesis       8.0/10  - Dissertations, theses
  grant        8.0/10  - Grant proposals
  preprint     7.5/10  - arXiv, bioRxiv, etc.
  report       7.5/10  - Technical reports
  poster       7.0/10  - Academic posters
  presentation 6.5/10  - Slides, talks
  default      7.5/10  - General purpose

Examples:
  python generate_schematic.py "CONSORT participant flow" -o figures/consort.png --doc-type journal
  python generate_schematic.py "Transformer architecture" -o figures/transformer.png --doc-type poster
  python generate_schematic.py "System block diagram" -o figures/system.png -v
        """
    )

    parser.add_argument("prompt", help="Description of the diagram to generate")
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    parser.add_argument("--doc-type", default="default",
                        choices=["journal", "conference", "poster", "presentation",
                                 "report", "grant", "thesis", "preprint", "default"],
                        help="Document type for quality context (default: default)")
    parser.add_argument("--iterations", type=int, default=1,
                        help="Max generation attempts (default: 1, max: 2)")
    parser.add_argument("--mode", choices=["auto", "api", "graphviz", "spec"],
                        default="auto", help="Force specific backend (default: auto-detect)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_path = Path(args.output)

    from backends import detect_backend
    from backends.api import APIBackend
    from backends.graphviz import GraphvizBackend
    from backends.spec import SpecBackend

    # Select backend
    if args.mode == "auto":
        backend = detect_backend(script_dir)
    elif args.mode == "api":
        backend = APIBackend(script_dir)
    elif args.mode == "graphviz":
        backend = GraphvizBackend(script_dir)
    else:
        backend = SpecBackend(script_dir)

    # Notify user of backend selection (even without -v for transparency)
    if not args.verbose and backend.name != "api":
        print(f"[INFO] Using '{backend.name}' backend")
    if args.verbose:
        print(f"Using backend: {backend.name}")

    # Generate
    iterations = min(max(args.iterations, 1), 2)
    result = backend.generate(
        prompt=args.prompt,
        output_path=output_path,
        doc_type=args.doc_type,
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
            doc_type=args.doc_type,
            iterations=iterations,
            verbose=args.verbose
        )

    if result.get("success"):
        if backend.name == "spec":
            print(f"\n[INFO] {result['message']}")
            print(f"Spec file: {result['spec_path']}")
            sys.exit(0)
        else:
            print(f"\nSuccess! Image saved to: {output_path}")
            if args.verbose:
                print(f"Backend: {result.get('mode')}")
                if "diagram_type" in result:
                    print(f"Diagram type: {result['diagram_type']}")
            sys.exit(0)
    else:
        print(f"\nGeneration failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
