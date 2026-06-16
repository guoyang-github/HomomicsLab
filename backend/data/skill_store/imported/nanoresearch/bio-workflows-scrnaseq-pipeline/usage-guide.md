# Single-Cell RNA-seq Pipeline - Usage Guide

## Overview

This is a **workflow orchestrator** that defines the standard single-cell RNA-seq analysis pipeline from raw counts to annotated cell types. It provides **Propose → Execute → Report** mode for every critical step and supports two complete single-language paths with zero cross-language switching.

**Languages:** R (Seurat ecosystem) or Python (Scanpy ecosystem)
**Workflow:** true
**Type:** Orchestrator (delegates implementation to sub-skills)

## Workflow Philosophy: Propose → Execute → Report

Every critical step follows this three-phase pattern:

1. **Propose**: Analyze current data, recommend parameters with data-driven justification
2. **Execute**: Run the recommended approach (or user-modified parameters)
3. **Report**: Summarize results, flag issues, suggest next steps

```
User: "Analyze my single-cell data"
  ↓
Agent (Propose): "Detected 10,231 cells. QC proposal: nFeature 200-7200, MT% <15%.
                  Justification: MT% median=8.2%, standard range."
  ↓
User: "Looks good, proceed"  [or: "Relax MT% to 20%"]
  ↓
Agent (Execute): Runs QC filtering
  ↓
Agent (Report): "QC complete: 8,432 cells retained (17.6% removed). Status: PASS.
                  Next: Doublet Detection."
```

### Modes

| Mode | Behavior | Use When |
|------|----------|----------|
| `interactive` | Pause at each decision point, show proposal, wait for user confirmation | Default; user wants control |
| `auto` | Run full pipeline without pausing, accept all proposals | User trusts defaults; batch processing |

### LLM Enhancement Mode

By default, every step generates a structured **diagnostic card** (markdown) that the LLM agent reads to provide deep, contextual advice. This is a two-layer architecture:

- **Rule layer** (deterministic): Proposes parameters, executes code, reports PASS/CAUTION/WARNING
- **LLM layer** (advisory): Interprets diagnostic cards and provides natural-language analysis

**Enable/disable LLM enhancement:**

```r
# R
c_result <- run_pipeline(..., use_llm = TRUE)   # default
result <- run_pipeline(..., use_llm = FALSE)  # disable
```

```python
# Python
result = run_pipeline(..., use_llm=True)   # default
result = run_pipeline(..., use_llm=False)  # disable
```

**What the agent sees in interactive mode:**

```
Agent: QC Proposal for your data:
  - nFeature_RNA: 200 - 7,200
  - percent.mt: <15%
  Justification: MT% median = 8.2% (moderate). Standard threshold applies.
  Estimated removal: ~18.5% cells

[LLM Diagnostic Card]
## Step 2: QC Filtering
Data Snapshot: 10,231 cells, MT% median 8.2%, 95th pct 14.1%
...
LLM Analysis Task: Is the removal rate reasonable? Any red flags?

Agent: [Reads diagnostic card, provides analysis]
```

**Saved reports:** When `use_llm = TRUE`, all diagnostic cards are saved to `output_dir/llm_reports/` (individual files + combined report).

## When to Use This Skill

Use this skill when the user says:
- "Analyze my single-cell data from start to finish"
- "Run the scRNA-seq pipeline"
- "Process my 10X data"
- "Complete single-cell workflow"
- "From raw counts to cell types"

## Language Path Selection

**Critical: Pick ONE path and stay in that language throughout.**

| Path | Tools | Best For |
|------|-------|----------|
| **Full R** | Seurat + scDblFinder + Harmony + ScType/SingleR | General analysis, well-established ecosystem |
| **Full Python** | Scanpy + Scrublet + harmony-py + CellTypist | Large datasets, Python ML integration |

### R Path dependencies
```r
install.packages(c('Seurat', 'ggplot2', 'dplyr', 'harmony'))
BiocManager::install(c('scDblFinder', 'SingleCellExperiment'))
```

### Python Path dependencies
```bash
pip install scanpy scrublet anndata celltypist harmonypy
```

## Pipeline Steps (9 Steps)

| Step | Action | Sub-Skill | State In → State Out | Decision Point |
|------|--------|-----------|---------------------|----------------|
| 1 | Load data | data-io | → `[Raw]` | D1: Format detection |
| 2 | QC + filter | preprocessing | `[Raw]` → `[Filtered]` | **D2: Thresholds** |
| 3 | Remove doublets | doublet-scdblfinder-r / scrublet | `[Filtered]` → `[Clean]` | — |
| 4 | Normalize + HVG | preprocessing | `[Clean]` → `[Normalized]`+`[HVG]` | — |
| 5 | Batch integration (if needed) | batch-integration | `[Normalized]` → `[Integrated]` | **D3: Integration** |
| 6 | PCA + Cluster + UMAP | clustering | → `[Scaled]`+`[PCA]`+`[UMAP]`+`[Clustered]` | **D4: Resolution** |
| 7 | Find markers | markers | → markers table | — |
| 8 | Annotate cells | annotation-* | → `[Annotated]` | **D5: Method** |

## Example Prompts

### Full pipeline with interaction

> "Run the complete scRNA-seq pipeline on my 10X data"

> "Analyze my PBMC data from raw counts to cell types using the R path"

### Starting mid-pipeline

> "I already have a Seurat object after QC, continue with clustering and annotation"

> "My data is normalized, just do clustering, find markers, and annotate"

### Specific steps with decisions

> "Check if my multi-sample data needs batch integration before clustering"

> "Find clusters at multiple resolutions and tell me which looks best"

