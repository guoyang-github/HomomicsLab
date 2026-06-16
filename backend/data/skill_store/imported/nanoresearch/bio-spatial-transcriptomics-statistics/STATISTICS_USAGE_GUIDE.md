# 空间统计指标使用场景详解

## 使用指南导航

```
你的研究问题是什么？
│
├── 基因表达是否有空间模式？
│   ├── 想看整体模式 → Moran's I / Geary's C
│   ├── 想看局部热点 → Getis-Ord Gi* / LISA
│   └── 想看基因间空间关联 → Bivariate Moran
│
├── 细胞类型如何空间分布？
│   ├── 是否随机分布？ → Join Counts
│   ├── 哪些类型共定位？ → Co-occurrence
│   └── 邻居关系如何？ → Neighborhood Enrichment
│
├── 组织结构特征是什么？
│   ├── 关键位置在哪里？ → Centrality Analysis
│   └── 网络拓扑如何？ → Network Properties
│
├── 特定区域有何特征？
│   ├── 围绕标志物的梯度 → Anchor Zone Analysis
│   └── 微环境组成 → Ro/e + Niche Enrichment
│
└── 点模式特征（单细胞）
    └── 聚类/分散/随机 → Ripley's K/L
```

---

## A. 核心自相关统计 (Core Autocorrelation)

### A1. Moran's I - 全局空间自相关

**🔬 核心用途**
检测基因表达在整个组织中是否存在空间聚集模式（高值聚类在一起，低值聚类在一起）

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **验证基因的空间表达** | "CD19在淋巴滤泡中是否真的空间聚集？" |
| **筛选空间变异基因** | 从30000个基因中找出1000个有空间模式的 |
| **比较不同条件** | "肿瘤vs正常组织中，VEGF的空间聚集程度是否不同？" |
| **质量控制** | 检测技术批次效应导致的空间梯度 |

**📝 输入要求**
- **表达矩阵**: 归一化后的连续数据（log1p转换）
- **空间坐标**: 每个spot/cell的x,y坐标
- **邻居关系**: 预先构建的空间邻接图（k=6常用）

**📈 结果解读**

| I值 | Z-score | P值 | 解释 |
|-----|---------|-----|------|
| +0.5~+1.0 | >2 | <0.05 | **强聚集** (高值聚类，低值聚类) |
| +0.1~+0.5 | 1~2 | 0.05~0.1 | **弱聚集** |
| ~0 | ~0 | >0.1 | **随机分布** |
| -0.1~-0.5 | <-1 | 0.05~0.1 | **弱分散** |
| -0.5~-1.0 | <-2 | <0.05 | **强分散** (高值被低值包围) |

**⚠️ 常见误区**
1. **混淆I值的含义**: I>0是聚集，I<0是分散，不是"好"或"坏"
2. **忽略Z-score**: 小样本时I值可能高但不显著，必须看p值
3. **全局vs局部**: Moran's I是全局统计，不能告诉你"哪里"聚集

**💡 最佳实践**
> **Note:** `sc.pl.spatial()` was removed in scanpy 1.12+. Use `sq.pl.spatial_scatter()` from squidpy instead.  
> Parameter mapping: `spot_size` → `size`. `alpha_img`, `bw`, and `scale_factor` are not supported in squidpy.
```python
# 批量筛选空间变异基因
results = compute_morans_i(adata, genes=adata.var_names, k=6)
sig_genes = results[results['p_value'] < 0.05].sort_values('I', ascending=False)

# 可视化top基因的空间分布
top_gene = sig_genes.index[0]
sq.pl.spatial_scatter(adata, color=top_gene)
```

---

### A2. Geary's C - 全局空间差异

**🔬 核心用途**
Moran's I的互补统计量，聚焦于局部差异（邻居之间是否相似）

**📊 与Moran's I的区别**

| 特性 | Moran's I | Geary's C |
|------|-----------|-----------|
| **敏感点** | 极端值的聚集 | 局部差异 |
| **数值含义** | I>0聚集, I<0分散 | C<1聚集, C>1分散, C=1随机 |
| **计算方式** | 协方差形式 | 差异平方和 |
| **适用** | 大范围模式 | 局部精细结构 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **检测边界基因** | 在组织边界处表达剧烈变化的基因 |
| **比较模式类型** | 同样I值的基因，C值不同表示不同的局部结构 |
| **小范围变异** | 短距离内的表达波动 |

**📈 结果解读**

