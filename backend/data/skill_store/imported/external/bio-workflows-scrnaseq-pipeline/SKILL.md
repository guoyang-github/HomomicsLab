---
name: bio-workflows-scrnaseq-pipeline
description: End-to-end single-cell RNA-seq workflow orchestrator. Defines the standard 8-step analysis pipeline from raw counts to annotated cell types, with Propose-Evaluate-Execute-Report mode and agent-orchestrated decision points. Provides complete single-language paths (Full R via Seurat, Full Python via Scanpy) with zero cross-language switching. Use when the user asks for a complete scRNA-seq analysis, "analyze my single-cell data", or "run the full pipeline".
tool_type: mixed
primary_tool: Seurat
workflow: true
depends_on:
  - bio-single-cell-data-io
  - bio-single-cell-preprocessing
  - bio-single-cell-doublet-scdblfinder-r
  - bio-single-cell-doublet-scrublet
  - bio-single-cell-clustering
  - bio-single-cell-annotation-sctype-r
  - bio-single-cell-annotation-singler-r
  - bio-single-cell-annotation-celltypist
  - bio-single-cell-batch-integration
  - bio-single-cell-markers
qc_checkpoints:
  - after_loading: "Expected cell count, integer counts matrix, reasonable UMI distribution"
  - after_qc: "Cells after filtering within expected range, MT% distribution reviewed"
  - after_doublet: "Doublet rate ~2-10% for 10X data, no excessive removal"
  - after_normalization: "HVGs look sensible, no batch effects visible (if multi-sample)"
  - after_integration: "Samples overlap in UMAP, biological variation preserved"
  - after_clustering: "Clusters are visually separable, resolution chosen based on biology"
  - after_markers: "Top markers show expected cell-type-specific patterns"
  - after_annotation: "Annotations match known biology for tissue type"
measurable_outcome: Execute skill workflow successfully with valid output within 15 minutes for 5k-10k cells.
---

# Single-Cell RNA-seq Pipeline (Orchestrator)

Defines the standard end-to-end workflow from raw counts to annotated cell types.
**This skill is an orchestrator** — it defines the flow, state transitions, QC checkpoints, and agent-orchestrated decision points. Each step delegates implementation details to specialized sub-skills. Refer to sub-skills for advanced parameters, method comparisons, and troubleshooting.

## Key Design Principles

1. **Propose → Evaluate → Execute → Report (PEER)**: Every step follows this pattern internally:
   - **Propose**: Analyze data, recommend parameters with justification
   - **Evaluate**: Guardrail layer — hard-rule validation BEFORE execution (BLOCK / CAUTION / PROCEED)
   - **Execute**: Run the step
   - **Report**: Summarize results, flag issues, suggest next steps

   **PEER operates inside each step function**. Cross-step orchestration (pause, skip, conditional branching) is handled by the **Agent orchestration layer**, not by the pipeline runner. See "Agent Orchestration Model" below.

2. **Single-Language Paths**: Two complete independent paths — no R/Python switching mid-pipeline:
   - **Full R Path**: Seurat → scDblFinder → Harmony → ScType/SingleR
   - **Full Python Path**: Scanpy → Scrublet → sc.external.harmony → CellTypist

3. **Evaluate Guardrail Layer**: Hard-rule pre-execution validation that intercepts dangerous parameters:
   - **BLOCK**: Parameter is dangerous — auto-correct if possible, otherwise stop
   - **CAUTION**: Parameter is suspicious — warn but allow proceed
   - **PROCEED**: Parameter passes all checks

   Example guards:
   - QC: Removal > 80% → auto-relax thresholds; > 50% → CAUTION
   - Integration: Batch mixing score < 0.1 → force skip; > 0.9 → CAUTION
   - Clustering: Resolution outside [0.1, 2.0] → clamp
   - Normalization: n_hvg outside [500, 5000] → clamp
   - Markers: n_clusters < 2 → BLOCK

4. **Agent-Orchestrated Decision Points**: Four steps (2, 5, 6, 8) require user confirmation before execution. The pipeline scripts provide the proposal data; the **Agent** (LLM orchestrator) consumes this data, formats the decision dialog, and pauses for user input. The `run_pipeline()` runner itself does NOT pause — it is a linear auto-runner. For true interactive execution, the Agent must call steps individually (see "Agent Orchestration Model" below).

   **Step classification:**
   - `[DECISION]`: Agent MUST present proposal and wait for user confirmation before Execute
   - `[AUTO]`: Step runs without user intervention; call `run_*_step()` directly
   - `[CONDITIONAL]`: Normally Auto; upgrades to Decision when Evaluate returns CAUTION

