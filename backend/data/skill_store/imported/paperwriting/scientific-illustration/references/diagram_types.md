<!-- Reference Metadata
Type: reference
Last Verified: 2026-05-19
Version: 2026.05.19
Note: 技术参考文档
-->

# Scientific Diagram Types

Catalog of scientific diagram types with recommended implementation paths.

## Overview

Choose your implementation path based on your environment and the diagram's complexity. This guide maps each diagram type to the best path(s) available.

| Path | Needs | Speed | Quality | Best For |
|------|-------|-------|---------|----------|
| **Code-Based** | Python only | Medium | Very High | Reproducible, precise, version-controlled |
| **LLM Native** | LLM with image gen | Fast | High | Quick drafts, complex artistic content |
| **AI API** | API key + config | Fast | High | Same as LLM Native, via external service |
| **Manual** | Design software | Slow | Very High | Biological schematics, precise iconography |

---

## Diagram Type Catalog

### 1. Flowchart / Study Design Diagram

**Best for:** CONSORT, PRISMA, clinical protocols, lab workflows, decision flows

**Recommended paths:**
1. **Code-Based (NetworkX)** — Best for publication. Handles branching (screened → excluded/randomized) correctly. Full control over layout.
2. **Code-Based (Graphviz)** — Only for simple linear flows (A → B → C). Cannot handle branching.
3. **LLM Native** — Good for quick drafts. May need regeneration for precise branching.

**Code-based example**: See SKILL.md Part 3.2 for a complete CONSORT flowchart with NetworkX.

**AI prompt tips:**
- Include specific numbers (n=500, 150 excluded)
- Describe decision points and branches clearly
- Specify direction (top-to-bottom, left-to-right)

---

### 2. Architecture / Hierarchy Diagram

**Best for:** Neural networks, model stacks, layered systems, encoder-decoder diagrams

**Recommended paths:**
1. **Code-Based (Matplotlib)** — Best for publication. Precise node placement, exact connection patterns (skip connections, multi-head attention).
2. **Code-Based (TikZ)** — Best for LaTeX workflows. Infinite resolution, native integration.
3. **LLM Native** — Good for conceptual diagrams. May struggle with complex connection patterns.

**Code-based example**: See SKILL.md Part 3.1 for a neural network layer diagram in Matplotlib.

**AI prompt tips:**
- List layers in order with dimensions
- Specify non-sequential connections (skip connections, attention)
- Include activation functions or normalization layers

---

### 3. Network / Pathway Diagram

**Best for:** Protein-protein interactions, gene regulatory networks, signaling cascades, social networks

**Recommended paths:**
1. **Code-Based (NetworkX)** — Best for publication. Handles cycles, branching, weighted edges, community detection.
2. **Manual (BioRender / Cytoscape)** — Best for biological pathways requiring precise iconography.
3. **LLM Native** — Good for simple linear pathways. Struggles with large or complex networks.

**Code-based example**: See SKILL.md Part 3.2 for a MAPK signaling pathway with NetworkX.

**AI prompt tips:**
- List nodes and their relationships
- Use arrow notation for directionality (->)
- Specify edge labels if important (phosphorylation, inhibition)

**Important**: Graphviz backend is NOT recommended for pathway diagrams. It produces only linear chains, which misrepresents most biological pathways.

---

### 4. Tree Diagram

**Best for:** Decision trees, phylogenetic trees, taxonomies, dendrograms

**Recommended paths:**
1. **Code-Based (NetworkX / SciPy dendrogram)** — Best for data-driven trees. Exact branch lengths, bootstrap values.
2. **Code-Based (Graphviz)** — Acceptable for simple binary trees with < 20 nodes.
3. **LLM Native** — Good for conceptual decision trees.

**AI prompt tips:**
- Define root node and branching rules
- Include leaf node characteristics
- Specify if branch lengths are meaningful

---

### 5. Block Diagram / System Diagram

**Best for:** System architectures, component diagrams, data flow, I/O flows

