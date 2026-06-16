---
name: bio-spatial-transcriptomics-communication-cellchat-r
description: Spatially-aware cell-cell communication analysis using SpatialCellChat (CellChat v3, R)
tool_type: r
primary_tool: SpatialCellChat
language: r
dependencies:
  - SpatialCellChat (>= 1.0)
  - Seurat (>= 5.0)
  - SeuratObject
  - jsonlite
  - dplyr
  - patchwork
  - igraph
system_requirements:
  - R >= 4.2.0
keywords: ["spatial-transcriptomics", "cell-communication", "CellChat", "SpatialCellChat", "ligand-receptor", "network", "Visium", "Xenium", "CosMx", "R"]
---

## Version Compatibility

- **R**: 4.2.0+
- **SpatialCellChat**: v3.0+ (GitHub: jinworks/SpatialCellChat)
- **CellChatDB**: v2 with spatial features
- **Seurat**: >= 5.0.0 (SpatialCellChat requires Seurat v5 for spatial features)
- **SeuratObject**: >= 5.0.0

## Installation

```r
# Install SpatialCellChat (CellChat v3) for spatial transcriptomics
remotes::install_github("jinworks/SpatialCellChat")

# Note: SpatialCellChat is an updated version of CellChat with single-cell
# resolution spatial analysis capabilities. The source code is currently
# maintained at a separate repository but will be merged into CellChat.
```

# Spatial Cell-Cell Communication with SpatialCellChat

Inference and analysis of spatially proximal cell-cell communication at single-cell resolution from spatially resolved transcriptomics.

## Quick Selector

| Feature | SpatialCellChat |
|---------|-----------------|
| **Data Types** | Visium, Visium HD, Xenium, Slide-seq, CosMx, Stereo-seq |
| **Distance** | Spatial distance-constrained communication |
| **Contact** | Contact-dependent signaling support |
| **Visualization** | Spatial network, hot spots, co-occurrence |
| **Resolution** | Single-cell level inference |

### When to Use SpatialCellChat

- Analyze cell-cell communication within spatial context at single-cell resolution
- Account for physical distance between cells/spots
- Identify contact-dependent (juxtacrine) signaling
- Visualize communication networks on tissue architecture
- Detect communication hot spots using Getis-Ord Gi statistics

---

## Scenarios

### Scenario 1: 10X Visium Basic Analysis

**Goal**: Run CellChat on standard 10X Visium data.

**Preconditions**:
- Seurat object with Visium data loaded via `Load10X_Spatial()`
- Cell type annotations in metadata (e.g., from deconvolution or clustering)
- `scalefactors_json.json` file from Space Ranger output

```r
source("scripts/r/cellchat_spatial.R")

# Recommended: provide scalefactors_json for accurate pixel-to-um conversion
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",           # metadata column with cell type annotations
  sample_name = "Visium_Sample",
  scalefactors_json = "spatial/scalefactors_json.json",  # recommended for accuracy
  assay = "Spatial",                # REQUIRED: avoid using integrated assay
  interaction_range = 250,          # max communication distance in um
  contact_range = 100               # Visium spot center-to-center distance
)

# Fallback: if scalefactors_json is unavailable, uses generic defaults (ratio=0.5)
# with a warning. Results may be less accurate.
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  assay = "Spatial",
  interaction_range = 250
)

# Agent checkpoint: if cellchat@net$count is all zeros, check that
# spatial.factors is a list (not data.frame) and scalefactors_json is correct
```

**Key parameters**:
- `scalefactors_json`: Path to Space Ranger's `scalefactors_json.json`. Recommended for accurate pixel-to-micrometer conversion. If omitted, uses generic defaults (ratio=0.5, tol=32.5) with a warning.
- `assay = "Spatial"`: Must explicitly specify to avoid accidentally using integrated assay.
- `interaction_range = 250`: Default for secreted signaling. Adjust to 200-300 for Visium.
- `contact_range = 100`: Default for Visium spots.

---

### Scenario 2: Visium with Cell Type Deconvolution

**Goal**: More accurate group-level communication by providing cell type proportions per spot.

**Preconditions**:
- Deconvolution results from RCTD, SPOTlight, or cell2location
- Proportion matrix: rows = spots, columns = cell types, values sum to 1 per spot

```r
# deconv_proportions: matrix with rownames = spot barcodes, colnames = cell types
# Must sum to 1 per row (spot)

cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  sample_name = "Visium_Sample",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial",
  cell_type_decomposition = deconv_proportions,  # spots x cell_types matrix
  avg_type = "avg",                               # "avg" or "sum"
  nboot = 100,                                    # bootstrap permutations
  interaction_range = 250,
  contact_range = 100
)

# When cell_type_decomposition is provided, computeAvgCommunProb_Visium()
# is automatically called after cell-level inference for group-level aggregation.
# Agent checkpoint: if group-level results look sparse, increase nboot to 200
```

