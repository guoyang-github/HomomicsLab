---
name: bio-single-cell-communication-cellchat-r
description: Single-cell cell-cell communication analysis using CellChat (R). Infer ligand-receptor signaling networks, identify active pathways, compare conditions, and export results from annotated scRNA-seq data.
version: "1.1"
tool_type: r
primary_tool: CellChat
supported_tools: [Seurat, dplyr, ggplot2, patchwork, NMF, ggalluvial, igraph]
language: r
dependencies:
  - CellChat (GitHub: jinworks/CellChat)
  - Seurat >= 4.3.0
  - dplyr
  - ggplot2
  - patchwork
  - NMF
  - ggalluvial
  - igraph
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "cell-communication", "CellChat", "ligand-receptor", "signaling", "network", "R"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| CellChat | Latest GitHub | Install from `jinworks/CellChat` |
| Seurat | >= 4.3.0 | CellChat v2 works with Seurat v4 and v5 |
| NMF | | Required for `identify_cellchat_patterns()` |
| ggalluvial | | Required for river plots |
| patchwork | | Required for multi-panel plots |

```r
remotes::install_github("jinworks/CellChat")
install.packages(c("NMF", "ggalluvial", "patchwork", "dplyr", "ggplot2", "igraph"))
```

## Skill Overview

CellChat infers cell-cell communication networks from single-cell RNA-seq data using a curated database of ~3,300 validated ligand-receptor (L-R) interactions.

**When to use:**
- You have annotated scRNA-seq data and want to infer active signaling between cell types.
- You want to identify dominant senders, receivers, and mediators for specific pathways.
- You need to compare communication networks across biological conditions (e.g., control vs. treatment).
- You want global communication patterns or pathway-level summaries.

**When NOT to use:**
- You need spatially constrained communication — use [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) instead.
- You need multi-species beyond human/mouse — CellChat only provides `CellChatDB.human` and `CellChatDB.mouse`.
- You have no cell type annotations — run clustering/annotation first.
- You need explicit stoichiometric or kinetic modeling — CellChat is statistical, not mechanistic.

## Quick Selector

| Feature | CellChat |
|---------|----------|
| **Database** | ~3,300 validated L-R interactions (CellChatDB v2) |
| **Signaling types** | Secreted, ECM-Receptor, Cell-Cell Contact, Non-protein |
| **Analysis** | Network inference + systems-level patterns |
| **Comparison** | Multi-condition comparison via merged objects |

## Core Workflow

### Step 1: Prepare Data

**Input:** Annotated `Seurat` object.  
**Requirements:**
- Cell type labels in `meta.data` (e.g., `cell_type`).
- Gene symbols (e.g., `CXCL12`, `CXCR4`), not ENSEMBL IDs.
- Normalization: CellChat uses its own internal preprocessing; raw counts are acceptable.

```r
library(Seurat)
seurat_obj <- readRDS("annotated_data.rds")
table(seurat_obj$cell_type)
```

### Step 2: Run Analysis

```r
source("scripts/r/cellchat_analysis.R")

cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  sample_name = "Sample1",
  db_use = "CellChatDB.human",        # or "CellChatDB.mouse"
  signaling_type = "Secreted Signaling",
  type = "triMean",
  min_cells = 10,
  n_workers = 4
)
```

### Step 3: Visualize & Interpret

```r
# Aggregated network
plot_cellchat_circle(cellchat)

# Specific pathway
plot_cellchat_pathway(cellchat, signaling = "CXCL", layout = "circle")

# Source-target L-R pairs
plot_cellchat_bubble(
  cellchat,
  sources.use = c("T_cell", "B_cell"),
  targets.use = c("Tumor", "Macrophage")
)
```

### Step 4: Export

```r
export_cellchat_results(
  cellchat,
  output_dir = "./cellchat_results",
  prefix = "sample1"
)
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
library(CellChat)

# 1. Load annotated Seurat object
seurat_obj <- readRDS("annotated_data.rds")

# 2. Source the skill wrapper
source("scripts/r/cellchat_analysis.R")

# 3. Run CellChat
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  sample_name = "Sample1",
  db_use = "CellChatDB.human",
  signaling_type = "Secreted Signaling",
  type = "triMean",
  min_cells = 10,
  n_workers = 4
)

# 4. Visualize
cellchat <- compute_cellchat_centrality(cellchat)
plot_cellchat_circle(cellchat)
plot_cellchat_pathway(cellchat, signaling = "CXCL", layout = "circle")
plot_cellchat_bubble(cellchat, signaling = c("CXCL", "CCL"))

# 5. Export
export_cellchat_results(cellchat, output_dir = "./cellchat_results", prefix = "sample1")
```

## Skill-Provided Functions

