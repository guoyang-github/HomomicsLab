# LIANA+ Usage Guide

> **本文档 vs SKILL.md**：`SKILL.md` 是给 AI Agent 看的操作指令（告诉 AI 怎么生成代码），本文档是给人类看的教程（告诉你这个分析是什么、怎么跑、结果怎么看）。做分析时看本文档，让 AI 帮你写代码时看 SKILL.md。

---

## 这个分析到底在算什么？

### 细胞通讯分析的本质

你身体里的细胞不是孤立存在的，它们通过**信号分子**互相说话。比如 T 细胞要攻击肿瘤细胞，需要先收到肿瘤细胞释放的某种信号；肿瘤细胞要逃避免疫，也会释放抑制信号。

这些信号的基本单元叫做**配体-受体对（Ligand-Receptor pair）**：
- **配体（Ligand）**：发送信号的细胞表面或分泌出来的蛋白（比如 TGFB1）
- **受体（Receptor）**：接收信号的靶细胞表面的蛋白（比如 TGFBR1）

LIANA+ 做的事情就是：**扫描你数据里所有已知的配体-受体对，统计哪些细胞类型之间可能存在信号传递。**

### 单细胞 vs 空间数据的区别

| 数据类型 | LIANA+ 能回答什么 | 关键区别 |
|----------|------------------|---------|
| **单细胞转录组（scRNA-seq）** | "A 类细胞表达配体，B 类细胞表达受体，它们**理论上**可以通讯" | 只算基因表达，不考虑物理距离 |
| **空间转录组（Visium/Xenium 等）** | "A 类细胞和 B 类细胞在组织切片上**确实靠得近**，而且配体/受体在空间上**协同表达**" | 加入了空间位置信息 |

**核心差异**：单细胞数据告诉你"谁有话筒、谁有收音机"，空间数据还能告诉你"它们是不是真的站在彼此能听到的距离里"。

### LIANA+ 的核心思路

LIANA+ 不是"一个方法"，而是"多个方法的集合 + 投票机制"：

1. 它内置了 8 种独立的通讯推断方法（CellPhoneDB、NATMI、CellChat 等）
2. 每种方法算出的"这个通讯通路有多强"都不一样
3. **Rank Aggregate（推荐默认）**把这 8 种方法的结果综合起来，取共识排名

这样比单一方法更稳健——某个方法的假阳性/假阴性可以被其他方法对冲掉。

---

## 你的数据准备好了吗？

### 单细胞数据（scRNA-seq）

**必需条件**：
- [ ] 一个 AnnData 对象（`adata`），已经过质控、归一化、对数变换
- [ ] `adata.obs` 里有细胞类型注释列（比如 `cell_type`）
- [ ] 每个细胞类型至少有 5 个细胞（推荐 10 个以上）
- [ ] 基因名为标准 symbol（如 `TGFB1`，不是 Ensembl ID）

**推荐但不必需**：
- 已经做完聚类和注释，细胞类型命名清晰
- 如果是人鼠跨物种分析，确保基因名和数据库物种一致

**数据长什么样**（示意）：

```
adata
├── .X                  # 表达矩阵 (n_cells x n_genes)，已归一化/对数变换
├── .obs
│   ├── cell_type       # 必须：细胞类型，如 "T_cell", "Macrophage"
│   ├── condition       # 可选：分组信息，如 "control", "tumor"
│   └── sample_id       # 可选：样本 ID，用于跨样本比较
├── .var
│   └── gene_symbol     # 基因名，如 "TGFB1"
└── .uns                # 分析结果会存在这里
```

### 空间转录组数据

**普通 Visium（spot-based）**：
- [ ] 和单细胞一样的基本要求
- [ ] `adata.obsm['spatial']` 包含空间坐标（2列：x, y）
- [ ] **强烈建议**：做过去卷积（cell2location / RCTD / SPOTlight），得到每个 spot 的细胞类型比例
- [ ] 如果没有去卷积，可以用聚类标签代替，但结果会粗糙很多

