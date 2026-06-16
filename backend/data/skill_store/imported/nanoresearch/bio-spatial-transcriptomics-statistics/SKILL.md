---
name: bio-spatial-transcriptomics-statistics
version: 1.0.0
description: Comprehensive spatial statistics for spatial transcriptomics data analysis
tags:
  - spatial-transcriptomics
  - statistics
  - spatial-autocorrelation
  - hotspot-detection
  - pattern-analysis
  - network-analysis
  - zone-analysis
author: NanoResearch Team
requirements:
  python:
    - scanpy>=1.9.0
    - squidpy>=1.2.0
    - numpy>=1.20.0
    - pandas>=1.3.0
    - matplotlib>=3.4.0
    - seaborn>=0.11.0
    - libpysal>=4.5.0
    - esda>=2.4.0
    - networkx>=2.6.0
    - scikit-learn>=1.0.0
    - pointpats>=2.2.0
    - scipy>=1.7.0
---

# 空间转录组统计分析方法

## 概述

本技能提供空间转录组数据的综合统计分析框架，涵盖5大类15+种统计方法：

| 类别 | 方法 | 用途 |
|------|------|------|
| **核心统计** | Moran's I, Geary's C, LISA, Bivariate Moran | 空间自相关分析 |
| **热点检测** | Getis-Ord Gi* | 识别统计显著的热点/冷点 |
| **模式分析** | Join Counts, Co-occurrence, Ripley's K/L | 空间模式识别 |
| **网络分析** | Centrality, Network Efficiency | 网络拓扑分析 |
| **区域分析** | Ro/e, Niche Enrichment | 微环境富集分析 |

## 快速选择器

### 按分析目标选择方法

```
问题: "这个基因的空间分布是随机的还是聚集的？"
    ↓ 选择 Moran's I (全局) 或 LISA (局部)

问题: "哪些区域显示高表达聚集？"
    ↓ 选择 Getis-Ord Gi* 热点检测

问题: "细胞类型A是否倾向于与细胞类型B共定位？"
    ↓ 选择 Co-occurrence 或 Join Counts

问题: "某种细胞类型在哪个尺度上聚集？"
    ↓ 选择 Ripley's K/L 函数

问题: "哪些节点在空间网络中起关键作用？"
    ↓ 选择 Centrality 分析

问题: "细胞类型X在距离神经元不同距离处的分布如何？"
    ↓ 选择 Anchor Zones + Ro/e 分析
```

### 按数据类型选择方法

| 数据类型 | 推荐方法 | 替代方法 |
|----------|----------|----------|
| 连续表达数据 (基因表达) | Moran's I, LISA | Geary's C, Getis-Ord Gi* |
| 分类数据 (细胞类型) | Join Counts, Co-occurrence | Ripley's K |
| 多变量关系 | Bivariate Moran's I | 相关网络分析 |
| 空间尺度分析 | Ripley's K/L 函数 | 变程分析 |

## 导入方法

```python
import sys
sys.path.append('scripts/python')

# 导入特定模块
from core_stats import compute_morans_i, compute_lisa, run_autocorrelation_analysis
from hotspot import compute_getis_ord_gi, comprehensive_hotspot_analysis
from pattern import compute_cooccurrence, compute_ripley_k, analyze_spatial_patterns
from network import compute_centrality_scores, analyze_network_structure
from zones import define_neural_zones, compute_roe, analyze_spatial_zones
from utils import validate_spatial_data, infer_spatial_platform, suggest_neighbors

# 或全部导入
from core_stats import *
from hotspot import *
from pattern import *
from network import *
from zones import *
from utils import *
```

## 核心空间自相关统计

### Moran's I - 全局空间自相关

**适用场景**: 检验基因表达是否存在空间聚集（正自相关）或分散（负自相关）

```python
from core_stats import compute_morans_i

# 分析特定基因
results = compute_morans_i(
    adata,
    genes=['GeneA', 'GeneB'],
    k=6,  # 邻居数（Visium推荐6）
    use_weights=True
)

print(results)
#      gene         I   p_value    z_score
# 0  GeneA  0.523456  0.000001  12.345678
# 1  GeneB  0.234567  0.012345   2.456789
```

**结果解读**:
- I > 0 且 p < 0.05: 显著空间聚集
- I < 0 且 p < 0.05: 显著空间分散
- I ≈ 0: 随机分布

### LISA - 局部空间自相关

**适用场景**: 识别具体哪些位置形成高-高（热点）或低-低（冷点）聚类

