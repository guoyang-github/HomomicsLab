# 空间转录组流程最佳实践（PER → PEER 架构升级方案）

## 目录

1. [架构设计原则](#1-架构设计原则)
2. [PEER 工作流模式](#2-peer-工作流模式)
3. [三层架构详解](#3-三层架构详解)
4. [守卫层设计规范](#4-守卫层设计规范)
5. [DAG 流程控制](#5-dag-流程控制)
6. [LLM 使用策略](#6-llm-使用策略)
7. [状态管理](#7-状态管理)
8. [实施路线图](#8-实施路线图)
9. [代码模板](#9-代码模板)

---

## 1. 架构设计原则

### 1.1 核心原则：确定性优先，智能化增强

| 原则 | 说明 | 违反的后果 |
|------|------|-----------|
| **确定性优先** | 参数推荐、执行逻辑必须可重复、可审计 | 结果不可复现，无法发表 |
| **守卫层兜底** | 关键决策必须有硬规则边界检查 | 执行明显错误的参数 |
| **LLM 不决策** | LLM 只提供建议，不直接修改参数 | 引入不可预测性 |
| **状态透明** | 每步状态必须显式标记，不可隐式推断 | 恢复流程时丢失上下文 |
| **独立可调用** | 每步函数必须可独立执行，不依赖全局状态 | 无法单元测试，无法部分重跑 |

### 1.2 反模式清单

| 反模式 | 示例 | 正确做法 |
|--------|------|---------|
| **LLM 推荐参数** | `gpt_pick_resolution(n_spots)` | 硬规则 `if (n_spots < 3000) 0.5 else 0.8` |
| **静默自动修正** | 自动调整分辨率而不告知 | 守卫层拦截并显式通知 |
| **隐式状态传递** | 依赖全局变量判断当前步骤 | 显式 `pipeline_state` 字段 |
| **不可逆操作无预览** | 直接过滤细胞不提示 | 预览过滤比例，超阈值时阻断 |
| **单文件超大函数** | 一个 500 行的 `run_pipeline()` | 拆分为 `propose`/`evaluate`/`execute`/`report` |

---

## 2. PEER 工作流模式

### 2.1 从 PER 到 PEER 的演进

```
PER (当前)
  Propose → Execute → Report
            ↑
            └── 无验证，可能执行错误参数

PEER (推荐)
  Propose → Evaluate → Execute → Report
                     ↑
                     └── 守卫层验证，拦截或修正
```

### 2.2 四阶段职责定义

#### Phase 1: Propose（提议）

**职责：** 基于数据特征推荐参数
**输入：** 当前状态的对象
**输出：** `proposal` 列表（推荐参数 + 诊断信息 + 理由）
**规则：**
- 必须是纯函数：相同输入 → 相同输出
- 不得调用外部 API（包括 LLM）
- 必须提供 `alternatives` 字段，列出替代方案

```r
propose_qc_thresholds <- function(obj) {
  # 纯确定性逻辑
  n_spots <- ncol(obj)
  mt_median <- median(obj$percent.mt)
  
  if (mt_median < 5)  max_mt <- 15
  else if (mt_median < 10) max_mt <- 20
  else max_mt <- 30
  
  list(
    recommendation = list(min_counts = 500, min_genes = 200, max_mt = max_mt),
    diagnostics = list(n_spots = n_spots, mt_median = mt_median),
    justification = sprintf("MT%% median = %.1f%% → max_mt = %d%%", mt_median, max_mt),
    alternatives = list(
      stringent = "max_mt = 15% (for very clean data)",
      permissive = "max_mt = 35% (for FFPE/necrotic tissue)"
    )
  )
}
```

#### Phase 2: Evaluate（评估）★ 新增

**职责：** 验证提议的合理性，拦截明显错误
**输入：** `proposal` + 当前对象
**输出：** `evaluation` 列表（裁决 + 修正参数 + 理由）
**规则：**
- 必须有硬规则守卫（不可仅依赖 LLM）
- 裁决分为三级：`PROCEED` / `CAUTION` / `BLOCK`
- `BLOCK` 时必须提供修正后的参数或明确的取消理由
- 所有修正必须记录到日志

```r
evaluate_qc_proposal <- function(proposal, obj) {
  # 模拟执行，预览影响
  n_total <- ncol(obj)
  simulated_keep <- obj$nCount_Spatial >= proposal$recommendation$min_counts &
                    obj$nFeature_Spatial >= proposal$recommendation$min_genes &
                    obj$percent.mt <= proposal$recommendation$max_mt
  n_keep <- sum(simulated_keep)
  pct_removed <- (1 - n_keep / n_total) * 100
  
  # 守卫规则
  if (pct_removed > 80) {
    # 自动放宽阈值
    relaxed_counts <- quantile(obj$nCount_Spatial, 0.05)
    relaxed_genes <- quantile(obj$nFeature_Spatial, 0.05)
    proposal$recommendation$min_counts <- relaxed_counts
    proposal$recommendation$min_genes <- max(100, relaxed_genes)
    
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("原参数将移除 %.1f%% 的 spot，超过 80%% 阈值。", pct_removed),
      adjusted_params = list(min_counts = relaxed_counts, min_genes = relaxed_genes)
    ))
  }
  
  if (pct_removed > 50) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("将移除 %.1f%% 的 spot，比例较高，建议人工确认。", pct_removed)
    ))
  }
  
  list(verdict = "PROCEED", adjusted = FALSE)
}
```

#### Phase 3: Execute（执行）

**职责：** 确定性执行，不修改推荐参数
**输入：** 对象 + 最终参数（可能已被 Evaluate 修正）
**输出：** 修改后的对象
**规则：**
- 不得修改 `proposal`，只读取最终参数
- 必须设置 `pipeline_state`
- 失败时必须抛出错误，不得静默跳过

```r
execute_qc <- function(obj, thresholds) {
  obj <- subset(obj, 
    subset = nCount_Spatial >= thresholds$min_counts &
             nFeature_Spatial >= thresholds$min_genes &
             percent.mt <= thresholds$max_mt
  )
  obj@misc$pipeline_state <- "Filtered"
  obj@misc$qc_thresholds <- thresholds
  return(obj)
}
```

#### Phase 4: Report（报告）

**职责：** 生成执行结果的状态报告
**输入：** 执行前/后对象 + 最终参数
**输出：** `report` 列表（状态 + 指标 + 建议）
**规则：**
- 状态必须为 `PASS` / `CAUTION` / `WARNING` / `SKIPPED` 之一
- 必须包含明确的 `next_step` 指引
- 必须包含 `recommendation` 文本，说明结果含义

```r
report_qc <- function(obj_before, obj_after, thresholds) {
  n_before <- ncol(obj_before)
  n_after <- ncol(obj_after)
  pct_removed <- (1 - n_after / n_before) * 100
  
  status <- if (pct_removed > 80) "WARNING"
            else if (pct_removed > 50) "CAUTION"
            else if (pct_removed > 30) "CAUTION"
            else "PASS"
  
  list(
    step = "QC Filtering",
    status = status,
    spots_before = n_before,
    spots_after = n_after,
    pct_removed = pct_removed,
    thresholds = thresholds,
    recommendation = case_when(
      pct_removed > 80 ~ "移除比例过高，已自动放宽阈值。建议检查原始数据质量。",
      pct_removed > 50 ~ "移除比例较高，建议确认阈值设置是否适合该组织类型。",
      TRUE ~ "QC 通过，继续下一步。"
    ),
    next_step = "Step 3: Normalization"
  )
}
```

---

## 3. 三层架构详解

### 3.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Human / Agent 交互层                               │
│  - 读取诊断卡片和评估结果                                     │
│  - 在 CAUTION/BLOCK 时做决策                                 │
│  - 手动覆盖参数（如用户明确指定 resolution = 1.2）            │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: LLM 顾问层（轻量级，可选）                          │
│  - 预飞行：审查 Proposal 的生物学合理性                      │
│  - 事后：生成诊断卡片，帮助解读结果                           │
│  - 绝不阻塞，除非置信度 > 95% 且规则守卫已触发               │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 确定性规则引擎（核心，不可绕过）                    │
│  - propose_*(): 硬规则参数推荐                               │
│  - evaluate_*(): 守卫层边界检查                              │
│  - execute_*(): 确定性执行                                   │
│  - report_*(): 状态报告                                      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 各层决策权限

| 场景 | Layer 1 (规则) | Layer 2 (LLM) | Layer 3 (用户) |
|------|---------------|---------------|----------------|
| 分辨率推荐 | ✅ 硬规则 | 💡 可建议微调 | ✅ 可覆盖 |
| q 值边界检查 | ✅ 自动拦截 | 💡 解释原因 | ✅ 可强制通过 |
| QC 阈值自动放宽 | ✅ 超 80% 时自动 | 💡 事后解释 | ✅ 可拒绝自动调整 |
| 方法选择（BayesSpace vs Leiden） | ✅ 基于数据量 | 💡 可补充生物学理由 | ✅ 可覆盖 |
| 组织类型特异性判断 | ❌ 规则无法判断 | 💡 LLM 提供参考 | ✅ 最终决策 |

---

## 4. 守卫层设计规范

### 4.1 守卫层分级

| 级别 | 触发条件 | 行为 | 示例 |
|------|---------|------|------|
| **BLOCK** | 参数明显错误，会导致无意义结果 | 自动修正参数或强制人工确认 | q > n_spots/10 |
| **CAUTION** | 参数可能不理想，结果需谨慎解读 | 继续执行但标记警告 | 移除 45% spot |
| **PROCEED** | 参数在合理范围内 | 正常执行 | 移除 15% spot |

### 4.2 各步骤守卫规则

#### Step 2: QC

```r
qc_guardrails <- list(
  max_removal = 0.80,      # 移除 > 80% → BLOCK，自动放宽
  caution_removal = 0.50,  # 移除 > 50% → CAUTION
  min_spots_after = 100,   # 过滤后 < 100 spot → BLOCK
  max_mt = 0.50,           # MT 阈值 > 50% → BLOCK
  min_counts = 100         # min_counts < 100 → BLOCK
)
```

#### Step 4: Integration

```r
integration_guardrails <- list(
  min_samples = 2,         # 样本数 < 2 → 跳过整个步骤
  max_samples = 20,        # 样本数 > 20 → CAUTION（内存风险）
  min_cells_per_sample = 50  # 某样本 < 50 细胞 → CAUTION
)
```

#### Step 5: Clustering

```r
clustering_guardrails <- list(
  resolution_range = c(0.1, 2.0),  # 超出范围 → BLOCK
  max_n_clusters = 100,            # > 100 cluster → CAUTION
  min_n_clusters = 2               # < 2 cluster → CAUTION
)
```

#### Step 7: Domain Detection

```r
domain_guardrails <- list(
  q_range = c(2, 30),           # BayesSpace q 超出 → BLOCK
  q_max_ratio = 0.1,            # q > n_spots * 0.1 → BLOCK
  resolution_range = c(0.1, 2.0),  # Leiden resolution 超出 → BLOCK
  min_domains = 2,              # 检测到 < 2 domain → WARNING
  max_domains = 50              # 检测到 > 50 domain → CAUTION
)
```

### 4.3 守卫层模板

```r
# 通用守卫层模板
evaluate_step_proposal <- function(proposal, obj, guardrails) {
  issues <- list()
  adjusted <- FALSE
  
  # 规则 1: 边界检查
  for (param_name in names(guardrails$ranges)) {
    value <- proposal$recommendation[[param_name]]
    range <- guardrails$ranges[[param_name]]
    if (value < range[1] || value > range[2]) {
      issues <- c(issues, sprintf("%s=%.2f 超出范围 [%.2f, %.2f]",
                                  param_name, value, range[1], range[2]))
      # 自动修正到边界
      proposal$recommendation[[param_name]] <- max(range[1], min(value, range[2]))
      adjusted <- TRUE
    }
  }
  
  # 规则 2: 影响预览
  if (!is.null(guardrails$impact_fn)) {
    impact <- guardrails$impact_fn(proposal, obj)
    if (impact$pct_affected > guardrails$max_impact) {
      issues <- c(issues, sprintf("影响 %.1f%% 的数据，超过阈值 %.1f%%",
                                  impact$pct_affected, guardrails$max_impact))
    }
  }
  
  # 裁决
  if (length(issues) > 0 && adjusted) {
    list(verdict = "BLOCK", adjusted = TRUE, reason = paste(issues, collapse = "; "))
  } else if (length(issues) > 0) {
    list(verdict = "CAUTION", adjusted = FALSE, reason = paste(issues, collapse = "; "))
  } else {
    list(verdict = "PROCEED", adjusted = FALSE)
  }
}
```

---

## 5. DAG 流程控制

### 5.1 为什么需要 DAG

线性流程的问题：
- 单样本时 Integration 步骤仍然被调用（只是内部跳过）
- 无法并行执行独立步骤
- 无法表达条件分支

### 5.2 DAG 定义示例

```r
# pipeline_dag.R
pipeline_dag <- list(
  
  # Step 1: Load
  load = list(
    fn = run_load_step,
    inputs = NULL,
    outputs = "Raw",
    skippable = FALSE
  ),
  
  # Step 2: QC
  qc = list(
    fn = run_qc_step,
    requires = "Raw",
    outputs = "Filtered",
    skippable = FALSE
  ),
  
  # Step 3: Normalization（可选分支）
  normalize = list(
    fn = run_normalization_step,
    requires = "Filtered",
    outputs = "Normalized",
    alternatives = list(
      lognormalize = run_lognormalize_step,
      sct = run_sct_step
    ),
    default = "lognormalize",
    skippable = FALSE
  ),
  
  # Step 3b: Doublet Detection（与 Normalization 并行）
  doublet = list(
    fn = run_doublet_step,
    requires = "Filtered",
    outputs = "Clean",
    parallel_to = "normalize",
    condition = function(obj) ncol(obj) > 1000,
    skippable = TRUE
  ),
  
  # Step 4: Integration（条件执行）
  integrate = list(
    fn = run_integration_step,
    requires = c("Normalized", "Clean"),
    condition = function(obj) {
      n_samples <- length(unique(obj$sample_id))
      n_samples > 1
    },
    outputs = "Integrated",
    skip_outputs = "Normalized",  # 跳过时保持 Normalized 状态
    skippable = TRUE
  ),
  
  # Step 5: Clustering
  cluster = list(
    fn = run_clustering_step,
    requires = c("Normalized", "Integrated"),
    outputs = "Clustered",
    skippable = FALSE
  ),
  
  # Step 6: Spatial Analysis
  spatial = list(
    fn = run_spatial_analysis_step,
    requires = "Clustered",
    outputs = "Spatial-Analyzed",
    condition = function(obj) length(obj@images) > 0,
    skip_outputs = "Clustered",
    skippable = TRUE
  ),
  
  # Step 7: Domain Detection
  domain = list(
    fn = run_domain_detection_step,
    requires = c("Spatial-Analyzed", "Clustered"),
    outputs = "Domains",
    skippable = TRUE
  )
)
```

### 5.3 DAG 执行器

```r
# dag_executor.R
run_dag <- function(obj, dag, from_step = NULL, mode = "interactive", ...) {
  # 1. 拓扑排序
  execution_order <- topological_sort(dag)
  
  # 2. 如果从中间恢复，截断前面的步骤
  if (!is.null(from_step)) {
    start_idx <- which(names(execution_order) == from_step)
    execution_order <- execution_order[start_idx:length(execution_order)]
  }
  
  reports <- list()
  prev_reports <- list()
  llm_reports <- list()
  
  for (step_name in names(execution_order)) {
    step_def <- dag[[step_name]]
    
    # 3. 检查前置状态
    current_state <- obj@misc$pipeline_state %||% "Raw"
    required_states <- step_def$requires %||% "Raw"
    
    if (!current_state %in% required_states && !is.null(step_def$requires)) {
      stop(sprintf("Step '%s' requires state %s, got %s",
                   step_name, paste(required_states, collapse = "/"), current_state))
    }
    
    # 4. 检查条件
    if (!is.null(step_def$condition)) {
      should_run <- step_def$condition(obj)
      if (!should_run) {
        message(sprintf("[%s] CONDITION FALSE → SKIPPING", step_name))
        if (!is.null(step_def$skip_outputs)) {
          obj@misc$pipeline_state <- step_def$skip_outputs
        }
        reports[[step_name]] <- list(step = step_name, status = "SKIPPED")
        next
      }
    }
    
    # 5. 检查并行步骤是否已完成
    if (!is.null(step_def$parallel_to)) {
      parallel_step <- dag[[step_def$parallel_to]]
      # 合并并行步骤的输出状态
    }
    
    # 6. 执行步骤
    message(sprintf("\n========== %s ==========", toupper(step_name)))
    result <- step_def$fn(obj, auto = (mode == "auto"), 
                          prev_reports = prev_reports, ...)
    
    obj <- result$obj
    reports[[step_name]] <- result$report
    prev_reports[[step_name]] <- result$report
    if (!is.null(result$llm_report)) {
      llm_reports[[step_name]] <- result$llm_report
    }
  }
  
  list(obj = obj, reports = reports, llm_reports = llm_reports)
}
```

### 5.4 与线性 runner 的对比

| 特性 | 线性 runner (`run_pipeline.R`) | DAG runner (`run_dag`) |
|------|-------------------------------|------------------------|
| 条件跳过 | 步骤内部判断，仍执行函数 | 条件为 FALSE 时完全不执行 |
| 并行执行 | 不支持 | 支持（`parallel_to`） |
| 替代方案 | 用户手动选择脚本 | `alternatives` 声明式配置 |
| 恢复 | `if (from_step <= 5)` 硬编码 | 拓扑排序自动处理依赖 |
| 复杂度 | 简单，7 步以内够用 | 15+ 步或复杂分支时必需 |

---

## 6. LLM 使用策略

### 6.1 LLM 介入时机

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Propose   │────→│  Evaluate   │────→│   Execute   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┴────────────┐
              │     Layer 2: LLM        │
              │  预飞行审查（可选）      │
              │  - 评估生物学合理性      │
              │  - 不阻塞，仅建议        │
              └─────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │     Layer 2: LLM        │
              │  事后诊断卡片（默认）    │
              │  - 解读结果              │
              │  - 跨步骤关联分析        │
              └─────────────────────────┘
```

### 6.2 预飞行 LLM 审查（轻量级）

仅在高风险决策点触发：

```r
# 仅在 BLOCK 时触发 LLM 解释
evaluation <- evaluate_qc_proposal(proposal, obj)

if (evaluation$verdict == "BLOCK") {
  # 生成 LLM 解释（可选，用于显示给用户）
  llm_context <- generate_pre_flight_context("qc", obj, proposal, evaluation)
  message("\n=== 预飞行审查 ===")
  message(llm_context)
}
```

**输出示例：**
```
=== 预飞行审查 ===
该数据集为新鲜冷冻小鼠脑组织，线粒体基因比例中位数为 25%，
这在脑组织中属于正常范围（20-35%）。

建议：将 MT% 阈值从 20% 放宽至 30%，以避免移除健康细胞。
理由：脑组织深部区域（海马、下丘脑）代谢活跃，MT% 天然较高。

[1] 接受建议    [2] 保持原阈值    [3] 手动调整
```

### 6.3 事后 LLM 诊断卡片（默认）

每步执行后生成，结构固定：

```markdown
## [LLM 诊断卡片] Step 2: QC 过滤

### 数据快照
| 指标 | 数值 |
|------|------|
| 初始 spot 数 | 3000 |
| 过滤后 spot 数 | 2550 |
| 移除比例 | 15.0% |

### 规则提案
| 参数 | 值 | 理由 |
|------|-----|------|
| min_counts | 500 | 5% 分位数 |
| max_mt | 30% | 新鲜冷冻脑组织 |

### 执行报告
| 结果 | 数值 |
|------|------|
| 状态 | **PASS** |

### 跨步骤上下文
- **load**: 状态=PASS

### LLM 分析任务
> 1. 15% 的移除比例对空间转录组数据是否合理？
> 2. 线粒体比例分布是否符合该组织类型的预期？
> 3. 被移除的 spot 是否集中在组织边缘（可能为切片伪影）？
```

### 6.4 LLM 不介入的场景

| 场景 | LLM 角色 | 原因 |
|------|---------|------|
| 分辨率推荐（基于 spot 数） | ❌ 不介入 | 硬规则足够，LLM 无额外信息 |
| q 值边界检查 | ❌ 不介入 | 数学边界，无需生物学知识 |
| MT 阈值调整 | 💡 可解释 | 需要组织类型知识 |
| 方法选择（BayesSpace vs STAGATE） | 💡 可建议 | 需要权衡速度与精度 |
| 聚类结果生物学解读 | ✅ 深度介入 | 需要领域知识 |
| 空间域与组织学对应 | ✅ 深度介入 | 需要解剖学知识 |

---

## 7. 状态管理

### 7.1 状态枚举

```r
# pipeline_states.R
VALID_STATES <- c(
  "Raw",           # 原始数据
  "Filtered",      # QC 后
  "Clean",         # 双细胞去除后（scRNA-seq）
  "Normalized",    # 归一化后
  "Integrated",    # 批次整合后
  "Clustered",     # 聚类后
  "UMAP",          # UMAP 后（与 Clustered 同时）
  "Spatial-Analyzed",  # 空间分析后
  "Domains",       # 空间域检测后
  "Deconvoluted",  # 反卷积后
  "Annotated",     # 细胞注释后（scRNA-seq）
  "Markers",       # marker 基因后（scRNA-seq）
  "Visualized"     # 可视化后
)
```

### 7.2 状态转换验证

```r
# 合法的状态转换表
VALID_TRANSITIONS <- list(
  "Raw" = c("Filtered"),
  "Filtered" = c("Clean", "Normalized"),
  "Clean" = c("Normalized"),
  "Normalized" = c("Integrated", "Clustered"),
  "Integrated" = c("Clustered"),
  "Clustered" = c("Spatial-Analyzed", "Markers", "Annotated"),
  "Spatial-Analyzed" = c("Domains", "Deconvoluted"),
  "Domains" = c("Visualized", "Deconvoluted")
)

validate_state_transition <- function(from_state, to_state) {
  allowed <- VALID_TRANSITIONS[[from_state]]
  if (is.null(allowed) || !to_state %in% allowed) {
    stop(sprintf("非法状态转换: %s → %s。合法目标: %s",
                 from_state, to_state, paste(allowed, collapse = ", ")))
  }
  TRUE
}
```

### 7.3 恢复机制

```r
resume_pipeline <- function(obj, from_step, dag, ...) {
  current_state <- obj@misc$pipeline_state
  
  # 验证当前状态是否允许从指定步骤恢复
  step_def <- dag[[from_step]]
  if (!current_state %in% step_def$requires) {
    stop(sprintf("当前状态 '%s' 无法从步骤 '%s' 恢复。需要: %s",
                 current_state, from_step, 
                 paste(step_def$requires, collapse = "/")))
  }
  
  run_dag(obj, dag, from_step = from_step, ...)
}
```

---

## 8. 实施路线图

### Phase 1: 立即实施（1-2 天）

1. **为每个步骤添加 `evaluate_*()` 守卫函数**
   - 先实现最关键的两个：QC（Step 2）和 Domain Detection（Step 7）
   - 规则：硬边界检查，不涉及 LLM

2. **修改 `run_*_step()` 包装函数**
   - 在 `execute_*()` 之前插入 `evaluate_*()`
   - 当 `verdict == "BLOCK"` 时，在 `auto=FALSE` 模式下显示警告并等待确认

### Phase 2: 短期实施（1 周）

3. **所有步骤完成 `evaluate_*()`**
   - Step 3 (Normalization): 检查 HVG 数量
   - Step 4 (Integration): 检查样本数和批次效应
   - Step 5 (Clustering): 检查分辨率范围
   - Step 6 (Spatial Analysis): 检查空间图构建

4. **LLM 预飞行审查**
   - 仅在 `verdict == "BLOCK"` 时生成简要上下文
   - 不阻塞，仅作为解释信息

### Phase 3: 中期实施（2-4 周）

5. **DAG 流程控制**
   - 定义 `pipeline_dag` 列表
   - 实现 `run_dag()` 执行器
   - 保留 `run_pipeline()` 作为兼容层（内部调用 `run_dag()`）

6. **状态机完善**
   - 添加 `VALID_STATES` 和 `VALID_TRANSITIONS`
   - 每步执行前验证状态转换
   - 添加 `validate_state()` 函数

### Phase 4: 长期优化（按需）

7. **并行执行**
   - 使用 `parallel_to` 标记独立步骤
   - 实现并行执行器（`future` / `parallel`）

8. **LLM 增强**
   - 事后诊断卡片增加生物学知识库引用
   - 预飞行审查增加置信度评分

---

## 9. 代码模板

### 9.1 完整步骤模板（R）

```r
#' Step X: [步骤名称] — 空间转录组流程（R）
#'
#' Input State:  [输入状态]
#' Output State: [输出状态]

library(Seurat)

# ───────────────────────────────────────────────────────────────────────────
# PHASE 1: PROPOSE
# ───────────────────────────────────────────────────────────────────────────

propose_xxx <- function(obj) {
  n_spots <- ncol(obj)
  
  # 硬规则推荐
  if (...) {
    param <- ...
    reason <- "..."
  } else {
    param <- ...
    reason <- "..."
  }
  
  list(
    recommendation = list(param = param),
    diagnostics = list(n_spots = n_spots),
    justification = reason,
    alternatives = list(
      option_a = "...",
      option_b = "..."
    )
  )
}

# ───────────────────────────────────────────────────────────────────────────
# PHASE 2: EVALUATE（守卫层）
# ───────────────────────────────────────────────────────────────────────────

evaluate_xxx_proposal <- function(proposal, obj) {
  # 守卫规则
  param <- proposal$recommendation$param
  
  if (param < GUARDRAIL$min || param > GUARDRAIL$max) {
    adjusted_param <- max(GUARDRAIL$min, min(param, GUARDRAIL$max))
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("参数 %.2f 超出范围 [%.2f, %.2f]，已修正为 %.2f",
                       param, GUARDRAIL$min, GUARDRAIL$max, adjusted_param),
      adjusted_params = list(param = adjusted_param)
    ))
  }
  
  # 影响预览
  if (!is.null(GUARDRAIL$max_impact)) {
    impact <- preview_impact(proposal, obj)
    if (impact$pct_affected > GUARDRAIL$max_impact) {
      return(list(
        verdict = "CAUTION",
        adjusted = FALSE,
        reason = sprintf("将影响 %.1f%% 的数据", impact$pct_affected)
      ))
    }
  }
  
  list(verdict = "PROCEED", adjusted = FALSE)
}

# ───────────────────────────────────────────────────────────────────────────
# PHASE 3: EXECUTE
# ───────────────────────────────────────────────────────────────────────────

execute_xxx <- function(obj, param, ...) {
  # 确定性执行
  obj <- do_something(obj, param)
  
  obj@misc$pipeline_state <- "[输出状态]"
  obj@misc$xxx_param <- param
  
  return(obj)
}

# ───────────────────────────────────────────────────────────────────────────
# PHASE 4: REPORT
# ───────────────────────────────────────────────────────────────────────────

report_xxx <- function(obj, proposal) {
  n_spots <- ncol(obj)
  
  status <- if (...) "WARNING" else if (...) "CAUTION" else "PASS"
  
  list(
    step = "步骤名称",
    status = status,
    metric = n_spots,
    recommendation = if (status == "PASS") "通过，继续下一步。" else "建议检查...",
    next_step = "Step Y: 下一步"
  )
}

# ───────────────────────────────────────────────────────────────────────────
# 完整步骤包装器
# ───────────────────────────────────────────────────────────────────────────

run_xxx_step <- function(obj, param = NULL, auto = FALSE,
                         use_llm = TRUE, prev_reports = list(), ...) {
  # 1. Propose
  proposal <- propose_xxx(obj)
  if (is.null(param)) param <- proposal$recommendation$param
  
  # 2. Evaluate（守卫层）
  evaluation <- evaluate_xxx_proposal(proposal, obj)
  
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    proposal$recommendation$param <- evaluation$adjusted_params$param
    param <- evaluation$adjusted_params$param
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }
  
  # 3. Execute
  if (!auto) {
    message("\n=== [步骤名称] 提案 ===")
    message(sprintf("参数: %s", param))
    message(sprintf("理由: %s", proposal$justification))
  }
  
  obj <- execute_xxx(obj, param = param, ...)
  report <- report_xxx(obj, proposal)
  
  # 4. LLM 诊断卡片
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("xxx", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }
  
  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
```

### 9.2 完整步骤模板（Python）

```python
"""Step X: [步骤名称] — 空间转录组流程（Python）

Input State:  [输入状态]
Output State: [输出状态]
"""

import numpy as np
import scanpy as sc

from llm_report import generate_llm_report

# ───────────────────────────────────────────────────────────────────────────
# PHASE 1: PROPOSE
# ───────────────────────────────────────────────────────────────────────────

def propose_xxx(adata: sc.AnnData) -> dict:
    n_spots = adata.n_obs
    
    if ...:
        param = ...
        reason = "..."
    else:
        param = ...
        reason = "..."
    
    return {
        "recommendation": {"param": param},
        "diagnostics": {"n_spots": n_spots},
        "justification": reason,
        "alternatives": {
            "option_a": "...",
            "option_b": "..."
        }
    }

# ───────────────────────────────────────────────────────────────────────────
# PHASE 2: EVALUATE（守卫层）
# ───────────────────────────────────────────────────────────────────────────

def evaluate_xxx_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    param = proposal["recommendation"]["param"]
    
    GUARDRAIL = {"min": 0.1, "max": 2.0, "max_impact": 0.8}
    
    if param < GUARDRAIL["min"] or param > GUARDRAIL["max"]:
        adjusted = max(GUARDRAIL["min"], min(param, GUARDRAIL["max"]))
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": f"参数 {param} 超出范围，已修正为 {adjusted}",
            "adjusted_params": {"param": adjusted}
        }
    
    return {"verdict": "PROCEED", "adjusted": False}

# ───────────────────────────────────────────────────────────────────────────
# PHASE 3: EXECUTE
# ───────────────────────────────────────────────────────────────────────────

def execute_xxx(adata: sc.AnnData, param: float, **kwargs) -> sc.AnnData:
    # 确定性执行
    ...
    
    adata.uns["pipeline_state"] = "[输出状态]"
    adata.uns["xxx_param"] = param
    
    return adata

# ───────────────────────────────────────────────────────────────────────────
# PHASE 4: REPORT
# ───────────────────────────────────────────────────────────────────────────

def report_xxx(adata: sc.AnnData, proposal: dict) -> dict:
    n_spots = adata.n_obs
    
    status = "PASS" if ... else "CAUTION"
    
    return {
        "step": "步骤名称",
        "status": status,
        "metric": n_spots,
        "recommendation": "通过，继续下一步。" if status == "PASS" else "建议检查...",
        "next_step": "Step Y: 下一步"
    }

# ───────────────────────────────────────────────────────────────────────────
# 完整步骤包装器
# ───────────────────────────────────────────────────────────────────────────

def run_xxx_step(adata: sc.AnnData, param: float = None,
                 auto: bool = False, use_llm: bool = True,
                 prev_reports: dict = None, **kwargs) -> dict:
    if prev_reports is None:
        prev_reports = {}
    
    # 1. Propose
    proposal = propose_xxx(adata)
    if param is None:
        param = proposal["recommendation"]["param"]
    
    # 2. Evaluate（守卫层）
    evaluation = evaluate_xxx_proposal(proposal, adata)
    
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        param = evaluation["adjusted_params"]["param"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")
    
    # 3. Execute
    if not auto:
        print("\n=== [步骤名称] 提案 ===")
        print(f"参数: {param}")
        print(f"理由: {proposal['justification']}")
    
    adata = execute_xxx(adata, param=param, **kwargs)
    report = report_xxx(adata, proposal)
    
    # 4. LLM 诊断卡片
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("xxx", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)
    
    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
```

---

## 附录：决策速查表

| 问题 | 答案 |
|------|------|
| PER 够不够用？ | 7 步以内、无复杂分支时够用。超过 10 步或需要条件跳过时升级到 PEER + DAG |
| 守卫层必须每个步骤都有吗？ | 不是。优先在高风险步骤实现：QC、Integration、Clustering、Domain Detection |
| LLM 会拖慢流程吗？ | 预飞行 LLM 只在 BLOCK 时触发。事后 LLM 卡片默认启用，可在 `auto` 模式关闭 |
| 如何保证可重复性？ | 所有参数推荐用硬规则；所有 LLM 输出只读不写；最终参数记录到 `obj@misc` |
| 用户如何覆盖自动修正？ | 守卫层修正的参数写入日志，用户可手动传入原始参数重新执行 |
