# Spatial Niche Analysis Guide

空间微环境 (Niche) 分析简明指南

---

## 什么是 Niche？

**Niche（微环境）** 是组织中具有相似细胞类型组成的空间区域。它代表了特定的生物学微环境，如：

- **肿瘤核心** (Tumor Core): 癌细胞主导的区域
- **三级淋巴结构** (TLS): 免疫细胞聚集区
- **神经侵袭区** (Neural Invasion Zone): 神经与癌细胞交互区
- **基质区** (Stroma): 成纤维细胞为主的区域

### 为什么分析 Niche？

传统单细胞分析告诉我们**有哪些细胞**，而 Niche 分析告诉我们**这些细胞如何组织在一起**，揭示：

1. **空间组织模式**: 细胞不是随机分布的，而是形成功能性区域
2. **疾病相关微环境**: 特定疾病状态有其特征性的 niche 组成
3. **细胞间相互作用**: 同一 niche 内的细胞更可能相互影响

---

## Niche 分析流程概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Niche 分析工作流程                            │
└─────────────────────────────────────────────────────────────────────┘

Step 1: 反卷积 (Deconvolution)          Step 2: Niche 聚类
┌─────────────────────┐                ┌─────────────────────┐
│  ST 数据            │                │  基于细胞类型组成    │
│  ↓                  │    ───────▶    │  对 spots 进行聚类   │
│  每个 spot 的        │                │  ↓                  │
│  细胞类型比例        │                │  Niche A, B, C...   │
└─────────────────────┘                └─────────────────────┘

Step 3: Niche 注释                      Step 4: 组间比较与差异分析
┌─────────────────────┐                ┌─────────────────────┐
│  根据标志细胞类型    │                │  Compare Niches     │
│  给 niche 命名       │    ───────▶    │  by Group           │
│  ↓                  │                │  (描述性比较)        │
│  TLS, Neural,       │                │  ↓                  │
│  Tumor_core...      │                │  Niche Differential │
└─────────────────────┘                │  Abundance          │
                                       │  (统计检验)          │
                                       └─────────────────────┘
```

---

## 核心概念可视化

### Niche 识别过程

```
Input: 反卷积结果 (每个 spot 的细胞类型比例)
┌──────────┬──────────┬──────────┬──────────┐
│ Spot     │ Cancer   │ T_cell   │ Macroph  │
├──────────┼──────────┼──────────┼──────────┤
│ 1        │ 60%      │ 10%      │ 20%      │
│ 2        │ 55%      │ 15%      │ 18%      │
│ 3        │ 15%      │ 40%      │ 25%      │
│ 4        │ 10%      │ 45%      │ 20%      │
└──────────┴──────────┴──────────┴──────────┘
                ↓ 聚类 (相似组成 = 同一 niche)
Output: Niche 分配
┌──────────┬──────────────────────────────────┐
│ Spot 1-2 │ Niche A: "Tumor_Infiltrated"     │
│ Spot 3-4 │ Niche B: "TLS" (三级淋巴结构)     │
└──────────┴──────────────────────────────────┘
```

### Niche 空间分布

```
组织切片示意图:

┌──────────────────────────────────────┐
│  ████████████  TLS  ████████████    │  ← Niche B (免疫细胞)
│  ████████████       ████████████    │
│        ██████████████████████        │
│        ████  Tumor Core ████        │  ← Niche A (癌细胞)
│        ██████████████████████        │
│  ░░░░░░              ░░░░░░░░░░    │
│  ░░░░  Stroma  ░░░░░░░░░░░░░░░░    │  ← Niche C (基质)
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
└──────────────────────────────────────┘