| C值 | 解释 |
|-----|------|
| 0~0.5 | **强聚集** (邻居高度相似) |
| 0.5~1.0 | **弱聚集** |
| ~1.0 | **随机** (邻居不相关) |
| 1.0~1.5 | **弱分散** |
| 1.5~2.0 | **强分散** (邻居高度不同) |

**💡 联合使用Moran's I和Geary's C**
```python
# 同时计算两个统计量
moran = compute_morans_i(adata, genes=['GeneA'], k=6)
geary = compute_gearys_c(adata, genes=['GeneA'], k=6)

# 解释组合
if moran['I'] > 0.5 and geary['C'] < 0.5:
    print("强聚集模式，邻居高度相似")
elif moran['I'] > 0.5 and geary['C'] > 1.0:
    print("聚集但内部有差异（可能有亚结构）")
```

---

### A3. LISA (Local Moran's I) - 局部空间自相关

**🔬 核心用途**
识别具体哪些spots属于空间集群（回答"哪里"的问题）

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **精确定位表达域** | "IL2基因高表达的spots具体在哪里？" |
| **识别异常spots** | 找出表达模式与邻居不符的异常点 |
| **空间聚类验证** | 验证聚类算法得到的空间cluster是否真实 |
| **绘制热点地图** | 生成HH/HL/LH/LL分类图 |

**📈 四象限解释 (LISA Clusters)**

| 类型 | 含义 | 生物学意义 |
|------|------|-----------|
| **HH (High-High)** | 高值spot被高值邻居包围 | **热点核心区** - 基因高表达区域 |
| **LL (Low-Low)** | 低值spot被低值邻居包围 | **冷点核心区** - 基因低表达区域 |
| **HL (High-Low)** | 高值spot被低值邻居包围 | **异常高值** - 可能边界点或异常 |
| **LH (Low-High)** | 低值spot被高值邻居包围 | **异常低值** - 可能空洞或抑制区 |
| **NS (Not Significant)** | 无显著空间关联 | 随机分布区域 |

**💡 典型应用：肿瘤微环境**
```python
# 分析免疫检查点基因的空间分布
lisa_results = compute_lisa(adata, gene='PD-L1', k=6)

# 标记HH spots为"PD-L1热点"
adata.obs['PDL1_hotspot'] = lisa_results['quadrant'] == 'HH'

# 分析热点区域的细胞组成
hotspot_cells = adata[adata.obs['PDL1_hotspot']].obs['cell_type'].value_counts()
print("PD-L1热点主要由以下细胞组成：", hotspot_cells)
```

---

### A4. Bivariate Moran's I - 双变量空间相关

**🔬 核心用途**
检测两个基因在空间上是否协同表达（一个基因高表达的地方，另一个也高表达）

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **配体-受体空间共表达** | "CXCL12在哪里表达，其受体CXCR4是否也在那里？" |
| **通路基因协同** | "缺氧通路中的多个基因是否空间共表达？" |
| **标记基因组合** | "CD4和FOXP3是否空间共定位（Treg细胞）？" |
| **空间调控验证** | "转录因子与其靶基因的空间关系" |

**📈 结果解读**

| I值 | 解释 |
|-----|------|
| +0.5~+1.0 | **强正空间相关** - 两基因共定位 |
| +0.1~+0.5 | **弱正相关** |
| ~0 | **无空间相关** |
| -0.1~-0.5 | **弱负相关** |
| -0.5~-1.0 | **强负相关** - 互斥分布 |

**💡 应用：配体-受体验证**
```python
# 检查配体-受体对的空间共定位
pairs = [('CXCL12', 'CXCR4'), ('TGFB1', 'TGFBR1'), ('IL2', 'IL2RA')]

for ligand, receptor in pairs:
    result = compute_bivariate_moran(adata, ligand, receptor, k=6)
    print(f"{ligand}-{receptor}: I={result['I']:.2f}, p={result['p_value']:.3f}")
    
# 筛选显著共定位的LR对
sig_pairs = [(l, r) for l, r in pairs 
             if compute_bivariate_moran(adata, l, r)['p_value'] < 0.05]
```

---

## B. 热点检测 (Hotspot Detection)

### B1. Getis-Ord Gi* - 热点/冷点识别

**🔬 核心用途**
识别统计显著的高值聚集区（热点）和低值聚集区（冷点）

**📊 与LISA的区别**

