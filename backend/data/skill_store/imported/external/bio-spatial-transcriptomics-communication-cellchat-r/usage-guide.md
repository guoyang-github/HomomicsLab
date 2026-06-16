# SpatialCellChat Spatial Transcriptomics Usage Guide

## Overview

SpatialCellChat (CellChat v3) enables inference of cell-cell communication at **single-cell resolution** from spatially resolved transcriptomics by integrating gene expression with spatial distance and prior knowledge of ligand-receptor interactions.

## When to Use

- Analyze cell-cell communication in spatial context
- Account for physical cell proximity in communication
- Identify short-range vs long-range signaling
- Detect communication hot spots in tissue
- Visualize communication networks on tissue architecture

## Step-by-Step

### 1. Prepare Data

```r
library(Seurat)
library(SpatialCellChat)

# Load Visium data
visium_data <- Load10X_Spatial(
  data.dir = "path/to/spaceranger/outs",
  filename = "filtered_feature_bc_matrix.h5"
)

# Ensure cell type annotations exist
# For deconvoluted Visium, cell types may be from RCTD/SPOTlight/cell2location
table(visium_data$cell_type)

# For Visium with deconvolution, prepare proportion matrix
# Rows = spots, columns = cell types, values = proportions (sum to 1 per spot)
# deconv_proportions <- read.csv("deconvolution_results.csv", row.names = 1)
```

### 2. Run SpatialCellChat on Visium

```r
source("scripts/r/cellchat_spatial.R")

# Basic Visium analysis (recommended: provide scalefactors_json)
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  sample_name = "Visium_Sample",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial",              # explicit to avoid using integrated assay
  interaction_range = 250,
  contact_range = 100
)

# Fallback without scalefactors_json (uses generic defaults with warning)
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  assay = "Spatial",
  interaction_range = 250
)

# Visium with deconvolution proportions (recommended)
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  sample_name = "Visium_Sample",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial",
  cell_type_decomposition = deconv_proportions,
  avg_type = "avg",
  nboot = 100
)
```

### 3. Run on Single-Cell Resolution Data

```r
# For Xenium, Visium HD, CosMx
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = xenium_data,
  group_by = "cell_type",
  sample_name = "Xenium_Sample",
  spatial_tech = "xenium",
  spot_size = 10,
  interaction_range = 250
)
```

### 4. Multi-Sample Analysis

```r
# Step 1: Process each sample independently
chat_list <- run_cellchat_multi(
  seurat_list = list(sample1, sample2, sample3),
  group_by = "cell_type",
  sample_names = c("S1", "S2", "S3"),
  scalefactors_list = list(sf1, sf2, sf3),
  spatial_tech = "visium",
  interaction_range = 250
)

# Step 2: Verify each sample has results
for (name in names(chat_list)) {
  if (sum(chat_list[[name]]@net$count) == 0) {
    warning(sprintf("Sample %s has zero communications", name))
  }
}

# Step 3: Unify cell type labels if needed
all_types <- lapply(chat_list, function(x) levels(x@idents))
if (!all(sapply(all_types, function(x) identical(x, all_types[[1]])))) {
  all_cell_types <- unique(unlist(all_types))
  chat_list <- lapply(chat_list, liftSpatialCellChat, group.new = all_cell_types)
}

# Step 4: Merge for comparison
chat_merged <- mergeSpatialCellChat(chat_list, add.names = c("S1", "S2", "S3"))

# Step 5: Differential analysis
netVisual_diffInteraction(chat_merged, comparison = c("S1", "S2"))
```

### 5. Visualize Results

Call native SpatialCellChat functions directly:

#### Spatial Network Plot

```r
SpatialCellChat::netVisual_aggregate(
  cellchat,
  signaling = "CXCL",
  layout = "spatial"
)
```

#### Cell Type Spatial Distribution

```r
SpatialCellChat::spatialDimPlot(cellchat, point.size = 1.5)
```

#### Gene Expression on Tissue

```r
SpatialCellChat::spatialFeaturePlot(
  cellchat,
  features = c("CXCL12", "CXCR4"),
  point.size = 0.8
)
```

#### Ligand-Receptor Pair

```r
SpatialCellChat::spatialFeaturePlot(
  cellchat,
  pairLR.use = "CXCL12_CXCR4",
  do.binary = TRUE,
  cutoff = 0.05
)
```

#### Communication Distance Distribution

```r
SpatialCellChat::communicationDistPlot2(cellchat, signaling.type = "All")
```

#### Communication Hot Spots

