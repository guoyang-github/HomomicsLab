# HomomicsLab 问题诊断与修正计划

> 生成日期: 2026-06-11
> 基于: v0.4.1 全面智能化改进后的深度诊断
> 测试基线: 538 tests passing

---

## 一、问题全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         问题分类矩阵 (8大类, 15项)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  [P0] 核心功能缺陷 — 影响系统可用性                                          │
│  [P1] 架构缺口 — 生产环境阻塞                                                │
│  [P2] 集成缺失 — v2 模块未接入主流程                                         │
│  [P3] 监控盲区 — 执行状态黑盒                                                │
│  [P4] 能力未启用 — 已有功能未利用                                            │
│  [P5] 文档缺口 — 用户无法正确使用                                            │
│  [P6] 架构演进 — 长期方向性改进                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、详细问题清单

### P0: 核心功能缺陷

#### P0-1: PlanEngine 无 LLM Fallback — 无领域知识时生成空洞计划 ✅ 已修复

**症状**: 用户输入不在任何策略的 `applicable_intents` 中时，PlanEngine 匹配到 `GENERIC_ANALYSIS`，生成 `[data_loading, exploratory, analysis, visualization]` 的空洞计划，所有 `selected_skill` 为 `None`，无法执行。

**代码位置**: `agent/plan/engine.py:58` → `strategy_library.select()` → `GENERIC_ANALYSIS`

**影响**: 系统对新领域完全不可用，没有 graceful degradation。

**修复方案（已实施）**:
- 新增 `agent/llm_client.py`：共享异步 OpenAI 客户端，无 key 时优雅降级。
- 新增 `agent/plan/llm_fallback.py`：`LLMFallbackPlanner` 通过语义搜索检索候选 skill，调用 LLM 生成可执行步骤，并验证所有 skill_id。
- 扩展 `PlanResult`：增加 `is_fallback` 和 `suggestion_text` 字段。
- 修改 `PlanEngine.plan()`：当 `strategy.name == "generic"` 时触发 LLM fallback。
- 修改 `TaskDecomposer`：对未知意图调用 `PlanEngine`，将 `PlanResult` 转换为 `TaskTree`；fallback 计划自动附加 HITL checkpoint。
- 修改 `TurnRunner`：识别 suggestion-only 的 fallback tree 并直接返回 TODO_LIST 消息；可执行 fallback 交给 `Orchestrator`。
- 修改 `api/chat.py`：`/send` 复用 `TurnRunner`，保证 HTTP 与 WebSocket 行为一致。
- 新增 5 个测试覆盖 fallback 触发、skill ID 校验、无 API key 降级、PlanResult 结构、TaskDecomposer 集成。

**工作量**: 1 人天（实际）
**优先级**: P0

---

#### P0-2: 实时监控缺失 — 所有执行后端都是黑盒

**症状**:
- `LocalScheduler`: `proc.communicate()` 阻塞等待完成，无任何中间状态
- `SlurmScheduler`: `_poll_job()` 每 5 秒 `sacct` 轮询，但不推送，只记录结果
- `NextflowRunner`: `proc.communicate()` 阻塞等待完成，无 `-with-weblog`
- 前端用户只能看到"执行中..."，不知道进展到哪一步

**代码位置**: `hpc/scheduler.py` 全部三个 Scheduler 的 `execute()` 方法

**影响**: 生产环境完全不可用，用户无法知道任务状态、无法诊断卡住原因。

**修复方案**:
```python
# 阶段 1: 增加 progress callback 机制
class BaseScheduler:
    def __init__(self, working_dir, progress_callback=None):
        self.progress_callback = progress_callback

    async def _report_progress(self, phase, status, progress_pct, logs=None):
        if self.progress_callback:
            await self.progress_callback({
                "job_id": self.current_job_id,
                "phase": phase,
                "status": status,  # PENDING | RUNNING | COMPLETED | FAILED
                "progress": progress_pct,  # 0-100
                "logs": logs or [],
            })

# 阶段 2: Nextflow 启用 -with-weblog
# NextflowRunner.execute():
cmd = ["nextflow", "run", str(nf_file), 
       "-with-weblog", f"{api_base_url}/webhook/nextflow"]

# 阶段 3: WebSocket 推送
# API 层新增:
@app.websocket("/ws/execution/{job_id}")
async def execution_websocket(websocket: WebSocket, job_id: str):
    # 订阅 Redis/内存 中的执行状态
    # 实时推送给前端
```

**工作量**: 3 人天
**优先级**: P0

---

### P1: 架构缺口

