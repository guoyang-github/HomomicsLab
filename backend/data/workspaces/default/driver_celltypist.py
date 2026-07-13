import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
from core_analysis import *
from utils import *
import anndata as ad, numpy as np, pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
OUT='/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default/outputs'; os.makedirs(OUT, exist_ok=True)
MODEL='Immune_All_High.pkl'
a=ad.read_h5ad('/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/raw/default/PA12_sc.h5ad')
n_cells,n_genes=a.shape
mdl=load_celltypist_model(MODEL); overlap=len(set(mdl.features)&set(a.var_names))
an=prepare_data_for_celltypist(a, layer='counts', normalize=True, log_transform=True)
an=run_celltypist_annotation(an, model=MODEL, majority_voting=False, prefix='celltypist_')
lab=[c for c in an.obs.columns if 'celltypist' in c and 'label' in c][0]
conf=[c for c in an.obs.columns if 'conf' in c][0]
an=filter_by_confidence(an, conf_col=conf, label_col=lab, threshold=0.5, unassigned_label='LowConf')
filt=[c for c in an.obs.columns if c!=lab and 'label' in c and 'celltypist' in c.lower()]
filt=filt[0] if filt else lab
def coarse(s):
 s=str(s)
 if any(k in s for k in ['CD8','cytotoxic T','Temra','Tem/Trm cytotoxic','Trm cytotoxic','Tcm/Naive cytotoxic']): return 'CD8T'
 if any(k in s for k in ['CD4','helper T','Th','Treg','Tfh','Tem/Effector helper','Tcm/Naive helper']): return 'CD4T'
 if 'NK' in s and 'NKT' not in s: return 'NK'
 if 'Plasma' in s: return 'Plasma'
 if any(k in s for k in ['B cell','Naive B','Memory B','Transitional B','Age-associated B','Germinal center B']): return 'B'
 if any(k in s for k in ['Platelet','Megakaryocyte']): return 'Platelet'
 if any(k in s for k in ['Monocyte','Macrophage','DC','Dendritic','Mast','Neutrophil','Myeloid']): return 'Myeloid'
 return 'Other'
df=pd.DataFrame({'cell':an.obs_names,'all_celltype':an.obs['all_celltype'].astype(str).values,'celltypist_predicted':an.obs[lab].astype(str).values,'celltypist_conf_score':an.obs[conf].values,'celltypist_label_filtered':an.obs[filt].astype(str).values})
df['celltypist_coarse']=df['celltypist_predicted'].map(coarse)
df.to_csv(OUT+'/celltypist_comparison.csv', index=False)
df[['cell','celltypist_predicted','celltypist_coarse','celltypist_conf_score']].to_csv(OUT+'/annotations.csv', index=False)
ct=pd.crosstab(df['all_celltype'], df['celltypist_coarse']); ct.to_csv(OUT+'/confusion.csv')
imm=['CD8T','CD4T','NK','B','Plasma','Myeloid','Platelet']
per=[]
for r,g in df.groupby('all_celltype'):
 top=g['celltypist_coarse'].value_counts(); per.append({'reference':r,'n':len(g),'top_pred':top.idxmax(),'top_frac':round(top.max()/len(g),4),'agree_frac':round((g['celltypist_coarse']==r).mean(),4),'mean_conf':round(g['celltypist_conf_score'].mean(),4)})
pr=pd.DataFrame(per); pr.to_csv(OUT+'/per_reference.csv', index=False)
di=df[df['all_celltype'].isin(imm)]; acc=(di['celltypist_coarse']==di['all_celltype']).mean()
ari=adjusted_rand_score(df['all_celltype'], df['celltypist_coarse']); nmi=normalized_mutual_info_score(df['all_celltype'], df['celltypist_coarse'])
un=(df['celltypist_predicted']=='Unassigned').mean()
rep=f"Input: {n_cells} cells x {n_genes} genes\nModel: {MODEL}\nGene overlap: {overlap} / {len(mdl.features)} model features\nMode: best match (no majority voting)\nConfidence threshold: 0.5 (filtered column: {filt})\nUnassigned rate: {un:.4f}\nPreprocessing: counts layer -> normalize total 1e4 -> log1p\nARI vs all_celltype (coarse-mapped): {ari:.4f}\nNMI vs all_celltype (coarse-mapped): {nmi:.4f}\nImmune-cell accuracy (7 immune classes): {acc:.4f} on {len(di)} cells\n\nPer-reference-label summary (incl. non-immune):\n"+pr.to_string(index=False)
open(OUT+'/report.txt','w').write(rep); open(OUT+'/comparison_report.txt','w').write(rep+'\n\nConfusion (all_celltype x celltypist_coarse):\n'+ct.to_string())
an.obs['celltypist_coarse']=df['celltypist_coarse'].values
safe_write_h5ad(an, OUT+'/annotated.h5ad')
for f in ['annotations.csv','celltypist_comparison.csv','confusion.csv','per_reference.csv','report.txt','comparison_report.txt','annotated.h5ad']: print(os.path.abspath(OUT+'/'+f))