**Key difference from Scenario 1**:
- Without `cell_type_decomposition`: spot-level inference only (each spot treated as one cell type)
- With `cell_type_decomposition`: group-level aggregation using spot proportions, more accurate for mixed spots

---

### Scenario 3: Single-Cell Resolution (Xenium / Visium HD / CosMx)

**Goal**: Analyze cell-cell communication on single-cell resolution spatial data.

**Preconditions**:
- Seurat object with single-cell resolution spatial data
- Cell type annotations (from segmentation or clustering)
- Coordinates already in micrometers (ratio = 1 for Xenium/Visium HD)

```r
# Xenium
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = xenium_data,
  group_by = "cell_type",
  sample_name = "Xenium_Sample",
  spatial_tech = "xenium",
  spot_size = 10,                   # typical cell diameter in um
  interaction_range = 250
)

# Visium HD
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = visium_hd_data,
  group_by = "cell_type",
  sample_name = "VisiumHD_Sample",
  spatial_tech = "visium_hd",
  spot_size = 8,
  interaction_range = 100           # smaller bins, reduce range
)

# CosMx (requires pixel-to-um conversion, ratio = 0.12028)
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = cosmx_data,
  group_by = "cell_type",
  sample_name = "CosMx_Sample",
  spatial_tech = "cosmx",
  spot_size = 10,
  interaction_range = 250
)

# Agent checkpoint: for CosMx, tol is auto-computed from nearest-neighbor distance
```

**Key differences from Visium**:
- No `scalefactors_json` needed (coordinates already in um)
- `spot_size` = cell diameter (~10 um), not spot size (~65 um)
- `contact_range` defaults to `spot_size` (cell diameter)
- No deconvolution needed (each cell is a single type)

---

### Scenario 4: Multiple Spatial Samples

**Goal**: Analyze and compare cell-cell communication across multiple samples.

**Principles**:
1. Process each sample **independently** first (separate SpatialCellChat objects)
2. Ensure cell type labels are **consistent** across all samples before merging
3. Use `mergeSpatialCellChat()` only after all samples pass individual checks
4. If labels differ, use `liftSpatialCellChat()` to unify them before merging

```r
# Step 1: Process each sample independently
chat_list <- run_cellchat_multi(
  seurat_list = list(sample1, sample2, sample3),
  group_by = "cell_type",
  sample_names = c("PA08", "PA11", "PA12"),
  scalefactors_list = list(sf1, sf2, sf3),  # list of scalefactors_json paths
  spatial_tech = "visium",
  interaction_range = 250,
  contact_range = 100
)
# Returns: named list of SpatialCellChat objects

# Agent checkpoint 1: Verify each sample has non-zero communications
for (name in names(chat_list)) {
  if (sum(chat_list[[name]]@net$count) == 0) {
    stop(sprintf("Sample %s has zero communications. Check spatial factors.", name))
  }
}

# Step 2: Check cell type label consistency across samples
all_types <- lapply(chat_list, function(x) levels(x@idents))
if (!all(sapply(all_types, function(x) identical(x, all_types[[1]])))) {
  # Labels differ - unify to the superset of all cell types before merge
  all_cell_types <- unique(unlist(all_types))
  chat_list <- lapply(chat_list, liftSpatialCellChat, group.new = all_cell_types)
}

# Step 3: Merge for comparison
chat_merged <- mergeSpatialCellChat(chat_list, add.names = names(chat_list))

# Step 4: Differential analysis (merged object only)
netVisual_diffInteraction(chat_merged, comparison = c("PA08", "PA12"))
```

**Common errors**:
- `"different cell types"` from `mergeSpatialCellChat()`: Run `liftSpatialCellChat()` on all samples first
- Inconsistent sample names: Ensure `run_cellchat_multi()` names match `mergeSpatialCellChat()` names
- Missing samples in merged object: Check that all samples have the same `group_by` column

---

### Scenario 5: Contact-Dependent Signaling Only

**Goal**: Identify juxtacrine (membrane-bound) signaling requiring physical contact.

```r
# Restrict database to Cell-Cell Contact only
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  sample_name = "Visium_Contact",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial",
  signaling_type = "Cell-Cell Contact",  # restrict DB to contact-dependent LR only
  contact_dependent = TRUE,               # enforce contact constraint
  contact_range = 100,                    # Visium: ~100um (spot diameter)
  interaction_range = 100                 # short range for contact only
)

# For single-cell resolution, contact_range = cell diameter (~10um)
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = xenium_data,
  group_by = "cell_type",
  spatial_tech = "xenium",
  signaling_type = "Cell-Cell Contact",
  contact_dependent = TRUE,
  spot_size = 10,                         # cell diameter
  interaction_range = 50                  # short range
)
```