```r
SpatialCellChat::spatialGiPlot(
  cellchat,
  slot.name = "netP",
  signaling.name = "CXCL",
  measure = "indeg"
)
```

#### Communication Scores on Tissue

```r
# Use wrapper for side-by-side outgoing/incoming plot
plot_spatial_scoring(
  cellchat,
  signaling = "CXCL",
  slot_name = "netP",
  measure = c("outdeg", "indeg")
)

# Or call native function directly
SpatialCellChat::spatialVisual_scoring(
  cellchat,
  signaling = "CXCL",
  slot.name = "netP",
  measure = "outdeg"
)
```

#### Standard CellChat Visualizations

```r
# Bubble plot
netVisual_bubble(cellchat, sources.use = 1:4, targets.use = 5:8)

# Circle plot (aggregated network)
cellchat <- aggregateNet(cellchat)
groupSize <- as.numeric(table(cellchat@idents))
netVisual_circle(
  cellchat@net$count,
  vertex.weight = groupSize,
  weight.scale = TRUE
)

# Heatmap
netVisual_heatmap(cellchat, measure = "count", color.heatmap = "Blues")

# Signaling role network
netAnalysis_signalingRole_network(
  cellchat,
  signaling = "CXCL",
  slot.name = "netP",
  measure = c("outdeg", "indeg"),
  measure.name = c("Sender", "Receiver"),
  width = 8, height = 3
)
```

### 6. Extract and Export Results

```r
# Extract all communications
df_net <- extract_communication_df(cellchat)
head(df_net)

# Extract specific signaling
df_cxcl <- extract_communication_df(cellchat, signaling = "CXCL")

# Extract enriched LR pairs for a pathway
enriched_lr <- extract_enriched_lr(cellchat, signaling = "CXCL", do.group = FALSE)

# Summarize by cell group
summary <- summarize_communication(cellchat)
print(summary)

# Export to CSV
write.csv(df_net, "cellchat_communications.csv")

# Save SpatialCellChat object
saveRDS(cellchat, "cellchat_spatial.rds")

# Export all results
export_cellchat_results(
  cellchat,
  output_dir = "./cellchat_results",
  prefix = "sample1",
  export_centrality = TRUE
)
```

## Specify Signaling Type

Use `signaling_type` to restrict the ligand-receptor database before running inference. You can pass a single string or a character vector to select multiple categories:

| Option | Meaning | When to Use |
|--------|---------|-------------|
| `"Secreted Signaling"` | Cytokines, chemokines, growth factors | Long-range paracrine communication |
| `"Cell-Cell Contact"` | Membrane-bound ligands and receptors | Juxtacrine signaling |
| `"ECM-Receptor"` | Extracellular matrix - receptor interactions | Tissue matrix microenvironment |
| `"all"` | All categories except non-protein | Exploratory analysis |

```r
# Default: analyze all three categories
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json"
)

# Contact-dependent signaling only
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  signaling_type = "Cell-Cell Contact",
  contact_dependent = TRUE,
  contact_range = 100
)

# Multiple signaling categories
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  signaling_type = c("Secreted Signaling", "ECM-Receptor")
)
```

## Subset to Specific Cell Types

Limit the analysis to selected cell types with the `cell_types` parameter:

```r
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  cell_types = c("T_cell", "Macrophage", "Fibroblast"),
  scalefactors_json = "spatial/scalefactors_json.json"
)
```

After analysis, filter by direction with `extract_communication_df()`:

```r
df <- extract_communication_df(
  cellchat,
  sources.use = c("Macrophage"),
  targets.use = c("T_cell")
)
```

## Technology-Specific Settings

### 10X Visium

```r
# Requires scalefactors_json.json from Space Ranger
scalefactors <- jsonlite::fromJSON("scalefactors_json.json")
conversion_factor <- 65 / scalefactors$spot_diameter_fullres

spatial_factors <- list(
  ratio = conversion_factor,
  tol = 65 / 2  # Half spot size
)
```

### Xenium / Visium HD / seqFISH / merFISH / STARmap

```r
# Coordinates already in micrometers
spatial_factors <- list(
  ratio = 1,
  tol = 10 / 2  # Half of typical cell size
)
```

### Slide-seq

```r
# Fixed conversion factor
spatial_factors <- list(
  ratio = 0.73,
  tol = 10 / 2
)
```

### CosMx

