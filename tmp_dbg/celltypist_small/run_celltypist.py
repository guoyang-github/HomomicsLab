import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad

INPUT = '/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad'
OUTDIR = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_small/outputs'
MODEL = 'Immune_All_Low.pkl'
TARGET = 'all_celltype'
os.makedirs(OUTDIR, exist_ok=True)

# ---------- Load ----------
adata = ad.read_h5ad(INPUT)
print(f'Loaded: {adata.shape}')

# CellTypist needs log1p-normalized expression in X; use 'normalized' layer if X looks like raw counts
use_layer = 'normalized'
if use_layer in adata.layers:
    Xl = adata.layers[use_layer]
    Xmax = Xl.max() if not hasattr(Xl, 'toarray') else None
    if hasattr(Xl, 'toarray'):
        Xmax = Xl.data.max() if Xl.nnz else 0
    print(f'Layer {use_layer} max value: {Xmax}')
    adata.X = Xl.toarray() if hasattr(Xl, 'toarray') else Xl
else:
    # fallback: standard normalization pipeline
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

# ---------- Validate ----------
try:
    validate_celltypist_input(adata, check_normalized=True)
    print('Input validation passed (normalized).')
except Exception as e:
    print('Validation warning:', e)

# ---------- Annotate ----------
predictions = annotate_cells(
    adata,
    model=MODEL,
    majority_voting=True,
    over_clustering=None,  # auto-generate
    mode='best match',
    use_GPU=False,
    min_prop=0,
)
adata = add_predictions_to_adata(predictions, insert_labels=True, insert_conf=True, prefix='celltypist_')

pred_col = 'celltypist_majority_voting' if 'celltypist_majority_voting' in adata.obs.columns else 'celltypist_predicted_labels'
conf_col = 'celltypist_conf_score'
print('Prediction column:', pred_col)
print(adata.obs[pred_col].value_counts())

# ---------- Compare with ground truth ----------
gt = adata.obs[TARGET].astype(str)
pred = adata.obs[pred_col].astype(str)

# Raw crosstab (ground truth rows x predicted cols)
conf = pd.crosstab(gt, pred, rownames=['ground_truth'], colnames=['predicted'])
conf.to_csv(os.path.join(OUTDIR, 'confusion.csv'))

# Map fine-grained predictions to the coarse ground-truth vocabulary
def map_pred(label):
    l = str(label).lower()
    if 'cd8' in l: return 'CD8T'
    if 'cd4' in l or 'regulatory t' in l or 'treg' in l: return 'CD4T'
    if 'nk' in l: return 'NK'
    if 'plasma' in l: return 'Plasma'
    if re.match('^b[ -]', l) or 'b cell' in l or l.startswith('b '): return 'B'
    if any(k in l for k in ['macrophage', 'monocyte', 'dendritic', ' dc', 'mast', 'myeloid', 'eosinophil', 'neutrophil', 'basophil']): return 'Myeloid'
    if 'endothelial' in l or 'ec ' in l: return 'Endothelial'
    if 'platelet' in l: return 'Platelet'
    if 'fibroblast' in l or 'stellate' in l: return 'Stellate'
    if 'caf' in l: return 'CAF'
    if 'epithelial' in l or 'ductal' in l: return 'Ductal'
    if 'endocrine' in l: return 'Endocrine'
    if 'schwann' in l: return 'Schwann'
    return 'Other'

import re
mapped = pred.map(map_pred)
agree = (mapped == gt)
accuracy = agree.mean()

per_class = []
for ct in gt.unique():
    mask = gt == ct
    n = mask.sum()
    acc = agree[mask].mean() if n else float('nan')
    per_class.append({'cell_type': ct, 'n_cells': int(n), 'accuracy': round(float(acc), 4)})
per_class_df = pd.DataFrame(per_class).sort_values('n_cells', ascending=False)
per_class_df.to_csv(os.path.join(OUTDIR, 'per_class_accuracy.csv'), index=False)

# ---------- Save outputs ----------
obs_out = adata.obs.copy()
obs_out['ground_truth'] = gt.values
obs_out['predicted_mapped'] = mapped.values
obs_out['agree'] = agree.values
obs_out.to_csv(os.path.join(OUTDIR, 'annotations.csv'))

adata.write_h5ad(os.path.join(OUTDIR, 'annotated.h5ad'))

with open(os.path.join(OUTDIR, 'report.txt'), 'w') as f:
    f.write('CellTypist Automated Annotation Report\n')
    f.write('=' * 45 + '\n')
    f.write(f'Input file      : {INPUT}\n')
    f.write(f'Model           : {MODEL}\n')
    f.write(f'N cells / genes : {adata.n_obs} / {adata.n_vars}\n')
    f.write(f'Ground truth col: {TARGET} ({gt.nunique()} classes)\n')
    f.write(f'Majority voting : True (over-clustering auto)\n\n')
    f.write('Predicted label distribution:\n')
    f.write(pred.value_counts().to_string() + '\n\n')
    f.write('Ground-truth label distribution:\n')
    f.write(gt.value_counts().to_string() + '\n\n')
    f.write(f'Overall accuracy (predictions mapped to ground-truth vocabulary): {accuracy:.4f}\n')
    f.write(f'N agreeing cells: {int(agree.sum())} / {len(agree)}\n\n')
    f.write('Per-class accuracy:\n')
    f.write(per_class_df.to_string(index=False) + '\n\n')
    f.write('Confusion matrix saved to confusion.csv (rows=ground truth, cols=predicted).\n')

print('\n==== SUMMARY ====')
print(f'Overall mapped accuracy: {accuracy:.4f} ({int(agree.sum())}/{len(agree)})')
print(per_class_df.to_string(index=False))
print('Done. Outputs in', OUTDIR)
