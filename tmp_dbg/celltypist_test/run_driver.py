import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata, pandas as pd
from sklearn.metrics import accuracy_score

IN = '/mnt/c/Users/guoyang/Desktop/DemoShot/PA12_sc.h5ad'
OUT = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_test/outputs'
GT = 'all_celltype'

adata = anndata.read_h5ad(IN)
adata = prepare_data_for_celltypist(adata, layer='counts', normalize=True, target_sum=1e4, log_transform=True)
preds = annotate_cells(adata, model='Immune_All_Low.pkl', majority_voting=True, mode='best match')
adata = add_predictions_to_adata(preds) if hasattr(preds, 'to_adata') else preds
print('obs cols:', list(adata.obs.columns))
pred_col = 'majority_voting' if 'majority_voting' in adata.obs.columns else [c for c in adata.obs.columns if 'predicted' in c][0]
conf_col = [c for c in adata.obs.columns if 'conf' in c.lower()][0]
print('pred col:', pred_col, '| conf col:', conf_col)

df = adata.obs[[GT, pred_col, conf_col]].copy()
df.columns = ['ground_truth', 'celltypist_prediction', 'confidence']
df.to_csv(f'{OUT}/annotations.csv')
acc = accuracy_score(df['ground_truth'], df['celltypist_prediction'])
pd.crosstab(df['ground_truth'], df['celltypist_prediction']).to_csv(f'{OUT}/confusion.csv')
summarize_annotations(adata, label_col=pred_col, conf_col=conf_col).to_csv(f'{OUT}/annotation_summary.csv')

with open(f'{OUT}/report.txt', 'w') as f:
    f.write(f'Input: {IN}\nModel: Immune_All_Low.pkl (majority_voting=True, mode=best match)\n')
    f.write(f'Cells: {adata.n_obs}\nRaw label-level accuracy vs ground truth: {acc:.4f}\n')
    f.write('Note: Immune_All_Low predicts fine-grained immune subtypes, so raw accuracy against\n')
    f.write('coarse ground-truth labels (CD8T/CD4T/Myeloid/...) is expected to be low; see\n')
    f.write('confusion.csv for the correspondence structure.\n\nTop predicted labels:\n')
    f.write(df['celltypist_prediction'].value_counts().head(20).to_string())
for p in ['annotations.csv','confusion.csv','annotation_summary.csv','report.txt']:
    print('OUTPUT:', os.path.abspath(f'{OUT}/{p}'))
