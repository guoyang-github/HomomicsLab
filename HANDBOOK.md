# HomomicsLab 一本通：从入门到精通的领域原生智能体平台

> 适合读者：生物信息学研究者、计算生物学团队、AI  Agent 开发者、希望把自然语言转化为可复现分析工作流的产品/工程人员。
>
> 阅读建议：前四章适合零基础快速建立直觉；第五章起进入架构与进阶机制；第七章、第八章适合需要二次开发或调优的读者。

---

## 目录

1. [前言：为什么需要 HomomicsLab](#一前言为什么需要-homomicslab)
2. [HomomicsLab 是什么](#二homomicslab-是什么)
3. [核心概念：六个关键词](#三核心概念六个关键词)
4. [一次完整对话的旅程](#四一次完整对话的旅程)
5. [架构设计总览](#五架构设计总览)
6. [进阶机制](#六进阶机制)
7. [v0.5.0 关键改进](#七v050-关键改进)
8. [如何扩展 HomomicsLab](#八如何扩展-homomicslab)
9. [最佳实践与避坑指南](#九最佳实践与避坑指南)
10. [附录](#十附录)

---

## 一、前言：为什么需要 HomomicsLab

### 1.1 计算生物学的三重困境

做生物信息学分析的人，通常卡在三个极端之间：

| 方案 | 优点 | 缺点 |
|---|---|---|
| **Galaxy / nf-core 等流程管线** | 可复现、经过社区验证 | 僵化，参数稍有不匹配就报错，用户必须会说"工作流语言" |
| **Scanpy / Seurat 教程笔记本** | 灵活、易学 | 碎片化、手动操作、无法规模化复现 |
| **ChatGPT / Claude Code 等通用 LLM** | 对话自然、代码能力强 | 没有生物信息学领域知识，会幻觉化包名、忽略批次效应 |

HomomicsLab 想做的是**第四种选择**：一个既懂生物学、又懂工程执行的**领域原生智能体平台**。

### 1.2 一句话定位

> **HomomicsLab 把自然语言研究问题，转化为可复现、可审计、可扩展的分析工作流。**

它不是简单的"LLM 生成代码"，也不是僵化的固定流程，而是在"用户意图"和"领域最佳实践"之间做智能路由：

- 简单请求 → 直接生成紧凑脚本运行；
- 复杂请求 → 按领域策略拆解成计划，再选择合适技能和执行后端；
- 所有步骤 → 被记录、被验证、可复现。

---

## 二、HomomicsLab 是什么

### 2.1 从用户视角看

你是一个研究者，上传了一个 `PBMC.h5ad` 文件，然后在聊天框输入：

> "分析我的 PBMC 数据集，找出每个 cluster 的 marker 基因，并生成 UMAP 和差异表达表。"

HomomicsLab 会：

1. **理解意图**：识别出"单细胞转录组分析、聚类、marker 鉴定、可视化"。
2. **检查数据**：读取 `.h5ad` 的元数据，判断是否需要 QC、标准化、批次校正。
3. **生成计划**：不是固定 8 步流水线，而是根据数据实际状态生成必要步骤。
4. **执行**：用 CodeAct 或精选 skill 生成脚本，在沙盒中运行。
5. **返回结果**：在对话中直接展示摘要、图表、表格，文件作为附件。
6. **记录一切**：代码、计划、环境、审批决策被打包成 `ReproducibilityBundle`。

### 2.2 从开发者视角看

HomomicsLab 是一个由以下层次组成的系统：

- **前端**：React + TypeScript 聊天/工作流/设置界面；
- **后端**：FastAPI + Pydantic，异步执行；
- **智能体层**：意图分析、任务分解、计划生成、执行路由；
- **技能层**：`SKILL.md + scripts/` 格式的可插拔技能；
- **领域层**：`domain.yaml` 声明的分析策略、意图、角色、SOP；
- **执行层**：本地 / SLURM / Nextflow / nf-core 多种后端；
- **记忆与知识层**：会话记忆、语义搜索、CBKB、SkillDAG。

---

## 三、核心概念：六个关键词

理解 HomomicsLab，先掌握六个核心概念。

### 3.1 Domain（领域）

**领域 = 一个分析领域的"最佳实践模板"。**

比如"单细胞转录组"是一个领域，"空间转录组"是另一个领域。每个领域用一个 `domain.yaml` 文件描述：

- `phases`：分析阶段骨架（如 QC → 标准化 → 降维 → 聚类 → 注释）；
- `intents`：用户可能怎么描述这个领域的需求；
- `roles`：该领域需要的专家角色；
- `sops`：标准操作规程；
- `dag_seeds`：SkillDAG 的初始边；
- `data_state_schema`：该领域关心的数据状态字段。

> **重要**：在 v0.5.0 中，domain 从"默认入口"退化为"参考模板 + 治理框架"。系统优先看用户意图和数据状态，而不是硬套 phase 模板。

### 3.2 Skill（技能）

**技能 = 一个可复用的分析能力单元。**

技能采用统一格式：

```text
skills/{skill_id}/
├── SKILL.md              # YAML frontmatter + 面向智能体的文档
├── scripts/              # 参考实现脚本
│   ├── python/
│   │   ├── core_analysis.py
│   │   └── utils.py
│   └── r/
│       └── core_analysis.R
├── requirements.txt      # Python 依赖
└── tests/                # 可选测试
```

> **v0.5.0 关键变化**：skill 不再有固定入口 `run.py`。`SKILL.md` 和 `scripts/` 是**参考资料**，CodeAct 读取它们后生成任务特定的紧凑脚本。

### 3.3 Agent（智能体）

**智能体 = 执行任务的"角色化工作者"。**

HomomicsLab 不硬编码"生物信息学智能体"，而是用 YAML 配置角色：

```yaml
role_id: single_cell_analyst
name: 单细胞分析专家
allowed_skills:
  - bio-single-cell-clustering
  - bio-single-cell-annotation-celltypist
allowed_tools:
  - file_read
  - file_write
permissions:
  can_execute: true
  max_concurrent_tasks: 2
```

同一个底层引擎，可以加载不同角色：分析专家、可视化专家、质控专家、审稿人（critic）等。

### 3.4 Plan（计划）

**计划 = 从意图到执行的中间表示。**

计划不是简单的 to-do list，而是带有以下信息的结构化对象：

- `phases`：每个阶段的类型、依赖、是否必需；
- `execution_mode`：固定管线（fixed_pipeline）/ CodeAct（codeact）/ 自动（auto）；
- `data_state`：当前数据状态（样本数、细胞数、是否已 QC 等）；
- `selected_skill`：每个阶段选用的 skill。

### 3.5 Execution（执行）

**执行 = 把计划落到具体的运行环境。**

执行路径分层：

| 模式 | 说明 |
|---|---|
| **CodeAct** | LLM 生成代码并执行，skill 仅作参考 |
| **fixed_pipeline** | 严格按 phase 和 skill 执行 |
| **auto** | 系统根据 skill 覆盖度、风险信号自动选择 |

执行后端可以是：

- **Local**：本地子进程沙盒；
- **SLURM**：HPC 集群批处理；
- **Nextflow**：可复现流程；
- **nf-core**：社区精选流程。

### 3.6 Memory / Context（记忆与上下文）

**记忆让对话有连续性，而不是每次从零开始。**

- **会话记忆**：当前对话的历史消息；
- **工作记忆**：当前任务的中间结果、数据状态；
- **语义记忆**：基于向量搜索的历史知识（可选）；
- **CBKB**：领域知识库；
- **SkillDAG**：技能之间的关系图谱。

---

## 四、一次完整对话的旅程

为了建立直觉，我们跟踪一次完整请求：

> "@file:data/PA12_small.h5ad 使用 CellTypist 对免疫细胞进行自动注释，并比较注释结果与现有 all_celltype 标签的一致性。"

### 4.1 第 0 步：文件上传

文件被放到 `workspaces/{project_id}/data/`。这是只读区域，所有分析代码从这里读数据。

### 4.2 第 1 步：意图分析

`IntentAnalyzer` 解析出：

- 领域：single-cell-transcriptomics
- 任务类型：annotation + comparison
- 点名工具：CellTypist
- 输入文件：`PA12_small.h5ad`
- 目标列：`all_celltype`

### 4.3 第 2 步：数据预检（Data Preflight）

`DataPreflight` 读取 `.h5ad` 元数据：

- shape
- `.obs` 列（确认有 `all_celltype`）
- `.var` 列
- `.layers`
- 是否已归一化

结论是：数据可以直接跑 CellTypist，不需要完整 QC/标准化/聚类流水线。

### 4.4 第 3 步：任务分解

`TaskDecomposer` 生成简洁计划：

1. 读取 `PA12_small.h5ad` 并检查数据；
2. 用 CellTypist 自动注释免疫细胞；
3. 比较 predicted label 与 `all_celltype` 一致性；
4. 生成结果摘要。

> 注意：不是旧版的 8 步流水线。因为用户明确点名了 CellTypist，且数据状态允许直接执行。

### 4.5 第 4 步：执行路由

由于用户点名了具体 skill（CellTypist），系统走 `use_skill_reference` 路径：

- 读取 `bio-single-cell-annotation-celltypist/SKILL.md` 和 `scripts/`；
- 把这些作为 prompt 上下文给 CodeAct；
- CodeAct 生成一个紧凑脚本：读 h5ad → 调用 celltypist → 比较标签 → 输出结果。

### 4.6 第 6 步：结果返回

执行完成后，系统在对话中返回：

- 文字摘要（ARI / NMI / 混淆矩阵关键值）；
- 图表（可选）；
- 输出文件链接（CSV / 新的 `.h5ad`）。

### 4.7 第 7 步：记录与复现

`ReproducibilityEngine` 打包：

- 生成的代码；
- 执行计划；
- 数据状态快照；
- 环境锁定（pip freeze）；
- 技能版本与 SHA-256。

---

## 五、架构设计总览

### 5.1 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                       │
│  Chat · Workflow Canvas · Skill Manager · Settings · Domain │
├─────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                        │
│  /api/chat · /api/skills · /api/plan · /api/execution       │
├─────────────────────────────────────────────────────────────┤
│  Agent Layer                                                │
│  TurnRunner · IntentAnalyzer · TaskDecomposer · Orchestrator│
├─────────────────────────────────────────────────────────────┤
│  Planning & Reasoning                                       │
│  PlanEngine · ModeSelector · DynamicReplanning · PhaseGate  │
├─────────────────────────────────────────────────────────────┤
│  Skill & Knowledge                                          │
│  SkillLoader · SkillRuntime · SkillDAG · CBKB               │
├─────────────────────────────────────────────────────────────┤
│  Execution Foundation                                       │
│  CodeAct · Code Safety · Code Cache · DataStore             │
├─────────────────────────────────────────────────────────────┤
│  Execution Backends                                         │
│  LocalScheduler · SlurmScheduler · NextflowRunner · nf-core │
├─────────────────────────────────────────────────────────────┤
│  Persistence & Provenance                                   │
│  Workspace · Artifact Registry · Version Lock · ReproBundle │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 数据流

```text
用户消息
   ↓
IntentAnalyzer（意图 + 领域）
   ↓
DataPreflight（数据状态）
   ↓
TaskDecomposer（任务树）
   ↓
ModeSelector（执行模式：auto / fixed_pipeline / codeact）
   ↓
Orchestrator（路由到 Agent / CodeAct / Skill）
   ↓
Execution Backend（Local / SLURM / Nextflow）
   ↓
ResultInterpreter（结果摘要）
   ↓
Chat 消息 + 文件附件
   ↓
ReproducibilityBundle（复现包）
```

### 5.3 核心模块职责

| 模块 | 职责 |
|---|---|
| `agent/orchestrator.py` | 任务调度、执行路由、重试、HITL |
| `agent/task_decomposer.py` | 把意图拆成任务树 |
| `agent/plan/` | 领域策略生成、模式选择 |
| `skills/runtime.py` | 统一 skill 执行，脚本拼接 |
| `skills/loader.py` | `SKILL.md + scripts/` 加载 |
| `execution/code_act.py` | CodeAct 代码生成与执行 |
| `execution/code_safety.py` | 生成代码静态安全审计 |
| `hpc/router.py` | 根据计划规模选择执行后端 |
| `workspace/manager.py` | 项目工作空间管理 |
| `provenance/` | 血缘与复现包 |

---

## 六、进阶机制

### 6.1 SkillDAG：技能关系图谱

SkillDAG 是一个有向图，节点是 skill，边表示技能之间的关系：

- `followed_by`：A 之后通常会做 B；
- `conflicts_with`：A 和 B 不应该一起用；
- `alternative_to`：A 可以替代 B。

边的来源：

- **seed**：`domain.yaml` 中 hand-curated 的边；
- **observed**：从连续成功执行中自动学习到，经过阈值确认后升级为 `CONFIRMED`。

SkillDAG 不是计划驱动器，而是计划辅助器：帮助 planner 做技能选择、冲突检测、备选推荐。

### 6.2 CBKB：领域知识库

CBKB（Computational Biology Knowledge Base）是一个五层知识库：

1. **术语层**：统一领域术语；
2. **SOP 层**：标准操作规程；
3. **参数经验层**：参数与结果的经验关系；
4. **异常模式层**：常见错误与修复策略；
5. **最佳实践层**：领域公认的分析流程。

CBKB 通过执行历史自动策展（curation），也可以手工维护。

### 6.3 自进化（Self-Evolution）

三个自进化闭环：

| 闭环 | 机制 | 触发条件 |
|---|---|---|
| **SkillDAG 自进化** | 成功执行记录边，多次成功后升级 | 连续成功执行 |
| **CBKB 自策展** | 从成功/失败案例中提取知识 | 夜间任务或手动触发 |
| **ModeSelector 自学习** | 记录 intent → execution_mode 的统计 | 模式选择反馈 |

> 注意：对个人用户，夜间任务默认关闭，避免消耗 token/资源。

### 6.4 信任模型

技能分为四个信任等级：

| 等级 | 来源 | 执行策略 |
|---|---|---|
| **official** | 内置 | 完全信任，可本地沙盒 |
| **verified** | 人工审核通过 | 可本地沙盒，缓存可用 |
| **community** | 社区贡献 | 必须 bubblewrap/容器沙盒，无缓存 |
| **experimental** | 未验证 | 交互模式下需 HITL 审批，非交互模式拒绝 |

### 6.5 多层稳定性保障

| 层级 | 机制 |
|---|---|
| **L1 Schema Validation** | 每个 skill 输入/输出按 JSON Schema 校验 |
| **L2 Version Locking** | 项目级锁定 skill 版本、脚本 SHA、pip freeze |
| **L2 Regression Testing** | 成功执行后记录基线，后续对比检测漂移 |
| **L2 Code Safety** | LLM 生成代码静态审计，拦截危险导入和操作 |
| **L3 HITL** | 高风险工具、experimental skill 需人工审批 |

---

## 七、v0.5.0 关键改进

### 7.1 从"Domain Phase 优先"到"意图 + 数据状态优先"

旧版默认：domain template → phases → skills → 失败才 fallback CodeAct。

新版默认：用户意图 + 数据状态 → 判断能否 single-shot / 需要哪些真实步骤 → CodeAct 或精选 skill。

带来的变化：

- 简单请求不再被硬套 8 步流水线；
- 用户点名 skill 时，skill 作为参考生成紧凑脚本；
- 结果直接内联到对话中。

### 7.2 use_skill_reference

当任务满足：

- 用户明确提到具体 skill/方法；
- 非 fixed_pipeline 模式；

系统走 `use_skill_reference` 路径：CodeAct 读取 skill 的文档和脚本，生成端到端脚本。

这是 domain↔CodeAct 的干净调和：CodeAct 是底座，domain template 是增强，skill 是参考。

### 7.3 Data Preflight

执行前让 LLM 先读数据元数据（shape、obs columns、var、layers），决定：

- 是否需要 QC / 标准化 / 聚类；
- 目标列是否存在；
- 走完整 pipeline 还是 single-shot。

### 7.4 结果内联

执行完成后，`ResultInterpreter` 读取关键 CSV/JSON/txt，生成 Markdown 摘要，前端在对话中直接渲染，文件作为附件。

### 7.5 脚本拼接执行

skill 不再有固定 `run.py` 入口。`SkillRuntimeExecutor` 拼接 `scripts/` 下所有 `.py`/`.R` 文件作为参考库，让 CodeAct 或沙盒按需调用。

---

## 八、如何扩展 HomomicsLab

### 8.1 添加一个 Domain

```bash
homomics init my-domain --phases "qc,normalization,dim_reduction,clustering,annotation"
```

编辑生成的 `domain.yaml`：

```yaml
name: my-domain
description: 我的自定义分析领域
phases:
  - phase_type: qc
    required: true
  - phase_type: annotation
    required: true
intents:
  - name: run_qc
    patterns: ["qc", "quality control", "质控"]
roles:
  - role_id: my_analyst
    name: 我的分析专家
    allowed_skills: [my-skill-1, my-skill-2]
```

### 8.2 添加一个 Skill

```bash
homomics skill generate "Use CellTypist for immune cell annotation"
```

或手工创建目录：

```text
skills/my-celltypist/
├── SKILL.md
└── scripts/python/
    ├── core_analysis.py
    └── utils.py
```

`SKILL.md` 示例：

```markdown
---
name: my-celltypist
description: 使用 CellTypist 进行免疫细胞自动注释
tool_type: python
keywords: [celltypist, annotation, immune]
inputs:
  input_path:
    type: string
    required: true
  model:
    type: string
    default: Immune_All_Low.pkl
outputs:
  annotated_h5ad:
    type: string
---

# My CellTypist Skill

读取 h5ad，运行 CellTypist，返回带 predicted labels 的 adata。
```

### 8.3 调整 LLM

在 `.env` 中配置：

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

---

## 九、最佳实践与避坑指南

### 9.1 对终端用户

1. **明确点名方法**："用 CellTypist 做注释"比"做细胞注释"更容易得到精准结果。
2. **上传文件后用 `@file:` 引用**：例如 `@file:data/PA12_small.h5ad`。
3. **小数据先试本地**：默认 local 后端最省资源；大数据/多步骤才考虑 Nextflow/SLURM。
4. **interactive 模式开 sandbox**：生产环境务必 `HOMOMICS_FORCE_SANDBOX=true`。

### 9.2 对开发者

1. **重构必跑相关测试**：改 `generate_code_async` 要跑 `test_skills`+`test_execution`；改 `select_execution_backend` 要跑 `test_runtime_backend`+`test_hpc`；改 orchestrator 路由要跑 `test_orchestrator`+`test_task_decomposer`。
2. **优先改 domain.yaml 而不是 Python**：分析策略、意图、角色、SOP 尽量放在 domain 里。
3. **skill 不写固定入口**：遵循 `SKILL.md + scripts/` 新规范，不要写 `run.py`。
4. **不要提交运行时文件**：`__code_act__.py`、workspace outputs 等是运行时产物，不要提交到 git。

### 9.3 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| TODO 列表有 8 步但用户只问了一个简单问题 | 旧版 phase 模板过拟合 | v0.5.0 已修复，确保走 data preflight + intent-centric 路径 |
| 结果只返回文件路径没有摘要 | ResultInterpreter 未触发或失败 | 检查 LLM 配置，确认输出文件在工作区 outputs/ |
| skill 不被执行 | trust_level=experimental 且非交互模式 | 先 `POST /api/skills/{id}/trust` 或开启 interactive 模式 |
| 切换 session 丢失 TODO/Execution Logs | session 状态未持久化 | 检查 session store 配置和 execution state 持久化 |
| Nextflow 没触发 | 阶段数 < 8 或样本数 ≤ 100 | 调低 `HOMOMICS_WORKFLOW_NEXTFLOW_MIN_PHASES` 或确认数据规模 |

---

## 十、附录

### 10.1 常用命令

```bash
# 启动后端
cd backend && uvicorn homomics_lab.main:app --reload --port 8080

# 启动前端
cd frontend && npm run dev

# 运行后端测试
cd backend && pytest tests/ -q

# 运行 lint
make lint-backend
make lint-frontend

# 初始化领域
homomics init my-domain --phases "qc,clustering,annotation"

# 生成技能
homomics skill generate "Use CellTypist for immune cell annotation"
```

### 10.2 目录速查

| 路径 | 内容 |
|---|---|
| `backend/homomics_lab/agent/` | 智能体编排 |
| `backend/homomics_lab/skills/` | 技能运行时、加载器、DAG |
| `backend/homomics_lab/domain/domains/` | 内置领域声明 |
| `backend/homomics_lab/execution/` | CodeAct、缓存、安全审计 |
| `backend/homomics_lab/hpc/` | 调度后端 |
| `backend/homomics_lab/workspace/` | 工作空间与溯源 |
| `skills/` | 运行时技能目录 |
| `frontend/src/components/chat/` | 聊天界面 |
| `frontend/src/stores/` | Zustand 状态管理 |

### 10.3 关键配置速查

| 变量 | 说明 |
|---|---|
| `HOMOMICS_LLM_PROVIDER` | LLM 提供商 |
| `HOMOMICS_LLM_MODEL` | 模型名 |
| `HOMOMICS_FORCE_SANDBOX` | 强制沙盒 |
| `HOMOMICS_INTERACTIVE_MODE` | 交互审批 |
| `HOMOMICS_SKILL_SANDBOX_BACKEND` | 沙盒后端 |
| `HOMOMICS_WORKFLOW_NEXTFLOW_MIN_PHASES` | Nextflow 触发阈值 |
| `HOMOMICS_CODEACT_CACHE_ENABLED` | CodeAct 缓存 |
| `HOMOMICS_SKILL_CACHE_ENABLED` | Skill 结果缓存 |

---

## 结语

HomomicsLab 的核心设计哲学可以概括为一句话：

> **让领域知识成为智能体的增强，而不是枷锁。**

它用 domain.yaml 保存最佳实践，用 SKILL.md + scripts/ 沉淀技能，用 CodeAct 保持通用灵活性，用多层稳定性保障和复现机制保证可信度。

对于小白，把它当成一个"会写代码、会查文献、会记笔记的生物信息学助手"即可；对于进阶用户，它是一个可扩展、可审计、可进化的领域原生 Agent 平台。