```r
# Pixel to um conversion: 0.12028 um per pixel
spatial_locs <- GetTissueCoordinates(cosmx_data)
d <- computeCellDistance(spatial_locs)

spatial_factors <- list(
  ratio = 0.12028,
  tol = min(d) * 0.12028 / 2
)
```

## AI Agent Test Cases

### Basic Usage

> "Run CellChat on my Visium spatial data"

```r
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json"
)
```

### Visium with Deconvolution

> "Analyze Visium data with cell type proportions"

```r
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  cell_type_decomposition = deconv_proportions,
  avg_type = "avg",
  nboot = 100
)
```

### Single-Cell Resolution

> "Analyze cell-cell communication on Xenium data"

```r
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = xenium_data,
  group_by = "cell_type",
  spatial_tech = "xenium"
)
```

### Multi-Sample

> "Run CellChat on multiple Visium samples and compare"

```r
chat_list <- run_cellchat_multi(
  seurat_list = list(s1, s2, s3),
  sample_names = c("S1", "S2", "S3"),
  scalefactors_list = list(sf1, sf2, sf3)
)

# Check consistency before merge
all_types <- lapply(chat_list, function(x) levels(x@idents))
if (!all(sapply(all_types, function(x) identical(x, all_types[[1]])))) {
  all_cell_types <- unique(unlist(all_types))
  chat_list <- lapply(chat_list, liftSpatialCellChat, group.new = all_cell_types)
}

chat_merged <- mergeSpatialCellChat(chat_list, add.names = c("S1", "S2", "S3"))
netVisual_diffInteraction(chat_merged, comparison = c("S1", "S3"))
```

### Contact-Dependent Signaling

> "Identify contact-dependent signaling in my spatial data"

```r
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "scalefactors.json",
  signaling_type = "Cell-Cell Contact",
  contact_range = 100,
  contact_dependent = TRUE
)
```

### Spatial Visualization

> "Plot CXCL signaling on the tissue"

```r
SpatialCellChat::netVisual_aggregate(
  cellchat,
  signaling = "CXCL",
  layout = "spatial"
)
```

> "Show ligand-receptor expression spatially"

```r
SpatialCellChat::spatialFeaturePlot(
  cellchat,
  pairLR.use = "CXCL12_CXCR4"
)
```

> "Find communication hot spots"

```r
SpatialCellChat::spatialGiPlot(
  cellchat,
  slot.name = "netP",
  signaling.name = "CXCL",
  measure = "indeg"
)
```

## Best Practices

1. **Distance Settings**: Use 250um for secreted signaling, 100um for Visium contact
2. **Cell Type Quality**: Use well-annotated cell types (from deconvolution or cell segmentation)
3. **Deconvolution for Visium**: Provide `cell_type_decomposition` for more accurate group-level inference
4. **Database Selection**: Use species-appropriate database (human/mouse)
5. **Multiple Samples**: Process separately with `run_cellchat_multi()`, verify results, then merge with `mergeSpatialCellChat()`. Use `liftSpatialCellChat()` if labels differ.
6. **Assay Selection**: For Visium, explicitly use `assay = "Spatial"` to avoid using integrated assay
7. **Signaling Types**: Analyze all three categories together for comprehensive results

## Troubleshooting

### No Communication Detected
- Check spatial coordinate format (pixels vs micrometers)
- Verify scalefactors are correct
- Ensure `spatial.factors` is a **list**, not data.frame
- Reduce `min_cells` or `min_links` threshold
- Try `selection.method = "meringue"` with `do.grid = TRUE` for large datasets

### Too Many Communications
- Decrease `interaction_range`
- Use `contact_dependent = TRUE` for short-range only
- Increase `min_links` filter
- Use `cell_types` to subset to relevant populations

### Spatial Plot Issues
- Ensure image data exists in Seurat object
- Adjust `alpha.image` for better visibility
- Verify spatial coordinates are correctly formatted (2-column matrix)

### Package Errors
- Ensure SpatialCellChat is installed: `remotes::install_github("jinworks/SpatialCellChat")`
- Do not confuse `CellChat::createCellChat()` with `SpatialCellChat::createSpatialCellChat()`

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. *Nature Protocols*.
2. SpatialCellChat tutorial: https://htmlpreview.github.io/?https://github.com/jinworks/SpatialCellChat/blob/master/tutorial/SpatialCellChat_analysis_of_spatial_transcriptomics_data.html
3. FAQ on spatial transcriptomics: https://htmlpreview.github.io/?https://github.com/jinworks/CellChat/blob/master/tutorial/FAQ_on_applying_CellChat_to_spatial_transcriptomics_data.html
