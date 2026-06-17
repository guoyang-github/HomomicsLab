---
name: bio-single-cell-enrichment-decoupler-r
description: |
  decoupleR infers pathway and transcription factor activities from gene expression
  using prior knowledge networks and multiple statistical methods. Supports PROGENy
  (14 pathways), DoRothEA (confidence-ranked TFs), and CollecTRI (expanded TFs).
  10 inference methods including ULM, MLM, AUCell, GSVA, FGSEA.
tool_type: r
primary_tool: decoupleR
languages: [r]
keywords: ["single-cell", "decoupleR", "pathway", "TF", "enrichment", "footprint",
           "PROGENy", "DoRothEA", "ulm", "R"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | >= 4.2.0 | |
| decoupleR | >= 2.6.0 | Bioconductor |
| Seurat | >= 4.3.0 | Optional; v4 and v5 both supported |
| OmnipathR | >= 3.0.0 | Optional; only if using `get_*_network()` |
| ggplot2 | >= 3.3.0 | Visualization |
| dplyr | >= 1.0.0 | Data manipulation |
| tidyr | >= 1.2.0 | Data reshaping |

## Installation

```r
# Bioconductor
check_install <- BiocManager::install(c("decoupleR", "OmnipathR"))

# CRAN
install.packages(c("dplyr", "tidyr", "ggplot2"))
install.packages("Seurat")  # optional, for Seurat wrappers
```

## Skill Overview

decoupleR infers biological activities (pathway and transcription factor) from gene expression using prior knowledge networks. Rather than looking at direct expression levels, it infers *activity* by examining the expression patterns of target genes (footprint-based analysis).

**Core workflow**: Prepare expression matrix -> Load network -> Run activity inference -> (Optional) Multi-method consensus -> Add to Seurat -> Visualize

**Three network types:**

| Network | Type | Use For | Function |
|---------|------|---------|----------|
| **PROGENy** | Pathway | 14 signaling pathways (MAPK, PI3K, TGFb, etc.) | `get_progeny_network()` |
| **DoRothEA** | TF | Confidence-ranked TFs (A=high, D=low) | `get_dorothea_network()` |
| **CollecTRI** | TF | Expanded TF coverage | `get_collectri_network()` |

**When to use:**
- Inferring signaling pathway activities from gene expression footprints
- Identifying active transcription factors in specific cell populations
- Understanding *why* expression changes happen (upstream drivers)
- Comparing pathway/TF activities across conditions

**When NOT to use:**
- Need direct TF expression levels -> use pySCENIC instead
- Want ORA/GSEA on DEG lists -> use clusterProfiler
- Cross-dataset comparison without normalization -> scores are relative within a dataset
- Genes are ENSEMBL IDs -> decoupleR networks use HGNC (human) or MGI (mouse) symbols

**Input requirements:**
- **Expression matrix**: Log-normalized data (genes x samples/cells); rownames = gene symbols
- **Network**: Data frame with `source`, `target`, `weight` columns
- **Pre-check**: Verify gene overlap between matrix and network (>30% recommended)

```r
overlap <- check_gene_overlap(mat, net)
# Check overlap$overlap_fraction > 0.3
```

## Core Workflow

### Step 1 -- Prepare Expression Matrix

**Input**: Seurat object or gene expression matrix
**Output**: Numeric matrix (genes x samples/cells)

```r
# Seurat v4
mat <- Seurat::GetAssayData(seurat_obj, slot = "data")
# Seurat v5
mat <- Seurat::GetAssayData(seurat_obj, layer = "data")

# mat: genes (rows) x samples/cells (columns); rownames must be gene symbols
```

**Key requirement:** Use **log-normalized** data. Raw counts produce near-zero activity scores.

**State after Step 1:** `mat` is a numeric matrix with gene symbols as `rownames`.

---

### Step 2 -- Load Network

**Input**: Organism + network type
**Output**: Network data frame (`source`, `target`, `weight`)

```r
source("scripts/r/core_analysis.R")

# Pathways
net <- get_progeny_network(organism = "human", top = 500)

# TFs (high confidence: A, B)
tf_net <- get_dorothea_network(organism = "human", levels = c("A", "B"))

# Check overlap
overlap <- check_gene_overlap(mat, net)
```

| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `organism` | `"human"` | Gene symbol convention | `"mouse"` for murine data |
| `top` | `500` | PROGENy: top N responsive genes per pathway | Lower for stricter pathway definition |
| `levels` | `c("A","B","C")` | DoRothEA confidence levels | `c("A","B")` for high-confidence only |

**State after Step 2:** `net` is a data frame with `source`, `target`, `weight` columns.

---

### Step 3 -- Run Activity Inference

**Input**: Expression matrix + network
**Output**: Activity scores tibble (`source`, `condition`, `score`, `statistic`, `p_value`)

```r
# Single method (recommended: ULM)
acts <- run_ulm_analysis(mat, net = net, minsize = 5, center = FALSE)

# From Seurat directly
acts <- run_decoupler_seurat(
  seurat_obj, net = net, method = "ulm", minsize = 5
)
```

**Method selection guide:**

| Method | Speed | Best For |
|--------|-------|----------|
| **ULM** | Fast | General purpose, recommended default |
| **MLM** | Medium | When regulators may interact |
| **WMean** | Fast | Simple interpretation |
| **AUCell** | Medium | Small gene sets, single-cell |
| **ORA** | Fast | Binary / differential input |
| **GSVA** | Slow | Bulk-like behavior |
| **FGSEA** | Medium | Rank-based enrichment |
| **UDT** | Fast | Univariate linear model |
| **MDT** | Medium | Multivariate decision tree |
| **WSum** | Fast | Weighted sum (returns 3 statistics) |


| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `minsize` | `5` | Min target genes per source | Lower = more sources, noisier; raise to 10 for robustness |
| `center` | `FALSE` | Center expression by gene mean | ULM/MLM only; `TRUE` for cross-sample comparison |

**State after Step 3:** `acts` is a tibble. **Important:** `condition` = sample/cell name (colnames of input matrix), NOT a group label.

---

### Step 4 -- (Optional) Multi-Method Consensus

**Input**: Expression matrix + network
**Output**: Combined tibble with consensus scores

```r
acts_multi <- run_decoupler_multi(
  mat, net = net,
  methods = c("ulm", "mlm", "wsum"),
  minsize = 5
)

# Add consensus scores (median across methods)
acts_consensus <- create_consensus_score(acts_multi)
```

**State after Step 4:** `acts_consensus` contains original method rows + new `statistic == "consensus"` rows.

---

### Step 5 -- Add to Seurat & Visualize

**Input**: Activity scores + Seurat object
**Output**: Modified Seurat object + ggplot objects

```r
# Add to metadata (recommended)
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = FALSE)

# Or add as new assay
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = TRUE)

# Visualize
plot_activity_heatmap(acts, n_top = 15, title = "Pathway Activities")
plot_activity_reduced(seurat_obj, source = "TNFa", dimred = "umap")
plot_method_comparison(acts_multi, method_x = "ulm", method_y = "wsum")
```

**State after Step 5:** Pathway/TF activities mapped onto cells and visualized.

## Complete Pipeline

```r
library(Seurat)
library(decoupleR)
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# 1. Get log-normalized matrix
mat <- Seurat::GetAssayData(seurat_obj, layer = "data")

# 2. Load network
net <- get_progeny_network(organism = "human", top = 500)

# 3. Run ULM
acts <- run_ulm_analysis(mat, net = net, minsize = 5)

# 4. (Optional) Multi-method consensus
acts_multi <- run_decoupler_multi(mat, net, methods = c("ulm", "mlm"), minsize = 5)
acts_all <- create_consensus_score(acts_multi)

# 5. Add to Seurat & visualize
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = FALSE)
plot_activity_heatmap(acts, n_top = 10)
plot_activity_reduced(seurat_obj, source = "TNFa", dimred = "umap")
```

Shortcut: `run_decoupler_seurat()` wraps Steps 1-3 for Seurat objects.

```r
acts <- run_decoupler_seurat(seurat_obj, net = net, method = "ulm", minsize = 5)
```

## Skill-Provided Functions & API Reference

> **Note**: Core analysis functions (`run_*_analysis`) are thin wrappers around `decoupleR::run_*()` that handle column name mapping (`source`/`target`/`weight`). They add no statistical logic -- the computation is native decoupleR.

### Network Retrieval

| Function | Signature | Purpose |
|----------|-----------|---------|
| `get_progeny_network(organism="human", top=500)` | spatial_roe_analysis.R | PROGENy pathway network |
| `get_dorothea_network(organism="human", levels=c("A","B","C"))` | spatial_roe_analysis.R | DoRothEA TF network |
| `get_collectri_network(organism="human")` | spatial_roe_analysis.R | CollecTRI TF network |
| `get_custom_network(df, source_col, target_col, weight_col)` | spatial_roe_analysis.R | Standardize custom network |

### Activity Inference (Single Method)

| Function | Signature | DecoupleR Native | Key Params |
|----------|-----------|------------------|------------|
| `run_ulm_analysis(mat, net, minsize=5, center=FALSE)` | `decoupleR::run_ulm()` | `minsize`, `center` |
| `run_mlm_analysis(mat, net, minsize=5)` | `decoupleR::run_mlm()` | `minsize` |
| `run_wmean_analysis(mat, net, minsize=5)` | `decoupleR::run_wmean()` | `minsize` |
| `run_wsum_analysis(mat, net, minsize=5)` | `decoupleR::run_wsum()` | `minsize` (returns 3 stats) |
| `run_aucell_analysis(mat, net, minsize=5, nproc=1)` | `decoupleR::run_aucell()` | `minsize`, `nproc` |
| `run_ora_analysis(mat, net, minsize=5, n_up=NULL)` | `decoupleR::run_ora()` | `minsize`, `n_up` (validates binary input) |
| `run_gsva_analysis(mat, net, minsize=5, method="gsva", kcdf="Gaussian")` | `decoupleR::run_gsva()` | `minsize`, `method`, `kcdf` |
| `run_fgsea_analysis(mat, net, minsize=5, nperm=1000)` | `decoupleR::run_fgsea()` | `minsize`, `nperm` |
| `run_udt_analysis(mat, net, minsize=5)` | `decoupleR::run_udt()` | `minsize` |
| `run_mdt_analysis(mat, net, minsize=5)` | `decoupleR::run_mdt()` | `minsize` |

### Multi-Method & Integration

| Function | Signature | Purpose | Key Value Over Native |
|----------|-----------|---------|----------------------|
| `run_decouple(mat, net, statistics, minsize)` | `decoupleR::decouple()` | Dispatcher | Wrapper handles column mapping |
| `run_decoupler_multi(mat, net, methods, minsize)` | Multiple `decoupleR::run_*()` | Run multiple methods + bind | Returns combined tibble with `statistic` column |
| `create_consensus_score(acts)` | Custom median | Median consensus across methods | Adds `statistic == "consensus"` rows |
| `run_decoupler_seurat(seurat_obj, net, method, assay, slot, minsize)` | `decoupleR::run_*()` | Seurat wrapper | Cross-version Seurat (v4/v5); auto-extracts matrix |
| `add_decoupler_to_seurat(seurat_obj, acts, as_assay=FALSE)` | Custom | Store scores as metadata or assay | Sanitizes column names (`decoupleR_TNFa`) |

### Utilities

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_decoupler_input(mat, net)` | — | Check matrix + network compatibility |
| `check_gene_overlap(mat, net)` | — | Overlap statistics |
| `filter_network_by_size(net, minsize, maxsize)` | — | Filter sources by target count |
| `filter_network_by_confidence(net, min_level)` | — | Filter by confidence (A/B/C/D) |
| `get_top_activities(acts, n_top)` | — | Average score per source, ranked |
| `get_differential_activities(acts, cond1, cond2)` | — | Compare two conditions |
| `summarize_decoupler_results(acts)` | — | Rich summary (n_scores, methods, correlations) |
| `export_decoupler_results(acts, output_dir, prefix)` | — | Export long, wide, summary CSVs |

### Visualization

| Function | Signature | Purpose |
|----------|-----------|---------|
| `plot_activity_heatmap(acts, n_top, scale, title)` | — | ComplexHeatmap or ggplot2 heatmap |
| `plot_activity_reduced(seurat_obj, source, dimred)` | — | FeaturePlot on UMAP/t-SNE |
| `plot_top_activities(acts, condition, n_top)` | — | Bar plot of top sources |
| `plot_method_comparison(acts, method_x, method_y)` | — | Scatter + correlation |
| `plot_activity_scatter(acts, x_condition, y_condition)` | — | Condition comparison scatter |
| `plot_activity_volcano(diff_results, logfc_col, pval_col)` | — | Volcano for differential activities |
| `plot_consensus_scores(acts, top_n)` | — | Bar plot of consensus scores |
| `plot_decoupler_summary(acts, net, output_dir)` | — | Generate all summary plots |

## Official API -- Agents Often Miss These

### Native `decoupleR::run_*()` signatures

```r
# ULM (Univariate Linear Model)
decoupleR::run_ulm(mat, network, .source, .target, .mor, minsize = 5, center = FALSE)

# MLM (Multivariate Linear Model)
decoupleR::run_mlm(mat, network, .source, .target, .mor, minsize = 5)

# WSum (Weighted Sum) -- returns 3 statistics!
decoupleR::run_wsum(mat, network, .source, .target, .mor, minsize = 5, times = 100)
# Returns: "wsum", "corr_wsum", "norm_wsum"

# AUCell
decoupleR::run_aucell(mat, network, .source, .target, minsize = 5, nproc = 1)

# GSVA
decoupleR::run_gsva(mat, network, .source, .target, minsize = 5,
                    method = "gsva", kcdf = "Gaussian")

# Multi-method dispatcher
decoupleR::decouple(mat, network, .source, .target, .mor,
                    statistics = c("ulm", "mlm", "wsum"), minsize = 5)
```

### Result structure

**Activity scores tibble** (from all `run_*` methods):

| Column | Type | Content |
|--------|------|---------|
| `source` | Character | Pathway or TF name |
| `condition` | Character | Sample/cell name (colnames of input matrix) |
| `score` | Numeric | Activity score |
| `statistic` | Character | Method name ("ulm", "mlm", "wsum", etc.) |
| `p_value` | Numeric | P-value (when available) |

**Important:** `condition` = sample/cell name, NOT a group label. To compare groups, aggregate first or use `get_differential_activities()`.

**WSum returns 3 statistics:**
```r
unique(acts$statistic)  # "wsum" "corr_wsum" "norm_wsum"
```

**Metadata column names after `add_decoupler_to_seurat`:**
```r
# Source "TNFa" becomes:
seurat_obj$decoupleR_TNFa  # sanitized via make.names()
```

### Key differences from skill wrappers

| Aspect | Skill Wrapper | Native decoupleR |
|--------|--------------|-----------------|
| Column mapping | Auto: `.source="source"`, `.target="target"`, `.mor="weight"` | Manual: must specify bare names |
| Input | Matrix or Seurat | Matrix only |
| Seurat v5 | Auto-detects `slot` vs `layer` | Manual |
| Multi-method | `run_decoupler_multi()` binds results | `decouple()` returns list |

## Common Pitfalls

1. **Warning `run_wsum` returns 3 statistics, not 1**
   `run_wsum_analysis()` produces "wsum", "corr_wsum", "norm_wsum". If you run `run_decoupler_multi(..., methods = c("ulm", "wsum"))`, you get 4 statistic rows total. Filter by `statistic` before consensus.

2. **Warning `condition` = sample/cell name, not group label**
   The `condition` column equals `colnames(mat)` -- individual sample identifiers. To compare groups, aggregate first or use `get_differential_activities()` on pseudobulk averages.

3. **Warning Scores are relative -- never compare across datasets directly**
   Activity scores depend on the expression distribution of the input dataset. Compare within a dataset only.

4. **Warning Using raw counts instead of log-normalized data**
   Raw counts produce near-zero activity scores. Always pass log-normalized expression (Seurat `slot="data"` / `layer="data"`).

5. **Warning Low gene overlap between matrix and network**
   Common with non-HGNC symbols or heavily filtered gene sets. Check `check_gene_overlap(mat, net)$overlap_fraction`; if < 0.3, lower `minsize` to 3.

6. **Warning `add_decoupler_to_seurat` metadata names are sanitized**
   A source named "TNFa" becomes `decoupleR_TNFa` in `seurat_obj@meta.data`. Use `make.names(paste0("decoupleR_", source))` to find the exact column name.

7. **Warning `run_decouple()` passed invalid `.mor`/`.likelihood` to `decoupleR::decouple()`**
   `decouple()` does not accept `.mor` or `.likelihood` directly. The skill wrapper dispatches correctly without these arguments.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| All scores near zero | Raw counts or unnormalized data | Use log-normalized data (Seurat `slot="data"` / `layer="data"`) |
| `No common genes between mat and net` | Gene ID mismatch | Verify `rownames(mat)` uses HGNC symbols |
| `unused arguments (.mor = ...)` | Old `run_decouple()` bug | Update skill scripts |
| `could not find function "create_consensus_score"` | Old name was `run_consensus` | Use `create_consensus_score()` |
| Heatmap fails with `unused argument (main = title)` | `ComplexHeatmap` API mismatch | Update visualization.R |
| `aes_string() was deprecated` | ggplot2 deprecation | Update visualization.R |
| `cor(x, y)` error in `plot_method_comparison` | Each source missing one method | Ensure all sources have all methods, or filter first |

## Related Skills

- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) -- ORA/GSEA with richer organism support
- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) -- Python GSEA, ORA, ssGSEA
- [bio-single-cell-regulatory-pyscenic](../bio-single-cell-regulatory-pyscenic/SKILL.md) -- TF regulon inference (Python)
- [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md) -- Native PROGENy (14 pathways, simpler)

## References

1. Badia-i-Mompel P, et al. (2022). decoupleR: Ensemble of computational methods to infer biological activities from omics data. *Bioinformatics Advances*, 2(1), vbac016.
2. Schubert M, et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*, 9(1), 20.
3. Garcia-Alonso L, et al. (2019). Benchmark and integration of resources for the estimation of human transcription factor activities. *Genome Research*, 29(8), 1363-1375.
4. decoupleR documentation: https://saezlab.github.io/decoupleR/
