import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import numpy as np, pandas as pd, scanpy as sc, anndata as ad
from sklearn.metrics import accuracy_score, adjusted_rand_score, classification_report, confusion_matrix
base='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default'
out=os.path.join(base,'outputs'); os.makedirs(out, exist_ok=True)
adata=ad.read_h5ad('/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/raw/default/PA12_sc.h5ad')
immune=['CD8T','CD4T','NK','B','Myeloid','Plasma']
adata=adata[adata.obs['all_celltype'].isin(immune)].copy()
adata.X=adata.layers['counts'].copy()
sc.pp.normalize_total(adata, target_sum=1e4); sc.pp.log1p(adata)
preds=annotate_cells(adata, model='Immune_All_Low.pkl', majority_voting=False)
adata=add_predictions_to_adata(preds, prefix='celltypist_')
lab=[c for c in adata.obs.columns if 'predicted_labels' in c][0]
conf=[c for c in adata.obs.columns if 'conf_score' in c][0]
def map_coarse(s):
    s=str(s)
    if any(k in s for k in ['CD8','cytotoxic T','Temra','Tem/Trm cytotoxic','Trm cytotoxic','Tcm/Naive cytotoxic']): return 'CD8T'
    if any(k in s for k in ['CD4','helper T','Th','Treg','Tfh','Tem/Effector helper','Tcm/Naive helper']): return 'CD4T'
    if 'NKT' in s: return 'Other'
    if 'NK' in s: return 'NK'
    if 'Plasma' in s: return 'Plasma'
    if any(k in s for k in ['B cell','Naive B','Memory B','Transitional B','Age-associated B','Germinal center B']): return 'B'
    if any(k in s for k in ['Monocyte','Macrophage','DC','Dendritic','Mast','Neutrophil','Myeloid']): return 'Myeloid'
    if any(k in s for k in ['Platelet','Megakaryocyte']): return 'Platelet'
    return 'Other'
adata.obs['celltypist_coarse']=adata.obs[lab].map(map_coarse)
y_true=adata.obs['all_celltype'].astype(str); y_pred=adata.obs['celltypist_coarse']
acc=accuracy_score(y_true,y_pred); ari=adjusted_rand_score(y_true,y_pred)
rep=classification_report(y_true,y_pred,zero_division=0)
cm=pd.DataFrame(confusion_matrix(y_true,y_pred,labels=immune+['Other']),index=immune+['Other'],columns=immune+['Other'])
cm.to_csv(os.path.join(out,'confusion.csv'))
ann=adata.obs[['all_celltype',lab,conf,'celltypist_coarse']].copy(); ann.columns=['all_celltype','celltypist_label','celltypist_conf','celltypist_coarse']
ann.to_csv(os.path.join(out,'annotations.csv'))
summ=summarize_annotations(adata,label_col=lab,conf_col=conf); summ.to_csv(os.path.join(out,'annotation_summary.csv'))
try:
    from utils import safe_write_h5ad; safe_write_h5ad(adata, os.path.join(out,'annotated.h5ad'))
except Exception:
    adata.write_h5ad(os.path.join(out,'annotated.h5ad'))
with open(os.path.join(out,'report.txt'),'w') as f:
    f.write('Model: Immune_All_Low.pkl (majority_voting=False)\nCells annotated (immune subset): %d\n'%adata.n_obs)
    f.write('Accuracy vs all_celltype: %.4f\nARI: %.4f\n\nClassification report:\n%s\n\nConfusion matrix:\n%s\n\nTop predicted labels:\n%s\n'%(acc,ari,rep,cm.to_string(),adata.obs[lab].value_counts().head(20).to_string()))
for fn in ['report.txt','confusion.csv','annotations.csv','annotation_summary.csv','annotated.h5ad']:
    print(os.path.join(out,fn))
print('ACC=%.4f ARI=%.4f'%(acc,ari))
