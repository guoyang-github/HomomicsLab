# SingleR Usage Guide

## Overview

SingleR annotates cells using correlation with curated reference datasets from celldex. Best for reference-based annotation across tissues and species.

## When to Use

- Reference-based annotation needed
- Flexible across tissues/species
- Mouse or human data
- Any reference dataset can be used

## When NOT to Use

- No suitable reference exists for your tissue/species
- Novel cell types or rare diseases not represented in references
- In these cases, use marker-based methods (scType) or pre-trained models (CellTypist)

## Quick Start

```r
library(Seurat)
library(SingleR)
library(celldex)

# Load reference
ref <- celldex::MonacoImmuneData()

# Run annotation
sce <- as.SingleCellExperiment(seurat_obj)
pred <- SingleR(
  test = sce,
  ref = ref,
  labels = ref$label.main
)

seurat_obj$SingleR_label <- pred$labels
```

## Reference Selection

### Human References

| Reference | Helper Name | Cell Types | Best For |
|-----------|-------------|-----------|----------|
| MonacoImmuneData | `monaco` | 29 | Sorted blood immune populations |
| BlueprintEncodeData | `blueprint` | 43 | Immune + stromal |
| HumanPrimaryCellAtlasData | `hpca` | 157 | General purpose, broad coverage |
| DatabaseImmuneCellExpressionData | `dice` | 15 | Activation states |
| NovershternHematopoieticData | `novershtern` | 38 | Hematopoiesis, stem/progenitor |

### Mouse References

| Reference | Helper Name | Cell Types | Best For |
|-----------|-------------|-----------|----------|
| ImmGenData | `immgen` | 253 | Comprehensive mouse immune |
| MouseRNAseqData | `mouse` | 20+ | General mouse atlas |

### Label Levels

- `label.main`: Broad types (e.g. "T cells", "B cells")
- `label.fine`: Subtypes (e.g. "CD4+ T cells", "Naive B cells") — only available for some references

## Step-by-Step

### 1. Prepare Data

```r
library(Seurat)
library(SingleCellExperiment)

# Load preprocessed data
seurat_obj <- readRDS("preprocessed.rds")

# Convert to SingleCellExperiment
sce <- as.SingleCellExperiment(seurat_obj)
```

### 2. Choose Reference

```r
# Human blood/immune
ref <- celldex::MonacoImmuneData()

# Human general purpose
ref <- celldex::HumanPrimaryCellAtlasData()

# Mouse immune
ref <- celldex::ImmGenData()
```

**Critical**: Match species. Using human ref on mouse data without ortholog mapping produces garbage results.

### 3. Run Annotation

```r
pred <- SingleR(
  test = sce,
  ref = ref,
  labels = ref$label.main,
  de.method = "wilcox",
  prune = TRUE          # marks low-confidence cells as NA
)

# Add to Seurat
seurat_obj$SingleR_label <- pred$labels
seurat_obj$SingleR_pruned <- pred$pruned.labels
```

### 4. Quality Control

```r
# Plot scores
plotScoreHeatmap(pred)
plotDeltaDistribution(pred)

# Filter by confidence
seurat_obj$SingleR_filtered <- ifelse(
  is.na(seurat_obj$SingleR_pruned),
  "Unknown",
  seurat_obj$SingleR_label
)
```

## Skill Helper Usage

```r
source("scripts/r/singler_annotation.R")

# Shorthand reference loader
ref <- load_singler_reference("monaco")

# End-to-end wrapper
seurat_obj <- run_singler_annotation(seurat_obj, ref = ref)

# Seurat v5 with non-default assay
seurat_obj <- run_singler_annotation(seurat_obj, ref = ref, assay = "RNA")

# Quality plots
plot_singler_quality(seurat_obj, output_file = "qc.pdf")

# Filter low confidence
seurat_obj <- filter_singler_by_confidence(seurat_obj)
```

## Parameters

| Parameter | Options | Description |
|-----------|---------|-------------|
| `de.method` | "wilcox", "t", "binom" | DE method for scoring |
| `prune` | TRUE/FALSE | Prune low-confidence labels (always use TRUE) |
| `labels` | `ref$label.main`, `ref$label.fine` | Annotation granularity |

## Best Practices

1. **Choose appropriate reference** for your tissue
2. **Match species** — human ref on mouse data = nonsense without ortholog mapping
3. **Use `prune = TRUE`** to flag low-confidence cells
4. **Check quality plots** before trusting results
5. **Use pruned labels** for downstream analysis
6. **Validate** with known marker genes

## Troubleshooting

### All cells labeled as "Unknown"

Check gene overlap:
```r
sum(rownames(sce) %in% rownames(ref)) / nrow(ref)
```
Should be > 50%. Low overlap usually means gene ID mismatch (ENSEMBL vs symbols).

### Poor annotation quality

Try a broader reference:
```r
ref <- celldex::HumanPrimaryCellAtlasData()
```

## References

1. Aran et al. (2019). Reference-based analysis of lung single-cell sequencing reveals a transitional profibrotic macrophage. *Nature Immunology*.
