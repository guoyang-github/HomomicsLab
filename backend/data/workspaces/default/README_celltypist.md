# CellTypist annotation for PA12 datasets

Inputs:
- data/PA12_sc.h5ad
- data/PA12_small.h5ad

A ready-to-run pipeline was generated: `run_celltypist_pipeline.py`.

## Run (in an environment with celltypist, scanpy, anndata, scikit-learn, scipy)

```bash
pip install celltypist scanpy anndata scikit-learn scipy
cd data/workspaces/default
python run_celltypist_pipeline.py \
  --inputs data/PA12_sc.h5ad data/PA12_small.h5ad \
  --model Immune_All_Low.pkl \
  --output-dir ./celltypist_results \
  --confidence 0.5
```

## What it does (skill workflow)
1. Load h5ad; auto-detect raw counts and apply normalize_total(1e4)+log1p if needed
2. Ensure `leiden` clusters for majority voting (compute HVG/PCA/neighbors if absent)
3. Download/load model (default `Immune_All_Low.pkl`)
4. `celltypist.annotate(mode='best match', majority_voting=True, over_clustering='leiden')`
5. Attach predictions to AnnData + convenience `celltypist_label` column
6. Confidence filtering -> `celltypist_label_filtered` (Unassigned < threshold)
7. Per-input outputs in `celltypist_results/<name>/`:
   - `<name>_summary.csv` (n_cells, proportion, mean/median confidence)
   - `<name>_annotations.csv` (barcode, label, filtered label, confidence)
   - UMAP figure and `<name>_annotated.h5ad` (nullable-string-safe write)

## Model choice
Default `Immune_All_Low.pkl` (28 broad human immune types). For finer subtypes use `Immune_All_High.pkl`.
Data must use **gene symbols** (not ENSEMBL) and be log-normalized with the full gene set (do NOT subset to HVGs before annotation).

## Execution status in this run
The automated shell sandbox was unavailable (bubblewrap init error: `Can't mkdir /work: Read-only file system`), so the pipeline could not be executed here. The script and these instructions are provided so the annotation can be run end-to-end in a working Python environment.