| 特性 | Getis-Ord Gi* | LISA |
|------|---------------|------|
| **输出** | Z-score（标准分数） | I值 + 象限分类 |
| **解释** | 热点/冷点的强度 | 聚类类型 |
| **可视化** | 连续z-score地图 | 离散分类地图 |
| **适用** | 识别显著热点区域 | 理解空间关系 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **寻找治疗靶点区域** | "肿瘤中PD-1表达最高的区域在哪里？" |
| **识别功能区域** | "海马体中神经元标记基因的热点区" |
| **质量控制** | "技术噪声导致的人工热点" |
| **空间域定义** | 基于热点边界定义组织区域 |

**📈 Z-score阈值解释**

| Z-score | P值 | 分类 | 颜色建议 |
|---------|-----|------|----------|
| >2.58 | <0.01 | **99%置信热点** | 深红 |
| 1.96~2.58 | 0.01~0.05 | **95%置信热点** | 浅红 |
| -1.96~1.96 | >0.05 | 不显著 | 灰色 |
| -2.58~-1.96 | 0.01~0.05 | **95%置信冷点** | 浅蓝 |
| <-2.58 | <0.01 | **99%置信冷点** | 深蓝 |

**💡 应用：肿瘤微环境分区**
```python
# 分析免疫检查点的空间热点
genes = ['PDCD1', 'CD274', 'CTLA4']  # PD-1, PD-L1, CTLA-4

for gene in genes:
    gi = compute_getis_ord_gi(adata, gene, k=6)
    adata.obs[f'{gene}_hotspot'] = gi['z_scores'] > 1.96

# 找出所有三个基因都是热点的区域（免疫热点）
adata.obs['immune_hotspot'] = (
    adata.obs['PDCD1_hotspot'] & 
    adata.obs['CD274_hotspot'] & 
    adata.obs['CTLA4_hotspot']
)
```

---

## C. 模式分析 (Pattern Analysis)

### C1. Join Count Statistics - 连接计数

**🔬 核心用途**
检验分类变量（如细胞类型、聚类标签）是否随机分布，还是呈现聚集或分散模式

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **细胞类型空间分布** | "T细胞是随机分布还是形成集群？" |
| **聚类验证** | "空间聚类是否真实存在（非随机）？" |
| **生态位分析** | "特定细胞类型是否占据特定生态位？" |
| **边界检测** | "细胞类型在组织边界处是否聚集？" |

**📈 输出解读**

| 计数类型 | 含义 | 随机期望 | 实际>期望 | 实际<期望 |
|----------|------|----------|-----------|-----------|
| **BB** | 相同标签相邻 | n×p² | **聚集** | 分散 |
| **WW** | 不同标签间相同 | - | - | - |
| **BW** | 不同标签相邻 | 2n×p×(1-p) | 混合良好 | **空间分离** |

**💡 应用：肿瘤-免疫边界分析**
```python
# 定义肿瘤vs非肿瘤标签
adata.obs['tumor_region'] = ['Tumor' if x == 'Tumor' else 'Non-tumor' 
                             for x in adata.obs['cell_type']]

# 计算Join Counts
jc = compute_join_counts(adata, 'tumor_region', k=6)

# 解释
if jc['BW'] < jc['BW_expected']:
    print("肿瘤和非肿瘤区域空间分离（有清晰边界）")
else:
    print("肿瘤和非肿瘤区域混合（浸润型）")
```

---

### C2. Co-occurrence Analysis - 共现分析

**🔬 核心用途**
量化细胞类型对之间的空间共现概率（是否倾向于待在一起）

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **细胞互作预测** | "哪些细胞类型经常相邻？可能是互作伙伴" |
| **微环境定义** | "肿瘤相关巨噬细胞常与哪些细胞共现？" |
| **空间niche发现** | "通过共现模式发现未知的细胞社群" |
| **发育过程** | "发育中细胞类型的空间组装过程" |

**📈 概率矩阵解读**

矩阵值P(i,j)表示：给定一个类型i的spot，其邻居是类型j的概率

| 值 | 解释 |
|----|------|
| >1.5×随机期望 | **显著共现** - 强烈倾向于共定位 |
| 0.8~1.2×期望 | **随机** - 无特殊关联 |
| <0.5×期望 | **互斥** - 避免相邻 |

**💡 应用：发现细胞互作网络**
```python
# 计算细胞类型共现
cooccur = compute_cooccurrence(adata, 'cell_type')

# 找出显著共现的细胞对
import itertools
cell_types = adata.obs['cell_type'].unique()
interactions = []

for ct1, ct2 in itertools.combinations(cell_types, 2):
    prob = cooccur.loc[ct1, ct2]
    expected = cooccur.loc['expected', ct2]
    if prob > 1.5 * expected:
        interactions.append((ct1, ct2, prob/expected))

# 可视化共现网络
import networkx as nx
G = nx.Graph()
for ct1, ct2, strength in interactions:
    G.add_edge(ct1, ct2, weight=strength)

nx.draw(G, with_labels=True)
```

