---
name: bio-single-cell-splicing-brie2
description: |
  BRIE2 (Bayesian Regression for Isoform Estimate) is a scalable Bayesian method to accurately 
  identify splicing phenotypes in single-cell RNA-seq experiments. It quantifies isoform 
  proportions and their uncertainty, supporting both differential alternative splicing (DAS) 
  and differential momentum genes (DMG) analysis.
tool_type: python
primary_tool: brie
languages: [python]
keywords: ["single-cell", "splicing", "alternative-splicing", "isoform", "bayesian", "psi", "brie2", "rnaseq"]
---

## Version Compatibility

- **Python**: >=3.8
- **brie**: >=2.2.0
- **scanpy**: >=1.9.0
- **anndata**: >=0.8.0
- **numpy**: >=1.20.0
- **pysam**: >=0.19.0
- **tensorflow**: >=2.8.0 (for quantification)

## Installation

```bash
pip install brie
```

Or install from source:
```bash
pip install -U git+https://github.com/huangyh09/brie
```

Additional dependencies for counting:
```bash
pip install pysam
```

## Data Requirements

### Input for Counting (brie-count)
- **GFF file**: Gene annotation with splicing events (SE format for exon skipping)
- **BAM/SAM files**: Aligned reads (Smart-seq2: one file per cell; 10x: single file with barcodes)
- **Barcode file** (for droplet data): Cell barcodes

### Input for Quantification (brie-quant)
- **h5ad file**: AnnData object with count matrices from brie-count
- **Cell features** (optional): Cell metadata for differential analysis
- **Gene features** (optional): Gene covariates

### Required AnnData Layers
- `isoform1`: Counts supporting inclusion/isoform1
- `isoform2`: Counts supporting exclusion/isoform2  
- `ambiguous`: Ambiguous counts (optional)

## Core Analysis Workflow

### 1. Count Reads (brie-count)

**Purpose:** Generate cell-by-event count matrices from aligned reads.

**Two modes:**
- **Smart-seq2**: Individual BAM files per cell
- **Droplet (10x)**: Single BAM with cell barcodes

**Smart-seq2 Example:**
```python
import brie

# Create sam list file: two columns [bam_path, cell_id]
# cell_001.bam    cell_001
# cell_002.bam    cell_002

# Run counting
brie.count.smartseq_count(
    gff_file='splicing_events.gff3',
    samList_file='sam_list.tsv',
    out_dir='brie_count_output',
    nproc=4,
    event_type='SE',  # Skipping Exon
    verbose=True
)
```

**Droplet (10x) Example:**
```python
import brie

# Run counting for 10x data
brie.count.droplet_count(
    gff_file='splicing_events.gff3',
    sam_file='possorted_genome_bam.bam',
    barcode_file='barcodes.tsv',
    out_dir='brie_count_output',
    nproc=4,
    event_type='SE',
    CB_tag='CB',      # Cell barcode tag in BAM
    UMI_tag='UR',     # UMI tag in BAM
    verbose=True
)
```

**Output:**
- `brie_count.h5ad`: AnnData with layers (isoform1, isoform2, ambiguous)
- `read_count.mtx`: Count matrix
- `gene_note.tsv`: Gene information
- `cell_note.tsv`: Cell information

### 2. Filter and Preprocess

**Purpose:** Filter low-quality cells and genes.

```python
import brie
import scanpy as sc

# Load count data
adata = brie.read_h5ad('brie_count_output/brie_count.h5ad')

# Filter genes
adata = brie.pp.filter_genes(
    adata,
    min_counts=50,           # Minimum total counts per gene
    min_counts_uniq=10,      # Minimum unique counts
    min_cells_uniq=30,       # Minimum cells with unique counts
    min_MIF_uniq=0.001,      # Minimum minor isoform frequency
    uniq_layers=['isoform1', 'isoform2'],
    copy=True
)

print(adata)
```

### 3. Quantify Splicing (brie-quant)

**Purpose:** Estimate PSI values and detect differential splicing.

**Basic Quantification:**
```python
from brie.models import fitBRIE

# Run BRIE quantification
model = fitBRIE(
    adata,
    min_iter=5000,
    max_iter=20000,
    batch_size=500000,
    pseudo_count=0.01
)

# Save results
adata.write_h5ad('brie_quant.h5ad')

# Export results table
df = brie.io.dump_results(adata)
df.to_csv('brie_ident.tsv', sep='\t')
```