## Version Compatibility

Reference examples tested with:
- **R**: 4.2+, Seurat 5.0+, scDblFinder 1.14+, SingleCellExperiment 1.20+
- **Python**: 3.9+, scanpy 1.10+, anndata 0.10+, celltypist 1.6+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

**Seurat v5 notes**:
- `FindClusters(resolution = c(...))` vector syntax is deprecated; use loop over resolutions
- Cluster result columns are named `<assay>_snn_res.<res>`; check `colnames(seurat_obj@meta.data)` if unsure
- `SCTransform` output uses `SCT` assay by default; downstream functions use it automatically
- For `as.SingleCellExperiment()`, ensure `SeuratObject` and `SingleCellExperiment` packages are compatible

---

## Data State Flow

Unified state labels follow [bio-single-cell-data-io](../bio-single-cell-data-io/) convention:

```
[Raw]                    (loaded from file)
   ↓ Load Data
[Raw] + QC metrics       (QC calculated, not yet filtered)
   ↓ QC Filtering
[Filtered]               (low-quality cells removed)
   ↓ Doublet Detection
[Filtered] + doublet labels
   ↓ Remove Doublets
[Clean]                  (doublets removed)
   ↓ Normalization + HVG
[Normalized] + [HVG]     (log/SCT normalized, HVGs selected)
   ↓ {Step 5: Batch Integration?}
   ├── yes → Batch Integration → [Integrated]
   └── no  → continue
   ↓ Clustering (internal: scale → PCA → neighbors → UMAP → Leiden)
[Clustered] + [UMAP]     (clusters assigned, UMAP embedded)
   ↓ Marker Detection
[Clustered] + markers    (top markers per cluster)
   ↓ Cell Type Annotation
[Annotated]              (cell type labels assigned)
```

| State | Check Method (Python) | Check Method (R) |
|-------|----------------------|------------------|
| `[Raw]` | `adata.X.dtype == np.integer` or `.max() > 1000` | `max(seurat_obj@assays$RNA$counts) > 100` |
| `[Filtered]` | Post-subset after QC thresholds | Post-`subset()` with QC thresholds |
| `[Clean]` | `~adata.obs['predicted_doublet']` | `seurat_obj$doublet_class == 'singlet'` |
| `[Normalized]` | `adata.X.max() < 100` | Assay switched to `SCT` or `data` slot populated |
| `[HVG]` | `'highly_variable' in adata.var` | `VariableFeatures(seurat_obj)` has entries |
| `[Scaled]`¹ | `adata.X.mean() ≈ 0` per column | `ScaleData()` completed |
| `[PCA]`¹ | `'X_pca' in adata.obsm` | `'pca' %in% names(seurat_obj@reductions)` |
| `[Integrated]` | Batch-corrected embedding present | `seurat_obj@reductions$harmony` or corrected PCA |
| `[Clustered]` | `'leiden' in adata.obs` | `seurat_clusters` column exists |
| `[UMAP]` | `'X_umap' in adata.obsm` | `'umap' %in% names(seurat_obj@reductions)` |
| `[Annotated]` | `'cell_type' in adata.obs` | `'cell_type' %in% colnames(seurat_obj@meta.data)` |

> **¹ Note:** `[Scaled]` and `[PCA]` are intermediate computational artifacts produced during the Clustering step. They are tracked via object metadata (e.g., `adata.obsm`, `seurat_obj@reductions`) but are **not** formal `pipeline_state` values in the state machine. The state machine transitions directly from `[Normalized]`/`[Integrated]` → `[Clustered]`.

---

## Agent Orchestration Model

This skill is designed for **two distinct execution contexts**:

### Context A: Agent Interactive (Recommended)

For `[DECISION]` and `[CONDITIONAL]` steps, the Agent calls **Propose → Evaluate → [decide] → Execute → Report** explicitly.

**Why:** `run_*_step()` executes Propose + Evaluate + Execute in one call. The Agent cannot intercept a CAUTION before data is modified. Use the **decomposed API** (`propose_*`, `evaluate_*`, `execute_*`, `report_*`) when user confirmation is required.

**Agent decision flow:**

