# Single-Cell Data I/O - Usage Guide

## Overview

This skill covers reading, writing, and creating single-cell data objects using both Seurat (R) and Scanpy (Python). Use it for loading 10X Genomics data, importing/exporting files, and managing cell and gene metadata.

## Prerequisites

**Python (Scanpy):**
```bash
pip install scanpy anndata
```

**R (Seurat):**
```r
install.packages('Seurat')
# For format conversion:
remotes::install_github('mojaveazure/seurat-disk')
```

## Quick Start

Ask your AI agent:

> "Load my 10X data into Scanpy"

> "Create a Seurat object from this count matrix"

> "Convert my h5ad file to Seurat format"

> "Load my 4 samples using a SampleSheet"

> "Load GEO data with merged MTX and metadata CSV"

## Example Prompts

### Loading Data
> "Read the 10X filtered_feature_bc_matrix folder"

> "Load this h5ad file and show the cell count"

> "Import the cellranger h5 output"

### Creating Objects
> "Create an AnnData object from this count matrix CSV"

> "Make a Seurat object from this sparse matrix"

### Multi-Sample Loading
> "Create a SampleSheet for my 4 samples and load them"

> "Load my samples as a list so I can QC them separately"

> "Load my 10X data and merge all samples into one object"

### GEO / Non-Standard Formats
> "Load GEO data with merged MTX and a metadata CSV"

> "Load this GEO H5 file as a Seurat object"

> "My data is a merged MTX from GEO with barcodes in a separate CSV"

### Metadata
> "Add sample labels to the cell metadata"

> "Show me all the cell metadata columns"

### Saving/Converting
> "Save this AnnData as h5ad"

> "Convert this Seurat object to h5ad for use in Python"

## What the Agent Will Do

### Standard Loading
1. Identify data format and choose appropriate reader
2. Load data into Seurat object or AnnData object
3. Add requested metadata
4. Save in requested format

### SampleSheet-Based Loading
1. Create or read a `samplesheet.csv` with sample metadata
2. Validate required columns (`sample_id`, `file_path`, `file_format`)
3. Load each sample using the correct format-specific loader
4. Inject optional metadata (`condition`, `batch`, `technology`, etc.)
5. Either merge into one object (default) or return as list
6. Report sample sizes and batch distribution

### GEO Non-Standard Formats
1. Detect the GEO data pattern (merged MTX, H5, etc.)
2. Align barcodes between MTX and metadata CSV (handle suffix differences)
3. Load counts and attach all metadata columns
4. Report sample sizes

## SampleSheet Format

```csv
sample_id,file_path,file_format,condition,batch,technology
PA08,data/PA08/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
PA11,data/PA11/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
```

| Column | Required | Description |
|--------|----------|-------------|
| `sample_id` | Yes | Unique sample identifier |
| `file_path` | Yes | Path to data file or directory |
| `file_format` | Yes | One of: 10x_mtx, 10x_h5, geo_mtx, geo_mtx_merged, geo_h5, h5ad, rds |
| `batch` | Recommended | Batch identifier for integration |
| `condition` | No | Biological condition/group |
| `technology` | No | Sequencing platform |

## Tool Comparison

| Task | Scanpy (Python) | Seurat (R) |
|------|-----------------|------------|
| Read 10X | `sc.read_10x_mtx()` | `Read10X()` |
| Create object | `ad.AnnData()` | `CreateSeuratObject()` |
| Native format | `.h5ad` | `.rds` |
| Access counts | `adata.X` | `LayerData(obj, layer='counts')` |

## Downstream Integration

After loading with `load_from_samplesheet(merge = TRUE)`:

```r
# R / Seurat v5
source('scripts/r/samplesheet.R')
obj <- load_from_samplesheet('samplesheet.csv', merge = TRUE)

# Directly pass to batch-integration
source('../bio-single-cell-batch-integration/scripts/r/seurat-v5/integrate.R')
obj <- integrate_v5_standard(obj = obj, method = 'harmony')
```

```python
# Python / Scanpy
from samplesheet import load_from_samplesheet
adata = load_from_samplesheet('samplesheet.csv', merge=True)

# sc.external.pp.harmony_integrate(adata, key='batch')
```

## Tips

- **Use h5ad for Python workflows** - Native AnnData format, efficient for large datasets
- **Use RDS for R workflows** - Preserves all Seurat object structure
- **Store raw counts** - Use `adata.raw` or `adata.layers['counts']` before normalization
- **Seurat v5 uses layers** - Not slots; use `LayerData()` instead of `GetAssayData()`
- **SeuratDisk for conversion** - Required for Seurat <-> AnnData conversion
