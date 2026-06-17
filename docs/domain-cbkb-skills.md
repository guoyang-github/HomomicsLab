# HomomicsLab 核心概念详解：领域模板、CBKB 与技能体系

本文档从设计目标、数据模型、运行机制和彼此关系四个维度，详细说明 HomomicsLab 的三个核心抽象：

1. **领域模板（Domain Templates）** —— 生物信息学分析领域的“工作流蓝图”。
2. **CBKB（Collective Bioinformatics Knowledge Base）** —— 可累积、可复现的领域知识库。
3. **技能体系（Skill System）** —— 可发现、可执行、可进化的最小能力单元。

---

## 1. 领域模板（Domain Templates）

### 1.1 什么是领域模板

一个 **Domain** 对应一个完整的生物信息学子领域，例如 `single_cell`、`genomics`、`mrnaseq`、`spatial`、`riboseq`、`database`、`paperwriting`。它用一份 `domain.yaml` 描述整个分析管线：

- 分析阶段（phases）及其先后顺序
- 每个阶段可用的技能（skills）
- 阶段之间的流转/分支/并行关系
- 用户意图（intents）关键词，用于自动路由
- 角色（roles）与权限
- 标准操作流程（SOPs）
- 代码模板（code_templates）
- SkillDAG 种子（dag_seeds）

> 设计目标：让 HomomicsLab 在面对“帮我做单细胞分析”这类需求时，能够先识别到 `single_cell` 领域，再按领域预定义的阶段骨架生成计划，而不是从零开始规划。

### 1.2 `domain.yaml` 核心结构

对应后端模型 `backend/homomics_lab/domain/models.py` 中的 `DomainDefinition`：

```python
class DomainDefinition(BaseModel):
    domain: str                       # 唯一标识
    description: str
    version: str

    phases: List[DomainPhase]
    phase_transitions: List[DomainPhaseTransition]
    state_checks: List[DomainStateCheck]

    orchestrator_skills: List[str]    # 跨阶段编排技能
    intents: List[DomainIntent]
    dag_seeds: List[DomainDAGSeed]
    roles: List[DomainRole]
    sops: List[DomainSOP]

    data_state_schema: Dict[str, Any]
    skills_dir: Optional[str]
    preferred_libraries: Dict[str, List[str]]
    code_templates: Dict[str, Dict[str, Any]]
    data_sources: List[Dict[str, Any]]
    fallback_rules: List[Dict[str, str]]
```

#### 1.2.1 Phases（分析阶段）

```python
class DomainPhase(BaseModel):
    id: str
    required: bool = True
    description: str = ""
    skills: List[str] = []           # 本阶段可用 skill id
    default_skill: Optional[str] = None
```

示例（`backend/homomics_lab/domains/single_cell/domain.yaml`）：

```yaml
phases:
  - id: qc
    required: true
    description: Quality control filtering for single-cell RNA-seq
    skills:
      - bio-single-cell-preprocessing
      - bio-single-cell-doublet-scrublet
      - bio-single-cell-doublet-solo
    default_skill: bio-single-cell-preprocessing
```

#### 1.2.2 Phase Transitions（阶段流转）

```python
class DomainPhaseTransition(BaseModel):
    from_phase: str = Field(alias="from")
    to_phase: str = Field(alias="to")
    type: str = "followed_by"   # followed_by | alternative_to | depends_on | parallel_to
    context: str = ""
```

示例：

```yaml
phase_transitions:
  - from: qc
    to: doublet_removal
  - from: annotation
    to: differential_expression
  - from: annotation
    to: cnv
    type: alternative_to
```

#### 1.2.3 State Checks（动态状态检查）

根据运行时数据状态动态插入、跳过或修改阶段：

```python
class DomainStateCheck(BaseModel):
    condition: str
    action: str       # insert | skip | modify_param
    target: str
    value: Optional[Any] = None
    after: Optional[str] = None
```

示例：

```yaml
state_checks:
  - condition: "batch_detected"
    action: insert
    target: batch_integration
    after: normalization
```

#### 1.2.4 Roles（角色）

用于限制 Agent 可调用技能/工具，实现专业化分工：

```yaml
roles:
  - role_id: genomics_specialist
    name: Genomics Specialist
    allowed_skills:
      - bio-genomics-alignment
      - bio-genomics-variant-snp-indel
    allowed_tools: [file_read, file_write, shell_exec]
    permissions:
      can_execute: true
      can_spawn_specialist: false
      max_concurrent_tasks: 3
```

