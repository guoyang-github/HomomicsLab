# Cell2location Usage Guide

## Overview

Cell2location is a principled Bayesian model that maps fine-grained cell types to spatial locations by deconvolving cell type compositions from spatial transcriptomics data using a reference single-cell RNA-seq atlas.

## Key Features

- **Bayesian Framework**: Accounts for technical variation and provides uncertainty quantification
- **Statistical Rigor**: Borrows strength across locations for improved sensitivity
- **Reference-Based**: Uses scRNA-seq signatures to guide spatial mapping
- **Uncertainty Quantification**: Provides 5%, 50%, 95% quantiles for cell abundance

## When to Use

- Map cell types to spatial coordinates with high resolution
- Estimate cell type abundance per spot with uncertainty
- Identify tissue niches/microenvironments
- Compare cell type distributions across conditions
- Have a high-quality annotated scRNA-seq reference

## Quick Start

### Installation

```bash
# Create conda environment
conda create -y -n cell2loc_env python=3.10
conda activate cell2loc_env

# Install cell2location
pip install cell2location[tutorials]

# Add jupyter kernel
python -m ipykernel install --user --name=cell2loc_env --display-name='Environment (cell2loc_env)'
```

### Basic Usage

```python
import cell2location
import scanpy as sc
from cell2location.models import RegressionModel, Cell2location

# Load reference scRNA-seq and spatial data
adata_ref = sc.read_h5ad("reference_sc.h5ad")
adata_vis = sc.read_h5ad("spatial_data.h5ad")

# Step 1: Estimate reference signatures
RegressionModel.setup_anndata(adata_ref, labels_key="cell_type")
mod = RegressionModel(adata_ref)
mod.train(max_epochs=250)
adata_ref = mod.export_posterior(adata_ref, sample_kwargs={"num_samples": 1000})

# Extract signatures
inf_aver = adata_ref.varm["means_per_cluster_mu_fg"][
    [f"means_per_cluster_mu_fg_{i}" for i in adata_ref.uns["mod"]["factor_names"]]
].copy()
inf_aver.columns = adata_ref.uns["mod"]["factor_names"]

# Step 2: Run cell2location on spatial data
Cell2location.setup_anndata(adata_vis, batch_key="sample")
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    N_cells_per_location=10,  # Expected cell count per spot
    detection_alpha=200       # Detection sensitivity prior
)
mod.train(max_epochs=30000, batch_size=None, use_gpu=True)
adata_vis = mod.export_posterior(adata_vis, sample_kwargs={"num_samples": 1000})
```

## Step-by-Step

### 1. Prepare Reference Data

```python
import cell2location
import scanpy as sc
import numpy as np

# Load reference scRNA-seq data
adata_ref = sc.read_h5ad("reference_sc.h5ad")

# Filter genes (recommended)
from cell2location.utils.filtering import filter_genes
selected = filter_genes(
    adata_ref,
    cell_count_cutoff=5,
    cell_percentage_cutoff2=0.03,
    nonz_mean_cutoff=1.12
)
adata_ref = adata_ref[:, selected].copy()

# Keep raw counts
data_ref.raw = adata_ref

# Normalize (for visualization only, model uses raw counts)
sc.pp.normalize_total(adata_ref, target_sum=1e4)
sc.pp.log1p(adata_ref)
```

### 2. Train Reference Signature Model

```python
from cell2location.models import RegressionModel

# Setup anndata
RegressionModel.setup_anndata(
    adata_ref,
    labels_key="cell_type",
    batch_key="sample"  # Optional: for batch correction
)

# Create and train model
mod = RegressionModel(adata_ref)
mod.train(
    max_epochs=250,
    accelerator='gpu'  # Use 'cpu' if no GPU
)

# Export results
adata_ref = mod.export_posterior(
    adata_ref,
    sample_kwargs={"num_samples": 1000, "batch_size": 2500}
)

# Check training history
mod.plot_history()

# Export cell type signatures
inf_aver = adata_ref.varm["means_per_cluster_mu_fg"][
    [f"means_per_cluster_mu_fg_{i}" for i in adata_ref.uns["mod"]["factor_names"]]
].copy()
inf_aver.columns = adata_ref.uns["mod"]["factor_names"]
```

