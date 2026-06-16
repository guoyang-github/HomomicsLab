---
name: bio-single-cell-atac-archr-r
description: Single-cell ATAC-seq analysis using ArchR. Fast and scalable analysis of chromatin accessibility data including dimensionality reduction, clustering, peak calling, and motif enrichment.
tool_type: r
primary_tool: ArchR
supported_tools: [MACS2, Seurat, ComplexHeatmap, ggplot2]
languages: [r]
keywords: ["single-cell", "ATAC", "ArchR", "chromatin", "accessibility", "peaks", "motifs", "clustering", "scATAC", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **ArchR**: >= 1.0.2
- **Bioconductor**: >= 3.17
- **Seurat**: >= 4.3.0 (optional, for scRNA-seq integration; compatible with both v4 and v5)

## Installation

```r
# Install Bioconductor dependencies
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install(c("magick", "ComplexHeatmap", "SummarizedExperiment"))

# Install ArchR from GitHub
devtools::install_github("GreenleafLab/ArchR", ref="master",
                         repos = BiocManager::repositories())

# Optional: Install MACS2 for peak calling
# pip install MACS2
```

## Import Wrapper Functions

Source the wrapper scripts before using:

```r
# Core analysis functions
source("scripts/r/core_analysis.R")

# Visualization functions
source("scripts/r/visualization.R")

# Utility functions
source("scripts/r/utils.R")
```

## Core Analysis Workflow

ArchR is a comprehensive R package for analyzing single-cell ATAC-seq data at scale.

### Step 1: Environment Setup

Configure ArchR threads and genome before analysis.

```r
# Setup ArchR environment
setup_archr(
  threads = 16,           # Number of parallel threads
  genome = "hg38"         # Genome: "hg38", "hg19", "mm10", "mm9"
)

# Check dependencies
check_archr_dependencies()

# Get parameter recommendations
params <- recommend_archr_params(
  n_cells = 10000,
  n_samples = 2,
  has_macs2 = check_macs2()
)
```

**Key Points:**
- Set threads based on available CPU cores
- Genome must be set before creating Arrow files
- MACS2 is required for peak calling

### Step 2: Create Arrow Files

Arrow files are ArchR's efficient storage format for scATAC-seq data.

```r
# Define input files
input_files <- c(
  "sample1_fragments.tsv.gz",
  "sample2_fragments.tsv.gz"
)
sample_names <- c("Sample1", "Sample2")

# Validate fragment files
validation <- validate_fragment_files(input_files)
print(validation)

# Create Arrow files
arrow_files <- create_arrow_files(
  input_files = input_files,
  sample_names = sample_names,
  filter_tss = 4,              # TSS enrichment cutoff
  filter_frags = 1000,         # Minimum fragments per cell
  add_tile_mat = TRUE,         # Add genome tile matrix
  add_gene_score_mat = TRUE,   # Add gene activity scores
  min_frags = 500,             # Minimum for cell calling
  max_frags = 1e6              # Maximum for cell calling
)
```

**Quality Filters:**
- `filter_tss`: Higher values = stricter quality (typical: 4-10)
- `filter_frags`: Higher values = more fragments required (typical: 1000-5000)
- Arrow files are created once and reused

### Step 3: Create ArchR Project

Create an ArchRProject from Arrow files.

```r
# Create project
proj <- create_archr_project(
  arrow_files = arrow_files,
  output_directory = "Save-ArchR",
  copy_arrows = TRUE           # Copy Arrow files to output directory
)

# View project info
summary <- get_archr_summary(proj)
print(summary)
```

**Project Structure:**
- Arrow files contain raw data
- Project stores metadata and computed results
- `copyArrows = TRUE` enables project portability

### Step 4: Doublet Detection and Removal

ArchR identifies and removes predicted doublets.

```r
# Add doublet scores
proj <- add_doublet_scores(
  proj,
  use_matrix = "TileMatrix",
  k = 10,                      # Nearest neighbors
  n_trials = 5                 # Simulation trials
)

# Filter doublets
proj <- filter_doublets(
  proj,
  filter_ratio = 1             # Stringency ratio
)
```

**Key Parameters:**
- `k`: Higher = more neighbors considered
- `n_trials`: More trials = more accurate but slower
- `filter_ratio`: Higher = more aggressive filtering

### Step 5: Dimensionality Reduction

ArchR uses iterative LSI (Latent Semantic Indexing) for dimensionality reduction.

```r
# Add iterative LSI
proj <- add_iterative_lsi(
  proj,
  name = "IterativeLSI",
  iterations = 2,              # Number of LSI iterations
  cluster_params = list(
    resolution = 2,
    sampleCells = 10000
  ),
  var_features = 25000,        # Number of variable features
  dims_to_use = 1:30,          # Dimensions to use
  binarize = TRUE              # Binarize counts
)
```

**LSI Parameters:**
- `iterations`: More iterations = better separation (typical: 2-3)
- `var_features`: Number of variable tiles to use
- `binarize`: Whether to binarize counts (recommended for ATAC)

### Step 6: Clustering

Cluster cells using LSI dimensions.

```r
# Add clusters
proj <- add_clusters(
  proj,
  reduced_dims = "IterativeLSI",
  name = "Clusters",
  method = "Seurat",
  resolution = 0.8,            # Clustering resolution
  k_neighbors = 30             # K for nearest neighbors
)

# View cluster distribution
table(proj$Clusters)
```

**Clustering Resolution:**
- Lower (0.4-0.6): Broader cell types
- Medium (0.8-1.2): Subtypes (default)
- Higher (>1.5): Fine subpopulations

### Step 7: UMAP Visualization

Compute UMAP embedding for visualization.

```r
# Add UMAP
proj <- add_umap(
  proj,
  reduced_dims = "IterativeLSI",
  n_neighbors = 40,            # Number of neighbors
  min_dist = 0.4,              # Minimum distance
  metric = "cosine"            # Distance metric
)

# Plot UMAP
plot_embedding(
  proj,
  embedding = "UMAP",
  color_by = "cellColData",
  name = "Clusters"
)
```

**UMAP Parameters:**
- `n_neighbors`: Higher = more global structure
- `min_dist`: Lower = tighter clusters
- `metric`: "cosine" recommended for LSI

### Step 8: Peak Calling

Call peaks using MACS2 for reproducible peak set.

```r
# Add reproducible peak set
proj <- add_reproducible_peak_set(
  proj,
  group_by = "Clusters",       # Group for peak calling
  peak_method = "Macs2",
  reproducibility = "2",       # Reproducibility across samples
  peaks_per_cell = 500,
  max_peaks = 250000,
  path_to_macs2 = "/path/to/macs2"
)

# Add peak matrix
proj <- add_peak_matrix(proj)

# View peaks
peaks <- getPeakSet(proj)
```

**Peak Calling:**
- Requires MACS2 installation
- `group_by`: Peaks called per group, then merged
- `reproducibility`: "2" = peaks in at least 2 samples

### Step 9: Motif Analysis

Add motif annotations and compute chromVAR deviations.

```r
# Add motif annotations
proj <- add_motif_annotations(
  proj,
  motif_set = "cisbp",         # "cisbp", "encode", "homer", "jasparkellis"
  anno_name = "Motif"
)

# Add deviations matrix
proj <- add_deviations_matrix(
  proj,
  peak_annotation = "Motif",
  out = "z"                    # Output z-scores
)
```

**Motif Databases:**
- `cisbp`: Comprehensive TF motifs (default)
- `encode`: ENCODE-curated motifs
- `homer`: HOMER motif database
- `jasparkellis`: JASPAR motifs

### Step 10: Run Complete Workflow

Run the entire ArchR pipeline in one command.

```r
# Complete workflow
proj <- run_archr_workflow(
  input_files = input_files,
  sample_names = sample_names,
  output_directory = "ArchR-Project",
  genome = "hg38",
  threads = 16,
  filter_tss = 4,
  filter_frags = 1000,
  lsi_iterations = 2,
  cluster_resolution = 0.8,
  run_umap = TRUE,
  run_doublet_filter = TRUE,
  run_peak_calling = TRUE,
  path_to_macs2 = "/path/to/macs2"
)
```

## Visualization

### Plot Embedding

```r
# Plot clusters
plot_embedding(
  proj,
  embedding = "UMAP",
  color_by = "cellColData",
  name = "Clusters",
  size = 0.5
)

# Plot by sample
plot_embedding(
  proj,
  color_by = "cellColData",
  name = "Sample"
)
```

### Plot Gene Scores

```r
# Define marker genes
marker_genes <- c("CD34", "GATA1", "PAX5", "CD19", "CD14")

# Plot gene scores
gene_plots <- plot_gene_scores(
  proj,
  genes = marker_genes,
  embedding = "UMAP",
  impute = TRUE                # Use imputation for smoothing
)

# Display plots
cowplot::plot_grid(plotlist = gene_plots, ncol = 3)
```

### Browser Tracks

```r
# Plot browser track
plot_browser_track(
  proj,
  gene_symbol = "GATA1",       # Gene to visualize
  group_by = "Clusters",
  upstream = 50000,            # Upstream extension
  downstream = 50000           # Downstream extension
)
```

### QC Plots

```r
# Create comprehensive QC plots
create_qc_plots(
  proj,
  output_dir = "./archr_qc",
  prefix = "sample"
)
```

## Integration with scRNA-seq

### Add Gene Integration Matrix

```r
# Load scRNA-seq data (Seurat object)
seRNA <- readRDS("scRNA_data.rds")

# Add gene integration matrix
proj <- addGeneIntegrationMatrix(
  ArchRProj = proj,
  seRNA = seRNA,
  nameATAC = "geneActivity",
  nameRNA = "RNA",
  groupATAC = "Clusters",
  groupRNA = "seurat_clusters"
)

# Transfer labels
proj$predictedCellType <- proj$predictedGroup_Un
```

### Convert to Seurat

```r
# Convert ArchR to Seurat
seurat_obj <- convert_to_seurat(
  proj,
  assay_name = "ATAC",
  use_matrix = "GeneScoreMatrix",
  transfer_embeddings = TRUE
)
```

## Advanced Topics

### Marker Features

```r
# Get marker features
markers <- getMarkerFeatures(
  ArchRProj = proj,
  groupBy = "Clusters",
  useMatrix = "GeneScoreMatrix",
  bias = c("TSSEnrichment", "log10(nFrags)")
)

# Get marker genes
marker_genes <- getMarkers(
  markers,
  cutOff = "FDR <= 0.01 & Log2FC >= 0.5"
)
```

### Trajectory Analysis

```r
# Add trajectory
proj <- addTrajectory(
  ArchRProj = proj,
  trajectory = "Myeloid",
  groupBy = "Clusters",
  reducedDims = "IterativeLSI"
)

# Plot trajectory
plotTrajectory(proj, trajectory = "Myeloid")
```

### Footprinting

```r
# Get footprints
proj <- addFootprints(
  ArchRProj = proj,
  motifName = "GATA1"
)

# Plot footprints
plotFootprints(proj, motifName = "GATA1")
```

## Input Requirements

### Fragment File Format

```
chr1    1000    1050    ACGTACGT-1    1
chr1    2000    2050    ACGTACGT-1    1
```

Columns:
1. Chromosome
2. Start (0-based)
3. End (1-based)
4. Cell barcode
5. Count (usually 1)

Files must be:
- Tab-delimited
- Gzipped (.tsv.gz)
- Sorted by position

### Sample Metadata

```r
# Create from filenames
metadata <- create_sample_metadata(
  fragment_files,
  pattern = "^([^_]+)"  # Extract sample prefix
)
```

## Output Specifications

### Cell Metadata

| Column | Description |
|--------|-------------|
| `Sample` | Sample name |
| `TSSEnrichment` | TSS enrichment score |
| `nFrags` | Number of fragments |
| `ReadsInTSS` | Reads in TSS regions |
| `BlacklistRatio` | Ratio of blacklist regions |
| `Clusters` | Cluster assignment |
| `DoubletScore` | Doublet score |
| `DoubletEnrichment` | Doublet enrichment |

### Peak Set

GRanges object with:
- Peak coordinates
- Peak score
- Group annotation
- Reproducibility info

## Key Parameters

### Quality Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `filter_tss` | 4 | Minimum TSS enrichment |
| `filter_frags` | 1000 | Minimum fragments |
| `min_frags` | 500 | Minimum for cell calling |
| `max_frags` | 1e6 | Maximum for cell calling |

### Clustering

| Parameter | Default | Description |
|-----------|---------|-------------|
| `resolution` | 0.8 | Clustering resolution |
| `k_neighbors` | 30 | K for nearest neighbors |
| `n_neighbors` | 40 | UMAP neighbors |
| `min_dist` | 0.4 | UMAP minimum distance |

### Peak Calling

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reproducibility` | "2" | Minimum samples with peak |
| `peaks_per_cell` | 500 | Target peaks per cell |
| `max_peaks` | 250000 | Maximum peaks |

## Expected Runtime

| Dataset Size | Runtime (16 cores) |
|--------------|-------------------|
| 5K cells, 1 sample | 10-15 min |
| 20K cells, 2 samples | 30-45 min |
| 100K cells, 4 samples | 2-3 hours |

*Runtime estimates include Arrow creation, LSI, clustering, UMAP, and peak calling.*

## Error Handling

### Common Errors and Solutions

**Arrow creation fails**
```
Error: Fragment file not valid
```
→ Check file format and gzip compression
→ Ensure files are sorted

**MACS2 not found**
```
Error: MACS2 not found in PATH
```
→ Install MACS2: `pip install MACS2`
→ Provide full path: `path_to_macs2 = "/usr/local/bin/macs2"`

**Out of memory**
```
Error: cannot allocate vector of size...
```
→ Reduce threads: `addArchRThreads(threads = 4)`
→ Process samples separately, then merge

## Best Practices

1. **Quality filtering**: Start with lenient filters, tighten after QC
2. **Doublet removal**: Always filter doublets before clustering
3. **Arrow files**: Create once, reuse for multiple analyses
4. **Iterative LSI**: Use 2-3 iterations for best results
5. **Peak calling**: Call peaks per biological replicate
6. **Backup**: Save project frequently with `saveArchRProject()`

## Related Skills

- [bio-single-cell-atac-signac-r](../bio-single-cell-atac-signac-r/SKILL.md) - Signac for scATAC-seq
- [bio-single-cell-atac-chromvar-r](../bio-single-cell-atac-chromvar-r/SKILL.md) - chromVAR for TF analysis
- [bio-single-cell-rna-seurat-r](../bio-single-cell-rna-seurat-r/SKILL.md) - Seurat for scRNA-seq

## References

1. Granja et al. (2021). ArchR is a scalable software package for integrative single-cell chromatin accessibility analysis. *Nature Genetics*, 53, 403-411.
2. ArchR documentation: https://www.archrproject.com/
3. ArchR GitHub: https://github.com/GreenleafLab/ArchR