图例: ████ Niche A (Tumor)  ████ Niche B (TLS)  ░░░░ Niche C (Stroma)
```

---

## Compare Niches by Group vs Niche Differential Abundance

| 维度 | Compare Niches by Group | Niche Differential Abundance |
|------|------------------------|------------------------------|
| **回答的问题** | "各组 niche 占比多少？" | "哪些 niche 有统计学差异？" |
| **分析类型** | 描述性统计 | 推断性统计 |
| **输出形式** | 比例表/堆叠图 | P值/Q值表/火山图 |
| **多重检验校正** | ❌ 否 | ✅ 是 (FDR) |
| **适用阶段** | 探索性分析 (EDA) | 验证性分析 |
| **典型发现** | "Neural niche 占 15% vs 3%" | "Neural niche 在 High NI 组显著富集 (q=0.001, FC=4.0)" |
| **使用建议** | **先用这个**看整体模式 | **再用这个**确认显著性 |

### 💡 何时使用哪个？

**使用 Compare Niches by Group 当:**
- 你想快速了解不同条件下 niche 组成
- 需要生成描述性图表（堆叠条形图）
- 样本量较小，不适合复杂统计

**使用 Niche Differential Abundance 当:**
- 你需要发表级别的统计证据
- 样本量足够 (n≥3 per group)
- 需要控制假阳性 (FDR 校正)

**最佳实践: 两个一起用!**
```
Step 1: Compare Niches → 发现 "Neural niche 在 High NI 组似乎更多"
Step 2: Differential Abundance → 验证 "确实显著富集 (q<0.05)"
Step 3: 可视化 → 在组织上定位这些 niche
```

---

## 应用场景决策矩阵

| 研究场景 | 分析目标 | 推荐方法 | 预期结果 |
|---------|---------|---------|---------|
| **病例 vs 对照** | High NI vs Low NI niche 组成差异 | Compare + DA | 发现疾病相关 niche |
| **治疗响应** | 治疗前后微环境重塑 | Compare + DA | 响应相关的 niche 变化 |
| **预后分层** | 好/差预后患者的空间特征 | Compare + DA | 预后相关的 niche 标志 |
| **肿瘤异质性** | 同一肿瘤内不同区域比较 | Compare | 肿瘤内 niche 分布图 |
| **大样本队列** | 发现稳健的生物标志物 | DA (严格校正) | 统计显著的差异 niche |
| **小样本探索** | 假设生成 | Compare | 初步模式，需验证 |

---

## 结果解读指南

### Compare Niches by Group 输出解读

```
                    High_NI    Low_NI    解读
─────────────────────────────────────────────────
Neural              0.15       0.03      ⭐ 高 NI 富集神经 niche
TLS                 0.10       0.12      两组相似
Tumor_core          0.35       0.42      低 NI 肿瘤 core 更多
Stroma              0.28       0.35      
Immune_infiltrate   0.12       0.08      高 NI 免疫浸润更多
```

**如何解读:**
- **比例差 > 2倍**: 可能有生物学意义 (如 Neural: 15% vs 3%)
- **比例差 < 1.5倍**: 可能只是随机波动
- **注意样本量**: 如果某组总 spot 数很少，比例可能不可靠

### Niche Differential Abundance 输出解读

```
Niche               pval       qval (FDR)  FC      解读
───────────────────────────────────────────────────────────
Neural              9.8e-5     0.001***    5.0     显著富集 ⭐
TLS                 0.08       0.15        0.83    不显著
Immune_excluded     0.0005     0.008**     0.42    显著减少
Stroma              0.35       0.52        0.80    不显著
```

**关键指标:**
- **qval < 0.05**: 统计显著 (FDR 校正后)
- **qval < 0.01**: 高度显著 (**)
- **qval < 0.001**: 极显著 (***)
- **FC (Fold Change)**: 效应大小，FC>2 或 <0.5 为强效应

### 综合解读示例

```
发现: Neural niche 在 High NI 组显著富集 (q=0.001, FC=5.0)

解读层次:
1. 统计层面: 这是真实差异，非随机波动 (q<0.05)
2. 效应层面: 差异很大，High NI 组该 niche 比例是 5 倍 (FC=5)
3. 生物学层面: 神经微环境可能与神经侵袭相关
4. 验证建议: 
   - 回查 H&E 确认该 niche 是否靠近神经
   - 检查该 niche 的细胞组成 (Schwann? EMT cancer?)
   - 在其他队列中验证
```

---

## 实战案例: PDAC Neural Invasion

### 研究背景
- **疾病**: 胰腺导管腺癌 (PDAC)
- **表型**: 神经侵袭 (Neural Invasion, NI) - 癌细胞沿神经扩散
- **数据**: 21 个 ST 样本 (10 High NI + 11 Low NI)
- **目标**: 找出与神经侵袭相关的空间微环境

### 分析流程

```
Step 1: 反卷积 (Cell2location/RCTD)
输入: ST 表达矩阵
输出: 每个 spot 的细胞类型比例 (12 种细胞类型)

Step 2: Niche 聚类
方法: Leiden 聚类 (spatial constraint)
输出: 8 个 niches

