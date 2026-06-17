---
name: bio-single-cell-annotation-markers
description: Marker-based cell type annotation using manual marker gene scoring in R (Seurat) and Python (Scanpy)
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, Seurat]
keywords: ["single-cell", "annotation", "markers", "manual", "scoring", "cell-type"]
---

# bio-single-cell-annotation-markers

基于已知标记基因手动注释单细胞RNA-seq数据的细胞类型。使用标记基因表达得分进行自动化细胞类型分配。

## 概述

基于已知细胞类型标记基因的平均表达得分，自动为每个cluster分配细胞类型。无需运行耗时的差异分析（FindAllMarkers），适合快速注释。

## 适用场景

- 单细胞RNA-seq数据（10x Genomics, Smart-seq2等）
- 需要快速基于已知标记基因进行细胞类型注释
- 无需运行耗时的差异分析（FindAllMarkers）

## 版本兼容性

- **R**: 4.0+
- **Seurat**: 4.0+ (支持v4和v5)
- **Python**: 3.8+
- **scanpy**: 1.9+

## 安装

### R依赖
```r
install.packages(c('Seurat', 'dplyr', 'ggplot2'))
```

### Python依赖
```bash
pip install scanpy pandas numpy matplotlib
```


---

## Seurat (R)

### 1. 准备数据

确保你有一个已聚类的Seurat对象（seurat_clustered.rds）：

```r
# 数据应包含:
# - 已标准化的表达矩阵 (NormalizeData)
# - 已识别的高变基因 (FindVariableFeatures)
# - 已缩放的数据 (ScaleData)
# - 已降维 (RunPCA, RunUMAP)
# - 已聚类 (FindNeighbors, FindClusters)
```

### 2. 运行注释

```r
library(Seurat)
library(dplyr)
library(ggplot2)

# 设置路径
data_dir <- '/path/to/your/data'
output_dir <- '/path/to/output'

# 加载数据
seurat_obj <- readRDS(file.path(data_dir, 'seurat_clustered.rds'))

# 定义细胞类型标记基因
marker_genes <- list(
  'CD8+ T cells' = c('CD3D', 'CD3E', 'CD8A'),
  'CD4+ T cells' = c('CD3D', 'CD3E', 'CD4'),
  'B cells' = c('CD79A', 'MS4A1'),
  'NK cells' = c('KLRF1', 'NCAM1'),
  'Myeloid' = c('AIF1', 'CD68', 'CST3'),
  'Platelet' = c('PPBP'),
  'Fibroblasts' = c('LUM', 'DCN', 'COL1A1'),
  'Stellate cells' = c('RGS5'),
  'Endothelial cells' = c('PLVAP', 'VWF', 'PECAM1'),
  'Schwann cells' = c('SOX10', 'PLP1'),
  'Acinar cells' = c('PRSS1', 'PRSS3'),
  'Endocrine' = c('CHGB'),
  'Ductal cells' = c('KRT19', 'MMP7'),
  'Alpha cells' = c('GCG'),
  'Beta cells' = c('INS', 'NKX2-2'),
  'Delta cells' = c('SST'),
  'Macrophages' = c('CD14', 'FCGR3A'),
  'Dendritic cells' = c('CD1C', 'FCER1A'),
  'Monocytes' = c('CD14', 'CCR2'),
  'Treg' = c('FOXP3', 'IL2RA')
)

# 计算每个cluster的平均表达
all_genes <- unique(unlist(marker_genes))
cluster_means <- AverageExpression(seurat_obj, features = all_genes, slot = 'data')$RNA

# 为每个cluster分配细胞类型
clusters <- sort(unique(seurat_obj$seurat_clusters))
manual_annotations <- c()

for (i in clusters) {
  cluster_col <- paste0('g', i)  # Seurat v5需要添加'g'前缀
  cluster_means_i <- cluster_means[, cluster_col, drop=FALSE]
  
  # 计算每个细胞类型的得分
  scores <- sapply(names(marker_genes), function(ct) {
    genes <- marker_genes[[ct]]
    genes_in_data <- genes[genes %in% rownames(cluster_means_i)]
    if (length(genes_in_data) > 0) {
      mean(as.matrix(cluster_means_i[genes_in_data, ]))
    } else {
      0
    }
  })
  
  # 分配得分最高的细胞类型
  best_ct <- names(which.max(scores))
  manual_annotations <- c(manual_annotations, best_ct)
  cat('Cluster', i, '->', best_ct, '\n')
}

names(manual_annotations) <- as.character(clusters)

# 添加到metadata
seurat_obj@meta.data$manual_cell_type <- manual_annotations[as.character(seurat_obj$seurat_clusters)]
```

### 3. 可视化