**单细胞分辨率（Xenium / CosMx / MERFISH）**：
- [ ] 和单细胞一样的基本要求
- [ ] `adata.obsm['spatial']` 包含空间坐标
- [ ] 每个 spot/cell 有明确的细胞类型注释

**数据长什么样**（Visium 示意）：

```
adata
├── .X                  # spot x gene 表达矩阵
├── .obs
│   ├── cell_type       # 必须（或去卷积得到的 dominant cell type）
│   └── array_row/array_col  # Visium 自带的位置信息
├── .obsm
│   └── spatial         # 必须：numpy array, shape (n_spots, 2), 列顺序 [x, y]
└── .uns
```

**检查空间坐标是否存在**：
```python
print(adata.obsm.keys())           # 应该包含 'spatial'
print(adata.obsm['spatial'].shape) # (n_spots, 2)
print(adata.obsm['spatial'][:3])   # 前3个spot的坐标
```

### 数据检查清单（运行前必做）

```python
from scripts.python.utils import validate_anndata  # 本技能 wrapper

# 基础检查
validate_anndata(adata, groupby='cell_type')

# 细胞类型数量检查
print(adata.obs['cell_type'].value_counts())
# 如果有细胞类型 < 5 个，建议合并或移除

# 如果是空间数据，检查坐标
if 'spatial' in adata.obsm:
    print(f"Spatial coords shape: {adata.obsm['spatial'].shape}")
    # 检查是否有 NaN
    assert not pd.isna(adata.obsm['spatial']).any(), "空间坐标有缺失值"

# 检查基因名格式
print(adata.var_names[:10])  # 应该是 TGFB1, TGFBR1 这种格式
```

---

## 分析流程概览

```
[数据准备] ──→ [基础CCC分析] ──→ [空间分析(如适用)] ──→ [结果解读] ──→ [可视化/导出]
     │                │                  │
     │                │                  ├─ Visium → bivariate / global specificity
     │                │                  └─ Xenium → inflow / MISTy
     │                │
     │                └─ rank_aggregate (推荐) 或 单个方法
     │
     └─ 质控、注释、检查 cell_type / spatial 坐标
```

---

## 详细步骤

### 步骤 1：数据准备

```python
import scanpy as sc
from scripts.python.utils import validate_anndata, filter_cell_types  # 本技能 wrapper

# 加载数据
adata = sc.read_h5ad("your_data.h5ad")

# 基础验证
validate_anndata(adata, groupby='cell_type')

# 查看细胞类型分布
print(adata.obs['cell_type'].value_counts())

# 过滤细胞数过少的类型（可选但推荐）
adata = filter_cell_types(adata, min_cells=10, min_expr_genes=50)
```

**什么时候需要过滤？**
- 某个细胞类型只有 1-2 个细胞 → 必然无法做统计，需要合并到上级类别或移除
- 数据质控后发现大量低质量细胞 → 先过滤再分析

---

### 步骤 2：运行 Rank Aggregate（推荐默认）

这是绝大多数情况下的首选方法。它同时运行 4 种基础方法（CellPhoneDB、NATMI、Connectome、SingleCellSignalR），然后取共识排名。

```python
from scripts.python.core_analysis import run_rank_aggregate  # 本技能 wrapper

run_rank_aggregate(
    adata,
    groupby='cell_type',           # 你的细胞类型列名
    resource_name='consensus',     # 配体-受体数据库 (run ln.rs.show_resources() to list)
    expr_prop=0.1,                 # 表达比例阈值
    min_cells=5,                   # 每组最少细胞数
    aggregate_method='rra',        # 共识方法：rra（推荐）或 mean
    n_perms=100,                   # 置换检验次数
    seed=42,
    key_added='liana_res',         # 结果存储位置
    inplace=True,
    verbose=True
)

# 查看结果
results = adata.uns['liana_res']
print(f"发现 {len(results)} 条相互作用")
print(results.head())
```