> **Note:** `sc.pl.spatial()` was removed in scanpy 1.12+. Use `sq.pl.spatial_scatter()` from squidpy instead.  
> Parameter mapping: `spot_size` → `size`. `alpha_img`, `bw`, and `scale_factor` are not supported in squidpy.
```python
from core_stats import compute_lisa

# 分析单个基因的空间聚类模式
lisa_results = compute_lisa(
    adata,
    gene='GeneA',
    k=6,
    permutations=999
)

# 结果包含每个spot的分类
adata.obs['lisa_cluster'] = lisa_results['cluster'].values

# 可视化
sq.pl.spatial_scatter(adata, color='lisa_cluster')
```

**聚类类型**:
- HH: 高值被高值包围（热点）
- LL: 低值被低值包围（冷点）
- HL: 高值被低值包围（异常值）
- LH: 低值被高值包围（异常值）

### Geary's C - 空间异质性

**适用场景**: 与Moran's I互补，对局部差异更敏感

```python
from core_stats import compute_gearys_c, compare_morans_geary

# 单独计算
c_results = compute_gearys_c(adata, genes=['GeneA'])

# 或比较两种统计量
comparison = compare_morans_geary(adata, genes=['GeneA', 'GeneB'])
```

**解读**:
- C < 1: 正空间自相关（与Moran's I > 0一致）
- C = 1: 随机分布
- C > 1: 负空间自相关

### 完整自相关分析

```python
from core_stats import run_autocorrelation_analysis

results = run_autocorrelation_analysis(
    adata,
    genes=None,  # 使用高变基因
    k=6,
    compute_local=True,  # 同时计算LISA
    top_genes=10
)

# 获取结果
moran_df = results['moran']
geary_df = results['geary']
top_clustered = results['top_clustered']  # 最聚集的基因
lisa_results = results['lisa']  # 局部分析结果
```

## 热点检测

### Getis-Ord Gi* 热点分析

**适用场景**: 识别统计显著的高值聚集（热点）或低值聚集（冷点）

```python
from hotspot import compute_getis_ord_gi, comprehensive_hotspot_analysis

# 分析单个基因
hotspots = compute_getis_ord_gi(adata, gene='GeneA', k=6)

# 批量分析多个基因
batch_results = comprehensive_hotspot_analysis(
    adata,
    genes=['GeneA', 'GeneB', 'GeneC'],
    k=6,
    alpha=0.05,
    min_hotspot_spots=5
)

# 获取有显著热点的基因
genes_with_hotspots = batch_results['genes_with_hotspots']
```

**结果分类**:
- Hotspot: 统计显著的高表达聚集
- Coldspot: 统计显著的低表达聚集
- Not significant: 无显著空间模式

## 模式分析

### Co-occurrence 共现分析

**适用场景**: 检验两种细胞类型是否倾向于在空间上邻近

```python
from pattern import compute_cooccurrence, compute_cooccurrence_probability

# 基础共现分析
cooccur = compute_cooccurrence(
    adata,
    cluster_key='cell_type',
    n_neighbors=6,
    method='observed_vs_expected'  # 或 'jaccard'
)

# 带显著性检验
result = compute_cooccurrence_probability(
    adata,
    cluster_key='cell_type',
    n_permutations=100
)

# 查看显著共现
significant = result['is_significant']
z_scores = result['z_scores']
```

**解读**:
- 值 > 1: 共现高于随机期望（吸引）
- 值 < 1: 共现低于随机期望（排斥）
- 值 = 1: 随机共现

### Join Counts 连接计数

**适用场景**: 分类数据的空间自相关分析（细胞类型是否成簇分布）

```python
from pattern import compute_join_counts, interpret_join_counts

jc = compute_join_counts(adata, cluster_key='cell_type', n_neighbors=6)

# 生成解读
interpretation = interpret_join_counts(jc)
print(interpretation)
# - Macrophage shows positive autocorrelation (z=5.23, p<0.001)
# - T_cell shows random distribution (z=0.45, p=0.65)
```

### Ripley's K/L 函数

**适用场景**: 分析不同空间尺度上的聚集/分散模式

```python
from pattern import compute_ripley_k, compute_ripley_l, plot_ripley

# 分析特定细胞类型的空间分布
ripley_k = compute_ripley_k(
    adata,
    cluster_key='cell_type',
    cluster_value='Macrophage',
    n_radii=20
)

# 绘制结果
fig = plot_ripley(ripley_k, metric='L')

# L函数解读:
# L(r) > 0: 在半径r处聚集
# L(r) < 0: 在半径r处分散
# L(r) = 0: 完全空间随机性
```

### Neighborhood Enrichment 邻域富集

**适用场景**: 分析某种细胞的邻域中哪些细胞类型富集

```python
from pattern import compute_neighborhood_enrichment, extract_enrichment_zscores

enrichment = compute_neighborhood_enrichment(
    adata,
    cluster_key='cell_type',
    n_neighbors=6,
    n_permutations=100
)

# 提取z-score矩阵用于热图
z_matrix = extract_enrichment_zscores(enrichment)

# 查看特定细胞类型的邻域偏好
macro_enrichment = enrichment[enrichment['source'] == 'Macrophage']
print(macro_enrichment.nlargest(3, 'enrichment'))
```

