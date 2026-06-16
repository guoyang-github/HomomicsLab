---
name: bio-workflows-spatial-pipeline
description: End-to-end spatial transcriptomics workflow orchestrator for Visium, Xenium, and other platform data. Defines the standard 7-step analysis pipeline from raw spatial data to spatial domains, with Propose-Execute-Report mode and LLM diagnostic cards. Use when the user asks for complete spatial transcriptomics analysis, "analyze my Visium data", or "spatial transcriptomics pipeline".
tool_type: mixed
primary_tool: squidpy
workflow: true
depends_on:
  - bio-spatial-transcriptomics-data-io
  - bio-spatial-transcriptomics-preprocessing
  - bio-spatial-transcriptomics-neighbors
  - bio-spatial-transcriptomics-statistics
  - bio-spatial-transcriptomics-domains-bayesspace-r
  - bio-spatial-transcriptomics-domains-graphst
  - bio-spatial-transcriptomics-domains-spagcn
  - bio-spatial-transcriptomics-domains-stagate
  - bio-spatial-transcriptomics-deconvolution-cell2location
  - bio-spatial-transcriptomics-deconvolution-rctd-r
  - bio-spatial-transcriptomics-deconvolution-spotlight-r
  - bio-spatial-transcriptomics-deconvolution-tangram
  - bio-spatial-transcriptomics-communication-commot
  - bio-spatial-transcriptomics-communication-cellchat-r
  - bio-spatial-transcriptomics-communication-liana
  - bio-spatial-transcriptomics-batch-integration
  - bio-spatial-transcriptomics-integration-spclue
  - bio-spatial-transcriptomics-microenvironment-misty-r
  - bio-spatial-transcriptomics-layers
  - bio-spatial-transcriptomics-niches
qc_checkpoints:
  - after_loading: "Spots/cells detected match expected, spatial coordinates present, image aligned"
  - after_qc: "Low-quality spots filtered, tissue coverage adequate, genes per spot reasonable"
  - after_normalization: "HVG count 1500-3000, no batch effects visible (if multi-sample)"
  - after_integration: "Samples overlap in UMAP, spatial structure preserved"
  - after_clustering: "Clusters are visually separable on tissue, no image-artifact-driven clusters"
  - after_spatial_analysis: "Spatial neighbors graph built, SVGs show expected tissue patterns"
  - after_domains: "Spatial domains correspond to known tissue regions or histological layers"
  - after_deconvolution: "Cell type proportions sum to ~1 per spot, spatial patterns biologically plausible"
measurable_outcome: Execute skill workflow successfully with valid output within 15 minutes for typical Visium slide.
allowed-tools:
  - read_file
  - run_shell_command
---

# Spatial Transcriptomics Pipeline (Orchestrator)

Defines the standard end-to-end workflow from raw spatial data to spatial domains and downstream analyses.
**This skill is an orchestrator** — it defines the flow, state transitions, QC checkpoints, and agent-orchestrated decision points. Each step delegates implementation details to specialized sub-skills. Refer to sub-skills for advanced parameters, method comparisons, and troubleshooting.

## Key Design Principles

1. **Propose → Evaluate → Execute → Report (PEER)**: Every step follows this pattern internally:
   - **Propose**: Analyze data, recommend parameters with justification
   - **Evaluate**: Guardrail layer — hard-rule validation BEFORE execution (BLOCK / CAUTION / PROCEED)
   - **Execute**: Run the step
   - **Report**: Summarize results, flag issues, suggest next steps

   **PEER operates inside each step function**. Cross-step orchestration (pause, skip, conditional branching) is handled by the **Agent orchestration layer**, not by the pipeline runner. See "Agent Orchestration Model" below.

2. **Single-Language Paths**: Two complete independent paths — no R/Python switching mid-pipeline:
   - **Full R Path**: Seurat → BayesSpace → SpatialFeaturePlot
   - **Full Python Path**: Scanpy → Squidpy → spatial_scatter

3. **Evaluate Guardrail Layer**: Hard-rule pre-execution validation that intercepts dangerous parameters:
   - **BLOCK**: Parameter is dangerous — auto-correct if possible, otherwise stop
   - **CAUTION**: Parameter is suspicious — warn but allow proceed
   - **PROCEED**: Parameter passes all checks

   Example guards:
   - QC: Removal > 80% → auto-relax thresholds; > 50% → CAUTION
   - Integration: Batch mixing score < 0.1 → force skip; > 0.9 → CAUTION
   - Clustering: Resolution outside [0.1, 2.0] → clamp
   - Normalization: n_hvg outside [500, 5000] → clamp
   - Domain Detection: Method not in {spatial_leiden, bayesspace} → fallback
   - Spatial Analysis: No spatial coordinates → BLOCK

