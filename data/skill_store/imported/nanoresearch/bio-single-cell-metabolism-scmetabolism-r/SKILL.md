---
name: bio-single-cell-metabolism-scmetabolism-r
description: Single-cell metabolic pathway analysis using scMetabolism (R)
tool_type: r
primary_tool: scMetabolism
language: r
dependencies:
  - scMetabolism
  - Seurat >= 4.3.0
  - ggplot2
  - dplyr
  - pheatmap
  - ggridges
  - viridis
  - wesanderson
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "metabolism", "scMetabolism", "pathway", "KEGG", "REACTOME", "GSVA", "VISION", "AUCell", "ssGSEA", "R"]
---

## Version Compatibility

- **R**: 4.2.0+
- **scMetabolism**: Latest from GitHub (wu-yc/scMetabolism)
- **Seurat**: 4.3+ or 5.x
- **Tested on**: Ubuntu 22.04, macOS 13+, Windows 11

## Installation

```r
# Install dependencies
install.packages(c("Seurat", "ggplot2", "dplyr", "pheatmap", "ggridges", "viridis", "devtools"))

# Install scMetabolism
devtools::install_github("wu-yc/scMetabolism")

# Optional: for color palettes
install.packages("wesanderson")
```

## System Requirements

- R version 4.2.0 or higher
- **Seurat**: >= 4.3.0 (v4 and v5 compatible via automatic slot/layer detection)
- Sufficient memory (8GB+ recommended for datasets >10,000 cells)
- Multi-core CPU recommended for parallel processing

---

# Single-Cell Metabolism with scMetabolism

Quantify metabolic pathway activities in single-cell RNA-seq data using multiple gene set scoring methods.

## Quick Selector

| Feature | scMetabolism |
|---------|--------------|
| **Algorithm** | VISION (default), AUCell, ssGSEA, GSVA |
| **Databases** | KEGG (85 pathways), REACTOME (82 pathways) |
| **Visualization** | DimPlot, DotPlot, BoxPlot, Heatmap, Violin, Ridge |
| **Input** | Seurat object or raw count matrix |
| **Speed** | Fast (AUCell) to Medium (ssGSEA) |
| **Memory** | Low (AUCell) to High (ssGSEA) |

### When to Use scMetabolism

- Pathway-level metabolism analysis
- Compare metabolic states across cell types or conditions
- Visualize metabolic heterogeneity
- Integrate with cell type annotations
- Identify metabolic shifts in disease states

### When NOT to Use scMetabolism

- Single-gene metabolic analysis (use standard DE analysis instead)
- Metabolic flux analysis (use dedicated tools like COMPASS)
- Spatial metabolic analysis without single-cell context

---

## Quick Start

```r
library(Seurat)

# Source the skill functions
source("scripts/r/run_scmetabolism.R")
source("scripts/r/visualize_scmetabolism.R")

# Load data
seurat_obj <- readRDS("your_data.rds")

# Run scMetabolism analysis
result <- run_scmetabolism(
  seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  ncores = 4
)

seurat_obj <- result$seurat_obj

# Visualize
DimPlot(seurat_obj, reduction = "umap", group.by = "cell_type")
dimplot_metabolism(seurat_obj, pathway = "Glycolysis / Gluconeogenesis")
```

---

## Detailed Usage

### 1. Run scMetabolism Analysis

#### On Seurat Object (Recommended)

```r
# Basic usage with default parameters
result <- run_scmetabolism(seurat_obj)
seurat_obj <- result$seurat_obj

# With custom parameters
result <- run_scmetabolism(
  seurat_obj = seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  imputation = FALSE,
  ncores = 4,
  assay = "RNA",
  slot = "counts",
  output_assay = "METABOLISM"
)
```

#### On Raw Count Matrix

```r
# Direct analysis on count matrix
metabolism_matrix <- run_scmetabolism_matrix(
  countexp = raw_counts,
  method = "AUCell",
  metabolism.type = "KEGG",
  ncores = 4
)
```

### 2. Explore Available Pathways

```r
# Get KEGG pathways
kegg_pathways <- get_metabolic_pathways("KEGG")
print(kegg_pathways[1:10])

# Get REACTOME pathways
reactome_pathways <- get_metabolic_pathways("REACTOME")
print(reactome_pathways[1:10])
```

