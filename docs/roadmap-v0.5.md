# HomomicsLab v0.5 优化路线图

## 背景

v0.4.1 已完成以下关键重构：

- `CascadeIntentAnalyzer` 多层意图识别（keyword + embedding + LLM + clarification）
- `TurnRunner` 统一对话轮询
- `PlanEngine` 领域策略驱动的分析计划
- `AgentCore` 动态角色注入（Analyst + Specialist）
- `ExecutionPubSub` + SSE 执行状态推送
- `ReproducibilityEngine` 可复现审计

v0.4.2 新增：

- **跨进程工具调用沙盒** (`tools/invoke_tool.py`)：支持 `local`/`bubblewrap`/`container` 后端
- **CodeAct 代码缓存** (`execution/code_cache.py`)：基于任务描述 embedding 相似度复用生成代码
- **自动回归基线**：CodeAct 成功执行后自动记录基线
- **前端“保存为 Skill”按钮**：将成功 CodeAct 运行提升为可复用技能包
- **领域模板市场** (`domain/marketplace.py` + `api/domains.py` + 前端 Domains 标签页)

当前测试基线：**901 passed, 8 warnings**。

v0.5 的目标是把系统从“对话式同步执行”升级为“可后台运行、可阶段校验、可多人机协作、可审计复现”的生产级生物信息学 Agent 平台。

---

## 一、长程任务后台执行

### 目标
- HTTP `/api/chat/send` 不再阻塞在完整 workflow 执行上。
- 复杂/长程任务提交后立即可返回 `job_id`，客户端通过 SSE 订阅进度。
- Worker 支持本地内存队列和后续替换为 Redis/RabbitMQ。

### 关键改动

| 新增/修改 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/homomics_lab/jobs/models.py` | `JobRecord`、`JobStatus` 模型 |
| 新增 | `backend/homomics_lab/jobs/queue.py` | `JobQueue`，先内存 + SQLite 持久化 |
| 新增 | `backend/homomics_lab/jobs/worker.py` | `ExecutionWorker`，dequeue 后调用 Orchestrator |
| 新增 | `backend/homomics_lab/jobs/store.py` | Job 状态持久化存储 |
| 新增 | `backend/homomics_lab/api/jobs.py` | `/jobs/{job_id}/status`、`/jobs/{job_id}/cancel` |
| 修改 | `backend/homomics_lab/agent/turn_runner.py` | 复杂任务入队，短任务仍同步执行 |
| 修改 | `backend/homomics_lab/main.py` | lifespan 启动 worker background task |

### 验收标准
- `/api/chat/send` 提交“帮我分析这组单细胞数据”在 < 200ms 内返回 `job_id`。
- SSE `/api/execution/{job_id}/events` 能收到 `QUEUED → PENDING → RUNNING → COMPLETED/AWAITING_HUMAN`。
- 单元测试覆盖：enqueue → worker execute → status update → SSE。

### 优先级 / 预估
**P0，1-2 周**

---

## 二、复杂任务防跑偏：Phase Gate + 自动 Replan

### 目标
- 每个 phase 执行后自动校验输出是否符合预期（success criteria）。
- 不符合时自动 replan 或升级 HITL，而不是继续跑错下一步。
- 保留历史快照，支持回滚到上一 phase。

### 关键改动

| 新增/修改 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/homomics_lab/execution/phase_gate.py` | `PhaseGate`：按 success criteria 评估输出 |
| 新增 | `backend/homomics_lab/execution/snapshot.py` | 每个 phase 前的数据快照 |
| 修改 | `backend/homomics_lab/agent/plan/models.py` | `Phase` 增加 `success_criteria` |
| 修改 | `backend/homomics_lab/agent/task_decomposer.py` | 把 criteria 写入 `TaskNode` |
| 修改 | `backend/homomics_lab/agent/orchestrator.py` | 执行后调用 Phase Gate，失败则触发 replan/HITL |
| 修改 | `backend/homomics_lab/agent/plan/replanning.py` | 接入 DataState 和失败原因，生成修复 plan |
| 修改 | `backend/homomics_lab/hitl/detector.py` | 增加“连续失败升级”和“gate 失败”触发器 |

### 验收标准
- 单细胞 pipeline 中 QC 输出过滤率异常（如 > 60%）时，流程暂停并给出 HITL/replan 建议。
- Replan 后能生成新的 `TaskTree`，保留已完成步骤，只修改下游。
- 测试覆盖 gate pass、gate fail、replan success、HITL escalation。

### 优先级 / 预估
**P0，2 周**

---

## 三、Plan 与 TODO List 解耦

### 目标
- `PlanResult` 成为版本化、可审批、可审计的执行契约。
- `TODO_LIST` 只是 Plan 的前端投影，支持实时刷新进度。
- LLM fallback 生成的 plan 必须经过人类批准才可执行。

### 关键改动