**Pipeline orchestration**
- `run_cellchat(seurat_obj, group_by, ...)` — complete analysis pipeline (object creation → database → inference → pathway aggregation).
- `create_cellchat_object(seurat_obj, group_by, verbose)` — create CellChat object from Seurat.
- `set_cellchat_database(cellchat, db_use, signaling_type, verbose)` — load and subset CellChatDB.

**Visualization**
- `plot_cellchat_circle(cellchat, slot_name, title_name, ...)` — aggregated circle plot (`net$count` or `net$weight`).
- `plot_cellchat_bubble(cellchat, sources.use, targets.use, signaling, ...)` — bubble plot of L-R pairs.
- `plot_cellchat_pathway(cellchat, signaling, layout, ...)` — pathway-specific network (`circle`, `hierarchy`, `chord`).
- `plot_cellchat_signaling_roles(cellchat, signaling, ...)` — signaling role network (requires centrality).

**Systems analysis**
- `compute_cellchat_centrality(cellchat, slot_name)` — compute network centrality.
- `identify_cellchat_patterns(cellchat, pattern, k, ...)` — NMF-based communication patterns (`outgoing`/`incoming`).

**Comparison & export**
- `compare_cellchat_conditions(object.list, add.names, ...)` — merge multiple CellChat objects.
- `plot_cellchat_comparison(comparison, measure, ...)` — bar plot comparing total interactions.
- `extract_cellchat_communications(cellchat, slot_name, signaling, sources.use, targets.use)` — extract results as data frame.
- `summarize_cellchat(cellchat, measure)` — per-group outgoing/incoming/total summary.
- `export_cellchat_results(cellchat, output_dir, prefix, export_object)` — export CSVs and RDS.

## Official API — Agents Often Miss These

**1. `subsetData()` must be called before `identifyOverExpressedGenes()`**
The skill wrapper handles this internally. If calling CellChat native functions directly, always run `cellchat <- subsetData(cellchat)` first.

**2. Database subsetting requires `subsetDB()` with `key = "annotation"`**
```r
# Correct
CellChatDB.use <- subsetDB(CellChatDB, search = "Secreted Signaling", key = "annotation")

# Wrong
CellChatDB.use <- CellChatDB[CellChatDB$annotation == "Secreted Signaling", ]  # list object
```

**3. `signaling_type` accepts a vector or `"all"`**
Use `c("Secreted Signaling", "ECM-Receptor")` for multiple categories. Use `"all"` to keep the full database.

**4. `subsetCommunication()` is the canonical extractor**
```r
df <- subsetCommunication(cellchat, sources.use = c("Macrophage"), targets.use = c("T_cell"))
```

**5. Multi-condition comparison requires consistent cell type labels**
Use `liftCellChat()` (native CellChat) or harmonize labels before `compare_cellchat_conditions()`.

**6. `future::plan("multisession", workers = n_workers)` is set inside `run_cellchat()`**
To reset to sequential afterwards, call `future::plan("sequential")`.

## Common Pitfalls

1. **⚠️ Missing cell type annotations**  
   CellChat groups cells by `group_by`. If the column does not exist, `create_cellchat_object()` errors. Verify with `group_by %in% colnames(seurat_obj@meta.data)`.

2. **⚠️ Wrong species database**  
   Human data with `CellChatDB.mouse` (or vice versa) yields few or no interactions. Always match `db_use` to the species.

3. **⚠️ Gene symbols vs. ENSEMBL IDs**  
   CellChatDB uses gene symbols. ENSEMBL IDs cause near-zero overlap. Convert gene names beforehand.

4. **⚠️ Too many small cell groups**  
   Groups with fewer than `min_cells` are filtered out, which can remove rare populations. Lower `min_cells` if justified.

5. **⚠️ Confusing `type = "triMean"` and `"truncatedMean"`**  
   - `triMean` (default): more stringent, keeps stronger signals.  
   - `truncatedMean`: more permissive; set `trim` (e.g., `0.1`) to control.

6. **⚠️ Calling `plot_cellchat_pathway()` for a pathway not in results**  
   Always verify the pathway exists with `cellchat@netP$pathways` first.

7. **⚠️ `identify_cellchat_patterns()` requires the NMF package**  
   Install `NMF` before running pattern analysis.

## Scenarios

### Scenario 1: Basic Single-Sample Analysis

```r
source("scripts/r/cellchat_analysis.R")

cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  sample_name = "Tumor",
  db_use = "CellChatDB.human",
  signaling_type = "Secreted Signaling",
  min_cells = 10,
  n_workers = 4
)

plot_cellchat_circle(cellchat)
```

### Scenario 2: Subset to Specific Cell Types

```r
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  cell_types = c("T_cell", "Macrophage", "Tumor"),
  min_cells = 5
)

# Filter direction after analysis
df <- subsetCommunication(
  cellchat,
  sources.use = c("Macrophage"),
  targets.use = c("T_cell")
)
```

### Scenario 3: Multi-Condition Comparison

