---
name: bio-single-cell-communication-cellchat-r
description: Single-cell cell-cell communication analysis using CellChat (R)
tool_type: r
primary_tool: CellChat
language: r
dependencies:
  - CellChat
  - Seurat >= 4.3.0
  - dplyr
  - ggplot2
  - patchwork
  - NMF
  - ggalluvial
  - igraph
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "cell-communication", "CellChat", "ligand-receptor", "signaling", "network", "R"]
---

## Version Compatibility

- **R**: 4.2.0+
- **CellChat**: Latest from GitHub
- **Seurat**: >= 4.3.0 (CellChat v2 is compatible with both Seurat v4 and v5)

## Installation

```r
remotes::install_github("jinworks/CellChat")
```

# Single-Cell Cell-Cell Communication with CellChat

Inference and analysis of cell-cell communication from single-cell RNA-seq data using ligand-receptor interactions.

## Quick Selector

| Feature | CellChat |
|---------|----------|
| **Database** | ~3,300 validated L-R interactions |
| **Signaling Types** | Secreted, ECM, Contact, Non-protein |
| **Analysis** | Network + Pattern recognition |
| **Comparison** | Multi-condition comparison |

### When to Use CellChat

- Infer cell-cell communication from scRNA-seq
- Identify active signaling pathways
- Compare communication across conditions
- Explore global communication patterns

---

## Detailed Usage

### 1. Run CellChat on Single Dataset

```r
source("scripts/r/cellchat_analysis.R")

cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  sample_name = "Tumor_Sample",
  db_use = "CellChatDB.human",
  signaling_type = "Secreted Signaling",
  min_cells = 10
)
```

### 2. Visualize Results

```r
# Circle plot
plot_cellchat_circle(cellchat)

# Bubble plot for specific interactions
plot_cellchat_bubble(
  cellchat,
  sources.use = c("T_cell", "B_cell"),
  targets.use = c("Tumor", "Macrophage")
)

# Signaling pathway
plot_cellchat_pathway(cellchat, signaling = "CXCL")
```

### 3. Systems Analysis

```r
# Compute network centrality
cellchat <- compute_cellchat_centrality(cellchat)

# Identify communication patterns
cellchat <- identify_cellchat_patterns(cellchat, pattern = "outgoing", k = 5)

# Plot signaling roles
plot_cellchat_signaling_roles(cellchat)
```

### 4. Compare Multiple Conditions

```r
# Run on control and treatment
control <- run_cellchat(seurat_control, group_by = "cell_type")
treatment <- run_cellchat(seurat_treatment, group_by = "cell_type")

# Compare
comparison <- compare_cellchat_conditions(
  list(Control = control, Treatment = treatment)
)

# Visualize differences
plot_cellchat_comparison(comparison)
```

### 5. Specify Signaling Type

Use `signaling_type` to restrict the ligand-receptor database before inference. You can pass a single string or a character vector to select multiple categories:

| Option | Meaning | When to Use |
|--------|---------|-------------|
| `"Secreted Signaling"` | Cytokines, chemokines, growth factors | General analysis (default) |
| `"Cell-Cell Contact"` | Membrane-bound ligands and receptors | Juxtacrine signaling |
| `"ECM-Receptor"` | Extracellular matrix – receptor interactions | Studying tissue microenvironment |
| `"all"` | All categories combined | Exploratory analysis |

```r
# Single category
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  signaling_type = "Cell-Cell Contact"
)

# Multiple categories
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  signaling_type = c("Secreted Signaling", "ECM-Receptor")
)
```

### 6. Subset to Specific Cell Types

Limit the analysis to selected cell types with the `cell_types` parameter. This reduces computation and improves statistical power:

```r
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  cell_types = c("T_cell", "Macrophage", "Tumor")
)
```

After analysis, filter by direction with `subsetCommunication()`:

```r
df <- subsetCommunication(
  cellchat,
  sources.use = c("Macrophage"),
  targets.use = c("T_cell")
)
```

---

## Parameters

### run_cellchat()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object |
| `group_by` | char | "cell_type" | Metadata column |
| `sample_name` | char | "Sample" | Sample name identifier |
| `db_use` | char | "CellChatDB.human" | Database |
| `signaling_type` | char / vector | "Secreted Signaling" | Signaling subset. Single string or vector (e.g. `c("Secreted Signaling", "ECM-Receptor")`). Use `"all"` for all categories. |
| `type` | char | "triMean" | Average method |
| `trim` | numeric | NULL | Trim value for truncatedMean |
| `population.size` | logical | FALSE | Consider cell population size |
| `cell_types` | char vector | NULL | Subset to specific cell types before analysis |
| `min_cells` | int | 10 | Min cells per group |
| `n_workers` | int | 4 | Number of parallel workers |
| `verbose` | logical | TRUE | Print progress messages |

---

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_cellchat()` | [cellchat_analysis.R:25](scripts/r/cellchat_analysis.R#L25) | Main analysis |
| `create_cellchat_object()` | [cellchat_analysis.R:85](scripts/r/cellchat_analysis.R#L85) | Create object |
| `plot_cellchat_circle()` | [cellchat_analysis.R:140](scripts/r/cellchat_analysis.R#L140) | Circle plot |
| `plot_cellchat_bubble()` | [cellchat_analysis.R:170](scripts/r/cellchat_analysis.R#L170) | Bubble plot |
| `plot_cellchat_pathway()` | [cellchat_analysis.R:210](scripts/r/cellchat_analysis.R#L210) | Pathway visualization |
| `compute_cellchat_centrality()` | [cellchat_analysis.R:250](scripts/r/cellchat_analysis.R#L250) | Network centrality |
| `identify_cellchat_patterns()` | [cellchat_analysis.R:290](scripts/r/cellchat_analysis.R#L290) | Communication patterns |
| `compare_cellchat_conditions()` | [cellchat_analysis.R:340](scripts/r/cellchat_analysis.R#L340) | Multi-condition comparison |

---

## Output Description

| Slot | Description |
|------|-------------|
| `@net$prob` | Communication probabilities |
| `@net$count` | Number of interactions |
| `@net$weight` | Interaction strength |
| `@netP$prob` | Pathway-level probabilities |
| `@netP$pathways` | Significant pathways |

---

## Related Skills

- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md)
- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md)
- [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/SKILL.md)

---

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. Nature Protocols.
2. Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. Nature Communications.
3. CellChat documentation: https://github.com/jinworks/CellChat
