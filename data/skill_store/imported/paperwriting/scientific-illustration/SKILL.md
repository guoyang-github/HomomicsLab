---
name: scientific-illustration
description: "Create publication-quality scientific diagrams through multiple pathways: AI generation (API or LLM Native), code-based rendering (Matplotlib/NetworkX/Schemdraw/TikZ, zero configuration), or manual design tools (BioRender/Inkscape). Provides quality standards, color conventions, and best practices regardless of which path you choose."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Illustration

## Overview

Scientific schematics and diagrams transform complex concepts into clear visual representations. **This skill is a comprehensive quality framework with four complementary implementation paths.** You do not need API keys or external services to create high-quality diagrams.

**Four Paths to Publication-Quality Diagrams:**

| Path | Requirements | Best For | Output Quality |
|------|-------------|----------|----------------|
| **AI API** | `config/ai_models.json` + API key | Rapid iteration, complex artistic diagrams | High (with review) |
| **LLM Native** | Calling LLM has image generation (e.g., Claude Code) | Quick turnaround, conceptual diagrams | High (with optimized prompt) |
| **Code-Based** | Python + standard packages (Matplotlib, NetworkX, etc.) | Reproducible, precise, version-controlled | Very High (vector output) |
| **Manual Tools** | BioRender, Inkscape, Affinity, etc. | Biological schematics, precise iconography | Very High (full control) |

**Key principle**: The quality of a scientific diagram depends on **design decisions** (layout, typography, color, accessibility), not on which tool generated it. This skill provides the design standards; you choose the implementation path that fits your environment.

---

## Part 1: Choose Your Path

### Path Selection Decision Tree

```
Do you need the diagram RIGHT NOW (tight deadline)?
  YES → Are you using Claude Code or an LLM with image generation?
          YES → Path: LLM Native (fastest, zero config)
          NO  → Is an image generation API configured?
                  YES → Path: AI API
                  NO  → Path: Code-Based (still fast, fully reproducible)
  NO  → Is the diagram biological/mechanistic (needs precise icons)?
          YES → Path: Manual Tools (BioRender/Inkscape)
          NO  → Do you need reproducibility/version control?
                  YES → Path: Code-Based (best for papers)
                  NO  → Path: LLM Native or AI API
```

### Path Comparison by Diagram Type

| Diagram Type | Best Path | Runner-up | Avoid |
|-------------|-----------|-----------|-------|
| CONSORT/PRISMA flowchart | Code-Based (NetworkX/Graphviz) | LLM Native | Manual redraw |
| Neural network architecture | Code-Based (TikZ/matplotlib) | LLM Native | Graphviz alone |
| Biological signaling pathway | Manual (BioRender) | LLM Native | Graphviz |
| Protein structure | Manual (ChimeraX/PyMOL) | — | AI generation |
| System block diagram | Code-Based (Schemdraw) | LLM Native | — |
| Circuit diagram | Code-Based (Schemdraw) | Manual (Inkscape) | AI generation |
| Data flow / pipeline | Code-Based (Graphviz) | LLM Native | — |
| Conceptual framework | LLM Native | AI API | — |
| Graphical abstract | Manual (BioRender/Affinity) | LLM Native | — |

---

## Part 2: AI-Generated Diagrams

### When to Use AI Generation

- Tight deadlines requiring immediate output
- Conceptual diagrams where exact precision is less critical than clarity
- Early-stage drafts where you will refine later
- Diagrams with complex artistic elements (3D structures, realistic textures)

### 2.1 External API Mode

**Requires**: `scripts/config/ai_models.json` + API key environment variable

This mode calls an external image generation model (e.g., DALL-E, Midjourney, Stable Diffusion, domestic providers like Qwen-VL, GLM-4V).

```bash
python scripts/generate_schematic.py "diagram description" -o output.png --doc-type journal
```

**Configuration**: See the Configuration section at the end of this document for provider setup (OpenRouter, DashScope, Zhipu, Moonshot, MiniMax, etc.).

### 2.2 LLM Native Mode (Zero Configuration)