For **`[DECISION]`** steps (2, 5, 6, 8) — **ALWAYS pause** after Propose + Evaluate:

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

report = report_*(obj, proposal)
```

**Critical rule for DECISION steps:** After presenting the proposal and asking for confirmation, the Agent **must stop its current response** and wait for the user to reply. The Agent must NOT proceed to execute_*() in the same LLM turn. This is because the user needs to see the proposal and respond before any data-modifying operation runs.

For **`[CONDITIONAL]`** steps (3) — **pause ONLY on CAUTION**:

```
proposal = propose_*(obj)
evaluation = evaluate_*(proposal, obj)

if evaluation.verdict == "BLOCK":
    → STOP or apply auto-adjusted params
elif evaluation.verdict == "CAUTION":
    → Present proposal + warning to user
    → ASK user for confirmation
    → END current response here. Do NOT call execute_*() in the same turn.
    → On next turn: User confirms → execute_*(obj, proposal)
    → On next turn: User rejects → adjust params or skip step
else:
    → Auto-execute execute_*(obj, proposal)

report = report_*(obj, proposal)
```

See each `[DECISION]` step in "Pipeline Steps" below for complete code examples.

### Context B: Script / Notebook (Auto Run)

`run_pipeline(mode="auto")` runs all steps sequentially without pausing. LLM diagnostic cards are still generated and saved to `output_dir/llm_reports/`, but they are not consumed in real-time.

```python
# One-shot execution for scripts/notebooks
result = run_pipeline(data_path, mode="auto")
```

**`mode="verbose"`** prints proposal summaries to stdout (useful for debugging) but still does NOT pause for user input.

**Note:** `run_pipeline()` is a linear auto-runner. It cannot pause mid-execution to wait for user input across LLM turns. The `mode` parameter accepts `"auto"` (silent) or `"verbose"` (print proposals). There is no interactive pause mode.

---

## Workflow Overview (8 Steps)

| Step | Process | Type | Input State | Output State | Reference Sub-Skill |
|------|---------|------|-------------|--------------|---------------------|
| 1 | Load Data | `[AUTO]` | — | `[Raw]` | [bio-single-cell-data-io](../bio-single-cell-data-io/) |
| 2 | QC + Filter | `[DECISION]` | `[Raw]` | `[Filtered]` | [bio-single-cell-preprocessing](../bio-single-cell-preprocessing/) |
| 3 | Doublet Detection | `[CONDITIONAL]` | `[Filtered]` | `[Clean]` | [bio-single-cell-doublet-scdblfinder-r](../bio-single-cell-doublet-scdblfinder-r/) (R) / [scrublet](../bio-single-cell-doublet-scrublet/) (Py) |
| 4 | Normalization + HVG | `[AUTO]` | `[Clean]` | `[Normalized]` + `[HVG]` | [bio-single-cell-preprocessing](../bio-single-cell-preprocessing/) |
| 5 | Batch Integration | `[DECISION]` | `[Normalized]` + `[HVG]` | `[Integrated]` | [bio-single-cell-batch-integration](../bio-single-cell-batch-integration/) |
| 6 | Dim Reduction + Clustering | `[DECISION]` | `[Normalized]`/`[Integrated]` | `[Clustered]` + `[UMAP]` | [bio-single-cell-clustering](../bio-single-cell-clustering/) |
| 7 | Marker Detection | `[AUTO]` | `[Clustered]` | `[Clustered]` + markers | [bio-single-cell-markers](../bio-single-cell-markers/) |
| 8 | Cell Type Annotation | `[DECISION]` | `[Clustered]` + markers | `[Annotated]` | [sctype-r](../bio-single-cell-annotation-sctype-r/) / [singler-r](../bio-single-cell-annotation-singler-r/) (R) / [celltypist](../bio-single-cell-annotation-celltypist/) (Py) |

**Type legend:** `[DECISION]` = Agent MUST present proposal and wait for user confirmation. `[AUTO]` = Step runs without user intervention. `[CONDITIONAL]` = Normally `[AUTO]`; upgrades to `[DECISION]` when Evaluate returns CAUTION.

**Expected Runtime:** 15-30 minutes for 5k-10k cells; 1-2 hours for 50k+ cells
**Memory Requirements:** 8-16GB RAM for typical datasets; 32GB+ for >100k cells

---

## Pipeline Steps

Steps are organized in execution order. Each step is tagged with its interaction type:
- `[AUTO]`: Execute directly with `run_*_step()`. No user confirmation needed.
- `[DECISION]`: Agent MUST call `propose_*` → `evaluate_*`, present proposal to user, wait for confirmation, then call `execute_*`.
- `[CONDITIONAL]`: Normally `[AUTO]`; upgrades to `[DECISION]` when `evaluate_*` returns CAUTION.

### Step 1: Load Data [AUTO]

**Trigger:** Pipeline start
**Action:** Auto-detect format, recommend loader
**Input State:** —
**Output State:** `[Raw]`

| Detection | Recommendation |
|-----------|----------------|
| Directory with `matrix.mtx` | Standard 10X Cell Ranger output |
| `.h5` file | 10X H5 (faster loading) |
| `.csv` file | SampleSheet (multi-sample) |
| `.rds` file | Existing Seurat object (resume) |

```r
# R: auto-detect and load
source('scripts/r/01_load.R')
obj <- load_data('filtered_feature_bc_matrix/', project = 'PBMC')
```

```python
# Python: auto-detect and load
from scripts.python.s01_load import load_data
adata = load_data('filtered_feature_bc_matrix.h5')
```

---

### Step 2: QC Thresholds [DECISION]

**Trigger:** After loading
**Action:** Diagnose distributions, propose dynamic thresholds
**Input State:** `[Raw]`
**Output State:** `[Filtered]`

**Basis for recommendation:**
- `nFeature_RNA`: Lower bound = 200 (standard); upper bound = 99th percentile × 1.2
- `percent.mt`: Median-driven — <5% = stringent (10%), 5-10% = standard (15%), >10% = conservative (20-25%)
- `nCount_RNA`: Minimum = max(500, 1st percentile of nCount)

**Agent workflow (MUST pause for user confirmation):**

```r
# R: Agent mode — DECISION step: ALWAYS pause for user confirmation
source('scripts/r/02_qc_decision.R')

