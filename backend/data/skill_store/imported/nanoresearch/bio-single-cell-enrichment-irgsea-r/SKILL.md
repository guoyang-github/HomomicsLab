---
name: bio-single-cell-enrichment-irgsea-r
description: Integrated multi-method gene set enrichment with RRA consensus scoring
tool_type: r
primary_tool: irGSEA
language: r
dependencies:
  - irGSEA
  - Seurat >= 4.3.0, < 5.0.0 (irGSEA not yet compatible with Seurat v5)
  - ComplexHeatmap
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "irGSEA", "multi-method", "RRA", "consensus", "R", "EMT Scoring"]
---

## Version Compatibility

- **R**: 4.2.0+
- **irGSEA**: Latest from GitHub
- **Seurat**: >= 4.3.0, < 5.0.0 (the underlying `irGSEA` package uses `slot` parameter internally which is incompatible with Seurat v5)

## Installation

```r
devtools::install_github("GitHUBZJY/irGSEA")
```

# irGSEA: Integrated Robust GSEA

Multi-method gene set enrichment with RRA (Robust Rank Aggregation) integration for consensus scoring.

## Quick Selector

| Methods Included | AUCell, UCell, singscore, ssgsea, ssGSEA2 |
|-----------------|------------------------------------------|
| **Integration** | RRA consensus |
| **Best for** | When method agreement is important |
| **Differential** | Built-in differential enrichment |

### When to Use irGSEA

- Want consensus across multiple scoring methods
- Need differential enrichment analysis
- Unsure which single method to choose
- Robustness is priority over speed

---

## Quick Start

```r
source("scripts/r/run_irgsea.R")

# Run with all methods + RRA
results <- run_irgsea(
  expr_matrix = expr_matrix,
  gene_sets = gene_sets,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  rra_integration = TRUE
)

# Access RRA consensus scores
rra_scores <- results$RRA
```

**Full implementation:** [scripts/r/run_irgsea.R](scripts/r/run_irgsea.R)

---

## Detailed Usage

### 1. Run All Methods

```r
source("scripts/r/run_irgsea.R")

results <- run_irgsea(
  expr_matrix = expr_matrix, # Expression matrix (genes x cells)
  gene_sets = marker_genes,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  minGSSize = 10,
  maxGSSize = 500,
  ncores = 4,
  rra_integration = TRUE
)

# Results contains:
# - results$AUCell
# - results$UCell
# - results$singscore
# - results$ssgsea
# - results$ssGSEA2
# - results$RRA (if rra_integration=TRUE)
```

### 2. With Seurat

```r
seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  slot = "counts"
)

# Access RRA scores
FeaturePlot(seurat_obj, features = "irGSEA.RRA.T_cells")
```

### 3. Differential Enrichment

```r
# Compare two conditions
diff_results <- differential_enrichment(
  irgsea_results = results,
  group_vector = seurat_obj$condition,
  method = "RRA",
  test = "wilcoxon"
)

# View significant pathways
head(diff_results[diff_results$padj < 0.05, ])
```

### 4. EMT Scoring (M/E Ratio)

Calculate EMT (Epithelial-Mesenchymal Transition) score using custom gene sets by irGSEA.