```r
control <- run_cellchat(seurat_control, group_by = "cell_type", sample_name = "Control")
treatment <- run_cellchat(seurat_treatment, group_by = "cell_type", sample_name = "Treatment")

comparison <- compare_cellchat_conditions(
  list(Control = control, Treatment = treatment),
  add.names = c("Control", "Treatment")
)

plot_cellchat_comparison(comparison)
netVisual_diffInteraction(comparison, weight.scale = TRUE)
```

**Agent checkpoint:** ensure identical cell type levels in both objects before comparison.

### Scenario 4: Systems Analysis

```r
# Centrality
cellchat <- compute_cellchat_centrality(cellchat)
netAnalysis_signalingRole_scatter(cellchat)

# Communication patterns
cellchat <- identify_cellchat_patterns(cellchat, pattern = "outgoing", k = 5)
netAnalysis_river(cellchat, pattern = "outgoing")
netAnalysis_dot(cellchat, pattern = "outgoing")
```

### Scenario 5: Extract and Export All Results

```r
# Extract all LR pairs
df_net <- extract_cellchat_communications(cellchat)

# Extract pathway-level
df_pathway <- extract_cellchat_communications(cellchat, slot_name = "netP")

# Per-group summary
summary <- summarize_cellchat(cellchat)

# Export to directory
export_cellchat_results(
  cellchat,
  output_dir = "./cellchat_results",
  prefix = "sample1"
)
```

Generated files: `_lr_pairs.csv`, `_pathways.csv`, `_summary.csv`, `.rds`.

## Signaling Type Selection

Use `signaling_type` to restrict the L-R database before inference:

| Option | Meaning | When to Use |
|--------|---------|-------------|
| `"Secreted Signaling"` | Cytokines, chemokines, growth factors | General analysis (default) |
| `"Cell-Cell Contact"` | Membrane-bound ligands and receptors | Juxtacrine signaling |
| `"ECM-Receptor"` | Extracellular matrix – receptor interactions | Tissue microenvironment |
| `"all"` | All categories combined | Exploratory analysis |

```r
# Single category
cellchat <- run_cellchat(seurat_obj, group_by = "cell_type", signaling_type = "Cell-Cell Contact")

# Multiple categories
cellchat <- run_cellchat(
  seurat_obj,
  group_by = "cell_type",
  signaling_type = c("Secreted Signaling", "ECM-Receptor")
)
```

## Parameters

### `run_cellchat()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Annotated Seurat object |
| `group_by` | char | `"cell_type"` | Metadata column defining cell groups |
| `sample_name` | char | `"Sample"` | Sample identifier |
| `db_use` | char | `"CellChatDB.human"` | Database: `"CellChatDB.human"` or `"CellChatDB.mouse"` |
| `signaling_type` | char / vector | `"Secreted Signaling"` | Signaling subset; use `"all"` or a vector for multiple |
| `type` | char | `"triMean"` | Average method: `"triMean"` or `"truncatedMean"` |
| `trim` | numeric | `NULL` | Trim value for `truncatedMean` |
| `population.size` | logical | `FALSE` | Consider cell population size in probability |
| `cell_types` | char vector | `NULL` | Subset to specific cell types before analysis |
| `min_cells` | int | `10` | Minimum cells per group |
| `n_workers` | int | `4` | Parallel workers for `future` |
| `verbose` | logical | `TRUE` | Print progress messages |

## Output Description

| Slot | Description |
|------|-------------|
| `@net$prob` | Communication probabilities (L-R pair level) |
| `@net$count` | Number of significant interactions (group level) |
| `@net$weight` | Interaction strength (group level) |
| `@netP$prob` | Pathway-level communication probabilities |
| `@netP$pathways` | Names of significant pathways |
| `@LR$LRsig` | Significant ligand-receptor pairs |

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `No communication detected` | Wrong annotations, wrong species DB, or `min_cells` too high | Check `group_by`; verify `db_use`; reduce `min_cells` |
| `No interactions found for signaling_type` | Invalid signaling type string | Use exact values from the table above |
| Too many weak interactions | `type = "truncatedMean"` with low `trim` | Use `type = "triMean"` or increase `min_cells` |
| Memory issues | Too many workers or large dataset | Reduce `n_workers` to 1 or 2 |
| Multi-condition merge fails | Cell type labels differ | Harmonize labels before `compare_cellchat_conditions()` |
| `NMF package required` | NMF not installed | `install.packages("NMF")` |

## Related Skills

- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) — Spatially-aware CellChat analysis
- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md) — Alternative spatial communication framework
- [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/SKILL.md) — OT-based spatial communication
- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) — Automated cell type annotation
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — Leiden/Louvain clustering

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. *Nature Protocols*.
2. Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. *Nature Communications*.
3. CellChat documentation: https://github.com/jinworks/CellChat