#### 1.2.5 Intents（意图）

用于 `CascadeIntentAnalyzer` 匹配用户请求属于哪个领域：

```yaml
intents:
  - analysis_type: single_cell_analysis
    keywords:
      - "单细胞"
      - "single cell"
      - "scrna-seq"
      - "10x"
      - "seurat"
    examples:
      - "帮我分析 PBMC 单细胞数据"
```

#### 1.2.6 DAG Seeds（SkillDAG 种子）

预声明技能之间的关系， boot 时写入 `SkillDAG`：

```yaml
dag_seeds:
  - from: bio-single-cell-preprocessing
    to: bio-single-cell-clustering
    type: followed_by
    context: "Normalize and reduce dimensions before clustering"
```

#### 1.2.7 Code Templates（代码模板）

领域内通用代码片段：

```yaml
code_templates:
  scanpy_qc:
    language: python
    skeleton: |
      import scanpy as sc
      sc.pp.calculate_qc_metrics(adata, inplace=True)
```

### 1.3 领域加载与注册流程

1. **`DomainLoader.load(domain_yaml_path)`**（`backend/homomics_lab/domain/loader.py`）
   - 解析 YAML 为 `DomainDefinition`
   - 若声明 `skills_dir`，则加载该目录下的 skill
   - `DomainValidator` 校验：阶段 skill 是否存在、流转目标是否合法、DAG 种子是否引用已知 skill、orchestrator skill 是否未重复出现在 phase skills 中
   - 将领域转换为 `AnalysisStrategy` 注册到 `StrategyLibrary`
   - 将 `dag_seeds` 注册到 `SkillDAG`
   - 尝试将 SOP 注册到 CBKB

2. **`DomainRegistry.register(...)`**（`backend/homomics_lab/domain/registry.py`）
   - 全局单例，保存所有已加载领域
   - 提供 `get`、`list_all`、`get_intent_config`、`get_roles`、`reload` 等方法

3. **启动加载**（`backend/homomics_lab/bootstrap.py`）

```python
domains_dir = Path(__file__).parent / "domains"
for domain_yaml in domains_dir.rglob("domain.yaml"):
    domain = domain_loader.load(domain_yaml)
    domain_registry.register(domain, domain_loader, domain_yaml)
```

4. **热重载**（`backend/homomics_lab/domain/hot_reload.py`）
   - `DomainHotReloader` 监听 `domain.yaml` 变更
   - 变更后自动重载领域，并刷新 `CascadeIntentAnalyzer`

### 1.4 前端 Domain Marketplace

- 组件：`frontend/src/components/domains/DomainMarketplace.tsx`
- API：`GET /api/domains/`、`GET /api/domains/{id}/preview`、`POST /api/domains/import`、`POST /api/domains/{id}/export`
- 后端实现：`backend/homomics_lab/api/domains.py`、`backend/homomics_lab/domain/marketplace.py`

---

## 2. CBKB（Collective Bioinformatics Knowledge Base）

### 2.1 定位

CBKB 是 **Computational Biology Knowledge Base** 的缩写，是一个面向生物信息学分析场景、以可复现实验为核心的 SQLite 知识库。它不是为了替代通用向量数据库，而是为了沉淀：

- 实验血缘与 provenance
- 参数-效果经验（parameter lore）
- 异常案例库（anomaly archive）
- 实验室 SOP（lab SOP）
- 技能进化历史（skill evolution log）

对应实现：`backend/homomics_lab/knowledge/cbkb.py`

### 2.2 五层数据模型

CBKB 默认存储在 `{data_dir}/.metadata/cbkb.db`，包含以下表：

| 表 | 数据类 | 用途 |
|---|---|---|
| `experiment_nodes` | `ExperimentNode` | 一次分析实验的摘要（项目、技能、阶段、时间） |
| `experiment_edges` | `ExperimentEdge` | 实验之间的共享数据/技能/参数/衍生关系 |
| `parameter_lore` | `ParameterLoreEntry` | 某个 skill 的参数取值与效果的对应记录 |
| `anomaly_archive` | `AnomalyRecord` | 阶段级异常及推荐处理 |
| `lab_sop` | `LabSOP` | 由成功案例蒸馏出的最佳实践模板 |
| `skill_evolution_log` | `SkillEvolutionRecord` | SkillDAG 边状态变化历史 |