4. **Spatial-Aware Defaults**: Parameters tuned for spot-level data (Visium, Xenium):
   - Neighbor methods: grid (Visium) vs KNN (Xenium)
   - Normalization: LogNormalize (not SCT, to avoid spot-level overfitting)
   - Clustering resolutions adapted to spot counts

5. **Agent-Orchestrated Decision Points**: Five steps (2, 4, 5, 6, 7) require user confirmation. The pipeline scripts provide proposal data; the **Agent** consumes this data, formats the dialog, and pauses for user input. The `run_pipeline()` runner itself does NOT pause — it is a linear auto-runner. For true interactive execution, the Agent must call steps individually (see "Agent Orchestration Model" below).

   **Step classification:**
   - `[DECISION]`: Agent MUST present proposal and wait for user confirmation before Execute
   - `[AUTO]`: Step runs without user intervention; call `run_*_step()` directly
   - `[OPTIONAL]`: Triggered on demand, not part of default flow

## Version Compatibility

Reference examples tested with:
- **Python**: 3.9+, scanpy 1.10+, squidpy 1.3+, anndata 0.10+
- **R**: 4.2+, Seurat 5.0+, SeuratData 0.2+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed package and adapt the example to match the actual API rather than retrying.

**Squidpy / scanpy notes:**
- `sq.read.visium()` was removed in squidpy 1.6+; use `sc.read_visium()` (scanpy 1.10+) instead
- `sc.pl.spatial()` was removed in scanpy 1.12+; use `sq.pl.spatial_scatter()` instead
- Parameter mapping: `spot_size` → `size`; `alpha_img`, `bw`, `scale_factor` are not supported

**Seurat v5 notes:**
- `FindClusters(resolution = c(...))` vector syntax is deprecated; use loop over resolutions
- Cluster result columns are named `<assay>_snn_res.<res>`
- For spatial data, use `Load10X_Spatial()` not `Read10X()`

---

## Data State Flow

```
[Raw]                    (loaded from Space Ranger / Xenium output)
   ↓ Load Data
[Raw] + spatial coords   (coordinates in adata.obsm['spatial'] or images slot)
   ↓ QC Filtering
[Filtered]               (low-quality spots/cells removed)
   ↓ Normalization + HVG
[Normalized] + [HVG]     (log-normalized, HVGs selected)
   ↓ {multi-sample?}
   ├── yes → Integration → [Integrated]
   └── no  → continue
   ↓ Clustering (internal: scale → PCA → neighbors → UMAP → Leiden)
[Clustered] + [UMAP]     (Leiden clusters)
   ↓ Spatial Analysis
[Spatial-Analyzed]       (spatial neighbors, SVGs, enrichment)
   ↓ Domain Detection
[Domains]                (spatially constrained clusters)
   ↓ {optional downstream}
   ├── Deconvolution → [Deconvoluted]
   ├── Communication → [Communication]
   └── Microenvironment → [Microenv]
[Visualized]             (plots on tissue image)
```

| State | Check Method (Python) | Check Method (R) |
|-------|----------------------|------------------|
| `[Raw]` | `adata.X.dtype == np.integer` | `max(counts) > 100` |
| `[Filtered]` | Post-subset after QC | Post-`subset()` |
| `[Normalized]` | `adata.X.max() < 100` | `data` slot populated |
| `[HVG]` | `'highly_variable' in adata.var` | `VariableFeatures()` has entries |
| `[Scaled]`¹ | `adata.X.mean() ≈ 0` | `ScaleData()` completed |
| `[PCA]`¹ | `'X_pca' in adata.obsm` | `'pca' %in% names(reductions)` |
| `[Integrated]` | Batch-corrected embedding present | `harmony` or corrected PCA present |
| `[Clustered]` | `'leiden' in adata.obs` | `seurat_clusters` exists |
| `[UMAP]` | `'X_umap' in adata.obsm` | `'umap' %in% names(reductions)` |
| `[Spatial-Analyzed]` | `'spatial_connectivities' in adata.obsp` | Spatial neighbors computed |
| `[Domains]` | `'spatial_domain' in adata.obs` | Domain labels assigned |
| `[Deconvoluted]` | `prop_*` columns in `adata.obs` | Proportions in `meta.data` |

> **¹ Note:** `[Scaled]` and `[PCA]` are intermediate computational artifacts produced during the Clustering step. They are tracked via object metadata (e.g., `adata.obsm`, `seurat_obj@reductions`) but are **not** formal `pipeline_state` values in the state machine. The state machine transitions directly from `[Normalized]`/`[Integrated]` → `[Clustered]`.

---

## Agent Orchestration Model

This skill is designed for **two distinct execution contexts**:

### Context A: Agent Interactive (Recommended)

For `[DECISION]` steps, the Agent calls **Propose → Evaluate → [decide] → Execute → Report** explicitly.