proposal <- propose_qc_thresholds(obj)
eval <- evaluate_qc_proposal(proposal, obj)

if (eval$verdict == "BLOCK" && !eval$adjusted) {
  stop(paste("QC blocked:", eval$reason))
} else {
  if (eval$adjusted) {
    proposal$thresholds <- eval$adjusted_thresholds
  }
  # Agent presents proposal to user and WAITS for confirmation
  # (include CAUTION warning if applicable)
  message(paste("📋 QC Proposal:"))
  message(sprintf("  nFeature_RNA: %d - %d",
                  proposal$thresholds$nFeature_RNA_min,
                  proposal$thresholds$nFeature_RNA_max))
  message(sprintf("  nCount_RNA_min: %d", proposal$thresholds$nCount_RNA_min))
  message(sprintf("  percent.mt_max: %.1f%%", proposal$thresholds$percent_mt_max))
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n) ...
}

obj_filtered <- execute_qc_filter(obj, proposal)
report <- report_qc(obj, obj_filtered, proposal)
```

```python
# Python: Agent mode — DECISION step: ALWAYS pause for user confirmation
from scripts.python.s02_qc_decision import (
    propose_qc_thresholds, evaluate_qc_proposal,
    execute_qc_filter, report_qc
)

proposal = propose_qc_thresholds(adata)
evaluation = evaluate_qc_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK" and not evaluation.get("adjusted"):
    raise RuntimeError(f"QC blocked: {evaluation['reason']}")
else:
    if evaluation.get("adjusted"):
        proposal["thresholds"] = evaluation["adjusted_thresholds"]
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 QC Proposal:")
    print(f"  nFeature_RNA: {proposal['thresholds']['nFeature_RNA_min']} - {proposal['thresholds']['nFeature_RNA_max']}")
    print(f"  nCount_RNA_min: {proposal['thresholds']['nCount_RNA_min']}")
    print(f"  percent.mt_max: {proposal['thresholds']['percent_mt_max']:.1f}%")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...

