# HomomicsLab 全面改进方案（最终版 v1.0）

**目标**：将 HomomicsLab 从“框架先进、内容空心、进化未闭环”的架构 Demo，演进为 **Agent 元能力强大 + 外部 Skill 生态繁荣 + CodeAct 灵活执行 + 真正自进化** 的生产级通用生物医学 Agent 平台。  
**时间预估**：8–10 周核心链路可用，16 周达到生产级。

---

## 一、现状诊断

### 1.1 已具备的优势（保留）

| 模块 | 状态 | 价值 |
|:---|:---|:---|
| Agent 编排框架 | 成熟 | Supervisor/Worker/Reviewer、Orchestrator、PlanEngine 已具备 |
| Skill 加载机制 | 可用 | `SkillLoader` 支持 `SKILL.md + scripts/` 格式 |
| 稳定性保障 | 可用 | Schema 校验、版本锁定、Phase Gate、快照回滚 |
| CBKB 知识库 | 可用 | 五层结构完整，但尚未接入主链路 |
| SkillDAG | 可用 | 边类型、生命周期完整，但生产未启用 |
| 后台 Job Queue | 可用 | SQLite + 可选 Redis，SSE 状态推送 |
| 678 测试通过 | 质量基线好 | 框架稳定 |

### 1.2 关键问题（必须解决）

| 问题类别 | 具体问题 | 影响 |
|:---|:---|:---|
| **内容空心化** | builtin 仅 4 个 skill，且多为 stub；domain.yaml 引用大量未实现 skill | 无法完成真实生信分析 |
| **自进化未闭环** | InterpretationEngine、ReproducibilityEngine、SkillDAG.record_execution、AgentEvolutionEngine 未接入主流程 | 系统不会越用越聪明 |
| **规划灵活性不足** | TaskDecomposer 硬编码 pipeline，LLM fallback 使用受限 | 难以处理新颖复杂任务 |
| **Skill 管理薄弱** | 无统一 SkillStore，namespace、version、test、依赖管理缺失 | 无法规模化引入外部 skill |
| **执行接口僵化** | 当前以固定 skill 调用为主，缺少 CodeAct 式代码组合能力 | 无法灵活组合循环/分支/并行 |
| **环境隔离不足** | LocalSandbox 基于 `__import__` 重写，可被绕过；无容器化执行 | 安全风险，依赖冲突 |
| **元数据脱节** | `SkillLoader` 未解析 Markdown 参数表到 `input_schema/output_schema` | SchemaValidator 失效 |

---

## 二、设计原则

1. **Agent 核心化**：builtin skill 只保留 Agent 自身元能力，业务逻辑全部外部化。
2. **Skill 生态化**：单细胞、空间、基因组、AIDD、文献辅助等业务能力由用户/社区引入。
3. **代码即接口**：引入 Biomni 的 CodeAct 思想，Agent 生成可执行代码来组合 skill/tool/库。
4. **检索增强规划**：Plan 由 LLM 基于 skill/tool/SOP/CBKB 检索结果动态生成，非硬编码模板。
5. **统一环境管理**：每个 skill 声明依赖，Agent 负责构建、锁定、隔离执行环境。
6. **统一治理闭环**：skill 的导入 → 发现 → 执行 → 监控 → 评估 → 进化全部在一个体系内完成。
7. **渐进式改造**：保留现有稳定模块，逐步替换僵化部分，不推倒重来。

---

## 三、架构重构方案

### 3.1 Builtin Skill 精简为 Agent 元能力

将 `backend/homomics_lab/skills/builtin/` 重构为以下 **6 个核心元能力 skill**：

