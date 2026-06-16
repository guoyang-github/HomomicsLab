# HomomicsLab 技术分享

> 基于 README.zh.md 整理，突出创新点和与通用 Agent 的对比。
> 每页以 `---` 分隔，可直接导入 Marp / Slidev / 导出 PPT。

---

## Slide 1

# HomomicsLab

**生物信息学领域的通用 Agent 操作系统**

让自然语言研究问题变成可复现、可审计、可扩展的分析工作流

---

## Slide 2

# 计算生物学的困境

研究者想做一次标准单细胞分析：

```
QC → Normalize → PCA → Cluster → Marker → 可视化
```

但现有方案各有硬伤：

| 方案 | 优势 | 致命弱点 |
|---|---|---|
| **Turnkey Pipelines** (Galaxy, nf-core) | 可复现、经过验证 | 僵化，参数一错就崩，要学 workflow 语言 |
| **Notebook 教程** (Scanpy, Seurat) | 灵活、可学习 | 碎片化、手动操作、难以规模化复现 |
| **通用 LLM Agent** (ChatGPT, Claude) | 对话自然、知识广 | 不懂生信，会幻觉包名，结果不可审计 |
| **工作流引擎** (Snakemake, Nextflow) | 可扩展、声明式 | 要专家画 DAG，对数据状态没有语义理解 |

**核心矛盾：灵活性与严谨性无法兼得。**

---

## Slide 3

# HomomicsLab 是什么？

**第四种选择：领域原生的 Agent 平台**

它同时满足三件事：
1. **听得懂自然语言**
2. **懂生物信息学领域**
3. **执行结果可复现、可审计、安全**

研究者说："分析我的 PBMC 数据"  
系统做：意图理解 → 计划生成 → 代码执行 → 技能调用 → 结果解释 → 可复现打包

输出：结果图表 + HTML 报告 + ReproducibilityBundle

---

## Slide 4

# 创新点 1：端到端分析闭环

## 从一句话到完整报告

用户输入：
> "分析我的 PBMC 数据集并找出每个 cluster 的 marker 基因"

系统自动完成：

1. **意图分析**：解析为结构化 `UserIntent`
2. **自适应规划**：从领域策略模板生成计划
3. **执行**：沙盒中运行 skill / CodeAct 代码
4. **解读**：阶段级结果分析与异常检测
5. **报告**：生成 HTML/Markdown 报告
6. **可复现性**：导出 `ReproducibilityBundle`

**创新价值**：把分散在多个工具中的步骤，压缩成一次对话。

---

## Slide 5

# 创新点 2：领域原生智能

## 生信知识内建在架构里，不是 prompt 里

### 策略模板
PlanEngine 从 `domain.yaml` 加载策略：

```yaml
phases:
  - id: qc
    skills: [scanpy_qc]
  - id: cluster
    skills: [scanpy_cluster]

state_checks:
  - condition: "batch_detected"
    action: insert
    target: integrate
    after: qc
```

### 数据状态自适应
- 检测到批次效应 → 自动注入整合步骤
- 细胞质量低 → 收紧 QC 阈值
- 已有 clusters → 跳过冗余步骤

### SkillDAG
自我进化的技能关系图，记录 `followed_by` / `alternative_to` / `conflicts_with`。

---

## Slide 6

# 创新点 3：活的能力单元

## Skill 不是插件，是有完整生命周期的能力

```
发现 → 验证 → 执行 → 进化 → 沉淀
```

### 统一格式
```
skill_id/
├── SKILL.md          # 元数据 + 输入输出 schema
├── scripts/
│   ├── python/main.py
│   └── r/main.R
└── tests/
```

### 完整生命周期
- **发现**：TF-IDF + sentence-transformers 语义搜索
- **验证**：JSON Schema 校验
- **执行**：沙盒运行，结果缓存
- **进化**：SkillDAG 记录技能关系，边从 `CANDIDATE` → `CONFIRMED`
- **沉淀**：成功 CodeAct 运行可通过 UI “保存为 Skill”

### 来源无关
内置、外部、社区、用户生成的 skill 使用完全相同的 `SKILL.md + scripts/` 格式。