> "Annotate my clusters — I have pancreas tissue"

### Auto mode (no interaction)

> "Run the full pipeline in auto mode on my 10X data"

> "Process my data start to finish, accept all defaults"

### Multi-sample with SampleSheet

> "I have 4 samples defined in samplesheet.csv, run the full pipeline"

> "Load my samples from the SampleSheet, integrate if needed, then cluster"

## Decision Point Interactions

### D2: QC Thresholds

The agent will analyze your data and propose thresholds. Example interaction:

```
Agent: QC Proposal for your data:
  - nFeature_RNA: 200 - 7,200
  - nCount_RNA: >500
  - percent.mt: <15%
  Justification: MT% median = 8.2% (moderate). Standard threshold applies.
  Estimated removal: ~18.5% cells

User: That looks good / Make MT% 20% / Use stricter nFeature min=500
Agent: [Executes with confirmed/modified parameters]
Agent: QC Report: PASS (10,231 → 8,342 cells, 18.5% removed)
```

### D3: Batch Integration (Critical)

The agent will diagnose batch effects BEFORE recommending integration:

```
Agent: Integration Decision:
  - Batches detected: 4 (Batch1, Batch2, Batch3, Batch4)
  - Batch mixing score: 0.72 (strong batch effect)
  - Recommendation: INTEGRATE with Harmony
  - Justification: Strong batch effect detected. Integration strongly recommended.

User: Use Harmony / Skip integration / Try RPCA instead
Agent: [Executes selected approach]
Agent: Integration Report: PASS (method=Harmony, 4 batches corrected)
```

### D4: Clustering Resolution

```
Agent: Clustering Proposal:
  - PCs: 50 computed, ~28 used (elbow-based)
  - Resolutions: 0.3, 0.5, 0.8, 1.2
  - Default: 0.8 (medium dataset)
  Justification: 8,342 cells — standard resolution range.

Agent: [Computes all resolutions]
Agent: Clustering Report: PASS (12 clusters at res=0.8, 8 at res=0.5, 18 at res=1.2)
  Recommendation: res=0.8 looks reasonable. res=1.2 may reveal subtypes.
```

### D5: Annotation Method

```
Agent: Annotation Proposal:
  - Tissue: Immune system (provided)
  - Recommended: ScType (R) / CellTypist (Python)
  - Justification: Tissue type known. Tissue-specific marker database is most accurate.

User: Use ScType / Try SingleR instead / I'll annotate manually
Agent: [Executes selected method]
Agent: Annotation Report: PASS (method=ScType, 8 cell types, 94.2% assigned)
```

## Input Requirements

| Input | Format | Notes |
|-------|--------|-------|
| 10X output | `filtered_feature_bc_matrix/` | Standard Cell Ranger output |
| 10X H5 | `.h5` | Single file |
| SampleSheet | `.csv` | Multi-sample declarative input (see bio-single-cell-data-io) |
| Seurat RDS | `.rds` | Can start mid-pipeline (resume from Step 5+) |
| AnnData h5ad | `.h5ad` | Can start mid-pipeline (resume from Step 5+) |

For non-standard formats (GEO MTX + metadata, multiple samples to merge), see [bio-single-cell-data-io](../bio-single-cell-data-io/).

## Expected Outputs

| File | Description |
|------|-------------|
| `seurat_annotated.rds` / `adata_annotated.h5ad` | Full annotated object |
| `all_markers.csv` | All markers per cluster |
| `top10_markers.csv` | Top 10 markers per cluster |
| `plots/umap_annotated.pdf` | UMAP with cell type labels |
| `plots/qc_violin.pdf` | QC plots (R path) |
| `plots/elbow.pdf` | PCA elbow plot |
| `plots/umap_resolutions.pdf` | Multi-resolution UMAP comparison |

## Tips

- **Cell numbers**: Expect 1,000-20,000 cells from typical 10X run
- **Genes per cell**: 200-5,000 is typical; very high may be doublets
- **Mitochondrial**: >20% suggests dying cells; <5% for nuclei
- **Resolution**: Start at 0.5-0.8, adjust based on cluster quality
- **Annotation**: Always cross-check with known canonical markers
- **Multi-sample**: Always check UMAP for batch-driven clusters before integration
- **Gene Set Scoring**: NOT part of standard pipeline. Use enrichment sub-skills after annotation if needed.

## Seurat vs Scanpy

| Feature | Seurat (R) | Scanpy (Python) |
|---------|------------|-----------------|
| Language | R | Python |
| Speed | Fast | Faster for large data |
| Memory | Moderate | Lower |
| Ecosystem | Bioconductor | Python ML stack |
| Best for | General analysis | Large datasets, deep learning integration |
| Doublet | scDblFinder | Scrublet |
| Integration | Harmony, CCA, RPCA | Harmony, Scanorama, scVI |
| Annotation | ScType, SingleR | CellTypist |

## When to Switch to Sub-Skills

| User Request | Switch To |
|-------------|-----------|
| "Compare doublet methods" | [bio-single-cell-doublet-scrublet](../bio-single-cell-doublet-scrublet/), [bio-single-cell-doublet-doubletfinder-r](../bio-single-cell-doublet-doubletfinder-r/) |
| "Which batch correction?" | [bio-single-cell-batch-integration](../bio-single-cell-batch-integration/) |
| "Better cell annotation" | [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/), [bio-single-cell-annotation-singler-r](../bio-single-cell-annotation-singler-r/) |
| "Score pathways" | [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/), [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/) |
| "Non-standard data format" | [bio-single-cell-data-io](../bio-single-cell-data-io/) |