核心数据类示例：

```python
@dataclass
class ExperimentNode:
    bundle_id: str
    project_id: str
    created_at: str
    skills_used: List[str]
    phases: List[str]
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParameterLoreEntry:
    skill_id: str
    param_name: str
    param_value: str
    outcome_metric: str
    outcome_value: float
    project_id: str
    context: str
    created_at: str
```

### 2.3 典型使用场景

#### 2.3.1 计划生成时注入历史参数

`PlanEngine._apply_learned_defaults()`（`backend/homomics_lab/agent/plan/engine.py`）会根据 CBKB 中某 skill 的历史参数建议，自动填充阶段默认参数：

```python
suggestions = self.cbkb.suggest_parameters(phase.selected_skill.id)
for suggestion in suggestions:
    if suggestion.get("samples", 0) < 3:
        continue
    phase.parameters[param_name] = suggestion["param_value"]
```

#### 2.3.2 意图分析时丰富上下文

`CascadeIntentAnalyzer._enrich_with_cbkb()`（`backend/homomics_lab/agent/intent/analyzer.py`）会读取相关 SOP、异常记录和参数经验，附加到 `UserIntent.metadata["cbkb"]` 中，供后续 planning 使用。

#### 2.3.3 执行完成后归档

`ReproducibilityEngine.finalize()`（`backend/homomics_lab/reproducibility/engine.py`）会生成 `ReproducibilityBundle`，并索引为 `ExperimentNode`；同时把 HITL 决策中的参数写入 `parameter_lore`。

`Orchestrator.run_tree()` 也会通过 `CBKBIngestionService.ingest_workflow()` 把任务树结果写入 CBKB。

#### 2.3.4 定期策展

`CBKBCurator`（`backend/homomics_lab/knowledge/curator.py`）会周期性地：

- 从新 bundle 蒸馏洞察（常用技能序列、参数组合、项目相似度）
- 按 Jaccard 相似度聚类主题
- 生成叙事报告
- 提出 SOP 更新建议并检测偏离
- 自动链接相似实验

#### 2.3.5 驱动 SkillDAG 进化

`SkillDAGMiner`（`backend/homomics_lab/evolution/skill_dag_miner.py`）从 CBKB 的 experiment nodes 中挖掘技能共现序列，转换为 `SkillDAG` 边，实现技能关系的自动进化。

### 2.4 当前限制

- `MemoryManager.enrich_context()` 对 CBKB 的利用目前仍是占位实现，仅初始化了空列表。
- 部分 `domain.yaml` 中的 SOP 字段与 `LabSOP` 数据模型不匹配，导致领域 SOP 目前未能成功写入 CBKB。

---

## 3. 技能体系（Skill System）

### 3.1 什么是 Skill

Skill 是 HomomicsLab 中的最小可执行能力单元，表现为一个独立目录：

```text
<skill-name>/
  SKILL.md
  scripts/
    python/run.py
    r/run.R
  requirements.txt
  dependencies.R
  tests/
  references/
  assets/
```

`SKILL.md` 是 skill 的唯一入口描述；脚本按需加载（progressive disclosure），避免启动时加载大量外部脚本。

### 3.2 `SKILL.md` 解析

`SkillLoader`（`backend/homomics_lab/skills/loader.py`）解析 YAML frontmatter。常用字段：

| 字段 | 含义 |
|---|---|
| `name` | skill id |
| `description` | 描述 |
| `version` | 版本 |
| `category` | 分类 |
| `tool_type` / `type` | 运行时类型：`python`、`r`、`mixed`、`cli`、`workflow`、`container`、`agent`、`knowledge`、`prompt` |
| `primary_tool` | 主要工具 |
| `supported_tools` | 支持工具 |
| `keywords` | 关键词 |
| `inputs` / `outputs` | 输入输出声明 |
| `code_act` | 是否由 CodeAct 引擎执行 |
| `entrypoint` / `script` | 入口脚本 |
| `depends_on` / `prerequisites` | 依赖 skill |

示例 frontmatter：

```yaml
---
name: bio-single-cell-clustering
description: Dimensionality reduction and clustering for single-cell RNA-seq...
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, matplotlib, leidenalg]
keywords: ["single-cell", "clustering", "PCA", "UMAP"]
---
```

### 3.3 模型与注册