## 网络分析

### Centrality 中心性分析

**适用场景**: 识别空间网络中的关键节点

```python
from network import compute_centrality_scores, compute_spatial_centrality

# 基础中心性分析
centrality = compute_centrality_scores(
    adata,
    n_neighbors=6,
    methods=['degree', 'closeness', 'betweenness']
)

# 加权的中心性（结合基因表达）
gene_centrality = compute_spatial_centrality(
    adata,
    gene='GeneA',
    percentile=95  # 识别前5%的关键节点
)

# 获取hub节点
hubs = gene_centrality[gene_centrality['is_hub']]
```

**中心性类型**:
- Degree: 连接数量（局部重要性）
- Closeness: 到其他所有节点的平均距离（全局可达性）
- Betweenness: 作为桥梁的频率（中介作用）

### 网络属性分析

```python
from network import compute_network_properties, analyze_network_structure

# 基础网络属性
props = compute_network_properties(adata, n_neighbors=6)
print(f"Global efficiency: {props['efficiency']['global_efficiency']:.3f}")
print(f"Mean clustering: {props['clustering']['mean']:.3f}")

# 完整网络结构分析
network_analysis = analyze_network_structure(
    adata,
    cluster_key='cell_type',
    n_neighbors=6
)

# 查看细胞类型间的连接模式
interaction_matrix = network_analysis['interaction_matrix']
```

## 区域分析

### Anchor Zones 锚点区域

**适用场景**: 创建以特定细胞类型为中心的距离分层区域

```python
from zones import define_anchor_zones, define_neural_zones

# 基于任意锚点细胞
anchor_mask = adata.obs['cell_type'] == 'Tumor'
zones = define_anchor_zones(
    adata,
    anchor_cells=anchor_mask,
    n_layers=5
)

# 专用于神经侵袭分析
neural_zones = define_neural_zones(
    adata,
    neural_cell_type='Neuron',
    cluster_key='cell_type',
    n_layers=5
)

adata.obs['neural_zone'] = neural_zones['zone_label']
```

### Ro/e 分析

**适用场景**: 量化细胞类型在特定区域/微环境的富集或缺失

```python
from zones import compute_roe, interpret_roe_results, plot_roe_heatmap

# 计算 Ro/e
roe = compute_roe(
    adata,
    cell_type_key='cell_type',
    niche_key='neural_zone'
)

# 解读结果
interpretation = interpret_roe_results(
    roe,
    enrichment_threshold=1.2,
    depletion_threshold=0.8
)

# 可视化
ax = plot_roe_heatmap(roe, title='Cell Type by Neural Zone')
```

**Ro/e 解读**:
- Ro/e > 1.2: 显著富集
- Ro/e = 1: 随机分布
- Ro/e < 0.8: 显著缺失

### 完整区域分析工作流

```python
from zones import analyze_spatial_zones

# 一站式区域分析
results = analyze_spatial_zones(
    adata,
    anchor_cell_type='Neuron',
    zone_type='neural',
    cell_type_key='cell_type',
    n_layers=5
)

# 获取所有结果
zones = results['zones']
composition = results['composition']
roe = results['roe']
significant = results['significant_enrichments']
```

## 完整工作流示例

### 工作流1: 基因空间表达模式分析

> **Note:** `sc.pl.spatial()` was removed in scanpy 1.12+. Use `sq.pl.spatial_scatter()` from squidpy instead.  
> Parameter mapping: `spot_size` → `size`. `alpha_img`, `bw`, and `scale_factor` are not supported in squidpy.
```python
import scanpy as sc
from core_stats import run_autocorrelation_analysis
from hotspot import comprehensive_hotspot_analysis

# 1. 加载数据
adata = sc.read_h5ad('spatial_data.h5ad')

# 2. 运行全局自相关分析
print("Running spatial autocorrelation analysis...")
autocorr = run_autocorrelation_analysis(
    adata,
    genes=None,  # 使用高变基因
    k=6,
    compute_local=True
)

# 3. 分析最聚集的基因
print(f"Top clustered genes: {autocorr['top_clustered'][:5]}")

# 4. 热点检测
print("Running hotspot detection...")
hotspot_results = comprehensive_hotspot_analysis(
    adata,
    genes=autocorr['top_clustered'][:10],
    k=6
)

# 5. 可视化
sq.pl.spatial_scatter(adata, color=autocorr['top_clustered'][0])
```

### 工作流2: 细胞类型共定位分析