**Recommended paths:**
1. **Code-Based (Matplotlib / Schemdraw)** — Best for publication. Clean boxes, labeled arrows, professional output.
2. **LLM Native** — Good for quick drafts.

**Code-based example**: See SKILL.md Part 3.1 for an IoT system block diagram in Matplotlib.

**AI prompt tips:**
- List all components
- Describe connections and data flow direction
- Specify protocols or interfaces

---

### 6. Circuit Diagram

**Best for:** Electrical circuits, electronic schematics, signal flow diagrams

**Recommended paths:**
1. **Code-Based (Schemdraw)** — Purpose-built for circuits. Standard symbols, proper connections.
2. **Manual (Inkscape / CAD)** — For complex multi-sheet schematics.

**Code-based example**: See SKILL.md Part 3.3 for a simple circuit in Schemdraw.

**AI prompt tips:**
- Specify component values (1kΩ, 10µF)
- Include voltage/current sources
- Describe the circuit function

---

### 7. Conceptual / Artistic Diagram

**Best for:** Graphical abstracts, mechanism illustrations, 3D structures, conceptual models

**Recommended paths:**
1. **LLM Native** — Fast, good visual quality.
2. **AI API** — Same as LLM Native, via external service.
3. **Manual (BioRender / Affinity)** — Best for biological content with precise icons.

**Not recommended**: Code-Based paths struggle with artistic and 3D content.

**AI prompt tips:**
- Describe the visual style explicitly ("minimalist", "detailed", "3D")
- Include color requirements
- Specify if text should be included inside the image (usually: no)

---

### 8. Molecular Structure

**Best for:** Protein structures, molecular models, binding pockets, conformational states

**Recommended paths:**
1. **Manual (ChimeraX / PyMOL)** — The only correct choice for publication-quality molecular structures.
2. **Protein Data Bank (PDB) + rendering tools** — For data-driven structures.

**Not recommended**: AI generation is not suitable for molecular structures. Accuracy is paramount; artistic interpretation is misleading.

---

## Quick Decision Matrix

| If you need... | And you have... | Use this path |
|---------------|-----------------|---------------|
| CONSORT / PRISMA | Python | **NetworkX** (Part 3.2) |
| Neural network architecture | Python | **Matplotlib** (Part 3.1) or **TikZ** (Part 3.4) |
| Biological pathway | BioRender license | **Manual (BioRender)** |
| Biological pathway | No BioRender | **NetworkX** (Part 3.2) or **LLM Native** |
| Circuit | Python | **Schemdraw** (Part 3.3) |
| System block diagram | Python | **Matplotlib** (Part 3.1) |
| Graphical abstract | Claude Code | **LLM Native** (Part 2.2) |
| Molecular structure | ChimeraX/PyMOL | **Manual** (Part 4) |
| Quick draft, any type | Claude Code | **LLM Native** (Part 2.2) |
| Quick draft, any type | API configured | **AI API** (Part 2.1) |

---

## Path Capability Boundaries

### Code-Based (Matplotlib / NetworkX / Schemdraw)
- **Excellent**: Branching structures, precise layouts, reproducibility, vector output
- **Good**: Color control, typography, annotations
- **Poor**: 3D perspective, artistic textures, photorealism
- **Not possible**: Molecular structures (use ChimeraX)

### LLM Native / AI API
- **Excellent**: Artistic content, conceptual diagrams, 3D structures
- **Good**: Simple flowcharts, architecture diagrams
- **Poor**: Reproducibility, precise branching, exact layout control
- **Not possible**: Publication-quality molecular structures

### Graphviz (Legacy Script)
- **Excellent**: Simple linear chains (A → B → C)
- **Good**: Trees with < 20 nodes
- **Poor**: Branching flows, complex pathways, anything non-linear
- **Not possible**: Artistic content, 3D, precise biological icons

### Manual Tools (BioRender / Inkscape / ChimeraX)
- **Excellent**: Biological schematics, molecular structures, precise iconography
- **Good**: Any diagram type with sufficient time
- **Poor**: Rapid iteration, batch generation
- **Requires**: License (BioRender) or learning curve (Inkscape, ChimeraX)
