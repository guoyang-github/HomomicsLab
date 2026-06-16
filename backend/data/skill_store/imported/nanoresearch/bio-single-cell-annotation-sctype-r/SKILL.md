---
name: bio-single-cell-annotation-sctype-r
description: Marker-based cell type annotation for scRNA-seq using the ScType algorithm in R. Supports 15+ built-in tissue databases, custom marker sets, and automatic tissue detection. Compatible with Seurat v4 and v5.
tool_type: r
primary_tool: ScType
supported_tools: [Seurat, dplyr, openxlsx]
languages: [r]
keywords: ["single-cell", "annotation", "sctype", "marker-based", "seurat", "r", "cell-type"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.0"
  seurat: ">=4.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.0 | |
| Seurat | >= 4.0 | v4 and v5 auto-detected |
| dplyr | >= 1.0 | For score aggregation |
| openxlsx | >= 4.0 | For reading marker databases |
| HGNChelper | >= 0.8 | For gene symbol correction |

## Installation

```r
install.packages(c("dplyr", "openxlsx", "HGNChelper"))
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("Seurat")
```

## Skill Overview

ScType assigns cell types to clusters based on curated marker gene sets. It scores each cluster for each cell type using positive markers (must be expressed) and negative markers (must NOT be expressed), then assigns the highest-scoring type. Low-confidence assignments are labeled "Unknown".

**Core workflow**: Source functions → Prepare Seurat object (clustered) → Run annotation → Review / adjust threshold → Visualize

**When to use**:
- Quick annotation without a matched scRNA-seq reference dataset
- Marker-based classification with interpretable, biologist-friendly rules
- Built-in marker database covers your tissue (15+ tissues available)
- Need to validate clustering results against known markers

**When NOT to use**:
- No clustering has been performed — ScType assigns per **cluster**, not per cell
- Your tissue is not in the built-in database and you don't have custom markers
- Gene names are not HGNC symbols (e.g., Ensembl IDs, mouse MGI symbols without conversion)
- Need single-cell resolution annotation — ScType assigns the same label to all cells in a cluster
- Highly novel cell types with no known markers — use automated methods (SingleR, scArches) instead

## Quick Reference

| Goal | Entry Point | Key Difference |
|------|-------------|---------------|
| Built-in markers | `run_sctype_annotation(seurat_obj, tissue = "Immune system")` | Uses ScTypeDB_full.xlsx or ScTypeDB_short.xlsx |
| Auto-detect tissue | `run_sctype_annotation(seurat_obj, tissue = NULL)` | Tests all tissues, picks best match by mean score |
| Custom markers (R list) | `run_sctype_annotation(seurat_obj, marker_list = my_list)` | Bypasses database entirely |
| Custom markers (Excel) | `run_sctype_annotation(seurat_obj, marker_file = "...", tissue = "...")` | Uses your own ScTypeDB-format file |

## Core Workflow (Step-by-Step)

### Step 1: Prepare Seurat Object

**Goal**: Clustered Seurat object with `seurat_clusters` (or custom cluster column).

```r
library(Seurat)

# Standard preprocessing pipeline (if starting from raw counts)
seurat_obj <- CreateSeuratObject(counts = raw_counts)
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj)
seurat_obj <- ScaleData(seurat_obj)
seurat_obj <- RunPCA(seurat_obj, features = VariableFeatures(object = seurat_obj))
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:10)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.8)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:10)

# REQUIRED: clustering must exist before annotation
stopifnot("seurat_clusters" %in% colnames(seurat_obj@meta.data))
```

**After this step**: `seurat_obj` has clusters in `meta.data$seurat_clusters`.

---

### Step 2: Source ScType Functions

**Goal**: Load skill functions into R session.

```r
# Set working directory to skill root, or use absolute paths
source("scripts/r/sctype_annotation.R")
```

**What this sources**: `run_sctype_annotation()`, `get_available_tissues()`, `create_marker_list()`.

**Dependencies auto-sourced**: `sctype_annotation.R` automatically sources `gene_sets_prepare.R` and `sctype_score.R` from the same `scripts/r/` directory. It searches for `scripts/r/` relative to the working directory.

**⚠️ Path sensitivity**: If you run from `examples/`, the auto-detection of `scripts/r/` may fail. Either `setwd()` to skill root or source with absolute paths.

---

### Step 3A: Annotate with Built-in Markers

**Goal**: Assign cell types using the curated ScType database.

```r
# List available tissues
get_available_tissues(db_source = "full")
# Returns: "Immune system" "PBMC" "Brain" "Lung" "Liver" ...

# Run annotation
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    assay = "RNA",              # Or "SCT" if using SCTransform
    slot = "data",              # "data" = normalized, "scale.data" = scaled, "counts" = raw
    cluster_col = "seurat_clusters",
    output_col = "sctype_cell_type",
    score_threshold = NULL,     # NULL = ncells/4 (default); set numeric for custom
    return_scores = FALSE,
    plot_results = FALSE
)
```

| Parameter | Default | When to Change |
|-----------|---------|----------------|
| `slot` | `"data"` | Use `"scale.data"` if clusters were defined on scaled data; `"counts"` for raw |
| `score_threshold` | `NULL` | Lower (e.g., 5) if many "Unknown"; raise (e.g., 20) if too many false positives |
| `db_source` | `"full"` | Use `"short"` for faster testing |

**After this step**: `seurat_obj@meta.data$sctype_cell_type` contains annotations.

---

### Step 3B: Auto-Detect Tissue Type

**Goal**: When tissue origin is unknown, let ScType test all tissues and pick the best match.

```r
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = NULL,          # Triggers auto-detection
    db_source = "short",    # Use short DB for faster auto-detect
    slot = "data"
)

# The auto-detected tissue is printed to console:
# "Auto-detected tissue: Immune system"
```

**What auto-detection does**: For each tissue in the database, calculates mean top-cluster score. The tissue with the highest mean score wins. A barplot is generated showing all tissue scores.

**⚠️ Auto-detect can be wrong** for complex tissues (e.g., tumor microenvironment may score higher on "Immune system" than "Lung" even if sample is from lung). Always validate results.

**After this step**: Same as 3A, but tissue was auto-selected.

---

### Step 3C: Use Custom Markers

**Goal**: For tissues not in the built-in database (e.g., specific cancer subtypes).

```r
# Method 1: R list
my_markers <- create_marker_list(
    positive_markers = list(
        "Tumor_Epithelial" = c("EPCAM", "KRT8", "KRT18"),
        "Fibroblast" = c("COL1A1", "COL1A2", "VIM"),
        "T_Cell" = c("CD3D", "CD3E", "CD247"),
        "Macrophage" = c("CD68", "CD14", "CSF1R")
    ),
    negative_markers = list(
        "Tumor_Epithelial" = c("VIM", "PECAM1"),
        "Fibroblast" = c("EPCAM", "PECAM1"),
        "T_Cell" = c("CD68", "EPCAM"),
        "Macrophage" = c("CD3D", "EPCAM")
    )
)

seurat_obj <- run_sctype_annotation(
    seurat_obj,
    marker_list = my_markers,
    slot = "data"
)

# Method 2: Custom Excel file (ScTypeDB format)
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    marker_file = "path/to/custom_markers.xlsx",
    tissue = "MyTissue",    # Must match tissueType column in Excel
    slot = "data"
)
```

**Excel format required**:

| Column | Description |
|--------|-------------|
| `tissueType` | Tissue category (must match `tissue` parameter) |
| `cellName` | Cell type name |
| `geneSymbolmore1` | Positive markers (comma-separated) |
| `geneSymbolmore2` | Negative markers (comma-separated) |

**After this step**: Same as 3A, but using your custom markers.

---

### Step 4: Review and Adjust Confidence

**Goal**: Check for too many "Unknown" or suspicious assignments.

```r
# Check distribution
table(seurat_obj$sctype_cell_type)
prop.table(table(seurat_obj$sctype_cell_type))

# If >30% are "Unknown", try lowering threshold or different slot
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    slot = "scale.data",        # Try scaled data instead
    score_threshold = 5,        # Lower = more permissive
    output_col = "sctype_relaxed"
)

# Compare
comparison <- table(
    seurat_obj$seurat_clusters,
    seurat_obj$sctype_cell_type,
    seurat_obj$sctype_relaxed
)
```

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| >50% "Unknown" | Threshold too strict or markers don't match data | Lower `score_threshold`, try `slot = "scale.data"`, verify tissue |
| All clusters same type | One cell type dominates markers | Check marker specificity; add negative markers |
| Obvious mismatch | Wrong tissue selected | Use auto-detect or try related tissues |

---

### Step 5: Visualize

**Goal**: Plot annotations on UMAP.

```r
# If plot_results = TRUE was passed, UMAP plot is auto-generated
# Otherwise, plot manually:
if ("umap" %in% names(seurat_obj@reductions)) {
    DimPlot(seurat_obj, group.by = "sctype_cell_type", label = TRUE, repel = TRUE)
}

# Compare clusters vs annotations side by side
p1 <- DimPlot(seurat_obj, group.by = "seurat_clusters", label = TRUE) + ggtitle("Clusters")
p2 <- DimPlot(seurat_obj, group.by = "sctype_cell_type", label = TRUE) + ggtitle("ScType")
p1 + p2
```

---

## Complete Pipeline

```r
library(Seurat)
library(dplyr)

# 1. Load data
seurat_obj <- readRDS("your_clustered_data.rds")

# 2. Source ScType
source("scripts/r/sctype_annotation.R")

# 3. Annotate with auto-detect or known tissue
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",   # or NULL for auto-detect
    slot = "data",
    score_threshold = NULL,
    return_scores = TRUE,
    plot_results = TRUE
)

# 4. Review
print(table(seurat_obj$sctype_cell_type))

# 5. Save
saveRDS(seurat_obj, "annotated_data.rds")
```

## Skill-Provided Functions

Source: `scripts/r/` directory

### Main Annotation

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_sctype_annotation(seurat_obj, ...)` | `tissue`, `marker_list`, `marker_file`, `slot`, `score_threshold`, `cluster_col`, `output_col` | **Primary entry point**. Sources deps automatically. Detects Seurat v4 vs v5 (`inherits(assay, "Assay5")`). Returns Seurat with annotation column in `meta.data` |
| `get_available_tissues(db_source)` | `"full"` or `"short"` | Reads Excel DB and returns unique `tissueType` values. Searches for `assets/markers/` in multiple parent directories |
| `create_marker_list(pos, neg)` | `positive_markers` (named list), `negative_markers` (named list) | Creates `list(gs_positive = ..., gs_negative = ...)` format expected by scoring functions. Negative defaults to empty character vectors |

### Core Algorithm (auto-sourced)

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `sctype_score(scRNAseqData, gs, gs2, ...)` | `scaled` (is matrix already z-scored?), `gene_names_to_uppercase` | Calculates cell-type scores per cell. Weights markers by sensitivity (rarity penalty). Positive markers add; negative markers subtract. Returns matrix: cell_types × cells |
| `gene_sets_prepare(path, cell_type)` | `path_to_db_file`, `cell_type` | Reads ScTypeDB Excel, filters to tissue, corrects gene symbols via **HGNChelper::checkGeneSymbols**, parses comma-separated markers into R lists |
| `auto_detect_tissue_type(path, seuratObject, scaled, assay)` | `path_to_db_file`, `seuratObject` | Iterates all tissues in DB, scores each, returns ranked data frame. Produces barplot of tissue scores |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `run_sctype_annotation()` sources dependencies | This function calls `source(file.path(script_dir, "gene_sets_prepare.R"))` and `source(file.path(script_dir, "sctype_score.R"))` internally. You do NOT need to source them separately unless using low-level functions directly. |
| `source("scripts/r/sctype_annotation.R")` path | The function searches for `scripts/r/` relative to `getwd()`. If your working directory is `examples/`, it tries `../scripts/r/`. Use absolute paths or `setwd()` to skill root for reliability. |
| Seurat v5 detection | Uses `inherits(seurat_obj[[assay]], "Assay5")`. If this fails on your Seurat version, the v4 branch (`seurat_obj[[assay]]@counts`) may error. Verify with `class(seurat_obj[["RNA"]])`. |
| `slot = "data"` vs `"scale.data"` | `"data"` = log-normalized (Seurat default). `"scale.data"` = z-scored. ScType internally z-scores if `scaled = FALSE`, so `"data"` is usually correct. Use `"scale.data"` only if you already scaled and want to skip internal scaling. |
| Score formula | For each cell type and cell: `sum(positive_marker_zscores) / sqrt(n_pos) + sum(negative_marker_zscores * -1) / sqrt(n_neg)`. Rare markers (present in fewer cell types) get higher weight. |
| Default threshold `ncells/4` | A cluster with 100 cells needs score > 25 to avoid "Unknown". This is cluster-size-dependent by design — larger clusters need stronger evidence. |
| `gene_names_to_uppercase = TRUE` | ScType converts all gene names to UPPERCASE internally. If your data uses mixed case (e.g., mouse genes), this ensures matching. |
| `HGNChelper::checkGeneSymbols` | `gene_sets_prepare()` **automatically corrects outdated/synonym gene symbols** using HGNChelper. This is why some marker names in output may differ from input. |
| `sctype_wrapper.R` | Contains `run_sctype()` — an older wrapper that downloads code from GitHub on every run. **Do not use**; prefer `run_sctype_annotation()` which uses local skill files. |

## Common Pitfalls

1. **Forgetting to cluster first**  
   ScType assigns labels to **clusters**, not individual cells. If `seurat_clusters` is missing, it errors. Run `FindClusters()` before annotation.

2. **Gene name case mismatch**  
   ScType uppercases all gene names internally. Human data is usually fine. Mouse data with lowercase gene names (e.g., `Cd3d`) will still match if uppercased, but ensure your Seurat object uses the same naming convention as the markers.

3. **Using `slot = "counts"` without scaling**  
   If you pass raw counts (`slot = "counts"`), set `scaled = FALSE` conceptually (though `run_sctype_annotation()` handles this automatically via `slot == "scale.data"` check). Raw counts will be z-scored internally.

4. **Over-relying on auto-detect for complex tissues**  
   Auto-detection picks the tissue with the highest average cluster score. Tumor samples may auto-detect as "Immune system" due to infiltrating immune cells, even if the tissue is "Lung". Validate with known biology.

5. **Not providing negative markers for custom lists**  
   `create_marker_list()` allows `negative_markers = NULL`, but negative markers significantly improve specificity. Always include them when possible.

6. **Running from wrong working directory**  
   `source("scripts/r/sctype_annotation.R")` is relative to `getwd()`. Running from `examples/` without adjusting the path is a common failure mode.

## Troubleshooting

### `Error: Please install HGNChelper`

```r
install.packages("HGNChelper")
```

`gene_sets_prepare()` now checks for HGNChelper and errors with clear message if missing.

### `Error in source(...): cannot open file 'scripts/r/sctype_annotation.R'`

Wrong working directory.

```r
# Fix: use absolute path or setwd()
setwd("/path/to/bio-single-cell-annotation-sctype-r")
source("scripts/r/sctype_annotation.R")
```

### All cells labeled "Unknown"

```r
# Debug: try different slot and lower threshold
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    slot = "scale.data",
    score_threshold = 5
)

