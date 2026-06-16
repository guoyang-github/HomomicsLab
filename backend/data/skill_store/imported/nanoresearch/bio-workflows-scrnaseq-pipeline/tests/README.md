# Test Cases — bio-workflows-scrnaseq-pipeline

Test data: PDAC scRNA-seq from DemoShot dataset

| File | Cells | Genes | Source | Tissues |
|------|-------|-------|--------|---------|
| PA08_sc.h5ad | 25,524 | 29,057 | PDAC patient PA08 | Adjacent_normal, PBMC, Tumor |
| PA12_sc.h5ad | 14,990 | 29,057 | PDAC patient PA12 | PBMC, Tumor |

**Data characteristics** (important for test design):
- Already contains `layers['counts']` and `layers['normalized']`
- QC metrics pre-computed: `n_genes`, `n_counts`, `mito_percent`
- HVG pre-computed in `var['highly_variable']`
- Ground-truth cell types in `obs['all_celltype']`
- Patient ID in `obs['patients']` (PA08 / PA12)

**Note**: Because the input data is pre-processed, some pipeline steps behave differently than on raw 10X output:
- Step 2 (QC): `mito_percent` already exists; `propose_qc_thresholds()` will use it directly after column rename
- Step 4 (Normalization): Will re-run log1p normalization on top of existing data
- Step 1 (Load): h5ad format bypasses 10X MTX/H5 loaders

---

## Test Case Overview

| # | Test | Input | Path | Mode | Focus |
|---|------|-------|------|------|-------|
| 1 | Single-sample full pipeline | PA08_sc.h5ad | Python | auto | End-to-end correctness |
| 2 | Multi-sample batch integration | PA08+PA12 merged | Python | auto | Batch detection + integration |
| 3 | Interactive decision points | PA08_sc.h5ad | Python | interactive | Proposal/report output |
| 4 | LLM enhancement toggle | PA08_sc.h5ad | Python | auto | Diagnostic card generation |
| 5 | Resume from mid-pipeline | PA08 normalized | Python | auto | State continuity |
| 6 | R path from RDS | Seurat RDS | R | auto | Full R ecosystem path |

---

## Running Tests

### Prerequisites

```bash
# Python
pip install scanpy anndata pandas celltypist harmonypy

# R
install.packages(c('Seurat', 'ggplot2', 'dplyr', 'harmony'))
BiocManager::install(c('scDblFinder', 'SingleCellExperiment'))
```

### Data preparation (one-time)

```bash
cd tests
python prepare_test_data.py
```

This creates:
- `PA08_sc_renamed.h5ad` — PA08 with `pct_counts_mt` column for QC compatibility
- `PA12_sc_renamed.h5ad` — PA12 with `pct_counts_mt` column
- `PA08_PA12_merged.h5ad` — Concatenated multi-sample object

### Run individual tests

```bash
# Test 1: Single-sample
python test_single_sample.py

# Test 2: Multi-sample
python test_multi_sample.py

# Test 3: Interactive mode (shows proposals, does not block)
python test_decision_points.py

# Test 4: LLM on/off
python test_llm_toggle.py

# Test 5: Resume
python test_resume.py

# Test 6: R path
Rscript test_r_path.R
```

---

## Expected Runtime

| Dataset | Cells | Approx. Runtime | Memory |
|---------|-------|-----------------|--------|
| PA08 | 25,524 | 8-12 min | 4-6 GB |
| PA12 | 14,990 | 5-8 min | 3-4 GB |
| Merged | 40,514 | 15-25 min | 8-12 GB |