**参数选择建议**：

| 参数 | 默认值 | 调大/调小的影响 |
|------|--------|----------------|
| `expr_prop` | 0.1 | 调大（0.2）→ 更严格，结果更少但更可信；调小（0.05）→ 更宽松，探索性分析 |
| `min_cells` | 5 | 调大 → 过滤小群体，减少噪声；调小 → 保留稀有细胞类型的信号 |
| `n_perms` | 100 | 调大（1000）→ 统计更可靠但慢；调小（10）→ 快速测试 |
| `resource_name` | consensus | 人用数据默认 consensus 即可；小鼠数据用 MouseConsensus |

---

### 步骤 3：探索结果

```python
from scripts.python.core_analysis import get_top_interactions  # 本技能 wrapper

# 看总体最强的20条
top20 = get_top_interactions(results, n=20, by='magnitude_rank')
print(top20[['source', 'target', 'ligand', 'receptor', 'magnitude_rank']])

# 只看特定细胞类型之间的通讯
macro_to_t = get_top_interactions(
    results,
    source_cells=['Macrophage'],
    target_cells=['T_cell'],
    n=10
)

# 看特定信号通路
tgfb = get_top_interactions(
    results,
    ligand='TGFB1',
    receptor='TGFBR1'
)
```

---

### 步骤 4：运行单个方法（可选）

如果你想看看不同方法的结果差异：

```python
from scripts.python.core_analysis import run_individual_method  # 本技能 wrapper

methods = ['cellphonedb', 'cellchat', 'connectome', 'natmi']
for method in methods:
    run_individual_method(
        adata,
        method=method,
        groupby='cell_type',
        resource_name='consensus',
        key_added=f'liana_{method}'
    )

# 找所有方法都检测到的交集
common = set(adata.uns['liana_cellphonedb']['interaction_key'])
for m in methods[1:]:
    common &= set(adata.uns[f'liana_{m}']['interaction_key'])
print(f"共识相互作用：{len(common)} 条")
```

**什么情况下需要跑单个方法？**
- 审稿人要求展示方法稳健性
- 某个方法的结果和预期不符，想排查是不是方法本身的问题
- 对特定统计框架有偏好（比如只信置换检验就用 CellPhoneDB）

---

### 步骤 5：空间分析

**所有空间 CCC 分析的前置步骤**：必须先计算空间邻居图。

```python
import squidpy as sq
import liana as ln

# Visium（六边形网格）
sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)

# 单细胞分辨率（Delaunay）
ln.ut.spatial_neighbors(adata, bandwidth=50, spatial_key='spatial')
```

#### 5A. Visium — Bivariate 分析

计算所有已知配体-受体对的空间共表达指标（Moran's I, Lee's L 等）。

```python
import liana as ln

# bivariate() 返回新的 AnnData，不修改原 adata
lrdata = ln.method.bivariate(
    adata,
    local_name='morans',           # 局部指标
    global_name=['morans', 'lee'], # 全局指标
    resource_name='consensus',
    connectivity_key='spatial_connectivities',
    n_perms=100,
    use_raw=True  # use adata.raw if present; set False to use adata.X
)

# 结果存储在返回的 lrdata 中：
# lrdata.X               : 每个 spot 的局部得分
# lrdata.var             : 全局统计（含 p-value）
# lrdata.layers['pvals'] : 置换检验 p-value
```

**Bivariate 回答什么问题？**
> "数据库里哪些配体-受体对在空间上是协同表达的？"

#### 5B. Global Specificity 汇总

对 bivariate 或 inflow 的结果按细胞类型做全局汇总。