**With Cell Features (Differential Analysis):**
```python
import pandas as pd
import numpy as np

# Load cell features
# Format: cell_id, feature1, feature2, ...
cell_features = pd.read_csv('cell_features.tsv', sep='\t', index_col=0)

# Match with adata
common_cells = adata.obs.index.intersection(cell_features.index)
adata = adata[common_cells]
Xc = cell_features.loc[common_cells].values

# Run with cell features
model = fitBRIE(
    adata,
    Xc=Xc,                    # Cell features
    LRT_index=[0, 1],         # Features to test (0-based indices)
    intercept_mode='gene',    # Gene-specific intercept
    min_iter=5000,
    max_iter=20000
)
```

### 4. Access Results

**PSI Values (Percent Spliced In):**
```python
# Cell-by-event PSI matrix
psi_matrix = adata.layers['psi']  # or adata.X

# With confidence intervals
psi_mean = adata.varm['psi_mean']    # Mean PSI per gene
psi_std = adata.varm['psi_std']      # Std deviation

# Get PSI for specific event
event_id = 'SE_event_001'
psi_values = adata[:, event_id].X.flatten()
```

**Differential Splicing Results:**
```python
# Load results table
df = brie.io.dump_results(adata)

# Key columns:
# - ELBO_gain: Evidence Lower Bound improvement
# - pval: P-value for differential splicing
# - qval: FDR-adjusted q-value

# Significant events
significant = df[df['qval'] < 0.05]
print(f"Found {len(significant)} significant DAS events")

# Sort by significance
top_events = df.sort_values('qval').head(10)
```

### 5. Visualization

**PSI Distribution:**
```python
import matplotlib.pyplot as plt
import seaborn as sns

# PSI distribution across cells
event_of_interest = 'SE_event_001'
psi = adata[:, event_of_interest].X.flatten()

fig, ax = plt.subplots(figsize=(8, 4))
sns.histplot(psi, bins=50, kde=True, ax=ax)
ax.set_xlabel('PSI (Percent Spliced In)')
ax.set_ylabel('Number of Cells')
ax.set_title(f'PSI Distribution: {event_of_interest}')
plt.savefig('psi_distribution.pdf')
```

**PSI by Cell Group:**
```python
# Add cell type annotations
adata.obs['cell_type'] = pd.Categorical(cell_types)

# Plot PSI by cell type
fig, ax = plt.subplots(figsize=(8, 6))
sns.boxplot(data=adata.obs, x='cell_type', y='psi_event_001', ax=ax)
ax.set_ylabel('PSI')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('psi_by_celltype.pdf')
```

**Volcano Plot:**
```python
# Differential splicing volcano plot
df = brie.io.dump_results(adata)

fig, ax = plt.subplots(figsize=(10, 8))
scatter = ax.scatter(
    df['ELBO_gain'],
    -np.log10(df['pval']),
    c=df['qval'] < 0.05,
    cmap='coolwarm',
    alpha=0.6
)
ax.set_xlabel('ELBO Gain')
ax.set_ylabel('-log10(p-value)')
ax.axhline(-np.log10(0.05), color='red', linestyle='--', label='p=0.05')
ax.legend()
plt.savefig('volcano_plot.pdf')
```

## Key Parameters

### Counting Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `event_type` | 'SE' | Splicing event type (SE=skipping exon) |
| `edge_hang` | 10 | Bases hanging over exon edge |
| `junc_hang` | 2 | Bases hanging over junction |
| `nproc` | 1 | Number of parallel processes |

### Quantification Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_counts` | 50 | Min total counts for gene filtering |
| `min_counts_uniq` | 10 | Min unique counts per gene |
| `min_cells_uniq` | 30 | Min cells with unique counts |
| `min_MIF_uniq` | 0.001 | Min minor isoform frequency |
| `min_iter` | 5000 | Min VI iterations |
| `max_iter` | 20000 | Max VI iterations |
| `MC_size` | 1 | Monte Carlo sample size |
| `batch_size` | 500000 | Elements per batch |
| `pseudo_count` | 0.01 | Pseudo count for stability |