`SkillDefinition`（`backend/homomics_lab/skills/models.py`）是运行时模型，包含：

```python
class SkillDefinition(BaseModel):
    id: str
    name: str
    version: str
    category: str
    description: str
    input_schema: SkillInputSchema
    output_schema: SkillOutputSchema
    runtime: SkillRuntime
    quality: SkillQuality
    metadata: Dict[str, Any]
```

`SkillRegistry`（`backend/homomics_lab/skills/registry.py`）维护所有已注册 skill，支持：

- `register` / `get` / `activate`
- `search`（关键词）
- `semantic_search`（TF-IDF 或 sentence-transformers）

### 3.4 SkillStore：生命周期管理

`SkillStore`（`backend/homomics_lab/skills/skill_store.py`）提供：

- 从本地路径 / git / zip 导入 skill
- enable / disable
- trust / untrust
- validate（结构校验）
- test（运行测试）
- 按项目锁定版本

元数据持久化在 `data/skill_store/skills.json`。

#### 来源与信任

```python
@staticmethod
def _is_trusted_source(source: str) -> bool:
    return source in {"builtin", "legacy"}
```

导入时：

```python
skill.metadata["source"] = source if trusted else "imported"
skill.metadata["origin"] = source
skill.metadata["namespace"] = namespace
skill.metadata["trusted"] = trusted
```

运行时执行会检查信任：

```python
if source in {"external", "community", "imported"} and not skill.metadata.get("trusted"):
    raise UntrustedSkillError(...)
```

外部 skill 默认不信任，需要用户显式 `POST /api/skills/{id}/trust` 或在 CLI 中 `homomics trust <id>`。

### 3.5 运行时执行

`SkillRuntimeExecutor`（`backend/homomics_lab/skills/runtime.py`）统一调度执行：

1. 获取 skill 并 `activate`
2. 校验输入
3. 根据类型分发：
   - `mcp` → 调用 MCP 工具
   - `code_act=True` → CodeAct 引擎
   - 声明式 skill → Agent 工具循环
   - 脚本目录 → `scripts/python/*.py` 或 `scripts/r/*.R`

脚本执行前会检查依赖：

- `requirements.txt` → pip 包检查
- `dependencies.R` → R 包检查
- `environment.yml` → 已识别但未自动安装

沙箱实现包括 `LocalSandbox`、`BubblewrapSandbox`、`ContainerSandbox`。

### 3.6 外部/社区技能发现

`backend/homomics_lab/bootstrap.py` 默认扫描项目根目录上层的 `*-Skills/skills` 仓库：

```python
for name in (
    "NanoResearch-Skills",
    "Genomics-Skills",
    "Utils-Skills",
    "paperwriting-Skills",
    "database-Skills",
    "mRNAseq-Skills",
    "riboseq-Skills",
):
    candidate = project_root.parent / name / "skills"
    ...
```

每个 skill 子目录通过 `SkillStore.import_skill()` 复制到 `data/skill_store/imported/<namespace>/`，namespace 由仓库名推导（如 `NanoResearch-Skills` → `nanoresearch`）。

### 3.7 SkillDAG

`SkillDAG`（`backend/homomics_lab/skills/skill_dag.py`）是自我进化的技能关系图。

边类型：

- `depends_on`
- `conflicts_with`
- `specializes`
- `followed_by`
- `alternative_to`
- `produces`

边状态：

- `candidate` → `confirmed` / `rejected` / `deprecated`

核心能力：

- `search`：图增强的 skill 检索
- `get_conflicts` / `get_alternatives` / `get_followed_by`：冲突检测与替代推荐
- `validate_sequence`：校验技能序列合法性
- `record_execution` / `infer_from_history`：从执行记录学习关系

> 注意：`PlanEngine` 不使用 SkillDAG 生成计划骨架，而是把它用于 **skill 选择**（例如“QC 阶段用哪个工具”）。

### 3.8 Skill 升级

`TransientSkillPromoter`（`backend/homomics_lab/skills/promotion.py`）将一次成功的 CodeAct 运行封装为新 skill，初始状态为 `generated` 且不信任，经人工审核后可提升为正式 skill。

---

## 4. 三者关系