**Why:** `run_*_step()` executes Propose + Evaluate + Execute in one call. The Agent cannot intercept a CAUTION before data is modified. Use the **decomposed API** (`propose_*`, `evaluate_*`, `execute_*`, `report_*`) when user confirmation is required.

**Agent decision flow:**

For **`[DECISION]`** steps (2, 4, 5, 6, 7) — **ALWAYS pause** after Propose + Evaluate:

```
proposal = propose_*(obj)
evaluation = evaluate_*(proposal, obj)

if evaluation.verdict == "BLOCK":
    if evaluation.adjusted:
        apply adjusted params to proposal
    → Report BLOCK reason to user and STOP (or offer adjusted params)
else:
    → Present full proposal to user (include CAUTION warning if applicable)
    → ASK user for confirmation (y/n or parameter adjustments)
    → END current response here. Do NOT call execute_*() in the same turn.
    → On next turn: User confirms → execute_*(obj, proposal)
    → On next turn: User rejects → adjust params, skip step, or stop pipeline

report = report_*(obj, proposal)  # Only after execute_* completes on next turn
```

**Critical rule for DECISION steps:** After presenting the proposal and asking for confirmation, the Agent **must stop its current response** and wait for the user to reply. The Agent must NOT proceed to execute_*() in the same LLM turn. This is because the user needs to see the proposal and respond before any data-modifying operation runs.

See each `[DECISION]` step in "Pipeline Steps" below for complete code examples.

### Context B: Script / Notebook (Auto Run)

`run_pipeline(mode="auto")` runs all steps sequentially without pausing.

```python
result = run_pipeline(data_path, mode="auto")
```

**`mode="verbose"`** prints proposal summaries to stdout (useful for debugging) but still does NOT pause.

**Note:** `run_pipeline()` is a linear auto-runner. It cannot pause mid-execution to wait for user input across LLM turns. The `mode` parameter accepts `"auto"` (silent) or `"verbose"` (print proposals). There is no interactive pause mode.

---

## Workflow Overview

### Core Pipeline (7 Steps)

| Step | Process | Type | Input State | Output State |
|------|---------|------|-------------|--------------|
| 1 | Load Spatial Data | `[AUTO]` | — | `[Raw]` + spatial coords |
| 2 | QC + Filter | `[DECISION]` | `[Raw]` | `[Filtered]` |
| 3 | Normalization + HVG | `[AUTO]` | `[Filtered]` | `[Normalized]` + `[HVG]` |
| 4 | Batch Integration (if needed) | `[DECISION]` | `[Normalized]` | `[Integrated]` |
| 5 | Clustering + UMAP | `[DECISION]` | `[Normalized]`/`[Integrated]` | `[Clustered]` + `[UMAP]` |
| 6 | Spatial Analysis | `[DECISION]` | `[Clustered]` | `[Spatial-Analyzed]` |
| 7 | Domain Detection | `[DECISION]` | `[Spatial-Analyzed]` | `[Domains]` |

### Optional Downstream Analyses

| Step | Process | Type | Input State | Output State | Reference Sub-Skill |
|------|---------|------|-------------|--------------|---------------------|
| 8 | Visualization | Auto | `[Domains]` | `[Visualized]` | — |
| 9 | Cell Type Deconvolution | Optional | `[Spatial-Analyzed]` | `[Deconvoluted]` | [cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/) / [rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/) / [spotlight-r](../bio-spatial-transcriptomics-deconvolution-spotlight-r/) / [tangram](../bio-spatial-transcriptomics-deconvolution-tangram/) |
| 10 | Spatial Communication | Optional | `[Deconvoluted]` or `[Spatial-Analyzed]` | `[Communication]` | [commot](../bio-spatial-transcriptomics-communication-commot/) / [cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/) / [liana](../bio-spatial-transcriptomics-communication-liana/) |
| 11 | Microenvironment | Optional | `[Spatial-Analyzed]` | `[Microenv]` | [misty-r](../bio-spatial-transcriptomics-microenvironment-misty-r/) |

**Type legend:** `[DECISION]` = Agent MUST present proposal and wait for user confirmation. `[AUTO]` = Step runs without user intervention. `[OPTIONAL]` = Triggered on demand, not part of default flow.

**Expected Runtime:** 15-30 minutes for single Visium slide; 1-2 hours for multi-sample or deconvolution
**Memory Requirements:** 8-16GB RAM for typical Visium; 32GB+ for Xenium / multi-sample

---

## Pipeline Steps

Steps are organized in execution order. Each step is tagged with its interaction type:
- `[AUTO]`: Execute directly with `run_*_step()`. No user confirmation needed.
- `[DECISION]`: Agent MUST call `propose_*` → `evaluate_*`, present proposal to user, wait for confirmation, then call `execute_*`.
- `[OPTIONAL]`: Triggered on demand, not part of default flow.

