# pySCENIC Usage Guide

## Overview

pySCENIC (Python Single-Cell Regulatory Network Inference and Clustering) identifies transcription factor regulons from scRNA-seq data using three steps: network inference, regulon prediction, and cellular enrichment.

## When to Use

- Infer TF regulons from scRNA-seq
- Identify cell type specific regulators
- Analyze gene regulatory networks
- Map regulatory states

## Input Data Requirements

### Required Data Format
- **AnnData object** with gene expression matrix (cells × genes)
- **Gene names must be gene symbols** (e.g., `TP53`, `SOX10`), NOT Ensembl IDs
- Minimum recommended: ≥100 cells, ≥5,000 genes

### Preprocessing Steps

```python
import scanpy as sc

# Load your data
adata = sc.read_h5ad("your_data.h5ad")

# 1. Filter cells and genes
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# 2. Convert to gene symbols (if needed)
# If you have Ensembl IDs, convert them first:
# adata.var_names = map_ensembl_to_symbol(adata.var_names)

# 3. Optional: Subsample for very large datasets
if adata.n_obs > 20000:
    sc.pp.subsample(adata, n_obs=20000, random_state=42)

# Note: Normalization is NOT required for SCENIC
# The algorithm uses ranking-based approach which is robust to count depth
```

### Batch Effects
- SCENIC is relatively robust to batch effects due to its ranking-based approach
- If batch correction is needed, use methods that preserve count structure (e.g., Harmony, Scanorama)
- Avoid log-transforming before SCENIC (use raw or normalized counts)

## Quick Start

```python
from pyscenic_analysis import (
    check_database,
    download_databases,
    run_pyscenic_pipeline
)

# Check/download databases
status = check_database("human", "10kb")
if not status['all_ready']:
    download_databases("human", "10kb")

# Run pipeline
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata, organism="human", num_workers=4
)
```

## Database Management

### Automatic Database Handling

```python
from pyscenic_analysis import (
    check_database,
    list_available_databases,
    download_databases
)

# Check all available databases
db_status = list_available_databases()
print(db_status)

# Check specific database
status = check_database(organism="human", db_type="10kb", motif_version="v10")

# Download if needed
if not status['all_ready']:
    paths = download_databases(
        organism="human",
        db_type="10kb",
        motif_version="v10"
    )
```

### Database Types

- **500bp**: Examines 500bp upstream + 100bp downstream of TSS
- **10kb**: Examines 10kb upstream + downstream of TSS

Use **10kb** for initial analysis (more comprehensive), **500bp** for promoter-focused analysis.

## Step-by-Step Pipeline

### 1. Complete Pipeline

```python
from pyscenic_analysis import run_pyscenic_pipeline

adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    motif_version="v10",
    grn_method="grnboost2",  # or "genie3"
    num_workers=4,
    seed=42,
    download_if_missing=True
)
```

### 2. Step-by-Step Execution

```python
from pyscenic_analysis import (
    run_grn_inference,
    run_cistarget,
    run_aucell
)

# Step 1: GRN inference
adjacencies = run_grn_inference(
    adata=adata,
    tf_file="allTFs_hg38.txt",
    method="grnboost2",
    num_workers=4
)

# Step 2: cisTarget
regulons = run_cistarget(
    adjacencies=adjacencies,
    database_path="path/to/database.feather",
    motif_annotations_path="path/to/motifs.tbl",
    adata=adata,  # Required: expression matrix for module creation
    num_workers=4
)

# Step 3: AUCell
auc_matrix = run_aucell(
    adata=adata,
    regulons=regulons,
    num_workers=4
)
```

## Result Analysis

### Add Results to AnnData

```python
from pyscenic_analysis import add_aucell_to_adata

adata = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")
```

### Get Top Regulons per Cell Type

```python
from pyscenic_analysis import get_top_regulons_per_celltype

top_regulons = get_top_regulons_per_celltype(
    adata,
    celltype_col="cell_type",
    top_n=10
)
```

### Export Regulons

```python
from pyscenic_analysis import export_regulons_to_gmt

export_regulons_to_gmt(
    regulons=regulons,
    output_file="regulons.gmt",
    min_genes=5
)
```

## Performance Tips

### Memory Requirements

| Step | Memory (10k cells) | Notes |
|------|-------------------|-------|
| GRN inference | ~4GB | Scales with num genes |
| cisTarget | ~8GB | Fixed, depends on database size |
| AUCell | ~2GB | Scales with num regulons |

### Parallelization

```python
# Use more workers for faster processing
run_pyscenic_pipeline(adata, num_workers=8)

# For cluster computing with dask
run_grn_inference(
    adata,
    client_or_address="scheduler-address:8786"
)
```

### Method Selection

- **GRNBoost2**: Faster, good for large datasets
- **GENIE3**: More accurate, slower

## Recommended Parameter Combinations

### Scenario 1: Large Dataset Screening (>20,000 cells)
For quick initial screening of large datasets:

```python
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",        # Broader regulatory regions
    motif_version="v10",
    grn_method="grnboost2",  # Fast algorithm
    num_workers=8,          # Use more workers if memory allows
    seed=42
)
```

**Rationale**: GRNBoost2 is 2-5x faster than GENIE3. 10kb database captures both promoter and enhancer regions for comprehensive screening.