---

### C3. Neighborhood Enrichment - 邻域富集

**🔬 核心用途**
统计检验哪些细胞类型倾向于成为彼此的邻居（置换检验）

**📊 与Co-occurrence的区别**

| 特性 | Co-occurrence | Neighborhood Enrichment |
|------|---------------|------------------------|
| **方法** | 概率计算 | 置换检验 |
| **输出** | 概率矩阵 | Z-score矩阵 |
| **显著性** | 无内置 | P值校正 |
| **优势** | 直观理解 | 统计严谨 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **严谨统计检验** | 发表级别的细胞相邻显著性检验 |
| **多重比较校正** | 同时检验多种细胞类型对 |
| **复杂组织** | 细胞类型很多的组织 |

**📈 Z-score解读**

| Z-score | P值 | 解释 |
|---------|-----|------|
| >3 | <0.001 | **极强富集** |
| 2~3 | 0.01~0.05 | **显著富集** |
| -2~2 | >0.05 | 随机 |
| <-2 | <0.05 | **显著避免** |

---

### C4. Ripley's K/L Statistics - 点模式分析

**🔬 核心用途**
分析点数据（如细胞位置）的空间分布模式：聚类、随机还是规则分布

**📊 K函数 vs L函数**

| 函数 | 公式 | 解释 |
|------|------|------|
| **K(r)** | K(r) = λ⁻¹E | 距离r内的邻居数期望 |
| **L(r)** | L(r) = √(K(r)/π) | K的方差稳定变换，更易解释 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **单细胞分辨率** | 细胞中心点的空间分布 |
| **细胞核定位** | DAPI+细胞核的空间模式 |
| **特定细胞类型** | "Treg细胞是聚类还是分散？" |
| **多尺度分析** | 不同距离下的模式变化 |

**📈 L(r)曲线解读**

| L(r) vs r | 模式 | 生物学意义 |
|-----------|------|-----------|
| L(r) > r | **聚类** | 细胞形成集群 |
| L(r) = r | **随机** | 泊松过程 |
| L(r) < r | **规则/分散** | 细胞互相排斥 |

**💡 距离r的选择**
- 小r (~10-50μm): 细胞-细胞相互作用距离
- 中r (~100μm): 局部微环境尺度
- 大r (~500μm): 组织结构尺度

**💡 应用：肿瘤浸润分析**
```python
# 分析T细胞在肿瘤中的分布模式
from pattern import compute_ripley_l

# 提取T细胞位置
t_cell_mask = adata.obs['cell_type'].str.contains('T_cell')
t_cell_adata = adata[t_cell_mask]

# 计算Ripley's L
ripley = compute_ripley_l(t_cell_adata, distances=np.linspace(0, 500, 50))

# 判断模式
if np.any(ripley['L'] > ripley['r'] * 1.2):
    print("T细胞在肿瘤中呈聚类分布（可能形成淋巴聚集体）")
else:
    print("T细胞随机或分散分布（均匀浸润）")
```

---

## D. 网络分析 (Network Analysis)

### D1. Centrality Analysis - 中心性分析

**🔬 核心用途**
识别组织中的"关键位置"——连接枢纽、结构桥、或易于到达的区域

**📊 三种中心性的区别**

| 中心性 | 测量什么 | 生物学解释 |
|--------|----------|-----------|
| **Degree** | 邻居数量 | 局部连接度（拥挤度） |
| **Closeness** | 到所有其他点的最短路径倒数 | 全局可达性（中心位置） |
| **Betweenness** | 经过该点的最短路径比例 | 桥接作用（连接不同区域） |

**📊 适用场景**

| 中心性 | 应用场景 |
|--------|----------|
| **Degree** | 找到最"拥挤"的区域；识别细胞密集区 |
| **Closeness** | 找到组织中心；代谢物质易到达区 |
| **Betweenness** | 找到结构桥；组织过渡区；潜在信号传递枢纽 |