```r
# Define EMT gene sets
emt_gene_sets <- list(
  # 上皮标志物 (Epithelial markers)
  Epithelial = c('CDH1', 'EPCAM', 'KRT8', 'KRT18', 'KRT19', 'OCLN', 'CLDN3', 'CLDN4',
                  'CLDN7', 'TJP1', 'TJP2', 'TJP3', 'CGN', 'MARVELD2', 'CRB3', 'DSP',
                  'PKP1', 'PKP2', 'PKP3', 'JUP', 'CTNNB1', 'ALCAM', 'CEACAM1', 'CEACAM5',
                  'CEACAM6', 'MUC1', 'MUC4', 'MUC16', 'CD24', 'HES1', 'PARD3', 'PARD6A',
                  'PARD6B', 'AMOT', 'AMOTL1', 'AMOTL2', 'INADL', 'MPP5', 'PALS1', 'CRUMBS3',
                  'LLGL1', 'LLGL2', 'SCRIB', 'DLG1', 'DLG2', 'DLG3', 'DLG4', 'DLG5'),

  # 间质标志物 (Mesenchymal markers)
  Mesenchymal = c('CDH2', 'VIM', 'FN1', 'SNAI1', 'SNAI2', 'TWIST1', 'ZEB1', 'ZEB2',
                  'MMP2', 'MMP3', 'MMP9', 'SERPINE1', 'ACTA2', 'TAGLN', 'TGFB1',
                  'TGFBR1', 'TGFBR2', 'SMAD2', 'SMAD3', 'COL1A1', 'COL1A2', 'COL3A1',
                  'COL5A1', 'FAP', 'THY1', 'VCAN', 'TNC', 'POSTN', 'WNT5A', 'WNT5B',
                  'AXL', 'LOXL2', 'LOXL3', 'ITGA5', 'ITGAV', 'ITGB1', 'CD44', 'EMP3',
                  'GADD45B', 'ID2', 'ID3', 'RHOC', 'ROCK1', 'RAC1', 'CDC42', 'PAK1',
                  'LIMK1', 'CFL1', 'DSTN', 'TPM1', 'TPM2', 'MYL9', 'MYH9', 'PRKCA',
                  'MARCKS', 'PPP1R12A', 'CALD1', 'MYLK', 'FLNA', 'FLNB'),

  # Core EMT transcription factors
  EMT_TFs = c("SNAI1", "SNAI2", "ZEB1", "ZEB2", "TWIST1", "TWIST2"),

  # EMT相关基因集（来自MSigDB Hallmark EMT）（用于参考）
  EMT_Hallmark = c('CTNNB1', 'GSK3B', 'MYC', 'SNAI1', 'SNAI2', 'TWIST1', 'ZEB1', 'ZEB2',
               'VIM', 'CDH2', 'FN1', 'MMP2', 'MMP9', 'SERPINE1', 'SPARC', 'TGFBR1',
               'TGFBR2', 'TGFB1', 'TGFB2', 'EGF', 'EGFR', 'PDGFRB', 'FGFR1', 'IGF1R',
               'WNT5A', 'WNT5B', 'AXL', 'LOXL2', 'LOXL3', 'ITGA5', 'ITGAV', 'COL1A1',
               'COL1A2', 'COL3A1', 'COL5A1', 'FAP', 'THY1', 'VCAN', 'TNC', 'POSTN',
               'MMP3', 'MMP10', 'MMP13', 'MMP14', 'MMP16', 'LAMB3', 'LAMC2', 'LAMA3',
               'TIMP1', 'TIMP2', 'ITGA2', 'ITGA3', 'ITGB1', 'CD44', 'EMP3', 'GADD45B',
               'TGIF1', 'ID2', 'ID3', 'FGF2', 'IGFBP3', 'IGFBP4', 'IGFBP5', 'VEGFA',
               'VEGFC', 'ANGPTL4', 'RHOC', 'ROCK1', 'RAC1', 'CDC42', 'PAK1', 'LIMK1',
               'CFL1', 'DSTN', 'ACTA2', 'TAGLN', 'TPM1', 'TPM2', 'MYL9', 'MYH9',
               'PRKCA', 'MARCKS', 'PPP1R12A', 'CALD1', 'MYLK', 'FLNA', 'FLNB', 'PALLD',
               'MYO10', 'ENAH', 'ARPC1B', 'ARPC2', 'ARPC3', 'ARPC4', 'ARPC5', 'WAS',
               'WASL', 'CYFIP1', 'ABI1', 'NCKAP1', 'HSPC300', 'BRK1')
)

# Run irGSEA with custom gene sets (auto-detects custom=TRUE)
# Add scores to Seurat object
seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = emt_gene_sets,
  slot = "counts",
  rra_integration = TRUE
)
# Scores are automatically extracted to metadata as:
# - irGSEA.UCell.Mesenchymal
# - irGSEA.UCell.Epithelial


# Run irGSEA with all methods
irgsea_results <- run_irgsea(
  expr_matrix = expr_matrix,
  gene_sets = emt_gene_sets,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  rra_integration = TRUE,
  ncores = 4
)

# Calculate EMT score as M/E ratio (recommended)
seurat_obj <- calculate_emt_score(
  seurat_obj,
  mesenchymal_col = "irGSEA.UCell.Mesenchymal",
  epithelial_col = "irGSEA.UCell.Epithelial",
  method = "ratio",  # "ratio" = M/E, "difference" = M-E
  new_col_name = "EMT_Score"
)

# Visualize
FeaturePlot(seurat_obj, features = "EMT_Score")
VlnPlot(seurat_obj, features = "EMT_Score", group.by = "cell_type")

# Compare EMT between conditions (e.g., High vs Low NI)
diff_emt <- differential_enrichment(
  irgsea_results = irgsea_results,
  group_vector = seurat_obj$NI_group,
  method = "RRA",
  test = "wilcoxon"
)
```