### Step 1: Data Loading & Platform Detection [AUTO]

**Trigger:** Pipeline start
**Action:** Auto-detect format and platform, recommend loader

| Detection | Platform Guess | Loader |
|-----------|---------------|--------|
| Directory with `spatial/` subdir | Visium | `sc.read_visium()` / `Load10X_Spatial()` |
| Directory with `cells.parquet` | Xenium | `sq.read.xenium()` / `LoadXenium()` |
| `.h5ad` file | Saved AnnData | `sc.read_h5ad()` |
| `.csv` file | SampleSheet | Delegate to data-io skill |

```python
# Python: auto-detect and load
from scripts.python.s01_load_spatial import load_spatial_data
adata = load_spatial_data("spaceranger_output/")
```

```r
# R: auto-detect and load
source('scripts/r/01_load_spatial.R')
obj <- load_spatial_data('spaceranger_output/')
```

### Step 2: QC Thresholds [DECISION]

**Trigger:** After loading
**Action:** Diagnose distributions, propose dynamic thresholds
**Input State:** `[Raw]`
**Output State:** `[Filtered]`

**Basis for recommendation:**
- `total_counts` / `nCount_Spatial`: Lower bound = max(500, 1st percentile)
- `n_genes_by_counts` / `nFeature_Spatial`: Minimum = 200
- `percent.mt`: Median-driven — <5% = stringent (15%), 5-10% = standard (20%), >10% = conservative (25-30%)
- Tissue coverage: % of spots with counts > 0 (spatial-specific)

```python
# Python: QC decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s02_qc_spatial import (
    propose_qc_thresholds, evaluate_qc_proposal,
    execute_qc_filter, report_qc
)

proposal = propose_qc_thresholds(adata)
evaluation = evaluate_qc_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK" and not evaluation.get("adjusted"):
    raise RuntimeError(f"QC blocked: {evaluation['reason']}")
else:
    if evaluation.get("adjusted"):
        print(f"Auto-adjusted: {evaluation['reason']}")
        proposal["thresholds"] = evaluation["adjusted_thresholds"]
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 QC Proposal:")
    print(f"  min_genes: {proposal['thresholds']['min_genes']}")
    print(f"  min_counts: {proposal['thresholds']['min_counts']}")
    print(f"  max_mt: {proposal['thresholds']['max_mt']:.1f}%")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...

adata_filtered = execute_qc_filter(adata, proposal)
report = report_qc(adata, adata_filtered, proposal)
```

```r
# R: QC decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/02_qc_spatial.R')

proposal <- propose_qc_thresholds(obj)
eval <- evaluate_qc_proposal(proposal, obj)

if (eval$verdict == "BLOCK" && !eval$adjusted) {
  stop(paste("QC blocked:", eval$reason))
} else {
  if (eval$adjusted) {
    proposal$thresholds <- eval$adjusted_thresholds
  }
  # Agent presents proposal to user and WAITS for confirmation
  message("📋 QC Proposal:")
  message(sprintf("  min_genes: %d", proposal$thresholds$min_genes))
  message(sprintf("  min_counts: %d", proposal$thresholds$min_counts))
  message(sprintf("  max_mt: %.1f%%", proposal$thresholds$max_mt))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n) ...
}

obj_filtered <- execute_qc_filter(obj, proposal)
report <- report_qc(obj, obj_filtered, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_qc_step(obj)$obj
```
```python
adata = run_qc_step(adata)["obj"]
```

---

### Step 3: Normalization + HVG [AUTO]

**Trigger:** After QC filtering
**Action:** Normalize counts, select highly variable genes
**Input State:** `[Filtered]`
**Output State:** `[Normalized]` + `[HVG]`

**R (Seurat):** Uses `NormalizeData + FindVariableFeatures` (LogNormalize, not SCT for spatial).
**Python (Scanpy):** Uses `sc.pp.normalize_total + sc.pp.log1p + sc.pp.highly_variable_genes`.

```r
# R: one-shot
source('scripts/r/03_normalize_spatial.R')
obj <- run_normalization_step(obj)$obj
```

```python
# Python: one-shot
from scripts.python.s03_normalize_spatial import run_normalization_step
adata = run_normalization_step(adata)["obj"]
```

---

### Step 4: Batch Integration [DECISION]

**Trigger:** After normalization, if `n_samples > 1`
**Action:** Diagnose batch mixing BEFORE integration, then recommend
**Input State:** `[Normalized]` + `[HVG]`
**Output State:** `[Integrated]` (or `[Normalized]` if skipped)