### Scenario 2: Small Dataset Deep Analysis (<5,000 cells)
For high-quality regulon identification in small datasets:

```python
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="500bp",        # Focus on core promoters
    motif_version="v10",
    grn_method="genie3",    # More accurate
    num_workers=4,
    seed=42
)
```

**Rationale**: GENIE3 provides more accurate edge weights for smaller datasets. 500bp database focuses on direct promoter regulation.

### Scenario 3: Memory-Limited Environment
When working with limited RAM (<16GB):

```python
# Option 1: Reduce workers
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    grn_method="grnboost2",
    num_workers=2,          # Reduce memory usage
    seed=42
)

# Option 2: Run step-by-step with subsampling
# Step 1: GRN inference (memory intensive)
adjacencies = run_grn_inference(
    adata=adata,
    tf_file=tf_path,
    method="grnboost2",
    num_workers=2
)

# Save intermediate results
adjacencies.to_csv("adjacencies.tsv", sep="\t", index=False)

# Step 2 & 3: Continue with remaining steps
```

**Memory Requirements by Step**:

| Step | Memory (10k cells) | Notes |
|------|-------------------|-------|
| GRN inference | ~4GB | Scales with num genes × num TFs |
| cisTarget | ~8GB | Fixed, depends on database size |
| AUCell | ~2GB | Scales with num regulons |

### Scenario 4: Quick Testing/Validation
For pipeline testing with small data subset:

```python
# Subsample for quick testing
sc.pp.subsample(adata, n_obs=1000, random_state=42)

adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    grn_method="grnboost2",
    num_workers=4,
    seed=42
)
```

## Interpreting Results

### AUCell Scores
The AUC matrix contains activity scores (0-1) for each regulon in each cell:

```python
# Add to AnnData
adata = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")

# Visualize on UMAP
sc.pl.umap(adata, color=["SOX10 (100g)", "MITF (85g)"])
```

**Interpretation guidelines**:
- **0.0 - 0.3**: Regulon is inactive in this cell
- **0.3 - 0.5**: Low activity
- **0.5 - 0.8**: Moderate activity (regulon likely functional)
- **0.8 - 1.0**: High activity (regulon is a driver)

### Identifying Cell-Type Specific Regulons

```python
# Method 1: Mean AUC per cell type
top_regulons = get_top_regulons_per_celltype(
    adata,
    celltype_col="cell_type",
    auc_key="X_aucell",
    top_n=10
)

# Method 2: Differential activity analysis
# Compare regulon activity between cell types
from scipy import stats

def find_specific_regulons(auc_matrix, cell_types, target_type):
    '''Find regulons specific to target cell type'''
    specific_regulons = []
    for regulon in auc_matrix.columns:
        target_values = auc_matrix.loc[cell_types == target_type, regulon]
        other_values = auc_matrix.loc[cell_types != target_type, regulon]
        
        # t-test for differential activity
        t_stat, pval = stats.ttest_ind(target_values, other_values)
        
        # Check if higher in target
        if target_values.mean() > other_values.mean() * 2 and pval < 0.05:
            specific_regulons.append({
                'regulon': regulon,
                'mean_auc_target': target_values.mean(),
                'mean_auc_other': other_values.mean(),
                'fold_change': target_values.mean() / (other_values.mean() + 0.01),
                'pvalue': pval
            })
    
    return pd.DataFrame(specific_regulons).sort_values('fold_change', ascending=False)
```

### Regulon Quality Assessment

High-quality regulons typically have:
1. **10-200 target genes** (shown in regulon name, e.g., `"SOX10 (50g)"`)
2. **Cell-type specific activity pattern** (not ubiquitously active)
3. **Consistent with known biology** (TF expressed in same cells as regulon active)

```python
# Check regulon sizes
for r in regulons[:10]:
    print(f"{r.name}: {len(r.gene2weight)} targets")

# Expected output:
# SOX10 (45g): 45 targets
# MITF (32g): 32 targets
```

## AI Agent Test Cases

### Basic Usage
> "Run pySCENIC pipeline on my scRNA-seq data"

> "Infer TF regulons using pySCENIC with GRNBoost2"

### Database Management
> "Check if pySCENIC databases are downloaded"

> "Download human 10kb cisTarget database"

### Analysis
> "Identify cell type specific regulons from pySCENIC"

> "Map regulatory states using pySCENIC AUCell"

### Export
> "Export pySCENIC regulons to GMT format"

> "Get top 10 regulons for each cell type"

---

## Advanced: Database Migration (Optional)

If you have existing databases in your home directory (`~/.pyscenic/`) and want to migrate them to the skill's `assets/` folder for project isolation:

```python
from pyscenic_analysis import migrate_databases_to_skill_assets

# Preview what would be migrated
result = migrate_databases_to_skill_assets(dry_run=True)
print(f"Files to migrate: {len(result['to_migrate'])}")
print(f"Already present: {len(result['already_present'])}")

# Execute migration
result = migrate_databases_to_skill_assets(dry_run=False)
```

**Note**: This is a one-time operation. After migration, subsequent runs will use the skill assets directory automatically.

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
2. pySCENIC documentation: https://github.com/aertslab/pySCENIC
3. cisTarget databases: https://resources.aertslab.org/cistarget/
