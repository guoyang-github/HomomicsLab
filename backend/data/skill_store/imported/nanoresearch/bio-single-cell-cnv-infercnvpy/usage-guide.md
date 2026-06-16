# infercnvpy Usage Guide

## Overview

infercnvpy infers copy number variation (CNV) from single-cell RNA-seq data using a sliding window approach. It is inspired by the R package InferCNV but is more scalable and integrates seamlessly with Scanpy/AnnData workflows.

## When to Use

- Identify large-scale chromosomal copy number alterations in tumor cells
- Distinguish tumor cells from normal cells based on CNV profiles
- Identify subclonal populations with distinct CNV patterns
- Validate cell type annotations in cancer samples

## Input Data Requirements

### Required Annotations

**1. Gene Positions (adata.var)**

```python
# Required columns in adata.var
adata.var["chromosome"] = "chr1"  # Chromosome name with 'chr' prefix
adata.var["start"] = 1000000      # Genomic start position
adata.var["end"] = 1001000        # Genomic end position
```

**2. Reference/Normal Cells (adata.obs)**

```python
# Column indicating reference (normal) cells
adata.obs["cell_type"] = ["T_cell", "Tumor", "B_cell", "Tumor", ...]
```

## Step-by-Step Guide

### 1. Prepare Gene Positions

#### Option A: From GTF File (Recommended)

```python
from infercnv_analysis import add_gene_positions

# Add gene positions directly from GTF
adata = add_gene_positions(
    adata,
    gtf_file="gencode.v38.annotation.gtf.gz"
)

# Verify
print(adata.var[["chromosome", "start", "end"]].head())
```

#### Option B: From Custom DataFrame

```python
import pandas as pd
from infercnv_analysis import add_gene_positions

# Create gene positions DataFrame
gene_pos = pd.DataFrame({
    "gene_name": ["TP53", "MYC", "EGFR"],
    "chromosome": ["chr17", "chr8", "chr7"],
    "start": [7661779, 1277356, 55019017],
    "end": [7687538, 1280304, 55211628]
}).set_index("gene_name")

# Add to AnnData
adata = add_gene_positions(adata, gene_positions=gene_pos)
```

#### Option C: Using infercnvpy's GTF Reader

```python
import infercnvpy as cnv

# Read gene positions
gene_pos = cnv.io.read_gtf(
    "gencode.v38.annotation.gtf.gz",
    gene_id_attribute="gene_name",  # or "gene_id" for Ensembl
    feature_type="gene"
)

# Merge with AnnData
from infercnv_analysis import add_gene_positions
adata = add_gene_positions(adata, gene_positions=gene_pos)
```

### 2. Run CNV Inference

#### Basic Usage

```python
from infercnv_analysis import run_infercnv_pipeline

# Identify normal cell types in your data
print(adata.obs["cell_type"].value_counts())
# T_cell        5000
# B_cell        3000
# Macrophage    2000
# Tumor        15000

# Run CNV inference using immune cells as reference
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["T_cell", "B_cell", "Macrophage"],
    window_size=100,
    step=10,
    key_added="cnv"
)
```

#### Advanced Parameters

```python
# High-resolution analysis (slower, more detailed)
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["T_cell", "B_cell", "Macrophage"],
    window_size=50,           # Smaller window
    step=5,                   # Smaller step
    lfc_clip=3,               # Clip extreme values
    dynamic_threshold=1.5,    # Denoising strength
    exclude_chromosomes=("chrX", "chrY", "chrM"),
    chunksize=2000,           # Smaller chunks for memory
    n_jobs=8,                 # Parallel processing
    key_added="cnv_highres"
)
```

#### Memory-Limited Settings

```python
# For large datasets (>50k cells)
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["Normal"],
    window_size=200,          # Larger window = fewer features
    step=20,                  # Larger step = fewer windows
    chunksize=1000,           # Smaller chunks
    n_jobs=4,                 # Fewer parallel jobs
    calculate_gene_values=False  # Skip per-gene values
)
```

### 3. Visualize Results

#### Chromosome Heatmap

```python
import infercnvpy as cnv
import scanpy as sc

# Basic heatmap by cell type
cnv.pl.chromosome_heatmap(adata, groupby="cell_type")

# Customized heatmap
cnv.pl.chromosome_heatmap(
    adata,
    groupby="cnv_leiden",
    cmap="RdBu_r",
    vmin=-1,
    vmax=1,
    figsize=(12, 8)
)

# Save figure
sc.settings.figdir = "./figures"
cnv.pl.chromosome_heatmap(adata, groupby="cell_type", save="_cnv.png")
```

#### UMAP of CNV Profiles

```python
from infercnv_analysis import cluster_by_cnv

# Cluster by CNV profile
cluster_by_cnv(adata, key="cnv", resolution=0.5)

# Visualize
sc.pl.umap(adata, color=["cnv_leiden", "cell_type"], ncols=1)
```

### 4. Analyze CNV Patterns

#### Identify Altered Regions

```python
from infercnv_analysis import identify_cnv_regions

# Find significant CNV alterations
cnv_regions = identify_cnv_regions(
    adata,
    key="cnv",
    threshold=0.3,
    min_cells=50
)

print(cnv_regions)
#   chromosome  mean_cnv  abs_mean_cnv   std_cnv  n_cells_amp  n_cells_del  n_cells_altered
# 0       chr8   0.523456      0.612345  0.234567          120           45              145
# 1       chr7   0.412345      0.523456  0.198765           95           30              110
```