**Diagnosis strategy:**
1. Quick PCA + UMAP without integration
2. Compute batch mixing score (fraction of k-NN from same sample)
   - Score < 0.3: Samples well-mixed → **skip integration**
   - Score 0.3-0.6: Moderate batch effect → **integrate with Harmony**
   - Score > 0.6: Strong batch effect → **integrate with Harmony**

**Critical for spatial data:** Integration must preserve spatial coordinates and images per sample.

```python
# Python: Integration decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s04_integration_spatial import (
    propose_integration, evaluate_integration_proposal,
    execute_integration, report_integration
)

proposal = propose_integration(adata, sample_col='sample_id')
evaluation = evaluate_integration_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK" and not evaluation.get("adjusted"):
    print(f"Integration blocked: {evaluation['reason']}")
    # Skip integration, continue with uncorrected data
else:
    if evaluation.get("adjusted"):
        proposal["recommendation"] = evaluation["adjusted_recommendation"]
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Integration Proposal:")
    print(f"  Samples: {proposal['diagnostics']['n_samples']}")
    if "batch_mixing_score" in proposal["diagnostics"]:
        print(f"  Batch mixing score: {proposal['diagnostics']['batch_mixing_score']:.3f}")
    print(f"  Recommendation: {proposal['justification']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...
    adata = execute_integration(adata, proposal)

report = report_integration(adata, proposal)
```

```r
# R: Integration decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/04_integration_spatial.R')

proposal <- propose_integration(obj, sample_col = 'sample_id')
eval <- evaluate_integration_proposal(proposal, obj)

if (eval$verdict == "BLOCK" && !eval$adjusted) {
  message(paste("Integration blocked:", eval$reason))
  # Skip integration, continue with uncorrected data
} else {
  if (eval$adjusted) {
    proposal$recommendation <- eval$adjusted_recommendation
  }
  # Agent presents proposal to user and WAITS for confirmation
  message("📋 Integration Proposal:")
  message(sprintf("  Samples: %d", proposal$diagnostics$n_samples))
  if (!is.null(proposal$diagnostics$batch_mixing_score)) {
    message(sprintf("  Batch mixing score: %.3f", proposal$diagnostics$batch_mixing_score))
  }
  message(sprintf("  Recommendation: %s", proposal$justification))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n) ...
  obj <- execute_integration(obj, proposal)
}

report <- report_integration(obj, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_integration_step(obj, sample_col = 'sample_id')$obj
```
```python
adata = run_integration_step(adata, sample_col='sample_id')["obj"]
```

---

### Step 5: Clustering Resolution [DECISION]

**Trigger:** After integration decision
**Action:** Multi-resolution clustering, recommend default based on spot count
**Input State:** `[Normalized]`/`[Integrated]`
**Output State:** `[Clustered]` + `[UMAP]`

| Dataset Size | Resolutions | Default | Reason |
|-------------|-------------|---------|--------|
| <3k spots | 0.3, 0.5, 0.8 | 0.5 | Avoid over-segmentation |
| 3k-20k spots | 0.3, 0.5, 0.8, 1.2 | 0.8 | Standard range |
| >20k spots | 0.3, 0.5, 0.8, 1.2, 1.6 | 1.2 | May reveal fine domains |

```python
# Python: Clustering (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s05_cluster_spatial import (
    propose_clustering_params, evaluate_clustering_proposal,
    execute_clustering, report_clustering
)

proposal = propose_clustering_params(adata)
evaluation = evaluate_clustering_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK":
    raise RuntimeError(f"Clustering blocked: {evaluation['reason']}")
else:
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Clustering Proposal:")
    print(f"  PCs: {proposal['recommendation']['n_pcs']} (use {proposal['recommendation']['n_pcs_use']})")
    print(f"  Resolutions: {proposal['recommendation']['resolutions']}")
    print(f"  Default resolution: {proposal['recommendation']['default_resolution']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n or resolution override) ...
    adata = execute_clustering(adata, proposal)
report = report_clustering(adata, proposal)
```

```r
# R: Clustering (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/05_cluster_spatial.R')

proposal <- propose_clustering_params(obj)
eval <- evaluate_clustering_proposal(proposal, obj)

if (eval$verdict == "BLOCK") {
  stop(paste("Clustering blocked:", eval$reason))
} else {
  # Agent presents proposal to user and WAITS for confirmation
  message("📋 Clustering Proposal:")
  message(sprintf("  PCs: %d (use %d)", proposal$recommendation$npcs, proposal$recommendation$npcs_use))
  message(sprintf("  Resolutions: %s", paste(proposal$recommendation$resolutions, collapse = ", ")))
  message(sprintf("  Default resolution: %.1f", proposal$recommendation$default_resolution))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n or resolution override) ...
  obj <- execute_clustering(obj, proposal)
}
report <- report_clustering(obj, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_clustering_step(obj)$obj
```
```python
adata = run_clustering_step(adata)["obj"]
```