**EMT Score Interpretation:**
| Method | Formula | Interpretation |
|--------|---------|----------------|
| `ratio` | M / (E + 0.001) | > 1: Mesenchymal-dominant, < 1: Epithelial-dominant |
| `difference` | M - E | Positive: Mesenchymal, Negative: Epithelial |

### EMT_TFs说明
作为独立的基因集，EMT_TFs 提供：

  1. 早期 EMT 检测
      - 转录因子变化早于结构蛋白（Vimentin, N-cadherin）
      - 识别"正在启动EMT"的细胞
  2. 区分 EMT 驱动 vs 结果
      - Epithelial/Mesenchymal = 细胞状态（结果）
      - EMT_TFs = 主动调控信号（驱动）
  3. 异质性分析

三种情况：
  1. 高 M + 低 E + 高 TFs = 活跃EMT（间质状态）
  2. 低 M + 高 E + 高 TFs = 早期EMT（上皮但正在转化）
  3. 高 M + 低 E + 低 TFs = 稳定间质（已完成EMT）

实际应用建议

  - 与 TGF-β 信号关联：TGF-β 是主要诱导 EMT TFs 的上游通路
  - 结合使用：EMT_TFs 高但 Mesenchymal 低 → EMT 早期阶段
  - 不需要用于 EMT_score 计算：比值通常只用 M/E，TFs 单独分析
  - EMT_TFs 可以帮助识别正在获得侵袭能力的细胞，而不仅仅是已经间质化的细胞。


### EMT评分对比
  1. EMT_Hallmark 评分

  混合基因集：包含 E 和 M 基因
  EMT_Hallmark = c("CDH1", "VIM", "SNAI1", "KRT8", "FN1", ...)
  - 高分数 = 细胞表达 EMT 相关基因（可能是上皮或间质）
  - 问题：无法区分 EMT 起始（上皮但响应信号）vs EMT 完成（间质状态）

  2. M/E 比值 (EMT_score)

  EMT_score = Mesenchymal / (Epithelial + 0.01)
  - 低值 (< 0.5) = 上皮状态为主
  - 高值 (> 2) = 间质状态为主
  - 中间值 = 混合/过渡状态



| 研究问题                     | 推荐指标               |
|------------------------------|------------------------|
| 细胞是否具有 EMT 特征？      | EMT_Hallmark           |
| 细胞处于 EMT 的哪个阶段？    | EMT_score（M/E）  |
| 比较 NI 高 vs 低的 EMT 程度  | EMT_score              |
| 筛选 EMT 阳性细胞            | 两者结合               |



### 5. Extract Scores from Assays

Manually extract scores from irGSEA assays to metadata (optional, `run_irgsea_seurat` does this automatically).

```r
# After running irGSEA
seurat_obj <- run_irgsea_seurat(seurat_obj, gene_sets, method = "UCell")

# Extract with custom prefix
seurat_obj <- extract_irgsea_scores(seurat_obj, method = "UCell", prefix = "UCell")

# Access scores
head(seurat_obj$UCell.GeneSetName)
FeaturePlot(seurat_obj, features = "UCell.Mesenchymal")
```


---

## Visualization

### 1. Heatmap Visualization

Visualize enrichment scores across cells and gene sets.

```r
# Basic heatmap with top variable gene sets
library(ComplexHeatmap)
hm <- plot_irgsea_heatmap(
  irgsea_results = irgsea_results,
  method = "RRA",
  group_vector = seurat_obj$cell_type,
  top_n = 20
)
draw(hm)

# Custom heatmap with annotations
scores <- irgsea_results$RRA
ha <- HeatmapAnnotation(
  CellType = seurat_obj$cell_type,
  Condition = seurat_obj$condition,
  col = list(
    CellType = c("T_cell" = "#1f77b4", "B_cell" = "#ff7f0e", "Myeloid" = "#2ca02c"),
    Condition = c("Control" = "#d62728", "Treatment" = "#9467bd")
  )
)
Heatmap(t(scores[, 1:10]),
        name = "Enrichment Score",
        top_annotation = ha,
        cluster_columns = TRUE,
        cluster_rows = TRUE,
        show_column_names = FALSE)
```