```text
┌─────────────────────────────────────────────────────────────┐
│                         用户请求                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Domain Intents  ──►  CascadeIntentAnalyzer                  │
│  （领域匹配）                                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Domain Strategy  ──►  PlanEngine                            │
│  （阶段骨架 + state_checks）                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SkillRetriever: SkillDAG + CBKB                             │
│  （选哪个 skill、用什么参数、参考哪些 SOP/异常）             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SkillRuntimeExecutor  ──►  执行技能                         │
│  （Python/R/CodeAct/Agent/MCP）                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  CBKB 归档实验节点、参数经验、异常、SOP                       │
│  SkillDAG 进化技能关系                                       │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Domain → Skill

- Domain 的 `phases[].skills` 引用具体 skill id。
- `DomainLoader` 校验这些 skill 在 `SkillRegistry` 中存在。
- `orchestrator_skills` 是跨阶段编排 skill。
- `dag_seeds` 在启动时写入 `SkillDAG`。

### 4.2 Domain → PlanEngine

- `DomainLoader._register_strategy()` 把 `DomainDefinition` 转换为 `AnalysisStrategy`，注册到 `StrategyLibrary`。
- `PlanEngine` 根据 `intent.analysis_type` 匹配策略，生成阶段骨架。

### 4.3 PlanEngine → SkillDAG + CBKB

- `PlanEngine` 调用 `SkillRetriever` 检索 skill、SOP、异常、参数经验。
- `SkillRetriever` 查询 `SkillDAG` 和 `CBKB`。
- `PlanEngine._apply_learned_defaults()` 把 CBKB 参数建议注入阶段参数。

### 4.4 TurnRunner 串联三者

`backend/homomics_lab/api/chat.py` 构造 `TurnRunner` 时传入：

```python
runner = TurnRunner(
    tool_registry=...,
    memory_manager=memory_manager,
    cbkb=cbkb,
)
```

流程：

1. `IntentAnalyzer` 使用 `DomainRegistry` 中的 intents 并 enrich CBKB。
2. `TaskDecomposer` / `PlanEngine` 选择领域策略和技能。
3. `Orchestrator` 执行任务树，结果通过 `CBKBIngestionService` 写入 CBKB。
4. `MemoryManager` 持久化会话。

---

## 5. 当前已知限制

1. **Domain SOP 模型不匹配**
   - `domain.yaml` 中 SOP 使用 `steps` 列表。
   - `DomainSOP` 模型期望 `content` 字符串。
   - `LabSOP` 数据类期望 `template` 字典。
   - 因此领域 SOP 目前未成功写入 CBKB。

2. **MemoryManager CBKB 增强未完整实现**
   - `enrich_context()` 仅初始化了空列表，尚未真正查询 CBKB。

3. **外部 skill 默认不信任**
   - 社区 skill 需要显式 trust 后才能执行脚本，这是安全设计，但需要用户注意。

---

## 6. 相关文件索引

| 模块 | 关键文件 |
|---|---|
| 领域模型 | `backend/homomics_lab/domain/models.py` |
| 领域加载 | `backend/homomics_lab/domain/loader.py` |
| 领域注册 | `backend/homomics_lab/domain/registry.py` |
| 领域市场 | `backend/homomics_lab/domain/marketplace.py` |
| 领域 API | `backend/homomics_lab/api/domains.py` |
| 领域热重载 | `backend/homomics_lab/domain/hot_reload.py` |
| 启动加载 | `backend/homomics_lab/bootstrap.py` |
| CBKB | `backend/homomics_lab/knowledge/cbkb.py` |
| CBKB 策展 | `backend/homomics_lab/knowledge/curator.py` |
| Skill 模型 | `backend/homomics_lab/skills/models.py` |
| Skill 加载 | `backend/homomics_lab/skills/loader.py` |
| Skill 注册 | `backend/homomics_lab/skills/registry.py` |
| Skill 执行 | `backend/homomics_lab/skills/runtime.py` |
| SkillStore | `backend/homomics_lab/skills/skill_store.py` |
| SkillDAG | `backend/homomics_lab/skills/skill_dag.py` |
| 意图分析 | `backend/homomics_lab/agent/intent/analyzer.py` |
| 计划引擎 | `backend/homomics_lab/agent/plan/engine.py` |
| 编排器 | `backend/homomics_lab/agent/orchestrator.py` |
| 可复现引擎 | `backend/homomics_lab/reproducibility/engine.py` |
| CBKB 摄取 | `backend/homomics_lab/evolution/ingestion.py` |
| SkillDAG 挖掘 | `backend/homomics_lab/evolution/skill_dag_miner.py` |