```python
ln.mt.compute_global_specificity(
    lrdata,                    # bivariate() 或 inflow() 返回的对象
    groupby='cell_type',
    use_raw=True  # use adata.raw if present; set False to use adata.X,
    uns_key='global_interactions'
)

global_res = lrdata.uns['global_interactions']
# 列包括：source, target, ligand_complex, receptor_complex, lr_mean, pval
```

#### 5C. 单细胞分辨率 — Inflow

适用于 Xenium、CosMx、MERFISH 等单细胞分辨率数据。

```python
import liana as ln

# Step 1: 空间邻居（必须）
ln.ut.spatial_neighbors(adata, bandwidth=50, spatial_key='spatial')

# Step 2: 加载资源并运行 inflow
resource = ln.rs.select_resource('consensus')
lrdata = ln.mt.inflow(
    adata,
    groupby='cell_type',
    resource=resource,         # 传 DataFrame，不是 resource_name 字符串
    use_raw=True  # use adata.raw if present; set False to use adata.X
)

# Step 3: 全局汇总
ln.mt.compute_global_specificity(
    lrdata,
    groupby='cell_type',
    use_raw=True  # use adata.raw if present; set False to use adata.X,
    uns_key='global_interactions'
)

inflow_res = lrdata.uns['global_interactions']

# 可视化
ln.pl.dotplot(
    lrdata,
    colour='lr_mean',
    size='pval',
    uns_key='global_interactions',
    inverse_size=True
)
```

**Inflow 回答什么问题？**
> "每个细胞从空间邻居那里接收到了多少特定信号？"

#### 5D. MISTy 多视图分析

更复杂的空间建模，适合挖掘多层次空间模式。

```python
misty = ln.method.lrMistyData(
    adata,
    resource_name='consensus',
    spatial_key='spatial',
    bandwidth=100,
    kernel='misty_rbf'
)
misty = misty.fit(n_neighbors=10)
misty.plot_target_metrics()
misty.plot_interactions()
misty.plot_contribution()
```

**注意：** MISTy 计算量很大，>5000 个 spot 建议先子集化。

---

### 步骤 6：跨条件比较

比如对照组 vs 肿瘤组，哪条通讯通路变了？

```python
import liana as ln

# 方法1：分别跑再比较
conditions = {}
for cond in ['control', 'tumor']:
    adata_cond = adata[adata.obs['condition'] == cond].copy()
    ln.mt.rank_aggregate(adata_cond, groupby='cell_type', inplace=True)
    conditions[cond] = adata_cond.uns['liana_res']

# 找肿瘤特有的相互作用
common = set(conditions['control']['interaction_key']).intersection(
    set(conditions['tumor']['interaction_key'])
)
tumor_specific = set(conditions['tumor']['interaction_key']) - common
print(f"肿瘤特有的相互作用：{len(tumor_specific)} 条")

# 方法2：by_sample（数据集内部有多个样本时）
ln.mt.rank_aggregate.by_sample(
    adata,
    groupby='cell_type',
    sample_key='sample_id',
    inplace=True,
    key_added='liana_by_sample'
)
```

---

### 步骤 7：可视化

**重要**：直接调用 `liana.plotting` 的原生函数，不要用任何 wrapper。

