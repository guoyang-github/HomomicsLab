---
name: bio-single-cell-annotation-singler-r
description: Reference-based cell type annotation using SingleR and celldex curated reference datasets. Correlation-based scoring with DE gene selection, supports human and mouse references, fine-grained labels, and confidence pruning.
tool_type: r
primary_tool: SingleR
supported_tools: [celldex, Seurat, SingleCellExperiment]
languages: [r]
keywords: ["single-cell", "annotation", "singler", "reference", "correlation", "celldex", "cell-type", "immune"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.2"
  singler: ">=2.4"
  celldex: ">=1.14"
  seurat: ">=4.3.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2 | |
| SingleR | >= 2.4 | Core annotation package |
| celldex | >= 1.14 | Curated reference datasets |
| Seurat | >= 4.3.0 | Optional; **v4 and v5 both supported** |
| SingleCellExperiment | — | Required for data conversion |

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install(c("SingleR", "celldex"))
```

## Skill Overview

SingleR annotates cells by correlating their expression profiles with curated reference datasets from celldex. It scores cell types using differentially expressed genes, making it robust across tissues and species.

**Core workflow**: Load reference → Convert data to SCE → `SingleR()` → Add labels to Seurat → Quality check → Confidence filtering

**When to use**: You have a reference dataset that matches your tissue/species. Best for immune cells, blood, and tissues with well-characterized atlases.

**When NOT to use**: Your tissue has no suitable reference (e.g. rare disease, novel organ). Consider [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/SKILL.md) or [bio-single-cell-annotation-markers](../bio-single-cell-annotation-markers/SKILL.md) instead.

## Quick Reference: Reference Selection

| Your Sample | Recommended Reference | Helper Name | Label Level |
|-------------|----------------------|-------------|-------------|
| Human blood/PBMC | `MonacoImmuneData` | `monaco` | `label.main` or `label.fine` |
| Human mixed tissue | `HumanPrimaryCellAtlasData` | `hpca` | `label.main` |
| Human immune + stromal | `BlueprintEncodeData` | `blueprint` | `label.main` |
| Human hematopoiesis | `NovershternHematopoieticData` | `novershtern` | `label.main` |
| Mouse immune | `ImmGenData` | `immgen` | `label.main` or `label.fine` |
| Mouse general | `MouseRNAseqData` | `mouse` | `label.main` |

**Label levels**: `label.main` = broad types (e.g. "T cells", "B cells"). `label.fine` = subtypes (e.g. "CD4+ T cells", "Naive B cells"). Use `label.main` for general annotation, `label.fine` for detailed immune subtyping.

## Core Workflow (Step-by-Step)

Source skill helpers before using convenience functions:

```r
source("scripts/r/singler_annotation.R")
```

### Step 1: Load Reference Dataset

**Goal**: Choose a reference that matches your tissue and species.

```r
# Option A: Direct from celldex
ref <- celldex::MonacoImmuneData()

# Option B: Using skill helper (shorthand names)
ref <- load_singler_reference("monaco")
# Valid names: "monaco", "blueprint", "hpca", "immgen", "dice", "novershtern", "mouse"
```

**⚠️ CRITICAL: Match species**. Using a human reference on mouse data (or vice versa) will produce nonsense results. Always check `ref$species` if uncertain.

**Cross-species strategy**: If no reference exists for your species, you can:
1. Convert gene symbols between species (ortholog mapping)
2. Use a closely related species reference with `restrict genes to one-to-one orthologs`
3. Fall back to marker-based annotation

---

### Step 2: Prepare Test Data

**Goal**: Convert your data to `SingleCellExperiment` format.

```r
library(SingleCellExperiment)

# From Seurat
sce <- as.SingleCellExperiment(seurat_obj)

# From count matrix
counts <- your_count_matrix
sce <- SingleCellExperiment(assays = list(counts = counts))
```

**Input requirements**:
- Raw or normalized counts (SingleR handles normalization internally)
- Gene symbols as rownames (not ENSEMBL IDs — unless reference also uses ENSEMBL)
- Cells as columns

---

### Step 3: Run Annotation

**Goal**: Predict cell types for each cell.

#### Option A: Direct official API

```r
pred <- SingleR(
  test = sce,
  ref = ref,
  labels = ref$label.main,    # or ref$label.fine for finer resolution
  de.method = "wilcox",       # "wilcox" (default), "t", or "binom"
  prune = TRUE                # marks low-confidence cells as NA
)

# Add to Seurat
seurat_obj$SingleR_label <- pred$labels
seurat_obj$SingleR_pruned <- pred$pruned.labels
```

| Parameter | Options | Description |
|-----------|---------|-------------|
| `de.method` | "wilcox", "t", "binom" | DE method for marker gene selection. "wilcox" is default and recommended. |
| `prune` | TRUE/FALSE | Whether to set low-confidence labels to NA. **Always use TRUE** for production. |
| `labels` | `ref$label.main`, `ref$label.fine` | Annotation granularity. `label.fine` only available for some references. |

#### Option B: Using skill wrapper

```r
seurat_obj <- run_singler_annotation(
  seurat_obj,
  ref = ref,
  label_col = "label.main",
  de.method = "wilcox",
  prune = TRUE,
  assay = "RNA"   # Seurat v5: specify assay if not default
)
# Adds: SingleR_label, SingleR_pruned, stores full pred in @misc$SingleR_pred
```

**What the wrapper adds**:
- Validates input is a Seurat object
- Auto-converts to SCE internally (supports Seurat v5 via `assay=` parameter)
- Validates `label_col` exists in reference before running
- Warns if gene overlap < 50% (catches ENSEMBL vs symbol mismatch)
- Stores full prediction object in `@misc$SingleR_pred` for downstream quality plots
- Defaults to `MonacoImmuneData` if no reference provided (human immune)

---

### Step 4: Quality Control

**Goal**: Assess annotation confidence and identify problematic cells.

```r
# Retrieve prediction object
pred <- seurat_obj@misc$SingleR_pred

# Score heatmap — shows per-cell scores across all cell types
plotScoreHeatmap(pred)

# Delta distribution — shows confidence margin between best and second-best label
plotDeltaDistribution(pred)

# Using skill helper (plots both + optional PDF output)
plot_singler_quality(seurat_obj, output_file = "singler_qc.pdf")
```

**How to interpret**:
- **Score heatmap**: Each row = one cell. Colors = correlation scores. Dark diagonal = confident assignment.
- **Delta distribution**: Higher delta = more confident. Bimodal distribution suggests some cells are ambiguous.
- **Low-confidence cells**: Shown as NA in `pruned.labels`. These are cells where the top score was not significantly better than the second-best.

---

### Step 5: Filter by Confidence

**Goal**: Remove or relabel low-confidence predictions.

```r
# Using skill helper
seurat_obj <- filter_singler_by_confidence(seurat_obj)
# Adds SingleR_filtered: "Unknown" for pruned (NA) cells, original label otherwise

# Manual equivalent
seurat_obj$SingleR_filtered <- ifelse(
  is.na(seurat_obj$SingleR_pruned),
  "Unknown",
  seurat_obj$SingleR_label
)
```

**What to do with "Unknown" cells**:
- Exclude from downstream differential expression
- Re-cluster them separately to find subpopulations
- Try a different reference (e.g. switch from `label.main` to `label.fine`)
- Use marker-based annotation as a secondary check

---

### Step 6: Visualize Results

```r
# UMAP with SingleR labels
DimPlot(seurat_obj, group.by = "SingleR_label", label = TRUE)

# Compare with clusters
DimPlot(seurat_obj, group.by = "seurat_clusters", label = TRUE)

# Proportions by sample/group
table(seurat_obj$SingleR_filtered, seurat_obj$sample)
```

---

## Complete Pipeline via Skill Wrapper

```r
source("scripts/r/singler_annotation.R")

# Load reference
ref <- load_singler_reference("monaco")

# Annotate
seurat_obj <- run_singler_annotation(seurat_obj, ref = ref, label_col = "label.main")

# Quality check
plot_singler_quality(seurat_obj, output_file = "singler_qc.pdf")

# Filter low confidence
seurat_obj <- filter_singler_by_confidence(seurat_obj)

# View results
table(seurat_obj$SingleR_filtered)
```

---

## Skill-Provided Helper Functions

Source: `scripts/r/singler_annotation.R`

| Function | Parameters | What it adds |
|----------|-----------|-------------|
| `run_singler_annotation(seurat_obj, ref = NULL, label_col = "label.main", de.method = "wilcox", prune = TRUE, assay = NULL)` | `ref` defaults to `MonacoImmuneData`; `assay` for Seurat v5 | Validates input, auto-converts SCE, checks gene overlap, stores full pred object |
| `load_singler_reference(name)` | `"monaco"`, `"blueprint"`, `"hpca"`, `"immgen"`, `"dice"`, `"novershtern"`, `"mouse"` | Shorthand loader for common celldex references |
| `filter_singler_by_confidence(seurat_obj)` | — | Replaces pruned (NA) labels with "Unknown" |
| `plot_singler_quality(seurat_obj, output_file = NULL)` | — | Plots score heatmap + delta distribution; optionally saves to PDF |

---

## Official API — Agents Often Miss These

| Function / Pattern | Key Point |
|-------------------|-----------|
| `ref$label.main` vs `ref$label.fine` | `label.fine` has more subtypes but is only available for some references. Check `names(colData(ref))` first. |
| `prune = TRUE` | **Always enable**. Without pruning, every cell gets a label even if confidence is near-random. |
| `pred$pruned.labels` | NA means "SingleR was not confident". Do NOT treat NA as a cell type. |
| `pred$scores` | Full score matrix. Use for custom QC or identifying cells with similar scores across multiple types. |
| `labels = ref$label.main` | Must match the column name exactly. Common mistake: using `"label_main"` or `"Label.Main"`. |
| Cross-species | Using human ref on mouse data without ortholog mapping produces garbage. Check species match. |
| Gene symbol match | If your data uses ENSEMBL IDs but reference uses gene symbols, annotation will fail silently (most cells get "Unknown" or wrong labels). |

---

## Common Pitfalls

1. **Wrong reference for tissue**: Using `MonacoImmuneData` (blood only) on solid tumor data will mislabel stromal/epithelial cells as immune.
2. **Wrong label column**: Using `label.fine` on a reference that only has `label.main` throws an error.
3. **Species mismatch**: Human reference on mouse data = meaningless results. Always verify.
4. **Gene ID mismatch**: ENSEMBL vs gene symbol mismatch causes near-zero overlap and poor annotation.
5. **Forgetting prune**: `prune = FALSE` assigns every cell a label, including those with no good match.
6. **Over-interpreting fine labels**: `label.fine` subtypes may not generalize across datasets. Validate with known markers.

---

## Hyperparameter Guide

| Parameter | Default | When to Change |
|-----------|---------|---------------|
| `de.method` | "wilcox" | "t" for speed on very large datasets; "binom" for UMI count data |
| `label_col` | "label.main" | "label.fine" for detailed immune subtyping (Monaco, ImmGen only) |
| `prune` | TRUE | Only set FALSE if you need every cell labeled and will filter manually later |

---

## Troubleshooting

### All cells labeled as "Unknown"

```r
# Check gene overlap
sum(rownames(sce) %in% rownames(ref)) / nrow(ref)
# Should be > 50%. If very low, check gene ID format (ENSEMBL vs symbol).
```

### Poor annotation quality

```r
# Try different reference
ref <- celldex::HumanPrimaryCellAtlasData()  # broader coverage

# Or use finer/coarser labels
pred <- SingleR(test = sce, ref = ref, labels = ref$label.fine)
```

### "Unknown reference" error from load_singler_reference

Valid names are: `monaco`, `blueprint`, `hpca`, `immgen`, `dice`, `novershtern`, `mouse`. Use exact lowercase names.

---

## Related Skills

- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) - Automated annotation with pre-trained models (Python)
- [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/SKILL.md) - Marker-based annotation (R)
- [bio-single-cell-annotation-markers](../bio-single-cell-annotation-markers/SKILL.md) - Manual marker-based annotation

## References

1. Aran et al. (2019). Reference-based analysis of lung single-cell sequencing reveals a transitional profibrotic macrophage. *Nature Immunology*, 20(2), 163-172.
2. SingleR Bioconductor: https://bioconductor.org/packages/SingleR
3. celldex reference datasets: https://bioconductor.org/packages/celldex
