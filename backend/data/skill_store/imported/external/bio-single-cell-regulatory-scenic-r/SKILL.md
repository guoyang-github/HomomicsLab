---
name: bio-single-cell-regulatory-scenic-r
description: SCENIC infers gene regulatory networks and cell type specific regulons from single-cell RNA-seq data using R. Includes TF validation, correlation-based network alternative, GENIE3 resume capability, and binarization support.
tool_type: r
primary_tool: SCENIC
supported_tools: [Seurat, AUCell]
languages: [r]
keywords: ["single-cell", "regulatory-network", "TF", "regulon", "scenic", "R", "genie3", "binarization"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.2.0"
  scenic: ">=1.3"
  seurat: ">=4.3.0"
  aucell: ">=1.16"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| SCENIC | >= 1.3 | Core framework (Bioconductor) |
| AUCell | >= 1.16 | Regulon scoring |
| Seurat | >= 4.3.0 | Optional; v4 and v5 compatible |
| reshape2 | -- | For binarization |

## Installation

```r
BiocManager::install("SCENIC")
install.packages("reshape2")
```

## Skill Overview

SCENIC (Single-Cell rEgulatory Network Inference and Clustering) reconstructs gene regulatory networks and identifies stable cell states based on transcription factor regulon activity. Pipeline: co-expression network → motif pruning (RcisTarget) → cell scoring (AUCell).

**When to use**:
- Infer TF regulons driving cell identity from scRNA-seq
- Identify cell-type-specific master regulators
- Map regulatory states across conditions

**When NOT to use**:
- < 100 cells per type — AUCell needs statistical power
- Only need marker gene expression — use standard Seurat instead
- Raw counts unavailable — SCENIC needs counts for co-expression
- > 50k cells on limited hardware — GENIE3 takes hours and significant RAM

## Core Workflow

### Step 1: Database Setup (First Time Only)

**Goal**: Ensure cisTarget databases are available (~1 GB per type).

Databases are cached hierarchically: skill `assets/` first, then `~/cisTarget/` fallback.

```r
source("scripts/r/scenic_analysis.R")

# Auto-download if missing (recommended)
scenicOptions <- init_scenic_auto(
  org = "hgnc",              # "hgnc" (human), "mmusculus" (mouse), "dmel" (fly)
  dbDir = "cisTarget",
  db_types = "10kb",         # "500bp", "10kb", or both
  motif_version = "v10",     # "v9" or "v10"
  download_if_missing = TRUE,
  nCores = 4
)
```

**Database sizes:**

| Type | Size | Scope |
|------|------|-------|
| 10kb | ~1.0 GB | Promoters + enhancers |
| 500bp | ~0.5 GB | Promoters only |

**CRITICAL**: `init_scenic_auto()` checks `assets/` first (if running within skill directory), then `~/cisTarget/`. If you run from elsewhere, it falls back to home. Verify with `check_cistarget_databases()`.

---

### Step 2: Initialize and Validate

**Goal**: Set up SCENIC options and verify TF list overlap.

**Input requirements**:
- `exprMat`: Matrix with **raw counts** (genes x cells)
- Gene names must be **gene symbols** (e.g., "TP53"), not Ensembl IDs

```r
# Get expression matrix from Seurat
if (packageVersion("SeuratObject") >= "5.0.0") {
  exprMat <- GetAssayData(seurat_obj, layer = "counts")
} else {
  exprMat <- GetAssayData(seurat_obj, slot = "counts")
}

# Initialize (if not using init_scenic_auto)
scenicOptions <- init_scenic("hgnc", dbDir = "cisTarget", nCores = 4)

# Validate TF overlap — critical sanity check
tfList <- getDbTfs(scenicOptions)
validation <- validate_tf_list(exprMat, tfList, minOverlapPct = 80)
# overlapPct should be > 80%. If low, check gene ID format.
```

---

### Step 3: Run Pipeline

**Goal**: Infer co-expression network, create regulons, and score cells.

**Choose your network method:**

| Method | Speed | Memory | Best For |
|--------|-------|--------|----------|
| GENIE3 (default) | Hours | High | Publication quality, < 10k cells |
| Correlation | Minutes | Low | Large datasets, quick screening |
| Resume GENIE3 | Skips if exists | — | Interrupted runs |

```r
# Option A: GENIE3 (default, most accurate)
scenicOptions <- run_scenic_pipeline(
  exprMat, scenicOptions,
  runGenie3 = TRUE,
  nParts = 10,              # More parts = less memory per part
  weightThreshold = 0.001,
  topThr = 0.005,
  nTopTargets = 50,
  minGenes = 20
)

# Option B: Resume interrupted GENIE3
scenicOptions <- run_scenic_pipeline(
  exprMat, scenicOptions,
  runGenie3 = TRUE,
  resumePreviousRun = TRUE   # Skips GENIE3 if genie3ll file exists
)

# Option C: Correlation network (fast)
scenicOptions <- run_scenic_pipeline(
  exprMat, scenicOptions,
  useCorrelationNetwork = TRUE,
  corMethod = "spearman",
  corThreshold = 0.03,
  topNPerTF = 50
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `nParts` | 10 | GENIE3 parallel chunks. Increase for lower memory |
| `weightThreshold` | 0.001 | Min edge weight for co-expression modules |
| `topThr` | 0.005 | Top quantile for co-expression pairs |
| `nTopTargets` | 50 | Top targets per TF to keep |
| `minGenes` | 20 | Min genes per module for RcisTarget. Lower for small datasets |

**What `run_scenic_pipeline` adds over raw SCENIC:**
- Built-in TF validation before running
- Orchestrates all 5 steps with progress messages
- Sets module-creation parameters (`weightThreshold`, `topThr`, `nTopTFs`, `nTopTargets`) in `scenicOptions@settings` (where SCENIC reads them) instead of passing them as invalid direct arguments
- Resume support for GENIE3
- Correlation network as GENIE3 alternative

---

### Step 4: Binarization (Optional)

**Goal**: Convert continuous AUC scores to binary active/inactive calls.

```r
scenicOptions <- run_aucell_binarization(
  scenicOptions,
  smallestPopPercent = 0.01    # Min 1% of cells must pass threshold
)

binaryMat <- load_binary_activity(scenicOptions)  # regulons x cells, 0/1
```

Use when you need crisp "active vs inactive" calls rather than continuous scores.

---

### Step 5: Add Results to Seurat

```r
seurat_obj <- add_scenic_to_seurat(
  seurat_obj, scenicOptions,
  assayName = "SCENIC",
  addBinary = TRUE              # Also adds "SCENIC_binary" assay
)
```

**What this adds over manual integration:**
- Seurat v4/v5 compatible (`slot =` vs `layer =` auto-detection)
- Cell name alignment check
- Graceful fallback if binary activity is missing
- Stores AUC values in `data` slot/layer

---

### Step 6: Analysis

```r
# Top regulons per cluster
top_regulons <- get_top_regulons(
  seurat_obj, group_by = "seurat_clusters", top_n = 10
)

# Cell-type-specific regulons (specificity = mean_in / mean_out)
specific <- find_celltype_specific_regulons(
  seurat_obj, group_by = "cell_type", min_auc = 0.05
)

# Active regulons per cell type (requires binarization)
cellInfo <- data.frame(
  cellType = seurat_obj$cell_type,
  row.names = colnames(seurat_obj)
)
active <- get_active_regulons_by_celltype(
  scenicOptions, cellInfo,
  cellTypeCol = "cellType",
  minActiveFrac = 0.25          # Active in 25%+ of cells in that type
)
```

**Regulon naming**: `"TF_NAME (n_targets)g"` — e.g., `"SOX10 (45g)"`. Plotting `"SOX10"` triggers a missing-regulon warning.

---

### Step 7: Visualization

```r
# Regulon activity on UMAP
plot_regulon_activity(
  seurat_obj,
  regulons = c("SOX10 (45g)", "MITF (32g)"),
  reduction = "umap"
)

# Heatmap of top regulons
DefaultAssay(seurat_obj) <- "SCENIC"
DoHeatmap(seurat_obj, features = unique(top_regulons$regulon)[1:20])
```

## Complete Pipeline

```r
source("scripts/r/scenic_analysis.R")
library(SCENIC)
library(Seurat)

seurat_obj <- readRDS("your_data.rds")

if (packageVersion("SeuratObject") >= "5.0.0") {
  exprMat <- GetAssayData(seurat_obj, layer = "counts")
} else {
  exprMat <- GetAssayData(seurat_obj, slot = "counts")
}

scenicOptions <- init_scenic_auto("hgnc", dbDir = "cisTarget", nCores = 4)

validation <- validate_tf_list(exprMat, getDbTfs(scenicOptions))

scenicOptions <- run_scenic_pipeline(
  exprMat, scenicOptions,
  runGenie3 = TRUE, nParts = 10
)

scenicOptions <- run_aucell_binarization(scenicOptions)

seurat_obj <- add_scenic_to_seurat(seurat_obj, scenicOptions, addBinary = TRUE)

top_regulons <- get_top_regulons(seurat_obj, group_by = "seurat_clusters", top_n = 10)

plot_regulon_activity(seurat_obj, regulons = head(top_regulons$regulon, 3))
```

## Skill-Provided Functions

### Initialization & Pipeline

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `init_scenic_auto(org, dbDir, ...)` | `download_if_missing`, `db_types` | Checks databases, downloads if missing, initializes SCENIC |
| `init_scenic(org, dbDir, ...)` | `datasetTitle`, `nCores` | Basic initialization (assumes databases exist) |
| `run_scenic_pipeline(exprMat, scenicOptions, ...)` | `runGenie3`, `useCorrelationNetwork`, `resumePreviousRun` | Full 5-step pipeline with TF validation |
| `run_correlation_network(exprMat, scenicOptions, ...)` | `corMethod`, `corThreshold` | Spearman/Pearson alternative to GENIE3 |
| `validate_tf_list(exprMat, tfList, ...)` | `minOverlapPct` | Overlap check; warns if < 80% |

### Post-Processing

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_aucell_binarization(scenicOptions, ...)` | `smallestPopPercent` | Thresholds AUC to binary 0/1 per regulon |
| `load_binary_activity(scenicOptions)` | `nonDuplicated` | Loads binary matrix; checks file exists |
| `add_scenic_to_seurat(seurat_obj, scenicOptions, ...)` | `assayName`, `addBinary` | Adds AUC as assay; v4/v5 compatible; cell-alignment safe |
| `get_top_regulons(seurat_obj, ...)` | `group_by`, `top_n` | Averages AUC per group, returns top N |
| `find_celltype_specific_regulons(seurat_obj, ...)` | `group_by`, `min_auc` | Specificity = mean_in / mean_out |
| `get_active_regulons_by_celltype(scenicOptions, cellInfo, ...)` | `cellTypeCol`, `minActiveFrac` | Uses binary activity; cell overlap validation |
| `plot_regulon_activity(seurat_obj, regulons, ...)` | `reduction` | FeaturePlot wrapper; missing regulon warning |
| `load_scenic_results(scenicOptions, type)` | `type`: aucell/regulons/modules/binary | Abstracts SCENIC internal file names |

### Database Management

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `check_cistarget_databases(org, dbDir, ...)` | `db_types`, `motif_version` | Returns availability + `all_ready` flag |
| `download_cistarget_databases(org, dbDir, ...)` | `db_types`, `force`, `timeout` | Downloads with progress; resume-friendly |
| `list_cistarget_databases(dbDir)` | | Data frame of all organisms/types status |
| `get_cistarget_dir(dbDir, ...)` | `prefer_skill_assets` | Hierarchical lookup: assets/ → home/ |
| `list_cistarget_cache_locations()` | | Returns `skill_assets` and `home_cache` paths |
| `migrate_databases_to_skill_assets(...)` | `home_dir`, `dry_run` | Copies databases from home to skill assets/ |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `init_scenic_auto()` | Checks `assets/` first, then `~/cisTarget/`. Downloads ~1 GB per db type if missing. Set `download_if_missing = FALSE` to fail fast. |
| `run_scenic_pipeline(..., resumePreviousRun = TRUE)` | Only skips GENIE3 if `genie3ll` file exists. **Does NOT resume correlation networks.** |
| `run_scenic_pipeline(..., useCorrelationNetwork = TRUE)` | Ignores `runGenie3`. Correlation result is saved as `genie3ll` for downstream compatibility. |
| `add_scenic_to_seurat()` | Creates assay with `data = auc_matrix`, so AUC values live in `data` slot/layer. `get_top_regulons` reads from `data`, not `counts`. |
| Regulon names | Format is `"TF_NAME (n_targets)g"` — e.g., `"SOX10 (45g)"`. Plotting `"SOX10"` triggers missing-regulon warning. |
| `getDbTfs(scenicOptions)` | Returns TF list from database. If overlap < 50%, your gene symbols probably don't match (e.g., Ensembl IDs). |
| `SCENIC::loadInt(scenicOptions, "aucell_regulonAUC")` | Returns `aucellResults` object. Use `AUCell::getAUC()` to extract matrix. Our `load_scenic_results(type = "aucell")` handles this. |

## Common Pitfalls

1. **Missing cisTarget databases**  
   `init_scenic()` fails with "directory not found". Use `init_scenic_auto()` or run `download_cistarget_databases()` first.

2. **Gene IDs are Ensembl, not symbols**  
   SCENIC databases use HGNC/MGI symbols. `validate_tf_list()` shows < 50% overlap. Convert IDs before running.

3. **Regulon names mismatch in plotting**  
   SCENIC outputs `"SOX10 (45g)"` but agents often write `"SOX10"`. `plot_regulon_activity()` warns and filters missing names.

4. **GENIE3 takes hours and lots of RAM**  
   For > 10k cells, use `useCorrelationNetwork = TRUE` or increase `nParts` to 20+.

5. **`resumePreviousRun` does not resume correlation networks**  
   Resume only checks for `genie3ll` file. Correlation network always runs fresh.

6. **Binarization requires completed pipeline**  
   `run_aucell_binarization()` reads `aucell_regulonAUC`. Running before `run_scenic_pipeline()` throws "Regulon AUC not found".

7. **Binary assay naming**  
   `add_scenic_to_seurat(addBinary = TRUE)` creates `"SCENIC_binary"` assay. Use this name for binary heatmaps.

## Troubleshooting

### `cisTarget database directory not found`

```r
scenicOptions <- init_scenic_auto("hgnc", dbDir = "cisTarget", download_if_missing = TRUE)
```

### `Low TF overlap (45% < 80%)`

Gene IDs don't match database format. Check:
```r
head(rownames(exprMat))   # Should be "TP53" "BRCA1" ... not "ENSG..."
```

### Download fails or times out

```r
download_cistarget_databases("hgnc", dbDir = "cisTarget", timeout = 3600)
# Or download manually from https://resources.aertslab.org/cistarget/
```

### `Invalid Feather file`

```r
download_cistarget_databases("hgnc", dbDir = "cisTarget", force = TRUE)
```

### GENIE3 out of memory

```r
# More parts = less memory per part
scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions, runGenie3 = TRUE, nParts = 20)

# Or use correlation
scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions, useCorrelationNetwork = TRUE)
```

### No regulons found after RcisTarget

```r
scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions, minGenes = 10)  # default 20
```

### `Regulon AUC not found` when binarizing

```r
# Pipeline was not completed
scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions)
scenicOptions <- run_aucell_binarization(scenicOptions)
```

### `No matching cells between Seurat object and SCENIC results`

```r
all(colnames(seurat_obj) == colnames(exprMat))
```

## Related Skills

- [bio-single-cell-regulatory-pyscenic](../bio-single-cell-regulatory-pyscenic/SKILL.md) — Python implementation; generally faster
- [bio-single-cell-annotation-markers](../bio-single-cell-annotation-markers/SKILL.md) — Cell type annotation before SCENIC analysis
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — Clustering needed for regulon specificity analysis

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*, 14, 1083-1086.
2. SCENIC documentation: https://github.com/aertslab/SCENIC
