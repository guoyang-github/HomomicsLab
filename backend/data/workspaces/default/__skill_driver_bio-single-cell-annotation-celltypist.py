import sys, os, json
import numpy as np, pandas as pd
import scanpy as sc, anndata
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *

WS = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default'
OUT = os.path.join(WS, 'outputs'); os.makedirs(OUT, exist_ok=True)
MODEL, MODE, P_THRES = 'Immune_All_Low.pkl', 'best match', 0.5
anndata.settings.allow_write_nullable_strings = True

adata = sc.read_h5ad(os.path.join(WS, 'data', 'PA12_small.h5ad'))
if 'counts' in adata.layers:
    adata.X = adata.layers['counts'].copy()
    prep = 'raw counts taken from layer "counts", then normalize_total(target_sum=1e4) + log1p'
else:
    prep = 'WARNING: no counts layer; existing X assumed raw counts, then normalize_total(target_sum=1e4) + log1p'
sc.pp.normalize_total(adata, target_sum=1e4); sc.pp.log1p(adata)
validate_celltypist_input(adata, check_normalized=True)
download_celltypist_model(MODEL)
overlap = int(len(np.intersect1d(adata.var_names, load_celltypist_model(MODEL).features)))

res = annotate_cells(adata, model=MODEL, mode=MODE, p_thres=P_THRES, majority_voting=True, use_GPU=False)
pl = res.predicted_labels
pred = (pl['majority_voting'] if 'majority_voting' in pl.columns else pl['predicted_labels']).astype(str)
conf = pl['conf_score'] if 'conf_score' in pl.columns else pd.Series(np.nan, index=pl.index)
truth = adata.obs['all_celltype'].astype(str)

adata.obs['celltypist_predicted'] = pred
adata.obs['celltypist_conf_score'] = conf.astype(float)
adata.obs.index = adata.obs.index.astype(str); adata.var.index = adata.var.index.astype(str)
for df in (adata.obs, adata.var):
    for c in df.columns:
        if str(df[c].dtype).startswith('string'):
            df[c] = df[c].astype(object).where(pd.notna(df[c]), None)

ari = adjusted_rand_score(truth, pred); nmi = normalized_mutual_info_score(truth, pred)
unassigned = float((pred == 'Unassigned').mean())
pl.to_csv(os.path.join(OUT, 'annotations.csv'))
pd.DataFrame({'all_celltype': truth, 'celltypist_predicted': pred,
              'celltypist_conf_score': conf.astype(float)}).to_csv(os.path.join(OUT, 'celltypist_comparison.csv'))
ct = pd.crosstab(truth, pred, normalize='index').round(3)
agree = pd.DataFrame({'top_celltypist_label': ct.idxmax(axis=1), 'agreement': ct.max(axis=1),
                      'n_cells': truth.value_counts()})
open(os.path.join(OUT, 'comparison_report.txt'), 'w').write(
    'Per all_celltype label agreement with CellTypist predictions\n\n' + agree.to_string()
    + '\n\nRow-normalized crosstab (all_celltype x celltypist_predicted):\n' + ct.to_string())

rep = [f'Cells x Genes: {adata.n_obs} x {adata.n_vars}', f'Model: {MODEL}',
       f'Gene overlap (model features vs data genes): {overlap}', f'Mode: {MODE}',
       f'p_thres: {P_THRES}', 'Majority voting: True', f'Preprocessing: {prep}',
       f'Unassigned rate: {unassigned:.3f}', f'ARI vs all_celltype: {ari:.3f}',
       f'NMI vs all_celltype: {nmi:.3f}', 'Per-label agreement:', agree.to_string()]
open(os.path.join(OUT, 'report.txt'), 'w').write('\n'.join(rep))

adata.write_h5ad(os.path.join(OUT, 'annotated.h5ad'))
files = ['outputs/annotated.h5ad', 'outputs/annotations.csv', 'outputs/celltypist_comparison.csv',
         'outputs/comparison_report.txt', 'outputs/report.txt']
json.dump({'outputs': files}, open(os.path.join(WS, '__skill_outputs__.json'), 'w'), indent=2)
print('\n'.join(rep[:10])); print('\nOutputs written:'); [print(' -', f) for f in files]