**Key parameters**:
- `signaling_type = "Cell-Cell Contact"`: Subsets DB to membrane-bound LR pairs only
- `contact_dependent = TRUE`: Enforces that sender and receiver must be within `contact_range`
- `contact_range`: Physical contact distance. Visium ~100um (spot size), single-cell ~10um (cell diameter)

---

### Scenario 6: Extract Results and Visualize

**Goal**: Extract communication results and create visualizations.

**Extract results**:
```r
# All LR communications as data frame
df_net <- extract_communication_df(cellchat)
# Columns: source, target, ligand, receptor, prob, pval, interaction_name, pathway_name

# Filter by pathway
df_cxcl <- extract_communication_df(cellchat, signaling = "CXCL")

# Filter by direction
df_macro_to_t <- extract_communication_df(
  cellchat,
  sources.use = c("Macrophage"),
  targets.use = c("T_cell")
)

# Extract enriched LR pairs for a pathway
enriched_lr <- extract_enriched_lr(cellchat, signaling = "CXCL", do.group = FALSE)

# Summarize by cell group
summary <- summarize_communication(cellchat, measure = "count")
# Returns: cell_group, outgoing, incoming, total

# Export all results to files
export_cellchat_results(
  cellchat,
  output_dir = "./cellchat_results",
  prefix = "sample1",
  export_network = TRUE,
  export_centrality = TRUE
)
# Generates: _lr_pairs.csv, _pathways.csv, _count.csv, _weight.csv,
#            _centrality_*.csv (per pathway), .rds
```

**Visualize** (call native SpatialCellChat functions directly):
```r
# Spatial network on tissue
SpatialCellChat::netVisual_aggregate(
  cellchat,
  signaling = "CXCL",
  layout = "spatial"
)

# Cell type spatial distribution
SpatialCellChat::spatialDimPlot(cellchat, point.size = 1.5)

# Gene expression on tissue
SpatialCellChat::spatialFeaturePlot(
  cellchat,
  features = c("CXCL12", "CXCR4")
)

# LR pair expression on tissue
SpatialCellChat::spatialFeaturePlot(
  cellchat,
  pairLR.use = "CXCL12_CXCR4",
  do.binary = TRUE,
  cutoff = 0.05
)

# Communication distance distribution
SpatialCellChat::communicationDistPlot2(cellchat, signaling.type = "All")

# Hot spot detection (Getis-Ord Gi)
SpatialCellChat::spatialGiPlot(
  cellchat,
  slot.name = "netP",
  signaling.name = "CXCL",
  measure = "indeg"
)

# Outgoing/incoming scores side-by-side (use wrapper for merged plot)
plot_spatial_scoring(
  cellchat,
  signaling = "CXCL",
  slot_name = "netP",
  measure = c("outdeg", "indeg")
)

# Standard CellChat visualizations (non-spatial)
netVisual_bubble(cellchat, sources.use = 1:4, targets.use = 5:8)
netVisual_heatmap(cellchat, signaling = "CXCL", color.heatmap = "Reds")
netAnalysis_signalingRole_network(
  cellchat,
  signaling = "CXCL",
  slot.name = "netP",
  measure = c("outdeg", "indeg")
)
```

---

## Technology Settings

Quick reference for spatial factor configuration:

| Technology | ratio | tol | contact.range |
|------------|-------|-----|---------------|
| Visium | auto from JSON | 32.5 | 100 |
| Xenium | 1 | 5 | 10 |
| Visium HD | 1 | 5 | 10 |
| Slide-seq | 0.73 | 5 | 10 |
| CosMx | 0.12028 | auto | 10 |
| seqFISH/merFISH | 1 | 5 | 10 |

**Note**: `spatial.factors` must be a **list** (`list(ratio = ..., tol = ...)`) for SpatialCellChat, not a data.frame.

---

## Signaling Type Selection

Use `signaling_type` to restrict the ligand-receptor database before inference:

| Option | Meaning | When to Use |
|--------|---------|-------------|
| `"Secreted Signaling"` | Cytokines, chemokines, growth factors | Long-range paracrine communication |
| `"Cell-Cell Contact"` | Membrane-bound ligands and receptors | Juxtacrine signaling |
| `"ECM-Receptor"` | Extracellular matrix - receptor interactions | Tissue matrix microenvironment |
| `"all"` | All categories except non-protein | Exploratory analysis |

```r
# Analyze all three categories (default)
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  signaling_type = c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact")
)

# Contact-dependent only
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  signaling_type = "Cell-Cell Contact",
  contact_dependent = TRUE,
  contact_range = 100
)
```

---

## Best Practices

### Workflow Order (Internal)

The complete SpatialCellChat workflow executed by this skill:

