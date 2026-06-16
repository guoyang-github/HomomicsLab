"""
Local Graphviz backend for structured scientific diagrams.

Generates publication-ready diagrams using Graphviz DOT language.
Supports: flowcharts, hierarchies, networks, trees, block diagrams.

Requires: graphviz Python package + system graphviz binary
"""

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import Backend


DIAGRAM_TYPES = {
    "flowchart": ["flowchart", "流程图", "participant flow", "CONSORT", "PRISMA",
                  "flow", "workflow", "process", "procedure", "steps"],
    "hierarchy": ["architecture", "层次", "encoder", "decoder", "transformer",
                  "neural network", "stack", "layer", "cnn", "rnn", "attention",
                  "model", "pipeline", "stages"],
    "network": ["network", "pathway", "signaling", "相互作用", "interaction",
                "cascade", "relation", "connection", "topology", "graph"],
    "tree": ["tree", "decision tree", "phylogenetic", "taxonomy", "hierarchy tree",
             "classification", "clustering", "dendrogram"],
    "block": ["block diagram", "系统框图", "component", "module", "system",
              "block", "box", "io", "input", "output"],
}


class GraphvizBackend(Backend):
    """Generate structured diagrams using Graphviz DOT."""

    name = "graphviz"

    # Okabe-Ito colorblind-friendly palette
    COLORS = ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
              "#0072B2", "#D55E00", "#CC79A7", "#999999"]

    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self._check_graphviz()

    def _check_graphviz(self):
        import graphviz
        if shutil.which("dot") is None:
            raise RuntimeError("Graphviz system binary 'dot' not found. Install graphviz.")

    def _detect_type(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        scores = {}
        for dtype, keywords in DIAGRAM_TYPES.items():
            scores[dtype] = sum(1 for kw in keywords if kw.lower() in prompt_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "block"

    def _extract_nodes(self, prompt: str) -> List[str]:
        """Extract candidate node labels from prompt."""
        # Look for quoted strings, parenthetical labels, or capitalized phrases
        nodes = []

        # Quoted strings
        for match in re.finditer(r'"([^"]{2,40})"', prompt):
            nodes.append(match.group(1).strip())

        # Parenthetical labels like (n=500)
        for match in re.finditer(r'\b([A-Z][a-zA-Z\s]{1,30})(?:\s*\(|\s*→|\s*-\u003e|\s*to\s)', prompt):
            label = match.group(1).strip()
            if len(label) > 2 and label not in nodes:
                nodes.append(label)

        # After "to", "→", "-", "and" separators
        parts = re.split(r'(?:→|->|to|and|\n)', prompt)
        for p in parts:
            p = p.strip().strip('"').strip("'")
            if 2 <= len(p) <= 40 and p not in nodes:
                nodes.append(p)

        # Deduplicate and limit
        seen = set()
        result = []
        for n in nodes:
            key = n.lower()
            if key not in seen and len(result) < 20:
                seen.add(key)
                result.append(n)
        return result

    def _build_flowchart(self, nodes: List[str]) -> str:
        dot = ['digraph G {', '  rankdir=TB;', '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12];', '  edge [fontname="Helvetica", fontsize=10];', '']
        for i, node in enumerate(nodes):
            color = self.COLORS[i % len(self.COLORS)]
            escaped = node.replace('"', '\\"')
            dot.append(f'  n{i} [label="{escaped}", fillcolor="{color}"];')
        dot.append('')
        for i in range(len(nodes) - 1):
            dot.append(f'  n{i} -> n{i+1};')
        dot.append('}')
        return '\n'.join(dot)

    def _build_hierarchy(self, nodes: List[str]) -> str:
        dot = ['digraph G {', '  rankdir=TB;', '  node [shape=box, style="filled", fontname="Helvetica", fontsize=12];', '  edge [fontname="Helvetica", fontsize=10];', '']
        # First node at top, rest in layers
        for i, node in enumerate(nodes):
            color = self.COLORS[i % len(self.COLORS)]
            escaped = node.replace('"', '\\"')
            dot.append(f'  n{i} [label="{escaped}", fillcolor="{color}"];')
        dot.append('')
        # Connect each to next, and optionally skip connections for layers
        for i in range(len(nodes) - 1):
            dot.append(f'  n{i} -> n{i+1};')
        dot.append('}')
        return '\n'.join(dot)

    def _build_network(self, nodes: List[str]) -> str:
        dot = ['digraph G {', '  rankdir=LR;', '  node [shape=ellipse, style="filled", fontname="Helvetica", fontsize=12];', '  edge [fontname="Helvetica", fontsize=10];', '']
        for i, node in enumerate(nodes):
            color = self.COLORS[i % len(self.COLORS)]
            escaped = node.replace('"', '\\"')
            dot.append(f'  n{i} [label="{escaped}", fillcolor="{color}"];')
        dot.append('')
        # Chain connections
        for i in range(len(nodes) - 1):
            dot.append(f'  n{i} -> n{i+1} [arrowhead=vee];')
        dot.append('}')
        return '\n'.join(dot)

    def _build_tree(self, nodes: List[str]) -> str:
        dot = ['digraph G {', '  rankdir=TB;', '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12];', '  edge [fontname="Helvetica", fontsize=10];', '']
        for i, node in enumerate(nodes):
            color = self.COLORS[i % len(self.COLORS)]
            escaped = node.replace('"', '\\"')
            dot.append(f'  n{i} [label="{escaped}", fillcolor="{color}"];')
        dot.append('')
        for i in range(len(nodes) - 1):
            dot.append(f'  n{i} -> n{i+1};')
        dot.append('}')
        return '\n'.join(dot)

    def _build_block(self, nodes: List[str]) -> str:
        dot = ['digraph G {', '  rankdir=LR;', '  node [shape=box, style="filled", fontname="Helvetica", fontsize=12, margin="0.2,0.15"];', '  edge [fontname="Helvetica", fontsize=10];', '']
        for i, node in enumerate(nodes):
            color = self.COLORS[i % len(self.COLORS)]
            escaped = node.replace('"', '\\"')
            dot.append(f'  n{i} [label="{escaped}", fillcolor="{color}"];')
        dot.append('')
        for i in range(len(nodes) - 1):
            dot.append(f'  n{i} -> n{i+1} [arrowhead=open];')
        dot.append('}')
        return '\n'.join(dot)

    def generate(self, prompt: str, output_path: Path, doc_type: str = "default",
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        if doc_type != "default" and verbose:
            print(f"[Graphviz] Note: doc_type='{doc_type}' is ignored by the graphviz backend")
        if iterations > 1 and verbose:
            print(f"[Graphviz] Note: iterations={iterations} is ignored by the graphviz backend")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        diagram_type = self._detect_type(prompt)
        nodes = self._extract_nodes(prompt)

        # If we couldn't infer a meaningful diagram type or extract nodes,
        # this prompt is likely not suitable for structured Graphviz diagrams.
        if diagram_type == "block" and len(nodes) < 2:
            return {
                "success": False,
                "error": (
                    "Prompt does not match any supported structured diagram type. "
                    "Graphviz backend supports only simple linear diagrams: flowcharts, hierarchies, "
                    "networks, trees, block diagrams (all rendered as node chains). "
                    "For branching diagrams or precise control, use Code-Based paths (NetworkX/Matplotlib) "
                    "or LLM Native mode. See SKILL.md Part 3 for code examples."
                ),
                "mode": "graphviz",
                "fallback_to_spec": True
            }

        if not nodes:
            # Fallback: create a minimal diagram with the prompt as label
            nodes = [prompt[:40]]

        builders = {
            "flowchart": self._build_flowchart,
            "hierarchy": self._build_hierarchy,
            "network": self._build_network,
            "tree": self._build_tree,
            "block": self._build_block,
        }
        dot_code = builders.get(diagram_type, self._build_block)(nodes)

        if verbose:
            print(f"[Graphviz] Detected type: {diagram_type}")
            print(f"[Graphviz] Nodes: {nodes}")

        import graphviz
        try:
            src = graphviz.Source(dot_code, format="png")
            # Render to the parent directory of output_path, then rename
            render_path = src.render(
                filename=output_path.stem,
                directory=str(output_path.parent),
                cleanup=True
            )
            # graphviz renders to .png automatically
            rendered = Path(render_path)
            if rendered != output_path and rendered.exists():
                rendered.rename(output_path)

            return {
                "success": True,
                "final_image": str(output_path),
                "mode": "graphviz",
                "diagram_type": diagram_type,
                "nodes": nodes,
                "iterations_used": 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Graphviz rendering failed: {e}",
                "mode": "graphviz"
            }