**💡 应用：组织结构分析**
```python
from network import compute_spatial_centrality

# 计算所有中心性
centrality = compute_spatial_centrality(adata, n_neighbors=6)

# 找出结构桥（高betweenness）
bridge_spots = centrality['betweenness'] > np.percentile(centrality['betweenness'], 95)
adata.obs['is_bridge'] = bridge_spots

# 分析桥接区域的基因表达特征
bridge_genes = adata[adata.obs['is_bridge']].X.mean(axis=0)
print("桥接区域高表达的基因：", adata.var_names[bridge_genes > np.percentile(bridge_genes, 90)])
```

---

### D2. Network Properties - 网络属性

**🔬 核心用途**
从整体角度分析组织空间网络的拓扑特征

**📊 网络指标解读**

| 指标 | 含义 | 高值解释 | 低值解释 |
|------|------|----------|----------|
| **密度** | 实际边数/可能边数 | 组织紧密连接 | 组织松散 |
| **聚类系数** | 邻居间相互连接程度 | 局部团簇结构 | 星型结构 |
| **效率** | 信息传输效率 | 快速信号传导 | 信号传递慢 |
| **模块化** | 社区结构强度 | 明显功能分区 | 均匀混合 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **组织结构比较** | "健康vs疾病组织的网络结构差异" |
| **发育研究** | "组织发育过程中的网络演化" |
| **治疗响应** | "治疗后组织结构的网络变化" |

---

## E. 区域分析 (Zone Analysis)

### E1. Anchor Proximity Zones - 锚点邻近区域

**🔬 核心用途**
围绕特定组织标志物（如肿瘤边界、神经核团）定义同心圆区域，分析梯度变化

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **肿瘤微环境** | 定义肿瘤核心-边缘-正常区域 |
| **神经解剖** | 围绕特定神经核团的同心层 |
| **血管周围** | 分析血管周围的细胞组成梯度 |
| **发育区域** | 围绕发育信号源的梯度 |

**📈 区域命名建议**

| 距离范围 | 命名 | 生物学意义 |
|----------|------|-----------|
| 0-50μm | **Core/Intra** | 锚点核心区 |
| 50-150μm | **Juxta/Peri** | 紧邻区域（细胞间互作） |
| 150-300μm | **Proximal** | 近端区域（旁分泌影响） |
| 300-500μm | **Distal** | 远端区域（内分泌影响） |
| >500μm | **Remote** | 远端对照 |

**💡 应用：肿瘤侵袭前沿分析**
```python
from zones import define_anchor_zones, analyze_zone_composition

# 定义肿瘤边缘
# 假设肿瘤spots已知
tumor_spots = adata.obs['cell_type'] == 'Tumor'

# 创建5层同心区域
zones = define_anchor_zones(
    adata,
    anchor_cells=tumor_spots,
    n_layers=5,
    max_distance=500
)

# 分析各区域的免疫细胞组成
composition = analyze_zone_composition(adata, zones, cell_type_key='cell_type')

# 绘制梯度图
import matplotlib.pyplot as plt
plt.plot(composition['distance'], composition['T_cell_ratio'])
plt.xlabel('Distance from tumor (μm)')
plt.ylabel('T cell proportion')
plt.title('T cell infiltration gradient')
```

---

### E2. Ro/e Analysis - 观测/期望比

**🔬 核心用途**
量化细胞类型在特定微环境中的富集程度（相对于随机分布的期望）

**📊 公式解释**
```
Ro/e = (观测到的细胞数) / (期望的细胞数)

期望 = (niche中的总细胞数) × (该细胞类型在整体中的比例)
```

**📈 解读标准**

| Ro/e | 解释 | 生物学意义 |
|------|------|-----------|
| >2.0 | **显著富集** | 该细胞类型偏好此微环境 |
| 1.5~2.0 | **中度富集** | 有一定偏好 |
| 0.8~1.2 | **随机** | 无特殊偏好 |
| 0.5~0.8 | **中度耗竭** | 倾向于避开 |
| <0.5 | **显著耗竭** | 避免此微环境 |

**📊 适用场景**

| 场景 | 示例 |
|------|------|
| **微环境定义** | "哪种细胞类型定义了炎症niche？" |
| **细胞定位** | "Treg细胞在哪个niche富集？" |
| **条件比较** | "疾病vs健康时，细胞定位如何改变？" |

**💡 应用：肿瘤免疫微环境**
```python
from zones import compute_roe, plot_roe_heatmap

# 假设已有niche定义（如基于聚类或空间域）
roe = compute_roe(adata, cell_type_key='cell_type', niche_key='spatial_niche')

# 找出每个niche的特征细胞类型
for niche in roe.columns:
    top_cells = roe[niche][roe[niche] > 2.0].sort_values(ascending=False)
    print(f"{niche}的特征细胞：", top_cells.index.tolist())

# 热图可视化
plot_roe_heatmap(roe, threshold=1.5)
```