```r
# UMAP - 手动注释
p1 <- DimPlot(seurat_obj, 
              reduction = 'umap', 
              group.by = 'manual_cell_type',
              label = TRUE,
              repel = TRUE) + 
  ggtitle('Manual Cell Type Annotation') +
  theme(legend.position = 'right')

ggsave(file.path(output_dir, 'umap_celltype_manual.png'), 
       p1, width = 12, height = 9)

# DotPlot - 标记基因
all_markers_plot <- unlist(marker_genes)
p2 <- DotPlot(seurat_obj, 
              features = all_markers_plot,
              group.by = 'seurat_clusters') + 
  RotatedAxis() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

ggsave(file.path(output_dir, 'dotplot_marker_genes.png'), 
       p2, width = 14, height = 8)
```

### 4. 保存结果

```r
# 保存注释结果CSV
annotation_df <- data.frame(
  cluster = names(manual_annotations),
  manual_cell_type = manual_annotations
)
write.csv(annotation_df, file.path(output_dir, 'celltype_annotations.csv'), 
          row.names = FALSE)

# 保存Seurat对象
saveRDS(seurat_obj, file.path(output_dir, 'seurat_annotated.rds'))
```

---

## Scanpy (Python)

### 1. 准备数据

确保你有一个已聚类的AnnData对象：

```python
import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 加载数据
adata = sc.read_h5ad('clustered_data.h5ad')

# 数据应包含:
# - 已标准化的表达矩阵 (adata.X为log-normalized)
# - 已识别的高变基因 (adata.var['highly_variable'])
# - 已降维 (adata.obsm['X_pca'], adata.obsm['X_umap'])
# - 已聚类 (adata.obs['leiden'])
```

### 2. 运行注释

```python
# 定义细胞类型标记基因
marker_genes = {
    'CD8+ T cells': ['CD3D', 'CD3E', 'CD8A'],
    'CD4+ T cells': ['CD3D', 'CD3E', 'CD4'],
    'B cells': ['CD79A', 'MS4A1'],
    'NK cells': ['KLRF1', 'NCAM1'],
    'Myeloid': ['AIF1', 'CD68', 'CST3'],
    'Platelet': ['PPBP'],
    'Fibroblasts': ['LUM', 'DCN', 'COL1A1'],
    'Stellate cells': ['RGS5'],
    'Endothelial cells': ['PLVAP', 'VWF', 'PECAM1'],
    'Schwann cells': ['SOX10', 'PLP1'],
    'Acinar cells': ['PRSS1', 'PRSS3'],
    'Endocrine': ['CHGB'],
    'Ductal cells': ['KRT19', 'MMP7'],
    'Alpha cells': ['GCG'],
    'Beta cells': ['INS', 'NKX2-2'],
    'Delta cells': ['SST'],
    'Macrophages': ['CD14', 'FCGR3A'],
    'Dendritic cells': ['CD1C', 'FCER1A'],
    'Monocytes': ['CD14', 'CCR2'],
    'Treg': ['FOXP3', 'IL2RA']
}

# 计算每个cluster的平均表达
clusters = sorted(adata.obs['leiden'].unique())
cluster_annotations = {}

for cluster in clusters:
    # 获取该cluster的细胞
    cluster_cells = adata.obs['leiden'] == cluster
    cluster_adata = adata[cluster_cells, :]
    
    # 计算每个细胞类型的得分
    scores = {}
    for cell_type, genes in marker_genes.items():
        # 筛选存在的基因
        genes_in_data = [g for g in genes if g in adata.var_names]
        if len(genes_in_data) > 0:
            # 计算平均表达
            expr = cluster_adata[:, genes_in_data].X.mean()
            scores[cell_type] = expr
        else:
            scores[cell_type] = 0
    
    # 分配得分最高的细胞类型
    best_cell_type = max(scores, key=scores.get)
    cluster_annotations[cluster] = best_cell_type
    print(f'Cluster {cluster} -> {best_cell_type}')

# 添加到obs
adata.obs['manual_cell_type'] = adata.obs['leiden'].map(cluster_annotations)
```

### 3. 替代方法：使用score_genes

```python
# 使用scanpy内置的score_genes函数为每个细胞打分
for cell_type, genes in marker_genes.items():
    genes_in_data = [g for g in genes if g in adata.var_names]
    if len(genes_in_data) > 0:
        sc.tl.score_genes(adata, genes_in_data, score_name=f'score_{cell_type.replace(" ", "_")}')

# 基于分数分配细胞类型
score_cols = [c for c in adata.obs.columns if c.startswith('score_')]
cluster_cell_types = {}

for cluster in clusters:
    cluster_data = adata.obs[adata.obs['leiden'] == cluster]
    # 计算每个细胞类型在该cluster的平均得分
    mean_scores = cluster_data[score_cols].mean()
    # 选择得分最高的
    best_cell_type = mean_scores.idxmax().replace('score_', '').replace('_', ' ')
    cluster_cell_types[cluster] = best_cell_type

adata.obs['manual_cell_type'] = adata.obs['leiden'].map(cluster_cell_types)
```

### 4. 可视化

