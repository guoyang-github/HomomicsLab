# SCENIC (R) Usage Guide

## Overview

SCENIC (Single-Cell rEgulatory Network Inference and Clustering) reconstructs gene regulatory networks and identifies stable cell states based on transcription factor regulon activity.

This enhanced skill extends the base SCENIC package with:
- **TF Validation** - Verify TF list overlap before running
- **Correlation Network** - Fast alternative to GENIE3
- **Resume Capability** - Continue interrupted GENIE3 runs
- **Flexible Parameters** - Customizable module creation thresholds
- **Binarization** - Convert AUC scores to binary active/inactive calls

## When to Use

- Infer TF regulons from scRNA-seq
- Identify cell type specific regulators
- Map regulatory states
- Analyze gene regulatory networks

## Quick Start

```r
library(SCENIC)
library(Seurat)
library(AUCell)

source("scripts/r/scenic_analysis.R")

# Initialize with validation
scenicOptions <- init_scenic("hgnc", dbDir = "cisTarget")
exprMat <- GetAssayData(seurat_obj, slot = "counts")

# Validate TF overlap before running
validation <- validate_tf_list(exprMat, getDbTfs(scenicOptions))

# Run complete pipeline
scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions)

# Optional: Binarize activity
scenicOptions <- run_aucell_binarization(scenicOptions)

# Add results to Seurat
seurat_obj <- add_scenic_to_seurat(seurat_obj, scenicOptions, addBinary = TRUE)
```

## Step-by-Step Guide

### 0. Database Setup (First Time Only)

SCENIC requires cisTarget databases (~1GB per database type). Databases are stored in a hierarchical cache system:

1. **Skill assets/** folder (preferred) - Project-specific storage in the skill directory
2. **Home directory** (fallback) - `~/cisTarget`

This design keeps projects self-contained while maintaining backward compatibility.

You have three options for database setup:

#### Option A: Auto-Download with Hierarchical Cache (Recommended)

```r
source("scripts/r/scenic_analysis.R")

# Automatically check and download databases if missing
# Uses skill assets/ first, falls back to ~/cisTarget
scenicOptions <- init_scenic_auto(
  org = "hgnc",                    # "hgnc" for human, "mmusculus" for mouse
  dbDir = "cisTarget",             # Fallback directory (in home)
  db_types = "10kb",               # "500bp", "10kb", or c("500bp", "10kb")
  motif_version = "v10",           # "v9" or "v10"
  download_if_missing = TRUE,      # Auto-download if not found
  prefer_skill_assets = TRUE,      # Prefer skill assets/ directory
  nCores = 4
)
```

**Where are databases stored?**

By default, databases are stored in the skill's `assets/` folder:
```
skills/bio-single-cell-regulatory-scenic-r/
├── assets/                       # <-- Databases stored here
│   ├── hg38__refseq-r80__10kb...
│   ├── motifs-v10nr_clust-nr...
│   └── allTFs_hg38.txt
├── scripts/
└── ...
```

If the skill directory cannot be determined (e.g., running from elsewhere), it falls back to `~/cisTarget/`.

**Cache location functions:**
```r
# View all cache locations
locations <- list_cistarget_cache_locations()
print(locations$skill_assets)   # /path/to/skill/assets
print(locations$home_cache)     # ~/cisTarget

# Control cache preference
get_cistarget_dir("cisTarget", prefer_skill_assets = TRUE)   # Use assets/
get_cistarget_dir("cisTarget", prefer_skill_assets = FALSE)  # Use home
```

#### Option B: Manual Download Control

```r
# Step 1: Check current status
status <- check_cistarget_databases(
  org = "hgnc",
  dbDir = "cisTarget",
  db_types = "10kb"
)

print(status$all_ready)           # TRUE if all files exist
print(status$rankings$`10kb`$exists)  # Check specific database
print(status$motif_annotation)    # Check motif file
print(status$tf_list)             # Check TF list

# Step 2: Download if needed
if (!status$all_ready) {
  db_paths <- download_cistarget_databases(
    org = "hgnc",
    dbDir = "cisTarget",
    db_types = "10kb",           # Database types to download
    motif_version = "v10",
    force = FALSE                # Set TRUE to re-download existing files
  )

  # Check downloaded files
  print(db_paths$rankings$`10kb`)
  print(db_paths$motif_annotation)
  print(db_paths$tf_list)
}

# Step 3: Initialize SCENIC
scenicOptions <- init_scenic("hgnc", dbDir = "cisTarget")
```

#### Option C: View All Database Status

```r
# List status of all databases
all_status <- list_cistarget_databases("cisTarget", prefer_skill_assets = TRUE)
print(all_status)

# Output:
#   organism   type ranking_exists motif_exists tf_list_exists all_ready
# 1     hgnc 500bp          FALSE        FALSE          FALSE     FALSE
# 2     hgnc  10kb           TRUE         TRUE           TRUE      TRUE
# 3 mmusculus 500bp          FALSE        FALSE          FALSE     FALSE
# 4 mmusculus  10kb          FALSE        FALSE          FALSE     FALSE
```

**Database Information:**

| Database | Size | Description |
|----------|------|-------------|
| `hg38_10kb` | ~1.0 GB | Human 10kb regions (enhancers + promoters) |
| `hg38_500bp` | ~0.5 GB | Human 500bp regions (promoters only) |
| `mm10_10kb` | ~1.0 GB | Mouse 10kb regions |
| `mm10_500bp` | ~0.5 GB | Mouse 500bp regions |
| Motif annotations | ~5 MB | TF-motif mappings |
| TF lists | ~10 KB | List of TFs per organism |

**Cache Location Hierarchy:**

| Priority | Location | When Used |
|----------|----------|-----------|
| 1 | `skills/bio-single-cell-regulatory-scenic-r/assets/` | Default (skill detected) |
| 2 | `~/cisTarget/` | Fallback (skill not detected) |
| Custom | User-specified | When `prefer_skill_assets=FALSE` |

### 1. Initialize and Validate

```r
library(SCENIC)
library(Seurat)

source("scripts/r/scenic_analysis.R")

# Initialize SCENIC
scenicOptions <- init_scenic(
  org = "hgnc",           # "hgnc" for human, "mmusculus" for mouse
  dbDir = "cisTarget",    # cisTarget database directory
  datasetTitle = "MySCENIC",
  nCores = 4
)

# Get expression matrix (genes x cells)
exprMat <- GetAssayData(seurat_obj, slot = "counts")

# Validate TF list overlap
tfList <- getDbTfs(scenicOptions)
validation <- validate_tf_list(exprMat, tfList, minOverlapPct = 80)

# Check results
print(validation$overlapPct)      # Percentage of TFs found
print(validation$missingTFs[1:10]) # First 10 missing TFs
```

### 2. Network Inference Options

Choose the network inference method based on your dataset size and computational resources:

#### Option A: Full GENIE3 (Best Accuracy, Slow)

```r
# Standard GENIE3 run
scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  runGenie3 = TRUE,
  nParts = 10                    # Split into 10 parts for parallelization
)
```

#### Option B: Resume Interrupted GENIE3

```r
# If GENIE3 was interrupted, resume without recomputing
scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  runGenie3 = TRUE,
  nParts = 10,
  resumePreviousRun = TRUE       # Skip if results already exist
)
```

#### Option C: Correlation Network (Fast, Large Datasets)

```r
# Use correlation instead of GENIE3 for datasets >10k cells
scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  useCorrelationNetwork = TRUE,   # Fast alternative
  corMethod = "spearman",
  corThreshold = 0.03,           # Minimum |correlation| to keep
  topNPerTF = 50                 # Top 50 targets per TF
)
```

**Method Comparison:**

| Method | Speed | Memory | Accuracy | Best For |
|--------|-------|--------|----------|----------|
| GENIE3 | Slow (hours) | High | High | Small datasets (<5k cells), publication |
| Correlation | Fast (minutes) | Low | Moderate | Large datasets (>10k cells), screening |

### 3. Flexible Module Creation

Customize how co-expression modules are created:

```r
scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  # Network inference (choose one method)
  runGenie3 = TRUE,
  nParts = 10,
  
  # Module creation parameters
  weightThreshold = 0.001,        # Min edge weight (lower = more edges)
  topThr = 0.005,                # Top 0.5% co-expression pairs
  nTopTFs = c(5, 10, 50),        # Top N TFs per method
  nTopTargets = 50,              # Top N targets per TF
  minGenes = 20                  # Min genes per module for RcisTarget
)
```

**Parameter Tuning Guide:**

| Goal | weightThreshold | topThr | nTopTargets |
|------|-----------------|--------|-------------|
| Stringent regulons | 0.01 | 0.001 | 20 |
| Balanced (default) | 0.001 | 0.005 | 50 |
| Permissive | 0.0001 | 0.01 | 100 |

### 4. Binarization (Optional)

Convert continuous AUC scores to binary active/inactive calls:

```r
# Run binarization with automatic threshold detection
scenicOptions <- run_aucell_binarization(
  scenicOptions,
  smallestPopPercent = 0.01,     # Min 1% of cells must pass threshold
  skipBoxplot = FALSE,           # Generate diagnostic plots
  skipHeatmaps = FALSE,
  skipTsne = TRUE
)

# Load binary activity matrix
binaryMat <- load_binary_activity(scenicOptions)

# Check dimensions
print(dim(binaryMat))  # regulons x cells
print(binaryMat[1:5, 1:5])  # 1 = active, 0 = inactive
```

### 5. Cell-Type Specific Analysis

```r
# Create cell info data frame
cellInfo <- data.frame(
  cellType = seurat_obj$cell_type,
  seurat_clusters = seurat_obj$seurat_clusters,
  row.names = colnames(seurat_obj)
)

# Find active regulons per cell type (>25% of cells)
activeRegulons <- get_active_regulons_by_celltype(
  scenicOptions,
  cellInfo,
  cellTypeCol = "cellType",
  minActiveFrac = 0.25,
  nonDuplicated = TRUE           # Remove "_extended" duplicates
)

# View results
head(activeRegulons)
#   cell_type      regulon active_fraction n_active_cells n_total_cells
# 1   T_cells  TBX21 (38g)            0.82            82           100
# 2   T_cells   GATA3 (45g)            0.76            76           100
```

### 6. Add Results to Seurat

```r
# Add continuous AUC scores
seurat_obj <- add_scenic_to_seurat(
  seurat_obj,
  scenicOptions,
  assayName = "SCENIC",
  addBinary = TRUE               # Also add binary activity
)

# View available assays
names(seurat_obj@assays)
# [1] "RNA" "SCENIC" "SCENIC_binary"

# Analyze top regulons per cluster
top_regulons <- get_top_regulons(
  seurat_obj,
  group_by = "seurat_clusters",
  top_n = 10
)

# Find cell-type specific regulons
specific_regulons <- find_celltype_specific_regulons(
  seurat_obj,
  group_by = "cell_type",
  min_auc = 0.05
)
```

### 7. Visualization

```r
# Plot regulon activity on UMAP
plots <- plot_regulon_activity(
  seurat_obj,
  regulons = c("SOX10 (45g)", "MITF (32g)"),
  reduction = "umap"
)
print(plots)

# Heatmap of top regulons
DefaultAssay(seurat_obj) <- "SCENIC"
DoHeatmap(seurat_obj, features = unique(top_regulons$regulon)[1:20])

# Binary activity heatmap (if addBinary=TRUE)
DefaultAssay(seurat_obj) <- "SCENIC_binary"
DoHeatmap(seurat_obj, features = unique(activeRegulons$regulon)[1:20])
```

## Recommended Parameter Combinations

### Small Dataset (< 5,000 cells)
```r
scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  runGenie3 = TRUE,
  nParts = 5,
  weightThreshold = 0.001,
  topThr = 0.005,
  minGenes = 20
)
```

### Large Dataset (> 20,000 cells)
```r
# For very large datasets, subsample or use correlation
if (ncol(exprMat) > 20000) {
  # Option 1: Subsample
  set.seed(42)
  cells <- sample(colnames(exprMat), 20000)
  exprMat <- exprMat[, cells]
  
  # Option 2: Use correlation network
  scenicOptions <- run_scenic_pipeline(
    exprMat,
    scenicOptions,
    useCorrelationNetwork = TRUE,
    corThreshold = 0.03
  )
}
```

### Memory-Limited Environment (< 16GB RAM)
```r
scenicOptions <- init_scenic("hgnc", dbDir = "cisTarget", nCores = 2)

scenicOptions <- run_scenic_pipeline(
  exprMat,
  scenicOptions,
  nParts = 20,                    # More parts = less memory per part
  useCorrelationNetwork = TRUE    # Lower memory than GENIE3
)
```

## AI Agent Test Cases

### Database Management
> "Check if SCENIC databases are downloaded"

> "Download human 10kb cisTarget database for SCENIC"

> "Initialize SCENIC with automatic database download"

> "List all available SCENIC databases and their status"

### Basic Usage
> "Run SCENIC pipeline on my scRNA-seq data"

> "Infer TF regulons using SCENIC in R"

### Validation
> "Check TF list overlap before running SCENIC"

> "Validate that my gene names match the SCENIC database"

### Network Methods
> "Run SCENIC with correlation network for speed"

> "Resume my interrupted GENIE3 run"

### Binarization
> "Binarize SCENIC regulon activity"

> "Find regulons active in at least 50% of T cells"

### Analysis
> "Identify cell type specific regulons with SCENIC"

> "Map regulatory states using SCENIC AUC scores"

### Visualization
> "Create regulon activity heatmap"

> "Plot regulon specificity on UMAP"

## Troubleshooting

### Database Not Found Error
```
Error: cisTarget database directory not found: cisTarget
```
**Solution**: Use `init_scenic_auto()` instead of `init_scenic()`:
```r
scenicOptions <- init_scenic_auto("hgnc", dbDir = "cisTarget", download_if_missing = TRUE)
```

Or manually download:
```r
download_cistarget_databases("hgnc", dbDir = "cisTarget", db_types = "10kb")
```

### Download Fails or Times Out
```
Error: Download failed: Timeout was reached
```
**Solution**: Increase timeout or download manually:
```r
# Increase timeout (default 600 seconds = 10 minutes)
download_cistarget_databases("hgnc", dbDir = "cisTarget", timeout = 1200)

# Or download manually from:
# https://resources.aertslab.org/cistarget/databases/
```

### Corrupt Database File
```
Error: Invalid Feather file
```
**Solution**: Force re-download:
```r
download_cistarget_databases("hgnc", dbDir = "cisTarget", force = TRUE)
```

### Low TF Overlap Warning
```
Warning: Low TF overlap (45% < 80%). Check gene ID format.
```
**Solution**: Ensure gene names are gene symbols (e.g., "TP53") not Ensembl IDs (e.g., "ENSG00000141510")

### GENIE3 Takes Too Long
**Solution**: Use correlation network for large datasets, or increase `nParts` to reduce memory usage per part

### Out of Memory Error
**Solution**: 
- Reduce `nCores`
- Increase `nParts` for GENIE3
- Use `useCorrelationNetwork=TRUE`

### No Regulons Found
**Solution**: Check `minGenes` parameter (default 20). Lower to 10 for small datasets.

---

## Advanced: Database Migration (Optional)

If you have existing databases in your home directory (`~/cisTarget/`) and want to migrate them to the skill's `assets/` folder for project isolation:

```r
# Preview what would be migrated
result <- migrate_databases_to_skill_assets(dry_run = TRUE)
print(result$to_migrate)      # Files to be moved
print(result$already_present) # Files already in skill assets

# Execute migration
result <- migrate_databases_to_skill_assets(dry_run = FALSE)
```

**Note**: This is a one-time operation. After migration, subsequent runs will use the skill assets directory automatically.

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
2. SCENIC documentation: https://github.com/aertslab/SCENIC
