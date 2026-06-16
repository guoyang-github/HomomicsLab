<!-- Reference Metadata
Type: reference
Last Verified: 2026-05-19
Version: 2026.05.19
Note: 工具参考文档
-->

# Scientific Illustration

**Create publication-quality scientific diagrams through multiple complementary paths.**

This skill provides a complete quality framework for scientific diagrams — not just a single generation tool. Choose the path that fits your environment: AI generation, code-based rendering, or manual design tools.

## Four Paths at a Glance

| Path | Setup | Output | Best For |
|------|-------|--------|----------|
| **Code-Based** | `pip install matplotlib networkx` | PDF/SVG (vector) | Reproducible, precise, version-controlled |
| **LLM Native** | None (Claude Code) | PNG | Quick drafts, conceptual diagrams |
| **AI API** | API key + config | PNG | Same as LLM Native, via external service |
| **Manual** | BioRender, Inkscape, etc. | PDF/SVG | Biological schematics, molecular structures |

## Quick Start by Path

### Path 1: Code-Based (Recommended for Publications)

Zero configuration. Pure Python. Vector output. Fully reproducible.

```bash
pip install matplotlib networkx numpy
```

```python
# Block diagram with Matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
# See SKILL.md Part 3.1 for complete examples

# Complex flowchart with NetworkX
import networkx as nx
# See SKILL.md Part 3.2 for CONSORT example
```

**Why choose this path:**
- Exact reproducibility (same code = same figure, years later)
- Version control friendly (text-based Python code)
- Vector output (PDF/SVG) with no rasterization
- No API costs, no rate limits, no external dependencies
- Handles branching structures correctly (unlike Graphviz)

### Path 2: LLM Native (Fastest)

No setup. No scripts. Claude generates the image directly.

```
Create a publication-quality scientific diagram:
- Clean white background, high contrast
- Sans-serif fonts, minimum 10pt
- Colorblind-friendly colors (Okabe-Ito)
- Logical left-to-right flow
- No overlapping elements

USER REQUEST: {your diagram description}
Document type: journal (threshold: 8.5/10)
```

**Why choose this path:**
- Fastest turnaround (single prompt)
- No software installation
- Good for artistic/conceptual content
- Ideal for early drafts and exploration

### Path 3: AI API

Requires API key configuration. See `scripts/config/ai_models.json`.

```bash
export OPENROUTER_API_KEY='your_key_here'
python scripts/generate_schematic.py "diagram description" -o output.png --doc-type journal
```

**Why choose this path:**
- Same capabilities as LLM Native but via external API
- Useful when LLM Native is not available

### Path 4: Manual Design Tools

For biological schematics, molecular structures, and precise iconography.

| Tool | Best For | Cost |
|------|---------|------|
| BioRender | Biological pathways, cell diagrams | ~$99/mo academic |
| Inkscape | Vector editing, custom schematics | Free |
| Affinity Designer | Professional vector + raster | ~$55 one-time |
| ChimeraX / PyMOL | Molecular structures, binding pockets | Free (academic) |

**Why choose this path:**
- Full creative control
- Precise biological iconography
- Standard tool in life sciences

## Which Path for Which Diagram?

| Diagram Type | Recommended Path | Runner-up |
|-------------|-----------------|-----------|
| CONSORT/PRISMA flowchart | **Code-Based (NetworkX)** | LLM Native |
| Neural network architecture | **Code-Based (Matplotlib/TikZ)** | LLM Native |
| Biological signaling pathway | **Manual (BioRender)** | Code-Based (NetworkX) |
| System block diagram | **Code-Based (Matplotlib)** | LLM Native |
| Circuit diagram | **Code-Based (Schemdraw)** | Manual (Inkscape) |
| Protein structure | **Manual (ChimeraX)** | — |
| Graphical abstract | **LLM Native** | Manual (BioRender) |
| Conceptual framework | **LLM Native** | AI API |

## Important Notes

### Graphviz Limitations

The `generate_schematic.py` script includes a Graphviz backend for simple structured diagrams. **Important**: Graphviz only supports linear chain connections (A → B → C). It cannot handle branching (e.g., CONSORT diagrams with "screened → excluded / randomized" splits). For branching diagrams, use **NetworkX** (Code-Based path).

### Spec Fallback

When no backend is available, the script generates a `*_spec.json` file containing an optimized prompt. This is a reference document, not an image. Use the LLM Native path or Code-Based path to actually generate the diagram.

## Quality Standards

All paths converge on the same quality standards:

- Clean white/light background
- High contrast for readability
- Clear labels (minimum 10pt font)
- Professional typography (sans-serif)
- Colorblind-friendly colors (Okabe-Ito palette)
- Proper spacing between elements
- Vector output preferred (PDF/SVG)

See SKILL.md for the complete quality checklist.

## Files in This Skill

- `SKILL.md` — Complete skill documentation with all four paths
- `references/QUICK_REFERENCE.md` — One-page cheat sheet
- `references/diagram_types.md` — Diagram type catalog with path recommendations
- `references/best_practices.md` — Detailed publication standards
- `scripts/generate_schematic.py` — AI API / Graphviz / Spec entry point
- `scripts/example_usage.sh` — Runnable examples for Code-Based and AI API paths
