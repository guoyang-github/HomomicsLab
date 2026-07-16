# HomomicsLab 一本通：从入门到精通的领域原生智能体平台

> 适合读者：生物信息学研究者、计算生物学团队、AI  Agent 开发者、希望把自然语言转化为可复现分析工作流的产品/工程人员。
>
> 阅读建议：前四章适合零基础快速建立直觉；第五章起进入架构与进阶机制；第七章、第八章适合需要二次开发或调优的读者。

---

## 目录

1. [前言：为什么需要 HomomicsLab](#一前言为什么需要-homomicslab)
2. [HomomicsLab 是什么](#二homomicslab-是什么)
3. [设计哲学与核心原则](#三设计哲学与核心原则)
4. [核心概念：六个关键词](#四核心概念六个关键词)
5. [一次完整对话的旅程](#五一次完整对话的旅程)
6. [架构设计总览](#六架构设计总览)
7. [进阶机制](#七进阶机制)
8. [v0.5.0 关键改进](#八v050-关键改进)
9. [如何扩展 HomomicsLab](#九如何扩展-homomicslab)
10. [最佳实践与避坑指南](#十最佳实践与避坑指南)
11. [附录](#十一附录)

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

## 三、设计哲学与核心原则

在深入概念之前，先理解 HomomicsLab 为什么这样设计。这些原则贯穿整个架构：

### 3.1 领域知识是增强，不是枷锁

早期设计曾把 `domain.yaml` 的 phase 模板作为默认入口，导致简单请求也被拆成 8 步流水线。v0.5.0 修正为：

> **CodeAct 是通用底座，domain 是增强，skill 是参考。**

- 用户意图明确且数据状态允许时，直接 single-shot 执行；
- 用户需要领域指导时，domain 提供策略骨架；
- 用户点名具体 skill 时，skill 作为 prompt 参考而不是黑箱入口。

### 3.2 数据状态驱动计划

计划不是从模板复制出来的，而是根据数据实际状态动态生成的。系统会读数据的 shape、列、层信息，决定跳过哪些步骤、注入哪些步骤。

### 3.3 可审计优先于方便

每个决策、每段代码、每次人工审批都被记录。宁可多一步记录，也要保证事后能复现、能追责、能学习。

### 3.4 信任是分级而不是二元的

不是"可信/不可信"，而是 `official → verified → community → experimental` 四级，对应不同的沙盒策略、缓存策略和 HITL 策略。

### 3.5 渐进式披露

Skill 的加载分三层：

1. **Discovery**：只读 frontmatter（名字、描述、runtime 类型）；
2. **Activation**：读完整 SKILL.md body + requirements；
3. **Execution**：读 scripts/ 下参考脚本。

这样启动时 registry 轻量，执行时才加载完整内容。

---

## 四、核心概念：六个关键词

理解 HomomicsLab，先掌握六个核心概念。

### 4.1 Domain（领域）

**领域 = 一个分析领域的"最佳实践模板"。**

比如"单细胞转录组"是一个领域，"空间转录组"是另一个领域。每个领域用一个 `domain.yaml` 文件描述：

- `phases`：分析阶段骨架（如 QC → 标准化 → 降维 → 聚类 → 注释）；
- `intents`：用户可能怎么描述这个领域的需求；
- `roles`：该领域需要的专家角色；
- `sops`：标准操作规程；
- `dag_seeds`：SkillDAG 的初始边；
- `data_state_schema`：该领域关心的数据状态字段。

> **重要**：在 v0.5.0 中，domain 从"默认入口"退化为"参考模板 + 治理框架"。系统优先看用户意图和数据状态，而不是硬套 phase 模板。

**Domain 的工作原理**：

1. `DomainLoader` 扫描 `backend/homomics_lab/domains/` 下的 `domain.yaml`；
2. 启动时只加载 frontmatter 和策略骨架，保持轻量；
3. `IntentAnalyzer` 根据用户消息中的关键词匹配 domain 的 `intents`；
4. `PlanEngine` 在需要时读取 domain 的 `phases` 和 `sops`，作为生成计划的参考；
5. 最终计划由 `TaskDecomposer` 根据意图 + 数据状态 + domain 模板共同决定。

**设计理由**：把领域知识外置到 YAML，而不是写死在 Python 里，使得生物信息学专家可以不修改代码就调整分析策略。

### 4.2 Skill（技能）

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

**Skill 的渐进式加载**：

| 层级 | 加载内容 | 时机 | 目的 |
|---|---|---|---|
| **Discovery** | frontmatter（id、描述、runtime 类型、keywords） | 启动/注册时 | registry 轻量 |
| **Activation** | 完整 SKILL.md body + requirements | 第一次执行前 | 获得详细文档 |
| **Execution** | scripts/ 下参考脚本 | 执行时 | 给 CodeAct 或沙盒作参考 |

**Skill 的执行方式**：

- **有 scripts 的 python/r/mixed skill**：`SkillRuntimeExecutor` 拼接所有 `.py`/`.R` 脚本，加入 `sys.path`，在沙盒中运行；
- **无 scripts 的 skill**：视为 agentic/knowledge skill，由 `AgentSkillExecutor` 做 LLM tool-calling；
- **被点名的 skill**：通过 `use_skill_reference` 路径，把 SKILL.md + scripts 作为 prompt 上下文，让 CodeAct 生成紧凑脚本。

**为什么去掉 run.py？**

旧规范假设每个 skill 有固定入口，导致：
- skill 作者必须写适配运行时的 wrapper；
- 系统把 skill 当黑箱，难以组合多个 skill；
- 简单请求被不必要的 pipeline 步骤拖累。

新规范让 skill 成为"参考素材"，LLM 可以按需挑选、组合、改写其中的代码片段。

### 4.3 Agent（智能体）

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

### 4.4 Plan（计划）

**计划 = 从意图到执行的中间表示。**

计划不是简单的 to-do list，而是带有以下信息的结构化对象：

- `phases`：每个阶段的类型、依赖、是否必需；
- `execution_mode`：固定管线（fixed_pipeline）/ CodeAct（codeact）/ 自动（auto）；
- `data_state`：当前数据状态（样本数、细胞数、是否已 QC 等）；
- `selected_skill`：每个阶段选用的 skill。

**Plan 的生成流程**：

1. `IntentAnalyzer` 输出 `UserIntent`（domain、scope、action、entities）；
2. `PlanEngine` 根据 domain 的 strategy templates 生成候选 plan；
3. `ModeSelector` 结合 skill 覆盖度、风险信号、历史统计选择 `execution_mode`；
4. `TaskDecomposer` 把 plan 转成 `TaskTree`，每个节点带 `skills_required`、`parameters`、`retry_policy`；
5. `DataPreflight` 在必要时读数据元数据，进一步精简或调整 plan。

**Plan 不是静态的**：执行过程中，`PhaseGateEvaluator` 会检查每个阶段的结果，如果数据状态变化（如发现低质量细胞），`DynamicReplanningEngine` 可以插入新阶段或跳过后续阶段。

### 4.5 Execution（执行）

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

**执行路由决策（Orchestrator 内部）**：

```
收到 TaskNode
   ↓
execution_mode == fixed_pipeline?
   ├─ 是 → 走 curated skill runtime
   ↓
use_skill_reference == True?
   ├─ 是 → _execute_task_with_skill_reference
   ↓
execution_mode == codeact?
   ├─ 是 → _execute_task_codeact
   ↓
否则 → supervisor / agent 执行
```

**执行后端选择（hpc/router.py）**：

```python
if nextflow_enabled and n_phases >= 8 and effective_samples > 100:
    return "nextflow"
if slurm_available and (effective_samples > 10 or n_phases > 2):
    return "slurm"
return "local"
```

> 默认值：Nextflow 需要 ≥8 个 phase 且 >100 个 effective samples/cells。这保证小分析不会为了启动 Nextflow 而付出额外开销。

### 4.6 Memory / Context（记忆与上下文）

**记忆让对话有连续性，而不是每次从零开始。**

- **会话记忆**：当前对话的历史消息；
- **工作记忆**：当前任务的中间结果、数据状态；
- **语义记忆**：基于向量搜索的历史知识（可选）；
- **CBKB**：领域知识库；
- **SkillDAG**：技能之间的关系图谱。

**上下文压缩机制**：

长对话会触发 token 上限。`ContextEngine` 会：

1. 提取关键决策点和结果摘要；
2. 把详细执行日志移到 `DataStore`；
3. 保留"用户要求什么、系统决定什么、结果是什么"的压缩表示。

**DataState 是工作记忆的核心**：

```python
@dataclass
class DataState:
    has_qc: bool = False
    low_quality: bool = False
    n_samples: Optional[int] = None
    n_cells: Optional[int] = None
    data_type: Optional[str] = None
    domain_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

每个 phase 执行后，系统会更新 `DataState`，下一阶段根据最新状态做决策。

---

## 五、一次完整对话的旅程

为了建立直觉，我们跟踪一次完整请求：

> "@file:data/PA12_small.h5ad 使用 CellTypist 对免疫细胞进行自动注释，并比较注释结果与现有 all_celltype 标签的一致性。"

下面把每一步拆开，说明系统内部调用了什么、生成了什么状态、为什么要这样设计。

### 5.1 第 0 步：文件上传与 Workspace 准备

用户把 `PA12_small.h5ad` 拖到前端，文件通过 `/api/projects/{project_id}/files` 进入后端。

**发生了什么**：

1. `WorkspaceManager` 确保 `workspaces/{project_id}/data/` 存在；
2. 文件被写入 `data/` 目录，这个目录对分析代码是**只读**的；
3. `ArtifactRegistry` 记录文件元数据：原始文件名、SHA-256、大小、上传时间；
4. 如果文件是 `.h5ad`，系统异步做一次轻量索引，记录 `n_obs`、`n_vars`、`.obs` 列名等，供后续快速查询。

**设计理由**：把输入数据放在只读区，可以防止分析脚本误删或覆盖原始数据；同时让任何复现包都能明确知道“分析从哪份原始数据开始”。

### 5.2 第 1 步：意图分析（IntentAnalyzer）

用户消息进入后端后，首先由 `IntentAnalyzer` 解析。它不是简单关键词匹配，而是一个 LLM 驱动的分类器。

**LLM 调用结构**：

```text
system: 你是一名生物信息学意图分析器。请从用户消息中提取：
        - domain（单细胞转录组 / 空间转录组 / 通用）
        - action（annotate / cluster / describe / compare / ...）
        - entities（文件名、方法名、目标列名）
        - scope（single-shot / pipeline / clarification）
        输出 JSON，不要解释。

user:   @file:data/PA12_small.h5ad 使用 CellTypist 对免疫细胞进行自动注释，
        并比较注释结果与现有 all_celltype 标签的一致性。
```

**输出示例**：

```json
{
  "domain": "single-cell-transcriptomics",
  "action": ["annotate", "compare"],
  "entities": {
    "files": ["data/PA12_small.h5ad"],
    "methods": ["CellTypist"],
    "target_column": "all_celltype"
  },
  "scope": "single-shot",
  "named_skill": "bio-single-cell-annotation-celltypist"
}
```

**状态更新**：

- `UserIntent` 对象被写入会话工作记忆；
- 如果 `scope == "clarification"`，系统不会进入执行，而是返回澄清问题；
- 如果识别到 `@file:` 引用，`FileResolver` 会把相对路径解析为绝对路径。

**为什么用 LLM 而不是关键词**：关键词无法区分“用 CellTypist 注释”和“用 SingleR 注释”，也无法处理“帮我看看这份数据”这种模糊请求。LLM 分类器让意图识别可泛化。

### 5.3 第 2 步：数据预检（DataPreflight）

在生成计划之前，系统先读数据元数据，决定是否需要完整流水线。

**读取什么**：

```python
{
  "format": "h5ad",
  "shape": [2700, 32738],
  "obs_columns": ["all_celltype", "n_genes_by_counts", "total_counts", ...],
  "var_columns": ["gene_ids", "feature_types"],
  "layers": ["counts", "log1p"],
  "obsm_keys": ["X_pca", "X_umap"],
  "uns_keys": ["celltypist_overdispersion", ...],
  "x_approx_max": 9.2
}
```

读取方式：对 `.h5ad` 使用 `anndata.read_h5ad(path, backed="r")`，只读索引和元数据，不加载表达矩阵。

**LLM 决策调用**：

```text
system: 你是生物信息学工作流规划器。只输出 JSON。

user:   用户请求：使用 CellTypist 对 PA12_small.h5ad 中的免疫细胞做自动注释，
        并比较 predicted label 与 all_celltype。
        文件元数据：...
        请决定最小必要步骤，以及可以跳过哪些 phase。
```

**返回的 PreflightResult**：

```python
PreflightResult(
    skip_phases=["qc", "doublet_removal", "dim_reduction", "clustering"],
    required_steps=[
        "load data",
        "run CellTypist annotation",
        "compare predicted labels with all_celltype",
        "summarize results"
    ],
    suggested_input_layer="log1p",
    target_column="all_celltype",
    target_column_exists=True,
    needs_annotation=True,
)
```

**失败回退**：如果 LLM 未配置或调用失败，`DataPreflight` 会退到启发式规则（关键词 + 元数据判断），保证系统在无 LLM 时仍能工作。

**设计理由**：这一步是 v0.5.0 从“模板驱动”转向“数据驱动”的关键。它让系统能回答“用户真的需要做 QC 吗？”这个问题，而不是无条件执行 domain.yaml 里的 8 个 phase。

### 5.4 第 3 步：任务分解（TaskDecomposer）

`TaskDecomposer` 把意图 + PreflightResult 转成一棵 `TaskTree`。

**TaskNode 的结构**：

```python
@dataclass
class TaskNode:
    id: str
    title: str                 # 给用户看的 TODO 标题
    description: str           # 内部说明
    phase_type: Optional[str]  # 对应的 domain phase（可为空）
    skills_required: List[str] # 候选 skill
    dependencies: List[str]    # 依赖的其他节点
    parameters: Dict[str, Any] # 运行参数
    retry_policy: RetryPolicy  # 重试策略
```

**本例生成的 TaskTree**：

```text
root
├── node-1: 读取 PA12_small.h5ad 并验证数据
├── node-2: 使用 CellTypist 自动注释免疫细胞
│   └── depends on node-1
├── node-3: 比较 predicted labels 与 all_celltype
│   └── depends on node-2
└── node-4: 生成结果摘要
    └── depends on node-3
```

**TODO 标题的生成原则**：标题来自用户原始消息中的“动词 + 目标”，而不是 domain phase。例如：

- 旧版：`1. data_io 2. qc 3. normalization 4. dim_reduction 5. clustering 6. annotation`
- 新版：`1. 读取 PA12_small.h5ad 并检查数据 2. 用 CellTypist 自动注释免疫细胞 3. 比较 predicted label 与 all_celltype 一致性 4. 生成结果摘要`

**为什么这样设计**：TODO 是用户理解执行进度的窗口。它应该反映用户的目标，而不是系统的内部实现阶段。

### 5.5 第 4 步：模式选择（ModeSelector）

`ModeSelector` 决定本次执行走 `codeact`、`fixed_pipeline` 还是 `auto`。

**决策因素**：

| 信号 | 影响 |
|---|---|
| 用户明确点名 skill/方法 | 倾向 `codeact` + `use_skill_reference` |
| `execution_mode == fixed_pipeline`（来自 domain 或用户指定） | 强制 `fixed_pipeline` |
| skill 覆盖度低 / 风险高 | 倾向 `codeact` 或需要 HITL |
| 数据量大 / phase 多 | 倾向后端调度（SLURM/Nextflow） |
| 历史统计（`mode_selection_lore`） | 当样本足够时作为先验 |

**本例决策**：用户明确点名 CellTypist，且 Preflight 显示可以 single-shot → 选择 `codeact` + `use_skill_reference`。

**设计理由**：模式选择不是二选一开关，而是把“用户意图强度、数据状态、历史经验”综合起来的决策点。它让系统既能在简单任务上像 kimi code 一样灵活，又能在复杂任务上保持领域管线的可审计性。

### 5.6 第 5 步：执行路由（Orchestrator）

`Orchestrator` 拿到 `TaskTree` 和 `execution_mode` 后，开始逐节点执行。

**路由逻辑**：

```text
收到 TaskNode
   ↓
execution_mode == fixed_pipeline?
   ├─ 是 → 走 curated skill runtime（按 phase 严格调用 skill 脚本）
   ↓
用户点名了具体 skill 且非 fixed_pipeline?
   ├─ 是 → use_skill_reference 路径：把 SKILL.md + scripts/ 注入 prompt，
   │       让 CodeAct 生成端到端脚本
   ↓
execution_mode == codeact?
   ├─ 是 → _execute_task_codeact（通用代码生成）
   ↓
否则 → supervisor / agent 执行
```

**本例执行细节**：

1. `Orchestrator` 读取 `bio-single-cell-annotation-celltypist/SKILL.md` 和 `scripts/python/*.py`；
2. 把这些内容格式化成 prompt 上下文：

```text
system: 你是一名生物信息学分析代码生成专家。请参考下面的 skill 文档和脚本，
        为用户请求生成一个紧凑、可运行的 Python 脚本。
        [SKILL.md 内容]
        [scripts/ 内容]

user:   读取 data/PA12_small.h5ad，用 CellTypist 注释免疫细胞，
        比较 predicted labels 与 all_celltype 列的一致性，输出 CSV 和图表。
        输入层建议：log1p
```

3. CodeAct 生成脚本，脚本被写入 `workspaces/{project_id}/intermediate/`；
4. 脚本在沙盒中运行（默认 `local` 子进程或 `bubblewrap`）；
5. 运行过程中产生 `progress_event`，通过 WebSocket 推送到前端；
6. 如果失败，进入自我修正循环：把 stderr 给 LLM，生成修复后的脚本，最多重试 3 次。

**进度事件示例**：

```json
{
  "type": "progress",
  "actor": "codeact:bio-single-cell-annotation-celltypist",
  "step": "run CellTypist",
  "status": "running",
  "message": "正在运行 CellTypist 注释..."
}
```

### 5.7 第 6 步：结果解释与内联（ResultAssembler）

脚本运行完成后，得到一组输出文件（CSV、.h5ad、PNG 等）。系统不会直接把文件路径甩给用户，而是由 `ResultAssembler` 生成对话摘要。

**做了什么**：

1. 读取关键输出文件（如 `annotation_report.csv`、`confusion_matrix.png`）；
2. 把文件路径、前 50 行数据、图表描述交给 LLM；
3. LLM 生成 Markdown 摘要：

```markdown
## CellTypist 注释结果摘要

- 总细胞数：2,700
- 成功注释细胞：2,698（99.9%）
- 与 all_celltype 一致性（ARI）：0.73
- 主要差异：CD4 T cell 被细分为 Naive CD4 T 和 Memory CD4 T

文件：
- annotated.h5ad — 带 predicted labels 的完整数据
- comparison_report.csv — 标签对比表
```

4. 前端把 Markdown 渲染为聊天消息，文件作为可下载附件。

**设计理由**：用户不应该离开对话去翻 outputs/ 目录。结果内联让对话成为主要交互界面，文件只是附件。

### 5.8 第 7 步：持久化与复现（Provenance & ReproBundle）

一次成功执行结束后，系统做三件事：

1. **ExecutionTrace**：把 trace_id、session_id、状态、节点执行记录写入 `execution_traces` 表；
2. **DataState 更新**：标记 `has_annotation=True`、`annotated_cell_count=2698` 等；
3. **ReproducibilityBundle**：打包以下内容到 `workspaces/{project_id}/.metadata/bundles/{bundle_id}/`：

```text
bundle/
├── code/
│   └── generated_analysis.py          # 本次生成的完整脚本
├── plan/
│   └── plan.json                      # TaskTree + execution_mode
├── data_state/
│   └── data_state.json                # 执行前后的 DataState 快照
├── environment/
│   └── requirements.lock.txt          # pip freeze
├── skills/
│   └── bio-single-cell-annotation-celltypist/
│       ├── SKILL.md
│       └── scripts/                   # 执行时的脚本副本
├── inputs/
│   └── PA12_small.h5ad.sha256         # 原始数据校验
└── manifest.json                      # 总清单
```

**设计理由**：可复现性不是锦上添花，而是科学研究的基础。Bundle 让任何第三方都能在相同环境下重跑同一段分析。

### 5.9 状态流转与前端同步

整个旅程中的状态变化可以通过下图理解：

```text
用户输入
   │
   ▼
[IntentAnalyzer] ──UserIntent──▶ 前端显示 "思考中..."
   │
   ▼
[DataPreflight] ──PreflightResult──▶ 更新 TODO（4 步）
   │
   ▼
[TaskDecomposer] ──TaskTree──▶ TODO 细化、依赖连线
   │
   ▼
[ModeSelector] ──execution_mode──▶ 显示执行模式标签
   │
   ▼
[Orchestrator] ──progress_event──▶ 实时更新 TODO 状态 / Execution Logs
   │
   ▼
[ResultAssembler] ──chat_message──▶ 对话中展示摘要 + 附件
   │
   ▼
[Provenance] ──bundle_id──▶ 可点击的复现包链接
```

前端通过 WebSocket 订阅 session 事件，因此切换 session 再切回来后，系统会从 `session_store` 和 `execution_traces` 恢复当前状态，而不是显示空白欢迎页。

---

## 六、架构设计总览

### 6.1 分层架构与每层职责

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

**为什么这样分层**：

- **Frontend / API 分离**：前端只负责展示和状态订阅，所有决策在后端完成，保证多客户端一致性。
- **Agent Layer 与 Planning 分离**：Agent 负责“怎么执行”，Planning 负责“要不要改计划”。这样 replanning 不会污染执行代码。
- **Skill & Knowledge 独立**：技能和知识库是扩展点，它们不依赖具体执行后端，可以被 CodeAct、Agent、nf-core 多种消费者使用。
- **Execution Foundation 与 Backends 分离**：CodeAct、缓存、安全审计是通用能力；Local / SLURM / Nextflow 是部署相关能力，二者解耦。

### 6.2 数据流深度解析

一条用户消息从进入系统到返回结果，经过以下阶段：

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
ResultAssembler（结果摘要）
   ↓
Chat 消息 + 文件附件
   ↓
ReproducibilityBundle（复现包）
```

**关键设计点**：

1. **每个阶段都产生一个结构化对象**：`UserIntent` → `PreflightResult` → `TaskTree` → `PlanResult` → `ExecutionResult` → `ChatMessage`。对象之间不共享可变字典，减少状态污染。
2. **阶段之间可以中断**：如果 `DataPreflight` 发现文件不存在，系统直接返回错误，不会进入 TaskDecomposer。
3. **事件与数据分离**：执行过程中产生的日志、进度事件走 WebSocket；最终状态写入数据库。这样即使前端断开，执行也能继续。

### 6.3 核心模块职责与调用关系

| 模块 | 职责 | 主要调用方 |
|---|---|---|
| `agent/turn_runner.py` | 单轮对话的总控：调意图分析、执行、结果组装 | `api/chat.py` |
| `agent/intent/analyzer.py` | 解析用户意图，输出 `UserIntent` | `TurnRunner` |
| `agent/data_preflight.py` | 读数据元数据，决定最小必要步骤 | `TurnRunner` |
| `agent/task_decomposer.py` | 把意图拆成任务树 | `TurnRunner` |
| `agent/plan/mode_selector.py` | 选择执行模式 | `TurnRunner` / `PlanEngine` |
| `agent/orchestrator.py` | 任务调度、执行路由、重试、HITL | `TurnRunner` |
| `agent/plan/replanning.py` | 根据执行结果动态调整计划 | `Orchestrator` / `PhaseGateEvaluator` |
| `agent/phase_gate.py` | 阶段结束后检查数据状态，决定是否继续 | `Orchestrator` |
| `skills/runtime.py` | 统一 skill 执行，脚本拼接 | `Orchestrator` |
| `skills/loader.py` | `SKILL.md + scripts/` 加载与缓存 | `SkillRegistry` |
| `skills/skill_dag.py` | 技能关系图与边状态机 | `PlanEngine` / `Retriever` |
| `execution/code_act.py` | CodeAct 代码生成与执行 | `Orchestrator` |
| `execution/code_safety.py` | 生成代码静态安全审计 | `CodeAct` |
| `execution/code_cache.py` | CodeAct 脚本缓存 | `CodeAct` |
| `hpc/router.py` | 根据计划规模选择执行后端 | `Orchestrator` |
| `workspace/manager.py` | 项目工作空间管理 | 多处 |
| `provenance/repro_bundle.py` | 生成复现包 | `Orchestrator` |
| `context/engine.py` | 长对话上下文压缩 | `TurnRunner` |

**调用链示例**：

```text
/api/chat POST
    └── TurnRunner.run_turn()
        ├── IntentAnalyzer.classify()
        ├── DataPreflight.run()
        ├── TaskDecomposer.decompose()
        ├── ModeSelector.select()
        └── Orchestrator.execute_tree()
            ├── for each TaskNode:
            │   ├── select backend (hpc/router.py)
            │   ├── CodeAct / SkillRuntime / Agent
            │   ├── PhaseGateEvaluator.check()
            │   └── DynamicReplanningEngine.adjust() if needed
            ├── ResultAssembler.summarize()
            └── Provenance.record_bundle()
```

### 6.4 异步与并发模型

HomomicsLab 后端基于 FastAPI + `asyncio`：

- **API 进程**：处理 HTTP / WebSocket 请求，本身不执行长时间计算；
- **Worker**：执行实际任务（CodeAct、skill、HITL 等待）。可以是内存队列（默认）或 Redis + 独立 worker；
- **Job 状态机**：`PENDING → RUNNING → COMPLETED / FAILED / AWAITING_EVENT → RESUMED`。

**为什么要分离 API 和 Worker**：

- 分析任务可能跑几分钟到几小时，不能占住 HTTP 连接；
- API 进程可以水平扩展，worker 可以按队列长度扩容；
- 即使前端关闭，任务仍在 worker 中继续执行。

**并发控制**：

- `Orchestrator` 默认顺序执行 TaskTree 节点（按依赖拓扑），但可以配置并行执行无依赖节点；
- 每个项目有独立的 workspace，避免多项目文件冲突；
- 高风险操作通过 `PersistentApprovalStore` 串行化审批。

### 6.5 错误处理与重试设计

系统在五层做错误处理：

| 层级 | 策略 |
|---|---|
| **LLM 调用层** | 超时、格式错误、空返回自动重试 3 次，退回到启发式/静态 fallback |
| **代码执行层** | CodeAct 失败时把 stderr 给 LLM，自我修正最多 3 次 |
| **任务节点层** | 每个 TaskNode 有 `retry_policy`（次数、退避、是否允许跳过） |
| **计划层** | `DynamicReplanningEngine` 可在失败后插入修复步骤（如先 QC 再注释） |
| **HITL 层** | 高风险操作或 experimental skill 暂停，等待用户审批后继续 |

**设计原则**：不是“失败就报错”，而是“失败时把上下文交给 LLM 或用户，做最小代价恢复”。

### 6.6 扩展性与部署权衡

**无状态 vs 有状态**：

- API 进程是无状态的，任意数量实例都可以；
- Worker 是有状态的（持有运行时文件、沙盒进程），通常按队列任务数量扩容；
- 共享存储（S3/MinIO 或 NFS）和共享数据库（PostgreSQL）是水平扩展的前提。

**后端选择阈值**（可在 `hpc/router.py` 配置）：

```python
if nextflow_enabled and n_phases >= 8 and effective_samples > 100:
    return "nextflow"
if slurm_available and (effective_samples > 10 or n_phases > 2):
    return "slurm"
return "local"
```

**为什么默认阈值这样设**：

- Nextflow 启动开销大，只有多阶段、大样本才划算；
- SLURM 适合中等规模批处理；
- 本地执行对小数据最快，也最适合快速迭代。

---

## 七、进阶机制

### 7.1 SkillDAG：技能关系图谱与边状态机

SkillDAG 是一个有向图，节点是 skill，边表示技能之间的关系：

- `followed_by`：A 之后通常会做 B；
- `conflicts_with`：A 和 B 不应该一起用；
- `alternative_to`：A 可以替代 B。

**边的生命周期**：

```text
SEED ──▶ CANDIDATE ──▶ CONFIRMED
              │
              ▼
         DEPRECATED / REJECTED
```

| 状态 | 含义 | 来源 |
|---|---|---|
| **SEED** | `domain.yaml` 中 hand-curated 的初始边 | 人工 |
| **CANDIDATE** | 从执行历史中观察到，但尚未满足确认阈值 | 自动学习 |
| **CONFIRMED** | 连续成功次数达到阈值，且零失败 | 自动升级 |
| **DEPRECATED** | 后续失败次数超过阈值，边不再被推荐 | 自动降级 |
| **REJECTED** | 与 seed 冲突或被人工拒绝 | 人工/冲突检测 |

**升级规则**（来自 `skills/skill_dag.py`）：

```text
if edge.source == "observed" and edge.consecutive_successes >= threshold:
    edge.status = CONFIRMED
```

**SkillDAG 在规划中的作用**：

1. **技能推荐**：当用户完成 A 后，系统推荐 `followed_by` 的 B；
2. **冲突检测**：如果计划同时包含 `conflicts_with` 的 A 和 B， planner 会标红并提示；
3. **备选推荐**：如果 A 失败，系统找 `alternative_to` 的 skill 作为 fallback；
4. **不是计划驱动器**：SkillDAG 只给 planner 提供参考，最终计划仍由意图 + 数据状态决定。

**设计理由**：把“技能之间有什么关系”沉淀为可演化的数据结构，让系统能从成功案例中学习，而不是靠硬编码规则。

### 7.2 CBKB：计算生物学知识库的五层结构

CBKB（Computational Biology Knowledge Base）不是简单的文档库，而是一个围绕实验溯源构建的知识系统：

| 层级 | 内容 | 示例 |
|---|---|---|
| **1. Experiment Graph** | 每次分析生成的 `ReproducibilityBundle` 作为节点，节点之间用血缘边连接 | `bundle_A` → `shares_data` → `bundle_B` |
| **2. Parameter Lore** | 记录“参数 → 结果质量”映射 | `n_pcs=30` 时 UMAP 批次效应最小 |
| **3. Anomaly Archive** | 结构化记录每次 phase-level 异常及修复建议 | `qc` 阶段线粒体比例过高 → 建议阈值 5%–10% |
| **4. Lab SOP** | 从重复成功案例中蒸馏出的标准操作规程 | “PBMC 标准分析流程 v2.1” |
| **5. Skill Evolution Log** | SkillDAG 边状态变化的完整历史 | `A → B` 从 CANDIDATE 升级为 CONFIRMED |

**知识如何进入 CBKB**：

1. **seed**：`domain.yaml` 中的 SOP 和 `knowledge/seed.py` 手工导入；
2. **curation**：`knowledge/curator.py` 夜间扫描成功/失败案例，提取 Parameter Lore 和 Anomaly Archive；
3. **execution feedback**：每次执行成功后，把参数和结果写入 Parameter Lore。

**查询方式**：planner 在执行前可以查询 CBKB：

- “我之前对这份数据用过什么 QC 阈值？”
- “CellTypist 在这个数据集上表现如何？”
- “有没有和当前异常相似的修复建议？”

> 注意：对个人用户，夜间 curation 默认关闭，避免消耗 token/资源。

### 7.3 自进化（Self-Evolution）闭环

HomomicsLab 有三个自进化闭环，它们相互独立但共享执行历史数据：

| 闭环 | 输入 | 输出 | 触发条件 |
|---|---|---|---|
| **SkillDAG 自进化** | 成功/失败的 skill 转换记录 | 边的 CANDIDATE → CONFIRMED / DEPRECATED | 连续成功执行 |
| **CBKB 自策展** | ReproBundle、执行日志、异常记录 | Parameter Lore、Lab SOP、Anomaly Archive | 夜间任务或手动触发 |
| **ModeSelector 自学习** | intent 特征 → execution_mode 结果 | `mode_selection_lore` 统计先验 | 每次模式选择反馈 |

**SkillDAG 自进化流程**：

```text
执行成功：skill A → skill B
   │
   ▼
查找或创建边 A --followed_by--> B
   │
   ▼
consecutive_successes += 1
   │
   ▼
if consecutive_successes >= seed_observed_promotion_threshold:
   status = CONFIRMED
   source = "observed"
```

**失败降级流程**：

```text
执行失败：skill A → skill B
   │
   ▼
consecutive_successes = 0
failures += 1
   │
   ▼
if failures >= deprecation_threshold:
   status = DEPRECATED
```

**ModeSelector 自学习**：

系统记录 `(intent_features, execution_mode, success)` 三元组。当某个 intent 特征下某模式的样本数足够且成功率高时，后续选择该模式会获得先验加分。

**设计理由**：自进化让系统越用越懂特定实验室的数据特点，而不是对所有用户都一视同仁。

### 7.4 信任模型与安全策略

技能分为四个信任等级，对应不同的执行策略：

| 等级 | 来源 | 沙盒策略 | HITL | CodeAct 缓存 |
|---|---|---|---|---|
| **official** | 内置 / builtin | 可本地沙盒 | 否 | 可用 |
| **verified** | 人工审核通过 | 可本地沙盒 | 否 | 可用 |
| **community** | 社区贡献 | 必须 bubblewrap/容器沙盒 | 否 | 不可用 |
| **experimental** | 未验证 | 必须 bubblewrap/容器沙盒 | 交互模式下需审批 | 不可用 |

**信任等级解析优先级**：

1. SKILL.md frontmatter 中显式声明的 `trust_level`；
2. `source == "builtin"` → official；
3. `trusted == true` 且 `source == "community"` → community；
4. `trusted == true` → verified；
5. 否则 → experimental。

**代码安全审计（Code Safety Audit）**：

CodeAct 生成的代码在执行前会经过静态审计：

1. **导入白名单**：检查 `import` 语句是否在允许列表内；
2. **危险操作检测**：扫描 `os.system`、`subprocess`、`eval`、`exec`、`__import__` 等；
3. **文件系统访问范围**：代码只能读写项目 workspace，不能访问 `/etc`、`~/.ssh` 等；
4. **网络访问控制**：默认禁止外网请求，除非 skill 显式声明。

审计不通过的代码会被拦截，并提示 LLM 重新生成。

**HITL 审批流程**：

```text
高风险工具调用 / experimental skill 执行
   │
   ▼
PersistentApprovalStore.create_checkpoint()
   │
   ▼
前端弹出审批弹窗，显示：工具名、参数、风险说明
   │
   ▼
用户批准 / 拒绝
   │
   ▼
批准后写入 audit log，继续执行
拒绝后返回拒绝原因，任务失败
```

### 7.5 复现包（ReproducibilityBundle）格式

每个成功执行都会产生一个复现包，结构类似 RO-Crate：

```text
workspaces/{project_id}/.metadata/bundles/{bundle_id}/
├── manifest.json                    # 总清单：时间、技能、输入输出、SHA
├── code/
│   └── generated_analysis.py        # 本次生成的脚本
├── plan/
│   └── plan.json                    # TaskTree、execution_mode、参数
├── data_state/
│   ├── before.json                  # 执行前 DataState
│   └── after.json                   # 执行后 DataState
├── environment/
│   ├── requirements.lock.txt        # pip freeze
│   └── python_version.txt           # Python 版本
├── skills/
│   └── {skill_id}/
│       ├── SKILL.md                 # 执行时使用的 skill 文档
│       └── scripts/                 # 执行时使用的脚本副本
├── inputs/
│   └── {filename}.sha256            # 原始输入文件 SHA-256
└── outputs/
    └── {filename}.sha256            # 输出文件 SHA-256
```

**如何复现**：

```bash
# 1. 解压/定位 bundle
# 2. 按 environment/requirements.lock.txt 创建环境
# 3. 把 inputs/ 中的文件放到 workspace/data/
# 4. 运行 code/generated_analysis.py
# 5. 对比 outputs/ 中的 SHA-256 与新生成文件
```

**设计理由**：复现包是科学可信度的基础设施。它不仅保存代码，还保存代码运行时的“上下文”——用了哪个 skill 版本、数据是什么状态、环境是什么。

### 7.6 记忆压缩与上下文管理

长对话会触发 token 上限。`ContextEngine` 负责在不丢失关键信息的前提下压缩上下文。

**三层记忆**：

| 层级 | 内容 | 存储位置 |
|---|---|---|
| **会话记忆** | 最近 N 轮对话消息 | 内存 / session_store |
| **工作记忆** | 当前任务的 DataState、中间结果、TODO 状态 | 内存 + SQLite |
| **语义记忆** | 历史消息和结果的向量摘要 | 向量数据库（Qdrant/pgvector/sqlite-vec） |

**压缩算法**：

1. **提取关键决策点**：把“用户要求什么、系统决定什么、结果是什么”保留为摘要；
2. **详细日志外移**：把完整 Execution Logs、stdout、stderr 存到 `DataStore`，只保留链接；
3. **按 token 预算截断**：当总 token 接近上限时，优先保留最近两轮和关键摘要，舍弃中间过程的细节；
4. **重要实体加权**：包含 `@file:` 引用、用户明确指令、失败重试记录的消息不会被压缩。

**DataState 是工作记忆的核心**：

```python
@dataclass
class DataState:
    has_qc: bool = False
    low_quality: bool = False
    n_samples: Optional[int] = None
    n_cells: Optional[int] = None
    data_type: Optional[str] = None
    annotated_cell_count: Optional[int] = None
    domain_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

每个 phase 执行后，系统会更新 `DataState`，下一阶段根据最新状态做决策。这样即使上下文被压缩，数据状态也不会丢失。

### 7.7 HITL 与 Waiting Orchestrator

HomomicsLab 的 HITL 不是简单弹窗，而是一个完整的“等待-恢复”机制。

**Waiting Orchestrator**：

- 当任务需要等待外部事件（用户审批、第三方 webhook、定时器）时，`JobService.suspend_for_event()` 把任务状态设为 `AWAITING_EVENT`；
- 任务从 worker 队列中移除，释放资源；
- 事件到达后，`/api/waiting/{id}/resume` 用 token 验证，任务重新入队，从暂停点继续。

**为什么需要 Waiting Orchestrator**：

- 审批可能持续几小时（用户不在线），不能让 worker 空转；
- webhook  resume 需要安全校验，不能任意触发；
- 定时器条件（如“24 小时后重试”）需要可靠调度。

**审批状态持久化**：

所有审批请求写入 `PersistentApprovalStore`（SQLite），即使后端重启，也不会丢失待审批任务。

---

## 八、v0.5.0 关键改进

### 8.1 从"Domain Phase 优先"到"意图 + 数据状态优先"

旧版默认：domain template → phases → skills → 失败才 fallback CodeAct。

新版默认：用户意图 + 数据状态 → 判断能否 single-shot / 需要哪些真实步骤 → CodeAct 或精选 skill。

带来的变化：

- 简单请求不再被硬套 8 步流水线；
- 用户点名 skill 时，skill 作为参考生成紧凑脚本；
- 结果直接内联到对话中。

### 8.2 use_skill_reference

当任务满足：

- 用户明确提到具体 skill/方法；
- 非 fixed_pipeline 模式；

系统走 `use_skill_reference` 路径：CodeAct 读取 skill 的文档和脚本，生成端到端脚本。

这是 domain↔CodeAct 的干净调和：CodeAct 是底座，domain template 是增强，skill 是参考。

### 8.3 Data Preflight

执行前让 LLM 先读数据元数据（shape、obs columns、var、layers），决定：

- 是否需要 QC / 标准化 / 聚类；
- 目标列是否存在；
- 走完整 pipeline 还是 single-shot。

### 8.4 结果内联

执行完成后，`ResultInterpreter` 读取关键 CSV/JSON/txt，生成 Markdown 摘要，前端在对话中直接渲染，文件作为附件。

### 8.5 脚本拼接执行

skill 不再有固定 `run.py` 入口。`SkillRuntimeExecutor` 拼接 `scripts/` 下所有 `.py`/`.R` 文件作为参考库，让 CodeAct 或沙盒按需调用。

---

## 九、如何扩展 HomomicsLab

### 9.1 添加一个 Domain

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

### 9.2 添加一个 Skill

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

### 9.3 调整 LLM

在 `.env` 中配置：

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

---

## 十、最佳实践与避坑指南

### 10.1 对终端用户

1. **明确点名方法**："用 CellTypist 做注释"比"做细胞注释"更容易得到精准结果。
2. **上传文件后用 `@file:` 引用**：例如 `@file:data/PA12_small.h5ad`。
3. **小数据先试本地**：默认 local 后端最省资源；大数据/多步骤才考虑 Nextflow/SLURM。
4. **interactive 模式开 sandbox**：生产环境务必 `HOMOMICS_FORCE_SANDBOX=true`。

### 10.2 对开发者

1. **重构必跑相关测试**：改 `generate_code_async` 要跑 `test_skills`+`test_execution`；改 `select_execution_backend` 要跑 `test_runtime_backend`+`test_hpc`；改 orchestrator 路由要跑 `test_orchestrator`+`test_task_decomposer`。
2. **优先改 domain.yaml 而不是 Python**：分析策略、意图、角色、SOP 尽量放在 domain 里。
3. **skill 不写固定入口**：遵循 `SKILL.md + scripts/` 新规范，不要写 `run.py`。
4. **不要提交运行时文件**：`__code_act__.py`、workspace outputs 等是运行时产物，不要提交到 git。

### 10.3 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| TODO 列表有 8 步但用户只问了一个简单问题 | 旧版 phase 模板过拟合 | v0.5.0 已修复，确保走 data preflight + intent-centric 路径 |
| 结果只返回文件路径没有摘要 | ResultInterpreter 未触发或失败 | 检查 LLM 配置，确认输出文件在工作区 outputs/ |
| skill 不被执行 | trust_level=experimental 且非交互模式 | 先 `POST /api/skills/{id}/trust` 或开启 interactive 模式 |
| 切换 session 丢失 TODO/Execution Logs | session 状态未持久化 | 检查 session store 配置和 execution state 持久化 |
| Nextflow 没触发 | 阶段数 < 8 或样本数 ≤ 100 | 调低 `HOMOMICS_WORKFLOW_NEXTFLOW_MIN_PHASES` 或确认数据规模 |

---

## 十一、附录

### 11.1 常用命令

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

### 11.2 目录速查

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

### 11.3 关键配置速查

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