| Skill ID | 职责 | 对应现有模块 |
|:---|:---|:---|
| `core_planning` | 意图理解、检索增强规划、plan 生成与验证 | `agent/plan/engine.py` |
| `core_code_act` | 生成并执行 Python/R/Bash 代码，组合 skill/tool/库 | 新增 |
| `core_skill_router` | 语义检索 skill，返回候选、schema、示例 | `skills/registry.py` |
| `core_interpretation` | 读取执行结果、检测异常、生成摘要 | `agent/interpretation.py` |
| `core_hitl` | 生成检查点、处理人类反馈 | `hitl/` |
| `core_reproducibility` | 捕获 plan/code/HITL/环境，生成 bundle | `reproducibility/engine.py` |

**移除/外迁**：`scanpy_qc`、`scanpy_cluster`、`data_loader`、`general_code_assistant` 等业务 skill 全部迁移到外部 skill 库。

### 3.2 外部 Skill 生态层

#### Skill 来源

| 来源 | 路径/方式 |
|:---|:---|
| 用户本地 | `~/.homomics/skills/` 或项目 `./skills/` |
| 团队/组织 | Git 仓库、私有 Registry |
| 社区 | `NanoResearch-Skills`、`Genomics-Skills` |
| 市场 | Homomics Skill Hub（未来） |

#### Skill 契约（统一）

```
<skill_id>/
├── SKILL.md                 # 元数据 + 使用文档
├── scripts/
│   ├── python/
│   │   ├── __init__.py
│   │   └── run.py
│   └── r/
│       └── run.R
├── requirements.txt         # pip 依赖
├── environment.yml          # conda 依赖（可选）
├── container/Dockerfile     # 容器化（可选）
├── tests/                   # pytest 测试
└── examples/                # 使用示例
```

#### SKILL.md frontmatter 标准

```yaml
name: bio-single-cell-qc
description: 使用 scanpy 进行单细胞 QC 过滤
version: 1.2.0
author: xxx
license: MIT
tool_type: python          # python | r | mixed | cli | workflow | container
primary_tool: scanpy
supported_tools: [scanpy, anndata, pandas]
keywords: [single-cell, qc, filter, scanpy]
category: single-cell
inputs:
  adata_path:
    type: string
    required: true
    description: 输入 h5ad 路径
  min_genes:
    type: integer
    default: 200
outputs:
  output_path:
    type: string
multi_sample:
  supported: false
depends_on: []
workflow: false
```

### 3.3 SkillStore：统一管理中心

新增 `backend/homomics_lab/skills/skill_store.py`：

```python
class SkillStore:
    def import_skill(source: str, namespace: str = "default") -> SkillDefinition
    def list_skills(domain: Optional[str] = None, 
                    namespace: Optional[str] = None) -> List[SkillDefinition]
    def get_skill(skill_id: str, 
                  version: Optional[str] = None,
                  namespace: Optional[str] = None) -> SkillDefinition
    def update_skill(skill_id: str, source: str) -> SkillDefinition
    def remove_skill(skill_id: str)
    def enable_skill(skill_id: str)
    def disable_skill(skill_id: str)
    def validate_skill(skill_dir: Path) -> ValidationReport
    def run_tests(skill_id: str) -> TestReport
    def lock_versions(project_id: str) -> VersionLock
    def resolve(skill_id: str, context: Dict) -> SkillDefinition
```

对应 API：

| 端点 | 功能 |
|:---|:---|
| `GET /api/skills` | 列出 skill（支持 namespace、category、enabled 过滤） |
| `GET /api/skills/{id}` | 详情 + 结构化 schema + 示例 |
| `POST /api/skills/import` | 导入本地/GIT/上传的 skill |
| `POST /api/skills/{id}/enable` | 启用 |
| `POST /api/skills/{id}/disable` | 禁用 |
| `POST /api/skills/{id}/test` | 运行测试 |
| `GET /api/skills/{id}/versions` | 版本历史 |
| `POST /api/skills/{id}/rollback` | 回滚到某版本 |
| `POST /api/projects/{id}/lock-skills` | 项目级版本锁定 |

### 3.4 CodeAct 引擎：学习 Biomni 的核心