```python
from pattern import analyze_spatial_patterns

# 运行完整模式分析
results = analyze_spatial_patterns(
    adata,
    cluster_key='cell_type',
    n_neighbors=6,
    n_permutations=100
)

# 检查共现结果
cooccur = results['cooccurrence']
print(f"Significant co-occurrences: {cooccur['is_significant'].sum().sum()}")

# 检查Join Counts
join_counts = results['join_counts']
print(join_counts[['category', 'autocorrelation']])

# 查看邻域富集
enrichment = results['neighborhood_enrichment']
```

### 工作流3: 神经侵袭微环境分析

```python
from zones import analyze_spatial_zones
import matplotlib.pyplot as plt
import seaborn as sns

# 1. 定义神经区域
results = analyze_spatial_zones(
    adata,
    anchor_cell_type='Neuron',
    zone_type='neural',
    cell_type_key='cell_type',
    n_layers=5
)

# 2. 查看区域组成
composition = results['composition']
print("Cell type composition by zone:")
print(composition)

# 3. Ro/e分析
roe = results['roe']
plt.figure(figsize=(10, 6))
sns.heatmap(roe, annot=True, cmap='RdYlBu_r', center=1)
plt.title('Ro/e: Cell Type Enrichment in Neural Zones')
plt.savefig('roe_heatmap.png', dpi=300)

# 4. 识别显著富集的细胞类型
significant = results['significant_enrichments']
print("Significant enrichments:")
print(significant)
```

## 参数选择指南

### 邻居数 (k) 的选择

| 平台 | 推荐k值 | 理由 |
|------|---------|------|
| Visium | 6 | 六边形网格的自然邻居数 |
| Visium HD | 8 | 高密度数据需要更多邻居 |
| Stereo-seq | 4 | 方形网格的4个直接邻居 |
| Slide-seq | 10+ | 近单细胞分辨率，距离决定 |

```python
from utils import suggest_neighbors, infer_spatial_platform

# 自动推荐
platform = infer_spatial_platform(adata)
recommendation = suggest_neighbors(adata)
print(f"Detected platform: {recommendation['platform']}")
print(f"Recommended k: {recommendation['n_neighbors']}")
```

### 置换检验次数

| 场景 | 推荐置换次数 | 计算时间 |
|------|--------------|----------|
| 快速探索 | 99 | 快 |
| 标准分析 | 999 | 中等 |
| 发表级 | 9999 | 慢 |

## 工具函数

### 数据验证

```python
from utils import validate_spatial_data, check_spatial_neighbors

# 验证数据格式
is_valid = validate_spatial_data(adata, require_raw=False)

# 检查邻居信息
neighbor_info = check_spatial_neighbors(adata, n_neighbors=6)
print(f"Has spatial neighbors: {neighbor_info['has_neighbors']}")
```

### 样本量检查

```python
from utils import check_sample_size

# 检查样本量是否适合特定统计
size_check = check_sample_size(adata, statistic_type='moran')
if not size_check['adequate']:
    print(f"Warning: {size_check['warning']}")
```

## 方法选择决策树

```
开始: 你要分析什么？
    │
    ├─ 基因表达的空间分布
    │   ├─ 整体是否聚集？ → Moran's I
    │   ├─ 具体哪些位置聚集？ → LISA
    │   └─ 高/低表达聚集区域？ → Getis-Ord Gi*
    │
    ├─ 细胞类型的空间关系
    │   ├─ 是否倾向共定位？ → Co-occurrence
    │   ├─ 是否成簇分布？ → Join Counts
    │   ├─ 邻域组成偏好？ → Neighborhood Enrichment
    │   └─ 在哪些尺度聚集？ → Ripley's K/L
    │
    ├─ 空间网络结构
    │   ├─ 关键节点识别？ → Centrality
    │   └─ 整体网络特征？ → Network Properties
    │
    └─ 区域/梯度分析
        ├─ 距离中心的空间梯度？ → Anchor Zones
        └─ 特定区域细胞组成？ → Ro/e Analysis
```

## 详细使用场景

详见 [STATISTICS_USAGE_GUIDE.md](STATISTICS_USAGE_GUIDE.md) 了解各统计方法的详细使用场景、数学原理和最佳实践。

## 代码实现

所有函数实现位于 `scripts/python/` 目录：

| 模块 | 文件 | 主要功能 |
|------|------|----------|
| core_stats | `core_stats.py` | Moran's I, Geary's C, LISA, Bivariate Moran |
| hotspot | `hotspot.py` | Getis-Ord Gi*, 批量热点检测 |
| pattern | `pattern.py` | Co-occurrence, Join Counts, Ripley's K/L, Neighborhood Enrichment |
| network | `network.py` | Centrality, Network Properties, Interaction Matrix |
| zones | `zones.py` | Anchor Zones, Ro/e, Niche Enrichment |
| utils | `utils.py` | 数据验证, 平台推断, 样本量检查 |

## 错误排查

### 常见问题

**ImportError: No module named 'libpysal'**
```bash
pip install libpysal esda pointpats networkx