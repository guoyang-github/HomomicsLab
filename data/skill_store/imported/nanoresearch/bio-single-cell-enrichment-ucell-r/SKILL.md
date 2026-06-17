---
name: bio-single-cell-enrichment-ucell-r
description: Per-cell gene set scoring using UCell (U statistic, robust for cross-dataset comparison)
tool_type: r
primary_tool: UCell
language: r
dependencies:
  - UCell >= 2.6.0
  - Seurat >= 4.3.0
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "UCell", "U-statistic", "cross-dataset", "R"]
---

## Version Compatibility

- **R**: 4.2.0+
- **UCell**: 2.6+
- **Seurat**: >= 4.3.0 (optional, for input objects; v4 and v5 compatible via automatic slot/layer detection)

## Installation

```r
devtools::install_github("carmonalab/UCell")
```

# Single-Cell Enrichment with UCell

U statistic-based gene set scoring. Fast and robust for cross-dataset comparisons.

## Quick Selector

| Feature | UCell | vs AUCell |
|---------|-------|-----------|
| **Algorithm** | Mann-Whitney U | AUC-based |
| **Speed** | Fast | Medium |
| **Cross-dataset** | Excellent | Good |
| **Best for** | Comparing across batches/studies | Sparse dropout data |
| **Scores** | 0-1 normalized | 0-1 normalized |

### When to Use UCell

- Comparing pathway activity across different datasets
- Large-scale screening (fast)
- Batch effect robustness needed
- Seurat/Signac workflow

---

## Quick Start

```r
source("scripts/r/run_ucell.R")

# Define gene sets
gene_sets <- list(
  T_cells = c("CD3D", "CD3E", "CD4", "CD8A"),
  B_cells = c("CD19", "CD79A", "MS4A1")
)

# Run UCell
scores <- run_ucell(
  expr_matrix = expr_matrix,
  gene_sets = gene_sets,
  maxRank = 1500
)
```

**Full implementation:** [scripts/r/run_ucell.R](scripts/r/run_ucell.R)

---

## Detailed Usage

### 1. With Seurat

```r
source("scripts/r/run_ucell.R")

seurat_obj <- run_ucell_seurat(
  seurat_obj,
  gene_sets = marker_genes,
  prefix = "UCell.",
  maxRank = 1500,
  ncores = 4
)

# Visualize
Seurat::FeaturePlot(seurat_obj, features = "UCell.T_cells")
```

### 2. Module Scoring

```r
# Similar to AddModuleScore but using UCell
seurat_obj <- AddModuleScore_UCell(
  seurat_obj,
  features = list(
    IFN_response = c("IFIT1", "IFIT3", "MX1", "OAS1"),
    Hypoxia = c("VEGFA", "EGLN3", "SLC2A1")
  ),
  name = "Module"
)
```

### 3. Export Results

```r
export_ucell_results(
  scores,
  output_file = "ucell_scores.csv",
  format = "csv"
)
```

---

## Parameters

### run_ucell()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `maxRank` | int | 1500 | Maximum rank for U statistic calculation |
| `ncores` | int | 1 | Parallel cores |
| `force.gc` | bool | FALSE | Force garbage collection |

**maxRank:** Higher = more genes considered, slower but potentially more accurate.

---

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_ucell()` | [run_ucell.R:24](scripts/r/run_ucell.R#L24) | Main UCell scoring |
| `run_ucell_seurat()` | [run_ucell.R:82](scripts/r/run_ucell.R#L82) | Seurat wrapper |
| `AddModuleScore_UCell()` | [run_ucell.R:115](scripts/r/run_ucell.R#L115) | Module scoring |

---

## Related Skills

- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) - gseapy
- [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md) - AUCell

---

## References

1. Andreatta & Carmona (2021). UCell: Robust and scalable single-cell gene signature scoring. Computational and Structural Biotechnology Journal.
2. UCell documentation: https://github.com/carmonalab/UCell
