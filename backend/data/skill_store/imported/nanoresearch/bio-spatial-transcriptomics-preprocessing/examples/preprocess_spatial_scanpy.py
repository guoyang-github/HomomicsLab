"""Preprocess 10x Visium spatial transcriptomics data with Scanpy + Squidpy"""
# Reference: scanpy 1.10+, squidpy 1.6+ | Verify API if version differs

import scanpy as sc
import squidpy as sq

# Step 1: Load Visium data -----------------------------------------------------
# NOTE: sq.read.visium was removed in squidpy 1.6+. Using sc.read_visium instead.
# Parameter changed from counts_file (plural) to count_file (singular).
adata = sc.read_visium(
    path="spatial/",
    count_file="filtered_feature_bc_matrix.h5",
    library_id="sample1"
)
print(f"Raw: {adata.n_obs} spots, {adata.n_vars} genes")

# Step 2: Calculate QC metrics -------------------------------------------------
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

# Step 3: Filter spots ---------------------------------------------------------
# Remove spots outside tissue (if present)
if 'in_tissue' in adata.obs.columns:
    adata = adata[adata.obs['in_tissue'] == 1].copy()

# Spatial thresholds are more lenient than single-cell
sc.pp.filter_cells(adata, min_genes=100)  # Lower than scRNA-seq (200)
adata = adata[adata.obs['total_counts'] > 200, :].copy()
adata = adata[adata.obs['pct_counts_mt'] < 20, :].copy()
print(f"Filtered: {adata.n_obs} spots, {adata.n_vars} genes")

# Step 4: Store raw counts and normalize ---------------------------------------
adata.raw = adata.copy()
adata.layers['counts'] = adata.X.copy()

sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Step 5: Highly variable genes ------------------------------------------------
sc.pp.highly_variable_genes(adata, n_top_genes=2000, flavor='seurat')
print(f"HVGs: {adata.var.highly_variable.sum()}")

# Step 6: Scale and dimensionality reduction -----------------------------------
sc.pp.scale(adata, max_value=10)
sc.pp.pca(adata, n_comps=50, use_highly_variable=True)

# Step 7: Clustering -----------------------------------------------------------
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.8)
sc.tl.umap(adata)

# Step 8: Spatial visualization ------------------------------------------------
sq.pl.spatial_scatter(adata, color=['leiden'], library_id='sample1', size=1.5)
sc.pl.umap(adata, color='leiden')

# Step 9: Spatially variable features (Moran's I) -----------------------------
# Compute on all genes or a subset for speed
sq.gr.spatial_autocorr(adata, genes=adata.var_names[adata.var.highly_variable][:100], mode="moran")
moran_df = adata.uns['moranI'].copy()
moran_df = moran_df.sort_values('I', ascending=False)
print(f"Top SVGs: {list(moran_df.head(6).index)}")

# Visualize top spatially variable genes
top_svgs = moran_df.head(6).index.tolist()
sq.pl.spatial_scatter(adata, color=top_svgs, library_id='sample1',
                      size=1.5, ncols=3, cmap='viridis')

# Step 10: Save ----------------------------------------------------------------
adata.write_h5ad('spatial_preprocessed.h5ad')
print('Saved preprocessed spatial data')