1. `createSpatialCellChat()` - Create object from Seurat with coordinates
2. `subsetData()` - Subset to signaling genes
3. `preProcessing()` - Preprocess expression data
4. `identifyOverExpressedGenes(selection.method = "meringue")` - Find spatially variable genes
5. `identifyOverExpressedInteractions()` - Find over-expressed LR pairs
6. `computeCommunProb(distance.use = TRUE)` - Compute spatially constrained probabilities
7. `filterProbability()` - Filter non-significant communications
8. `filterCommunication(min.links = 10)` - Filter by minimum links
9. `computeCommunProbPathway()` - Aggregate to pathway level
10. `aggregateNet()` - Calculate aggregated network
11. `netAnalysis_computeCentrality()` - Compute centrality (cell-level + group-level)

For **Visium with deconvolution**, steps 7-11 are replaced by `computeAvgCommunProb_Visium()`.

### Agent Rules

1. **Always specify `assay = "Spatial"` for Visium** to avoid using integrated assay
2. **Never pass data.frame to `spatial_factors`** - must be `list(ratio = ..., tol = ...)`
3. **Process multi-sample data independently first**, verify non-zero results, then merge
4. **Use `liftSpatialCellChat()` before merge** if cell type labels differ across samples
5. **Provide `cell_type_decomposition` for Visium** when deconvolution results are available

### Choosing Interaction Range

| Data Type | Recommended Range | Rationale |
|-----------|-------------------|-----------|
| Visium (55um spots) | 200-300 um | ~4-5 spot diameters |
| Visium HD (8um bins) | 50-100 um | Multiple cell diameters |
| Xenium (cellular) | 100-250 um | 10-25 cell diameters |
| CosMx (subcellular) | 50-150 um | Depends on cell density |

### Choosing Cell Type Annotations

- Use `group_by` with broad cell types first (e.g., "T cell", "B cell")
- Avoid using too fine subtypes (>15 groups) - reduces statistical power
- Ensure each group has sufficient cells (>10 spots/cells)
- For Visium: provide `cell_type_decomposition` from deconvolution tools (RCTD, SPOTlight, cell2location) for more accurate group-level inference

### Troubleshooting

**No communication detected:**
- Check spatial coordinates are in correct units (pixels vs micrometers)
- Verify `scalefactors_json` is correct for Visium
- Ensure `spatial.factors` is a **list**, not data.frame
- Reduce `min_cells` or `min_links` threshold
- Try `selection.method = "meringue"` with `do.grid = TRUE` for large datasets

**Too many non-specific interactions:**
- Decrease `interaction_range`
- Use `contact_dependent = TRUE` for short-range only
- Increase `min_links` filter
- Use `cell_types` parameter to subset to relevant populations

**Spatial plot issues:**
- Ensure image data exists in Seurat object
- Adjust `alpha.image` for better visibility
- Verify spatial coordinates are correctly formatted (2-column matrix)

**Package errors:**
- Ensure SpatialCellChat is installed: `remotes::install_github("jinworks/SpatialCellChat")`
- Do not confuse `CellChat::createCellChat()` with `SpatialCellChat::createSpatialCellChat()`

---

## Output Description

| Slot | Description |
|------|-------------|
| `@data` / `@data.signaling` | Normalized expression data |
| `@net$prob` | Communication probabilities (cell-level) |
| `@net$count` | Number of interactions (group-level) |
| `@net$weight` | Interaction strength (group-level) |
| `@net$prob.cell` | Cell-level probability (3D sparse array) |
| `@net$centr` / `@net$centr.cell` | Centrality scores |
| `@netP$prob` | Pathway-level probabilities |
| `@netP$centr` / `@netP$centr.cell` | Pathway centrality scores |
| `@images$coordinates` | Spatial coordinates |
| `@images$spatial.factors` | Distance conversion factors |
| `@images$result.computeCellDistance` | Distance and contact matrices |
| `@meta` | Cell metadata with hot spot annotations |

---

## Related Skills

- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md)
- [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/SKILL.md)
- [bio-single-cell-communication-cellchat-r](../bio-single-cell-communication-cellchat-r/SKILL.md)

---

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. *Nature Protocols*.
2. SpatialCellChat documentation: https://github.com/jinworks/SpatialCellChat
3. CellChat documentation: https://github.com/jinworks/CellChat
4. Spatial CellChat tutorial: https://htmlpreview.github.io/?https://github.com/jinworks/SpatialCellChat/blob/master/tutorial/SpatialCellChat_analysis_of_spatial_transcriptomics_data.html
5. FAQ on spatial transcriptomics: https://htmlpreview.github.io/?https://github.com/jinworks/CellChat/blob/master/tutorial/FAQ_on_applying_CellChat_to_spatial_transcriptomics_data.html
