import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata as ad, numpy as np, pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
IN='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/raw/default/PA12_sc.h5ad'
OUT='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default/outputs'
os.makedirs(OUT, exist_ok=True)
adata=ad.read_h5ad(IN)
adata=prepare_data_for_celltypist(adata, layer='counts', normalize=True, target_sum=1e4, log_transform=True)
MODEL='Immune_All_Low.pkl'
m=load_celltypist_model(MODEL)
try: overlap=len(set(map(str,adata.var_names))&set(map(str,m.features)))
except Exception: overlap=-1
import scanpy as sc
sc.pp.pca(adata, n_comps=30); sc.pp.neighbors(adata, n_neighbors=15); sc.tl.leiden(adata, resolution=1.0)
res=annotate_cells(adata, model=MODEL, mode='best match', majority_voting=True, over_clustering='leiden')
adata=add_predictions_to_adata(res, prefix='celltypist_')
cols=list(adata.obs.columns)
pc=[c for c in cols if 'majority' in c.lower()]
pc=pc[0] if pc else [c for c in cols if 'predicted' in c.lower()][0]
cc=[c for c in cols if 'conf' in c.lower()][0]
adata.obs['celltypist_predicted']=adata.obs[pc].astype(str)
adata.obs['celltypist_conf_score']=pd.to_numeric(adata.obs[cc], errors='coerce').fillna(0)
TH=0.5
adata.obs['celltypist_label_filtered']=np.where(adata.obs['celltypist_conf_score']>=TH, adata.obs['celltypist_predicted'], 'Unassigned')
def cmap(l):
 s=l.lower()
 if 'unassigned' in s: return 'Unassigned'
 if 'nkt' in s: return 'Other'
 if 'cd8' in s or 'cytotoxic' in s or 'temra' in s: return 'CD8T'
 if 'cd4' in s or 'helper' in s or 'treg' in s or 'tfh' in s or s.startswith('th'): return 'CD4T'
 if 'nk' in s: return 'NK'
 if 'plasma' in s: return 'Plasma'
 if 'b cell' in s or s.endswith(' b') or 'naive b' in s or 'memory b' in s or 'germinal' in s or 'age-associated' in s: return 'B'
 if any(k in s for k in ['monocyte','macrophage','dendritic','mast','neutrophil','myeloid']) or s.startswith('dc'): return 'Myeloid'
 if 'platelet' in s or 'megakaryocyte' in s: return 'Platelet'
 return 'Other'
adata.obs['celltypist_coarse']=adata.obs['celltypist_label_filtered'].map(cmap)
df=adata.obs[['all_celltype','celltypist_predicted','celltypist_conf_score','celltypist_label_filtered','celltypist_coarse']]
df.to_csv(os.path.join(OUT,'celltypist_comparison.csv'))
df.to_csv(os.path.join(OUT,'annotations.csv'))
ct=pd.crosstab(df.all_celltype, df.celltypist_coarse)
ct.to_csv(os.path.join(OUT,'confusion.csv'))
ari=adjusted_rand_score(df.all_celltype, df.celltypist_coarse)
nmi=normalized_mutual_info_score(df.all_celltype, df.celltypist_coarse)
rows=[]
for r,g in df.groupby('all_celltype'):
 rows.append({'reference':r,'n':len(g),'agreement':round(float((g.celltypist_coarse==r).mean()),4),'top_pred':str(g.celltypist_coarse.value_counts().head(3).to_dict())})
pr=pd.DataFrame(rows)
pr.to_csv(os.path.join(OUT,'per_reference.csv'), index=False)
un=float((df.celltypist_label_filtered=='Unassigned').mean())
acc=float((df.all_celltype==df.celltypist_coarse).mean())
lines=[f'Input: {adata.shape[0]} cells x {adata.shape[1]} genes (PA12_sc.h5ad)',f'Model: {MODEL}',f'Gene overlap: {overlap} model features present in data',f'Mode: best match + majority voting (over_clustering=True)',f'Confidence threshold: {TH}',f'Unassigned rate: {un:.4f} ({int((df.celltypist_label_filtered=="Unassigned").sum())} cells)','Preprocessing: counts layer -> normalize_total(target_sum=1e4) -> log1p',f'Overall coarse-category accuracy vs all_celltype: {acc:.4f}',f'ARI: {ari:.4f}   NMI: {nmi:.4f}','','Per-reference agreement (all labels incl. non-immune):',pr.to_string(index=False),'','Confusion matrix (rows=reference all_celltype, cols=CellTypist coarse):',ct.to_string()]
open(os.path.join(OUT,'report.txt'),'w').write('\n'.join(lines))
open(os.path.join(OUT,'comparison_report.txt'),'w').write('\n'.join(lines))
try:
 safe_write_h5ad(adata, os.path.join(OUT,'annotated.h5ad'))
except Exception:
 adata.write_h5ad(os.path.join(OUT,'annotated.h5ad'))
for f in sorted(os.listdir(OUT)): print(os.path.join(OUT,f))
