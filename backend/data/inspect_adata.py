import scanpy as sc
import celltypist

adata = sc.read_h5ad('/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/mock_pbmc_processed.h5ad')
print('AnnData shape:', adata.shape)
print('Obs columns:', adata.obs.columns.tolist())
print('Var index first 10:', adata.var_names[:10].tolist())
print('X max sample:', adata.X[:100].max())
print('X min sample:', adata.X[:100].min())
print('X mean sample:', adata.X[:100].mean())