| 新增/修改 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/homomics_lab/plan/store.py` | `PlanStore`：Plan 版本化存储 |
| 新增 | `backend/homomics_lab/plan/presenter.py` | `PlanPresenter`：Plan → TODO_LIST / PARAMETER_FORM |
| 新增 | `backend/homomics_lab/api/plan.py` | `/plan/{plan_id}/approve`、`/plan/{plan_id}/reject`、`/plan/{plan_id}/versions` |
| 修改 | `backend/homomics_lab/agent/turn_runner.py` | 复杂任务生成 Plan → 等待批准 → 入队执行 |
| 修改 | `backend/homomics_lab/models/common.py` | `MessageType` 增加 `PLAN_REQUEST` |

### 验收标准
- 用户收到“分析计划已生成，请确认后执行”消息，点击确认后任务才入队。
- Plan 修改（如 HITL 调整参数）生成新版本，旧版本保留在 `PlanStore`。
- 可复现 bundle 包含所有 plan 版本和批准记录。

### 优先级 / 预估
**P0，1-2 周**

---

## 四、Multi-Agent：Supervisor-Worker-Reviewer

### 目标
- 把 `AgentCore` 升级为 `SupervisorAgent`，统一负责规划、委派、评审、重规划。
- 引入独立的 `Reviewer` 角色，对高风险/异常步骤做独立校验。
- 新增 `AgentMessageBus`，支持 Supervisor ↔ Worker ↔ Reviewer 的异步消息。

### 关键改动

| 新增/修改 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/homomics_lab/agent/supervisor.py` | `SupervisorAgent`：plan / delegate / review / replan |
| 新增 | `backend/homomics_lab/agent/core/roles/reviewer.yaml` | Reviewer 角色定义 |
| 新增 | `backend/homomics_lab/agent/message_bus.py` | `AgentMessageBus`：agent 间消息总线 |
| 新增 | `backend/homomics_lab/agent/worker_result.py` | `WorkerResult`：结构化执行结果 |
| 修改 | `backend/homomics_lab/agent/core/agent_core.py` | 保留兼容，逐步把能力迁移到 Supervisor |
| 修改 | `backend/homomics_lab/agent/orchestrator.py` | 执行结果交给 Reviewer，必要时触发 replan |
| 修改 | `backend/homomics_lab/agent/factory.py` | 默认注册 Supervisor + Worker + Reviewer |

### 验收标准
- clustering 参数被用户自定义后，Reviewer 校验并可能要求重新确认。
- Worker 执行失败 2 次后自动升级给 Supervisor replan，再失败转 HITL。
- 新增 `test_supervisor.py` 覆盖 delegate → execute → review → replan 全链路。

### 优先级 / 预估
**P1，2-3 周**

---

## 五、轻量 Group Chat / Debate 补充

### 目标
- 只在**意图歧义、Plan 选择、异常解释**等场景触发短轮 debate。
- 不替代 SWR 主架构，避免 token 浪费和错误共识。

### 关键改动

