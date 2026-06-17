# Spatial Transcriptomics Batch Integration - Usage Guide

## Overview

Integrate multiple spatial transcriptomics slices/samples to remove technical batch effects while preserving biological spatial patterns. This skill focuses on **R/Seurat V5** workflows, as spatial transcriptomics analysis is predominantly performed in the Seurat ecosystem.

## Prerequisites

```r
# R
install.packages("Seurat")  # V5 by default
install.packages("harmony")
BiocManager::install("batchelor")  # For fastMNN
```

## Quick Start

Tell your AI agent what you want to do:
- "Integrate my Visium slices to remove batch effects"
- "Run Harmony on my merged spatial object"
- "Check if my consecutive sections have batch effects"
- "Integrate multiple ST samples with different conditions"

## How to Choose

### Step 1: Identify Your Data Type

| Platform | Spot Size | Notes |
|----------|-----------|-------|
| 10X Visium | ~55um | Most common; spots contain multiple cells |
| 10X Visium HD | ~2um | Near-single-cell resolution |
| 10X Xenium | Single-cell | Subcellular resolution; different workflow |
| Slide-seq | ~10um beads | Similar to Visium |
| Stereo-seq | ~0.5-0.7um | Nanometer resolution |
| CosMx/MERFISH | Single-cell | Different gene panels |

**Critical: Only integrate data from the same platform.** Cross-platform integration (e.g. Visium + Xenium) mixes resolution and gene panel differences with true biology.

### Step 2: Choose Normalization Strategy

| Strategy | Best For | Notes for ST |
|----------|----------|-------------|
| **Standard (LogNormalize)** | Most use cases | Default; works well for Visium spot data |
| **SCTransform** | Variable sequencing depth | Spot-level contains multiple cells; SCT assumptions less exact |

**Recommendation:** Start with Standard. SCTransform's regularized negative binomial regression assumes single-cell resolution, which Visium spots do not satisfy.

### Step 3: Choose Integration Method

| Method | Best For | Speed | When to Use |
|--------|----------|-------|-------------|
| **Harmony** | General purpose | Fast | Default for most scenarios |
| **Seurat CCA** | Conserved biology | Medium | Reference atlas mapping |
| **Seurat RPCA** | Large datasets | Fast | Faster alternative to CCA |
| **fastMNN** | Rare populations | Medium | Preserving rare spatial domains |

## Key Difference from Single-Cell Integration

### Image Slot Handling

When merging multiple spatial objects, each has its own H&E image. Seurat's `merge()` overwrites images with the same name (default: "slice1").

**This skill automatically handles this.** `prepare_input_spatial()` renames image slots before merge:

```r
# Before merge: image slots are renamed to prevent overwrite
# e.g. "slice1" -> "sample1_slice1", "sample2_slice1"
```

### Validation Uses Spatial Plots

Instead of just `DimPlot`, validate integration with `SpatialDimPlot` per slice:

```r
# Check batch mixing on each slice's H&E image
SpatialDimPlot(obj, group.by = "sample", ncol = 3)
```

## Common Scenarios

### "I want to integrate multiple Visium slices"

```r
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds", "slice3.rds"),
  sample_col = "sample"
)

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_standard(obj = obj, method = "harmony")
```

### "I want to check batch effects before and after"

```r
# Before integration: plot by sample on each slice
SpatialDimPlot(obj, group.by = "sample", ncol = 3)

# After integration: plot by sample on each slice (should be mixed)
SpatialDimPlot(obj, group.by = "sample", ncol = 3)

# Also check UMAP
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
DimPlot(obj, group.by = "sample")
```

### "I need to correct for multiple batch variables"

```r
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds"),
  sample_col = "sample"
)

source("scripts/r/seurat-v5/integrate.R")
obj <- harmony_spatial_v5_compat(
  obj = obj,
  group.by.vars = c("sample", "condition")
)
```

### "I'm using SCTransform"

```r
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds"),
  sample_col = "sample"
)

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_sct(obj = obj, method = "harmony")

# DE requires PrepSCTFindMarkers
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj)
```

## Tips

- **Same platform only:** Never integrate Visium with Xenium or MERFISH
- **Image slot names:** After `prepare_input_spatial()`, check `names(obj@images)` to see all preserved images
- **Consecutive sections:** Adjacent tissue sections from the same block often have minimal batch effects. Run integration only if you see clear batch-specific clusters in UMAP
- **Batch column:** Use `"sample"` or `"slice"` rather than `"orig.ident"` for spatial data ("orig.ident" often reflects capture area, not biological sample)
- **Resolution matters:** Visium HD (2um) and Visium (55um) should not be integrated together

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "Not a spatial object" | Input lacks `@images` slot | Ensure data was loaded with `Load10X_Spatial()` or similar |
| Images missing after merge | Image slots had same name before merge | Use `prepare_input_spatial()` which auto-renames |
| "Multiple platforms detected" | Mixing Visium/Xenium/etc. | Keep platforms separate; do not integrate across platforms |
| Batch still visible on SpatialDimPlot | Strong batch effects | Try RPCA or increase `npcs` |

## Related Skills

- **bio-single-cell-batch-integration** - For pure scRNA-seq integration (Python methods, V4 support)
- **bio-spatial-transcriptomics-data-io** - Loading spatial data
- **bio-spatial-transcriptomics-domains** - Spatial domain detection after integration