### 3. Extract and Analyze Scores

```r
# Extract all scores
scores <- extract_metabolism_scores(seurat_obj, assay = "METABOLISM")

# Extract specific pathways
glycolysis_scores <- extract_metabolism_scores(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation")
)

# Get top variable pathways
top_pathways <- get_top_variable_pathways(seurat_obj, n_top = 10)

# Compare between groups
comparison <- compare_metabolism(
  seurat_obj,
  group.by = "cell_type",
  pathways = top_pathways[1:5]
)
```

### 4. Visualize Results

#### Dimensionality Reduction Overlay

```r
# UMAP overlay
dimplot_metabolism(
  seurat_obj,
  pathway = "Glycolysis / Gluconeogenesis",
  reduction = "umap",
  size = 0.5,
  palette = "Zissou1"
)

# tSNE overlay
dimplot_metabolism(
  seurat_obj,
  pathway = "Oxidative phosphorylation",
  reduction = "tsne",
  palette = "plasma"
)
```

#### Dot Plot

```r
dotplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)"),
  group.by = "cell_type",
  norm = "y"  # Normalize by pathway
)
```

#### Box Plot

```r
boxplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation"),
  group.by = "condition",
  ncol = 2
)
```

#### Heatmap

```r
heatmap_metabolism(
  seurat_obj,
  pathways = get_top_variable_pathways(seurat_obj, 20),
  group.by = "cell_type",
  scale = "row"
)
```

#### Violin Plot

```r
violinplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis"),
  group.by = "cell_type"
)
```

#### Ridge Plot

```r
ridgeplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Fatty acid degradation"),
  group.by = "cell_type"
)
```

### 5. Export Results

```r
export_scmetabolism_results(
  seurat_obj,
  output_dir = "scmetabolism_output",
  prefix = "analysis_run1"
)

# Save annotated object
saveRDS(seurat_obj, "seurat_with_metabolism.rds")
```

---

## Parameters

### run_scmetabolism()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object containing scRNA-seq data |
| `method` | char | "VISION" | Scoring method: VISION, AUCell, ssGSEA, GSVA |
| `metabolism.type` | char | "KEGG" | Pathway database: KEGG or REACTOME |
| `imputation` | bool | FALSE | Whether to impute data before scoring |
| `ncores` | int | 4 | Number of cores for parallel computation |
| `assay` | char | "RNA" | Assay to use for analysis |
| `slot` | char | "counts" | Slot to extract data from (counts/data) |
| `min.cells` | int | 10 | Minimum cells threshold |
| `min.feature` | int | 10 | Minimum features threshold |
| `output_assay` | char | "METABOLISM" | Name for output assay |
| `return_matrix` | bool | TRUE | Return metabolism matrix separately |

### dimplot_metabolism()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object |
| `pathway` | char | required | Pathway name to visualize |
| `reduction` | char | "umap" | Dimensionality reduction (umap/tsne/pca) |
| `assay` | char | "METABOLISM" | Assay containing scores |
| `size` | num | 1 | Point size |
| `palette` | char | "Zissou1" | Color palette |

---

## Algorithm Selection Guide

| Method | Speed | Memory | Sensitivity | Best Use Case |
|--------|-------|--------|-------------|---------------|
| **VISION** | Medium | Medium | High | General purpose, balanced |
| **AUCell** | Fast | Low | Medium | Large datasets, screening |
| **ssGSEA** | Slow | High | Very High | Detailed analysis |
| **GSVA** | Medium | Medium | Medium | Standard pathway analysis |

### Method Details

**VISION (Default)**
- Uses random walk with restarts on cell-cell similarity graph
- Accounts for expression similarity between cells
- Best balance of speed and accuracy

**AUCell**
- Area Under the Curve calculation
- Fast and memory efficient
- Good for datasets >10,000 cells

**ssGSEA**
- Single-sample Gene Set Enrichment Analysis
- Most sensitive for detecting subtle pathway differences
- Computationally intensive

**GSVA**
- Gene Set Variation Analysis
- Non-parametric, unsupervised
- Standard method for pathway enrichment

---

## Pathway Databases

