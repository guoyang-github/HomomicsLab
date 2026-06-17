# BRIE2 Single-Cell Splicing Analysis - Usage Guide

## Overview

BRIE2 (Bayesian Regression for Isoform Estimate) is a scalable Bayesian method for:
- **Differential Alternative Splicing (DAS)**: Quantifying isoform proportions and detecting differential splicing
- **Differential Momentum Genes (DMG)**: Analyzing unspliced/spliced RNA ratios for RNA velocity

## Quick Start

### 1. Installation

```bash
# Install BRIE2
pip install brie

# Verify installation
python -c "import brie; print(brie.__version__)"
```

### 2. Basic Workflow

#### Step 1: Count Reads (brie-count)

**For Smart-seq2 data:**
```bash
# Create sam list file (tab-delimited)
# Format: bam_path\tcell_id
cell1.bam	cell1
cell2.bam	cell2
...

# Run counting
brie-count -a splicing_events.gff3 -S sam_list.tsv -o counts/ -p 4
```

**For 10x Genomics data:**
```bash
brie-count -a splicing_events.gff3 \
           -S aligned.bam \
           -b barcodes.tsv \
           -o counts/ \
           -p 4 \
           --CBtag CB \
           --UMItag UR
```

#### Step 2: Quantify Splicing (brie-quant)

```bash
# Basic quantification
brie-quant -i counts/brie_count.h5ad -o results/brie_quant.h5ad -p 4

# With cell features for differential analysis
brie-quant -i counts/brie_count.h5ad \
           -c cell_features.tsv \
           -o results/brie_quant.h5ad \
           --LRTindex All \
           -p 4
```

## Python API Usage

### Basic Analysis

```python
import brie
import scanpy as sc
from brie.models import fitBRIE

# Load count data
adata = brie.read_h5ad('counts/brie_count.h5ad')

# Filter low-quality genes
adata = brie.pp.filter_genes(
    adata,
    min_counts=50,
    min_cells_uniq=30,
    min_MIF_uniq=0.001
)

# Run quantification
model = fitBRIE(adata, min_iter=5000, max_iter=20000)

# Save results
adata.write_h5ad('results/brie_quant.h5ad')

# Export statistics table
df = brie.io.dump_results(adata)
df.to_csv('results/brie_stats.tsv', sep='\t')
```

### Differential Splicing Analysis

```python
import pandas as pd

# Load cell features (e.g., cell types, conditions)
cell_features = pd.read_csv('cell_types.tsv', sep='\t', index_col=0)

# One-hot encode categorical features
Xc = pd.get_dummies(cell_features['cell_type']).values

# Run with LRT
model = fitBRIE(
    adata,
    Xc=Xc,
    LRT_index=[0, 1, 2],  # Test specific features
    intercept_mode='gene',
    min_iter=5000,
    max_iter=20000
)

# Get significant events
df = brie.io.dump_results(adata)
significant = df[df['qval'] < 0.05].sort_values('qval')
```

### Trajectory Analysis

```python
# Use pseudotime as continuous covariate
adata.obs['pseudotime'] = pseudotime_values

model = fitBRIE(
    adata,
    Xc=adata.obs[['pseudotime']].values,
    LRT_index=[0],
    min_iter=5000,
    max_iter=20000
)
```

## Input File Formats

### GFF3 Format for Splicing Events

```
chr1	BRIE2	exon	1000	1100	.	+	.	gene_id "gene1"; transcript_id "isoform1";
chr1	BRIE2	exon	1200	1300	.	+	.	gene_id "gene1"; transcript_id "isoform1";
chr1	BRIE2	exon	1000	1100	.	+	.	gene_id "gene1"; transcript_id "isoform2";
chr1	BRIE2	exon	1400	1500	.	+	.	gene_id "gene1"; transcript_id "isoform2";
```

### Cell Features File

Tab-delimited with header:
```
cell_id	cell_type	condition
 cell1	Neuron	Control
 cell2	Glial	Control
 cell3	Neuron	Treated
```

### SAM/BAM List (Smart-seq2)

Tab-delimited:
```
/path/to/cell1.bam	cell1
/path/to/cell2.bam	cell2
```

## Output Files

### brie_count.h5ad

AnnData with layers:
- `isoform1`: Counts supporting inclusion/isoform1
- `isoform2`: Counts supporting exclusion/isoform2
- `ambiguous`: Ambiguous reads

### brie_quant.h5ad

AnnData with:
- `X`: PSI values (cells × events)
- `varm['psi_mean']`: Mean PSI per event
- `varm['psi_std']`: PSI standard deviation
- `uns['brie_version']`: BRIE version

### brie_ident.tsv

Statistics table with columns:
- `ELBO_gain`: Model improvement
- `pval`: P-value
- `qval`: FDR-corrected q-value

## Visualization

### PSI Distribution

```python
import matplotlib.pyplot as plt
import seaborn as sns

psi = adata[:, 'event_001'].X.flatten()
sns.histplot(psi, bins=50, kde=True)
plt.xlabel('PSI')
plt.ylabel('Cells')
plt.savefig('psi_distribution.pdf')
```

### Volcano Plot

```python
df = brie.io.dump_results(adata)
plt.scatter(df['ELBO_gain'], -np.log10(df['pval']))
plt.xlabel('ELBO Gain')
plt.ylabel('-log10(p-value)')
plt.savefig('volcano.pdf')
```

## Common Issues

### Low Coverage Warning
- **Solution**: Lower `min_counts`, `min_cells_uniq` thresholds

### Convergence Issues
- **Solution**: Increase `max_iter` to 50000

### Memory Issues
- **Solution**: Reduce `batch_size` to 100000

### No Significant Events
- Check cell numbers per group (need >30 cells)
- Check if splicing events have enough coverage
- Increase effect size by biological separation

## Best Practices

1. **Quality Control**: Filter low-coverage genes before analysis
2. **Cell Numbers**: Ensure sufficient cells per group (>30)
3. **Batch Effects**: Include batch as covariate if needed
4. **Multiple Testing**: Use q-values for significance
5. **Validation**: Visualize top hits manually

## References

1. Huang & Sanguinetti (2021). BRIE2: computational identification of splicing phenotypes. *Genome Biology*, 22:251.
2. Documentation: https://brie.readthedocs.io
3. GitHub: https://github.com/huangyh09/brie