---

## Slide 7

# 创新点 4：单文件领域声明

## 扩展一个组学领域 = 写一个 YAML

传统方式：改策略、改意图、改角色、改 DAG、改 SOP……5+ 个文件。

HomomicsLab：一个 `domain.yaml` 全部搞定。

```yaml
domain: metagenomics_16s
phases: [qc, denoising, taxonomy, diversity]
state_checks:
  - condition: "host_contamination > 0.1"
    action: insert
    target: dehost
intents:
  - analysis_type: metagenomics_analysis
    keywords: ["16S", "microbiome", "qiime"]
roles:
  - role_id: metagenomicist
    allowed_skills: [metagenomics_qc, metagenomics_taxonomy]
sops:
  - id: sop_16s_v1
    title: 16S Analysis SOP
```

- `homomics validate` 秒级验证
- `homomics install` 热加载，无需重启
- 可通过 Domain Marketplace 导入导出

---

## Slide 8

# 创新点 5：多层稳定性防线

## 让 Agent 从“玩具”变成“工具”

| 层级 | 防御机制 | 拦截的问题 |
|---|---|---|
| **L1 Schema** | 每个 skill 输入/输出 JSON Schema 校验 | 类型错误、缺字段、数据损坏 |
| **L2 版本锁定** | 锁定技能版本、脚本 SHA、pip 依赖、Python 版本 | “昨天还能跑” |
| **L2 回归基线** | 成功执行自动记录基线，检测后续漂移 | 技能更新导致结果变化 |
| **L3 代码安全** | 静态审计 LLM 生成代码 | 危险导入、路径遍历、shell 注入 |
| **L3 沙盒执行** | `bubblewrap`/`container` 跨进程隔离 | 危险代码影响主机 |
| **HITL 审批** | 高风险/低置信度操作需用户确认 | 关键决策人工把关 |

**创新价值**：这是把生产级数据工程的严谨性，引入到 Agent 执行中。

---

## Slide 9

# 创新点 6：完整可复现性

## 每个分析都是一份“实验记录”

`ReproducibilityBundle` 包含：
- 智能体生成的精确代码
- 带数据状态自适应的完整执行计划
- 每一次 HITL 决策
- 环境锁定（`pip freeze`、Python 版本）
- 技能版本锁定（精确版本和脚本校验和）

```
ReproducibilityBundle/
├── code/
├── plan/
├── hitl/
├── env/
└── skills/
```

**创新价值**：你得到的不只是结果，而是可以重跑、审查、发表的分析包。

---

## Slide 10

# 创新点 7：可解释，不是黑盒

## InterpretationEngine

每个主要阶段后自动生成：

- **人类可读摘要**
  > "QC 过滤了 12% 的细胞（剩余 2,531 个），在正常范围内。"

- **异常标记**
  > "高细胞过滤率：80% — 请检查数据质量"

- **可操作建议**
  > "下一步：使用 PCA 降维"

**创新价值**：用户始终知道发生了什么、为什么发生、下一步该做什么。

---

## Slide 11

# 创新点 8：数据溯源作为一等公民

## Workspace 结构

```
workspaces/{project_id}/
├── data/               # 原始数据 — 只读保护
├── intermediate/       # 带 SHA-256 校验和的步骤工件
├── outputs/            # 最终交付物
├── logs/               # 执行日志
└── .metadata/          # 工件注册表、血缘图谱、快照、version.lock
```

### 核心能力
- **LineageGraph**：从原始数据 → QC → 聚类 → DE → 图表的有向溯源
- **Snapshots**：时间点状态捕获
- **Checksum Integrity**：每个工件 SHA-256，篡改可检测

---

## Slide 12

# 创新点 9：动态智能体角色

## 不是硬编码 Agent 类，而是 YAML 配置化角色

```yaml
role_id: visualization
name: Visualization Specialist
allowed_skills: [plot_umap, plot_heatmap, plot_violin]
allowed_tools: [file_read, file_write]
permissions:
  can_execute: true
  can_spawn_specialist: false
  max_concurrent_tasks: 2
```