### 3. Prepare Spatial Data

```python
# Load spatial data
adata_vis = sc.read_h5ad("spatial_data.h5ad")

# Filter to same genes as reference
adata_vis = adata_vis[:, adata_vis.var_names.isin(adata_ref.var_names)].copy()
adata_vis.raw = adata_vis

# Normalize (for visualization only)
sc.pp.normalize_total(adata_vis, target_sum=1e4)
sc.pp.log1p(adata_vis)

# Calculate QC metrics
sc.pp.calculate_qc_metrics(adata_vis, inplace=True)
```

### 4. Run Cell2location Deconvolution

```python
from cell2location.models import Cell2location

# Setup
Cell2location.setup_anndata(adata_vis, batch_key="sample")

# Create model with hyperparameters
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    N_cells_per_location=10,   # Expected cells per spot
    detection_alpha=200         # Detection sensitivity
)

# Train
mod.train(
    max_epochs=30000,
    batch_size=None,           # Use full data
    train_size=1,
    accelerator='gpu'
)

# Export results
adata_vis = mod.export_posterior(
    adata_vis,
    sample_kwargs={"num_samples": 1000}
)
```

### 5. Analyze Results

```python
# Add cell abundance to obs (using 5% quantile = conservative estimate)
adata_vis.obs[adata_vis.uns["mod"]["factor_names"]] = adata_vis.obsm["q05_cell_abundance_w_sf"]

# Visualize cell type proportions
sq.pl.spatial_scatter(
    adata_vis,
    cmap="magma",
    color=["B_cells", "T_cells", "Macrophages"],
    ncols=3
)

# Extract all quantiles
q05 = adata_vis.obsm["q05_cell_abundance_w_sf"]
q50 = adata_vis.obsm["q50_cell_abundance_w_sf"]
q95 = adata_vis.obsm["q95_cell_abundance_w_sf"]

# Calculate uncertainty (IQR)
uncertainty = q95 - q05
```

## Hyperparameter Selection

### N_cells_per_location

Expected number of cells per spatial spot. This is a critical parameter that depends on your tissue and technology:

| Technology | Typical Range | Notes |
|------------|---------------|-------|
| Visium (55μm) | 3-10 | Depends on tissue density |
| Visium HD (2μm) | 1-3 | Higher resolution |
| Slide-seq | 1-3 | Single-cell resolution |
| MERFISH | 1 | True single-cell |

**How to determine:**
1. Check tissue histology images
2. Consider cell size and tissue density
3. Start with literature values for your tissue
4. Sensitivity analysis: try multiple values

### detection_alpha

Detection sensitivity prior. Models technical variability in RNA detection:

| Value | When to Use |
|-------|-------------|
| 200 (default) | Low within-slide variability |
| 20 | High within-slide variability |

**Guidance:**
- Try `detection_alpha=200` first
- If you see strong batch effects within a slide, try `detection_alpha=20`
- Check the detection efficiency plot in results

### max_epochs

Training iterations for the model:

| Model | Recommended | Range |
|-------|-------------|-------|
| RegressionModel (reference) | 250 | 100-500 |
| Cell2location (spatial) | 30000 | 20000-50000 |

**Convergence check:**
```python
mod.plot_history()  # Should plateau at the end
```

### Additional Parameters

```python
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    N_cells_per_location=10,
    detection_alpha=200,
    
    # Optional parameters
    detection_mean_per_sample=True,  # Account for sample-specific sensitivity
    N_cells_mean_var_ratio=1.0,      # Variance in cell abundance
    w_alpha=20.0,                    # Prior on cell type proportions
)
```

## Output Interpretation

| Output | Description | Location |
|--------|-------------|----------|
| `q05_cell_abundance_w_sf` | 5th percentile (conservative) | `.obsm` |
| `q50_cell_abundance_w_sf` | Median (best estimate) | `.obsm` |
| `q95_cell_abundance_w_sf` | 95th percentile | `.obsm` |
| `means_cell_abundance_w_sf` | Mean abundance | `.obsm` |
| `stds_cell_abundance_w_sf` | Standard deviation | `.obsm` |