```python
import liana as ln

# 点图（最常用）
ln.pl.dotplot(
    adata,
    colour='magnitude_rank',     # 颜色 = 强度
    size='specificity_rank',     # 大小 = 特异性
    top_n=30,                    # 只看前30条
    orderby='magnitude_rank',
    orderby_ascending=True       # magnitude_rank 越低越强
)

# 聚合视图（看细胞类型对之间的总体通讯强度）
# NOTE: tileplot 要求 fill/label 必须同时有 ligand_ 和 receptor_ 前缀版本。
# 最适合单个方法结果（如 cellphonedb）。rank_aggregate 结果只有 means/props
# 两对列可用，建议 rank_aggregate 用 dotplot 可视化。
ln.pl.tileplot(
    adata,
    fill='means',            # 对应 ligand_means & receptor_means
    label='props',           # 对应 ligand_props & receptor_props
    top_n=20,
    orderby='magnitude_rank',
    orderby_ascending=True
)

# 网络图（圆形布局）
ln.pl.circle_plot(
    adata,
    groupby='cell_type',         # 必需：分析时用的细胞类型列
    score_key='magnitude_rank',  # 用于边权重的列
    inverse_score=True,          # -log10 变换（rank 越低越强）
    top_n=20
)

# 多条件对比图
ln.pl.dotplot_by_sample(
    adata,
    sample_key='condition',
    colour='magnitude_rank',
    size='specificity_rank'
)

# 空间邻居连接图（验证空间邻居结构，不是 CCC 结果！）
ln.pl.connectivity(adata, idx=0, spatial_key='spatial')
```

---

### 步骤 8：导出结果

```python
from scripts.python.core_analysis import export_results  # 本技能 wrapper

# CSV（最通用）
export_results(results, 'liana_results.csv', format='csv')

# TSV（导入 R 用）
export_results(results, 'liana_results.tsv', format='tsv')

# Excel（给不懂代码的合作者）
export_results(results, 'liana_results.xlsx', format='excel')

# 保存完整的 AnnData（包含结果，下次直接读取）
adata.write_h5ad('adata_with_liana.h5ad')
```

---

## 结果解读指南

### 拿到结果表后先看什么

典型的 `liana_res` 长这样：

| source | target | ligand | receptor | magnitude_rank | specificity_rank | ligand_props | receptor_props |
|--------|--------|--------|----------|----------------|------------------|--------------|----------------|
| Macrophage | T_cell | TGFB1 | TGFBR1 | 0.01 | 0.05 | 0.85 | 0.72 |
| Tumor | Fibroblast | CXCL12 | CXCR4 | 0.03 | 0.12 | 0.91 | 0.68 |
| ... | ... | ... | ... | ... | ... | ... | ... |

**阅读顺序**：
1. **先看 `magnitude_rank`**（越低 = 越强），排序后取前 20-50 条
2. **再看 `specificity_rank`**（越低 = 越特异），排除那些在所有细胞对里都很强的"泛信号"
3. **检查 `ligand_props` 和 `receptor_props`**，确保不是极端低表达（比如 < 0.05 的结果可信度低）
4. **结合生物学知识判断**：这条通路在你的研究背景下是否合理？

### 关键列含义（再强调一次）

| 列名 | 含义 | 怎么看 |
|------|------|--------|
| `magnitude_rank` | 综合强度排名（0-1） | **越低越强**。前 5% 的结果通常是"显著"的 |
| `specificity_rank` | 细胞类型特异性（0-1） | **越低越特异**。如果为 0.5，说明这条通路在很多细胞对里都强 |
| `ligand_props` | 源细胞表达该配体的比例 | 太低（<0.1）意味着只有少数细胞在发信号 |
| `receptor_props` | 靶细胞表达该受体的比例 | 太低意味着靶细胞大多收不到信号 |

### 什么结果算"好"

没有绝对的阈值，但经验法则：
- `magnitude_rank < 0.05`：强相互作用，值得深入研究
- `magnitude_rank 0.05-0.2`：中等强度，可作为候选
- `magnitude_rank > 0.5`：弱信号，通常忽略

### 常见疑问

**Q：排名第一的相互作用一定是真实的吗？**
A：不一定。排名是基于表达数据的统计推断，可能存在假阳性。建议：
- 看多个方法是否一致（rank aggregate 已经做了这件事）
- 结合文献，看这个 LR 对在你的组织类型中是否已有报道
- 用空间数据验证（如果做了空间实验）

**Q：为什么同一个 LR 对出现在多条记录里？**
A：一条记录 = source + target + ligand + receptor 的组合。同一个 LR 对可能在多个细胞类型对之间出现（比如 Tumor→T_cell 和 Tumor→Macrophage 都用 TGFB1-TGFBR1）。