### Differential Testing Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LRT_index` | [] | Feature indices to test (None=all) |
| `intercept_mode` | 'gene' | Intercept type: gene, cell, or None |
| `base_mode` | 'full' | Base model: full, null |

## Output Specifications

### Core Outputs

| Output | Type | Description |
|--------|------|-------------|
| `psi` | ndarray | PSI values (cells × events) |
| `psi_mean` | ndarray | Mean PSI per event |
| `psi_std` | ndarray | PSI standard deviation |
| `ELBO_gain` | float | Model improvement metric |
| `pval` | float | P-value for differential splicing |
| `qval` | float | FDR-corrected q-value |

### AnnData Structure

```
AnnData object with n_obs × n_vars = 5000 × 2000
    obs: 'cell_id', 'cell_type', ...
    var: 'GeneID', 'GeneName', ...
    layers:
        'isoform1': inclusion counts
        'isoform2': exclusion counts
        'ambiguous': ambiguous counts
        'psi': PSI values
    varm:
        'psi_mean': mean PSI per gene
        'psi_std': std PSI per gene
    uns:
        'brie_version': BRIE version
        'Xc_ids': cell feature names
```

## Common Analysis Patterns

### Pattern 1: Basic Splicing Quantification
```python
# 1. Count
brie.count.droplet_count(gff, bam, barcodes, out_dir='counts')

# 2. Load and filter
adata = brie.read_h5ad('counts/brie_count.h5ad')
adata = brie.pp.filter_genes(adata, min_counts=50)

# 3. Quantify
model = fitBRIE(adata)

# 4. Save
adata.write_h5ad('results.h5ad')
```

### Pattern 2: Differential Splicing by Cell Type
```python
# Prepare cell features (one-hot encoded cell types)
cell_types = pd.get_dummies(adata.obs['cell_type'])

# Run with LRT
model = fitBRIE(adata, Xc=cell_types.values, LRT_index=[0, 1, 2])

# Get results
df = brie.io.dump_results(adata)
significant = df[df['qval'] < 0.05]
```

### Pattern 3: Splicing Trajectory Analysis
```python
# Use pseudotime as continuous covariate
adata.obs['pseudotime'] = pseudotime_values

# Run with pseudotime
model = fitBRIE(adata, Xc=adata.obs[['pseudotime']].values, LRT_index=[0])

# Identify dynamic splicing events
df = brie.io.dump_results(adata)
dynamic_events = df[df['qval'] < 0.05].sort_values('qval')
```

### Pattern 4: RNA Velocity Integration (DMG)
```python
# For momentum genes (spliced/unspliced)
# Layers: 'unspliced', 'spliced'

model = fitBRIE(adata, layer_keys=['unspliced', 'spliced'])
df = brie.io.dump_results(adata)
```

## Expected Runtime

| Dataset Size | Counting | Quantification |
|--------------|----------|----------------|
| 1K cells × 1K events | 5-10 min | 10-20 min |
| 5K cells × 2K events | 20-30 min | 1-2 hours |
| 10K cells × 3K events | 1-2 hours | 3-5 hours |

*Runtime depends on CPU cores and convergence*

## Error Handling

### Low count warning
```python
# Increase filtering thresholds
adata = brie.pp.filter_genes(adata, min_counts=100, min_cells_uniq=50)
```

### Convergence issues
```python
# Increase iterations
model = fitBRIE(adata, min_iter=10000, max_iter=50000)
```

### Memory issues
```python
# Reduce batch size
model = fitBRIE(adata, batch_size=100000)
```

## References

1. Huang & Sanguinetti (2021). BRIE2: computational identification of splicing phenotypes from single-cell transcriptomic experiments. **Genome Biology**, 22(1):251.
2. Huang & Sanguinetti (2017). BRIE: transcriptome-wide splicing quantification in single cells. **Genome Biology**, 18(1):123.
3. Documentation: https://brie.readthedocs.io
4. GitHub: https://github.com/huangyh09/brie
5. Tutorials: https://github.com/huangyh09/brie-tutorials

## Related Skills

- [bio-single-cell-trajectory-scvelo](../bio-single-cell-trajectory-scvelo/SKILL.md) - RNA velocity analysis
- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) - Cell type annotation