### KEGG (85 Pathways)

| Category | Example Pathways |
|----------|-----------------|
| Carbohydrate | Glycolysis/Gluconeogenesis, TCA cycle, Pentose phosphate |
| Energy | Oxidative phosphorylation, Photosynthesis |
| Lipid | Fatty acid biosynthesis, Fatty acid degradation, Steroid biosynthesis |
| Amino Acid | Alanine/aspartate/glutamate, Glycine/serine/threonine |
| Cofactors/Vitamins | Porphyrin metabolism, Riboflavin metabolism |

### REACTOME (82 Pathways)

Alternative pathway annotations with different gene sets and definitions.

---

## Common Key Pathways

| Pathway | Biological Process |
|---------|-------------------|
| Glycolysis / Gluconeogenesis | Glucose metabolism |
| Citrate cycle (TCA cycle) | Central carbon metabolism |
| Oxidative phosphorylation | ATP production (OXPHOS) |
| Fatty acid degradation | Lipid catabolism |
| Fatty acid biosynthesis | Lipid anabolism |
| Pentose phosphate pathway | NADPH and ribose production |
| Glutathione metabolism | Redox homeostasis |
| One carbon pool by folate | Nucleotide/methylation metabolism |

---

## API Reference

### Analysis Functions

| Function | Description |
|----------|-------------|
| `run_scmetabolism()` | Main analysis function for Seurat objects |
| `run_scmetabolism_matrix()` | Analysis on raw count matrices |
| `get_metabolic_pathways()` | List available pathways |
| `extract_metabolism_scores()` | Extract scores as data frame |
| `compare_metabolism()` | Statistical comparison between groups |
| `get_top_variable_pathways()` | Find most variable pathways |
| `export_scmetabolism_results()` | Export results to files |

### Visualization Functions

| Function | Description |
|----------|-------------|
| `dimplot_metabolism()` | UMAP/tSNE overlay |
| `dotplot_metabolism()` | Dot plot by group |
| `boxplot_metabolism()` | Box plot comparison |
| `violinplot_metabolism()` | Violin plot distribution |
| `ridgeplot_metabolism()` | Ridge/joy plot |
| `heatmap_metabolism()` | Heatmap visualization |

---

## Troubleshooting

### Common Issues

**Issue**: "Pathway 'X' not found"
```r
# Solution: Check exact pathway name
get_metabolic_pathways("KEGG")  # List all available pathways
```

**Issue**: Low scores across all cells
```r
# Solution: Use data slot instead of counts
result <- run_scmetabolism(seurat_obj, slot = "data")
```

**Issue**: Out of memory
```r
# Solution: Use AUCell method with fewer cores
result <- run_scmetabolism(seurat_obj, method = "AUCell", ncores = 1)
```

**Issue**: Missing metabolic genes
```r
# Check overlap between your genes and pathway genes
# Consider using imputation for sparse data
result <- run_scmetabolism(seurat_obj, imputation = TRUE)
```

---

## Related Skills

- [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/SKILL.md) - Cell type annotation
- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/SKILL.md) - CNV analysis
- [bio-single-cell-communication-nichenet-r](../bio-single-cell-communication-nichenet-r/SKILL.md) - Cell-cell communication
- [bio-single-cell-differential-expression-r](../bio-single-cell-differential-expression-r/SKILL.md) - Differential expression

---

## References

1. **Primary Citation**
   Wu Y, Yang S, Ma J, et al. Spatiotemporal Immune Landscape of Colorectal Cancer Liver Metastasis at Single-Cell Level. Cancer Discovery. 2021.
   https://pubmed.ncbi.nlm.nih.gov/34417225/

2. **Package Documentation**
   https://github.com/wu-yc/scMetabolism

3. **Algorithm References**
   - VISION: DeTomaso D, et al. Nat Commun. 2019
   - AUCell: Aibar S, et al. Nat Methods. 2017
   - ssGSEA: Xiao Z, et al. Nat Commun. 2019
   - GSVA: Hänzelmann S, et al. BMC Bioinformatics. 2013

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-04-03 | Added comprehensive visualization functions, Seurat v5 support |
| 1.0.0 | 2024-01-15 | Initial skill creation with basic analysis functions |