```python
# UMAP - 手动注释
sc.pl.umap(adata, color='manual_cell_type', legend_loc='on data', 
           title='Manual Cell Type Annotation', save='_celltype_manual.png')

# DotPlot - 标记基因
all_markers = [g for genes in marker_genes.values() for g in genes]
sc.pl.dotplot(adata, var_names=all_markers, groupby='leiden', 
              title='Marker Gene Expression', save='_marker_genes.png')

# 热图
sc.pl.heatmap(adata, var_names=all_markers, groupby='manual_cell_type',
              show_gene_labels=True, save='_marker_heatmap.png')
```

### 5. 保存结果

```python
# 保存注释结果CSV
annotation_df = pd.DataFrame({
    'cluster': list(cluster_annotations.keys()),
    'manual_cell_type': list(cluster_annotations.values())
})
annotation_df.to_csv('celltype_annotations.csv', index=False)

# 保存AnnData对象
adata.write('annotated_data.h5ad')
```

---

## 常用细胞类型标记基因参考

### 免疫细胞

| 细胞类型 | 标记基因 |
|----------|----------|
| CD8+ T cells | CD3D, CD3E, CD8A, GZMA, GZMB |
| CD4+ T cells | CD3D, CD3E, CD4, IL7R |
| B cells | CD79A, MS4A1, CD19, IGKC |
| NK cells | KLRF1, NCAM1, NKG7, GNLY |
| Tregs | FOXP3, IL2RA, CTLA4 |
| Macrophages | AIF1, CD68, CST3, CD14 |
| Monocytes | CD14, CCR2, FCGR3A |
| Dendritic cells | CD1C, FCER1A, HLA-DRA |
| Neutrophils | S100A8, S100A9, CXCR2 |
| Mast cells | TPSB2, TPSAB1, KIT |
| Platelet | PPBP, PF4, GP9 |

### 基质细胞

| 细胞类型 | 标记基因 |
|----------|----------|
| Fibroblasts | LUM, DCN, COL1A1, COL3A1 |
| Stellate cells | RGS5, PDGFRA, NG2 |
| Myofibroblasts | ACTA2, TAGLN, MYL9 |
| Smooth muscle cells | ACTA2, MYH11, DES |

### 上皮细胞

| 细胞类型 | 标记基因 |
|----------|----------|
| Ductal cells | KRT19, MMP7, SOX9 |
| Acinar cells | PRSS1, PRSS3, CPA1, AMY2A |
| Endocrine | CHGB, INS, GCG, SST |
| Alpha cells | GCG, MAFA |
| Beta cells | INS, NKX2-2, PDX1 |
| Delta cells | SST, HHEX |
| Goblet cells | MUC1, TFF3, KRT20 |

### 其他细胞类型

| 细胞类型 | 标记基因 |
|----------|----------|
| Endothelial cells | PLVAP, VWF, PECAM1, CDH5 |
| Schwann cells | SOX10, PLP1, MBP |
| Neurons | MAP2, NEUN, SYNAPTOPHYSIN |
| Adipocytes | LPL, FABP4, ADIPOQ |
| Hepatocytes | ALB, APOB, TTR |
| Cholangiocytes | KRT7, KRT19, AQP1 |

## 参数说明

### R (Seurat)

| 参数 | 说明 |
|------|------|
| `marker_genes` | 列表，每个细胞类型对应的标记基因向量 |
| `cluster_col` | Seurat对象中cluster所在的列名（默认'seurat_clusters'） |
| `output_col` | 输出细胞类型注释的列名 |

### Python (Scanpy)

| 参数 | 说明 |
|------|------|
| `marker_genes` | 字典，每个细胞类型对应的标记基因列表 |
| `cluster_col` | AnnData.obs中cluster所在的列名（默认'leiden'） |
| `output_col` | 输出细胞类型注释的列名 |

## 注意事项

1. **Seurat v5兼容性**: Seurat v5中`AverageExpression`的输出列名会添加'g'前缀
2. **标记基因选择**: 确保选择的标记基因在数据中有表达
3. **多亚型注释**: 某些细胞类型可能有多个亚型，需要更精细的标记基因组合
4. **验证**: 建议使用多种方法交叉验证注释结果

## 输出文件

### R输出
- `seurat_annotated.rds`: 包含细胞类型注释的Seurat对象
- `celltype_annotations.csv`: Cluster到细胞类型的映射表
- `umap_celltype_manual.png`: 细胞类型UMAP可视化
- `dotplot_marker_genes.png`: 标记基因DotPlot

### Python输出
- `annotated_data.h5ad`: 包含细胞类型注释的AnnData对象
- `celltype_annotations.csv`: Cluster到细胞类型的映射表
- `figures/umap_celltype_manual.png`: 细胞类型UMAP可视化
- `figures/dotplot_marker_genes.png`: 标记基因DotPlot

## 扩展阅读

- [Seurat - Guided Clustering Tutorial](https://satijalab.org/seurat/articles/pbmc3k_tutorial.html)
- [Scanpy Documentation](https://scanpy.readthedocs.io/)
- [CellMarker 2.0](http://bio-bigdata.hrbmu.edu.cn/CellMarker/): 细胞标记基因数据库
- [PanglaoDB](https://panglaodb.se/): 单细胞测序数据库