**Use this when**: Your calling environment includes an LLM with native image generation capabilities (e.g., Claude with visual output, GPT-4o, Gemini, GLM-4V, etc.). No API keys, no configuration files, no external services.

**In Claude Code**: Ask Claude to generate the diagram directly using the optimized prompt template below. Claude will create the image and save it to your working directory.

**In other environments**: Use your LLM's native image generation with the same prompt template.

**How it works**: The LLM generates the image using its native capability. The value of this skill is the **optimized prompt template and quality checklist** — not the generation mechanism itself.

**Optimized Prompt Template:**

```
Create a publication-quality scientific diagram with these requirements:

VISUAL QUALITY:
- Clean white or light background (no textures or gradients)
- High contrast for readability and printing
- Professional, publication-ready appearance
- Sharp, clear lines and text
- Adequate spacing between elements

TYPOGRAPHY:
- Clear, readable sans-serif fonts, minimum 10pt
- Consistent font sizes throughout
- All text horizontal and readable
- No overlapping text

SCIENTIFIC STANDARDS:
- Accurate representation of concepts
- Clear labels for all components
- Standard scientific notation and symbols
- Include units where applicable

ACCESSIBILITY:
- Colorblind-friendly color palette (Okabe-Ito colors)
- High contrast between elements
- Redundant encoding (shapes + colors)
- Works well in grayscale

LAYOUT:
- Logical flow (left-to-right or top-to-bottom)
- Clear visual hierarchy
- Balanced composition
- No figure numbers or captions inside the image

USER REQUEST: {your diagram description}
Document type: {journal|conference|poster|etc.}
Quality threshold: {8.5|8.0|7.0|etc.}/10
```

**Self-Review Criteria (if the LLM supports vision):**
Score the generated image 0-10 on:
1. Scientific Accuracy (0-2)
2. Clarity and Readability (0-2)
3. Label Quality (0-2)
4. Layout and Composition (0-2)
5. Professional Appearance (0-2)

If score < threshold for the document type, regenerate with improvements.

**Quality Thresholds by Document Type:**

| Document Type | Threshold | Description |
|---------------|-----------|-------------|
| journal | 8.5/10 | Nature, Science, peer-reviewed journals |
| conference | 8.0/10 | Conference papers |
| thesis | 8.0/10 | Dissertations, theses |
| grant | 8.0/10 | Grant proposals |
| preprint | 7.5/10 | arXiv, bioRxiv, etc. |
| report | 7.5/10 | Technical reports |
| poster | 7.0/10 | Academic posters |
| presentation | 6.5/10 | Slides, talks |
| default | 7.5/10 | General purpose |

### 2.3 Legacy Script Fallback (Graphviz / Spec)

The `generate_schematic.py` script can auto-detect backends. Without an API configured:

- **Graphviz**: Generates simple structured diagrams (flowcharts, hierarchies, trees). **Limitation**: only supports linear chain connections. Cannot handle branching (e.g., a true CONSORT diagram with "screened → excluded / randomized" split). Use **Code-Based** path instead for complex structured diagrams.
- **Spec**: Generates a `*_spec.json` file with an optimized prompt. Useful only as a reference; does not produce an image.

```bash
# Graphviz (simple flowcharts only)
pip install graphviz
# Also install system graphviz: apt/brew/choco install graphviz
python scripts/generate_schematic.py "simple linear flowchart" -o output.png

# Spec fallback (writes JSON, no image)
python scripts/generate_schematic.py "diagram description" -o output.png
```

---

## Part 3: Code-Based Diagrams (Zero Configuration)

**This is the recommended path when you do not have an image generation API configured.** Code-based diagrams are reproducible, version-controllable, and produce vector output. They require only standard Python scientific packages.

### When to Choose Code-Based

- **Reproducibility matters**: Every line of code is version-controlled; regenerate the exact same figure years later
- **Precision matters**: Exact control over layout, fonts, colors, line weights
- **Batch generation**: Need 50 similar diagrams with varying parameters
- **No API access**: No external services, no rate limits, no costs
- **Journal submission**: Direct PDF/SVG output, no rasterization artifacts

### 3.1 Matplotlib for Schematics