新增 `backend/homomics_lab/skills/builtin/core_code_act/`：

Agent 生成可执行代码，代码中可调用：

```python
# Agent 自动生成的分析代码示例
from homomics.runtime import skill, tool

# 调用 skill
adata = skill.call("bio-single-cell-io", {
    "path": "data/pbmc3k.h5ad",
    "format": "h5ad"
})

qc = skill.call("bio-single-cell-qc", {
    "adata_path": adata["output_path"],
    "min_genes": 200
})

# 直接调用底层库
import scanpy as sc
adata = sc.read_h5ad(qc["output_path"])
sc.pp.normalize_total(adata, target_sum=1e4)

# 调用数据库工具
pubmed = tool.call("pubmed_search", {"query": "PBMC marker genes"})
```

CodeAct 执行循环：

```
用户请求
  → 检索相关 skill/tool/SOP
  → LLM 生成高层 plan
  → LLM 生成代码片段
  → Code Interpreter 执行
  → 观察输出
  → 反思是否需要继续/修正/replan
  → 循环直到完成
```

优势：
- 支持循环、分支、并行、动态组合
- 不依赖预定义函数签名
- 可处理未预见过的新任务
- 与人类科学家的工作方式一致

### 3.5 检索增强规划（RAP）

新增 `backend/homomics_lab/agent/plan/retrieval.py`：

```python
class SkillRetriever:
    def retrieve(self, query: str, context: Dict, top_k: int = 10) -> RetrievalResult:
        # 1. 语义搜索 skill
        # 2. 搜索 skill 内具体功能/示例
        # 3. 搜索 CBKB 历史成功 plan
        # 4. 搜索 SOP
        # 5. 搜索 InterpretationEngine 规则
        pass
```

PlanEngine 新流程：

```
Intent Analysis
  → SkillRetriever.retrieve()
  → LLM.generate_plan(retrieved_context)
  → PlanValidator.check(skill_existence, schema_compatibility, dependency)
  → Human Approval（可选）
  → Code Generation
  → Execution
```

### 3.6 统一执行环境

执行后端扩展：

| 执行方式 | 适用场景 | 实现 |
|:---|:---|:---|
| Local Sandbox | 轻量、快速测试 | 当前 subprocess + 资源限制 |
| Conda Env | Python/R skill | 按 `environment.yml`/`requirements.txt` 构建 |
| Docker Container | 复杂依赖、生产环境 | 按 `container/Dockerfile` 构建 |
| Apptainer/Singularity | HPC 环境 | 容器转 singularity |
| Nextflow | 大规模 workflow | 多 process workflow |

项目级环境锁定文件 `homomics.lock`：

```yaml
project_id: proj_xxx
python_version: 3.12.0
skills:
  bio-single-cell-qc:
    version: 1.2.0
    container_sha: sha256:abc...
    python_packages:
      scanpy: 1.10.0
      anndata: 0.10.0
```

### 3.7 自进化闭环真正运行

将以下模块接入主执行链路：

| 模块 | 接入点 | 触发条件 |
|:---|:---|:---|
| `InterpretationEngine` | 每个 phase 执行后 | 始终 |
| `ReproducibilityEngine.finalize()` | 任务完成或失败时 | 始终 |
| `SkillDAG.record_execution()` | skill 执行成功/失败时 | 始终 |
| `CBKB.add_experiment_node()` | 任务完成时 | 始终 |
| `CBKB.add_parameter_lore()` | skill 输出包含可评估指标时 | 当 outcome_metric 可计算 |
| `CBKB.archive_anomaly()` | InterpretationEngine 检测到异常时 | 异常时 |
| `AgentEvolutionEngine` | 定时任务（ nightly/weekly ） | 周期性 |
| `CBKBCurator` | 定时任务 | 周期性 |

