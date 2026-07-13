import sys, os, re
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata as ad, scanpy as sc, pandas as pd, numpy as np
from sklearn.metrics import accuracy_score, adjusted_rand_score, classification_report
SRC='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/raw/default/PA12_sc.h5ad'
OUT='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default/outputs'
os.makedirs(OUT, exist_ok=True)
adata=ad.read_h5ad(SRC)
IMM=['CD8T','CD4T','NK','B','Myeloid','Plasma','Platelet']
ad2=adata[adata.obs['all_celltype'].isin(IMM)].copy()
print('immune cells:', ad2.shape)
ad2.X=ad2.layers['counts'].copy()
sc.pp.normalize_total(ad2, target_sum=1e4); sc.pp.log1p(ad2)
ad2=run_celltypist_annotation(ad2, model='Immune_All_Low.pkl', majority_voting=True, prefix='celltypist_')
print('obs cols:', list(ad2.obs.columns))
pred_col=[c for c in ad2.obs.columns if 'majority' in c] or [c for c in ad2.obs.columns if 'predicted' in c]
pred_col=pred_col[0]; conf_col=[c for c in ad2.obs.columns if 'conf' in c][0]
def map_coarse(l):
    s=str(l)
    if re.search(r'CD8|cytotoxic T|Temra|Tem/Trm cytotoxic|Trm cytotoxic|Tcm/Naive cytotoxic', s, re.I): return 'CD8T'
    if re.search(r'CD4|helper T|Th|Treg|Tfh|Tem/Effector helper|Tcm/Naive helper', s, re.I): return 'CD4T'
    if re.search(r'NK', s) and not re.search(r'NKT', s): return 'NK'
    if re.search(r'Plasma', s, re.I): return 'Plasma'
    if re.search(r'B cell|Naive B|Memory B|Transitional B|Age-associated B|Germinal center B', s, re.I): return 'B'
    if re.search(r'Platelet|Megakaryocyte', s, re.I): return 'Platelet'
    if re.search(r'Monocyte|Macrophage|DC|Dendritic|Mast|Neutrophil|Myeloid', s, re.I): return 'Myeloid'
    return 'Other'
ad2.obs['celltypist_coarse']=ad2.obs[pred_col].map(map_coarse)
yt=ad2.obs['all_celltype'].astype(str); yp=ad2.obs['celltypist_coarse']
acc=accuracy_score(yt, yp); ari=adjusted_rand_score(yt, yp)
conf=pd.crosstab(yt, yp)
conf.to_csv(os.path.join(OUT,'confusion.csv'))
cls=classification_report(yt, yp, digits=3)
sumdf=summarize_annotations(ad2, label_col=pred_col, conf_col=conf_col)
export_annotations(ad2, os.path.join(OUT,'annotations.csv'), label_col=pred_col, conf_col=conf_col)
with open(os.path.join(OUT,'report.txt'),'w') as f:
    f.write(f'Model: Immune_All_Low.pkl (majority voting)\nImmune cells annotated: {ad2.n_obs}\n')
    f.write(f'Prediction column: {pred_col}; confidence column: {conf_col}\n')
    f.write(f'Overall accuracy vs all_celltype (coarse-mapped): {acc:.4f}\nARI: {ari:.4f}\n\nPer-class report:\n{cls}\n\nConfusion (rows=all_celltype, cols=celltypist_coarse):\n{conf.to_string()}\n\nPredicted label counts:\n{ad2.obs[pred_col].value_counts().to_string()}\n\nCoarse mapped counts:\n{yp.value_counts().to_string()}\n\nAnnotation summary:\n{sumdf.to_string()}\n')
try:
    safe_write_h5ad(ad2, os.path.join(OUT,'annotated.h5ad'))
except NameError:
    ad2.write_h5ad(os.path.join(OUT,'annotated.h5ad'))
print('ACC', acc, 'ARI', ari)
for fn in ['annotations.csv','confusion.csv','report.txt','annotated.h5ad']:
    print('OUTPUT', os.path.join(OUT,fn))