### 2. Dimensionality Reduction Plots

Display enrichment scores on UMAP/t-SNE.

```r
# Single gene set
top_geneset <- "T_cells"
FeaturePlot(seurat_obj, 
            features = paste0("irGSEA.RRA.", top_geneset),
            min.cutoff = 0, max.cutoff = 1) +
  scale_color_viridis_c() +
  ggtitle(paste("RRA Score:", top_geneset))

# Multiple gene sets
gene_sets_to_plot <- c("irGSEA.RRA.Epithelial", 
                       "irGSEA.RRA.Mesenchymal",
                       "irGSEA.RRA.T_cells")
FeaturePlot(seurat_obj, features = gene_sets_to_plot, ncol = 2)

# Overlay multiple scores using blend
FeaturePlot(seurat_obj, 
            features = c("irGSEA.RRA.Epithelial", "irGSEA.RRA.Mesenchymal"),
            blend = TRUE, blend.threshold = 0.5)
```

### 3. Distribution Plots

Compare scores across cell types or conditions.

```r
library(ggplot2)

# Violin plot by cell type
VlnPlot(seurat_obj, 
        features = "irGSEA.RRA.T_cells",
        group.by = "cell_type",
        pt.size = 0) +
  geom_boxplot(width = 0.1, fill = "white", outlier.size = 0)

# Ridge plot for density comparison
library(ggridges)
plot_data <- data.frame(
  Score = seurat_obj$irGSEA.RRA.T_cells,
  CellType = seurat_obj$cell_type
)
ggplot(plot_data, aes(x = Score, y = CellType, fill = CellType)) +
  geom_density_ridges(alpha = 0.7) +
  theme_ridges() +
  labs(title = "T Cell Signature Distribution")

# Boxplot with statistics
library(ggpubr)
ggboxplot(plot_data, x = "CellType", y = "Score",
          add = "jitter", add.params = list(size = 0.3, alpha = 0.5)) +
  stat_compare_means(method = "anova") +
  rotate_x_text(45)
```

### 4. Method Comparison

Compare scores from different enrichment methods.

```r
# Extract scores for one gene set across methods
gene_set <- "T_cells"
method_scores <- data.frame(
  AUCell = irgsea_results$AUCell[, gene_set],
  UCell = irgsea_results$UCell[, gene_set],
  singscore = irgsea_results$singscore[, gene_set],
  ssgsea = irgsea_results$ssgsea[, gene_set],
  RRA = irgsea_results$RRA[, gene_set]
)

# Correlation heatmap
cor_matrix <- cor(method_scores, use = "complete.obs")
pheatmap(cor_matrix, 
         main = "Method Correlation",
         display_numbers = TRUE,
         color = colorRampPalette(c("blue", "white", "red"))(100))

# Scatter plot comparing two methods
ggplot(method_scores, aes(x = AUCell, y = RRA)) +
  geom_point(alpha = 0.3) +
  geom_smooth(method = "lm") +
  stat_cor(method = "pearson") +
  labs(title = paste(gene_set, "- AUCell vs RRA"))

# All pairwise comparisons (pairs plot)
library(GGally)
ggpairs(method_scores, 
        lower = list(continuous = wrap("smooth", alpha = 0.3)),
        diag = list(continuous = wrap("barDiag", bins = 30)),
        title = "Method Comparison")
```

### 5. Differential Enrichment Visualization

Visualize differential enrichment results.