---

### Step 6: Spatial Analysis [DECISION]

**Trigger:** After clustering
**Action:** Build spatial neighbors, detect SVGs, compute enrichment
**Input State:** `[Clustered]`
**Output State:** `[Spatial-Analyzed]`

**Neighbor method selection:**
| Data Type | Recommended | Why |
|-----------|-------------|-----|
| Visium (hex grid) | Grid (6 neighs) | Matches hexagonal layout |
| Xenium / MERFISH | KNN (15 neighs) | High density, fixed neighborhood |
| Irregular spots | Delaunay / Radius | Adaptive to local density |

**SVG detection:** Moran's I (Python) or markvariogram (R)

```python
# Python: Spatial analysis (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s06_spatial_analysis import (
    propose_spatial_analysis, evaluate_spatial_proposal,
    execute_spatial_analysis, report_spatial_analysis
)

proposal = propose_spatial_analysis(adata)
evaluation = evaluate_spatial_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK":
    raise RuntimeError(f"Spatial analysis blocked: {evaluation['reason']}")
else:
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Spatial Analysis Proposal:")
    print(f"  Platform guess: {proposal['diagnostics']['platform_guess']}")
    print(f"  Neighbor method: {proposal['recommendation']['neighbor_method']}")
    print(f"  SVG test genes: {proposal['recommendation']['n_svg_test']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...
    adata = execute_spatial_analysis(adata, proposal)
report = report_spatial_analysis(adata, proposal)
```

```r
# R: Spatial analysis (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/06_spatial_analysis.R')

proposal <- propose_spatial_analysis(obj)
eval <- evaluate_spatial_proposal(proposal, obj)

if (eval$verdict == "BLOCK") {
  stop(paste("Spatial analysis blocked:", eval$reason))
} else {
  # Agent presents proposal to user and WAITS for confirmation
  message("📋 Spatial Analysis Proposal:")
  message(sprintf("  Platform guess: %s", proposal$diagnostics$platform_guess))
  message(sprintf("  Neighbor method: %s", proposal$recommendation$neighbor_method))
  message(sprintf("  SVG test genes: %d", proposal$recommendation$n_svg_test))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n) ...
  obj <- execute_spatial_analysis(obj, proposal)
}
report <- report_spatial_analysis(obj, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_spatial_analysis_step(obj)$obj
```
```python
adata = run_spatial_analysis_step(adata)["obj"]
```

---

### Step 7: Domain Detection [DECISION]

**Trigger:** After spatial analysis
**Action:** Recommend method based on data size and complexity
**Input State:** `[Spatial-Analyzed]`
**Output State:** `[Domains]`

| Condition | Recommended | Alternative |
|-----------|-------------|-------------|
| <50k spots, R available | BayesSpace | Spatial Leiden |
| >50k spots | Spatial Leiden | STAGATE (Python) |
| Complex architecture | STAGATE | BayesSpace |
| Need uncertainty | BayesSpace | — |

```python
# Python: Domain detection (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s07_domain_detection import (
    propose_domain_method, evaluate_domain_proposal,
    execute_domain_detection, report_domain_detection
)

proposal = propose_domain_method(adata)
evaluation = evaluate_domain_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK":
    raise RuntimeError(f"Domain detection blocked: {evaluation['reason']}")
else:
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Domain Detection Proposal:")
    print(f"  Method: {proposal['recommendation']['method']}")
    print(f"  Resolution: {proposal['recommendation']['resolution']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...
    adata = execute_domain_detection(
        adata,
        method=proposal["recommendation"]["method"],
        resolution=proposal["recommendation"]["resolution"]
    )
report = report_domain_detection(adata, proposal)
```

```r
# R: Domain detection (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/07_domain_detection.R')

proposal <- propose_domain_method(obj)
eval <- evaluate_domain_proposal(proposal, obj)

if (eval$verdict == "BLOCK") {
  stop(paste("Domain detection blocked:", eval$reason))
} else {
  # Agent presents proposal to user and WAITS for confirmation
  message("📋 Domain Detection Proposal:")
  message(sprintf("  Method: %s", proposal$recommendation$method))
  message(sprintf("  Resolution: %.1f", proposal$recommendation$resolution))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n) ...
  obj <- execute_domain_detection(
    obj,
    method = proposal$recommendation$method,
    resolution = proposal$recommendation$resolution
  )
}
report <- report_domain_detection(obj, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_domain_detection_step(obj)$obj
```
```python
adata = run_domain_detection_step(adata)["obj"]
```

---

## LLM Enhancement Mode

This pipeline features a **two-layer architecture**: a deterministic rule engine as the main execution path, with an LLM advisory layer that generates structured "diagnostic cards" at every step and critical decision point.

### Design Principle