AgentEvolutionEngine 应用策略：
- 只应用于 `locked=false` 的 role/SOP
- 重大变更需人类审批
- 所有变更写入 audit log

---

## 四、Agent 执行流程重构

### 新流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求                                  │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Intent Analysis（core_planning）                             │
│     - 关键词/embedding/LLM 级联识别                              │
│     - 从 DomainRegistry 加载领域术语                             │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Skill Retrieval（core_skill_router）                         │
│     - 语义搜索 skill                                             │
│     - SkillDAG 图增强                                            │
│     - CBKB/SOP 历史推荐                                          │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Plan Generation（core_planning + LLM）                       │
│     - 基于检索上下文生成 plan                                    │
│     - 区分固定 pipeline / CodeAct 动态执行                       │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Plan Validation                                              │
│     - 检查 skill 是否存在、是否启用                              │
│     - schema 兼容性检查                                          │
│     - 依赖冲突检查                                               │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Human Approval（高复杂度/LLM fallback 时）                   │
│     - 展示 plan + 涉及 skill + 预估资源                          │
│     - 用户确认/修改/拒绝                                         │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Code Generation（core_code_act）                             │
│     - 将 plan 转为可执行代码                                     │
│     - 插入监控/日志/异常捕获                                     │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Execution（Orchestrator + Worker）                           │
│     - 选择执行后端（local/conda/docker/nextflow）                │
│     - 执行代码或单个 skill                                       │
│     - 实时进度推送（SSE）                                        │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. Interpretation（core_interpretation）                        │
│     - 分析输出是否符合预期                                       │
│     - 检测异常                                                   │
│     - 生成摘要                                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  9. Decision                                                     │
│     - 正常 → 继续下一步                                          │
│     - 异常 → replan / retry / HITL                               │
│     - 完成 → finalize                                            │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  10. Finalize（core_reproducibility + CBKB）                     │
│     - 生成 ReproducibilityBundle                                 │
│     - 写入 CBKB（experiment、parameter lore、anomaly）           │
│     - SkillDAG.record_execution()                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、数据模型与 API 调整

### 5.1 SkillDefinition 增强

```python
class SkillDefinition(BaseModel):
    id: str
    name: str
    version: str
    namespace: str = "default"           # 新增
    author: str
    license: str
    description: str
    input_schema: SkillInputSchema       # 必须结构化
    output_schema: SkillOutputSchema     # 必须结构化
    runtime: SkillRuntime
    quality: SkillQuality                # 测试用例
    metadata: Dict[str, Any]
    enabled: bool = True                 # 新增
    trusted_level: str = "community"     # 新增：official/verified/community/experimental
```

### 5.2 PlanResult 增强

```python
class PlanResult(BaseModel):
    plan_id: str
    version: int
    intent: UserIntent
    retrieved_skills: List[SkillDefinition]   # 新增
    retrieved_sops: List[LabSOP]              # 新增
    phases: List[Phase]
    execution_mode: str                       # "pipeline" | "code_act"
    generated_code: Optional[str]             # CodeAct 时
    is_fallback: bool
    requires_approval: bool
    approval_status: str                      # pending | approved | rejected
```

---

## 六、实施路线图

### 阶段 1：基础重构（第 1–2 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| 精简 builtin skill | 保留 6 个元能力 skill，移除业务 skill | `pytest tests/test_skills/test_builtin.py` 通过 |
| 修复 SkillLoader | 解析 Markdown 参数表到 schema | 所有 skill 有结构化 input/output schema |
| 接入外部 skill | 批量导入 NanoResearch-Skills 74 个 + Genomics-Skills 22 个 | 至少 90 个 skill 可注册 |
| 修复 SkillDAG 启用 | PlanEngine/DomainLoader 正确传入 SkillDAG | SkillDAG 有实例，edge 可被查询 |

