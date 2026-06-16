# Spatial Data I/O - Usage Guide

## Overview

This skill covers loading spatial transcriptomics data from various platforms including 10X Visium, Xenium, MERFISH, Slide-seq, CosMx, and more using **Squidpy/SpatialData (Python)** and **Seurat (R)**.

## Prerequisites

### Python
```bash
pip install squidpy spatialdata spatialdata-io scanpy anndata
```

### R
```r
install.packages('Seurat')
install.packages('jsonlite')
# Optional: for h5ad conversion
remotes::install_github('mojaveazure/seurat-disk')
```

## Quick Start

Tell your AI agent what you want to do:

### Python
- "Load my Visium data from the Space Ranger output using Python"
- "Read this Xenium experiment into an AnnData"
- "Load my MERFISH spatial data with Squidpy"

### R
- "Load my Visium data in R"
- "Read Xenium into a Seurat object"
- "Load CosMx data with Seurat"
- "Convert my h5ad spatial file to Seurat"
- "Load my 4 Visium samples using a SampleSheet"
- "Load GEO spatial data with h5 and spatial.tar.gz"

## Example Prompts

### Visium
> "Load my 10X Visium data"

> "Read the Space Ranger output in this folder"

> "Load Visium into a Seurat object"

> "Load multiple Visium samples from a SampleSheet"

### Xenium
> "Load my Xenium data"

> "Read single-cell spatial data from Xenium"

> "Load Xenium into R"

### GEO / Non-Standard Formats
> "Load GEO Visium data with h5 and spatial.tar.gz"

> "My GEO data has separate h5 and spatial files, load them"

> "Prepare GEO spatial data for standard analysis"

### Other Platforms
> "Load my MERFISH data"

> "Read Slide-seq bead coordinates"

> "Import CosMx data"

> "Convert spatial h5ad to RDS"

## SampleSheet Format

```csv
sample_id,file_path,file_format,technology,condition,batch,slice
PA08,data/PA08,visium,Tumor,Batch1,slice1
PA11,data/PA11,visium,Tumor,Batch1,slice1
PA02,data/PA02,xenium,Normal,Batch2,fov
PA12,data/PA12,geo_visium,Normal,Batch2,slice1
```

| Column | Required | Description |
|--------|----------|-------------|
| `sample_id` | Yes | Unique sample identifier |
| `file_path` | Yes | Path to data file or directory |
| `file_format` | Yes | One of: visium, visium_h5, xenium, cosmx, merfish, geo_visium, geo_visium_h5 |
| `technology` | No | Platform name |
| `batch` | Recommended | Batch identifier for integration |
| `condition` | No | Biological condition/group |
| `slice` | No | Slice/FOV name (Visium default: "slice1", Xenium default: "fov") |

## Python vs R: When to Use Which

| Task | Recommended | Reason |
|------|-------------|--------|
| Downstream with Squidpy/Scanpy | Python | Native spatial analysis ecosystem |
| Downstream with Seurat/CellChat (R) | R | Avoid format conversion |
| Multi-modal spatial (images + shapes) | Python | SpatialData handles this best |
| scRNA-seq + spatial integration | R or Python | Match your single-cell pipeline |
| Need to convert h5ad ↔ RDS | Both | Use SeuratDisk as bridge |

## What the Agent Will Do

### Python Path
1. Identify the appropriate reader for your platform (`squidpy.read.*` or `spatialdata_io`)
2. Load expression data into AnnData format
3. Extract spatial coordinates into `obsm['spatial']`
4. Load tissue images if available
5. Return a properly formatted spatial object

### R Path
1. Identify the appropriate Seurat reader (`Load10X_Spatial`, `LoadXenium`, etc.)
2. Load expression and spatial image data into a Seurat object
3. Extract spatial coordinates via `GetTissueCoordinates()`
4. Extract scale factors from `@images[[slice]]@scale.factors`
5. Return a properly formatted Seurat spatial object

### SampleSheet-Based Loading
1. Read and validate `samplesheet.csv` (required: `sample_id`, `file_path`, `file_format`)
2. For each sample, route to the correct technology-specific loader
3. Inject optional metadata (`condition`, `batch`, `technology`, etc.)
4. Either merge into one object (default) or return as list
5. For GEO Visium: auto-restructure `.h5` + `spatial.tar.gz` into standard Space Ranger format

### GEO Non-Standard Formats
1. Detect GEO pattern (h5 + spatial.tar.gz, or h5 only)
2. For h5 + tar.gz: extract tar.gz, move spatial files to `spatial/` directory
3. Rename h5 to `filtered_feature_bc_matrix.h5`
4. Call `Load10X_Spatial()` on the restructured directory
5. Report sample sizes and spatial image availability

## Tips

- **Visium** uses spots (~55um), while Xenium/MERFISH have single-cell resolution
- **SpatialData** is the newer Python format that handles multi-modal spatial data well
- **Library ID / Slice name** is needed to access images in Visium data
- **Coordinates** in Python are stored in `adata.obsm['spatial']` as (x, y) pairs
- **Coordinates** in R are accessed via `GetTissueCoordinates(seurat_obj)`
- **Scale factors** in R live in `seurat_obj@images$slice1@scale.factors`
- For **Seurat v5**, remember to call `JoinLayers()` after `merge()`