- **Rule layer** (deterministic): `propose_*()` computes parameters, `evaluate_*()` guards against dangerous values, `execute_*()` runs code, `report_*()` generates PASS/CAUTION/WARNING. Fast, deterministic, works offline.
- **LLM layer** (advisory): `generate_llm_report()` assembles structured diagnostic data into a markdown "diagnostic card". The LLM agent reads this card and generates natural-language deep analysis.
- **No external API calls**: In the agent environment, the agent itself is the LLM. The enhancement works by outputting rich, structured diagnostic context that the agent consumes.

### Enabling LLM Enhancement

LLM enhancement is **enabled by default**. Disabling it depends on the execution mode:

**Script Mode** (`run_*_step` one-shot):
```r
# R: disable LLM diagnostic cards
result <- run_pipeline(..., use_llm = FALSE)

# Or per-step:
qc_result <- run_qc_step(obj, use_llm = FALSE)
```

```python
# Python: disable LLM diagnostic cards
result = run_pipeline(..., use_llm=False)

# Or per-step:
qc_result = run_qc_step(adata, use_llm=False)
```

**Agent Mode** (decomposed API):
No parameter needed — simply omit the `generate_llm_report()` call.

```r
# R: Agent mode without LLM card
proposal <- propose_qc_thresholds(obj)
eval <- evaluate_qc_proposal(proposal, obj)
obj_before <- obj
obj <- execute_qc_filter(obj, proposal)
report <- report_qc(obj_before, obj, proposal)
# No generate_llm_report() call — card is skipped
```

```python
# Python: Agent mode without LLM card
proposal = propose_qc_thresholds(adata)
evaluation = evaluate_qc_proposal(proposal, adata)
adata_before = adata
adata = execute_qc_filter(adata, proposal)
report = report_qc(adata_before, adata, proposal)
# No generate_llm_report() call — card is skipped
```

### Diagnostic Card Structure

Each step generates a markdown diagnostic card containing:

1. **Data Snapshot**: Key metrics (spot count, gene count, platform guess)
2. **Rule Proposal**: What the rule engine proposed and why
3. **Execution Report**: Results with PASS/CAUTION/WARNING status
4. **Cross-Step Context**: References to previous step reports
5. **LLM Analysis Task**: A framed question for the agent to answer

Example (Spatial Analysis step):

```markdown
## [LLM Diagnostic Card] Step 6: Spatial Analysis [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | 4521 |
| Neighbor method | grid |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **PASS** |
| SVGs detected | 87 |
| Top SVG | COL1A1 |

### LLM Analysis Task [DECISION POINT]
> 1. Do top SVGs match expected tissue architecture markers?
> 2. Is grid appropriate for this platform?
> 3. Do neighborhood enrichment patterns match known tissue biology?
> 4. Any clusters with no spatial structure (possible artifacts)?
```

### Critical Steps

Steps 2 (QC), 4 (Integration), and 7 (Domain Detection) are **critical steps** where poor decisions have the highest downstream impact. Their diagnostic cards include enhanced LLM analysis tasks. When the Agent uses the decomposed API (`propose_*` → `evaluate_*` → `execute_*`), it should read `llm_report` from the result and incorporate the analysis task into its reasoning before presenting the decision to the user. If using `run_*_step()` (one-shot), the Agent can only inspect the report after execution — CAUTION verdicts will have already executed.

### Saved Reports

**Script Mode**: When `use_llm = TRUE`, all diagnostic cards are saved to `output_dir/llm_reports/`:
- Individual files: `qc_diagnostic.md`, `normalization_diagnostic.md`, etc.
- Combined report: `combined_report.md`

In `mode = "auto"`, reports are saved to files without printing to the console. In `mode = "verbose"`, they are also printed to stdout.

**Agent Mode**: Diagnostic cards are generated only when the `generate_llm_report()` call is present in the Agent's code. They are returned as strings and can be saved manually or presented to the user.

---

## Full R Path (Seurat Ecosystem)

Complete pipeline with zero language switching.

```r
# === Full Pipeline (R) ===
# All scripts in scripts/r/

source('scripts/r/run_pipeline.R')

result <- run_pipeline(
  data_path = 'spaceranger_output/',
  output_dir = 'results',
  mode = 'auto',             # 'auto' = silent full run; 'verbose' = prints proposals
  sample_col = 'sample_id'   # for integration decision
)

# Access results
obj <- result$obj
reports <- result$reports
# reports$qc, reports$normalization, reports$integration, etc.
```

### Resume from intermediate state (R)

```r
# If you have a Seurat object after normalization and want to continue
source('scripts/r/run_pipeline.R')
obj <- readRDS('spatial_normalized.rds')
result <- resume_pipeline(obj, from_step = 5, mode = 'auto')
```

---