### 运行时模型
- **Analyst**：常驻协调者
- **Specialist**：按需生成（QC、可视化、宏基因组等）
- **Reviewer**：独立校验高风险步骤
- **Supervisor**：规划、委派、重规划

### 多智能体集群
- 并行执行独立任务
- 共识投票处理冲突
- Supervisor 广播协调上下文

---

## Slide 13

# 创新点 10：大数据与记忆化

## 生信数据不适合塞进 JSON

### DataStore
- `DataFrame` → Parquet
- `AnnData` → H5AD
- 大对象 → pickle
- API 只传轻量 `ResultReference`

### 缓存机制
- **SkillCache**：`skill_id + inputs + fingerprint` 的 SHA-256 键值记忆化
- **CodeActCache**：基于任务描述 embedding 相似度缓存生成代码

### 价值
- 长任务秒级返回
- 降低 LLM 调用成本
- API 不被大数据阻塞

---

## Slide 14

# 安全与信任模型

## 默认不信任，关键操作要审批

- 导入技能默认 `trusted=false`
- `POST /api/skills/{id}/trust` 切换信任状态
- 高风险工具（`shell_exec`、`file_write`、`file_edit`）携带 `risk_level=high`
- `HOMOMICS_INTERACTIVE_MODE=true` 要求高风险工具调用前显式批准
- `HOMOMICS_FORCE_SANDBOX=true` 使 shell/代码执行走 bubblewrap/容器沙盒

---

## Slide 15

# 深入：CBKB 结构化知识库

## 不是黑盒向量数据库

CBKB 是围绕生信分析本体构建的结构化记忆：

| 层级 | 存储内容 | 价值 |
|---|---|---|
| **ExperimentGraph** | 每个 ReproducibilityBundle 作为节点，带类型边 | 哪些过往分析用了相同 QC 策略？ |
| **ParameterLore** | 技能参数 → 结果质量映射 | PBMC 数据 `resolution=0.6` historically 效果最好 |
| **AnomalyArchive** | InterpretationEngine 检测到的异常 | 批次效应 >30% 时 Harmony 优于 scVI |
| **LabSOP** | 重复成功分析中提炼的 SOP | 实验室版本化最佳实践 |
| **SkillEvolutionLog** | SkillDAG 边状态转换历史 | QC→PCA→Cluster 已确认 47 次 |

### 关键约束
每条记录都可追溯到 `ReproducibilityBundle`、`Workspace` 产物或 `SkillDAG` 边。

---

## Slide 16

# 深入：CodeAct 与 Skill 的关系

## CodeAct 是执行基座，Skill 是能力单元

```
┌─────────────────────────────────────┐
│           CodeAct 执行基座           │
│  生成并执行 Python/R/Bash 代码       │
│  可调用 Skill / Tool / 底层库        │
└─────────────────────────────────────┘
           │           │           │
           ▼           ▼           ▼
      ┌────────┐  ┌────────┐  ┌────────┐
      │ Skill  │  │  Tool  │  │  底层库 │
      │ scanpy │  │pubmed  │  │pandas  │
      │  _qc   │  │_search │  │numpy   │
      └────────┘  └────────┘  └────────┘
```

### 为什么这样设计？
- Skill 适合高频确定性任务（快、稳定、可缓存）
- CodeAct 适合复杂/新颖任务（灵活、可组合）
- Agent 根据任务复杂度自动选择

---

## Slide 17

# 通用 LLM Agent 为什么做不好生信？

## 三个真实场景

### 场景 1：调用不存在的包
> 用户："用 scanpy 做批次效应校正"
> ChatGPT："用 `sc.pp.combat(adata, key='batch')`"
> 问题：`combat` 不是 scanpy 的公开 API，代码跑不通。

### 场景 2：忽略数据特征
> 用户："做差异表达分析"
> ChatGPT：直接写 `sc.tl.rank_genes_groups`，但不问是否有重复、是否正态分布、是否需要 pseudobulk。
> 问题：生信分析高度依赖数据状态，通用 Agent 没有 DataState 概念。