```r
# Volcano plot
diff_results$significant <- diff_results$padj < 0.05
ggplot(diff_results, aes(x = log2FC, y = -log10(padj), color = significant)) +
  geom_point(size = 3) +
  geom_vline(xintercept = c(-0.5, 0.5), linetype = "dashed") +
  geom_hline(yintercept = -log10(0.05), linetype = "dashed") +
  geom_text_repel(data = subset(diff_results, significant),
                  aes(label = gene_set), max.overlaps = 15) +
  scale_color_manual(values = c("grey", "red")) +
  labs(title = "Differential Enrichment",
       x = "Log2 Fold Change",
       y = "-Log10 Adjusted P-value")

# Bar plot of top differential gene sets
top_diff <- head(diff_results[order(diff_results$padj), ], 15)
ggplot(top_diff, aes(x = reorder(gene_set, -log10(padj)), 
                     y = -log10(padj), fill = log2FC > 0)) +
  geom_bar(stat = "identity") +
  coord_flip() +
  scale_fill_manual(values = c("blue", "red"),
                    labels = c("Down", "Up"),
                    name = "Direction") +
  labs(title = "Top Differential Gene Sets",
       x = "Gene Set",
       y = "-Log10 Adjusted P-value")

# Lollipop plot
ggplot(top_diff, aes(x = reorder(gene_set, log2FC), y = log2FC)) +
  geom_segment(aes(x = gene_set, xend = gene_set, y = 0, yend = log2FC),
               color = "grey") +
  geom_point(aes(color = padj < 0.05), size = 4) +
  scale_color_manual(values = c("grey50", "red")) +
  coord_flip() +
  labs(title = "Log2FC of Top Gene Sets")
```

### 6. Multi-method Consensus Visualization

Visualize agreement across methods.

```r
# Upset plot for top cells by each method
library(UpSetR)

# Get top 10% cells for each method
top_cells <- lapply(c("AUCell", "UCell", "singscore", "ssgsea", "RRA"), 
                    function(m) {
  scores <- irgsea_results[[m]][, "T_cells"]
  names(sort(scores, decreasing = TRUE))[1:round(0.1 * length(scores))]
})
names(top_cells) <- c("AUCell", "UCell", "singscore", "ssgsea", "RRA")

# Create binary matrix for upset plot
all_cells <- colnames(seurat_obj)
binary_matrix <- sapply(top_cells, function(cells) {
  as.integer(all_cells %in% cells)
})
rownames(binary_matrix) <- all_cells

upset(as.data.frame(binary_matrix), 
      nsets = 5,
      main.bar.color = "maroon",
      sets.bar.color = "steelblue",
      title = "Method Agreement - Top T Cell Signature Cells")

# Agreement score per cell
method_agreement <- rowMeans(binary_matrix)
seurat_obj$method_agreement <- method_agreement
FeaturePlot(seurat_obj, features = "method_agreement") +
  ggtitle("Fraction of Methods Calling Cell Positive")
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `methods` | vector | All 5 | Methods to run |
| `rra_integration` | bool | TRUE | RRA consensus integration |
| `minGSSize` | int | 10 | Min genes per set |
| `maxGSSize` | int | 500 | Max genes per set |

**Available methods:** `AUCell`, `UCell`, `singscore`, `ssgsea`, `ssGSEA2`

---

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_irgsea()` | [run_irgsea.R:41](scripts/r/run_irgsea.R#L41) | Main irGSEA analysis (matrix input) |
| `run_irgsea_seurat()` | [run_irgsea.R:175](scripts/r/run_irgsea.R#L175) | Seurat wrapper (auto-detects custom gene sets) |
| `extract_irgsea_scores()` | [run_irgsea.R:361](scripts/r/run_irgsea.R#L361) | Extract scores from assays to metadata |
| `calculate_emt_score()` | [run_irgsea.R:420](scripts/r/run_irgsea.R#L420) | Calculate EMT score (M/E ratio or M-E) |
| `differential_enrichment()` | [run_irgsea.R:236](scripts/r/run_irgsea.R#L236) | Differential analysis between groups |
| `plot_irgsea_heatmap()` | [run_irgsea.R:300](scripts/r/run_irgsea.R#L300) | Heatmap visualization |
| `export_irgsea_results()` | [run_irgsea.R:343](scripts/r/run_irgsea.R#L343) | Export all results to CSV |

---

## Related Skills

- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) - gseapy
- [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md) - AUCell
- [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/SKILL.md) - UCell

---

## References

1. Zhang et al. (2023). irGSEA: a comprehensive package for single-cell gene set enrichment analysis. Bioinformatics.
2. Kolde et al. (2012). Robust rank aggregation for gene list integration and meta-analysis. Bioinformatics.
3. irGSEA documentation: https://github.com/GitHUBZJY/irGSEA