### 阶段 2：SkillStore 与统一管理（第 3–4 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| 实现 SkillStore | import/list/get/update/remove/enable/disable/test/lock | API 测试覆盖 |
| namespace 隔离 | 不同来源 skill 不冲突 | 同名 skill 不同 namespace 可共存 |
| 前端 Skill 管理 | 列表、搜索、详情、启用/禁用、测试、导入 | UI 可完成 skill 全生命周期管理 |
| 版本锁定 | 项目级 `homomics.lock` | 锁定文件可导出/导入/复现 |

### 阶段 3：CodeAct + RAP（第 5–7 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| core_code_act skill | 生成并执行 Python/R/Bash 代码 | 可完成“读取数据→QC→聚类”的代码生成执行 |
| SkillRetriever | 语义搜索 + SkillDAG + CBKB + SOP | 检索准确率 > 80% |
| 改造 PlanEngine | 基于检索上下文生成 plan | 90% 常见请求无需硬编码 template |
| Plan Validation | skill 存在性、schema、依赖检查 | 错误 plan 在生成阶段被拦截 |
| 自适应 replan | 根据 Interpretation 结果自动调整 | QC 异常时可自动插入 remediation |

### 阶段 4：统一执行环境（第 8–10 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| Conda 执行后端 | 按 `environment.yml` 构建环境 | skill 在隔离 conda env 中运行 |
| Docker 执行后端 | 按 `Dockerfile` 构建容器 | 复杂依赖 skill 在容器中运行 |
| 后端自动选择 | 根据任务特征选择 local/conda/docker/nextflow | 无需用户手动选择 |
| 资源监控 | CPU/内存/GPU/磁盘实时监控 | ExecutionState 包含资源字段 |

### 阶段 5：自进化闭环（第 11–12 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| 接入 InterpretationEngine | 每个 phase 后调用 | 输出被分析并记录 |
| 接入 ReproducibilityEngine | 任务结束时 finalize | Bundle 可生成并导出 |
| 接入 SkillDAG.record_execution | skill 执行后记录 | 边 confidence 随执行更新 |
| 接入 CBKB | experiment/parameter lore/anomaly | CBKB 表有真实数据 |
| 调度 AgentEvolutionEngine | nightly 运行 | 提出并应用非锁定 role/SOP 更新 |
| 建立 benchmark | 标准数据集 + 指标 | 可量化评估进化效果 |

### 阶段 6：生产加固（第 13–16 周）

| 任务 | 具体内容 | 验收标准 |
|:---|:---|:---|
| 安全加固 | 容器隔离、命令审计、网络限制 | 危险操作需审批 |
| 性能优化 | 快照增量化、缓存机制、并行优化 | 长流程执行时间合理 |
| 文档完善 | 开发者指南、用户手册、API 文档 | 新用户可独立上手 |
| 社区生态 | Skill Hub 初版、贡献规范 | 第三方可发布 skill |

---

## 七、测试与质量保障

### 7.1 测试分层

| 层级 | 内容 | 目标 |
|:---|:---|:---|
| Unit Tests | skill 元数据解析、schema 校验、Agent 决策 | 覆盖率 > 80% |
| Integration Tests | PlanEngine + CodeAct + Execution | 端到端跑通标准数据集 |
| Skill Tests | 每个外部 skill 自带的 `tests/` | 导入时自动运行 |
| Regression Tests | 固定数据集固定参数，检测输出漂移 | 防止 skill 更新破坏结果 |
| Benchmark Tests | 标准任务（PBMC 3k、WGS variant calling 等） | 量化 Agent 能力 |

### 7.2 关键测试数据集