**Q：结果是空的怎么办？**
见下方 Troubleshooting。

---

## 参数详解

### expr_prop（表达比例阈值）

控制"至少多少比例的细胞表达这个基因，才算这个基因在该细胞类型中有表达"。

| 值 | 适用场景 |
|----|---------|
| 0.05 | 探索性分析，不想漏掉任何潜在相互作用 |
| **0.1** | **默认，平衡灵敏度和特异性** |
| 0.2 | 高置信度分析，只保留广泛表达的基因 |
| 0.3+ | 极严格，只保留最稳健的相互作用 |

### aggregate_method（共识方法）

| 方法 | 说明 | 推荐度 |
|------|------|--------|
| `rra` | Robust Rank Aggregate，对异常值稳健，适合方法间差异大的场景 | ⭐⭐⭐ 首选 |
| `mean` | 简单平均排名，方法间差异小时可用 | ⭐⭐ 备选 |

### n_perms（置换次数）

| 值 | 耗时 | 用途 |
|----|------|------|
| 10-50 | 秒级 | 快速测试代码是否能跑通 |
| **100** | 分钟级 | **默认，适合常规分析** |
| 1000 | 10分钟-小时级 | 发表级别，审稿人可能会要求 |

### 空间分析前置参数

空间分析需要先计算邻居图，参数在 `sq.gr.spatial_neighbors()` 或 `ln.ut.spatial_neighbors()` 中设置：

| 技术 | 邻居计算方法 | 推荐参数 |
|------|------------|---------|
| Visium | `sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)` | 六边形网格，6个邻居 |
| Visium HD | `sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)` | 六边形网格 |
| Xenium | `ln.ut.spatial_neighbors(adata, bandwidth=50)` | Delaunay + 距离阈值 |
| CosMx | `ln.ut.spatial_neighbors(adata, bandwidth=50)` | Delaunay + 距离阈值 |

**注意**：`bivariate()` 和 `inflow()` 本身不接受 `neighbours` 或 `bandwidth` 参数。它们读取 `adata.obsp['spatial_connectivities']`。

---

## 常见问题排查

### 空结果 / 结果极少

| 可能原因 | 排查方法 | 解决办法 |
|---------|---------|---------|
| `groupby` 列名不对 | `print(adata.obs.columns)` | 确认列名拼写完全一致 |
| 细胞类型细胞数太少 | `adata.obs['cell_type'].value_counts()` | 合并稀有类型或降低 `min_cells` |
| 基因名不匹配 | `print(adata.var_names[:10])` | 人/鼠基因名要统一，去除版本号（如 ENSG000001 → TGFB1） |
| 资源库基因覆盖率低 | 见下方"检查资源覆盖率" | 换资源库或确认数据物种 |
| `expr_prop` 设太高 | 试试 `expr_prop=0.05` | 逐步降低阈值 |

**检查资源覆盖率**：
```python
import liana as ln
resource = ln.rs.select_resource('consensus')  # 或 'CellChatDB'
genes_in_data = set(adata.var_names)
resource_genes = set(resource['ligand']) | set(resource['receptor'])
coverage = len(resource_genes & genes_in_data) / len(resource_genes)
print(f"覆盖率: {coverage:.1%}")  # < 50% 就比较危险了
```

### 内存不足

| 现象 | 解决办法 |
|------|---------|
| 进程被杀死 / OOM | 降低 `n_perms`（100 → 50） |
| | 先用 `filter_cell_types()` 保留主要细胞类型 |
| | 空间分析：MISTy 先子集化到 5000 个 spot 以内 |
| | 关掉 `verbose=False` 减少日志开销 |

### 不同方法结果差异大

这是**正常现象**。不同方法的统计框架不同：
- CellPhoneDB：看差异表达，对零膨胀敏感
- NATMI：加权表达乘积，对高表达基因敏感
- Connectome：网络权重，对全局连通性敏感