#### P1-1: NextflowRunner 只能执行单 process

**症状**: `NextflowRunner._build_nextflow_script()` 生成只有一个 process 的 `.nf` 文件，用大炮（Nextflow）打蚊子（单个 skill）。

**代码位置**: `hpc/scheduler.py:375-405`

**影响**: 无法利用 Nextflow 的 DAG 并行、缓存、断点续跑等核心能力。

**修复方案**:
```python
# 方案 A: 集成 utils-workflow-management-nextflow 技能（推荐）
# 新增 hpc/workflow_translator.py
class WorkflowTranslator:
    """将 PlanResult 翻译为完整 Nextflow 项目"""
    
    async def to_nextflow(self, plan: PlanResult) -> Path:
        # 调用 utils-workflow-management-nextflow 技能
        # 输出: main.nf + modules/ + subworkflows/ + config/
        pass

# 方案 B: 简化版 PlanEngine → Nextflow 翻译器
# 新增 hpc/simple_nf_translator.py
class SimpleNFTranslator:
    """将 PlanResult 翻译为最小 Nextflow DSL2 脚本"""
    
    def translate(self, plan: PlanResult) -> str:
        # 为每个 phase 生成一个 process
        # 用 workflow {} 串联
        pass
```

**工作量**: 2 人天（方案A依赖外部技能）/ 3 人天（方案B自研）
**优先级**: P1

---

#### P1-2: 执行后端自动选择逻辑缺失

**症状**: 没有根据任务特征自动选择 `native` / `slurm` / `nextflow` 的逻辑。当前 `get_scheduler()` 的 `auto` 模式只检查 SLURM 可用性。

**代码位置**: `hpc/scheduler.py:507-513`

**影响**: 用户需要手动选择执行后端，无法根据任务复杂度自动路由。

**修复方案**:
```python
def select_execution_backend(plan: PlanResult, data_state: DataState) -> str:
    n_phases = len([p for p in plan.phases if p.required])
    n_samples = data_state.n_samples or 1
    
    if n_samples > 100 or n_phases > 10:
        return "nextflow"  # 大规模/复杂流程
    elif SlurmScheduler.is_available() and n_samples > 10:
        return "slurm"     # 中等规模 HPC
    else:
        return "local"     # 小规模本地执行
```

**工作量**: 0.5 人天
**优先级**: P1

---

### P2: 集成缺失（v2 模块未接入主流程）

#### P2-1: DataState v2 未替换旧版

**症状**: `models_v2.py` 存在但 `agent/plan/models.py` 仍是旧版（只有 `n_samples` 字段被添加），`domain_state` 命名空间未实际启用。

**代码位置**: `agent/plan/models.py` 仍在使用，`models_v2.py` 未被导入

**影响**: DataState 字段膨胀问题未解决，新领域仍然需要修改 `models.py`。

**修复方案**:
1. 将 `models_v2.py` 内容合并到 `models.py`
2. 更新所有 `StateCheck` 的 lambda 表达式使用 `.get()` API
3. 更新所有测试

**工作量**: 1 人天
**优先级**: P2

---

#### P2-2: IntentAnalyzer v2 未替换旧版

**症状**: `intent_analyzer_v2.py` 存在但 `IntentAnalyzer` 仍使用旧版硬编码关键词。

**代码位置**: `agent/intent_analyzer.py` 仍在使用

**影响**: 新领域需要硬编码修改 Python 代码，无法通过 domain.yaml 动态加载。

**修复方案**:
1. 将 `intent_analyzer.py` 备份为 `intent_analyzer_legacy.py`
2. 将 `intent_analyzer_v2.py` 重命名为 `intent_analyzer.py`
3. 在主模块初始化时 `IntentAnalyzer.use_domain_registry = True`
4. 确保 DomainLoader 加载后自动更新 IntentAnalyzer

**工作量**: 0.5 人天
**优先级**: P2

---

#### P2-3: HotReload 未集成到启动流程

**症状**: `domain/hot_reload.py` 存在但 `main.py` 中没有启动 `DomainHotReloader` 和 `SkillHotReloader`。

**代码位置**: `main.py` 或 `api/server.py` 中没有 hot reload 初始化

**影响**: 运行时修改 domain.yaml 或 skill 不会自动生效，需要重启服务。