Matplotlib is not just for plots. With `patches`, `lines`, and `text`, it is a powerful diagramming engine.

**What it can do**: Block diagrams, flowcharts, architecture diagrams, annotation overlays, combined plot+diagram figures.

**Install**: Already included in any scientific Python environment. If not:
```bash
pip install matplotlib numpy
```

**Example: System Block Diagram**

Uses `FancyBboxPatch` for rounded boxes and `FancyArrowPatch` for labeled connections. Exports to both PDF (vector) and PNG.

```bash
cd scripts/examples
python matplotlib_block_diagram.py
# Output: iot_block_diagram.pdf, iot_block_diagram.png
```

**Key techniques:**
- `FancyBboxPatch(..., boxstyle="round,pad=0.02,rounding_size=0.2")` for rounded rectangles
- `FancyArrowPatch(..., arrowstyle='->', mutation_scale=20)` for directed edges
- Okabe-Ito color palette for colorblind accessibility
- Dual export: `plt.savefig('.pdf')` for LaTeX, `.png` for web

**Full code:** `scripts/examples/matplotlib_block_diagram.py`

**Example: Neural Network Layer Diagram**

Uses `plt.Circle` for nodes and nested loops for dense connections. Supports skip connections by adding extra `draw_connections` calls.

```bash
python scripts/examples/matplotlib_neural_network.py
# Output: neural_network.pdf, neural_network.png
```

**Key techniques:**
- `np.linspace()` for even vertical spacing
- `plt.Circle(..., ec='black', linewidth=1)` for outlined nodes
- Nested loops for all-to-all connections with `alpha=0.3` for subtlety
- `ax.set_aspect('equal')` to prevent node distortion

**Full code:** `scripts/examples/matplotlib_neural_network.py`

### 3.2 NetworkX for Networks and Pathways

NetworkX handles complex graph structures: branching, cycles, node attributes, edge labels. Far more powerful than Graphviz for anything beyond linear chains.

**Install**:
```bash
pip install networkx matplotlib
```

**Example: CONSORT Flowchart (with branching)**

NetworkX handles branching correctly (screened → excluded AND randomized), which Graphviz cannot do.

```bash
python scripts/examples/networkx_consort.py
# Output: consort_flowchart.pdf, consort_flowchart.png
```

**Key techniques:**
- `G.add_node(key, pos=(x*8, y), label=label)` for manual positioning
- `G.add_edges_from([...])` for branching (one source → multiple targets)
- Per-node styling with `nx.draw_networkx_nodes(..., nodelist=[node], ...)`
- Color coding by category (screening=blue, allocation=green, analysis=orange)

**Full code:** `scripts/examples/networkx_consort.py`

**Example: Biological Signaling Pathway**

Linear cascade with edge labels (phosphorylation) and a custom membrane boundary line.

```bash
python scripts/examples/networkx_pathway.py
# Output: mapk_pathway.pdf, mapk_pathway.png
```

**Key techniques:**
- `ax.axhline()` for drawing the cell membrane boundary
- Mixed node shapes: circles for proteins, square for nucleus
- `nx.draw_networkx_edge_labels()` for phosphorylation markers
- Custom arrow styling: `arrowstyle='->', width=2`

**Full code:** `scripts/examples/networkx_pathway.py`

### 3.3 Schemdraw for Circuits and Flowcharts

Schemdraw is purpose-built for electrical circuits and flowcharts with precise, publication-quality output.

**Install**:
```bash
pip install schemdraw
```

**Example: Simple Circuit**

Schemdraw provides standard circuit symbols (voltage source, resistor, capacitor, ground) with proper connection rendering.

```bash
pip install schemdraw
python scripts/examples/schemdraw_circuit.py
# Output: circuit.pdf
```

**Key techniques:**
- Chain-style API: `elm.SourceV().label('5V')` then `.right().label('1kΩ')`
- Automatic connection routing between elements
- `d.save('circuit.pdf')` for vector output

**Full code:** `scripts/examples/schemdraw_circuit.py`

### 3.4 TikZ (via Python + matplotlib)

For LaTeX users, TikZ provides the most precise control. You can generate TikZ code programmatically from Python.

