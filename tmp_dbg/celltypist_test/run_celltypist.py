import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata as ad
import pandas as pd
import numpy as np

IN = '/mnt/c/Users/guoyang/Desktop/DemoShot/PA12_sc.h5ad'
OUT = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_test/outputs'
MODEL = 'Immune_All_Low.pkl'
GT = 'all_celltype'

adata = ad.read_h5ad(IN)
adata = prepare_data_for_celltypist(adata, layer='counts', normalize=True, target_sum=1e4, log_transform=True)
print('validated:', validate_celltypist_input(adata))
mpath = download_celltypist_model(MODEL)
print('model at:', mpath)
adata = run_celltypist_annotation(adata, model=MODEL, majority_voting=False, mode='best match', copy=False)

lab, conf = 'predicted_labels', 'conf_score'
ann_csv = os.path.join(OUT, 'annotations.csv')
export_annotations(adata, ann_csv, label_col=lab, conf_col=conf)
summ = summarize_annotations(adata, label_col=lab, conf_col=conf)
summ.to_csv(os.path.join(OUT, 'annotation_summary.csv'))
ct = pd.crosstab(adata.obs[lab], adata.obs[GT])
ct.to_csv(os.path.join(OUT, 'confusion.csv'))

def coarse(x):
    x = str(x)
    if 'CD8' in x: return 'CD8T'
    if 'CD4' in x or 'Treg' in x: return 'CD4T'
    if x.startswith('NK') or 'NK cell' in x: return 'NK'
    if 'B cell' in x or x == 'B': return 'B'
    if 'Plasma' in x: return 'Plasma'
    if any(k in x for k in ['Macrophage','Monocyte','DC','Dendritic','Mast','Neutrophil','Eosinophil','Myeloid']): return 'Myeloid'
    return 'Other'
pred_coarse = adata.obs[lab].map(coarse)
gt = adata.obs[GT].astype(str)
exact = float((adata.obs[lab].astype(str) == gt).mean())
coarse_acc = float((pred_coarse.values == gt.values).mean())
immune_mask = gt.isin(['CD8T','CD4T','NK','B','Myeloid','Plasma'])
coarse_acc_immune = float((pred_coarse.values[immune_mask.values] == gt.values[immune_mask.values]).mean())

with open(os.path.join(OUT, 'report.txt'), 'w') as f:
    f.write(f'CellTypist annotation report\nmodel: {MODEL}\ninput: {IN}\ncells: {adata.n_obs}, genes: {adata.n_vars}\n')
    f.write(f'predicted label classes: {adata.obs[lab].nunique()}\n')
    f.write(f'mean confidence: {adata.obs[conf].mean():.4f}\n')
    f.write(f'exact label match vs {GT}: {exact:.4f} (expected low: model predicts finer immune subtypes)\n')
    f.write(f'coarse-group agreement (mapped predictions) overall: {coarse_acc:.4f}\n')
    f.write(f'coarse-group agreement on immune ground-truth cells: {coarse_acc_immune:.4f}\n')
    f.write('note: granularity differs (e.g. CD8T -> Tem/Trm subtypes); see confusion.csv\n')

safe_write_h5ad(adata, os.path.join(OUT, 'annotated.h5ad'))
print('exact:', round(exact,4), 'coarse:', round(coarse_acc,4), 'coarse_immune:', round(coarse_acc_immune,4))
for fn in ['annotations.csv','annotation_summary.csv','confusion.csv','report.txt','annotated.h5ad']:
    print(os.path.join(OUT, fn))