**修复方案**:
```python
# 在 main.py 的 startup 事件中
@app.on_event("startup")
async def startup():
    # ... 现有初始化 ...
    
    # 启动热加载
    from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
    from homomics_lab.domain.registry import get_domain_registry
    from homomics_lab.domain.loader import DomainLoader
    from homomics_lab.agent.plan.strategies import StrategyLibrary
    
    domain_reloader = DomainHotReloader(
        get_domain_registry(),
        DomainLoader(skill_registry, StrategyLibrary())
    )
    skill_reloader = SkillHotReloader(skill_registry)
    
    # 监控所有已安装的 domain.yaml
    domains_dir = Path("homomics_lab/domains")
    for domain_yaml in domains_dir.rglob("domain.yaml"):
        domain_reloader.watch_domain(domain_yaml)
    
    # 监控外部技能目录
    if settings.external_skills_dir:
        skill_reloader.watch_skills_directory(settings.external_skills_dir)
    
    await domain_reloader.start()
    await skill_reloader.start()
```

**工作量**: 0.5 人天
**优先级**: P2

---

#### P2-4: CLI 未注册到 pyproject.toml

**症状**: `homomics` CLI 命令存在但无法通过 `pip install` 后直接使用。

**影响**: 用户无法运行 `homomics domain init` 等命令。

**修复方案**:
```toml
# pyproject.toml
[project.scripts]
homics = "homomics_lab.cli.main:main"
```

**工作量**: 5 分钟
**优先级**: P2

---

### P3: 监控盲区

#### P3-1: SLURM 轮询无 WebSocket 推送

**症状**: `_poll_job()` 轮询 `sacct` 但不向客户端推送状态。前端只能等待 HTTP 响应超时。

**修复方案**: 同 P0-2

**工作量**: 已计入 P0-2
**优先级**: P3

---

#### P3-2: 缺乏统一执行状态抽象

**症状**: 三个 Scheduler 各自返回不同的 Dict 格式，没有统一的 `ExecutionState` 模型。

**修复方案**:
```python
@dataclass
class ExecutionState:
    job_id: str
    status: str  # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    current_phase: Optional[str]
    progress_pct: float
    started_at: datetime
    estimated_completion: Optional[datetime]
    resource_usage: Dict[str, Any]  # cpu, memory, disk
    logs: List[str]
    error_message: Optional[str]
    scheduler_type: str  # local | slurm | nextflow
```

**工作量**: 0.5 人天
**优先级**: P3

---

### P4: 能力未启用

#### P4-1: Nextflow 原生监控未利用

**症状**: NextflowRunner 没有启用 `-with-weblog`、`-with-trace`、`-with-timeline`。

**修复方案**: 同 P0-2

**工作量**: 已计入 P0-2
**优先级**: P4

---

#### P4-2: AgentCore 未使用语义搜索路由技能

**症状**: `AgentCore.resolve_agent_for_task()` 只使用显式 skill_id 匹配，没有利用 `SkillRegistry.semantic_search()` 的能力。

**代码位置**: `agent/core/agent_core.py:98-147`

**修复方案**:
```python
# 当 task 没有显式 skills_required 时，使用语义搜索
if skill_id is None and getattr(task, "description", None):
    results = self.skill_registry.semantic_search(task.description, top_k=3)
    if results:
        skill_id = results[0][0].id
```

**工作量**: 0.5 人天
**优先级**: P4

---

### P5: 文档缺口

#### P5-1: operations.md 未更新 CLI 使用说明

**症状**: `docs/operations.md` 没有 `homomics domain init/validate/install/generate/list` 的使用说明。

**修复方案**: 在 operations.md 的"配置指南"后新增"领域扩展"章节。

**工作量**: 0.5 人天
**优先级**: P5

---

#### P5-2: 缺少 v2 模块的 API 文档

**症状**: DataState v2 的 `.get()` / `.set()` API，DomainLoader 的使用方式，都没有文档。

**修复方案**: 在 design.md 中新增"Domain Extension Architecture"章节。

**工作量**: 0.5 人天
**优先级**: P5

---

### P6: 架构演进方向

#### P6-1: PlanEngine 支持复杂 DAG（可选）

**症状**: `phases: List[Phase]` 只能表达线性列表，无法表达 DAG 分支/并行/合并。

**影响**: 复杂分析流程（多分支、大规模并行）无法表达。

**修复方案**: 
```python
# 长期演进方向
@dataclass
class TaskNode:
    id: str
    phase_type: str
    dependencies: List[str]  # DAG 依赖
    skill: Optional[SkillDefinition]
    condition: Optional[str]  # 条件执行
    parallel_group: Optional[str]  # 并行组标识

@dataclass
class PlanResultV2:
    nodes: Dict[str, TaskNode]
    entry_nodes: List[str]
```

**工作量**: 5 人天
**优先级**: P6（长期，非阻塞）