- 单细胞：PBMC 3k / 10x Genomics 官方数据
- 空间转录组：Visium 小鼠大脑
- 基因组：GIAB HG001 WGS
- 宏基因组：16S 示例数据

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|:---|:---|:---|
| 外部 skill 质量参差不齐 | 执行失败、结果不可靠 | 导入时自动测试 + 信任等级 + 社区 review |
| CodeAct 产生危险代码 | 安全漏洞、数据损坏 | 容器隔离 + 命令审计 + 网络限制 + HITL |
| LLM 幻觉导致 plan 错误 | 执行无效流程 | Plan Validation + Human Approval + 检索增强 |
| 自进化引入劣质策略 | 系统行为退化 | 只应用于非锁定 role + 人类审批 + A/B 测试 |
| 性能瓶颈 | 长流程卡顿 | 增量快照、缓存、并行、分布式 worker |
| 依赖冲突 | skill 间环境不兼容 | namespace 隔离 + 容器化 + 项目级 lock |

---

## 九、成功标准

### 9.1 短期（8–10 周）

- [ ] 系统可完成 PBMC 3k 单细胞分析全流程（QC → Normalize → PCA → Cluster → DE → Viz）
- [ ] 至少 90 个外部 skill 可导入并注册
- [ ] CodeAct 可处理至少 5 种非预定义复杂任务
- [ ] Plan 审批流程可用
- [ ] 自进化闭环初步运行（CBKB 有真实数据）

### 9.2 中期（16 周）

- [ ] 支持单细胞、空间、基因组、宏基因组四大领域的标准分析
- [ ] 外部 skill 导入 → 测试 → 启用 → 执行 → 反馈 → 进化全自动化
- [ ] 容器化执行成为默认生产模式
- [ ] Benchmark 显示系统性能随使用逐步提升
- [ ] 第三方开发者可独立发布 skill

### 9.3 长期（6 个月+）

- [ ] 成为生物信息领域领先的通用 Agent 平台
- [ ] 活跃的 skill 生态（1000+ skill）
- [ ] 支持 AIDD、文献辅助、实验设计等跨学科任务
- [ ] 真正的自进化：系统能发现新 workflow 并验证推广

---

## 十、关键决策建议

### 决策 1：是否完全废弃硬编码 domain strategy？

**建议**：保留 `domain.yaml`，但角色从 **“plan 驱动器”** 改为 **“领域引导”**：
- 提供领域术语、意图关键词、推荐 skill 候选集、SOP 种子
- 不强制生成固定 pipeline
- Plan 由检索 + LLM + 执行反馈动态生成

### 决策 2：固定 pipeline 与 CodeAct 如何共存？

**建议**：
- 简单、高频、高确定性任务：固定 pipeline（快、稳定、可审计）
- 复杂、新颖、需要灵活组合的任务：CodeAct（灵活、通用）
- Agent 根据意图复杂度自动选择，用户可手动覆盖

### 决策 3：外部 skill 的信任模型？

**建议**：
- `official`：HomomicsLab 官方维护
- `verified`：通过自动化测试 + 人工 review
- `community`：通过自动化测试
- `experimental`：未测试或测试失败
- 用户可按信任等级过滤启用

### 决策 4：自进化是自动应用还是建议式？

**建议**：
- 参数级、低影响变更：自动应用（如 role metadata 偏好参数）
- Role prompt、SOP 内容变更：建议式，需人类审批
- 所有变更写入 audit log，支持 rollback

---

## 十一、总结

**HomomicsLab 的下一跳不是继续堆功能，而是完成三个关键转身：**

1. **从“带业务 skill 的 Agent 框架” → “Agent 元能力平台”**
   - builtin skill 极简，业务 skill 全部外部化

2. **从“固定 skill pipeline” → “CodeAct + 检索增强规划”**
   - 学习 Biomni，让 Agent 以代码为通用接口灵活组合工具

3. **从“可进化的架构” → “真正自进化的系统”**
   - 把 Interpretation、CBKB、SkillDAG、Reproducibility、Evolution 全部接入主执行链路

**只要完成这三个转身，并快速引入 NanoResearch-Skills、Genomics-Skills 等外部资产，HomomicsLab 就能从当前的先进框架真正成长为生物信息领域的强大通用 Agent 工具。**