**Example: Generate TikZ Code from Python**

Programmatically generates a standalone-compilable `.tex` file. The output wraps TikZ code in a `standalone` document class for direct compilation.

```bash
python scripts/examples/generate_tikz_network.py
# Output: network.tex
# Compile: pdflatex network.tex
```

**Key techniques:**
- Generate `.tex` file programmatically from Python data structures
- Wrap in `standalone` document class for direct `pdflatex` compilation
- Named nodes `(n{layer}_{index})` enable precise connection drawing
- Color mapping: `input` → `#E69F00`, `hidden` → `#56B4E9`, `output` → `#009E73`

**Full code:** `scripts/examples/generate_tikz_network.py`

### 3.5 Quick Reference: Code-Based vs. AI-Generated

| Aspect | Code-Based | AI-Generated |
|--------|-----------|--------------|
| Reproducibility | Exact regeneration from code | Non-deterministic |
| Version control | Full (text code) | Partial (prompt only) |
| Output format | PDF/SVG (vector) | PNG (raster) |
| Iteration speed | Slow (edit code, rerun) | Fast (regenerate) |
| Complex artistic content | Poor | Excellent |
| Branching structures | Excellent | Variable |
| Fine layout control | Excellent | Limited |
| Accessibility (colorblind) | Guaranteed (explicit palette) | Requires verification |

---

## Part 4: Manual Design Tools

For biological schematics, mechanism diagrams, and graphical abstracts requiring precise iconography, manual design tools remain the gold standard.

### Tool Comparison

| Tool | Best For | Cost | Output | Learning Curve |
|------|---------|------|--------|---------------|
| **BioRender** | Quick biological schematics; built-in icon library | ~$99/mo academic | PNG, SVG, PDF | Low |
| **Inkscape** | Full vector editing; open-source | Free | SVG, PDF | Medium |
| **Affinity Designer** | Professional vector + raster hybrid | ~$55 one-time | SVG, PDF | Medium |
| **ChimeraX / PyMOL** | Molecular structure renders | Free (academic) | PNG, TIFF, movie | High |
| **draw.io / Cytoscape** | Pathway diagrams, network layouts | Free | SVG, PDF | Low |

### Biological Color Conventions

- DNA: blue/navy or gray; mRNA: orange/yellow; Protein: consistent per family
- Nucleus: light gray/blue; Membrane: tan/beige; Mitochondria: orange; Lysosomes: red/purple
- Activation arrows: solid → (green); Inhibition: ⊣ flat bar (red); Indirect: - - → (gray)
- **Never use red–green encoding alone**; add shape cues (✓/✗, solid/dashed)

### Critical Rules for Manual Schematics

1. Start with a paper sketch before opening any tool
2. Define a consistent visual vocabulary (colors, arrow styles, fonts) at the project level
3. Set canvas to journal column width (e.g., 85 mm for single-column) before placing elements
4. Export from vector source at target DPI (≥300); never screenshot
5. Keep arrow semantics exact: one arrow style = one relationship type
6. Move arrow labels to figure caption, not into the diagram
7. Version-control source files (`.svg`, `.afdesign`, `.brd`)

---

## Part 5: Quality Standards

Regardless of which path you choose, verify your diagram against these standards before submission.

### Universal Quality Checklist

#### Visual Quality
- [ ] High-quality image format (PDF/SVG for vector, PNG for raster)
- [ ] No overlapping elements or text
- [ ] Adequate spacing between all components
- [ ] Clean, professional alignment
- [ ] All arrows connect properly to intended targets

#### Accessibility
- [ ] Colorblind-safe palette (Okabe-Ito) used
- [ ] Works in grayscale (test by converting to grayscale)
- [ ] Sufficient contrast between elements
- [ ] Redundant encoding where appropriate (shapes + colors)

#### Typography and Readability
- [ ] Text minimum 7-8 pt at final size
- [ ] All elements labeled clearly and completely
- [ ] Consistent font family and sizing
- [ ] No text overlaps or cutoffs
- [ ] Units included where applicable