**Which quantile to use?**
- `q05` (5%): Conservative, minimizes false positives
- `q50` (50%): Best point estimate
- `q95` (95%): Liberal, captures potential signal

## Niche Analysis

Identify cell type co-location patterns:

```python
from cell2location import run_colocation

# Run co-location analysis
res_dict, adata_vis = run_colocation(
    adata_vis,
    model_name="CoLocatedGroupsSklearnNMF",
    train_args={
        "n_fact": 8,       # Number of niches
        "n_iter": 10000,   # Iterations
    },
    export_args={
        "path": "./colocation_results/",
        "run_name": "niche_analysis"
    }
)

# View niche composition
res_dict["n_fact8"].print_gene_loadings()

# Plot niche spatial distribution
sq.pl.spatial_scatter(adata_vis, color="niche", ncols=3)
```

## Multi-Sample Analysis

### Processing Multiple Slides

```python
# Process each sample separately
samples = ['Sample_A', 'Sample_B', 'Sample_C']
results = {}

for sample in samples:
    adata_vis = sc.read_h5ad(f"{sample}.h5ad")
    
    # Use same reference signatures
    mod = Cell2location(
        adata_vis,
        cell_state_df=inf_aver,  # Same reference
        N_cells_per_location=10,
        detection_alpha=200
    )
    mod.train(max_epochs=30000)
    adata_vis = mod.export_posterior(adata_vis, sample_kwargs={"num_samples": 1000})
    
    results[sample] = adata_vis
```

## AI Agent Test Cases

### Basic Usage
> "Run cell2location on my Visium data with scRNA-seq reference"

```python
results = run_cell2location(
    spatial_adata, 
    reference_adata, 
    cell_type_key='cell_type',
    max_epochs=30000
)
```

### Hyperparameter Tuning
> "Adjust N_cells_per_location to 5 for sparse tissue"

```python
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    N_cells_per_location=5  # Reduced for sparse tissue
)
```

> "Run with detection_alpha=20 for high technical variability"

```python
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    detection_alpha=20  # High variability
)
```

### Result Analysis
> "Extract cell type proportions with conservative estimate"

```python
props = estimate_cell_type_proportions(
    results,
    q_threshold=0.05,  # Conservative 5% quantile
    normalize=True
)
```

> "Identify tissue niches with cell2location"

```python
from cell2location import run_colocation
res_dict, adata_vis = run_colocation(
    adata_vis,
    model_name="CoLocatedGroupsSklearnNMF",
    train_args={"n_fact": 8}
)
```

## Best Practices

1. **Quality reference**: Use well-annotated scRNA-seq from same tissue/condition
2. **Matching samples**: Reference and spatial should be from similar biological conditions
3. **Gene overlap**: Ensure sufficient gene overlap (>1000 genes recommended)
4. **Raw counts**: Always use raw integer counts, not normalized data
5. **GPU recommended**: Training is computationally intensive (hours on GPU, days on CPU)
6. **Convergence check**: Monitor ELBO history for convergence
7. **Multiple runs**: Consider running with different hyperparameters for sensitivity

## Troubleshooting

### CUDA out of memory
```python
# Reduce batch size or use CPU
mod.train(
    max_epochs=30000,
    batch_size=1000,  # Reduce from None
    accelerator='cpu'  # Use CPU
)
```

### Poor convergence
```python
# Increase epochs and check data quality
mod.train(max_epochs=50000)
mod.plot_history()  # Check convergence
```

### Unrealistic abundances
```python
# Adjust hyperparameters
mod = Cell2location(
    adata_vis,
    cell_state_df=inf_aver,
    N_cells_per_location=5,     # Lower if spots are smaller
    detection_alpha=20           # Try different values
)
```

### Reference signature issues
```python
# Check reference quality
mod_ref.plot_history()

# Visualize signatures
sc.pl.heatmap(adata_ref, var_names=inf_aver.index, groupby='cell_type')