## Full Python Path (Scanpy + Squidpy Ecosystem)

Complete pipeline with zero language switching.

```python
# === Full Pipeline (Python) ===
# All scripts in scripts/python/

import sys
sys.path.insert(0, 'scripts/python')
from run_pipeline import run_pipeline

result = run_pipeline(
    data_path='spaceranger_output/',
    output_dir='results',
    mode='auto',              # 'auto' = silent full run; 'verbose' = prints proposals
    sample_col='sample_id'
)

# Access results
adata = result['obj']
reports = result['reports']
# reports['qc'], reports['normalization'], reports['integration'], etc.
```

### Resume from intermediate state (Python)

```python
from run_pipeline import resume_pipeline
import scanpy as sc

adata = sc.read_h5ad('adata_normalized.h5ad')
result = resume_pipeline(adata, from_step=5, mode='auto')
```

---

## Parameter Recommendations

| Step | Parameter | Default | When to Adjust |
|------|-----------|---------|----------------|
| QC | min_counts | 500 | Lower for low-UMI samples; higher for high-quality |
| QC | min_genes | 200 | Higher for Visium; lower for Xenium |
| QC | percent.mt | data-driven | <20% fresh frozen; <30% FFPE |
| Normalize | target_sum | 1e4 | Standard CPM for spatial |
| Normalize | n_hvg | 2000 | 1500-3000 is optimal range |
| Neighbors | n_neighs | 6 (Visium) / 15 (Xenium) | Grid for Visium; KNN for high-res |
| Cluster | resolution | 0.5-0.8 | Lower for broad domains; higher for subtypes |
| SVG | n_perms | 100 | Increase to 1000 for publication |
| Domains | resolution | 0.5-0.8 | Lower for fewer, larger domains |

---

## Troubleshooting

| Issue | Likely Cause | Solution | Delegate To |
|-------|--------------|----------|-------------|
| `spatial` not in obsm | Wrong load function | Use `sc.read_visium()` not `sc.read_10x_mtx()` | data-io |
| Clusters match image artifacts | QC not filtering edges/folds | Filter by image tissue detection | preprocessing |
| No spatially variable genes | Too few spots / low variance | Increase n_perms, check neighbor graph | statistics |
| Domains don't match histology | Wrong neighbor method / resolution | Try Delaunay or domain sub-skills | domains-* |
| Deconvolution proportions >1 | Model not converged | Check reference quality, increase epochs | deconvolution-* |
| Memory error | Xenium / large dataset | Use `backed` mode or subset | data-io |
| COMMOT install fails | Complex dependencies | Use conda environment or Docker | communication-commot |

---

## Related Skills

| Skill | Role in Pipeline |
|-------|-----------------|
| [bio-spatial-transcriptomics-data-io](../bio-spatial-transcriptomics-data-io/) | Loading non-standard formats, multi-sample merging |
| [bio-spatial-transcriptomics-preprocessing](../bio-spatial-transcriptomics-preprocessing/) | Advanced QC, SCTransform, spatial visualization |
| [bio-spatial-transcriptomics-neighbors](../bio-spatial-transcriptomics-neighbors/) | Neighbor graph methods (KNN, Delaunay, radius, grid) |
| [bio-spatial-transcriptomics-statistics](../bio-spatial-transcriptomics-statistics/) | Advanced spatial statistics (LISA, SPARK-X, Trendsceek) |
| [bio-spatial-transcriptomics-domains-stagate](../bio-spatial-transcriptomics-domains-stagate/) | Graph attention domain detection |
| [bio-spatial-transcriptomics-domains-bayesspace-r](../bio-spatial-transcriptomics-domains-bayesspace-r/) | Statistical domain detection with uncertainty |
| [bio-spatial-transcriptomics-domains-spagcn](../bio-spatial-transcriptomics-domains-spagcn/) | Histology-integrated domain detection |
| [bio-spatial-transcriptomics-domains-graphst](../bio-spatial-transcriptomics-domains-graphst/) | Joint spatial-expression clustering |
| [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/) | High-resolution deconvolution |
| [bio-spatial-transcriptomics-deconvolution-rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/) | Robust cell type discrimination |
| [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/) | Optimal transport communication |
| [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/) | Comprehensive LR analysis |
| [bio-spatial-transcriptomics-microenvironment-misty-r](../bio-spatial-transcriptomics-microenvironment-misty-r/) | Multi-view spatial modeling |
| [bio-spatial-transcriptomics-batch-integration](../bio-spatial-transcriptomics-batch-integration/) | Multi-sample batch correction |
| [bio-spatial-transcriptomics-niches](../bio-spatial-transcriptomics-niches/) | Cellular niche identification |
| [bio-spatial-transcriptomics-layers](../bio-spatial-transcriptomics-layers/) | Histological layer detection |
