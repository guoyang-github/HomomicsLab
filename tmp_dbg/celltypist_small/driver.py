import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata as ad, pandas as pd, numpy as np
inp='/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad'
out='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_small/outputs'
adata=ad.read_h5ad(inp)
adata=prepare_data_for_celltypist(adata, layer='counts', normalize=True, target_sum=1e4, log_transform=True)
adata=run_celltypist_annotation(adata, model='Immune_All_Low.pkl', majority_voting=True, prefix='celltypist_')
print('obs cols:', list(adata.obs.columns))
pred_col=[c for c in adata.obs.columns if 'majority' in c or c=='celltypist_cell_type']
conf_col=[c for c in adata.obs.columns if 'conf' in c]
pred_col=pred_col[0]; conf_col=conf_col[0] if conf_col else None
res=adata.obs[['all_celltype',pred_col]+([conf_col] if conf_col else [])].copy()
for c in ['all_celltype',pred_col]: res[c]=res[c].astype(str)
res.columns=['ground_truth','predicted']+(['confidence'] if conf_col else [])
res.to_csv(os.path.join(out,'annotations.csv'))
ct=pd.crosstab(res['ground_truth'],res['predicted'])
ct.to_csv(os.path.join(out,'confusion.csv'))
acc=(res['ground_truth']==res['predicted']).mean()
with open(os.path.join(out,'report.txt'),'w') as f:
    f.write('CellTypist annotation report\n')
    f.write(f'Model: Immune_All_Low.pkl (majority voting)\n')
    f.write(f'Cells: {adata.n_obs}\n')
    f.write(f'Prediction column: {pred_col}\n')
    f.write(f'Exact-match accuracy vs all_celltype: {acc:.4f}\n')
    f.write('Note: ground-truth labels are coarse (e.g. CD8T, Myeloid); model predicts finer immune subtypes, so exact-match accuracy underestimates biological agreement. See confusion.csv.\n\n')
    f.write('Predicted label counts:\n'+res['predicted'].value_counts().to_string()+'\n\n')
    f.write('Confusion matrix:\n'+ct.to_string()+'\n')
print('accuracy:',acc)
print(os.path.join(out,'annotations.csv'))
print(os.path.join(out,'confusion.csv'))
print(os.path.join(out,'report.txt'))