#### Summarize by Chromosome and Group

```python
from infercnv_analysis import summarize_cnv_by_chromosome

# Summarize by cell type
chr_summary = summarize_cnv_by_chromosome(
    adata,
    key="cnv",
    groupby="cell_type"
)

# View tumor-specific alterations
tumor_summary = chr_summary[chr_summary["group"] == "Tumor"]
print(tumor_summary.sort_values("mean_cnv", ascending=False))
```

#### Compare CNV Clusters

```python
# Compare CNV clusters with original annotations
import pandas as pd

comparison = pd.crosstab(
    adata.obs["cnv_leiden"],
    adata.obs["cell_type"],
    normalize="index"
)
print(comparison)
```

### 5. Export Results

```python
from infercnv_analysis import export_cnv_results

# Export all results
export_cnv_results(
    adata,
    output_dir="./cnv_results/",
    key="cnv",
    prefix="tumor_sample1"
)

# Files created:
# - ./cnv_results/tumor_sample1_infercnv_matrix.csv.gz
# - ./cnv_results/tumor_sample1_infercnv_chr_pos.csv
# - ./cnv_results/tumor_sample1_infercnv_cell_metadata.csv
```

## Parameter Recommendations

### Window Size Selection

| Window | Step | Resolution | Speed | Use Case |
|--------|------|------------|-------|----------|
| 50 | 5 | High | Slow | Detecting focal alterations |
| 100 | 10 | Medium | Medium | **Default, balanced** |
| 200 | 20 | Low | Fast | Large-scale changes only |

### Reference Cell Selection

**Good reference candidates:**
- Immune cells (T cells, B cells, macrophages)
- Stromal cells (fibroblasts, endothelial cells)
- Matched normal tissue
- Cell types with known diploid state

**Avoid as reference:**
- Tumor cells
- Cells with known CNVs
- Small populations (< 50 cells)

### Denoising Settings

| Parameter | Default | Effect | When to Adjust |
|-----------|---------|--------|----------------|
| `lfc_clip` | 3.0 | Caps extreme values | Increase for noisy data |
| `dynamic_threshold` | 1.5 | Removes background noise | Decrease to keep more signal |

## Interpreting Results

### CNV Value Interpretation

| CNV Value | Interpretation |
|-----------|----------------|
| > 0.5 | High-level amplification (3+ copies) |
| 0.3 - 0.5 | Low-level gain (2-3 copies) |
| -0.3 to 0.3 | Normal diploid (2 copies) |
| -0.5 to -0.3 | Low-level loss (1-2 copies) |
| < -0.5 | High-level loss/deletion (0-1 copies) |

### Common Cancer Alterations

| Cancer Type | Common CNVs |
|-------------|-------------|
| Glioblastoma | Chr 7 gain, Chr 10 loss |
| Breast cancer | Chr 1q gain, Chr 8q gain (MYC) |
| Lung adenocarcinoma | Chr 3q gain, Chr 7 gain (EGFR) |
| Colorectal cancer | Chr 8q gain, Chr 18 loss |

## Troubleshooting

### Error: "Gene positions not found"

**Solution**: Add gene positions before running infercnv
```python
from infercnv_analysis import add_gene_positions
adata = add_gene_positions(adata, gtf_file="annotation.gtf")
```

### Error: "Ensure your var_names are unique"

**Solution**: Make gene names unique
```python
adata.var_names_make_unique()
```

### Low gene overlap warning

**Cause**: Gene naming mismatch between AnnData and GTF

**Solution**: Check and fix gene names
```python
# Check example gene names
print(adata.var_names[:10])

# If using Ensembl IDs, set appropriate attribute
gene_pos = cnv.io.read_gtf("gtf_file", gene_id_attribute="gene_id")
```

### Memory errors

**Solution**: Reduce chunksize and window_size
```python
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat="Normal",
    window_size=200,    # Larger window
    step=20,            # Larger step
    chunksize=500       # Smaller chunks
)
```

### No clear CNV signal

**Possible causes:**
1. Reference cells not truly normal
2. Tumor purity too low
3. Window size too large

**Solutions:**
- Verify reference cell identity with marker genes
- Try different window parameters
- Check individual chromosomes manually

## AI Agent Test Cases

### Basic Usage
> "Run CNV inference on my tumor scRNA-seq data"

> "Identify copy number alterations in glioblastoma cells"

### Data Preparation
> "Add gene positions from GTF file to AnnData"

> "Prepare scRNA-seq data for CNV analysis"

### Analysis
> "Cluster cells by CNV profile"

> "Find which chromosomes are amplified in tumor cells"

> "Compare CNV patterns between cell types"

### Visualization
> "Create CNV heatmap grouped by cell type"

> "Plot UMAP colored by CNV clusters"

### Export
> "Export CNV results to CSV files"

## References

1. Miller et al. (2018). InferCNV of the TCGA Glioblastoma dataset. *bioRxiv*.
2. infercnvpy documentation: https://infercnvpy.readthedocs.io/
3. Original InferCNV: https://github.com/broadinstitute/inferCNV/wiki