| 新增/修改 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/homomics_lab/agent/debate.py` | `LightweightDebate`：1-2 轮，Supervisor 最终决策 |
| 新增 | `backend/homomics_lab/agent/core/roles/domain_expert.yaml` | 可选的辩论参与者 |
| 修改 | `backend/homomics_lab/agent/intent/analyzer.py` | 低置信度 intent 触发 debate |
| 修改 | `backend/homomics_lab/agent/plan/engine.py` | 多候选 strategy 时可选 debate |
| 修改 | `backend/homomics_lab/agent/interpretation.py` | 异常解释可引入 debate |

### 验收标准
- “分析数据”这种歧义输入触发 debate，输出 2-3 个候选意图供用户选择。
- debate 最多 2 轮，最终由 Supervisor 决策并写入审计日志。

### 优先级 / 预估
**P2，1-2 周**

---

## 实施路线图

| 阶段 | 状态 | 时间 | 任务 | 依赖 |
|---|---|---|---|---|
| **P0-1** | ✅ 已完成 | 2025-06-13 | 长程任务后台执行（Job Queue + Worker） | 无 |
| **P0-2** | ✅ 已完成 | 2026-06-10 | Plan 与 TODO 解耦（PlanStore + 审批） | P0-1 |
| **P0-3** | ✅ 已完成 | 2026-06-10 | Phase Gate + 自动 Replan | P0-1, P0-2 |
| **P1-1** | ✅ 已完成 | 2026-06-10 | Supervisor-Worker-Reviewer | P0-1, P0-3 |
| **P1-2** | ✅ 已完成 | 2026-06-10 | Plan 版本化 UI + HITL 升级界面 | P0-2, P1-1 |
| **P2** | ✅ 已完成 | 2026-06-10 | 轻量 Debate | P1-1 |
| **定时任务** | ✅ 已完成 | 2026-06-10 | APScheduler + CBKB 夜间整理 | — |
| **MCP 工具** | ✅ 已完成 | 2026-06-10 | Agent 调用 MCP Tools（PubMed/GEO/UniProt） | — |
| **P3** | 🔄 进行中 | 1-2 周 | Redis Job Queue + 分布式 Worker | P0-1 |

## P0-2 实施摘要

已完成文件：
- `backend/homomics_lab/database/models.py`（新增 `PlanRecord`）
- `backend/homomics_lab/plan/__init__.py`
- `backend/homomics_lab/plan/models.py`
- `backend/homomics_lab/plan/store.py`
- `backend/homomics_lab/plan/presenter.py`
- `backend/homomics_lab/agent/plan/models.py`（PlanResult 序列化）
- `backend/homomics_lab/agent/task_decomposer.py`（`decompose_with_plan`）
- `backend/homomics_lab/agent/turn_runner.py`（`AWAITING_PLAN_APPROVAL`）
- `backend/homomics_lab/api/chat.py`（返回 plan / plan_id）
- `backend/homomics_lab/api/plan.py`（`/plan/{id}/approve`、`/plan/{id}`、`/plan/{id}/versions`）
- `backend/homomics_lab/api/router.py`
- `backend/homomics_lab/main.py`（`app.state.plan_store`）
- `backend/homomics_lab/reproducibility/bundle.py`（`plan_id`、`plan_result`）
- `backend/homomics_lab/reproducibility/engine.py`（`record_plan` 支持 plan）
- 新增/更新测试：`tests/test_plan/*`、`tests/test_api/test_plan_api.py`、`tests/test_reproducibility/test_engine.py`、`tests/test_agent/test_turn_runner.py`

验证结果：
```bash
pytest --ignore=tests/test_context/test_semantic_memory.py --ignore=tests/test_skills/test_semantic_memory.py --ignore=tests/test_skills/test_semantic_search_v2.py
# 622 passed, 7 warnings
```

---

## P0-1 实施摘要

已完成文件：
- `backend/homomics_lab/database/base.py`
- `backend/homomics_lab/database/models.py`
- `backend/homomics_lab/jobs/constants.py`
- `backend/homomics_lab/jobs/models.py`
- `backend/homomics_lab/jobs/repository.py`
- `backend/homomics_lab/jobs/queue.py`
- `backend/homomics_lab/jobs/runner.py`
- `backend/homomics_lab/jobs/service.py`
- `backend/homomics_lab/agent/orchestrator.py`（进度推送）
- `backend/homomics_lab/agent/turn_runner.py`（`execute_tree`、`QUEUED` mode、progress callback）
- `backend/homomics_lab/api/chat.py`（入队 + HITL resume）
- `backend/homomics_lab/api/execution.py`（`/status` 端点）
- `backend/homomics_lab/main.py`（lifespan 启动 worker）
- 新增/更新测试：`tests/test_jobs/*`、`tests/test_api/test_chat.py`、`tests/test_api/test_hitl_api.py`、`tests/test_api/test_execution_status.py`

验证结果：
```bash
pytest --ignore=tests/test_context/test_semantic_memory.py --ignore=tests/test_skills/test_semantic_search_v2.py
# 612 passed, 7 warnings
```

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Job Queue 引入后状态管理复杂 | 高 | 先 SQLite 持久化，验证稳定后再切 Redis |
| Phase Gate 规则过严导致误拦截 | 中 | criteria 默认阈值从宽松开始，可配置 |
| Reviewer 增加延迟 | 中 | 只对高风险/异常步骤触发 Reviewer |
| Debate 导致 token 成本飙升 | 中 | 严格限制 2 轮 + 只在歧义场景触发 |
| Plan 审批打断用户体验 | 低 | 对已知 workflow 可设“ trusted mode”自动批准 |

---

## 预期收益

1. **响应体验**：HTTP 请求从秒级/分钟级降到毫秒级。
2. **执行可靠性**：Phase Gate + Replan 把错误拦截在发生时，而不是最后。
3. **可控性**：Plan 审批 + HITL 升级让用户始终掌握关键决策。
4. **可扩展性**：SWR 架构支持未来接入更多 specialist（spatial、metagenomics、report）。
5. **可审计性**：Plan 版本、Agent 消息、执行快照全部进入 Reproducibility Bundle。

---

## 下一步建议

P0-1、P0-2、P0-3、P1-1、P1-2、P2 及 v0.4.2 增强项均已完成。当前建议进入：

1. **P3 收尾**：Redis Job Queue + 分布式 Worker（已完成框架，待生产验证）。
2. **个人用户上车体验**：本地模型默认、示例数据集、引导式首屏。
3. **技能生态填充**：引入/编写覆盖单细胞、空间、基因组、宏基因组的高质量 skill。
4. **自进化闭环验证**：在积累足够执行历史后启用 `HOMOMICS_CURATION_ENABLED` 和 `HOMOMICS_EVOLUTION_ENABLED`，观察 CBKB 与 AgentEvolution 的实际效果。
