<!-- Reference Metadata
Type: reference
Last Verified: 2026-05-19
Version: 2026.05.19
Note: 工具参考文档
-->

# Scientific Illustration - Quick Reference

## Four Paths to Publication-Quality Diagrams

| Path | Needs | Best For | Output |
|------|-------|----------|--------|
| **Code-Based** | Python + packages | Reproducible, precise diagrams | PDF/SVG (vector) |
| **LLM Native** | Claude Code / image-capable LLM | Quick drafts, artistic content | PNG |
| **AI API** | API key + config | Same as LLM Native, via service | PNG |
| **Manual** | BioRender, Inkscape, etc. | Biological schematics, molecules | PDF/SVG |

---

## Path Selection (30 Seconds)

```
Need it NOW?
  YES → Using Claude Code? → YES → LLM Native (fastest)
                    → NO → API configured? → YES → AI API
                                          → NO → Code-Based (still fast)
  NO  → Biological/mechanistic? → YES → Manual (BioRender)
                          → NO → Need reproducibility? → YES → Code-Based
                                                      → NO → LLM Native
```

---

## Path 1: Code-Based (Zero Configuration)

**Install once:**
```bash
pip install matplotlib networkx numpy
# Optional: pip install schemdraw
```

**Block diagram (Matplotlib):**
```python
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
# See SKILL.md Part 3.1 for complete examples
```

**Flowchart with branching (NetworkX):**
```python
import networkx as nx
import matplotlib.pyplot as plt
# See SKILL.md Part 3.2 for CONSORT example
```

**Circuit (Schemdraw):**
```python
import schemdraw
import schemdraw.elements as elm
# See SKILL.md Part 3.3
```

**Output**: `plt.savefig('figure.pdf')` — direct vector output.

---

## Path 2: LLM Native (Claude Code)

No setup. Use the optimized prompt template from SKILL.md Part 2.2:

```
Create a publication-quality scientific diagram:
- Clean white background, high contrast
- Sans-serif fonts, min 10pt
- Colorblind-friendly (Okabe-Ito palette)
- Logical left-to-right flow
- No overlapping text
- No figure numbers inside image

USER REQUEST: {your description}
Document type: journal (threshold: 8.5/10)
```

Claude generates the image directly. No scripts, no APIs.

---

## Path 3: AI API

**Setup:**
```bash
export OPENROUTER_API_KEY='sk-or-v1-your_key'
# Or domestic provider: DASHSCOPE_API_KEY, MOONSHOT_API_KEY, etc.
```

**Run:**
```bash
python scripts/generate_schematic.py "diagram description" -o output.png --doc-type journal
```

---

## Path 4: Manual Tools

| Tool | Best For | Cost |
|------|---------|------|
| BioRender | Biological schematics | ~$99/mo academic |
| Inkscape | Vector editing | Free |
| Affinity Designer | Professional hybrid | ~$55 one-time |
| ChimeraX / PyMOL | Molecular structures | Free (academic) |

---

## Quality Thresholds

| Document Type | Threshold | Use For |
|---------------|-----------|---------|
| journal | 8.5/10 | Nature, Science, peer-reviewed |
| conference | 8.0/10 | Conference papers |
| thesis | 8.0/10 | Dissertations |
| grant | 8.0/10 | Grant proposals |
| preprint | 7.5/10 | arXiv, bioRxiv |
| poster | 7.0/10 | Academic posters |
| presentation | 6.5/10 | Slides |

---

## Quick Checklist

Before submitting any diagram:
- [ ] Format: PDF/SVG for vector, PNG for raster (300+ DPI)
- [ ] No overlapping elements or text
- [ ] Colorblind-safe palette (Okabe-Ito)
- [ ] Works in grayscale
- [ ] Text ≥ 7-8 pt at final size
- [ ] All components labeled
- [ ] Consistent with other figures
- [ ] Caption written, abbreviations defined

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No API key | Use **Code-Based** path (Matplotlib/NetworkX) |
| Graphviz too simple | Use **NetworkX** for branching, **Matplotlib** for custom layouts |
| Need biological icons | Use **BioRender** or **Inkscape** |
| Quick draft needed | Use **LLM Native** (Claude direct generation) |
| Must be reproducible | Use **Code-Based** path, version-control the .py file |