---

## F. 方法选择决策树

```
开始：你的数据是什么类型？
│
├── 连续变量（基因表达）
│   ├── 想看整体模式？
│   │   └── Moran's I / Geary's C
│   ├── 想看哪里是热点？
│   │   └── Getis-Ord Gi* / LISA
│   └── 想看基因间关系？
│       └── Bivariate Moran
│
├── 分类变量（细胞类型/聚类）
│   ├── 是否随机分布？
│   │   └── Join Counts
│   ├── 哪些类型在一起？
│   │   └── Co-occurrence / Neighborhood Enrichment
│   └── 点模式（单细胞）？
│       └── Ripley's K/L
│
├── 网络/结构
│   ├── 关键位置？
│   │   └── Centrality (Degree/Closeness/Betweenness)
│   └── 整体结构？
│       └── Network Properties
│
└── 区域/梯度
    ├── 围绕标志物？
    │   └── Anchor Zones
    └── 微环境组成？
        └── Ro/e + Niche Enrichment
```

---

## G. 常见组合分析流程

### G1. 空间变异基因发现流程
```python
# Step 1: Moran's I筛选全局空间变异基因
moran_results = compute_morans_i(adata, genes=adata.var_names, k=6)
svg_candidates = moran_results[moran_results['p_value'] < 0.05].index

# Step 2: Getis-Ord Gi*确定热点位置
for gene in svg_candidates[:10]:
    gi = compute_getis_ord_gi(adata, gene, k=6)
    adata.obs[f'{gene}_hotspot'] = gi['z_scores'] > 1.96

# Step 3: LISA分类每个spot的类型
for gene in svg_candidates[:10]:
    lisa = compute_lisa(adata, gene, k=6)
    adata.obs[f'{gene}_cluster'] = lisa['quadrant']
```

### G2. 肿瘤微环境分析流程
```python
# Step 1: 定义肿瘤区域
# ... 根据marker基因或其他方法定义 ...

# Step 2: 创建距离区域
zones = define_anchor_zones(adata, tumor_spots, n_layers=5)

# Step 3: Ro/e分析各区域的细胞组成
roe = compute_roe(adata, 'cell_type', zones)

# Step 4: 共现分析发现互作
from pattern import compute_cooccurrence
cooccur = compute_cooccurrence(adata, 'cell_type')

# Step 5: 邻域富集验证
from pattern import compute_neighborhood_enrichment
enrich = compute_neighborhood_enrichment(adata, 'cell_type')
```

### G3. 组织结构分析流程
```python
# Step 1: 网络属性整体评估
from network import compute_network_properties
props = compute_network_properties(adata, n_neighbors=6)

# Step 2: 中心性找到关键位置
from network import compute_spatial_centrality
centrality = compute_spatial_centrality(adata, n_neighbors=6)

# Step 3: 热点分析功能区域
from hotspot import compute_getis_ord_gi
hotspots = compute_getis_ord_gi(adata, gene='Structural_Marker', k=6)

# Step 4: Join Counts验证聚类
from pattern import compute_join_counts
jc = compute_join_counts(adata, 'cell_type', k=6)
```

---

## H. 注意事项与最佳实践

### H1. 邻居数k的选择

| 平台 | 推荐k | 原因 |
|------|-------|------|
| Visium | 6 | 六边形网格的自然邻居 |
| Visium HD | 8-12 | 更高分辨率需要更多邻居 |
| Stereo-seq | 4-8 | 正方形网格 |
| Slide-seq | 5-10 | 近单细胞，基于距离 |
| MERFISH | 5-15 | 基于距离而非网格 |

### H2. 多重检验校正

当同时检验多个基因或细胞类型时，必须进行多重检验校正：

```python
from statsmodels.stats.multitest import multipletests

# 对p值进行FDR校正
p_values = results['p_value'].values
reject, p_adj, _, _ = multipletests(p_values, method='fdr_bh', alpha=0.05)
results['p_adjusted'] = p_adj
```

### H3. 常见错误

1. **在归一化前计算**：必须使用log-normalized数据
2. **忽略平台差异**：不同平台的空间分辨率不同
3. **k值过大**：会平滑掉局部模式
4. **样本量过小**：n<30时结果不可靠
5. **混淆相关性**：空间相关≠生物学相关，需验证

---

**文档版本**: 1.0  
**最后更新**: 2026-04-07