#### Publication Standards
- [ ] Consistent styling with other figures in manuscript
- [ ] Comprehensive caption written with all abbreviations defined
- [ ] Referenced appropriately in manuscript text
- [ ] Meets journal-specific dimension requirements
- [ ] Exported in required format for journal (PDF/EPS/TIFF)

### Prompt Engineering Best Practices (for AI paths)

**Effective prompts** (specific, detailed):
- "CONSORT flowchart showing participant flow from screening (n=500) through randomization to final analysis"
- "Transformer neural network architecture with encoder stack on left, decoder stack on right, showing multi-head attention and cross-attention connections"
- "Biological signaling cascade: EGFR receptor → RAS → RAF → MEK → ERK → nucleus, with phosphorylation steps labeled"

**Avoid vague prompts**:
- "Make a flowchart" (too generic)
- "Neural network" (which type? what components?)
- "Pathway diagram" (which pathway? what molecules?)

**Key elements to include in every prompt**:
- **Type**: Flowchart, architecture diagram, pathway, circuit, etc.
- **Components**: Specific elements to include
- **Flow/Direction**: How elements connect
- **Labels**: Key annotations or text
- **Style**: Any specific visual requirements

---

## Part 6: Integration with Other Skills

- **scientific-visualization** — Shares color palettes, typography rules, and journal-specific figure guidelines
- **scientific-communication** — Diagrams for slides and posters; poster-specific font sizes and layout rules
- **scientific-manuscript** — Figure placement, caption writing, in-text referencing
- **scientific-peer-review** — Evaluate diagram clarity, accessibility, and scientific accuracy

---

## Part 7: Troubleshooting

### "I don't have any image generation API configured"

**Use Code-Based path.** See Part 3 for complete examples. Matplotlib + NetworkX can produce publication-quality flowcharts, pathway diagrams, and architecture schematics with zero external dependencies.

### "Graphviz produces overly simple diagrams"

This is by design. The Graphviz backend is limited to linear chain connections. For branching diagrams (true CONSORT, complex pathways), use **NetworkX** (Part 3.2) or **LLM Native** mode.

### "AI-generated image has overlapping text"

- Add explicit layout instructions to the prompt: "generous spacing", "no overlapping elements"
- Use Code-Based path for precise control
- Regenerate with increased specificity about component positions

### "Colors look wrong when printed in grayscale"

- Test by converting to grayscale before submission
- Use redundant encoding (line styles, shapes, labels) in addition to color
- Stick to Okabe-Ito palette: `#E69F00`, `#56B4E9`, `#009E73`, `#F0E442`, `#0072B2`, `#D55E00`, `#CC79A7`, `#999999`

---

## Part 8: Configuration (for AI API Mode Only)

Only needed if you choose the External API path. All other paths require zero configuration.

**Default (OpenRouter):**
```bash
export OPENROUTER_API_KEY='your_api_key_here'
```

**Domestic providers** (e.g., 阿里云 DashScope):
Edit `scripts/config/ai_models.json`:
```json
{
  "provider": "dashscope",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "auth_type": "bearer",
  "env_key_name": "DASHSCOPE_API_KEY",
  "image_generation_model": "qwen-vl-max",
  "image_review_model": "qwen-max"
}
```

Supported domestic providers: 阿里云 DashScope (`qwen-vl-max`), 智谱 AI (`glm-4v-plus`), 硅基流动 SiliconFlow, Kimi (`kimi-k2`), MiniMax (`minimax-image-01`), DeepSeek, etc.

---

## Resources

### Within This Skill
- `references/diagram_types.md` — Catalog of scientific diagram types
- `references/best_practices.md` — Detailed publication standards and accessibility guidelines

### External Python Libraries
- Matplotlib: https://matplotlib.org/
- NetworkX: https://networkx.org/documentation/
- Schemdraw: https://schemdraw.readthedocs.io/

### Publication Standards
- Nature Figure Guidelines: https://www.nature.com/nature/for-authors/final-submission
- Science Figure Guidelines: https://www.science.org/content/page/instructions-preparing-initial-manuscript
- CONSORT Diagram: http://www.consort-statement.org/consort-statement/flow-diagram