# Verify gene names are uppercase symbols
head(rownames(seurat_obj))
# Should be: "CD3D" "CD3E" "CD4" ...
```

### `Error: could not find function "group_by"` / `"slice_max"`

dplyr not loaded. `auto_detect_tissue_type()` now uses `dplyr::` prefix, but `run_sctype_annotation()` also uses dplyr. Ensure dplyr is installed and loaded.

```r
library(dplyr)
```

### Seurat v5 `LayerData` not found

Your Seurat version may be too old (< 4.9) or too new with API changes.

```r
# Check version
packageVersion("Seurat")

# Manual workaround: extract matrix yourself and pass to sctype_score
expr <- as.matrix(GetAssayData(seurat_obj, layer = "data"))
# Then use low-level API (see usage-guide.md)
```

### `Error: Built-in database not found`

Database file not found relative to working directory.

```r
# Fix: verify file exists
file.exists("assets/markers/ScTypeDB_full.xlsx")

# If running from examples/, adjust path
source("../scripts/r/sctype_annotation.R")
```

## Related Skills

- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) — Python-based; good for large-scale automated annotation
- [bio-single-cell-annotation-singler-r](../bio-single-cell-annotation-singler-r/SKILL.md) — R-based reference-mapping annotation
- [bio-single-cell-annotation-markers](../bio-single-cell-annotation-markers/SKILL.md) — Simple marker-based annotation without ScType scoring
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — Clustering step that must precede ScType annotation

## References

1. Ianevski et al. (2022). Fully-automated and ultra-fast cell-type identification using specific marker combinations from single-cell transcriptomic data. *Nature Communications* 13, 1246. https://doi.org/10.1038/s41467-022-28803-w
2. ScType GitHub: https://github.com/IanevskiAleksandr/sc-type