**处理建议**：
- Rank aggregate 已经做了共识，优先看它
- 如果只关心"统计显著性"，重点关注 CellPhoneDB 的 pvalue
- 如果只关心"表达量大小"，看 NATMI 或 geometric_mean

### 空间分析报错

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `spatial_connectivities not found` | 没跑空间邻居计算 | 先跑 `sq.gr.spatial_neighbors()` 或 `ln.ut.spatial_neighbors()` |
| `spatial_key not found` | `adata.obsm` 里没有 `spatial` | 确认坐标存储位置，可能需要手动添加 |
| `NaN in coordinates` | 空间坐标有缺失 | `adata = adata[~pd.isna(adata.obsm['spatial']).any(axis=1)]` |
| MISTy 跑不动 | 数据量太大 | `adata_subset = sc.pp.subsample(adata, n_obs=5000, copy=True)` |
| bivariate/inflow 返回空 | `obsp['spatial_connectivities']` 为空或格式不对 | 检查 `adata.obsp['spatial_connectivities']` 是否存在且非空 |

**重要概念纠正**：
- `bivariate()` 和 `inflow()` **返回新的 AnnData**，不修改原 `adata`
- 它们读取 `adata.obsp['spatial_connectivities']`，**不自己计算邻居**
- `connectivity()` 是画空间邻居图的，**不能用来展示 CCC 结果**

### 基因名问题（最常见！）

LIANA+ 内置数据库的基因名是标准 human symbol（如 `TGFB1`）。如果你的数据是：
- **小鼠数据**：基因名是 `Tgfb1`（首字母大写），需要统一为大写，或确认数据库是否支持小鼠
- **Ensembl ID**：`ENSG00000105329` → 需要转换为 gene symbol
- **带版本号**：`TGFB1.2` → 需要去除版本号
- **全小写**：`tgfb1` → 转大写

**快速修复**：
```python
# 统一为大写
adata.var_names = adata.var_names.str.upper()
# 去除版本号
adata.var_names = adata.var_names.str.split('.').str[0]
```

### 结果里有不认识的基因名

可能是：
- 复合受体（如 `TGFBR1_TGFBR2`）→ 这是 CellChatDB 数据库的写法，表示需要两个亚基
- 非标准命名 → 用 `ln.rs.select_resource('consensus')` 查看数据库原始内容

---

## 从结果到生物学故事

拿到排名靠前的相互作用后，怎么讲一个合理的故事？

**建议的思考路径**：

1. **先定位核心细胞类型对**
   - 哪对 source→target 出现频率最高？
   - 和你的生物学假设一致吗？（比如肿瘤-免疫互作）

2. **再看具体通路**
   - 这些相互作用集中在哪些信号通路？（VEGF、TGFβ、WNT、Chemokine...）
   - 用 `summarize_by_cell_pair()` 做汇总矩阵

3. **验证方向**
   - 文献中是否有类似报道？
   - 空间数据是否支持物理 proximity？
   - 如果做了实验，这些通路的抑制剂/激活剂能否复现表型？

4. **可视化优先级**
   - 先画 `ln.pl.dotplot()` 看全局
   - 再聚焦到感兴趣的 source→target 对
   - 空间数据用 `ln.pl.dotplot(lrdata, ...)` 或 `ln.pl.tileplot()` 增强说服力

---

## 参考资料

1. Dimitrov D., et al. (2024). LIANA+ provides an all-in-one framework for cell-cell communication inference. *Nature Cell Biology*.
2. Dimitrov D., et al. (2022). Comparison of methods and resources for cell-cell communication inference. *Nature Communications*, 13, 3224.
3. LIANA+ 官方文档：https://liana-py.readthedocs.io/
4. 数据库详情：`ln.rs.show_resources()` 后查看具体资源表