Step 3: Niche 注释
根据标志细胞类型:
- Niche 0: Cancer_EMT + Schwann → "Neural_NI"
- Niche 1: B_cell + T_cell → "TLS"
- Niche 2: Cancer_classical → "Tumor_Core"
- ...

Step 4: Compare Niches by Group
         High_NI    Low_NI
Neural_NI   18%        4%    ← 肉眼可见的差异
TLS         12%       15%
...

Step 5: Niche Differential Abundance
Niche       qval      FC       结论
Neural_NI   0.0002    4.5      ✅ 显著富集
TLS         0.12      0.8      ❌ 不显著
...

Step 6: 验证
- 空间可视化: Neural_NI niche 确实位于神经周围
- 细胞组成: 含 Schwann + EMT cancer + NLRP3+ macrophage
- 文献支持: 与已发表的神经侵袭机制一致
```

### 关键发现

| Niche | High NI | Low NI | Q值 | 生物学意义 |
|-------|---------|--------|-----|-----------|
| **Neural_NI** | 18% | 4% | *** | 神经侵袭发生的微环境 |
| **TLS** | 12% | 15% | NS | 免疫激活区域，两组相似 |
| **Immune_Excluded** | 8% | 18% | ** | 低 NI 组更多免疫排除区 |

**科学结论**: 
- High NI 肿瘤具有独特的 "神经侵袭微环境"
- 该 niche 的特征: Schwann 细胞 + EMT 癌细胞 + 促炎巨噬细胞
- 潜在机制: 神经-癌细胞相互作用促进侵袭

---

## 常见问题 (FAQ)

### Q1: Niche 数量如何选择？
**A**: 建议从 8-12 开始，根据生物学意义调整：
- 太少 (5-6): 可能合并了不同的微环境
- 太多 (15+): 可能出现稀有/不稳定的 niche
- 评估标准: 每个 niche 应包含合理的 spot 数 (≥20)

### Q2: 是否必须使用 spatial constraint？
**A**: 
- **推荐**: 对于大多数组织分析，使用 spatial constraint (Leiden + spatial)
- **例外**: 如果细胞类型组成本身就很特异，可以只用 proportions (KMeans)
- **判断**: 如果 niche 在空间上分散成很多小碎片，增加 spatial constraint

### Q3: 稀有 niche (spots < 10) 如何处理？
**A**: 
1. 合并到相似的 niche (基于细胞组成相关性)
2. 在注释时标记为 "Mixed/Other"
3. 差异分析时排除 (样本量不足以支持统计检验)

### Q4: Niche 分析与 Ro/e 分析的区别？
**A**: 

| | Niche 分析 | Ro/e 分析 |
|---|---|---|
| **输入** | 反卷积比例 | 反卷积比例 + 坐标 |
| **方法** | 聚类 (无监督) | 邻域统计 (有监督) |
| **输出** | 离散的 niche 标签 | 连续的 co-occurrence 分数 |
| **发现** | "这里有 3 种微环境" | "细胞 A 和 B 倾向于共定位" |
| **互补性** | 识别"是什么区域" | 识别"谁和谁在一起" |

**建议**: 两个都做! Niche 给出整体格局，Ro/e 给出具体相互作用。

### Q5: 如何解释 "不显著" 的结果？
**A**: 
- 可能真的没有差异
- 可能样本量不足 (需要更多样本)
- 可能 niche 定义不够精细 (尝试更多 clusters)
- 可能分组本身有问题 (考虑其他临床变量)

---

## 最佳实践 checklist

- [ ] 检查每个 niche 的 spot 数 (建议 ≥20)
- [ ] 检查 niche 的空间连续性 (不应过于破碎)
- [ ] 注释时参考已知生物学标志
- [ ] 差异分析前平衡样本量
- [ ] 多重检验校正 (FDR)
- [ ] 可视化验证 (在组织上查看 niche 分布)
- [ ] 与 H&E 或 IF 图像对比验证

---

## 相关资源

- **上游分析**: `bio-spatial-transcriptomics-deconvolution-*` - 获取细胞类型比例
- **下游分析**: `bio-spatial-transcriptomics-differential-abundance-roe-r` - 细胞共定位分析
- **可视化**: `bio-spatial-transcriptomics-visualization` - 高级空间可视化

---

*最后更新: 2026-04-01*