adata_filtered = execute_qc_filter(adata, proposal)
report = report_qc(adata, adata_filtered, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_qc_step(obj)$obj
```
```python
adata = run_qc_step(adata)["obj"]
```

---

### Step 3: Doublet Detection [CONDITIONAL]

**Trigger:** After QC filtering
**Normal behavior:** Auto — runs without user intervention
**Upgrade condition:** `evaluate_doublet_proposal` returns CAUTION

```python
# Python: Conditional decision for doublet detection
from scripts.python.s03_doublet import propose_doublet_params, evaluate_doublet_proposal, run_doublet_step

# Pre-check (does not modify data)
proposal = propose_doublet_params(adata)
evaluation = evaluate_doublet_proposal(proposal, adata)

if evaluation["verdict"] == "CAUTION":
    print(f"⚠️ {evaluation['reason']}")
    # Agent presents to user:
    # "预期双细胞率 25%，建议按样本分别检测。是否调整？[按样本/继续合并]"
    # User chooses per-sample → pass sample_col
    result = run_doublet_step(adata, sample_col="sample_id", auto=True)
else:
    # Normal Auto run
    result = run_doublet_step(adata, auto=True)

adata = result["obj"]
report = result["report"]
```

```r
# R: Conditional decision for doublet detection
source('scripts/r/03_doublet.R')

proposal <- propose_doublet_params(obj)
eval <- evaluate_doublet_proposal(proposal, obj)

if (eval$verdict == "CAUTION") {
  message(paste("⚠️", eval$reason))
  # Agent asks user: per-sample or merged?
  result <- run_doublet_step(obj, sample_col = "sample_id", auto = TRUE)
} else {
  result <- run_doublet_step(obj, auto = TRUE)
}

obj <- result$obj
report <- result$report
```

### Step 4: Normalization + HVG [AUTO]

**Trigger:** After doublet removal
**Action:** Normalize counts, select highly variable genes
**Input State:** `[Clean]`
**Output State:** `[Normalized]` + `[HVG]`

**R (Seurat):** Uses `SCTransform` or `NormalizeData + FindVariableFeatures`.
**Python (Scanpy):** Uses `sc.pp.normalize_total + sc.pp.log1p + sc.pp.highly_variable_genes`.

```r
# R: one-shot
source('scripts/r/04_normalize.R')
obj <- run_normalization_step(obj)$obj
```

```python
# Python: one-shot
from scripts.python.s04_normalize import run_normalization_step
adata = run_normalization_step(adata)["obj"]
```

---

### Step 5: Batch Integration [DECISION]

**Trigger:** After normalization, if `n_batches > 1`
**Action:** Diagnose batch mixing BEFORE integration, then recommend

**Diagnosis strategy:**
1. Quick PCA + UMAP without integration
2. Color by batch/sample
3. Compute batch mixing score (fraction of k-NN from same batch)
   - Score < 0.3: Batches well-mixed → **skip integration**
   - Score 0.3-0.6: Moderate batch effect → **integrate with Harmony**
   - Score > 0.6: Strong batch effect → **integrate with Harmony or RPCA**

**Method selection logic:**
| Condition | Recommended | Alternative |
|-----------|-------------|-------------|
| 2-5 batches, <50k cells | Harmony | fastMNN |
| >5 batches or >50k cells | RPCA (R) / Scanorama (Python) | scVI |
| Reference + query | CCA | RPCA |
| Preserving rare populations | fastMNN | Harmony |

```r
# R: Integration decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/05_integration_decision.R')

proposal <- propose_integration(obj, batch_col = 'sample_id')
eval <- evaluate_integration_proposal(proposal, obj)

if (eval$verdict == "BLOCK" && !eval$adjusted) {
  message(paste("Integration blocked:", eval$reason))
  # Skip integration, continue with uncorrected data
} else {
  if (eval$adjusted) {
    proposal$recommendation <- eval$adjusted_recommendation
  }
  # Agent presents proposal to user and WAITS for confirmation
  message(sprintf("📋 Integration Proposal:"))
  message(sprintf("  Batches: %d", proposal$diagnostics$n_batches))
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

```python
# Python: Integration decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s05_integration_decision import (
    propose_integration, evaluate_integration_proposal,
    execute_integration, report_integration
)

proposal = propose_integration(adata, batch_col='sample_id')
evaluation = evaluate_integration_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK" and not evaluation.get("adjusted"):
    print(f"Integration blocked: {evaluation['reason']}")
    # Skip integration, continue with uncorrected data
else:
    if evaluation.get("adjusted"):
        proposal["recommendation"] = evaluation["adjusted_recommendation"]
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Integration Proposal:")
    print(f"  Batches: {proposal['diagnostics']['n_batches']}")
    if "batch_mixing_score" in proposal["diagnostics"]:
        print(f"  Batch mixing score: {proposal['diagnostics']['batch_mixing_score']:.3f}")
    print(f"  Recommendation: {proposal['justification']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n) ...
    adata = execute_integration(adata, proposal)

report = report_integration(adata, proposal)
```

**Script mode (one-shot):**
```r
obj <- run_integration_step(obj, batch_col = 'sample_id')$obj
```
```python
adata = run_integration_step(adata, batch_col='sample_id')["obj"]
```

---

### Step 6: Clustering Resolution [DECISION]

**Trigger:** After integration decision
**Action:** Multi-resolution clustering (0.3, 0.5, 0.8, 1.2), recommend default based on cell count

| Dataset Size | Resolutions | Default | Reason |
|-------------|-------------|---------|--------|
| <3k cells | 0.3, 0.5, 0.8 | 0.5 | Avoid over-clustering |
| 3k-20k cells | 0.3, 0.5, 0.8, 1.2 | 0.8 | Standard range |
| >20k cells | 0.3, 0.5, 0.8, 1.2, 1.6 | 1.2 | May reveal subtypes |

```r
# R: Clustering (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/06_cluster.R')

proposal <- propose_clustering_params(obj)
eval <- evaluate_clustering_proposal(proposal, obj)

if (eval$verdict == "BLOCK") {
  stop(paste("Clustering blocked:", eval$reason))
} else {
  # Agent presents proposal to user and WAITS for confirmation
  message(sprintf("📋 Clustering Proposal:"))
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

```python
# Python: Clustering (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s06_cluster import (
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

**Script mode (one-shot):**
```r
obj <- run_clustering_step(obj)$obj
```
```python
adata = run_clustering_step(adata)["obj"]
```

---

### Step 7: Marker Detection [AUTO]

**Trigger:** After clustering
**Action:** Find differentially expressed genes per cluster
**Input State:** `[Clustered]`
**Output State:** `[Clustered]` + markers

```r
# R: one-shot
source('scripts/r/07_markers.R')
obj <- run_marker_step(obj)$obj
```

```python
# Python: one-shot
from scripts.python.s07_markers import run_marker_step
adata = run_marker_step(adata)["obj"]
```

---

### Step 8: Cell Type Annotation Method [DECISION]

**Trigger:** After marker detection
**Action:** Recommend method based on data characteristics

| Condition | Recommended | Alternative |
|-----------|-------------|-------------|
| Tissue known | ScType (R) / CellTypist (Python) | Manual with markers |
| Large dataset (>10k) | SingleR (R) / CellTypist (Python) | Manual |
| Immune cells | ScType / SingleR / CellTypist | — |
| Novel populations | Manual with top markers | — |

```r
# R: Annotation decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
source('scripts/r/08_annotation_decision.R')

proposal <- propose_annotation_method(obj, tissue_hint = 'Immune system')
eval <- evaluate_annotation_proposal(proposal, obj)

if (eval$verdict == "BLOCK") {
  stop(paste("Annotation blocked:", eval$reason))
} else {
  # Agent presents proposal to user and WAITS for confirmation
  message(sprintf("📋 Annotation Proposal:"))
  message(sprintf("  Recommended method: %s", proposal$recommendation$method))
  if (!is.null(proposal$recommendation$tissue)) {
    message(sprintf("  Tissue: %s", proposal$recommendation$tissue))
  }
  if (eval$verdict == "CAUTION") {
    message(paste("⚠️", eval$reason))
  }
  # ... WAIT for user confirmation (y/n or method override) ...
  method <- proposal$recommendation$method
  if (method == "ScType") {
    obj <- execute_sctype_annotation(obj, tissue = proposal$recommendation$tissue)
  } else if (method == "SingleR") {
    obj <- execute_singler_annotation(obj, tissue = proposal$recommendation$tissue)
  }
}
report <- report_annotation(obj)
```

```python
# Python: Annotation decision (Agent mode — decomposed API)
# DECISION step: ALWAYS present proposal and wait for user confirmation
from scripts.python.s08_annotation_decision import (
    propose_annotation_method, evaluate_annotation_proposal,
    execute_celltypist_annotation, execute_manual_annotation,
    report_annotation
)

proposal = propose_annotation_method(adata, tissue_hint='Immune system')
evaluation = evaluate_annotation_proposal(proposal, adata)

if evaluation["verdict"] == "BLOCK":
    raise RuntimeError(f"Annotation blocked: {evaluation['reason']}")
else:
    # Agent presents proposal to user and WAITS for confirmation
    print("📋 Annotation Proposal:")
    print(f"  Recommended method: {proposal['recommendation']['method']}")
    if proposal['recommendation'].get('tissue'):
        print(f"  Tissue: {proposal['recommendation']['tissue']}")
    if evaluation["verdict"] == "CAUTION":
        print(f"⚠️ {evaluation['reason']}")
    # ... WAIT for user confirmation (y/n or method override) ...
    method = proposal["recommendation"]["method"]
    if method == "CellTypist":
        adata = execute_celltypist_annotation(adata, tissue=proposal["recommendation"]["tissue"])
    elif method == "Manual":
        adata = execute_manual_annotation(adata, cluster_annotations)
report = report_annotation(adata)
```

**Script mode (one-shot):**
```r
obj <- run_annotation_step(obj, tissue = 'Immune system')$obj
```
```python
adata = run_annotation_step(adata, tissue='Immune system')["obj"]
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

1. **Data Snapshot**: Key metrics (cell count, gene count, batch info)
2. **Rule Proposal**: What the rule engine proposed and why
3. **Execution Report**: Results with PASS/CAUTION/WARNING status
4. **Cross-Step Context**: References to previous step reports (e.g., QC removal % → doublet rate linkage)
5. **LLM Analysis Task**: A framed question for the agent to answer

Example (QC step):

```markdown
## [LLM Diagnostic Card] Step 2: QC Filtering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Initial cells | 10231 |
| nFeature_RNA median | 3240 |
| MT% median | 8.2% |

### Rule Proposal
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| nFeature_RNA min | 200 | Range 200-7200 captures >95% of cells |
| MT% max | 15.0% | MT% median = 8.2% (moderate). Standard threshold applies. |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **PASS** |
| Cells after filter | 8342 |
| Cells removed | 18.5% |

### Cross-Step Context
- **load**: status=PASS

### LLM Analysis Task
> Analyze this QC profile and assess whether the proposed thresholds are
> appropriate for downstream analysis. Consider:
> 1. Is the MT% distribution consistent with the expected tissue type?
> 2. Is the removal rate (18.5%) reasonable, or does it suggest over/under-filtering?
> 3. Are there any red flags that warrant special attention?
> 4. Should any thresholds be adjusted before proceeding?
```

### Critical Steps

Steps 2 (QC), 5 (Integration), and 8 (Annotation) are **critical steps** where poor decisions have the highest downstream impact. Their diagnostic cards include enhanced LLM analysis tasks. When the Agent uses the decomposed API (`propose_*` → `evaluate_*` → `execute_*`), it should read `llm_report` from the result and incorporate the analysis task into its reasoning before presenting the decision to the user. If using `run_*_step()` (one-shot), the Agent can only inspect the report after execution — CAUTION verdicts will have already executed.

### Saved Reports

**Script Mode**: When `use_llm = TRUE`, all diagnostic cards are saved to `output_dir/llm_reports/`:
- Individual files: `qc_diagnostic.md`, `doublet_diagnostic.md`, etc.
- Combined report: `combined_report.md`

In `mode = "auto"`, reports are saved to files without printing to the console. In `mode = "verbose"`, they are also printed to stdout.

**Agent Mode**: Diagnostic cards are generated only when the `generate_llm_report()` call is present in the Agent's code. They are returned as strings and can be saved manually or presented to the user.

---

## Full R Path (Seurat Ecosystem)

Complete pipeline with zero language switching. All tools from R/Bioconductor.

```r
# === Full Pipeline (R) ===
# All scripts in scripts/r/

source('scripts/r/run_pipeline.R')

result <- run_pipeline(
  data_path = 'filtered_feature_bc_matrix/',
  project = 'PBMC',
  output_dir = 'results',
  mode = 'auto',             # 'auto' = silent full run; 'verbose' = prints proposals
  batch_col = 'sample_id',   # for integration decision
  tissue = 'Immune system'   # for annotation recommendation
)

# Access results
seurat_obj <- result$obj
reports <- result$reports
# reports$qc, reports$doublet, reports$integration, etc.
```

### Resume from intermediate state (R)

```r
# If you have a Seurat object after normalization and want to continue
source('scripts/r/run_pipeline.R')
obj <- readRDS('seurat_normalized.rds')
result <- resume_pipeline(obj, from_step = 5, mode = 'auto')
```

---

## Full Python Path (Scanpy Ecosystem)

Complete pipeline with zero language switching. All tools from Python ecosystem.

```python
# === Full Pipeline (Python) ===
# All scripts in scripts/python/

import sys
sys.path.insert(0, 'scripts/python')
from run_pipeline import run_pipeline

result = run_pipeline(
    data_path='filtered_feature_bc_matrix.h5',
    output_dir='results',
    mode='auto',              # 'auto' = silent full run; 'verbose' = prints proposals
    batch_col='sample_id',
    tissue='Immune system'
)

# Access results
adata = result['obj']
reports = result['reports']
# reports['qc'], reports['doublet'], reports['integration'], etc.
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
| QC | nFeature min | 200 | Lower for low-coverage data; higher for nuclei |
| QC | nFeature max | 99th pct × 1.2 | Higher for heterogeneous tissues |
| QC | percent.mt | data-driven | <5% for nuclei; <30% for low-quality tissue |
| Normalize (R) | SCT vars.regress | percent.mt | Add cell cycle, nCount if needed |
| Normalize (Py) | target_sum | 1e4 | Standard CPM normalization |
| PCA | npcs | 50 | Increase for complex tissues; decrease for simple |
| UMAP | dims | 20-30 | Match chosen PCs from elbow |
| Cluster | resolution | 0.5-0.8 | Lower for broad types; higher for subtypes |
| Markers | min.pct | 0.25 | Lower for rare populations |
| Markers | logfc.threshold | 0.25 | Higher for stricter markers |

---

## Troubleshooting

| Issue | Likely Cause | Solution | Delegate To |
|-------|--------------|----------|-------------|
| All cells filtered | QC too strict | Relax thresholds | preprocessing |
| Doublet rate >15% | Samples aggregated | Run per-sample | doublet-scdblfinder-r |
| Poor UMAP separation | Too few HVGs/PCs | Increase nfeatures, check elbow | clustering |
| Batch-driven clusters | Strong batch effects | Run integration | batch-integration |
| Too many/few clusters | Wrong resolution | Adjust resolution | clustering |
| Unknown cell types | Missing markers | Try SingleR or custom markers | annotation sub-skills |
| Annotation mismatches | Wrong reference | Switch tissue type or reference | annotation sub-skills |
| Memory error | Dataset too large | Use BPCells (R) or `backed` mode (Python) | data-io |

---

## Related Skills

| Skill | Role in Pipeline |
|-------|-----------------|
| [bio-single-cell-data-io](../bio-single-cell-data-io/) | Loading non-standard formats, format conversion, saving, SampleSheet |
| [bio-single-cell-preprocessing](../bio-single-cell-preprocessing/) | Advanced QC, normalization methods, HVG selection |
| [bio-single-cell-doublet-scdblfinder-r](../bio-single-cell-doublet-scdblfinder-r/) | Doublet detection in R (multi-sample, parameter tuning) |
| [bio-single-cell-doublet-scrublet](../bio-single-cell-doublet-scrublet/) | Doublet detection in Python |
| [bio-single-cell-clustering](../bio-single-cell-clustering/) | Advanced clustering, Leiden/Louvain, multi-resolution |
| [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/) | Marker-based annotation with tissue databases |
| [bio-single-cell-annotation-singler-r](../bio-single-cell-annotation-singler-r/) | Reference-based annotation with celldex |
| [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/) | Immune cell annotation with pre-trained models |
| [bio-single-cell-batch-integration](../bio-single-cell-batch-integration/) | Batch correction method selection and execution |
| [bio-single-cell-markers](../bio-single-cell-markers/) | Marker detection methods, visualization, conservation |

### Optional Post-Pipeline Analysis

These steps are NOT part of the standard pipeline but can be run after annotation:

| Analysis | Skill | When to Use |
|----------|-------|-------------|
| Pathway scoring | [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/) | User asks for pathway activity |
| Gene set scoring | [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/) | Quick signature scoring |
| Differential expression | [bio-single-cell-markers](../bio-single-cell-markers/) | Compare conditions |
| Trajectory | [bio-single-cell-trajectory-monocle3-r](../bio-single-cell-trajectory-monocle3-r/) | Pseudotime analysis |
| Cell communication | [bio-single-cell-communication-cellchat-r](../bio-single-cell-communication-cellchat-r/) | Ligand-receptor analysis |