### 场景 3：结果无法复现
> ChatGPT 生成一段代码，用户复制运行后得到结果。
> 三个月后换台机器再跑，包版本变了，结果变了，原始代码也找不到了。
> 问题：没有环境锁定、没有审计追踪、没有 ReproducibilityBundle。

**根本原因：通用 Agent 没有领域知识、没有执行沙盒、没有可复现框架。**

---

## Slide 18

# 对比：与通用 LLM Agent

| 维度 | 通用 LLM Agent | HomomicsLab |
|---|---|---|
| 领域知识 | 通用，会 hallucinate 生信包名和参数 | 内置生信策略模板、SkillDAG、CBKB |
| 数据状态理解 | 无 | DataState + state_checks 驱动计划调整 |
| 执行能力 | 只生成代码，需手动复制运行 | 直接沙盒执行，返回结果和图表 |
| 可复现性 | 无环境锁定，无审计 | 完整 ReproducibilityBundle |
| 稳定性 | 无 schema/版本/回归校验 | L1/L2/L3 多层防线 |
| 可解释性 | 黑盒回答 | 每个 phase 生成摘要、异常标记、下一步建议 |
| 安全性 | 代码直接运行 | 沙盒隔离 + 代码审计 + 人工审批 |
| 扩展性 | 每个新工具都要写 prompt 或插件 | 一个 `domain.yaml` 扩展一个领域 |
| 错误处理 | 失败即止，无替代方案 | SkillDAG 找替代 skill，自动 replan |

**本质区别**：
- 通用 Agent = **会写代码的聊天机器人**
- HomomicsLab = **会执行、会审计、会进化的生信分析操作系统**

---

## Slide 19

# 对比：与传统生信平台

## Galaxy / nf-core 为什么不能替代？

| 维度 | Galaxy / nf-core | HomomicsLab |
|---|---|---|
| 使用方式 | GUI 拖拽 / 命令行 | 自然语言对话 |
| 灵活性 | 固定 workflow，参数预定义 | 根据数据状态动态调整计划 |
| 可解释性 | 黑盒 pipeline | 每个 phase 生成摘要和建议 |
| 学习曲线 | 需学平台术语 | 像和同事对话 |
| 决策捕获 | 只捕获参数 | 还捕获 LLM/Agent 决策和推理 |

**本质区别**：
- Galaxy = **给你一套工具箱，你自己组装**
- HomomicsLab = **给你一位懂领域、会动手、能解释的生信助手**

---

## Slide 20

# 总结：九大创新点

1. **端到端分析闭环**：一句话到完整报告
2. **领域原生智能**：策略模板 + 数据状态自适应 + SkillDAG
3. **活的能力单元**：Skill 有发现、验证、执行、进化、沉淀生命周期
4. **单文件领域声明**：一个 YAML 扩展一个组学领域
5. **多层稳定性防线**：Schema + 版本锁 + 回归 + 代码安全 + 沙盒 + HITL
6. **完整可复现性**：ReproducibilityBundle 捕获完整因果链
7. **可解释与溯源**：InterpretationEngine + Workspace 血缘
8. **动态角色与多智能体**：配置化角色 + 1+N 协作
9. **大数据与记忆化**：DataStore + SkillCache + CodeActCache + CBKB

---

## Slide 21

# 对用户的价值

- **更低门槛**：自然语言替代 workflow 语言
- **更高可信度**：每次执行都有校验、隔离、审计
- **更强复现性**：一键导出可重跑实验包
- **更易扩展**：YAML 配置加新领域和新技能
- **更省成本**：本地运行 + 缓存减少 LLM 调用
- **更隐私安全**：数据默认不离开本机

---

## Slide 22

# Demo 脚本建议

3 分钟演示：

1. **输入**："Analyze my PBMC data"
2. **计划**：展示 Agent 生成的分析计划
3. **执行**：SSE 进度 + phase 摘要
4. **结果**：HTML 报告、UMAP、DE 表
5. **审计**：下载 ReproducibilityBundle
6. **扩展**：Domain Marketplace 导入新领域

---

## Slide 23

# 谢谢

## Q&A