---

## 三、修正计划

### 第一阶段：生产阻塞修复（1 周）

| 编号 | 问题 | 工作量 | 负责人 |
|:---|:---|:---|:---|
| P0-1 | PlanEngine LLM Fallback | 1 天 | — |
| P0-2 | 实时监控机制 | 3 天 | — |
| P2-4 | CLI 注册到 pyproject.toml | 5 分钟 | — |
| P2-2 | IntentAnalyzer v2 替换 | 0.5 天 | — |
| P2-3 | HotReload 集成到 startup | 0.5 天 | — |
| **小计** | | **5 天** | |

**目标**: 系统对新领域有 graceful degradation，用户可以实时看到执行进展。

### 第二阶段：架构补全（1 周）

| 编号 | 问题 | 工作量 | 负责人 |
|:---|:---|:---|:---|
| P2-1 | DataState v2 替换 | 1 天 | — |
| P1-1 | PlanEngine → Nextflow 翻译器 | 2 天 | — |
| P1-2 | 执行后端自动选择 | 0.5 天 | — |
| P3-2 | ExecutionState 统一抽象 | 0.5 天 | — |
| P4-2 | AgentCore 语义搜索路由 | 0.5 天 | — |
| **小计** | | **4.5 天** | |

**目标**: 系统可以自动选择执行后端，复杂流程可以委托 Nextflow 执行。

### 第三阶段：文档完善（2 天）

| 编号 | 问题 | 工作量 | 负责人 |
|:---|:---|:---|:---|
| P5-1 | operations.md CLI 章节 | 0.5 天 | — |
| P5-2 | design.md Domain Architecture | 0.5 天 | — |
| 回归测试 | 全量 538 测试 + 新增测试 | 1 天 | — |
| **小计** | | **2 天** | |

### 第四阶段：架构演进（长期）

| 编号 | 问题 | 工作量 | 时间线 |
|:---|:---|:---|:---|
| P6-1 | PlanEngine DAG 支持 | 5 天 | v0.6.0 |

---

## 四、实施优先级决策矩阵

```
紧急程度
    ↑
 P0-1 │ P0-2 │        │
 LLM  │ 监控  │        │
Fallback│     │        │
──────┼──────┼────────┤
 P2-4 │ P2-2 │ P2-3   │ P2-1
 CLI  │Intent│HotReload│DataState
──────┼──────┼────────┤
      │ P1-1 │ P1-2   │ P3-2
      │Nextflow│自动选择│ExecutionState
      │翻译器 │        │
──────┼──────┼────────┤
      │ P4-2 │ P5-1   │ P5-2
      │语义  │文档    │ 文档
      │搜索  │        │
──────┴──────┴────────┘
   高    中    低   → 影响范围
```

---

## 五、测试覆盖计划

| 模块 | 当前测试 | 需新增测试 | 目标 |
|:---|:---|:---|:---|
| domain (models/loader/registry) | 34 | 0 | ✅ 已完成 |
| PlanEngine LLM Fallback | 5 | 0 | ✅ P0-1 已完成 |
| 执行监控 (ExecutionState) | 0 | 8 | P0-2 + P3-2 |
| NextflowTranslator | 0 | 6 | P1-1 |
| HotReload 集成 | 0 | 4 | P2-3 |
| DataState v2 | 0 | 5 | P2-1 |
| IntentAnalyzer v2 | 0 | 4 | P2-2 |
| 自动后端选择 | 0 | 3 | P1-2 |
| **总计** | **34** | **35** | **→ 573** |

---

## 六、关键决策点

### 决策 1: LLM Fallback 的定位

- **选项 A**: LLM 生成可执行计划（高风险：幻觉技能名、不可审计）
- **选项 B**: LLM 生成 TODO list + 建议（推荐：用户友好、安全可控）

**推荐**: 选项 B

### 决策 2: Nextflow 翻译器的实现路径

- **选项 A**: 集成 `utils-workflow-management-nextflow` 技能（高质量、依赖外部）
- **选项 B**: 自研简化版翻译器（`SimpleNFTranslator`，只生成单文件 main.nf）

**推荐**: 先实现 B（快速可用），再演进 A（生产级）

### 决策 3: 监控推送技术选型

- **选项 A**: WebSocket（实时性好、有状态连接）
- **选项 B**: Server-Sent Events（SSE，单向推送、更简单）
- **选项 C**: 轮询 HTTP API（兼容性最好、实时性差）

**推荐**: SSE（Nextflow weblog 推送 + 后端 SSE 广播，无需 WebSocket 双向连接）
